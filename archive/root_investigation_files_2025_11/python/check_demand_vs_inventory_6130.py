#!/usr/bin/env python3
"""Check which products have demand vs inventory at 6130 on Oct 17"""

from datetime import date, timedelta
from src.parsers.excel_parser import ExcelParser
from src.parsers.product_alias_resolver import ProductAliasResolver
from src.parsers.inventory_parser import InventoryParser

INVENTORY_SNAPSHOT = date(2025, 10, 16)
PLANNING_START = date(2025, 10, 17)

resolver = ProductAliasResolver('data/examples/Network_Config.xlsx')

# Get demand
forecast_parser = ExcelParser('data/examples/Gluten Free Forecast - Latest.xlsm', resolver)
forecast_raw = forecast_parser.parse_forecast()

demand_oct17_6130 = [e for e in forecast_raw.entries if e.location_id == '6130' and e.forecast_date == PLANNING_START]

# Get inventory
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', resolver, INVENTORY_SNAPSHOT)
inv_snapshot = inv_parser.parse()

inv_6130 = {}
for entry in inv_snapshot.entries:
    if entry.location_id == '6130':
        product_id = resolver.resolve_product_id(entry.product_id) if resolver else entry.product_id
        inv_6130[product_id] = entry.quantity

print("="*80)
print("DEMAND vs INVENTORY at 6130 on Oct 17")
print("="*80)
print(f"{'Product':<45} {'Demand':>10} {'Inventory':>10} {'Gap':>10}")
print("-"*80)

all_products = set()
for e in demand_oct17_6130:
    all_products.add(e.product_id)
for p in inv_6130.keys():
    all_products.add(p)

total_demand = 0
total_inventory = 0
total_shortage = 0

for product in sorted(all_products):
    demand = sum(e.quantity for e in demand_oct17_6130 if e.product_id == product)
    inventory = inv_6130.get(product, 0)
    gap = demand - inventory

    total_demand += demand
    total_inventory += inventory
    if gap > 0:
        total_shortage += gap

    if demand > 0 or inventory > 0:
        gap_str = f"{gap:+.0f}" if gap != 0 else "0"
        print(f"{product:<45} {demand:>10.0f} {inventory:>10.0f} {gap_str:>10}")

print("-"*80)
print(f"{'TOTAL':<45} {total_demand:>10.0f} {total_inventory:>10.0f} {total_demand - total_inventory:+10.0f}")
print()
print(f"Inventory can cover: {total_inventory:.0f} / {total_demand:.0f} units ({100*total_inventory/total_demand if total_demand > 0 else 0:.1f}%)")
print(f"Expected Day 1 shortage if no arrivals: {max(0, total_demand - total_inventory):.0f} units")
print()

if total_inventory >= total_demand:
    print("✅ Sufficient inventory to meet Day 1 demand!")
    print("   Model SHOULD consume from inventory, not take shortages")
else:
    print(f"⚠️  Inventory insufficient for Day 1 demand")
    print(f"   Some shortages expected: {total_demand - total_inventory:.0f} units")
