"""
Check if hubs are included in the inventory_ambient_index.

This will help determine if the inventory balance constraint
is even being created for hub locations.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("HUB INVENTORY INDEX CHECK")
print("=" * 80)

print("\nLoading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

product_ids = sorted(set(e.product_id for e in forecast.entries))

# Create initial inventory
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

print("\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

print(f"\n{'=' * 80}")
print("INVENTORY INDEX SETS")
print("=" * 80)

print(f"\nInventory locations: {sorted(model.inventory_locations)}")
print(f"Total inventory locations: {len(model.inventory_locations)}")

print(f"\n{'=' * 80}")
print("AMBIENT INVENTORY INDEX")
print("=" * 80)

# Check which locations have ambient inventory index entries
locations_in_ambient_index = set()
for (loc, prod, date) in model.inventory_ambient_index_set:
    locations_in_ambient_index.add(loc)

print(f"\nLocations in ambient inventory index: {sorted(locations_in_ambient_index)}")
print(f"Total: {len(locations_in_ambient_index)}")

# Check hubs specifically
hubs = {'6104', '6125'}
print(f"\n{'=' * 80}")
print("HUB STATUS")
print("=" * 80)

for hub in sorted(hubs):
    print(f"\n{hub}:")
    print(f"  In inventory_locations? {hub in model.inventory_locations}")
    print(f"  In ambient_index? {hub in locations_in_ambient_index}")

    # Check if hub has demand
    hub_demand = sum(v for (loc, p, d), v in model.demand.items() if loc == hub)
    print(f"  Has demand? {hub_demand > 0} ({hub_demand:,.0f} units)")

    # Check if hub has outgoing legs
    outgoing_legs = [(o, d) for (o, d) in model.leg_keys if o == hub]
    print(f"  Has outgoing legs? {len(outgoing_legs) > 0} ({len(outgoing_legs)} legs)")
    if outgoing_legs:
        for (o, d) in outgoing_legs:
            print(f"    {o} → {d}")

    # Check if hub has incoming legs
    incoming_legs = [(o, d) for (o, d) in model.leg_keys if d == hub]
    print(f"  Has incoming legs? {len(incoming_legs) > 0} ({len(incoming_legs)} legs)")

    # Count index entries for this hub
    hub_index_count = sum(1 for (loc, p, d) in model.inventory_ambient_index_set if loc == hub)
    print(f"  Ambient index entries: {hub_index_count}")

print(f"\n{'=' * 80}")
print("DESTINATIONS vs INVENTORY LOCATIONS")
print("=" * 80)

print(f"\nDestinations: {sorted(model.destinations)}")
print(f"Inventory locations: {sorted(model.inventory_locations)}")

# Check if there's a difference
dest_not_in_inv = set(model.destinations) - set(model.inventory_locations)
inv_not_in_dest = set(model.inventory_locations) - set(model.destinations)

if dest_not_in_inv:
    print(f"\n⚠️  Destinations NOT in inventory_locations: {sorted(dest_not_in_inv)}")
if inv_not_in_dest:
    print(f"\n✅ Inventory locations NOT in destinations: {sorted(inv_not_in_dest)}")

print(f"\n{'=' * 80}")
