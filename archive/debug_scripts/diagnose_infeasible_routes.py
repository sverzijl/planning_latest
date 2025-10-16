"""Diagnose which routes are shelf-life infeasible."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.route_enumerator import RouteEnumerator
from src.network.graph_builder import NetworkGraphBuilder
from collections import defaultdict

print("Loading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
forecast = forecast_parser.parse_forecast()

# Build network graph
graph_builder = NetworkGraphBuilder(locations, routes)
graph_builder.build_graph()

# Create route enumerator
route_enum = RouteEnumerator(
    graph_builder=graph_builder,
    manufacturing_site_id=manufacturing_site.id,
    max_routes_per_destination=5
)

# Get destinations from forecast
destinations = set(entry.location_id for entry in forecast.entries)

print(f"\n{'='*70}")
print("ROUTE SHELF LIFE ANALYSIS")
print(f"{'='*70}")

# Shelf life rules
AMBIENT_SHELF_LIFE = 17
FROZEN_SHELF_LIFE = 120
THAWED_SHELF_LIFE = 14
MIN_SHELF_LIFE_AT_DELIVERY = 7

print(f"\nShelf life rules:")
print(f"  Ambient: {AMBIENT_SHELF_LIFE} days")
print(f"  Frozen: {FROZEN_SHELF_LIFE} days")
print(f"  Thawed (6130): {THAWED_SHELF_LIFE} days")
print(f"  Minimum at delivery: {MIN_SHELF_LIFE_AT_DELIVERY} days")
print(f"  Maximum transit time: {AMBIENT_SHELF_LIFE - MIN_SHELF_LIFE_AT_DELIVERY} days")

# Enumerate routes for all destinations
print(f"\nEnumerating routes for {len(destinations)} destinations...")
route_enum.enumerate_routes_for_destinations(
    destinations=list(destinations),
    rank_by='cost'
)

# Get all enumerated routes
all_routes = route_enum.get_all_routes()

print(f"\n{'='*70}")
print(f"ENUMERATED ROUTES: {len(all_routes)} total")
print(f"{'='*70}")

# Group by destination
by_dest = defaultdict(list)
for route in all_routes:
    by_dest[route.destination_id].append(route)

# Check each destination
feasible_count = 0
infeasible_count = 0
destinations_with_no_feasible = []

for dest_id in sorted(destinations):
    dest_routes = by_dest.get(dest_id, [])

    print(f"\n{dest_id}:")
    print(f"  Total routes enumerated: {len(dest_routes)}")

    if not dest_routes:
        print(f"  ⚠️  NO ROUTES ENUMERATED!")
        destinations_with_no_feasible.append(dest_id)
        continue

    feasible = []
    infeasible = []

    for route in dest_routes:
        transit_days = route.total_transit_days

        # Determine if frozen route
        is_frozen = any('frozen' in leg.transport_mode.lower() for leg in route.route_path.route_legs)

        if is_frozen:
            # Frozen route
            remaining_after_transit = FROZEN_SHELF_LIFE - transit_days
            # After thawing at 6130, it has 14 days
            if dest_id == '6130':
                remaining_after_delivery = THAWED_SHELF_LIFE
            else:
                remaining_after_delivery = remaining_after_transit
        else:
            # Ambient route
            remaining_after_delivery = AMBIENT_SHELF_LIFE - transit_days

        is_feasible = remaining_after_delivery >= MIN_SHELF_LIFE_AT_DELIVERY

        if is_feasible:
            feasible.append((route, transit_days, remaining_after_delivery))
            feasible_count += 1
        else:
            infeasible.append((route, transit_days, remaining_after_delivery))
            infeasible_count += 1

    print(f"  Feasible routes: {len(feasible)}")
    print(f"  Infeasible routes: {len(infeasible)}")

    if feasible:
        print(f"  Feasible route details:")
        for route, transit, remaining in feasible[:3]:  # Show first 3
            mode = "frozen" if any('frozen' in leg.transport_mode.lower() for leg in route.route_path.route_legs) else "ambient"
            print(f"    - {transit}d transit, {remaining:.0f}d remaining ({mode})")

    if infeasible:
        print(f"  ⚠️  Infeasible route details:")
        for route, transit, remaining in infeasible[:3]:  # Show first 3
            mode = "frozen" if any('frozen' in leg.transport_mode.lower() for leg in route.route_path.route_legs) else "ambient"
            print(f"    - {transit}d transit, {remaining:.0f}d remaining ({mode}) - FILTERED OUT")

    if not feasible:
        print(f"  ❌ NO FEASIBLE ROUTES FOR THIS DESTINATION!")
        destinations_with_no_feasible.append(dest_id)

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
print(f"Total routes: {len(all_routes)}")
print(f"  Feasible: {feasible_count}")
print(f"  Infeasible: {infeasible_count}")
print(f"\nDestinations with no feasible routes: {len(destinations_with_no_feasible)}")
if destinations_with_no_feasible:
    for dest in destinations_with_no_feasible:
        # Get demand for this destination
        dest_demand = sum(e.quantity for e in forecast.entries if e.location_id == dest)
        print(f"  - {dest}: {dest_demand:,.0f} units demand cannot be met")

# Calculate total infeasible demand
if destinations_with_no_feasible:
    total_infeasible_demand = sum(
        e.quantity for e in forecast.entries
        if e.location_id in destinations_with_no_feasible
    )
    total_demand = sum(e.quantity for e in forecast.entries)
    print(f"\nTotal infeasible demand: {total_infeasible_demand:,.0f} units ({total_infeasible_demand/total_demand*100:.1f}% of total)")
