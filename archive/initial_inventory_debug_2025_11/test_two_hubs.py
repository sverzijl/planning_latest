#!/usr/bin/env python3
"""Test: 1 product at TWO hubs (6104 and 6125)."""

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

# 2-day test
start = date(2025, 10, 17)
end = start + timedelta(days=1)

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

# Initial inventory at TWO hubs
initial_inv = {
    ('6104', 'HELGAS GFREE MIXED GRAIN 500G', 'ambient'): 100.0,
    ('6125', 'HELGAS GFREE MIXED GRAIN 500G', 'ambient'): 100.0,
}

print("="*80)
print("TEST: 1 product at TWO hubs (6104 and 6125), 2-day horizon")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)

print(f"\nResult: {result.termination_condition}")

if result.is_optimal():
    print("✓ OPTIMAL - Multiple locations work!")
else:
    print("✗ INFEASIBLE - Multiple demand nodes with same product fails!")

print("="*80)
