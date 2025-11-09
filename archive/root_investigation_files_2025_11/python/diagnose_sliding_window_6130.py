#!/usr/bin/env python3
"""Diagnose exactly what the sliding window constraint evaluates to for 6130"""

from datetime import date, timedelta
from pyomo.environ import value
from src.parsers.excel_parser import ExcelParser
from src.parsers.product_alias_resolver import ProductAliasResolver
from src.parsers.inventory_parser import InventoryParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast
from src.parsers.multi_file_parser import MultiFileParser
from src.models.location import LocationType

INVENTORY_SNAPSHOT = date(2025, 10, 16)
PLANNING_START = date(2025, 10, 17)
PLANNING_END = PLANNING_START + timedelta(days=27)

resolver = ProductAliasResolver('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gluten Free Forecast - Latest.xlsm', resolver)
forecast_raw = forecast_parser.parse_forecast()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', resolver, INVENTORY_SNAPSHOT)
inv_snapshot = inv_parser.parse()

forecast_filtered = [e for e in forecast_raw.entries if PLANNING_START <= e.forecast_date <= PLANNING_END]

parser = MultiFileParser('data/examples/Gluten Free Forecast - Latest.xlsm', 'data/examples/Network_Config.xlsx', 'data/examples/inventory_latest.XLSX')
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

forecast_obj = Forecast(name="Oct17", entries=forecast_filtered)

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast_obj)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

network_parser = ExcelParser('data/examples/Network_Config.xlsx', resolver)
products_dict = network_parser.parse_products()

inv_dict = {}
for entry in inv_snapshot.entries:
    product_id = resolver.resolve_product_id(entry.product_id) if resolver else entry.product_id
    inv_dict[(entry.location_id, product_id, 'ambient')] = entry.quantity

cost_structure.waste_cost_multiplier = 10.0

model_builder = SlidingWindowModel(nodes, unified_routes, forecast_obj, labor_calendar, cost_structure, products_dict, PLANNING_START, PLANNING_END, unified_truck_schedules, inv_dict, INVENTORY_SNAPSHOT, True, True, True)

print("\nSolving...")
result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05)

model = model_builder.model

# Check sliding window constraint for 6130, Day 1
print("\n" + "="*80)
print("SLIDING WINDOW CONSTRAINT DIAGNOSIS: 6130 Oct 17")
print("="*80)

product = 'HELGAS GFREE MIXED GRAIN 500G'
t = PLANNING_START

if hasattr(model, 'ambient_shelf_life_con'):
    key = ('6130', product, t)
    if key in model.ambient_shelf_life_con:
        constraint = model.ambient_shelf_life_con[key]
        print(f"\nConstraint exists: ambient_shelf_life_con[6130, {product}, {t}]")
        print(f"\nConstraint body (O <= Q):")
        print(f"  {constraint.body}")

        # Try to evaluate
        try:
            lhs_val = value(constraint.body.arg(0), exception=False)  # O (outflows)
            rhs_val = value(constraint.body.arg(1), exception=False)  # Q (inflows)

            print(f"\n  Evaluated:")
            print(f"    O (outflows) = {lhs_val}")
            print(f"    Q (inflows) = {rhs_val}")
            print(f"    Constraint: {lhs_val} <= {rhs_val}")
            print(f"    Satisfied: {lhs_val <= rhs_val if lhs_val is not None and rhs_val is not None else 'Unknown'}")

        except Exception as e:
            print(f"  Could not evaluate: {e}")
    else:
        print(f"  ❌ Constraint key not found!")
        print(f"  Available keys sample: {list(model.ambient_shelf_life_con.keys())[:5]}")

# Check consumption limit constraint
print("\n" + "="*80)
print("CONSUMPTION LIMIT CONSTRAINT: 6130 Oct 17")
print("="*80)

if hasattr(model, 'demand_consumed_ambient_limit_con'):
    key = ('6130', product, t)
    if key in model.demand_consumed_ambient_limit_con:
        constraint = model.demand_consumed_ambient_limit_con[key]
        print(f"\nConstraint exists: demand_consumed_ambient_limit_con[6130, {product}, {t}]")
        print(f"\nConstraint body (consumption <= available):")
        print(f"  {constraint.body}")

        try:
            lhs_val = value(constraint.body.arg(0), exception=False)  # consumption
            rhs_val = value(constraint.body.arg(1), exception=False)  # available

            print(f"\n  Evaluated:")
            print(f"    Consumption = {lhs_val}")
            print(f"    Available = {rhs_val}")
            print(f"    Constraint: {lhs_val} <= {rhs_val}")
            print(f"    Satisfied: {lhs_val <= rhs_val if lhs_val is not None and rhs_val is not None else 'Unknown'}")

        except Exception as e:
            print(f"  Could not evaluate: {e}")

# Check demand balance
print("\n" + "="*80)
print("DEMAND BALANCE: 6130 Oct 17")
print("="*80)

if hasattr(model, 'demand_balance_con'):
    key = ('6130', product, t)
    if key in model.demand_balance_con:
        constraint = model.demand_balance_con[key]
        print(f"\nConstraint exists: demand_balance_con[6130, {product}, {t}]")
        print(f"\nConstraint body (consumption + shortage = demand):")
        print(f"  {constraint.body}")

        try:
            if hasattr(constraint.body, 'arg'):
                lhs_val = value(constraint.body.arg(0), exception=False)  # LHS
                rhs_val = value(constraint.body.arg(1), exception=False)  # RHS (demand)

                print(f"\n  Evaluated:")
                print(f"    LHS (consumption + shortage) = {lhs_val}")
                print(f"    RHS (demand) = {rhs_val}")
                print(f"    Constraint: {lhs_val} == {rhs_val}")

        except Exception as e:
            print(f"  Could not evaluate: {e}")

# Check actual variable values
print("\n" + "="*80)
print("ACTUAL VARIABLE VALUES: 6130 Oct 17")
print("="*80)

cons_key = ('6130', product, t)
short_key = ('6130', product, t)

if cons_key in model.demand_consumed_from_ambient:
    cons_val = value(model.demand_consumed_from_ambient[cons_key])
    print(f"  demand_consumed_from_ambient = {cons_val:.2f}")

if short_key in model.shortage:
    short_val = value(model.shortage[short_key])
    print(f"  shortage = {short_val:.2f}")

# Check init_inv
print(f"\n  Initial ambient inventory at 6130 for {product}:")
init_inv = model_builder.initial_inventory.get(('6130', product, 'ambient'), 0)
print(f"    {init_inv:.0f} units")

print("\n" + "="*80)
