"""Test sliding window model with 4-week horizon (production scenario)."""
from datetime import date, timedelta
import time
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel

print("=" * 80)
print("SLIDING WINDOW MODEL - 4-WEEK TEST (PRODUCTION SCENARIO)")
print("=" * 80)

# Parse data (same as integration test)
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Convert to unified format
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    forecast=forecast
)

# Get products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
from src.models.product import Product
products = {pid: Product(id=pid, sku=pid, name=pid, units_per_mix=400) for pid in product_ids}

# Get initial inventory (simplified - skip for now)
initial_inv = None

print(f"\n📁 Data loaded:")
print(f"  Nodes: {len(nodes)}")
print(f"  Routes: {len(unified_routes)}")
print(f"  Products: {len(products)}")

# Build 4-WEEK model (full production scenario)
start = date(2025, 10, 27)
end = start + timedelta(weeks=4) - timedelta(days=1)  # 4 weeks

print(f"\n📅 Planning horizon: {start} to {end} (4 weeks, 28 days)")

# Create model
build_start = time.time()
model = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_params,
    products=products,
    start_date=start,
    end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv.to_optimization_dict() if initial_inv else None,
    inventory_snapshot_date=start,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=False  # Disable for now
)

print("\n🔨 Building model...")
pyomo_model = model.build_model()
build_time = time.time() - build_start

print(f"✅ Model built in {build_time:.2f}s")

# Count variables
from pyomo.environ import Var
num_vars = sum(1 for _ in pyomo_model.component_data_objects(Var))
print(f"  Total variables: {num_vars:,}")

# Solve
print("\n🚀 Solving 4-week horizon with HiGHS...")
print(f"  Target: <2 minutes (vs cohort's 6-8 minutes)")

solve_start = time.time()
result = model.solve(
    solver_name='appsi_highs',
    time_limit_seconds=300,  # 5 min max
    mip_gap=0.02,  # 2% gap
    tee=False
)
solve_time = time.time() - solve_start

print(f"\n✅ SOLVE COMPLETE")
print(f"  Status: {result.termination_condition}")
print(f"  Build time: {build_time:.1f}s")
print(f"  Solve time: {solve_time:.1f}s")
print(f"  TOTAL time: {build_time + solve_time:.1f}s")
if result.objective_value:
    print(f"  Objective: ${result.objective_value:,.2f}")

# Extract solution
solution = model.get_solution()
if solution:
    print(f"\n📊 SOLUTION QUALITY:")
    print(f"  Total production: {solution.get('total_production', 0):,.0f} units")
    print(f"  Total shortage: {solution.get('total_shortage_units', 0):,.0f} units")
    print(f"  Fill rate: {solution.get('fill_rate', 0) * 100:.1f}%")

    # Check state flows
    thaw_total = sum(solution.get('thaw_flows', {}).values())
    freeze_total = sum(solution.get('freeze_flows', {}).values())
    print(f"  Thaw flows: {thaw_total:,.0f} units")
    print(f"  Freeze flows: {freeze_total:,.0f} units")

    # Performance comparison
    print(f"\n⚡ PERFORMANCE:")
    print(f"  Sliding window: {solve_time:.1f}s")
    print(f"  Cohort model: ~400s (baseline)")
    if solve_time > 0:
        speedup = 400 / solve_time
        print(f"  Speedup: {speedup:.1f}×")

    if solve_time < 120:
        print(f"\n🎯 SUCCESS! <2 minute target ACHIEVED!")
    else:
        print(f"\n⚠️  Solve time: {solve_time:.1f}s (target was <120s)")
