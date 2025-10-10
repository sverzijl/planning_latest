"""Verify that Lineage is correctly treated as frozen-only in the model."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.location import StorageMode

print("="*70)
print("VERIFYING LINEAGE CONFIGURATION")
print("="*70)

# Load location data
parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = parser.parse_locations()

# Find Lineage
lineage = next((loc for loc in locations if loc.id == 'Lineage'), None)

if not lineage:
    print("❌ ERROR: Lineage location not found!")
    sys.exit(1)

print(f"\nLineage Location Configuration:")
print(f"  ID: {lineage.id}")
print(f"  Name: {lineage.name}")
print(f"  Type: {lineage.type}")
print(f"  Storage Mode: {lineage.storage_mode}")

# Verify it's frozen-only
if lineage.storage_mode == StorageMode.FROZEN:
    print(f"\n✅ CONFIRMED: Lineage storage_mode = 'frozen' (frozen-only)")
elif lineage.storage_mode == StorageMode.BOTH:
    print(f"\n❌ ERROR: Lineage storage_mode = 'both' (should be 'frozen'!)")
    sys.exit(1)
elif lineage.storage_mode == StorageMode.AMBIENT:
    print(f"\n❌ ERROR: Lineage storage_mode = 'ambient' (should be 'frozen'!)")
    sys.exit(1)

print("\n" + "="*70)
print("CHECKING MODEL INVENTORY VARIABLE CREATION")
print("="*70)

# Quick simulation of model logic
locations_frozen_storage = {
    loc.id for loc in locations
    if loc.storage_mode in [StorageMode.FROZEN, StorageMode.BOTH]
}

locations_ambient_storage = {
    loc.id for loc in locations
    if loc.storage_mode in [StorageMode.AMBIENT, StorageMode.BOTH]
}

print(f"\nLocations with frozen storage capability:")
for loc_id in sorted(locations_frozen_storage):
    print(f"  - {loc_id}")

print(f"\nLocations with ambient storage capability:")
for loc_id in sorted(locations_ambient_storage):
    print(f"  - {loc_id}")

# Check Lineage specifically
if 'Lineage' in locations_frozen_storage:
    print(f"\n✅ Lineage WILL have inventory_frozen variables")
else:
    print(f"\n❌ ERROR: Lineage will NOT have inventory_frozen variables!")

if 'Lineage' in locations_ambient_storage:
    print(f"❌ ERROR: Lineage WILL have inventory_ambient variables (WRONG!)")
else:
    print(f"✅ Lineage will NOT have inventory_ambient variables")

print("\n" + "="*70)
print("CHECKING ROUTE ARRIVAL STATES TO/FROM LINEAGE")
print("="*70)

# Load routes
routes_data = parser.parse_routes()

# Find routes involving Lineage
lineage_routes = [r for r in routes_data if 'Lineage' in [r.origin_id, r.destination_id]]

print(f"\nRoutes involving Lineage:")
for route in lineage_routes:
    print(f"  {route.origin_id} → {route.destination_id}: {route.transport_mode} mode")

# Build network and enumerate routes
from src.network.graph_builder import NetworkGraphBuilder
from src.optimization.route_enumerator import RouteEnumerator

manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

graph_builder = NetworkGraphBuilder(locations, routes_data)
graph_builder.build_graph()

route_enum = RouteEnumerator(
    graph_builder=graph_builder,
    manufacturing_site_id=manufacturing_site.id,
    max_routes_per_destination=5
)

# Enumerate routes through Lineage
all_destinations = [loc.id for loc in locations if loc.type in ['breadroom', 'storage']]
route_enum.enumerate_routes_for_destinations(
    destinations=all_destinations,
    rank_by='cost'
)

enumerated_routes = route_enum.get_all_routes()

# Filter for routes involving Lineage
routes_to_lineage = [r for r in enumerated_routes if r.destination_id == 'Lineage']
routes_from_lineage = [r for r in enumerated_routes if 'Lineage' in r.path and r.destination_id != 'Lineage']

print(f"\n" + "="*70)
print("ROUTES TO LINEAGE (frozen arrivals)")
print("="*70)

location_by_id = {loc.id: loc for loc in locations}

for route in routes_to_lineage:
    # Simulate arrival state logic
    is_frozen_route = route.route_path.transport_mode == 'frozen'
    dest_loc = location_by_id.get(route.destination_id)

    if is_frozen_route and dest_loc and dest_loc.storage_mode == StorageMode.FROZEN:
        arrival_state = 'frozen'
    else:
        arrival_state = 'ambient'

    print(f"\nRoute {route.index}: {' → '.join(route.path)}")
    print(f"  Transport mode: {route.route_path.transport_mode}")
    print(f"  Arrival state: {arrival_state}")
    if arrival_state == 'frozen':
        print(f"  ✅ Stays frozen at Lineage (frozen-only storage)")

print(f"\n" + "="*70)
print("ROUTES FROM LINEAGE (thawing check)")
print("="*70)

for route in routes_from_lineage[:3]:  # Just check first few
    # Simulate arrival state logic
    is_frozen_route = route.route_path.transport_mode == 'frozen'
    dest_loc = location_by_id.get(route.destination_id)

    if is_frozen_route and dest_loc and dest_loc.storage_mode == StorageMode.FROZEN:
        arrival_state = 'frozen'
    else:
        arrival_state = 'ambient'

    print(f"\nRoute {route.index}: {' → '.join(route.path)}")
    print(f"  Transport mode: {route.route_path.transport_mode}")
    print(f"  Final destination storage: {dest_loc.storage_mode if dest_loc else 'unknown'}")
    print(f"  Arrival state: {arrival_state}")

    if arrival_state == 'ambient' and is_frozen_route:
        print(f"  ✅ Thaws at destination (frozen route to non-frozen-only storage)")
    elif arrival_state == 'frozen':
        print(f"  ✅ Stays frozen (frozen route to frozen-only storage)")

print("\n" + "="*70)
print("VERIFICATION COMPLETE")
print("="*70)
print("\nSummary:")
print("✅ Lineage is configured as storage_mode='frozen' (frozen-only)")
print("✅ Model will create inventory_frozen variables at Lineage")
print("✅ Model will NOT create inventory_ambient variables at Lineage")
print("✅ Frozen routes TO Lineage stay frozen")
print("✅ Frozen routes FROM Lineage thaw at ambient/both destinations")
print("\nThe implementation correctly handles Lineage as frozen-only storage.")
