#!/usr/bin/env python3
"""Diagnostic: Check initial inventory by location and inferred state."""

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

# Convert to 2-tuple format (as workflow does)
inv_2tuple = inventory_data.to_optimization_dict()

# Build location dict
loc_dict = {loc.id: loc for loc in locations}

print("="*80)
print("INITIAL INVENTORY BY LOCATION")
print("="*80)

# Group by location
from collections import defaultdict
by_location = defaultdict(list)
for (location_id, product_id), qty in inv_2tuple.items():
    by_location[location_id].append((product_id, qty))

print(f"\nTotal inventory entries: {len(inv_2tuple)}")
print(f"\nInventory by location:")

for location_id in sorted(by_location.keys()):
    entries = by_location[location_id]
    total_qty = sum(qty for _, qty in entries)

    # Get location info
    loc = loc_dict.get(location_id)
    if loc:
        storage_mode = loc.storage_mode
        loc_name = loc.name
    else:
        storage_mode = "UNKNOWN"
        loc_name = "UNKNOWN"

    print(f"\n{location_id}: {loc_name}")
    print(f"  Storage mode: {storage_mode}")
    print(f"  Entries: {len(entries)}, Total: {total_qty:.0f} units")

    # Determine inferred state (as workflow does - always 'ambient')
    inferred_state = 'ambient'
    print(f"  Workflow inferred state: {inferred_state}")

    # Check for conflict
    if storage_mode == "frozen" and inferred_state == "ambient":
        print(f"  *** CONFLICT: Location only supports FROZEN but inventory is AMBIENT! ***")

    # Show entries
    for prod, qty in entries:
        print(f"    - {prod[:50]}: {qty:.0f}")

print("\n" + "="*80)
print("\nSUMMARY:")
print("  Workflow converts ALL inventory to (location, product, 'ambient') format")
print("  BUT Lineage location only supports FROZEN storage!")
print("  This creates a constraint violation in the model.")
print("="*80)
