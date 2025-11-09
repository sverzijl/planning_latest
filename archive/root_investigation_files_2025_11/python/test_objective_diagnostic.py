#!/usr/bin/env python3
"""Diagnostic: Inspect objective function components using Pyomo."""

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

# Parse inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()
inventory_data.snapshot_date = date(2025, 10, 16)

# Convert
inv_2tuple = inventory_data.to_optimization_dict()
initial_inv = {}
loc_dict = {loc.id: loc for loc in locations}
for (location, product), quantity in inv_2tuple.items():
    loc_node = loc_dict.get(location)
    if loc_node and str(loc_node.storage_mode) == 'frozen':
        state = 'frozen'
    else:
        state = 'ambient'
    initial_inv[(location, product, state)] = quantity

# 1-week
start = date(2025, 10, 17)
end = start + timedelta(days=6)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("OBJECTIVE FUNCTION DIAGNOSTIC")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    inventory_snapshot_date=inventory_data.snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\nSolve: {result.termination_condition}")

if result.is_optimal():
    pyomo_model = model.model

    # Check if objective exists
    print(f"\nObjective function:")
    if hasattr(pyomo_model, 'obj'):
        obj = pyomo_model.obj
        print(f"  Objective exists: Yes")
        print(f"  Objective value: ${pyo.value(obj):,.2f}")
        print(f"  Sense: {obj.sense}")

        # Get the objective expression
        obj_expr = obj.expr
        print(f"\n  Expression type: {type(obj_expr)}")

        # Try to decompose expression to see components
        # Pyomo expressions are trees - we can't easily decompose sums
        # But we can evaluate individual cost variables if they exist in the model

        # Check for cost-related variables that might be in objective
        cost_vars = ['labor_hours_used', 'overtime_hours', 'shortage', 'disposal', 'production']
        print(f"\n  Checking if cost-related variables appear in model:")
        for var_name in cost_vars:
            has_var = hasattr(pyomo_model, var_name)
            print(f"    {var_name}: {has_var}")

        # Calculate individual cost components manually
        print(f"\n  Manual cost component calculation:")

        # Production cost
        prod_cost_total = 0
        if hasattr(pyomo_model, 'production'):
            prod_cost_per_unit = cost_params.production_cost_per_unit or 1.30
            for key in pyomo_model.production:
                val = pyo.value(pyomo_model.production[key])
                if val:
                    prod_cost_total += val * prod_cost_per_unit
        print(f"    Production: ${prod_cost_total:,.2f}")

        # Shortage cost
        shortage_cost_total = 0
        if hasattr(pyomo_model, 'shortage'):
            shortage_penalty = cost_params.shortage_penalty_per_unit
            for key in pyomo_model.shortage:
                val = pyo.value(pyomo_model.shortage[key])
                if val:
                    shortage_cost_total += val * shortage_penalty
        print(f"    Shortage: ${shortage_cost_total:,.2f}")

        # Disposal cost
        disposal_cost_total = 0
        if hasattr(pyomo_model, 'disposal'):
            disposal_penalty = shortage_penalty * 1.5  # From model
            for key in pyomo_model.disposal:
                val = pyo.value(pyomo_model.disposal[key])
                if val:
                    disposal_cost_total += val * disposal_penalty
        print(f"    Disposal: ${disposal_cost_total:,.2f}")

        # Waste cost (end-of-horizon inventory)
        waste_cost_total = 0
        last_date = end
        total_end_inv = 0
        for (node_id, prod, state, t) in pyomo_model.inventory:
            if t == last_date:
                val = pyo.value(pyomo_model.inventory[node_id, prod, state, t])
                if val:
                    total_end_inv += val
        waste_mult = cost_params.waste_cost_multiplier or 10.0
        prod_cost_per_unit = cost_params.production_cost_per_unit or 1.30
        waste_cost_total = waste_mult * prod_cost_per_unit * total_end_inv
        print(f"    Waste (end inv): ${waste_cost_total:,.2f} ({total_end_inv:,.0f} units × ${waste_mult * prod_cost_per_unit:.2f})")

        manual_total = prod_cost_total + shortage_cost_total + disposal_cost_total + waste_cost_total
        print(f"\n  Manual total: ${manual_total:,.2f}")
        print(f"  Objective value: ${pyo.value(obj):,.2f}")
        print(f"  Difference: ${abs(manual_total - pyo.value(obj)):,.2f}")

        if abs(manual_total - pyo.value(obj)) > 1000:
            print(f"\n  ⚠️  Large difference suggests missing cost components!")
        else:
            print(f"\n  ✓ Cost components match objective")

print("="*80)
