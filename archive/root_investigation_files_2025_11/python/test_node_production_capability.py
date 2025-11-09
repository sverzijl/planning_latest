#!/usr/bin/env python3
"""Check if manufacturing node can produce."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, _, truck_schedules, _ = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

print("="*80)
print("NODE PRODUCTION CAPABILITY CHECK")
print("="*80)

# nodes is a dict
nodes_dict = {n.id: n for n in nodes} if isinstance(nodes, list) else nodes

for node_id, node in nodes_dict.items():
    can_produce = node.can_produce()
    prod_state = node.get_production_state() if can_produce else "N/A"

    print(f"\n{node_id}: {node.name}")
    print(f"  can_produce(): {can_produce}")
    if can_produce:
        print(f"  get_production_state(): {prod_state}")
        print(f"  Type: {node.type}")
        print(f"  Storage mode: {node.storage_mode}")

print("\n" + "="*80)
print("DIAGNOSIS:")
print("="*80)

mfg = nodes_dict.get('6122')
if mfg:
    print(f"\nManufacturing node (6122):")
    print(f"  can_produce(): {mfg.can_produce()}")
    print(f"  get_production_state(): {mfg.get_production_state()}")

    if not mfg.can_produce():
        print(f"  ✗ CRITICAL BUG: Manufacturing node can't produce!")
    elif mfg.get_production_state() != 'ambient':
        print(f"  ✗ ISSUE: Production state is {mfg.get_production_state()}, not 'ambient'")
        print(f"    This means production won't appear in ambient material balance!")
    else:
        print(f"  ✓ Manufacturing node configured correctly")

print("="*80)
