"""
Diagnose why demand isn't being satisfied.

Check:
1. What demand locations exist
2. What legs go to those locations
3. Whether breadrooms have incoming legs
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
print("DEMAND SATISFACTION DIAGNOSTIC")
print("=" * 80)

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
    allow_shortages=False,
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

print("\n" + "=" * 80)
print("DEMAND LOCATIONS")
print("=" * 80)

demand_locations = set()
for (dest, prod, date), qty in model.demand.items():
    demand_locations.add(dest)

print(f"Locations with demand: {sorted(demand_locations)}")
print(f"Total demand locations: {len(demand_locations)}")

print("\n" + "=" * 80)
print("LEGS TO DEMAND LOCATIONS")
print("=" * 80)

for dest in sorted(demand_locations):
    legs_to_dest = model.legs_to_location.get(dest, [])

    print(f"\n{dest}:")
    if legs_to_dest:
        print(f"  Incoming legs: {len(legs_to_dest)}")
        for (origin, d) in legs_to_dest[:5]:  # Show first 5
            transit = model.leg_transit_days.get((origin, d), 'unknown')
            print(f"    {origin} → {d} ({transit} days)")
    else:
        print(f"  ❌ NO INCOMING LEGS!")

print("\n" + "=" * 80)
print("ALL NETWORK LEGS")
print("=" * 80)

print(f"Total legs in model: {len(model.leg_keys)}")
print(f"\nLeg destinations:")
leg_destinations = set()
for (origin, dest) in model.leg_keys:
    leg_destinations.add(dest)

print(f"  {sorted(leg_destinations)}")

print("\n" + "=" * 80)
print("MISSING LEGS TO DEMAND LOCATIONS")
print("=" * 80)

missing = demand_locations - leg_destinations

if missing:
    print(f"❌ CRITICAL: {len(missing)} demand locations have NO incoming legs:")
    for loc in sorted(missing):
        # Count demand at this location
        total_demand = sum(qty for (d, p, date), qty in model.demand.items() if d == loc)
        print(f"  {loc}: {total_demand:,.0f} units of demand")
else:
    print(f"✅ All demand locations have incoming legs")

print("\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)

if missing:
    print(f"\n⚠️  ROOT CAUSE IDENTIFIED:")
    print(f"  {len(missing)} breadroom locations have demand but NO incoming legs")
    print(f"  This means the model CANNOT satisfy their demand via leg shipments")
    print(f"  The inventory balance constraint will be violated")
    print(f"\nMISSING LEGS:")
    for loc in sorted(missing):
        print(f"  Need legs TO {loc}")
else:
    print(f"✅ Demand structure looks correct")

print("\n" + "=" * 80)
