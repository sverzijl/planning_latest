"""Check if there are destinations with demand but no routes."""

from src.parsers import ExcelParser

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
forecast = forecast_parser.parse_forecast()

# Get unique destinations with demand
destinations_with_demand = set()
for entry in forecast.entries:
    destinations_with_demand.add(entry.location_id)

print(f"Destinations with demand: {sorted(destinations_with_demand)}")
print(f"Total: {len(destinations_with_demand)}")

# Get destinations served by routes
destinations_with_routes = set()
for route in routes:
    destinations_with_routes.add(route.destination_id)

print(f"\nDestinations with routes: {sorted(destinations_with_routes)}")
print(f"Total: {len(destinations_with_routes)}")

# Find destinations with demand but no routes
no_routes = destinations_with_demand - destinations_with_routes

if no_routes:
    print(f"\n❌ PROBLEM: Destinations with demand but NO routes:")
    for dest in sorted(no_routes):
        # Count demand entries for this destination
        count = sum(1 for e in forecast.entries if e.location_id == dest)
        total_demand = sum(e.quantity for e in forecast.entries if e.location_id == dest)
        print(f"   {dest}: {count} forecast entries, {total_demand:,.0f} total units")
else:
    print(f"\n✅ All destinations with demand have routes")

# Also check manufacturing site
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
print(f"\nManufacturing site: {manufacturing_site.id if manufacturing_site else 'NOT FOUND'}")

# Check if any routes originate from non-manufacturing locations
print(f"\nRoute origins:")
origins = set(r.origin_id for r in routes)
for origin in sorted(origins):
    count = sum(1 for r in routes if r.origin_id == origin)
    print(f"   {origin}: {count} routes")
