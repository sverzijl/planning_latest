"""
Check if there are first-day arrivals that create phantom supply.

The model warns about Route 6122 → Lineage arriving on day 1 from a pre-horizon departure.
If Lineage doesn't have this in initial_inventory, it's phantom supply!
"""

from datetime import datetime, timedelta
from src.validation.data_coordinator import DataCoordinator

# Load data
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

print("="*80)
print("CHECKING INITIAL INVENTORY AT LINEAGE")
print("="*80)

# Check if Lineage has initial inventory
lineage_inv = {}
for key, qty in validated.get_inventory_dict().items():
    node_id, prod, state = key
    if node_id == 'Lineage':
        lineage_inv[key] = qty

print(f"\nLineage initial inventory entries: {len(lineage_inv)}")
print(f"Total quantity at Lineage: {sum(lineage_inv.values()):,.0f} units")

if len(lineage_inv) == 0:
    print(f"\n❌ LINEAGE HAS NO INITIAL INVENTORY!")
    print(f"But the model warns about first-day arrivals at Lineage from pre-horizon shipments.")
    print(f"This creates PHANTOM SUPPLY!")
else:
    print(f"\n✓ Lineage has initial inventory")
    print(f"\nBreakdown by product:")
    for (node_id, prod, state), qty in sorted(lineage_inv.items()):
        print(f"  {prod[:40]:<40} ({state}): {qty:>8,.0f} units")

print("\n" + "="*80)
print("CHECKING ALL NODES WITH ZERO INITIAL INVENTORY")
print("="*80)

# Check which nodes have zero initial inventory
all_inv = validated.get_inventory_dict()
nodes_with_inv = set(node_id for (node_id, prod, state) in all_inv.keys())

# Get all nodes from the data
from src.parsers.multi_file_parser import MultiFileParser
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
_, locations, _, _, _, _ = parser.parse_all()

all_nodes = set(loc.id for loc in locations)
nodes_without_inv = all_nodes - nodes_with_inv

print(f"\nNodes WITH initial inventory: {sorted(nodes_with_inv)}")
print(f"\nNodes WITHOUT initial inventory: {sorted(nodes_without_inv)}")

if 'Lineage' in nodes_without_inv:
    print(f"\n❌ CONFIRMED: Lineage has NO initial inventory!")
    print(f"   This is the source of phantom supply!")

print("\n" + "="*80)
