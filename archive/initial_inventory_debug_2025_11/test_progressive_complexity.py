"""Progressive complexity test - Find where waste penalty breaks.

Start simple (works), add complexity until it breaks.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import timedelta, date

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

# Strong waste penalty
cost_params.waste_cost_multiplier = 100.0

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("PROGRESSIVE COMPLEXITY TEST")
print("="*80)
print("Finding where waste penalty stops working...")
print()

# Test different horizons
horizons_to_test = [2, 3, 4, 7, 14, 21, 28]

for days in horizons_to_test:
    end = start + timedelta(days=days)

    # Test WITHOUT initial inventory first
    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params,
        start_date=start, end_date=end,
        truck_schedules=unified_trucks,
        initial_inventory=None,  # NO initial inventory
        inventory_snapshot_date=start,
        allow_shortages=True,
        use_pallet_tracking=False,
        use_truck_pallet_tracking=False
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.05, tee=False)

    if result.is_optimal() or result.is_feasible():
        solution = model.get_solution()

        last_day = end - timedelta(days=1)
        end_inv = sum(qty for (n, p, s, d), qty in solution.inventory_state.items() if d == last_day)

        status = "✅ ZERO" if end_inv < 10 else f"❌ {end_inv:,.0f} units"

        print(f"  {days:2d} days: End inventory = {status}")

        if end_inv > 1000:
            print(f"          ^^^ BREAKS HERE! Investigating...")

            # Check if it's a solve quality issue
            print(f"          Termination: {result.termination_condition}")
            print(f"          Shortage: {solution.total_shortage_units:,.0f}")

            # This is the breaking point - investigate why
            if days == 3 or days == 4:
                print(f"\n  Breaking point found at {days} days")
                print(f"  Will investigate this specific case...")
            break
    else:
        print(f"  {days:2d} days: INFEASIBLE")

print("\n" + "="*80)
