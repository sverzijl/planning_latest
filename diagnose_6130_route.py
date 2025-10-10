"""Diagnose the 6122 -> Lineage -> 6130 route structure."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.network.graph_builder import NetworkGraphBuilder
from src.optimization.route_enumerator import RouteEnumerator

print("Loading network data...")
parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = parser.parse_locations()
routes = parser.parse_routes()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

print("\n" + "="*70)
print("ROUTE LEGS TO 6130")
print("="*70)

# Find route legs involving Lineage and 6130
for route in routes:
    if '6130' in [route.origin_id, route.destination_id] or 'Lineage' in [route.origin_id, route.destination_id]:
        print(f"\nRoute: {route.origin_id} → {route.destination_id}")
        print(f"  Mode: {route.transport_mode}")
        print(f"  Transit: {route.transit_days} days")
        print(f"  Cost: ${route.cost_per_unit}/unit")

# Build network graph and enumerate routes
print("\n" + "="*70)
print("ENUMERATED ROUTES TO 6130")
print("="*70)

graph_builder = NetworkGraphBuilder(locations, routes)
graph_builder.build_graph()

route_enum = RouteEnumerator(
    graph_builder=graph_builder,
    manufacturing_site_id=manufacturing_site.id,
    max_routes_per_destination=5
)

# Enumerate routes to 6130
route_enum.enumerate_routes_for_destinations(
    destinations=['6130'],
    rank_by='cost'
)

routes_to_6130 = [r for r in route_enum.get_all_routes() if r.destination_id == '6130']

if not routes_to_6130:
    print("\n❌ NO ROUTES ENUMERATED TO 6130!")
else:
    for route in routes_to_6130:
        print(f"\nRoute {route.index}:")
        print(f"  Path: {' → '.join(route.path)}")
        print(f"  Transit: {route.total_transit_days} days")
        print(f"  Cost: ${route.total_cost:.2f}/unit")
        print(f"  Hops: {route.num_hops}")

        # Check route legs
        if hasattr(route, 'route_path') and hasattr(route.route_path, 'route_legs'):
            print(f"  Route legs:")
            for leg in route.route_path.route_legs:
                print(f"    - {leg.from_location_id} → {leg.to_location_id}: {leg.transport_mode} ({leg.transit_days}d, triggers_thaw={leg.triggers_thaw})")

print("\n" + "="*70)
print("SHELF LIFE ANALYSIS FOR 6130 ROUTE")
print("="*70)

# Analyze shelf life for the frozen route
FROZEN_SHELF_LIFE = 120
THAWED_SHELF_LIFE = 14
MIN_SHELF_LIFE_AT_DELIVERY = 7

print(f"\nShelf life rules:")
print(f"  Frozen: {FROZEN_SHELF_LIFE} days")
print(f"  Thawed (after arrival at 6130): {THAWED_SHELF_LIFE} days")
print(f"  Minimum at delivery: {MIN_SHELF_LIFE_AT_DELIVERY} days")

for route in routes_to_6130:
    print(f"\nRoute {route.index} analysis:")

    # Check if Lineage is in path
    if 'Lineage' in route.path:
        print(f"  ✓ Route includes Lineage (frozen buffer)")

        # Find segment from Lineage to 6130
        lineage_idx = route.path.index('Lineage')
        dest_idx = route.path.index('6130')

        if dest_idx > lineage_idx:
            print(f"  ✓ Lineage → 6130 segment exists")

            # Calculate transit from Lineage to 6130
            lineage_to_6130_legs = route.route_path.route_legs[lineage_idx:dest_idx]
            lineage_to_6130_transit = sum(leg.transit_days for leg in lineage_to_6130_legs)

            print(f"  Transit time Lineage → 6130: {lineage_to_6130_transit} days")
            print(f"  Product state at Lineage: FROZEN (120d shelf life)")
            print(f"  Product state at 6130 arrival: FROZEN")
            print(f"  Product state after thawing: THAWED (14d shelf life)")
            print(f"  Available shelf life after thaw: {THAWED_SHELF_LIFE}d")

            if THAWED_SHELF_LIFE >= MIN_SHELF_LIFE_AT_DELIVERY:
                print(f"  ✓ FEASIBLE: {THAWED_SHELF_LIFE}d >= {MIN_SHELF_LIFE_AT_DELIVERY}d minimum")
            else:
                print(f"  ❌ INFEASIBLE: {THAWED_SHELF_LIFE}d < {MIN_SHELF_LIFE_AT_DELIVERY}d minimum")
    else:
        print(f"  ⚠️  Route does NOT include Lineage!")

print("\n" + "="*70)
print("MODEL LIMITATION IDENTIFIED")
print("="*70)

print("""
The current Pyomo model does NOT properly model:

1. **Inventory at Lineage:**
   - Lineage has no demand, so no inventory variables created
   - Product can't accumulate at frozen buffer

2. **State tracking (frozen vs thawed):**
   - Model doesn't track whether inventory is frozen or ambient
   - Can't model shelf life reset when product thaws at 6130

3. **Thawing timing:**
   - Model doesn't know WHEN product thaws at 6130
   - Can't enforce 14-day post-thaw shelf life constraint

**Current approach (simplified):**
- Treats 6130 route as frozen with 120-day limit
- Assumes product arrives frozen and thaws immediately
- Assumes 14 days remaining after thaw (correct by luck for this route)

**Correct approach would require:**
- Inventory variables at Lineage
- State variables (frozen/ambient) for inventory
- Thawing decision variables at 6130
- Shelf life constraints based on current state
- Transit time accounting in frozen vs ambient mode

**Impact:**
Currently works because the route is short (3.5d total), but would
fail for longer frozen routes where timing of thaw matters.
""")
