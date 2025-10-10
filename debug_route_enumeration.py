"""Check route enumeration with shelf life enforcement."""

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

print("Building model WITH shelf life enforcement...")
model_with_shelf_life = IntegratedProductionDistributionModel(
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

print(f"Routes enumerated: {len(model_with_shelf_life.enumerated_routes)}")
print(f"Routes to destinations: {len(model_with_shelf_life.routes_to_destination)}")

# Check each destination
for dest in sorted(model_with_shelf_life.routes_to_destination.keys()):
    route_indices = model_with_shelf_life.routes_to_destination[dest]
    print(f"\n{dest}: {len(route_indices)} routes")
    for idx in route_indices[:3]:  # Show first 3
        route = model_with_shelf_life.route_enumerator.get_route(idx)
        if route:
            path = ' → '.join(route.path)
            transit = route.total_transit_days
            print(f"   Route {idx}: {path} ({transit:.1f} days)")

# Check if any destination has ZERO routes
destinations_with_zero_routes = []
forecast_dests = set(e.location_id for e in forecast.entries)
for dest in forecast_dests:
    if dest not in model_with_shelf_life.routes_to_destination or \
       not model_with_shelf_life.routes_to_destination[dest]:
        destinations_with_zero_routes.append(dest)

if destinations_with_zero_routes:
    print(f"\n❌ PROBLEM: Destinations with demand but ZERO enumerated routes:")
    for dest in destinations_with_zero_routes:
        count = sum(1 for e in forecast.entries if e.location_id == dest)
        total_demand = sum(e.quantity for e in forecast.entries if e.location_id == dest)
        print(f"   {dest}: {count} forecast entries, {total_demand:,.0f} total units")
        print(f"      This will cause infeasibility even with allow_shortages=True!")
else:
    print(f"\n✅ All destinations with demand have enumerated routes")

print(f"\n\nBuilding model WITHOUT shelf life enforcement...")
model_without_shelf_life = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=False,
)

print(f"Routes enumerated: {len(model_without_shelf_life.enumerated_routes)}")

print(f"\n\nDifference: {len(model_without_shelf_life.enumerated_routes) - len(model_with_shelf_life.enumerated_routes)} routes filtered by shelf life")
