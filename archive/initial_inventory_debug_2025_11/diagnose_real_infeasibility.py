"""Diagnose ACTUAL infeasibility in refactored model.

The model reports infeasible with pallet tracking + initial inventory.
Need to find which constraint is violated.
"""
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("INFEASIBILITY ROOT CAUSE - Systematic Investigation")
print("=" * 80)

# Parse
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start_date = inventory_snapshot.snapshot_date + timedelta(days=1)
end_date = start_date + timedelta(days=27)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()

print(f"\nConfiguration:")
print(f"  Start: {start_date}")
print(f"  End: {end_date}")
print(f"  Initial inventory snapshot: {inventory_snapshot.snapshot_date}")
print(f"  Initial inventory entries: {len(initial_inv_dict)}")

# ============================================================================
# TEST 1: Progressively add features to find where infeasibility starts
# ============================================================================

print(f"\n" + "=" * 80)
print("TEST 1: No initial inventory, no pallet tracking")
print("=" * 80)
m1 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)
pm1 = m1.build_model()
r1 = m1.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
print(f"Result: {r1.termination_condition}")

print(f"\n" + "=" * 80)
print("TEST 2: WITH initial inventory, no pallet tracking")
print("=" * 80)
m2 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=inventory_snapshot.snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)
pm2 = m2.build_model()
r2 = m2.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
print(f"Result: {r2.termination_condition}")

print(f"\n" + "=" * 80)
print("TEST 3: WITH initial inventory, WITH pallet tracking")
print("=" * 80)
m3 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=inventory_snapshot.snapshot_date,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=True
)
pm3 = m3.build_model()
r3 = m3.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
print(f"Result: {r3.termination_condition}")

# ============================================================================
# ANALYSIS
# ============================================================================
print(f"\n" + "=" * 80)
print("INFEASIBILITY ISOLATION")
print("=" * 80)

print(f"\nTest 1 (no inv, no pallets): {r1.termination_condition}")
print(f"Test 2 (WITH inv, no pallets): {r2.termination_condition}")
print(f"Test 3 (WITH inv, WITH pallets): {r3.termination_condition}")

if str(r1.termination_condition) == 'optimal' and str(r2.termination_condition) == 'optimal':
    if str(r3.termination_condition) != 'optimal':
        print(f"\n❌ INFEASIBILITY ISOLATED:")
        print(f"  Occurs when: initial_inventory + pallet_tracking BOTH enabled")
        print(f"  Likely cause: Pallet ceiling constraint conflicts with initial inventory")
        print(f"\n  Investigation needed: How are initial inventory pallets calculated?")
elif str(r2.termination_condition) != 'optimal':
    print(f"\n❌ INFEASIBILITY ISOLATED:")
    print(f"  Occurs when: initial_inventory enabled (regardless of pallets)")
    print(f"  Likely cause: Initial inventory conflicts with in_transit variables")
    print(f"  Hypothesis: Arrivals calculation for initial inventory may be broken")
else:
    print(f"\n⚠️  Unexpected pattern")
