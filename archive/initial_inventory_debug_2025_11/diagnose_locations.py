#!/usr/bin/env python3
"""Diagnostic: Show location storage modes."""

from src.parsers.multi_file_parser import MultiFileParser

# Parse files
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

_, locations, _, _, _, _ = parser.parse_all()

print("="*80)
print("LOCATION STORAGE MODES")
print("="*80)

for loc in locations:
    print(f"{loc.id:6s} {loc.name:30s} type={loc.type:15s} storage={loc.storage_mode}")

print("\n" + "="*80)

# Group by storage mode
from collections import defaultdict
by_mode = defaultdict(list)
for loc in locations:
    by_mode[loc.storage_mode].append(loc)

print("\nBy storage mode:")
for mode, locs in sorted(by_mode.items()):
    print(f"  {mode}: {len(locs)} locations")
    for loc in locs:
        print(f"    - {loc.id}: {loc.name}")

print("\n" + "="*80)
