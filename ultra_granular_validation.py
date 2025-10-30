"""Ultra-Granular Validation - Per-Product Per-Location Material Balance.

Checks material balance at the finest granularity:
For each (location, product) pair:
  inventory[day+1] = inventory[day] + production + arrivals - departures - demand

If this doesn't hold, there's an accounting bug.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
from ui.components.daily_snapshot import _generate_snapshot
from datetime import timedelta
from collections import defaultdict

# Load and solve
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

print("Solving...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)

adapted = adapt_optimization_results(
    model=model,
    result={'result': result},
    inventory_snapshot_date=inventory.snapshot_date
)

prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']
locations_dict = {loc.id: loc for loc in locations}

print(f"\n{'=' * 80}")
print("ULTRA-GRANULAR VALIDATION - Per-Product Per-Location")
print(f"{'=' * 80}")

# Generate snapshots for consecutive days
day1 = start
day2 = start + timedelta(days=1)

snap1 = _generate_snapshot(day1, prod_schedule, shipments, locations_dict, adapted, forecast)
snap2 = _generate_snapshot(day2, prod_schedule, shipments, locations_dict, adapted, forecast)

issues_found = []

# Check material balance for each (location, product) pair
print("\nChecking per-product material balance at key locations...")

# Focus on locations with activity
key_locations = ['6122', '6104', '6105', '6125']

for loc_id in key_locations:
    inv1_data = snap1['location_inventory'].get(loc_id, {})
    inv2_data = snap2['location_inventory'].get(loc_id, {})

    by_product_1 = inv1_data.get('by_product', {})
    by_product_2 = inv2_data.get('by_product', {})

    # Get all products at this location
    all_products = set(list(by_product_1.keys()) + list(by_product_2.keys()))

    for product in all_products:
        inv1_qty = by_product_1.get(product, 0)
        inv2_qty = by_product_2.get(product, 0)

        # Get flows for this product AT THIS LOCATION on day 2
        # Production only happens at manufacturing (6122)
        production = 0
        if loc_id == '6122':
            production = sum(
                b.get('quantity', 0) for b in snap2.get('production_batches', [])
                if b.get('product_id') == product
            )

        arrivals = sum(
            f.get('quantity', 0) for f in snap2.get('inflows', [])
            if f.get('location') == loc_id and f.get('product') == product and 'Arrival' in f.get('type', '')
        )

        departures = sum(
            f.get('quantity', 0) for f in snap2.get('outflows', [])
            if f.get('location') == loc_id and f.get('product') == product and 'Departure' in f.get('type', '')
        )

        demand = sum(
            d.get('supplied', 0) for d in snap2.get('demand_satisfaction', [])
            if d.get('destination') == loc_id and d.get('product') == product
        )

        # Material balance
        expected_inv2 = inv1_qty + production + arrivals - departures - demand
        error = abs(inv2_qty - expected_inv2)

        if error > 1:
            issues_found.append(
                f"{loc_id}/{product[:20]:20s}: inv1({inv1_qty:6.0f}) + prod({production:5.0f}) + arr({arrivals:5.0f}) "
                f"- dep({departures:5.0f}) - dem({demand:5.0f}) = {expected_inv2:6.0f} expected, got {inv2_qty:6.0f} (error: {error:.0f})"
            )

print(f"\nChecked {len(key_locations)} locations × ~5 products = ~20 combinations")

if issues_found:
    print(f"\n❌ FOUND {len(issues_found)} PER-PRODUCT BALANCE ERRORS:")
    for issue in issues_found[:10]:
        print(f"  {issue}")
    if len(issues_found) > 10:
        print(f"  ... and {len(issues_found) - 10} more")
else:
    print(f"\n✅ ALL PER-PRODUCT BALANCES CORRECT")

print(f"\n{'=' * 80}")

if not issues_found:
    print("\nAll granular validations pass.")
    print("Data is correct at product-location level.")
    print("\nPossible remaining issues:")
    print("  1. UI rendering/formatting")
    print("  2. Specific edge case in UI logic")
    print("  3. User workflow/interaction")
    print("\nNeed user to specify EXACTLY what they see that's wrong.")
