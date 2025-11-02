#!/usr/bin/env python3
"""Test solution extraction from SlidingWindowModel."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

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

# 1-week test
start = date(2025, 10, 17)
end = start + timedelta(days=6)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("SOLUTION EXTRACTION TEST")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    inventory_snapshot_date=inventory_data.snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

# Solve
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\nSolve result: {result.termination_condition}")
print(f"Success: {result.success}")
print(f"Objective: ${result.objective_value:,.2f}" if result.objective_value else "N/A")

# Check if model.solution was populated
print(f"\nmodel.solution exists: {model.solution is not None}")

if model.solution:
    print(f"model.solution type: {type(model.solution)}")
    print(f"model.solution.production_batches: {len(model.solution.production_batches) if model.solution.production_batches else 0}")

    if hasattr(model.solution, 'production_by_date_product'):
        prod_dict = model.solution.production_by_date_product
        print(f"model.solution.production_by_date_product: {len(prod_dict) if prod_dict else 0} entries")
        if prod_dict:
            # Show first few
            for i, (key, val) in enumerate(list(prod_dict.items())[:5]):
                print(f"  {key}: {val:.0f}")
    else:
        print("model.solution MISSING production_by_date_product attribute!")

# Test get_solution() method
solution_via_method = model.get_solution()
print(f"\nmodel.get_solution() returns: {solution_via_method is not None}")
if solution_via_method:
    print(f"  Type: {type(solution_via_method)}")
    print(f"  Has production_batches: {hasattr(solution_via_method, 'production_batches')}")
    if hasattr(solution_via_method, 'production_by_date_product'):
        print(f"  production_by_date_product: {len(solution_via_method.production_by_date_product) if solution_via_method.production_by_date_product else 0}")

print("="*80)
