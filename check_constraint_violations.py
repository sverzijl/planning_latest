"""Check if truck_route_linking constraint is satisfied."""

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

# Build model (same as before)
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

test_forecast = Forecast(name="Constraint Check", entries=test_entries)

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

# Get the Pyomo model
pyomo_model = model_obj.pyomo_model

print("Checking truck_route_linking_con constraint...")
print("="*80)

# The constraint is indexed by (dest_id, date)
if hasattr(pyomo_model, 'truck_route_linking_con'):
    for (dest_id, d) in pyomo_model.truck_route_linking_con:
        constraint = pyomo_model.truck_route_linking_con[dest_id, d]

        # Get the constraint body value
        body_value = value(constraint.body)
        lower = constraint.lower() if constraint.has_lb() else None
        upper = constraint.upper() if constraint.has_ub() else None

        # For equality constraints, lower == upper
        if lower is not None and upper is not None and abs(lower - upper) < 0.001:
            # Equality constraint
            target = lower
            violation = abs(body_value - target)
            if violation > 0.1:  # Allow small numerical tolerance
                print(f"\n❌ VIOLATION: {dest_id}, {d}")
                print(f"   Target: {target:.2f}")
                print(f"   Actual: {body_value:.2f}")
                print(f"   Violation: {violation:.2f}")

                # Break down the left and right sides
                # Left side: sum of shipments
                manufacturing_id = model_obj.manufacturing_site.id
                direct_routes = []
                for route_idx in model_obj.route_indices:
                    route = model_obj.route_enumerator.get_route(route_idx)
                    if route and route.origin_id == manufacturing_id:
                        first_leg_dest = route.path[1] if len(route.path) >= 2 else route.destination_id
                        if first_leg_dest == dest_id:
                            direct_routes.append(route_idx)

                ship_total = 0.0
                for r in direct_routes:
                    for p in pyomo_model.products:
                        ship_qty = value(pyomo_model.shipment[r, p, d])
                        if ship_qty > 0.01:
                            route = model_obj.route_enumerator.get_route(r)
                            print(f"     Shipment [{r}:{route.origin_id}→{route.destination_id}, {p}, {d}]: {ship_qty:.2f}")
                            ship_total += ship_qty

                # Right side: sum of truck loads
                trucks_to_dest = model_obj.trucks_to_destination.get(dest_id, [])
                truck_total = 0.0
                for t in trucks_to_dest:
                    for p in pyomo_model.products:
                        truck_qty = value(pyomo_model.truck_load[t, dest_id, p, d])
                        if truck_qty > 0.01:
                            truck = model_obj.truck_by_index[t]
                            print(f"     Truck [{t}:{truck.truck_name}, {dest_id}, {p}, {d}]: {truck_qty:.2f}")
                            truck_total += truck_qty

                print(f"   Ship total: {ship_total:.2f}")
                print(f"   Truck total: {truck_total:.2f}")
            elif d.weekday() < 5:  # Only print weekdays for brevity
                print(f"✅ OK: {dest_id}, {d.strftime('%Y-%m-%d %a')}: {body_value:.2f} == {target:.2f}")
else:
    print("⚠️  truck_route_linking_con constraint not found!")

print(f"\n{'='*80}")
print("Summary: If you see violations above, the constraint is not working correctly.")
print("If no violations, then the comparison script logic is wrong.")
