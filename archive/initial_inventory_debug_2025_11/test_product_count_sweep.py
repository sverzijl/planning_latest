#!/usr/bin/env python3
"""Test: Increasing number of products at hub 6125."""

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

all_product_ids = [
    'HELGAS GFREE MIXED GRAIN 500G',
    'HELGAS GFREE TRAD WHITE 470G',
    'HELGAS GFREE WHOLEM 500G',
    'WONDER GFREE WHITE 470G',
    'WONDER GFREE WHOLEM 500G'
]

print("="*80)
print("PRODUCT COUNT SWEEP (at hub 6125)")
print("="*80)

for n_products in [1, 2, 3, 4, 5]:
    product_ids = all_product_ids[:n_products]
    products = create_test_products(product_ids)

    # Initial inventory: 100 units each
    initial_inv = {}
    for prod_id in product_ids:
        initial_inv[('6125', prod_id, 'ambient')] = 100.0

    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params, start_date=start, end_date=end,
        truck_schedules=unified_trucks, initial_inventory=initial_inv,
        allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)

    status = "✓ OPTIMAL" if result.is_optimal() else f"✗ {result.termination_condition}"
    print(f"{n_products} products: {status}")

print("="*80)
