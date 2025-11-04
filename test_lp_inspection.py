#!/usr/bin/env python3
"""Write LP file with symbolic labels and inspect."""

from datetime import date
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
import pyomo.environ as pyo

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# 1 day, 1 product
start = date(2025, 10, 17)
end = start

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

print("="*80)
print("LP FILE INSPECTION WITH SYMBOLIC LABELS")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

m = model.build_model()

# Write with symbolic labels
m.write('test_symbolic.lp', format='lp', io_options={'symbolic_solver_labels': True})
print(f"\nWrote model to test_symbolic.lp with symbolic labels")

# Check for production in file
import subprocess
result = subprocess.run(['grep', '-c', 'production\\[', 'test_symbolic.lp'], capture_output=True, text=True)
count = int(result.stdout.strip()) if result.returncode == 0 else 0

print(f"  Occurrences of 'production[' in LP file: {count}")

if count > 0:
    print(f"  ✓ Production variables appear in LP file")
    # Show first few occurrences
    result2 = subprocess.run(['grep', 'production\\[', 'test_symbolic.lp'], capture_output=True, text=True)
    lines = result2.stdout.strip().split('\n')[:10]
    print(f"\n  First occurrences:")
    for line in lines:
        print(f"    {line[:100]}")
else:
    print(f"  ✗ Production does NOT appear in LP file!")
    print(f"  This means Pyomo is eliminating it during LP write")

# Check objective
result3 = subprocess.run(['head', '-50', 'test_symbolic.lp'], capture_output=True, text=True)
print(f"\n  Objective function (first 30 lines):")
obj_lines = result3.stdout.strip().split('\n')[2:32]  # Skip header
for line in obj_lines:
    print(f"    {line}")

print("="*80)
