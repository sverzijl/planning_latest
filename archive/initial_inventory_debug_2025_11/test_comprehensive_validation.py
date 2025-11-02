#!/usr/bin/env python3
"""Comprehensive validation of disposal variable solution."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
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

# Parse FULL inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()
inventory_data.snapshot_date = date(2025, 10, 16)

# Convert all
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

# Test setup
start = date(2025, 10, 17)
end = start + timedelta(days=27)  # 28 days

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("COMPREHENSIVE VALIDATION")
print("="*80)

# Calculate total demand
total_demand = sum(e.quantity for e in forecast.entries if start <= e.forecast_date <= end)
print(f"\nTotal demand (28 days): {total_demand:,.0f} units")
print(f"Initial inventory: {sum(initial_inv.values()):,.0f} units")
print(f"Initial inventory / total demand: {sum(initial_inv.values()) / total_demand * 100:.1f}%")

# Test 1: WITH initial inventory
print("\n" + "="*80)
print("TEST 1: WITH INITIAL INVENTORY")
print("="*80)

model_with = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    inventory_snapshot_date=inventory_data.snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

result_with = model_with.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01, tee=False)

print(f"\nResult: {result_with.termination_condition}")

if result_with.is_optimal():
    pyomo_model_with = model_with.model

    # Extract key metrics
    total_disposal = 0
    if hasattr(pyomo_model_with, 'disposal'):
        total_disposal = sum(
            value(pyomo_model_with.disposal[k])
            for k in pyomo_model_with.disposal
            if value(pyomo_model_with.disposal[k]) > 0
        )

    total_shortage = 0
    if hasattr(pyomo_model_with, 'shortage'):
        total_shortage = sum(
            value(pyomo_model_with.shortage[k])
            for k in pyomo_model_with.shortage
            if value(pyomo_model_with.shortage[k]) > 0
        )

    total_production = 0
    if hasattr(pyomo_model_with, 'production'):
        total_production = sum(
            value(pyomo_model_with.production[k])
            for k in pyomo_model_with.production
            if value(pyomo_model_with.production[k]) > 0
        )

    fill_rate = (total_demand - total_shortage) / total_demand * 100 if total_demand > 0 else 0

    print(f"\n  Total production: {total_production:,.0f} units")
    print(f"  Total disposal: {total_disposal:,.0f} units")
    print(f"  Total shortage: {total_shortage:,.0f} units")
    print(f"  Fill rate: {fill_rate:.1f}%")
    print(f"  Objective: ${result_with.objective_value:,.2f}")

# Test 2: WITHOUT initial inventory
print("\n" + "="*80)
print("TEST 2: WITHOUT INITIAL INVENTORY (baseline)")
print("="*80)

model_without = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

result_without = model_without.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01, tee=False)

print(f"\nResult: {result_without.termination_condition}")

if result_without.is_optimal():
    pyomo_model_without = model_without.model

    total_shortage_no_inv = 0
    if hasattr(pyomo_model_without, 'shortage'):
        total_shortage_no_inv = sum(
            value(pyomo_model_without.shortage[k])
            for k in pyomo_model_without.shortage
            if value(pyomo_model_without.shortage[k]) > 0
        )

    total_production_no_inv = 0
    if hasattr(pyomo_model_without, 'production'):
        total_production_no_inv = sum(
            value(pyomo_model_without.production[k])
            for k in pyomo_model_without.production
            if value(pyomo_model_without.production[k]) > 0
        )

    fill_rate_no_inv = (total_demand - total_shortage_no_inv) / total_demand * 100 if total_demand > 0 else 0

    print(f"\n  Total production: {total_production_no_inv:,.0f} units")
    print(f"  Total shortage: {total_shortage_no_inv:,.0f} units")
    print(f"  Fill rate: {fill_rate_no_inv:.1f}%")
    print(f"  Objective: ${result_without.objective_value:,.2f}")

# Comparison
print("\n" + "="*80)
print("COMPARISON")
print("="*80)

if result_with.is_optimal() and result_without.is_optimal():
    production_reduction = total_production_no_inv - total_production
    shortage_reduction = total_shortage_no_inv - total_shortage
    cost_reduction = result_without.objective_value - result_with.objective_value

    print(f"\nBenefit of initial inventory:")
    print(f"  Production reduction: {production_reduction:,.0f} units ({production_reduction/total_production_no_inv*100:.1f}%)")
    print(f"  Shortage reduction: {shortage_reduction:,.0f} units")
    print(f"  Cost reduction: ${cost_reduction:,.2f} ({cost_reduction/result_without.objective_value*100:.1f}%)")

    print(f"\nInitial inventory utilization:")
    used_init_inv = sum(initial_inv.values()) - total_disposal
    print(f"  Used: {used_init_inv:,.0f} units ({used_init_inv/sum(initial_inv.values())*100:.1f}%)")
    print(f"  Disposed: {total_disposal:,.0f} units ({total_disposal/sum(initial_inv.values())*100:.1f}%)")

    # Sanity checks
    print(f"\n✓ SANITY CHECKS:")
    print(f"  1. Model solves: {'PASS' if result_with.is_optimal() else 'FAIL'}")
    print(f"  2. Fill rate reasonable: {'PASS' if fill_rate > 80 else 'FAIL'} ({fill_rate:.1f}%)")
    print(f"  3. Init_inv reduces production: {'PASS' if production_reduction > 0 else 'FAIL'}")
    print(f"  4. Init_inv reduces cost: {'PASS' if cost_reduction > 0 else 'FAIL'}")
    print(f"  5. Disposal < initial inventory: {'PASS' if total_disposal < sum(initial_inv.values()) else 'FAIL'}")
    print(f"  6. Used inventory > 0: {'PASS' if used_init_inv > 0 else 'FAIL'}")

print("\n" + "="*80)
