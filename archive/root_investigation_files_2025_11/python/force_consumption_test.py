#!/usr/bin/env python3
"""
CONSTRAINT PROBING TEST: Force ambient consumption at 6130

If forcing consumption produces LOWER objective → MIP gap issue (solver didn't find optimal)
If forcing consumption produces HIGHER objective or infeasible → Formulation bug
"""

import sys
import os
os.environ['PYOMO_LOG_LEVEL'] = 'ERROR'

from datetime import date, timedelta
from pyomo.environ import value
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.excel_parser import ExcelParser
from src.parsers.product_alias_resolver import ProductAliasResolver
from src.parsers.inventory_parser import InventoryParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast
from src.models.location import LocationType

INVENTORY_SNAPSHOT = date(2025, 10, 16)
PLANNING_START = date(2025, 10, 17)
PLANNING_END = PLANNING_START + timedelta(days=27)

resolver = ProductAliasResolver('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gluten Free Forecast - Latest.xlsm', resolver)
forecast_raw = forecast_parser.parse_forecast()
forecast_filtered = [e for e in forecast_raw.entries if PLANNING_START <= e.forecast_date <= PLANNING_END]
forecast_obj = Forecast(name="Oct17", entries=forecast_filtered)

parser = MultiFileParser('data/examples/Gluten Free Forecast - Latest.xlsm', 'data/examples/Network_Config.xlsx', 'data/examples/inventory_latest.XLSX')
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast_obj)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

network_parser = ExcelParser('data/examples/Network_Config.xlsx', resolver)
products_dict = network_parser.parse_products()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', resolver, INVENTORY_SNAPSHOT)
inv_snapshot = inv_parser.parse()
inv_dict = {}
for entry in inv_snapshot.entries:
    product_id = resolver.resolve_product_id(entry.product_id) if resolver else entry.product_id
    inv_dict[(entry.location_id, product_id, 'ambient')] = entry.quantity

cost_structure.waste_cost_multiplier = 10.0

print("="*80)
print("CONSTRAINT PROBING: Force Ambient Consumption at 6130")
print("="*80)

# BASELINE SOLVE (5% MIP gap, unconstrained)
print("\n1. BASELINE SOLVE (unconstrained, 5% MIP gap)")
print("-"*80)

model_builder = SlidingWindowModel(nodes, unified_routes, forecast_obj, labor_calendar, cost_structure, products_dict, PLANNING_START, PLANNING_END, unified_truck_schedules, inv_dict, INVENTORY_SNAPSHOT, True, True, True)
result_baseline = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05)

model = model_builder.model
product = 'HELGAS GFREE MIXED GRAIN 500G'
t = PLANNING_START
key = ('6130', product, t)

baseline_obj = result_baseline.objective_value
baseline_cons = value(model.demand_consumed_from_ambient[key])
baseline_short = value(model.shortage[key])
baseline_demand = model_builder.demand.get(key, 0)

print(f"Objective: ${baseline_obj:,.2f}")
print(f"Demand at 6130 for {product} on Oct 17: {baseline_demand:.2f}")
print(f"Consumption (ambient): {baseline_cons:.2f}")
print(f"Shortage: {baseline_short:.2f}")

# FORCED CONSUMPTION TEST
print("\n2. FORCED CONSUMPTION SOLVE")
print("-"*80)
print(f"Forcing: consumption = {baseline_demand:.2f} (meet all demand)")

# Rebuild model
model_builder2 = SlidingWindowModel(nodes, unified_routes, forecast_obj, labor_calendar, cost_structure, products_dict, PLANNING_START, PLANNING_END, unified_truck_schedules, inv_dict, INVENTORY_SNAPSHOT, True, True, True)

# Build model first
from pyomo.environ import Constraint
model2 = model_builder2.build_model()

# FORCE consumption to meet demand
key_cons = ('6130', product, t)
if key_cons in model2.demand_consumed_from_ambient:
    print(f"Fixing consumption variable to {baseline_demand:.2f}")
    model2.demand_consumed_from_ambient[key_cons].fix(baseline_demand)
else:
    print("❌ Variable doesn't exist!")
    sys.exit(1)

# Solve with fixed consumption
from pyomo.opt import SolverFactory
solver = SolverFactory('appsi_highs')
solver.options['mip_gap'] = 0.05
solver.options['time_limit'] = 60

print("Solving...")
result_forced = solver.solve(model2, tee=False, load_solutions=False)

print(f"\nResult: {result_forced.solver.termination_condition}")
print(f"Status: {result_forced.solver.status if hasattr(result_forced.solver, 'status') else 'N/A'}")

if str(result_forced.solver.termination_condition) == 'optimal':
    # Get objective
    forced_obj = value(model2.obj)

    print(f"Objective: ${forced_obj:,.2f}")
    print()

    print("="*80)
    print("COMPARISON")
    print("="*80)
    print(f"  Baseline (consumption=0):       ${baseline_obj:,.2f}")
    print(f"  Forced (consumption={baseline_demand:.0f}):  ${forced_obj:,.2f}")
    print(f"  Difference:                     ${baseline_obj - forced_obj:+,.2f}")
    print()

    if forced_obj < baseline_obj:
        savings = baseline_obj - forced_obj
        print(f"✅ FORCED CONSUMPTION IS BETTER by ${savings:,.2f}!")
        print()
        print("ROOT CAUSE: MIP Gap Issue")
        print("  The optimal solution consumes ambient inventory")
        print("  But 5% MIP gap allows solver to stop at suboptimal solution")
        print("  Solution: Use tighter MIP gap (1-2%) or add branching priorities")
    elif forced_obj > baseline_obj:
        cost = forced_obj - baseline_obj
        print(f"⚠️  FORCED CONSUMPTION IS WORSE by ${cost:,.2f}")
        print()
        print("  This suggests the model found the true optimum")
        print("  (consuming costs more than not consuming)")
        print("  Indicates formulation issue or missing constraint")
    else:
        print("  Same objective - inconclusive")

elif 'infeasible' in str(result_forced.solver.termination_condition).lower():
    print()
    print("❌ INFEASIBLE!")
    print()
    print("ROOT CAUSE CONFIRMED: Formulation Bug")
    print("  Forcing consumption=154.78 violates a constraint")
    print("  This PROVES there's a constraint preventing ambient consumption")
    print()
    print("Most likely culprit:")
    print("  - Sliding window constraint on Day 17 (Nov 2)")
    print("  - Limits sum(consumption[Oct17...Nov2]) <= 518")
    print("  - But total demand in that window = 2,028 units")
    print("  - Setting Oct17 consumption=155 uses up the budget")
    print("  - Leaves insufficient for later days in window")
    print()
    print("FIX NEEDED:")
    print("  Initial inventory should NOT be subject to sliding window")
    print("  constraint at leaf nodes (no production to refresh supply)")
    print("  Sliding window designed for production batches, not pre-existing stock")
else:
    print(f"\n⚠️  Solver terminated with: {result_forced.solver.termination_condition}")
    print("  Test inconclusive")
