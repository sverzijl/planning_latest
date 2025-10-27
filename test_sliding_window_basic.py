"""Basic test of sliding window model (core constraints only)."""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel

print("=" * 80)
print("SLIDING WINDOW MODEL - BASIC TEST (1 WEEK)")
print("=" * 80)

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Extract products from forecast
from collections import defaultdict
demand_dict = defaultdict(float)
for entry in forecast.entries:
    key = (entry.location_id, entry.product_id, entry.forecast_date)
    demand_dict[key] += entry.quantity

# Get unique products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
from src.models.product import Product
products = {pid: Product(id=pid, sku=pid, name=pid, units_per_mix=400) for pid in product_ids}

print(f"\n📁 Data loaded:")
print(f"  Locations: {len(locations)}")
print(f"  Routes: {len(routes)}")
print(f"  Products: {len(products)}")
print(f"  Demand entries: {len(demand_dict)}")

# Build 1-week model (fast test)
start = date(2025, 10, 27)
end = start + timedelta(days=6)  # 7 days

print(f"\n📅 Planning horizon: {start} to {end} (1 week)")

# Create model
model = SlidingWindowModel(
    locations=locations,
    routes=routes,
    products=products,
    demand=dict(demand_dict),
    truck_schedules=truck_schedules,
    labor_calendar=labor_calendar,
    cost_structure=cost_params,
    start_date=start,
    end_date=end,
    initial_inventory=None,  # Start from scratch for simplicity
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=False  # Disable for basic test
)

print("\n🔨 Building model...")
try:
    pyomo_model = model.build()
    print("✅ Model built successfully!")

    # Count variables
    from pyomo.environ import Var
    num_vars = sum(1 for _ in pyomo_model.component_data_objects(Var))
    print(f"  Total variables: {num_vars:,}")

    # Try solving (with HiGHS if available)
    print("\n🚀 Solving...")
    result = model.solve(
        solver_name='appsi_highs',
        time_limit_seconds=60,
        mip_gap=0.05,
        tee=False
    )

    print(f"\n✅ SOLVE COMPLETE")
    print(f"  Status: {result.termination_condition}")
    print(f"  Solve time: {result.solve_time:.1f}s")
    print(f"  Objective: ${result.objective_value:,.2f}" if result.objective_value else "  Objective: N/A")

    # Extract solution
    solution = model.get_solution()
    if solution:
        print(f"\n📊 SOLUTION:")
        print(f"  Total production: {solution.get('total_production', 0):,.0f} units")
        print(f"  Total shortage: {solution.get('total_shortage_units', 0):,.0f} units")
        print(f"  Fill rate: {solution.get('fill_rate', 0) * 100:.1f}%")

        # Check state flows
        thaw_total = sum(solution.get('thaw_flows', {}).values())
        freeze_total = sum(solution.get('freeze_flows', {}).values())
        print(f"  Thaw flows: {thaw_total:,.0f} units")
        print(f"  Freeze flows: {freeze_total:,.0f} units")

        print(f"\n🎯 SUCCESS! Sliding window model works!")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
