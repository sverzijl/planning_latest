#!/usr/bin/env python3
"""Find which constraint becomes infeasible when production = 5000."""

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

# 1 day
start = date(2025, 10, 17)
end = start

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

print("="*80)
print("FIND INFEASIBLE CONSTRAINT")
print("="*80)

model_obj = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

m = model_obj.build_model()

# Fix production
node_id = '6122'
prod_id = 'HELGAS GFREE MIXED GRAIN 500G'
day1 = start

print(f"\nSetting production[{node_id}, {prod_id[:30]}, {day1}] = 1000")
m.production[node_id, prod_id, day1].fix(1000)

# Set other decision variables manually to trace through
# If production = 1000, what must happen?

# From material balance: inventory + shipments = production
# So we need: inventory + shipments = 1000

# Let's check what constraints involve this production variable
print(f"\nConstraints involving production[{node_id}, {prod_id[:30]}, {day1}]:")

# Mix-based: production = mix_count × units_per_mix
if hasattr(m, 'mix_production_con') and (node_id, prod_id, day1) in m.mix_production_con:
    con = m.mix_production_con[node_id, prod_id, day1]
    print(f"  mix_production_con: {con.expr}")
    # With production = 1000, this forces mix_count = 1000/415 = 2.41
    # But mix_count is integer, so infeasible?

# Check if mix_count is integer
if hasattr(m, 'mix_count') and (node_id, prod_id, day1) in m.mix_count:
    mix_var = m.mix_count[node_id, prod_id, day1]
    print(f"  mix_count domain: {mix_var.domain}")
    print(f"  mix_count bounds: [{mix_var.lb}, {mix_var.ub}]")

    # Get units_per_mix
    product = products[prod_id]
    units_per_mix = product.units_per_mix if hasattr(product, 'units_per_mix') else 415
    print(f"  units_per_mix: {units_per_mix}")
    print(f"  Required mix_count: 1000 / {units_per_mix} = {1000 / units_per_mix:.2f}")

    if mix_var.is_integer():
        print(f"\n  ✗ BUG FOUND: mix_count is INTEGER!")
        print(f"     production = 1000 requires mix_count = {1000/units_per_mix:.2f}")
        print(f"     But mix_count must be integer!")
        print(f"     This makes production = 1000 INFEASIBLE!")
        print(f"\n     Production must be in multiples of {units_per_mix}")
        print(f"     Nearest valid: {int(1000/units_per_mix) * units_per_mix} or {int(1000/units_per_mix + 1) * units_per_mix}")

print("="*80)
