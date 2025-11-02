#!/usr/bin/env python3
"""Check inventory on day 16 - last valid day for initial inventory."""

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

# 16-day test
start = date(2025, 10, 17)
end = start + timedelta(days=15)  # 16 days

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("TEST: 16 days - Check if initial inventory remains on day 16")
print("="*80)
print(f"Snapshot: Oct 16, Day 16 = Nov 1, Init_inv age on day 16 = 16")

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.01, tee=False)

print(f"\nSolve result: {result.termination_condition}")

if result.is_optimal():
    print("✓ OPTIMAL\n")

    # Get Pyomo model
    pyomo_model = model.model

    # Check inventory on day 16
    day16 = end
    print(f"Inventory on day 16 ({day16}):")

    total_inv_day16 = 0
    remaining_count = 0
    for (node_id, prod, state), init_qty in initial_inv.items():
        if init_qty > 0:  # ALL initial inventory
            inv_var = pyomo_model.inventory[node_id, prod, state, day16]
            inv_value = value(inv_var)
            total_inv_day16 += inv_value
            if inv_value > 0.01:  # Any remaining inventory
                remaining_count += 1
                print(f"  {node_id}, {prod[:40]}, {state}: init={init_qty:.0f}, day16={inv_value:.0f}")

    print(f"\nEntries with remaining inventory: {remaining_count}")
    print(f"Total inventory on day 16: {total_inv_day16:.0f} units")
    print("\nWith age < 17: Init_inv NOT in Q on day 17 (age 17 excluded)")
    print("If any init_inv remains on day 16, it will cause infeasibility on day 17")

else:
    print("✗ Model failed to solve")

print("="*80)
