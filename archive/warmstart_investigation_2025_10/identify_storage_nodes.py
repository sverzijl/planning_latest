"""Identify storage nodes without truck schedules that need the constraint."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

parser = MultiFileParser(
    forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
    network_file="data/examples/Network_Config.xlsx",
    inventory_file="data/examples/inventory.XLSX",
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

print("="*80)
print("STORAGE NODES ANALYSIS")
print("="*80)

# Identify nodes with trucks
nodes_with_trucks = set(n.id for n in nodes if n.requires_trucks())
print(f"\nNodes WITH truck schedules ({len(nodes_with_trucks)}):")
for node_id in sorted(nodes_with_trucks):
    node = [n for n in nodes if n.id == node_id][0]
    print(f"  {node_id}: {node.name}")

# Identify nodes with outbound routes
nodes_with_outbound = set(r.origin_node_id for r in unified_routes)

# Storage nodes = have outbound routes BUT no truck schedules
storage_nodes_needing_constraint = nodes_with_outbound - nodes_with_trucks

print(f"\nStorage nodes WITHOUT trucks (need 1-day delay constraint) ({len(storage_nodes_needing_constraint)}):")
for node_id in sorted(storage_nodes_needing_constraint):
    node = [n for n in nodes if n.id == node_id][0]
    outbound_routes = [r for r in unified_routes if r.origin_node_id == node_id]
    print(f"  {node_id}: {node.name}")
    print(f"    Outbound routes: {len(outbound_routes)}")
    for r in outbound_routes:
        print(f"      → {r.destination_node_id} ({r.transport_mode}, {r.transit_days} days)")

print("\n" + "="*80)
print("CONSTRAINT REQUIREMENT")
print("="*80)
print(f"\nThese {len(storage_nodes_needing_constraint)} nodes need constraint:")
print(f"  'Shipments on day D can only use inventory from day D-1 or earlier'")
print(f"  'Same-day arrivals cannot be shipped until day D+1'")

for node_id in sorted(storage_nodes_needing_constraint):
    print(f"\n  {node_id}:")
    print(f"    ∀ outbound shipments on date D:")
    print(f"      sum(departures[D]) ≤ inventory[D-1] + arrivals[D-1]")
    print(f"      (Cannot use arrivals[D] for departures[D])")

print("\n" + "="*80)
