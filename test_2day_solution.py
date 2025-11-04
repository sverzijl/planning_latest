#!/usr/bin/env python3
"""Test 2-day model to see if it produces."""

from datetime import date, timedelta
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

# 2 days
start = date(2025, 10, 17)
end = start + timedelta(days=1)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Calculate expected
total_demand = sum(e.quantity for e in forecast.entries if start <= e.forecast_date <= end)
day1_demand = sum(e.quantity for e in forecast.entries if e.forecast_date == start)
day2_demand = total_demand - day1_demand

print("="*80)
print("2-DAY SOLUTION TEST")
print("="*80)
print(f"\nDemand:")
print(f"  Day 1: {day1_demand:,.0f} (must be shortage - no time to produce+ship)")
print(f"  Day 2: {day2_demand:,.0f} (CAN produce day 1 → arrive day 2)")
print(f"  Total: {total_demand:,.0f}")

print(f"\nExpected:")
print(f"  Production day 1: ~{day2_demand:,.0f} units (for day 2 demand)")
print(f"  Shortage day 1: {day1_demand:,.0f} units")
print(f"  Shortage day 2: 0 units")

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\n" + "="*80)
print("ACTUAL SOLUTION:")
print("="*80)

if result.is_optimal():
    m = model.model

    total_prod = sum(pyo.value(m.production[k], exception=False) or 0 for k in m.production)
    total_short = sum(pyo.value(m.shortage[k], exception=False) or 0 for k in m.shortage)

    print(f"  Total production: {total_prod:,.0f} units")
    print(f"  Total shortage: {total_short:,.0f} units")
    print(f"  Objective: ${pyo.value(m.obj):,.2f}")

    if total_prod > 10000:
        print(f"\n  ✓ Model IS producing for 2-day horizon!")
    else:
        print(f"\n  ✗ Still zero production even with 2 days")
        print(f"     Expected: ~{day2_demand:,.0f} units")
        print(f"     This confirms a fundamental bug in the model")

print("="*80)
