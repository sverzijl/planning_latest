#!/usr/bin/env python3
"""Systematically disable constraint groups to find which prevents production."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
import pyomo.environ as pyo

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

# Minimal test: 1 day, 1 product
start = date(2025, 10, 17)
end = start  # Just 1 day

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

print("="*80)
print("CONSTRAINT ELIMINATION TEST (1 day, 1 product)")
print("="*80)

# Test 1: Full model
print("\nTest 1: FULL MODEL")
print("-"*80)

model1 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result1 = model1.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)
prod1 = sum(pyo.value(model1.model.production[k]) for k in model1.model.production if pyo.value(model1.model.production[k]) > 0)
print(f"  Result: {result1.termination_condition}, Production: {prod1:,.0f}")

# Test 2: Disable shelf life constraints
print("\nTest 2: Disable SHELF LIFE constraints")
print("-"*80)

m2 = model1.build_model()
if hasattr(m2, 'ambient_shelf_life_con'):
    m2.ambient_shelf_life_con.deactivate()
if hasattr(m2, 'frozen_shelf_life_con'):
    m2.frozen_shelf_life_con.deactivate()
if hasattr(m2, 'thawed_shelf_life_con'):
    m2.thawed_shelf_life_con.deactivate()

model1.model = m2
result2 = model1.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)
prod2 = sum(pyo.value(m2.production[k]) for k in m2.production if pyo.value(m2.production[k]) > 0)
print(f"  Result: {result2.termination_condition}, Production: {prod2:,.0f}")

# Test 3: Disable changeover constraints
print("\nTest 3: Disable CHANGEOVER constraints")
print("-"*80)

m3 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
).build_model()

if hasattr(m3, 'product_binary_linking_con'):
    m3.product_binary_linking_con.deactivate()
if hasattr(m3, 'changeover_detection_con'):
    m3.changeover_detection_con.deactivate()
if hasattr(m3, 'product_start_detection_con'):
    m3.product_start_detection_con.deactivate()

model_temp = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)
model_temp.model = m3
result3 = model_temp.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)
prod3 = sum(pyo.value(m3.production[k]) for k in m3.production if pyo.value(m3.production[k]) > 0)
print(f"  Result: {result3.termination_condition}, Production: {prod3:,.0f}")

# Test 4: Disable mix-based production
print("\nTest 4: Disable MIX-BASED production constraint")
print("-"*80)

m4 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
).build_model()

if hasattr(m4, 'mix_production_con'):
    m4.mix_production_con.deactivate()
    print("  Deactivated mix_production_con")

model_temp2 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)
model_temp2.model = m4
result4 = model_temp2.solve(solver_name='appsi_highs', time_limit_seconds=30, mip_gap=0.01, tee=False)
prod4 = sum(pyo.value(m4.production[k]) for k in m4.production if pyo.value(m4.production[k]) > 0)
print(f"  Result: {result4.termination_condition}, Production: {prod4:,.0f}")

print("\n" + "="*80)
print("DIAGNOSIS:")
if prod1 == 0 and prod2 > 0:
    print("  ✗ Shelf life constraints prevent production")
elif prod1 == 0 and prod3 > 0:
    print("  ✗ Changeover constraints prevent production")
elif prod1 == 0 and prod4 > 0:
    print("  ✗ Mix-based production constraint prevents production")
else:
    print("  ? Need more investigation")
print("="*80)
