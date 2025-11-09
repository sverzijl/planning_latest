"""
EXACT UI SCENARIO TEST - For User Verification

This replicates the EXACT configuration the user specified:
- Files: Gluten Free Forecast - Latest.xlsm, inventory_latest.XLSX, Network_Config.xlsx
- Inventory snapshot: 2025/10/16
- Planning horizon: 4 weeks
- MIP Gap: 1%
- Allow shortages: True
- Track batches: True
- Use pallet costs: True

RUN THIS TEST TO VERIFY YOUR CODE IS UP TO DATE
"""
import subprocess
from datetime import timedelta, date
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("UI EXACT SCENARIO TEST - Version Check + Solve")
print("=" * 80)

# Check git commit
result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True)
current_commit = result.stdout.strip()
print(f"\nCurrent git commit: {current_commit}")
print(f"Required commit: aa5f6bd (or later)")

if current_commit != 'aa5f6bd':
    print(f"\n⚠️  WARNING: You may not have the latest fix!")
    print(f"   Please run: git pull origin master")
    print(f"   Expected commit: aa5f6bd")
    print(f"   Your commit: {current_commit}")

# Check for in_transit variable creation with pre-horizon
print(f"\n" + "=" * 80)
print("CODE VERSION CHECK")
print("=" * 80)

with open('src/optimization/sliding_window_model.py', 'r') as f:
    content = f.read()
    if 'pre_horizon_start = self.start_date - timedelta(days=int(max_transit_days))' in content:
        print(f"✅ Code has pre-horizon in-transit fix")
    else:
        print(f"❌ Code MISSING pre-horizon in-transit fix")
        print(f"   You need to pull the latest code!")
        exit(1)

# Parse data
print(f"\n" + "=" * 80)
print("PARSING DATA")
print("=" * 80)

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

print(f"Inventory snapshot date: {inventory_snapshot.snapshot_date}")

# Verify snapshot date
if inventory_snapshot.snapshot_date != date(2025, 10, 16):
    print(f"⚠️  Snapshot date mismatch!")
    print(f"   File has: {inventory_snapshot.snapshot_date}")
    print(f"   Expected: 2025-10-16")

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Calculate dates
start_date = inventory_snapshot.snapshot_date + timedelta(days=1)  # 2025-10-17
end_date = start_date + timedelta(days=27)  # 4 weeks

print(f"Planning: {start_date} to {end_date}")

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Convert inventory
initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()
else:
    for entry in inventory_snapshot.entries:
        key = (entry.location_id, entry.product_id, 'ambient')
        initial_inv_dict[key] = initial_inv_dict.get(key, 0) + entry.quantity

print(f"Initial inventory: {len(initial_inv_dict)} entries, {sum(initial_inv_dict.values()):,.0f} units")

# Build model
print(f"\n" + "=" * 80)
print("BUILDING MODEL - EXACT UI SETTINGS")
print("=" * 80)
print(f"  allow_shortages: True")
print(f"  use_pallet_tracking: True")
print(f"  use_truck_pallet_tracking: True")

model = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    products=products,
    labor_calendar=labor_calendar,
    cost_structure=cost_params,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=inventory_snapshot.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

pyomo_model = model.build_model()
print(f"✅ Model built")

# Solve
print(f"\n" + "=" * 80)
print("SOLVING")
print("=" * 80)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.01, tee=False)

print(f"\n" + "=" * 80)
print("RESULT")
print("=" * 80)
print(f"Success: {result.success}")
print(f"Termination: {result.termination_condition}")
print(f"is_optimal(): {result.is_optimal()}")
print(f"is_feasible(): {result.is_feasible()}")
print(f"Objective: ${result.objective_value:,.2f}" if result.objective_value else "None")
print(f"Solve time: {result.solve_time_seconds:.1f}s" if result.solve_time_seconds else "N/A")

print(f"\n" + "=" * 80)
print("VERDICT")
print("=" * 80)

if result.is_feasible() and result.is_optimal():
    print(f"\n✅ TEST PASSED")
    print(f"   Model solves optimally with exact UI configuration")
    print(f"   Objective: ${result.objective_value:,.2f}")
    print(f"\n   If you're still seeing errors in UI:")
    print(f"   1. Verify you have commit aa5f6bd or later")
    print(f"   2. Restart Streamlit (may have cached old code)")
    print(f"   3. Check Windows file paths are correct")
elif not result.is_feasible():
    print(f"\n❌ TEST FAILED - Model is infeasible")
    print(f"   Termination: {result.termination_condition}")
    print(f"   This means your code is NOT up to date")
    print(f"\n   ACTION REQUIRED:")
    print(f"   Run: git pull origin master")
    print(f"   Expected commit: aa5f6bd")
else:
    print(f"\n⚠️  PARTIAL: {result.termination_condition}")
