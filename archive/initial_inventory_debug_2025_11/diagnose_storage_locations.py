#!/usr/bin/env python3
"""Diagnostic: Check storage location mapping."""

from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser

# Parse files
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

# Get alias resolver
alias_resolver = parser.parse_product_aliases()

# Parse inventory with alias resolver
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()

print("="*80)
print("STORAGE LOCATION DIAGNOSTIC")
print("="*80)

# Group by storage location
from collections import defaultdict
by_storage = defaultdict(list)
for entry in inventory_data.entries:
    storage_loc = entry.storage_location if entry.storage_location else "None"
    by_storage[storage_loc].append(entry)

print(f"\nTotal inventory entries: {len(inventory_data.entries)}")
print(f"\nBreakdown by storage_location:")

for storage_loc in sorted(by_storage.keys()):
    entries = by_storage[storage_loc]
    total_qty = sum(e.quantity for e in entries)
    print(f"\n{storage_loc}: {len(entries)} entries, {total_qty:.0f} units")

    # Show unique locations
    unique_locs = set(e.location_id for e in entries)
    print(f"  Location IDs: {sorted(unique_locs)}")

    # Show first few entries
    for entry in entries[:3]:
        print(f"    - location={entry.location_id}, product={entry.product_id[:40]}, qty={entry.quantity:.0f}")

print("\n" + "="*80)
print("\nISSUE:")
print("  Storage location 4070 should map to location 'Lineage'")
print("  BUT to_optimization_dict() ignores storage_location!")
print("  Result: 4070 inventory stays at location_id (e.g., 6122) instead of Lineage")
print("="*80)

# Check what to_optimization_dict produces
print("\nWhat to_optimization_dict() produces:")
opt_dict = inventory_data.to_optimization_dict()
for (loc_id, prod_id), qty in list(opt_dict.items())[:5]:
    print(f"  ({loc_id}, {prod_id[:40]}): {qty:.0f}")

print(f"\nTotal entries in optimization dict: {len(opt_dict)}")
print("="*80)
