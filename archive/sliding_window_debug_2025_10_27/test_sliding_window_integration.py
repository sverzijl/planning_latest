"""Test sliding window model with EXACT integration test setup."""
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("SLIDING WINDOW MODEL - INTEGRATION TEST (4 WEEKS)")
print("=" * 80)

# Parse data (EXACT same as integration test)
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

# Convert to unified format (same as integration test)
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_truck_schedules = converter.convert_all(
    manufacturing_site=mfg_site,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    forecast=forecast
)

# Parse initial inventory if available
try:
    initial_inventory = parser.parse_inventory()
    inventory_snapshot_date = initial_inventory.snapshot_date if initial_inventory else None
except:
    initial_inventory = None
    inventory_snapshot_date = None

print(f"\n✓ Data loaded:")
print(f"  Nodes: {len(nodes)}")
print(f"  Routes: {len(unified_routes)}")
print(f"  Forecast entries: {len(forecast.entries)}")

# Set planning horizon (EXACT same as integration test)
if inventory_snapshot_date is not None:
    print(f"  Inventory snapshot date: {inventory_snapshot_date}")
else:
    inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)
    print(f"  No inventory - using earliest forecast date: {inventory_snapshot_date}")

planning_start_date = inventory_snapshot_date
planning_end_date = planning_start_date + timedelta(weeks=4)

print(f"\n📅 Planning horizon: {planning_start_date} to {planning_end_date} (4 weeks)")

# Create products (EXACT same as integration test)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)
print(f"  Products: {len(products)}")

# Create model (EXACT same setup as UnifiedNodeModel test)
print("\n🔨 Building model...")
model_start = time.time()

model = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    products=products,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=planning_start_date,
    end_date=planning_end_date,
    truck_schedules=unified_truck_schedules,
    initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
    inventory_snapshot_date=inventory_snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,  # Integer pallets for storage
    use_truck_pallet_tracking=True  # Integer pallets for trucks
)

model_build_time = time.time() - model_start
print(f"✅ Model built in {model_build_time:.2f}s")

# Solve with appsi_highs
print("\n🚀 Solving with APPSI HiGHS...")
solve_start = time.time()

result = model.solve(
    solver_name='appsi_highs',
    time_limit_seconds=60,  # Should be much faster than 400s baseline
    mip_gap=0.02,  # 2% gap (relaxed from 1% for speed)
    tee=True  # Show solver output
)

solve_time = time.time() - solve_start

print(f"\n✅ SOLVE COMPLETE:")
print(f"  Status: {result.termination_condition}")
print(f"  Is optimal: {result.is_optimal()}")
print(f"  Is feasible: {result.is_feasible()}")
print(f"  Solve time: {solve_time:.1f}s")
print(f"  Objective: ${result.objective_value:,.2f}" if result.objective_value else "  Objective: N/A")
if result.gap:
    print(f"  MIP gap: {result.gap * 100:.2f}%")

# Extract solution
print("\n📊 Extracting solution...")
solution = model.get_solution()

if solution:
    total_production = solution.get('total_production', 0)
    total_shortage = solution.get('total_shortage_units', 0)
    fill_rate = solution.get('fill_rate', 0)

    print(f"\n  Production: {total_production:,.0f} units")
    print(f"  Shortage: {total_shortage:,.0f} units")
    print(f"  Fill rate: {fill_rate * 100:.1f}%")

    # Calculate expected demand
    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if planning_start_date <= e.forecast_date <= planning_end_date
    )
    print(f"  Demand in horizon: {demand_in_horizon:,.0f} units")

    # Check state flows
    thaw_total = sum(solution.get('thaw_flows', {}).values())
    freeze_total = sum(solution.get('freeze_flows', {}).values())
    print(f"  Thaw flows: {thaw_total:,.0f} units")
    print(f"  Freeze flows: {freeze_total:,.0f} units")

    # VALIDATION
    print("\n🎯 VALIDATION:")
    if total_production > 0:
        print("  ✅ Production > 0")
    else:
        print("  ❌ Production = 0 (ISSUE!)")

    if fill_rate >= 0.85:
        print(f"  ✅ Fill rate {fill_rate*100:.1f}% >= 85%")
    else:
        print(f"  ⚠️  Fill rate {fill_rate*100:.1f}% < 85%")

    if solve_time < 30:
        print(f"  ✅ Solve time {solve_time:.1f}s < 30s (vs 400s cohort baseline)")
    else:
        print(f"  ⚠️  Solve time {solve_time:.1f}s >= 30s (expected <30s)")

    print("\n🎊 SUCCESS! Sliding window model validated with real data!")
else:
    print("\n❌ SOLUTION EXTRACTION FAILED")
    print("  Result success:", result.success)
    print("  Result metadata:", result.metadata)
