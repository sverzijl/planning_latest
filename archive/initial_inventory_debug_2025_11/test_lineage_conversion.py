"""Test if Lineage node is being created by converter."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

# parse_all returns: Forecast, Locations, Routes, LaborCalendar, TruckSchedules, CostStructure
forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

print(f"=== PARSED DATA ===\n")
print(f"Locations count: {len(locations)}")
print(f"Location IDs: {[loc.id for loc in locations]}")

lineage_in_locations = any(loc.id == 'Lineage' for loc in locations)
print(f"\nLineage in locations: {lineage_in_locations}")

# Find manufacturing site (ID 6122)
manufacturing_site = next((loc for loc in locations if loc.id == '6122'), None)
if manufacturing_site:
    print(f"Manufacturing site: {manufacturing_site.id}")
else:
    print("⚠️  Manufacturing site (6122) not found in locations")

# Convert
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=manufacturing_site,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    forecast=forecast
)

print(f"\n=== CONVERTED NODES ===\n")
print(f"Total nodes: {len(nodes)}")
print(f"Node IDs: {[n.id for n in nodes]}")

lineage_in_nodes = any(n.id == 'Lineage' for n in nodes)
print(f"\nLineage in unified nodes: {lineage_in_nodes}")

if not lineage_in_nodes and lineage_in_locations:
    print(f"\n🚨 LINEAGE WAS IN LOCATIONS BUT NOT IN UNIFIED NODES!")
    print(f"   Converter filtered it out somewhere")

    # Check why
    lineage_loc = next(loc for loc in locations if loc.id == 'Lineage')
    print(f"\nLineage location:")
    print(f"  ID: {lineage_loc.id}")
    print(f"  Type: {lineage_loc.type}")
    print(f"  Equals manufacturing site ID: {lineage_loc.id == manufacturing_site.id}")

# Check routes
print(f"\n=== CONVERTED ROUTES ===\n")
lineage_routes = [r for r in unified_routes if r.origin_node_id == 'Lineage' or r.destination_node_id == 'Lineage']
print(f"Routes involving Lineage: {len(lineage_routes)}")
for r in lineage_routes:
    print(f"  {r.origin_node_id} → {r.destination_node_id} ({r.transport_mode})")

wa_routes = [r for r in unified_routes if r.origin_node_id == '6130' or r.destination_node_id == '6130']
print(f"\nRoutes involving 6130: {len(wa_routes)}")
for r in wa_routes:
    print(f"  {r.origin_node_id} → {r.destination_node_id} ({r.transport_mode})")
