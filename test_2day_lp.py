#!/usr/bin/env python3
"""Generate 2-day LP to check if arrivals appear on day 2."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

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

# 2 days
start = date(2025, 10, 17)
end = start + timedelta(days=1)

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

print("="*80)
print("2-DAY LP GENERATION")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

m = model.build_model()
m.write('test_2day.lp', format='lp', io_options={'symbolic_solver_labels': True})

print(f"\nGenerated test_2day.lp")

# Check day 1 balance
import subprocess
result = subprocess.run(['grep', '-A', '10', 'ambient_balance_con(_6104__HELGAS_GFREE_MIXED_GRAIN_500G_2025-10-17', 'test_2day.lp'], capture_output=True, text=True)
print(f"\nDay 1 (2025-10-17) balance for hub 6104:")
print(result.stdout)

# Check day 2 balance
result2 = subprocess.run(['grep', '-A', '10', 'ambient_balance_con(_6104__HELGAS_GFREE_MIXED_GRAIN_500G_2025-10-18', 'test_2day.lp'], capture_output=True, text=True)
print(f"\nDay 2 (2025-10-18) balance for hub 6104:")
print(result2.stdout)

# Check if day 2 includes arrivals (goods that departed day 1)
has_arrivals_day2 = 'in_transit(_6122___6104__HELGAS_GFREE_MIXED_GRAIN_500G_2025-10-17_ambient)' in result2.stdout
print(f"\nDay 2 includes arrivals from day 1 shipment: {has_arrivals_day2}")

if has_arrivals_day2:
    print("  ✓ Arrivals ARE included on day 2")
    print("  Model should be able to produce day 1 → arrive day 2 → consume day 2")
else:
    print("  ✗ Arrivals NOT included on day 2!")
    print("  This is the bug - production can't flow to demand nodes")

print("="*80)
