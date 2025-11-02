#!/usr/bin/env python3
"""Test inventory conversion with storage location mapping."""

from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser

# Parse files
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, _, _, _ = parser.parse_all()

# Get alias resolver
alias_resolver = parser.parse_product_aliases()

# Parse inventory with alias resolver
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()

print("="*80)
print("INVENTORY CONVERSION TEST")
print("="*80)

# Build location dict
loc_dict = {loc.id: loc for loc in locations}

# Call to_optimization_dict
inv_2tuple = inventory_data.to_optimization_dict()

print(f"\nAfter to_optimization_dict():")
print(f"  Total entries: {len(inv_2tuple)}")

# Check for Lineage
lineage_entries = [(loc, prod, qty) for (loc, prod), qty in inv_2tuple.items() if loc == "Lineage"]
print(f"  Lineage entries: {len(lineage_entries)}")
if lineage_entries:
    for loc, prod, qty in lineage_entries:
        print(f"    - {prod[:50]}: {qty:.0f}")

# Check location 6122
loc_6122_entries = [(loc, prod, qty) for (loc, prod), qty in inv_2tuple.items() if loc == "6122"]
print(f"  Location 6122 entries: {len(loc_6122_entries)}")
total_6122 = sum(qty for _, _, qty in loc_6122_entries)
print(f"  Location 6122 total: {total_6122:.0f} units")

# Now convert to 3-tuple (as workflow does)
print(f"\nConverting to 3-tuple format (location, product, state):")
initial_inventory_dict = {}
for (location, product), quantity in inv_2tuple.items():
    # Find location in network
    loc_node = None
    for loc in locations:
        if loc.id == location:
            loc_node = loc
            break

    # Infer state from location storage mode
    if loc_node and str(loc_node.storage_mode) == 'frozen':
        # Frozen-only location (e.g., Lineage)
        state = 'frozen'
        print(f"  {location} (storage_mode={loc_node.storage_mode}) → frozen")
    else:
        # Ambient or both → assume ambient (default)
        state = 'ambient'

    initial_inventory_dict[(location, product, state)] = quantity

print(f"\nAfter 3-tuple conversion:")
print(f"  Total entries: {len(initial_inventory_dict)}")

# Group by state
from collections import defaultdict
by_state = defaultdict(list)
for (loc, prod, state), qty in initial_inventory_dict.items():
    by_state[state].append((loc, prod, qty))

for state in ['ambient', 'frozen', 'thawed']:
    if state in by_state:
        entries = by_state[state]
        total_qty = sum(qty for _, _, qty in entries)
        print(f"  {state}: {len(entries)} entries, {total_qty:.0f} units")

# Show Lineage inventory
if 'frozen' in by_state:
    print(f"\nLineage frozen inventory:")
    lineage_frozen = [(loc, prod, qty) for (loc, prod, qty) in by_state['frozen'] if loc == "Lineage"]
    for loc, prod, qty in lineage_frozen:
        print(f"  - {prod[:50]}: {qty:.0f}")

print("\n" + "="*80)
