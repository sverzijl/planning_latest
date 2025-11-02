#!/usr/bin/env python3
"""Check if initial inventory might be too old (expired)."""

from datetime import date, timedelta
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
print("INVENTORY AGE ANALYSIS")
print("="*80)

snapshot_date = inventory_data.snapshot_date
planning_start = date(2025, 10, 17)  # From simulation

print(f"\nSnapshot date (from file): {snapshot_date}")
print(f"Snapshot date (UI override): 2025-10-16")
print(f"Planning start: {planning_start}")

# Calculate age at planning start
age_from_file_snapshot = (planning_start - snapshot_date).days
age_from_ui_snapshot = (planning_start - date(2025, 10, 16)).days

print(f"\nAge at planning start:")
print(f"  If using file snapshot date: {age_from_file_snapshot} days")
print(f"  If using UI override (Oct 16): {age_from_ui_snapshot} day(s)")

print(f"\nShelf life limits:")
print(f"  Ambient: 17 days")
print(f"  Frozen: 120 days")
print(f"  Thawed: 14 days")

# Check by storage location
opt_dict = inventory_data.to_optimization_dict()

# Group by location
from collections import defaultdict
by_location = defaultdict(list)
for (loc, prod), qty in opt_dict.items():
    by_location[loc].append((prod, qty))

print(f"\nInventory by location:")
for loc in sorted(by_location.keys()):
    entries = by_location[loc]
    total = sum(qty for _, qty in entries)
    print(f"  {loc}: {len(entries)} products, {total:.0f} units")

# The critical question
print(f"\n" + "="*80)
print("CRITICAL QUESTION:")
print("="*80)
print(f"\nIf inventory snapshot is from {snapshot_date} ({age_from_file_snapshot} days before planning),")
print(f"and ambient inventory has 17-day shelf life,")
print(f"then inventory older than {17 - age_from_file_snapshot} days at snapshot is ALREADY EXPIRED!")

if age_from_file_snapshot >= 17:
    print(f"\n❌ PROBLEM: All ambient inventory would be expired!")
    print(f"   Snapshot is {age_from_file_snapshot} days old, but ambient shelf life is only 17 days")
elif age_from_file_snapshot > 0:
    print(f"\n⚠️  WARNING: Inventory has {age_from_file_snapshot} days of unknown age")
    print(f"   If any was produced more than {17 - age_from_file_snapshot} days before snapshot,")
    print(f"   it would be expired at planning start")
else:
    print(f"\n✓ Snapshot is same day as planning start")

print("="*80)
