#!/usr/bin/env python3
"""Debug truck pallet constraints for 14-day vs 15-day."""

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

# Parse inventory - PLANT + ONE HUB (6125)
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()

# Keep only plant and hub 6125
inv_2tuple = inventory_data.to_optimization_dict()
initial_inv = {}
loc_dict = {loc.id: loc for loc in locations}
for (location, product), quantity in inv_2tuple.items():
    if location in ['6122', '6125']:
        loc_node = loc_dict.get(location)
        if loc_node and str(loc_node.storage_mode) == 'frozen':
            state = 'frozen'
        else:
            state = 'ambient'
        initial_inv[(location, product, state)] = quantity

print(f"Initial inventory: Plant + Hub 6125, {sum(initial_inv.values()):.0f} units")

# Test both horizons
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

start = date(2025, 10, 17)

for days in [14, 15]:
    end = start + timedelta(days=days-1)

    print("\n" + "="*80)
    print(f"TEST: {days}-DAY HORIZON")
    print("="*80)

    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params, start_date=start, end_date=end,
        truck_schedules=unified_trucks, initial_inventory=initial_inv,
        allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
    )

    # Build model
    pyomo_model = model.build_model()

    # Analyze truck constraints for hub 6125
    if hasattr(pyomo_model, 'truck_pallet_ceiling_con'):
        print(f"\nTruck pallet ceiling constraints:")
        count_6125 = 0
        for idx in list(pyomo_model.truck_pallet_ceiling_con)[:20]:
            if len(idx) >= 2 and idx[1] == '6125':  # dest = 6125
                count_6125 += 1
                if count_6125 <= 5:
                    print(f"  {idx}")

        total_6125 = sum(1 for idx in pyomo_model.truck_pallet_ceiling_con if len(idx) >= 2 and idx[1] == '6125')
        print(f"  Total constraints for dest=6125: {total_6125}")

    # Solve
    result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

    print(f"\nResult: {result.termination_condition}")

print("="*80)
