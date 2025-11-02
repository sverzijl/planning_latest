#!/usr/bin/env python3
"""Test: All 5 products, minimal inventory at plant only."""

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

# 4-week test
start = date(2025, 10, 17)
end = start + timedelta(days=27)

# All 5 products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Minimal initial inventory: 100 units each product at plant
initial_inv = {}
for prod_id in product_ids:
    initial_inv[('6122', prod_id, 'ambient')] = 100.0

print("="*80)
print("TEST: 5 products, 100 units each at plant (4 weeks)")
print("="*80)
print(f"Products: {len(product_ids)}")
print(f"Initial inventory: {sum(initial_inv.values()):.0f} units total")

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.01, tee=False)

print(f"\nResult: {result.termination_condition}")

if result.is_optimal():
    print("✓ OPTIMAL - 5 products with minimal inventory works!")
else:
    print(f"✗ {result.termination_condition} - Issue with 5-product setup")

print("="*80)
