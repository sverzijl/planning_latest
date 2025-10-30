"""Test EXACT data that UI receives for Daily Snapshot.

This mimics the exact code path in ui/components/daily_snapshot.py
to discover what the UI is actually seeing.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
from datetime import timedelta

# Load data
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

# EXACT UI code path
adapted = adapt_optimization_results(
    model=model,
    result={'result': result},
    inventory_snapshot_date=inventory.snapshot_date
)

print(f"\n{'=' * 80}")
print("TESTING EXACT UI RENDERING PATH")
print(f"{'=' * 80}")

# Import the EXACT function the UI calls
from ui.components.daily_snapshot import _generate_snapshot_for_date

# This is what the UI calls
locations_dict = {loc.id: loc for loc in locations}
snapshot_date = start + timedelta(days=1)  # Day 2

snapshot_data = _generate_snapshot_for_date(
    snapshot_date=snapshot_date,
    results=adapted,
    locations_dict=locations_dict,
    forecast=forecast
)

print(f"\nSnapshot data returned to UI:")
print(f"  Date: {snapshot_data['date']}")
print(f"  Total inventory: {snapshot_data['total_inventory']:,.0f} units")
print(f"  Locations: {len(snapshot_data['location_inventory'])}")

# Check what's in location_inventory
location_inv = snapshot_data['location_inventory']
print(f"\nLocation inventory structure:")
for loc_id, inv_data in list(location_inv.items())[:3]:
    print(f"\n  {loc_id}:")
    print(f"    total: {inv_data.get('total', 0):.0f}")
    print(f"    by_product keys: {list(inv_data.get('by_product', {}).keys())}")
    print(f"    batches keys: {list(inv_data.get('batches', {}).keys())}")

    batches = inv_data.get('batches', {})
    if batches:
        first_product = list(batches.keys())[0]
        print(f"    Sample product '{first_product[:30]}': {len(batches[first_product])} batches")
    else:
        print(f"    ❌ BATCHES DICT IS EMPTY!")

print(f"\n{'=' * 80}")

# Check if this matches what validator saw
if snapshot_data['total_inventory'] <= 0:
    print("❌ ISSUE CONFIRMED: UI receives zero inventory")
elif not any(inv_data.get('batches') for inv_data in location_inv.values()):
    print("❌ ISSUE CONFIRMED: UI receives no batch details (can't render product breakdown)")
else:
    print("✅ UI receives correct inventory data")
