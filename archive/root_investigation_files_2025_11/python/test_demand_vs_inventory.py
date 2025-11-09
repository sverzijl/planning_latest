#!/usr/bin/env python3
"""Check if initial inventory is sufficient to cover demand."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast_data, _, _, _, _, _ = parser.parse_all()

# Parse inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()

# 1-week horizon
start = date(2025, 10, 17)
end = start + timedelta(days=6)

# Calculate demand
total_demand = sum(
    e.quantity
    for e in forecast_data.entries
    if start <= e.forecast_date <= end
)

# Calculate inventory
total_inventory = sum(e.quantity for e in inventory_data.entries)

print("="*80)
print("DEMAND vs INVENTORY ANALYSIS (1-week horizon)")
print("="*80)
print(f"\nPlanning horizon: {start} to {end} (7 days)")
print(f"\nTotal demand: {total_demand:,.0f} units")
print(f"Total initial inventory: {total_inventory:,.0f} units")
print(f"Coverage: {total_inventory / total_demand * 100:.1f}%")

if total_inventory >= total_demand:
    print("\n✓ Initial inventory covers ALL demand")
    print("  Optimal solution: ZERO production (use inventory only)")
    print("  This is CORRECT economic behavior!")
else:
    print("\n  Initial inventory does NOT cover demand")
    print(f"  Shortfall: {total_demand - total_inventory:,.0f} units")
    print("  Model should produce to fill gap")

print("="*80)
