#!/usr/bin/env python3
"""Force production by disallowing shortages and removing initial inventory."""

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

# 1-week, NO inventory
start = date(2025, 10, 17)
end = start + timedelta(days=6)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("TEST: Force production (no inventory, no shortages)")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=False,  # MUST PRODUCE
    use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.01, tee=False)

print(f"\nResult: {result.termination_condition}")

if result.is_optimal():
    pyomo_model = model.model

    total_prod = 0
    if hasattr(pyomo_model, 'production'):
        for key in pyomo_model.production:
            val = value(pyomo_model.production[key])
            if val and abs(val) > 0.01:
                total_prod += val

    total_consumed = 0
    if hasattr(pyomo_model, 'demand_consumed'):
        for key in pyomo_model.demand_consumed:
            val = value(pyomo_model.demand_consumed[key])
            if val and abs(val) > 0.01:
                total_consumed += val

    print(f"\nProduction: {total_prod:,.0f} units")
    print(f"Consumed: {total_consumed:,.0f} units")

    if total_prod > 10000:
        print("✓ PASS: Model produces when forced")
    else:
        print("✗ FAIL: Still not producing (fundamental constraint bug)")
else:
    print(f"✗ INFEASIBLE: {result.termination_condition}")
    print("This confirms there's a constraint preventing demand satisfaction")

print("="*80)
