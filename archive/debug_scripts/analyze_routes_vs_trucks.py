"""Detailed analysis of which routes and dates have truck loads vs not.

This will show us exactly which (dest, product, date) combinations
have truck loads and which don't.
"""

import sys
from pathlib import Path
from datetime import date
from collections import defaultdict

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
full_forecast = forecast_parser.parse_forecast()

# Small test
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 15)
products_to_keep = ['168846', '168847']
locations_to_keep = ['6104', '6110']

test_entries = [
    entry for entry in full_forecast.entries
    if (entry.forecast_date >= start_date and
        entry.forecast_date <= end_date and
        entry.product_id in products_to_keep and
        entry.location_id in locations_to_keep)
]

test_forecast = Forecast(name="Routes vs Trucks", entries=test_entries)

# Build and solve
model = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=1,
    allow_shortages=True,
    enforce_shelf_life=False,
)

result = model.solve(solver_name='cbc', time_limit_seconds=60, tee=False)

solution = model.get_solution()
truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
shipments = model.get_shipment_plan()

manufacturing_id = model.manufacturing_site.location_id
mfg_shipments = [s for s in shipments if s.origin_id == manufacturing_id]

print("=" * 80)
print("COMPLETE MAPPING: SHIPMENTS vs TRUCK LOADS")
print("=" * 80)

# Build sets of (dest, product, date) for both
shipment_keys = set()
for s in mfg_shipments:
    key = (s.first_leg_destination, s.product_id, s.delivery_date)
    shipment_keys.add(key)

truck_keys = set()
for (truck_idx, dest, prod, date), qty in truck_loads.items():
    key = (dest, prod, date)
    truck_keys.add(key)

print(f"\nUnique (dest, product, date) combinations:")
print(f"  In shipments: {len(shipment_keys)}")
print(f"  In truck loads: {len(truck_keys)}")
print(f"  Overlap: {len(shipment_keys & truck_keys)}")
print(f"  Shipments only: {len(shipment_keys - truck_keys)}")
print(f"  Truck loads only: {len(truck_keys - shipment_keys)}")

print(f"\n{'=' * 80}")
print("SHIPMENTS WITHOUT MATCHING TRUCK LOADS")
print(f"{'=' * 80}")

orphan_keys = shipment_keys - truck_keys
if orphan_keys:
    for dest, prod, delivery_date in sorted(orphan_keys):
        print(f"\n{dest}, {prod}, {delivery_date.strftime('%Y-%m-%d %a')}:")
        matching_shipments = [s for s in mfg_shipments
                             if s.first_leg_destination == dest
                             and s.product_id == prod
                             and s.delivery_date == delivery_date]
        for s in matching_shipments:
            print(f"  {s.id}: {s.origin_id}→{s.destination_id}, {s.quantity:.1f} units")
else:
    print("None - all shipments have matching truck loads!")

print(f"\n{'=' * 80}")
print("TRUCK LOADS WITHOUT MATCHING SHIPMENTS")
print(f"{'=' * 80}")

orphan_truck_keys = truck_keys - shipment_keys
if orphan_truck_keys:
    for dest, prod, date in sorted(orphan_truck_keys):
        print(f"\n{dest}, {prod}, {date.strftime('%Y-%m-%d %a')}:")
        matching_trucks = [(truck_idx, qty) for (truck_idx, d, p, dt), qty in truck_loads.items()
                          if d == dest and p == prod and dt == date]
        for truck_idx, qty in matching_trucks:
            truck = model.truck_by_index[truck_idx]
            print(f"  Truck {truck_idx} ({truck.truck_name}): {qty:.1f} units")
else:
    print("None - all truck loads have matching shipments!")

print(f"\n{'=' * 80}")
print("ANALYSIS")
print(f"{'=' * 80}")
if orphan_keys:
    print(f"⚠️  {len(orphan_keys)} shipment keys have no truck loads!")
    print("This means shipments exist but trucks can't carry them.")
    print("Possible causes:")
    print("  1. Trucks don't serve these (dest, date) combinations")
    print("  2. Bug in truck_route_linking_con constraint")
if orphan_truck_keys:
    print(f"⚠️  {len(orphan_truck_keys)} truck load keys have no shipments!")
    print("This means trucks are loaded but nothing is shipped.")
    print("This would be a constraint violation!")
if not orphan_keys and not orphan_truck_keys:
    print("✅ Perfect match - all shipments and truck loads align!")
