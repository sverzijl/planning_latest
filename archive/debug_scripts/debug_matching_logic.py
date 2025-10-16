"""Debug the exact truck assignment matching logic.

This script will show the exact state of truck_loads dictionary
and the exact matching attempts to pinpoint why assignments fail.
"""

import sys
from pathlib import Path
from datetime import date

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

test_forecast = Forecast(name="Debug Test", entries=test_entries)

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

# Get solution and shipments
solution = model.get_solution()
truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
shipments = model.get_shipment_plan()

manufacturing_id = model.manufacturing_site.location_id
mfg_shipments = [s for s in shipments if s.origin_id == manufacturing_id]

print("=" * 80)
print("EXACT TRUCK LOADS DICTIONARY")
print("=" * 80)
print(f"Type: {type(truck_loads)}")
print(f"Keys: {type(list(truck_loads.keys())[0]) if truck_loads else 'empty'}")
print(f"\nAll truck_loads entries:")
for key, qty in sorted(truck_loads.items()):
    truck_idx, dest, prod, date = key
    truck = model.truck_by_index[truck_idx]
    print(f"  Key: ({truck_idx}, '{dest}', '{prod}', {date})")
    print(f"    Truck: {truck.truck_name}, Quantity: {qty:.0f}")

print(f"\n{'=' * 80}")
print("EXACT MATCHING ATTEMPTS")
print("=" * 80)

for shipment in sorted(mfg_shipments, key=lambda x: x.id)[:10]:
    print(f"\n--- Shipment {shipment.id} ---")
    print(f"  Product: {shipment.product_id}")
    print(f"  Destination: {shipment.destination_id}")
    print(f"  First-leg dest: {shipment.first_leg_destination}")
    print(f"  Delivery date: {shipment.delivery_date}")
    print(f"  Currently assigned: {shipment.assigned_truck_id or 'NONE'}")

    # Exact matching logic from integrated_model.py
    immediate_destination = shipment.first_leg_destination
    matching_date = shipment.delivery_date

    print(f"\n  Looking for truck_load key: (any_truck, '{immediate_destination}', '{shipment.product_id}', {matching_date})")

    # Try to find match
    found_match = False
    for (truck_idx, dest, prod, date), quantity in truck_loads.items():
        if (dest == immediate_destination and
            prod == shipment.product_id and
            date == matching_date):
            print(f"  ✅ MATCH: truck_idx={truck_idx}, qty={quantity:.0f}")
            truck = model.truck_by_index[truck_idx]
            print(f"     Truck: {truck.truck_name}")
            found_match = True
            break

    if not found_match:
        print(f"  ❌ NO MATCH")
        # Show what's close
        print(f"  Checking near misses...")
        near_dest_prod = [(truck_idx, dest, prod, date, qty)
                          for (truck_idx, dest, prod, date), qty in truck_loads.items()
                          if dest == immediate_destination and prod == shipment.product_id]
        if near_dest_prod:
            print(f"    Same dest+product, different dates:")
            for truck_idx, dest, prod, date, qty in near_dest_prod[:3]:
                diff = (date - matching_date).days
                print(f"      Date {date} (diff: {diff:+d} days)")
