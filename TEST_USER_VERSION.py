"""Test script - Run this and send me the output!

This will show:
1. What version of the code you're running
2. What results you get with the latest fixes
"""

import os
import subprocess
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import date, timedelta

print("=" * 80)
print("VERSION CHECK")
print("=" * 80)

# Check git commit
try:
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
    print(f"Git commit: {commit}")

    # Check if critical commit is in history
    has_phantom_fix = subprocess.call(['git', 'log', '--oneline', '--grep', 'CRITICAL.*phantom'], stdout=subprocess.DEVNULL) == 0
    print(f"Has phantom inventory fix (commit 38d1415): {has_phantom_fix}")
except:
    print("Git check failed - unable to verify version")

# Check if code has the fix
import inspect
source = inspect.getsource(SlidingWindowModel._add_variables)
has_separate_thaw_index = 'thaw_index' in source and 'supports_frozen_storage()' in source
print(f"Code has separate thaw_index (phantom fix): {has_separate_thaw_index}")

print("\n" + "=" * 80)
print("SOLVE TEST")
print("=" * 80)

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=False,
    use_truck_pallet_tracking=False
)

print(f"Solving 4-week horizon...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)
solution = model.get_solution()

print(f"\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

print(f"Status: {result.termination_condition}")
print(f"Solve time: {result.solve_time_seconds:.1f}s")
print(f"Total production: {solution['total_production']:,.0f} units")
print(f"Shortage: {solution.get('total_shortage_units', 0):,.0f} units")
print(f"Fill rate: {solution['fill_rate']*100:.1f}%")

by_product = {}
for (node, prod, date), qty in solution['production_by_date_product'].items():
    by_product[prod] = by_product.get(prod, 0) + qty

print(f"\nProduction by product:")
for prod in sorted(by_product.keys()):
    print(f"  {prod}: {by_product[prod]:,.0f} units")

labor = solution.get('labor_hours_by_date', {})
if labor:
    avg = sum(labor.values()) / len(labor)
    print(f"\nLabor: {sum(labor.values()):.0f}h total, {avg:.1f}h/day")

print(f"\n" + "=" * 80)
print("EXPECTED RESULTS (if you have the fix):")
print("=" * 80)
print("  Production: ~300k units")
print("  Products: ALL 5 products")
print("  Labor: ~11h/day average")
print("  Fill rate: 90-95%")

print(f"\n" + "=" * 80)
if solution['total_production'] > 250000:
    print("✅ CORRECT - You have the phantom inventory fix!")
elif solution['total_production'] < 100000:
    print("❌ WRONG - You DON'T have the fix yet!")
    print("   Please verify 'git pull' completed successfully")
    print("   Check commit: git log --oneline -1")
else:
    print("⚠️ PARTIAL - Something is still limiting production")

print("=" * 80)
print("\nPLEASE SEND ME THIS ENTIRE OUTPUT!")
