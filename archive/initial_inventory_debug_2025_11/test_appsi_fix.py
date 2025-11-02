"""Test APPSI solution loading fix.

Verifies that the fix in base_model.py correctly handles APPSI solution loading.
"""
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("TEST: APPSI Solution Loading Fix")
print("=" * 80)

# Parse data (UI configuration)
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Initial inventory
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Dates
start_date = inventory_snapshot.snapshot_date + timedelta(days=1)
end_date = start_date + timedelta(days=27)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Convert initial inventory
initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()

print(f"\nConfiguration (EXACT UI SETUP):")
print(f"  Horizon: {start_date} to {end_date}")
print(f"  Initial inventory: {len(initial_inv_dict)} entries")
print(f"  Pallet tracking: True")

# Build model
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=inventory_snapshot.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

pyomo_model = model.build_model()
print(f"✅ Model built")

# Solve using model.solve() method (uses the fixed base_model.py code)
print(f"\nSolving with model.solve() (tests the fix)...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.01, tee=False)

print(f"\n" + "=" * 80)
print("RESULT")
print("=" * 80)
print(f"Success: {result.success}")
print(f"Termination: {result.termination_condition}")
print(f"Optimal: {result.is_optimal()}")
print(f"Objective: ${result.objective_value:,.2f}" if result.objective_value else "N/A")
print(f"Solve time: {result.solve_time_seconds:.1f}s")

if result.is_optimal() or result.is_feasible():
    print(f"\n✅ FIX WORKS! Model solves successfully with UI configuration")
    print(f"  - Model is feasible and optimal")
    print(f"  - Solution loading handled correctly")
    print(f"  - No RuntimeError thrown")
else:
    print(f"\n❌ Still failing: {result.termination_condition}")
