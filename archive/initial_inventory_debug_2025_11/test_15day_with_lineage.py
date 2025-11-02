#!/usr/bin/env python3
"""Test 15 days: all demand nodes + Lineage."""

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

# 15-day test
start = date(2025, 10, 17)
end = start + timedelta(days=14)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("TEST: 15 days with FULL inventory (all locations + Lineage)")
print("="*80)
print(f"Total: {sum(initial_inv.values()):.0f} units")

by_state = {}
for (loc, prod, state), qty in initial_inv.items():
    by_state[state] = by_state.get(state, 0) + qty
for state, qty in by_state.items():
    print(f"  {state}: {qty:.0f} units")

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.01, tee=False)

print(f"\nResult: {result.termination_condition}")

if result.is_optimal():
    print("✓✓✓ OPTIMAL - PROBLEM FULLY SOLVED! ✓✓✓")
else:
    print("✗ INFEASIBLE - Still has issues")

print("="*80)
