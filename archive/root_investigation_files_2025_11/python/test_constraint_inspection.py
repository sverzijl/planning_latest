#!/usr/bin/env python3
"""Pyomo diagnostic: Inspect material balance constraint for manufacturing node."""

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

# 1-week
start = date(2025, 10, 17)
end = start + timedelta(days=6)

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']  # Just one product
products = create_test_products(product_ids)

print("="*80)
print("MATERIAL BALANCE CONSTRAINT INSPECTION")
print("="*80)

model_obj = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Build model (don't solve yet)
m = model_obj.build_model()

print(f"\nModel built. Inspecting ambient_balance_con for node 6122, day 1...")

# Check if ambient_balance_con exists
if hasattr(m, 'ambient_balance_con'):
    print(f"  ambient_balance_con exists: Yes")

    # Get constraint for manufacturing node, first product, first day
    node_id = '6122'
    prod = 'HELGAS GFREE MIXED GRAIN 500G'
    first_date = start

    if (node_id, prod, first_date) in m.ambient_balance_con:
        con = m.ambient_balance_con[node_id, prod, first_date]
        print(f"\n  Constraint: ambient_balance_con['{node_id}', '{prod[:30]}', {first_date}]")
        print(f"  Active: {con.active}")

        # Get constraint expression
        if con.expr is not None:
            expr_str = str(con.expr)
            print(f"\n  Expression (first 500 chars):")
            print(f"    {expr_str[:500]}")

            # Check if production appears
            has_production = 'production[' in expr_str
            print(f"\n  Contains 'production[': {has_production}")

            if has_production:
                print(f"    ✓ Production IS in material balance")
            else:
                print(f"    ✗ CRITICAL: Production NOT in material balance!")
                print(f"    This explains why production is unconstrained!")
        else:
            print(f"  ✗ Constraint has no expression!")
    else:
        print(f"  ✗ Constraint key not found!")
        print(f"  Available keys (first 5): {list(m.ambient_balance_con.keys())[:5]}")
else:
    print(f"  ✗ ambient_balance_con doesn't exist!")

print("="*80)
