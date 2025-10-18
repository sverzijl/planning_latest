"""Quick diagnostic for remaining unassigned shipments."""

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

test_forecast = Forecast(name="Quick Test", entries=test_entries)

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
unassigned = [s for s in mfg_shipments if s.assigned_truck_id is None]

print("Unassigned shipments:")
for s in unassigned[:5]:
    print(f'\nShipment {s.id}:')
    print(f'  Product: {s.product_id}')
    print(f'  Destination: {s.destination_id}')
    print(f'  First-leg dest: {s.first_leg_destination}')
    print(f'  Delivery date: {s.delivery_date}')
    print(f'  Looking for truck_load: (any_truck, "{s.first_leg_destination}", "{s.product_id}", {s.delivery_date})')

    # Check if there's a match
    matches = [(truck_idx, dest, prod, date, qty)
               for (truck_idx, dest, prod, date), qty in truck_loads.items()
               if dest == s.first_leg_destination and
                  prod == s.product_id and
                  date == s.delivery_date]

    if matches:
        print(f'  ✅ FOUND MATCH (should be assigned!):')
        for truck_idx, dest, prod, date, qty in matches:
            truck = model.truck_by_index[truck_idx]
            print(f'    Truck {truck_idx} ({truck.truck_name}): {qty:.0f} units')
    else:
        print(f'  ❌ NO MATCH')
        # Show near matches
        near = [(truck_idx, dest, prod, date, qty)
                for (truck_idx, dest, prod, date), qty in truck_loads.items()
                if dest == s.first_leg_destination and prod == s.product_id]
        if near:
            print(f'  Near matches (same dest+product, different date):')
            for truck_idx, dest, prod, date, qty in near[:3]:
                diff = (date - s.delivery_date).days
                print(f'    Date {date} (diff: {diff:+d} days)')
