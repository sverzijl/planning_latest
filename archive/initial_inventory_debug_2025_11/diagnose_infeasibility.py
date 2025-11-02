"""Diagnose infeasibility in SlidingWindowModel with pallet tracking and initial inventory.

This script will help identify which constraints are causing infeasibility.
"""
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("INFEASIBILITY DIAGNOSTIC - Sliding Window with Pallet Tracking")
print("=" * 80)

# Parse data (same as UI workflow)
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

# Get start date and create initial inventory (like UI does)
start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=27)  # 4 weeks
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print(f"\nScenario:")
print(f"  Horizon: {start} to {end}")
print(f"  Products: {len(products)}")
print(f"  Pallet tracking: TRUE (this is where infeasibility occurs)")

# Test 1: Without initial inventory, without pallet tracking
print(f"\n" + "=" * 80)
print("TEST 1: No initial inventory, no pallet tracking")
print("=" * 80)

model1 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

pyomo_model1 = model1.build_model()
result1 = model1.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
print(f"Result: {result1.termination_condition}, optimal={result1.is_optimal()}")

# Test 2: Without initial inventory, WITH pallet tracking
print(f"\n" + "=" * 80)
print("TEST 2: No initial inventory, WITH pallet tracking")
print("=" * 80)

model2 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=True
)

pyomo_model2 = model2.build_model()
result2 = model2.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
print(f"Result: {result2.termination_condition}, optimal={result2.is_optimal()}")

if not result2.is_optimal():
    print(f"\n⚠️  INFEASIBILITY FOUND: Pallet tracking causes infeasibility!")
    print(f"\nThis narrows down the issue to pallet-related constraints:")
    print(f"  - Storage pallet ceiling")
    print(f"  - Pallet entry detection")
    print(f"  - Truck pallet ceiling")
    print(f"  - Truck capacity constraints")

# Test 3: Try with only storage pallet tracking (no truck pallets)
print(f"\n" + "=" * 80)
print("TEST 3: Storage pallet only (no truck pallet tracking)")
print("=" * 80)

model3 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=False
)

pyomo_model3 = model3.build_model()
result3 = model3.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
print(f"Result: {result3.termination_condition}, optimal={result3.is_optimal()}")

# Test 4: Truck pallet only (no storage pallets)
print(f"\n" + "=" * 80)
print("TEST 4: Truck pallet only (no storage pallet tracking)")
print("=" * 80)

model4 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

pyomo_model4 = model4.build_model()
result4 = model4.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
print(f"Result: {result4.termination_condition}, optimal={result4.is_optimal()}")

# Summary
print(f"\n" + "=" * 80)
print("DIAGNOSTIC SUMMARY")
print("=" * 80)

print(f"\nTest 1 (no pallets): {result1.termination_condition}")
print(f"Test 2 (both pallets): {result2.termination_condition}")
print(f"Test 3 (storage pallet only): {result3.termination_condition}")
print(f"Test 4 (truck pallet only): {result4.termination_condition}")

if result4.is_optimal():
    print(f"\n✅ Truck pallet constraint is OK")
else:
    print(f"\n❌ PROBLEM: Truck pallet ceiling constraint")
    print(f"  This is where the refactoring likely introduced an issue")
    print(f"  The truck_pallet_ceiling_rule needs investigation")

if result3.is_optimal():
    print(f"\n✅ Storage pallet constraint is OK")
else:
    print(f"\n⚠️  Storage pallet constraint may have issues")
