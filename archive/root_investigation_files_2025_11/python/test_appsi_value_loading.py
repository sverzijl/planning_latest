#!/usr/bin/env python3
"""Test if APPSI HiGHS loads variable values correctly."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from pyomo.environ import value

# Parse data (minimal setup)
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

# Minimal setup
start = date(2025, 10, 17)
end = start + timedelta(days=6)  # 1 week

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("APPSI VALUE LOADING TEST")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Solve
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\nSolve: {result.termination_condition}")

if result.is_optimal():
    pyomo_model = model.model

    # Check production variables directly
    if hasattr(pyomo_model, 'production'):
        print(f"\nproduction variables exist: {len(list(pyomo_model.production))}")

        # Try to get values
        count_with_value = 0
        count_none_value = 0
        count_zero_value = 0

        for (node_id, prod, t) in list(pyomo_model.production)[:10]:
            var = pyomo_model.production[node_id, prod, t]

            # Method 1: var.value attribute
            val_attr = var.value if hasattr(var, 'value') else None

            # Method 2: Pyomo value() function
            try:
                val_func = value(var, exception=False)
            except:
                val_func = None

            print(f"\n  production[{node_id}, {prod[:20]}, {t}]:")
            print(f"    var.value: {val_attr}")
            print(f"    value(var): {val_func}")

            if val_attr is not None and abs(val_attr) > 0.01:
                count_with_value += 1
            elif val_func is not None and abs(val_func) > 0.01:
                count_with_value += 1
            elif val_attr == 0 or val_func == 0:
                count_zero_value += 1
            else:
                count_none_value += 1

        total_vars = len(list(pyomo_model.production))
        print(f"\nSummary ({total_vars} total production variables):")
        print(f"  With value: {count_with_value}")
        print(f"  Zero value: {count_zero_value}")
        print(f"  None value: {count_none_value}")

print("="*80)
