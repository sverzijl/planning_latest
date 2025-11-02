#!/usr/bin/env python3
"""Compare truck constraints for 14-day vs 15-day with same minimal inventory."""

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

# Parse minimal inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()

# Convert and keep only 6122 (plant)
inv_2tuple = inventory_data.to_optimization_dict()
initial_inv = {}
loc_dict = {loc.id: loc for loc in locations}
for (location, product), quantity in inv_2tuple.items():
    if location == '6122':  # Plant only
        initial_inv[(location, product, 'ambient')] = quantity

print(f"Plant inventory: {sum(initial_inv.values()):.0f} units")

# Test both horizons
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

start = date(2025, 10, 17)

print("="*80)
print("TRUCK CONSTRAINT COMPARISON")
print("="*80)

for days in [14, 15]:
    end = start + timedelta(days=days-1)

    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params, start_date=start, end_date=end,
        truck_schedules=unified_trucks, initial_inventory=initial_inv,
        allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True  # ENABLED
    )

    # Build but don't solve
    pyomo_model = model.build_model()

    # Check truck variables
    if hasattr(pyomo_model, 'truck_pallet_load'):
        truck_vars = len(list(pyomo_model.truck_pallet_load))
        print(f"\n{days} days: {truck_vars} truck_pallet_load variables")
        # Check dates
        dates_in_truck = set(d for (_, _, _, d) in pyomo_model.truck_pallet_load)
        print(f"  Delivery dates in truck_pallet_load: {min(dates_in_truck)} to {max(dates_in_truck)}")
        print(f"  Planning dates: {start} to {end}")

    # Try to solve
    result = model.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)
    status = "✓ OPTIMAL" if result.is_optimal() else f"✗ {result.termination_condition}"
    print(f"  Solve: {status}")

print("="*80)
