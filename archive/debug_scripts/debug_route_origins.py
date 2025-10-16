"""Check route origins and multi-hop structure."""

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

print(f"Manufacturing site: {manufacturing_site.id}\n")

print("Route definitions from Excel:")
for i, route in enumerate(routes):
    print(f"  Route {i}: {route.origin_id} → {route.destination_id}")

print(f"\n\nBuilding model...")
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

print(f"\nEnumerated routes ({len(model.enumerated_routes)}):")
for route_idx in sorted(model.route_indices):
    route = model.route_enumerator.get_route(route_idx)
    if route:
        path = ' → '.join(route.path)
        print(f"  Route {route_idx}: {path} (origin: {route.origin_id}, dest: {route.destination_id})")

print(f"\n\nRoutes by origin:")
by_origin = {}
for route_idx in model.route_indices:
    route = model.route_enumerator.get_route(route_idx)
    if route:
        origin = route.origin_id
        if origin not in by_origin:
            by_origin[origin] = []
        by_origin[origin].append(route_idx)

for origin in sorted(by_origin.keys()):
    print(f"\n  From {origin}:")
    for idx in by_origin[origin]:
        route = model.route_enumerator.get_route(idx)
        path = ' → '.join(route.path)
        print(f"    Route {idx}: {path}")

print(f"\n\nProduction happens at: {manufacturing_site.id}")
print(f"Routes from manufacturing: {len(by_origin.get(manufacturing_site.id, []))}")
print(f"Routes from other locations: {sum(len(v) for k, v in by_origin.items() if k != manufacturing_site.id)}")

if sum(len(v) for k, v in by_origin.items() if k != manufacturing_site.id) > 0:
    print(f"\n❌ PROBLEM: Routes exist from non-manufacturing locations!")
    print(f"   But model only has production variables at {manufacturing_site.id}")
    print(f"   These routes would need shipments but have no source!")
