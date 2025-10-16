"""Check if orphan shipments have zero quantities in the model.

If get_shipment_plan() is creating Shipment objects for zero-quantity
shipment variables, that would explain why they can't be assigned.
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
from pyomo.environ import value

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

test_forecast = Forecast(name="Orphan Quantities", entries=test_entries)

# Build and solve
model_obj = IntegratedProductionDistributionModel(
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

result = model_obj.solve(solver_name='cbc', time_limit_seconds=60, tee=False)

# Access Pyomo model and get shipments
m = model_obj.model
shipments = model_obj.get_shipment_plan()

manufacturing_id = model_obj.manufacturing_site.location_id
solution = model_obj.get_solution()
truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})

print("=" * 80)
print("ORPHAN SHIPMENT QUANTITY CHECK")
print("=" * 80)

# Find shipments without truck loads
orphan_count = 0
zero_orphan_count = 0

for s in sorted(shipments, key=lambda x: x.id):
    if s.origin_id != manufacturing_id:
        continue

    # Check if this shipment has a matching truck load
    key = (s.first_leg_destination, s.product_id, s.delivery_date)
    has_truck = any(
        (dest == key[0] and prod == key[1] and date == key[2])
        for (truck_idx, dest, prod, date) in truck_loads.keys()
    )

    if not has_truck:
        orphan_count += 1
        print(f"\n{s.id}: {s.origin_id}→{s.destination_id}")
        print(f"  Product: {s.product_id}")
        print(f"  Delivery date: {s.delivery_date}")
        print(f"  Shipment.quantity (Shipment object): {s.quantity:.3f} units")

        # Find the route index for this shipment
        route_match = None
        for r_idx in model_obj.route_indices:
            route = model_obj.route_enumerator.get_route(r_idx)
            if (route and
                route.origin_id == s.origin_id and
                route.destination_id == s.destination_id):
                route_match = r_idx
                break

        if route_match is not None:
            var_value = value(m.shipment[route_match, s.product_id, s.delivery_date])
            print(f"  Model variable value: {var_value:.3f} units")

            if var_value < 0.01:
                zero_orphan_count += 1
                print(f"  ❌ NEAR-ZERO! This shipment shouldn't be in get_shipment_plan()")
            else:
                print(f"  ✅ NON-ZERO - this is a real shipment without a truck!")
        else:
            print(f"  ⚠️  Could not find matching route in model")

print(f"\n{'=' * 80}")
print(f"SUMMARY")
print(f"{'=' * 80}")
print(f"Total orphan shipments: {orphan_count}")
print(f"Orphans with near-zero quantity: {zero_orphan_count}")
print(f"\nIf zero orphans > 0, get_shipment_plan() has a bug (including zero shipments)")
print(f"If zero orphans == 0, then real shipments exist without trucks (constraint bug?)")
