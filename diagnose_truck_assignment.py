"""Detailed diagnostic for truck assignment matching logic.

This script examines why shipments are not being assigned to trucks by:
1. Showing truck_loads structure
2. Showing shipment attributes
3. Attempting to match and logging why matches fail
"""

import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

# Parse data (same as Test 1)
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

# Small test subset
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

test_forecast = Forecast(name="Diagnostic Test", entries=test_entries)

print("="*80)
print("DIAGNOSTIC: TRUCK ASSIGNMENT MATCHING")
print("="*80)

# Build and solve model
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

if not (result.is_optimal() or result.is_feasible()):
    print("Model did not solve optimally")
    sys.exit(1)

solution = model.get_solution()
truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
shipments = model.get_shipment_plan()

print(f'\n{"="*80}')
print("PART 1: TRUCK LOADS STRUCTURE")
print(f'{"="*80}')
print(f'Total truck load entries: {len(truck_loads)}')
print(f'\nTruck loads dictionary keys: (truck_idx, dest, product, date)')
print(f'\nAll truck loads:')
for (truck_idx, dest, prod, date), qty in sorted(truck_loads.items(), key=lambda x: x[0]):
    truck = model.truck_by_index[truck_idx]
    day_name = date.strftime('%a')
    print(f'  ({truck_idx}, "{dest}", "{prod}", {date} {day_name}): {qty:.0f} units - Truck: {truck.truck_name}')

print(f'\n{"="*80}')
print("PART 2: SHIPMENTS FROM MANUFACTURING")
print(f'{"="*80}')

manufacturing_id = model.manufacturing_site.location_id
mfg_shipments = [s for s in shipments if s.origin_id == manufacturing_id]

print(f'Total shipments from manufacturing: {len(mfg_shipments)}')
print(f'\nShipment attributes needed for matching:')
print(f'  - first_leg_destination')
print(f'  - product_id')
print(f'  - production_date (calculated as delivery_date - transit_days)')

print(f'\nAll manufacturing shipments:')
for s in sorted(mfg_shipments, key=lambda x: (x.delivery_date, x.product_id)):
    delivery_day = s.delivery_date.strftime('%a')
    prod_day = s.production_date.strftime('%a')
    route_info = f"{s.origin_id}→{s.destination_id}"
    print(f'\n  Shipment {s.id}:')
    print(f'    Quantity: {s.quantity:.0f} units')
    print(f'    Product: {s.product_id}')
    print(f'    Route: {route_info}')
    print(f'    First-leg dest: {s.first_leg_destination}')
    print(f'    Delivery date: {s.delivery_date} ({delivery_day})')
    print(f'    Production date: {s.production_date} ({prod_day})')
    print(f'    Assigned truck: {s.assigned_truck_id or "NONE"}')

print(f'\n{"="*80}')
print("PART 3: MATCHING ANALYSIS")
print(f'{"="*80}')

print(f'\nAttempting to match each shipment to truck loads...')
print(f'Looking for: (truck_idx, first_leg_dest, product_id, production_date)')

matched_count = 0
unmatched_count = 0

for s in sorted(mfg_shipments, key=lambda x: (x.delivery_date, x.product_id)):
    print(f'\n--- Shipment {s.id} ---')
    print(f'  Looking for: (any_truck, "{s.first_leg_destination}", "{s.product_id}", {s.production_date})')

    # Check if there's a matching truck load
    matching_loads = [(truck_idx, dest, prod, date, qty)
                      for (truck_idx, dest, prod, date), qty in truck_loads.items()
                      if dest == s.first_leg_destination and
                         prod == s.product_id and
                         date == s.production_date]

    if matching_loads:
        print(f'  ✅ MATCH FOUND:')
        for truck_idx, dest, prod, date, qty in matching_loads:
            truck = model.truck_by_index[truck_idx]
            print(f'    Truck {truck_idx} ({truck.truck_name}): {qty:.0f} units on {date}')
        matched_count += 1
    else:
        print(f'  ❌ NO MATCH - Checking why...')
        unmatched_count += 1

        # Check destination mismatches
        dest_matches = [(truck_idx, dest, prod, date, qty)
                       for (truck_idx, dest, prod, date), qty in truck_loads.items()
                       if prod == s.product_id and date == s.production_date]
        if dest_matches:
            print(f'    Product + Date match, but WRONG DESTINATION:')
            for truck_idx, dest, prod, date, qty in dest_matches[:3]:
                print(f'      Truck load has dest="{dest}", need "{s.first_leg_destination}"')

        # Check date mismatches
        date_matches = [(truck_idx, dest, prod, date, qty)
                       for (truck_idx, dest, prod, date), qty in truck_loads.items()
                       if dest == s.first_leg_destination and prod == s.product_id]
        if date_matches:
            print(f'    Destination + Product match, but WRONG DATE:')
            for truck_idx, dest, prod, date, qty in date_matches[:3]:
                truck = model.truck_by_index[truck_idx]
                date_diff = (date - s.production_date).days
                print(f'      Truck load has date={date} ({date.strftime("%a")}), need {s.production_date} ({s.production_date.strftime("%a")})')
                print(f'      Difference: {date_diff} days - Truck: {truck.truck_name}')

        # Check product mismatches
        prod_matches = [(truck_idx, dest, prod, date, qty)
                       for (truck_idx, dest, prod, date), qty in truck_loads.items()
                       if dest == s.first_leg_destination and date == s.production_date]
        if prod_matches:
            print(f'    Destination + Date match, but WRONG PRODUCT:')
            for truck_idx, dest, prod, date, qty in prod_matches[:3]:
                print(f'      Truck load has product="{prod}", need "{s.product_id}"')

        # If none of the above, completely no overlap
        if not dest_matches and not date_matches and not prod_matches:
            print(f'    No truck loads match ANY of the three criteria!')
            print(f'    Truck loads available:')
            for (truck_idx, dest, prod, date), qty in list(truck_loads.items())[:5]:
                print(f'      ({truck_idx}, "{dest}", "{prod}", {date})')

print(f'\n{"="*80}')
print("SUMMARY")
print(f'{"="*80}')
print(f'Matched: {matched_count}')
print(f'Unmatched: {unmatched_count}')
print(f'Assignment rate: {100*matched_count/(matched_count + unmatched_count):.1f}%')

if unmatched_count > 0:
    print(f'\n⚠️  DIAGNOSIS: Truck assignment matching logic has issues!')
    print(f'Most likely cause: Date mismatch between shipment.production_date and truck departure date')
