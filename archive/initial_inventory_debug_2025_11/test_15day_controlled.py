#!/usr/bin/env python3
"""Controlled test: 15 days with manually constructed inventory."""

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

# 15-day test
start = date(2025, 10, 17)
end = start + timedelta(days=14)  # 15 days

# All 5 products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("15-DAY CONTROLLED TEST")
print("="*80)

# Test cases with specific inventory setups
test_cases = [
    ("Empty", {}),
    ("Plant only, 500 units each", {
        ('6122', prod, 'ambient'): 500.0 for prod in product_ids
    }),
    ("Hub 6125 only, 500 units each", {
        ('6125', prod, 'ambient'): 500.0 for prod in product_ids
    }),
    ("Plant + Hub 6125, 500 units each", {
        **{('6122', prod, 'ambient'): 500.0 for prod in product_ids},
        **{('6125', prod, 'ambient'): 500.0 for prod in product_ids}
    }),
]

for name, inv in test_cases:
    total = sum(inv.values()) if inv else 0

    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params, start_date=start, end_date=end,
        truck_schedules=unified_trucks, initial_inventory=inv if inv else None,
        allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

    status = "✓ OPTIMAL" if result.is_optimal() else f"✗ {result.termination_condition}"
    print(f"{name:35s} ({total:5.0f} units): {status}")

print("="*80)
