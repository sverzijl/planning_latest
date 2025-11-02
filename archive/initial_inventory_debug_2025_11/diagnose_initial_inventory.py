#!/usr/bin/env python3
"""Diagnostic: Examine initial inventory structure and values."""

from src.parsers.excel_parser import ExcelParser
from src.parsers.inventory_parser import InventoryParser
from src.models.product import Product

# Parse data
parser = ExcelParser("data/examples/Gluten Free Forecast - Latest.xlsm")
result = parser.parse_all()

# Parse inventory with alias resolver
inventory_parser = InventoryParser()
inventory_data = inventory_parser.parse_file(
    "data/examples/inventory_latest.XLSX",
    alias_resolver=result.alias_resolver
)

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
    print(f"  WARNING: {len(negative)} negative quantities")
    for e in negative[:5]:
        print(f"    {e.location_id}, {e.product_id}, {e.state}: {e.quantity}")

zero = [e for e in inventory_data.entries if e.quantity == 0]
if zero:
    print(f"  INFO: {len(zero)} zero quantities")

large = [e for e in inventory_data.entries if e.quantity > 10000]
if large:
    print(f"  INFO: {len(large)} entries > 10,000 units")
    for e in large:
        print(f"    {e.location_id}, {e.product_id[:30]}, {e.state}: {e.quantity:.0f}")

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
else:
    print(f"  OK: No duplicates")

# Compare product IDs
print(f"\nProduct ID matching:")
print(f"  Forecast products: {len(result.products)}")
product_ids = set(result.products.keys())
inventory_product_ids = set(e.product_id for e in inventory_data.entries)
print(f"  Inventory products: {len(inventory_product_ids)}")
matched = product_ids & inventory_product_ids
print(f"  Matched: {len(matched)} products")
if matched:
    print(f"  Matched products: {sorted(matched)[:3]}...")

# Show sample entries
print(f"\nSample entries (first 10):")
for i, entry in enumerate(inventory_data.entries[:10]):
    print(f"  {i+1}. {entry.location_id}, {entry.product_id[:40]}, {entry.state}: {entry.quantity:.0f}")

print("\n" + "="*80)
