"""Verify the truck_route_linking constraint is satisfied.

This script checks if shipments from manufacturing match truck loads
by comparing the raw optimization variables.
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

test_forecast = Forecast(name="Constraint Verification", entries=test_entries)

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

# Access the Pyomo model
m = model_obj.model

print("=" * 80)
print("CONSTRAINT VERIFICATION: truck_route_linking_con")
print("=" * 80)

# Get manufacturing ID
mfg_id = model_obj.manufacturing_site.location_id

# For each destination and date, check the constraint
for dest in ['6104', '6110']:
    print(f"\n{'=' * 80}")
    print(f"Destination: {dest}")
    print(f"{'=' * 80}")

    for date in sorted(model_obj.production_dates):
        # Calculate left side: sum of shipments going to this destination
        # (routes from manufacturing with first leg to dest)
        shipment_total = 0.0
        direct_routes = []

        for route_idx in model_obj.route_indices:
            route = model_obj.route_enumerator.get_route(route_idx)
            if route and route.origin_id == mfg_id:
                first_leg_dest = route.path[1] if len(route.path) >= 2 else route.destination_id
                if first_leg_dest == dest:
                    direct_routes.append(route_idx)

        for r in direct_routes:
            for p in m.products:
                qty = value(m.shipment[r, p, date])
                if qty > 0.01:
                    shipment_total += qty

        # Calculate right side: sum of truck loads to this destination
        truck_total = 0.0
        trucks_to_dest = model_obj.trucks_to_destination.get(dest, [])

        for t in trucks_to_dest:
            for p in m.products:
                qty = value(m.truck_load[t, dest, p, date])
                if qty > 0.01:
                    truck_total += qty

        # Compare
        diff = abs(shipment_total - truck_total)
        if diff > 0.1 or shipment_total > 0.01 or truck_total > 0.01:
            status = "✅" if diff < 0.1 else "❌"
            print(f"\n{status} {date.strftime('%Y-%m-%d %a')}:")
            print(f"    Shipments: {shipment_total:7.1f} units")
            print(f"    Truck loads: {truck_total:7.1f} units")
            print(f"    Difference: {diff:7.1f} units")

            if diff > 0.1:
                print(f"\n    ⚠️  CONSTRAINT VIOLATION!")

                # Show details
                if shipment_total > 0.01:
                    print(f"    Shipment details:")
                    for r in direct_routes:
                        for p in m.products:
                            qty = value(m.shipment[r, p, date])
                            if qty > 0.01:
                                route = model_obj.route_enumerator.get_route(r)
                                print(f"      Route {r} ({route.origin_id}→{route.destination_id}), {p}: {qty:.1f}")

                if truck_total > 0.01:
                    print(f"    Truck load details:")
                    for t in trucks_to_dest:
                        for p in m.products:
                            qty = value(m.truck_load[t, dest, p, date])
                            if qty > 0.01:
                                truck = model_obj.truck_by_index[t]
                                print(f"      Truck {t} ({truck.truck_name}), {p}: {qty:.1f}")

print(f"\n{'=' * 80}")
print("If you see violations above, there's a bug in the constraint!")
print(f"{'=' * 80}")
