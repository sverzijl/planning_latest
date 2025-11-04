#!/usr/bin/env python3
"""Pyomo diagnostic: Why isn't model producing?"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
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

# 1-week, NO initial inventory to isolate production behavior
start = date(2025, 10, 17)
end = start + timedelta(days=6)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("WHY NO PRODUCTION DIAGNOSTIC")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\nSolve: {result.termination_condition}")

if result.is_optimal():
    m = model.model

    # Check production variable bounds and values
    print(f"\nProduction variables (first 10):")
    count = 0
    for key in m.production:
        if count >= 10:
            break
        var = m.production[key]
        val = pyo.value(var)
        lb = var.lb if var.lb is not None else "None"
        ub = var.ub if var.ub is not None else "None"
        print(f"  production{key}: value={val:.2f}, bounds=[{lb}, {ub}]")
        count += 1

    # Check if production is in objective
    obj_expr = m.obj.expr
    obj_str = str(obj_expr)[:500]  # First 500 chars
    has_production_in_obj = 'production[' in obj_str
    print(f"\nProduction in objective expression: {has_production_in_obj}")
    if has_production_in_obj:
        print(f"  ✓ Production cost is in objective")
    else:
        print(f"  ✗ Production cost MISSING from objective!")

    # Calculate what production WOULD cost if we produced the shortfall
    total_shortage = sum(pyo.value(m.shortage[k]) for k in m.shortage if pyo.value(m.shortage[k]) > 0)
    print(f"\nCurrent solution:")
    print(f"  Shortage: {total_shortage:,.0f} units × $10 = ${total_shortage * 10:,.2f}")

    print(f"\nIf model produced instead:")
    print(f"  Production: {total_shortage:,.0f} units × $1.30 = ${total_shortage * 1.30:,.2f}")
    print(f"  Savings: ${total_shortage * 10 - total_shortage * 1.30:,.2f}")
    print(f"  Model SHOULD prefer production!")

    # Check production constraints
    print(f"\nProduction-related constraints:")
    for c in m.component_objects(pyo.Constraint, active=True):
        name = c.name
        if 'production' in name.lower() or 'mix' in name.lower():
            print(f"  - {name}: {len(list(c))} constraints")

print("="*80)
