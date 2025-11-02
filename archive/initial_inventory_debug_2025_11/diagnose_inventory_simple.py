#!/usr/bin/env python3
"""Simple diagnostic: Examine initial inventory structure."""

from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser

# Parse network file to get alias resolver
print("Parsing files...")
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

# Get alias resolver
alias_resolver = parser.parse_product_aliases()
print(f"Alias resolver: {alias_resolver}\n")

# Parse inventory with alias resolver
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()

print("="*80)
print("INITIAL INVENTORY DIAGNOSTIC")
print("="*80)

print(f"\nInventory snapshot date: {inventory_data.snapshot_date}")
print(f"Total entries: {len(inventory_data.entries)}")

# Group by state
by_state = {}
for entry in inventory_data.entries:
    state = entry.state
    if state not in by_state:
        by_state[state] = []
    by_state[state].append(entry)

print(f"\nBreakdown by state:")
for state, entries in by_state.items():
    total_qty = sum(e.quantity for e in entries)
    print(f"  {state}: {len(entries)} entries, {total_qty:.0f} units")

# Check for unusual values
print(f"\nChecking for unusual values:")

negative = [e for e in inventory_data.entries if e.quantity < 0]
if negative:
    print(f"  WARNING: {len(negative)} negative quantities (should have been set to 0)")

zero = [e for e in inventory_data.entries if e.quantity == 0]
if zero:
    print(f"  INFO: {len(zero)} zero quantities")

large = [e for e in inventory_data.entries if e.quantity > 10000]
if large:
    print(f"  INFO: {len(large)} entries > 10,000 units")
    for e in large:
        print(f"    {e.location_id}, {e.product_id[:40]}, {e.state}: {e.quantity:.0f}")

# Check for duplicate keys
print(f"\nChecking for duplicates:")
keys = [(e.location_id, e.product_id, e.state) for e in inventory_data.entries]
unique_keys = set(keys)
if len(keys) != len(unique_keys):
    print(f"  WARNING: Found {len(keys) - len(unique_keys)} duplicate keys")
    from collections import Counter
    counts = Counter(keys)
    for key, count in counts.items():
        if count > 1:
            print(f"    {key}: {count} occurrences")
            # Show the duplicate entries
            dupes = [e for e in inventory_data.entries if (e.location_id, e.product_id, e.state) == key]
            for d in dupes:
                print(f"      quantity={d.quantity}")
else:
    print(f"  OK: No duplicates")

# Show sample entries
print(f"\nAll entries:")
for i, entry in enumerate(inventory_data.entries):
    print(f"  {i+1}. ({entry.location_id}, {entry.product_id[:40]}, {entry.state}): {entry.quantity:.0f}")

print("\n" + "="*80)
