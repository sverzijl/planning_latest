"""Check truck-to-destination mapping."""

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
forecast = forecast_parser.parse_forecast()

# Build model
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print("Destinations with demand:")
dest_with_demand = set(e.location_id for e in forecast.entries)
for dest in sorted(dest_with_demand):
    print(f"  {dest}")

print(f"\nTrucks to destinations (model.trucks_to_destination):")
for dest, trucks in sorted(model.trucks_to_destination.items()):
    print(f"  {dest}: {len(trucks)} trucks")

print(f"\nDestinations with NO trucks:")
for dest in sorted(dest_with_demand):
    if dest not in model.trucks_to_destination or not model.trucks_to_destination[dest]:
        print(f"  ❌ {dest} - has demand but NO trucks!")

        # Check if this destination has routes
        if dest in model.routes_to_destination:
            route_indices = model.routes_to_destination[dest]
            print(f"      But has {len(route_indices)} route(s):")
            for idx in route_indices:
                route = model.route_enumerator.get_route(idx)
                if route:
                    path = ' → '.join(route.path)
                    print(f"        Route {idx}: {path}")

                    # Check if first leg is from manufacturing
                    if route.origin_id == manufacturing_site.id:
                        first_leg_dest = route.path[1] if len(route.path) >= 2 else route.destination_id
                        print(f"          First leg from {route.origin_id} → {first_leg_dest}")

                        if first_leg_dest != dest:
                            print(f"          ⚠️  This is a MULTI-HOP route (via {first_leg_dest})")
                        else:
                            print(f"          ⚠️  This is a DIRECT route BUT NO TRUCKS!")

print(f"\n\nTruck schedules ({len(truck_schedules_list)} total):")
for ts in truck_schedules_list[:5]:
    print(f"  {ts.name}: → {ts.destination_id} ({ts.departure_type})")
