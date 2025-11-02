#!/usr/bin/env python3
"""Check disposal values in 28-day solution."""

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

# 28-day test
start = date(2025, 10, 17)
end = start + timedelta(days=27)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("="*80)
print("DISPOSAL REPORT: 28-day horizon with full inventory")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    inventory_snapshot_date=inventory_data.snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01, tee=False)

print(f"\nSolve result: {result.termination_condition}")

if result.is_optimal():
    print("✓ OPTIMAL\n")

    # Extract disposal values
    pyomo_model = model.model

    if hasattr(pyomo_model, 'disposal'):
        print("Disposal by date:")
        disposal_by_date = {}
        total_disposal = 0

        for (node_id, prod, state, t) in pyomo_model.disposal:
            disp_val = value(pyomo_model.disposal[node_id, prod, state, t])
            if disp_val > 0.01:
                if t not in disposal_by_date:
                    disposal_by_date[t] = []
                disposal_by_date[t].append((node_id, prod, state, disp_val))
                total_disposal += disp_val

        if disposal_by_date:
            for date_key in sorted(disposal_by_date.keys()):
                entries = disposal_by_date[date_key]
                date_total = sum(d[3] for d in entries)
                age = (date_key - inventory_data.snapshot_date).days
                print(f"\n  {date_key} (age {age}): {date_total:.0f} units")
                for node_id, prod, state, disp in entries[:10]:
                    init_qty = initial_inv.get((node_id, prod, state), 0)
                    print(f"    - {node_id}, {prod[:35]}, {state}: {disp:.0f} (init={init_qty:.0f})")

            print(f"\nTotal disposal: {total_disposal:.0f} units")
            print(f"Initial inventory: {sum(initial_inv.values()):.0f} units")
            print(f"Disposal rate: {total_disposal / sum(initial_inv.values()) * 100:.1f}%")
        else:
            print("No disposal occurred (all initial inventory consumed/shipped)")
    else:
        print("No disposal variables in model")

else:
    print("✗ Model failed to solve")

print("="*80)
