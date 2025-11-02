#!/usr/bin/env python3
"""Test with allow_shortages=False to force production."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from pyomo.environ import value

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

# 1-week, empty inventory
start = date(2025, 10, 17)
end = start + timedelta(days=6)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("TEST: No shortages allowed (should force production)")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=False,  # FORCE PRODUCTION
    use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\nResult: {result.termination_condition}")

if result.is_optimal():
    pyomo_model = model.model

    # Check production
    total_prod = 0
    count_nonzero = 0
    if hasattr(pyomo_model, 'production'):
        for (node_id, prod, t) in pyomo_model.production:
            val = value(pyomo_model.production[node_id, prod, t])
            if val and abs(val) > 0.01:
                total_prod += val
                count_nonzero += 1

    print(f"Total production: {total_prod:,.0f} units")
    print(f"Non-zero production variables: {count_nonzero}")

    if total_prod > 0:
        print("✓ PASS: Model produces when shortages not allowed")
    else:
        print("✗ FAIL: Still zero production (constraint bug)")

print("="*80)
