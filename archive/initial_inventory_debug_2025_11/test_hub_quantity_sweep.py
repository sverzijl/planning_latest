#!/usr/bin/env python3
"""Test: 5 products at hub 6125 with increasing quantities."""

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

# Get real quantities from inventory file
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_snapshot = inv_parser.parse()

# Get real 6125 quantities
real_quantities = {}
for entry in inventory_snapshot.entries:
    if entry.location_id == '6125' and entry.storage_location == '4000':
        real_quantities[entry.product_id] = entry.quantity

print("Real quantities at 6125:")
for prod, qty in real_quantities.items():
    print(f"  {prod[:40]}: {qty:.0f}")
print(f"  Total: {sum(real_quantities.values()):.0f}")

# 2-day test
start = date(2025, 10, 17)
end = start + timedelta(days=1)

all_product_ids = list(real_quantities.keys())
products = create_test_products(all_product_ids)

print("\n" + "="*80)
print("QUANTITY SWEEP (all 5 products at hub 6125)")
print("="*80)

# Test different scales
for scale in [0.01, 0.05, 0.1, 0.5, 1.0]:
    initial_inv = {}
    for prod_id, real_qty in real_quantities.items():
        initial_inv[('6125', prod_id, 'ambient')] = real_qty * scale

    total = sum(initial_inv.values())

    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params, start_date=start, end_date=end,
        truck_schedules=unified_trucks, initial_inventory=initial_inv,
        allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)

    status = "✓ OPTIMAL" if result.is_optimal() else f"✗ {result.termination_condition}"
    print(f"{scale*100:5.1f}% ({total:6.0f} units): {status}")

print("="*80)
