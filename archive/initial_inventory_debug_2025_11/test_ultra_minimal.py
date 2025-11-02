#!/usr/bin/env python3
"""Ultra-minimal test: 1 day, 1 product, minimal inventory."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
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

# ULTRA-MINIMAL setup
start = date(2025, 10, 17)
end = start  # ONLY 1 DAY

# Only 1 product
product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

# Minimal initial inventory: 100 units at plant, ambient state
initial_inv = {
    ('6122', 'HELGAS GFREE MIXED GRAIN 500G', 'ambient'): 100.0
}

print("="*80)
print("ULTRA-MINIMAL TEST")
print("="*80)
print(f"Horizon: {start} (1 DAY ONLY)")
print(f"Products: 1 ({product_ids[0]})")
print(f"Initial inventory: 100 units at 6122 (plant), ambient")
print("="*80)

# Create model
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Build Pyomo model
pyomo_model = model.build_model()

# Write LP file
pyomo_model.write('ultra_minimal.lp', format='lp', io_options={'symbolic_solver_labels': True})
print(f"\nLP file written: ultra_minimal.lp")
import os
if os.path.exists('ultra_minimal.lp'):
    print(f"Size: {sum(1 for _ in open('ultra_minimal.lp'))} lines")

# Try to solve
result = model.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)

print(f"\nResult: {result.termination_condition}")

if result.is_optimal():
    print("✓ OPTIMAL")
else:
    print("✗ INFEASIBLE")
    print("\nNow test WITHOUT initial inventory...")

    # Test without initial inventory
    model2 = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params, start_date=start, end_date=end,
        truck_schedules=unified_trucks, initial_inventory=None,
        allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
    )

    result2 = model2.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)
    print(f"Without init_inv: {result2.termination_condition}")

print("="*80)
