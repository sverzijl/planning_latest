"""Check if initial inventory exceeds pallet storage bounds.

Hypothesis: Pallet integer variables have bounds (0, 62 pallets)
If initial inventory at any location exceeds 62 * 320 = 19,840 units,
the pallet ceiling constraint becomes infeasible.
"""
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

# Convert to 3-tuple
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    inv_2tuple = inventory_snapshot.to_optimization_dict()
    initial_inv_dict = {}
    for (location, product), quantity in inv_2tuple.items():
        initial_inv_dict[(location, product, 'ambient')] = quantity
else:
    initial_inv_dict = {}

print("Checking if initial inventory exceeds pallet bounds...")
print(f"\nPallet bounds: 0-62 pallets")
print(f"Max capacity per location: 62 pallets × 320 units/pallet = 19,840 units")

# Aggregate by location
location_totals = {}
for (loc, prod, state), qty in initial_inv_dict.items():
    location_totals[loc] = location_totals.get(loc, 0) + qty

print(f"\nInitial inventory by location:")
for loc, total in sorted(location_totals.items(), key=lambda x: x[1], reverse=True):
    pallets_needed = total / 320
    print(f"  {loc}: {total:>8,.0f} units = {pallets_needed:>6.2f} pallets", end="")
    if total > 19840:
        print(f"  *** EXCEEDS BOUND! Need {pallets_needed:.0f} but max is 62 ***")
    elif pallets_needed > 60:
        print(f"  (WARNING: Close to limit)")
    else:
        print()

print(f"\nIf any location exceeds 19,840 units, pallet ceiling constraint is INFEASIBLE")
