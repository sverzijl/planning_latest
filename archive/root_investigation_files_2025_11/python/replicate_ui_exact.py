"""Replicate EXACT UI scenario that user is experiencing.

Configuration:
- Files: Gluten Free Forecast - Latest.xlsm, inventory_latest.XLSX, Network_Config.xlsx
- Inventory snapshot date: 2025/10/16
- Planning horizon: 4 weeks from snapshot + 1 day
- Allow shortages: True
- Track batches: True
- Use pallet costs: True
- MIP gap: 1%
"""
from datetime import timedelta, date
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("EXACT UI SCENARIO REPLICATION")
print("=" * 80)

# Parse data files
print("\n1. Parsing data files...")
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Parse inventory with EXACT snapshot date
print("2. Parsing inventory...")
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

print(f"\n   Inventory snapshot date: {inventory_snapshot.snapshot_date}")
print(f"   Inventory entries: {len(inventory_snapshot.entries)}")

# Check if snapshot date matches user's scenario
expected_snapshot_date = date(2025, 10, 16)
if inventory_snapshot.snapshot_date != expected_snapshot_date:
    print(f"   ⚠️  WARNING: Snapshot date is {inventory_snapshot.snapshot_date}, expected {expected_snapshot_date}")

# Convert to unified
print("\n3. Converting to unified format...")
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Calculate planning horizon (snapshot + 1 day, then 4 weeks)
start_date = inventory_snapshot.snapshot_date + timedelta(days=1)
end_date = start_date + timedelta(days=27)  # 4 weeks = 28 days

print(f"\n4. Planning horizon:")
print(f"   Snapshot date: {inventory_snapshot.snapshot_date}")
print(f"   Planning start: {start_date} (snapshot + 1)")
print(f"   Planning end: {end_date} (4 weeks)")
print(f"   Duration: {(end_date - start_date).days + 1} days")

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Convert initial inventory
initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()
else:
    for entry in inventory_snapshot.entries:
        key = (entry.location_id, entry.product_id, 'ambient')
        initial_inv_dict[key] = initial_inv_dict.get(key, 0) + entry.quantity

print(f"\n5. Initial inventory converted:")
print(f"   Unique (location, product, state): {len(initial_inv_dict)}")
total_initial_inv = sum(initial_inv_dict.values())
print(f"   Total units: {total_initial_inv:,.0f}")

# Build model with EXACT UI settings
print(f"\n6. Building model with EXACT UI settings:")
print(f"   allow_shortages: True")
print(f"   track_batches: True")
print(f"   use_pallet_costs: True")
print(f"   mip_gap: 0.01")

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
    allow_shortages=True,  # EXACT UI setting
    use_pallet_tracking=True,  # EXACT UI setting
    use_truck_pallet_tracking=True  # EXACT UI setting
)

pyomo_model = model.build_model()
print(f"\n✅ Model built")

# Check in_transit variable range
if hasattr(pyomo_model, 'in_transit'):
    departure_dates = set(dep for (_, _, _, dep, _) in pyomo_model.in_transit)
    min_dep = min(departure_dates)
    max_dep = max(departure_dates)

    print(f"\nIn-transit variables:")
    print(f"   Departure date range: {min_dep} to {max_dep}")
    print(f"   Planning horizon: {start_date} to {end_date}")

    pre_horizon_days = (start_date - min_dep).days
    print(f"   Pre-horizon window: {pre_horizon_days} days (for first-day arrivals)")

# Solve with load_solution=False to check termination
print(f"\n7. Solving...")
from pyomo.contrib.appsi.solvers import Highs

solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 120
solver.config.mip_gap = 0.01

results = solver.solve(pyomo_model)

print(f"\n" + "=" * 80)
print("SOLVE RESULT")
print("=" * 80)
print(f"Termination: {results.termination_condition}")

from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC

if results.termination_condition == AppsiTC.optimal:
    print(f"✅ OPTIMAL")
    print(f"   Objective: ${results.best_feasible_objective:,.2f}")
    print(f"\n✅ UI SCENARIO REPLICATION: SUCCESS")
    print(f"   Model is feasible and optimal with exact UI configuration")
elif results.termination_condition == AppsiTC.infeasible:
    print(f"❌ INFEASIBLE")
    print(f"\n❌ UI SCENARIO REPLICATION: CONFIRMED")
    print(f"   Model is infeasible with exact UI configuration")
    print(f"\n   Proceeding to systematic debugging Phase 1...")

    # Use Pyomo infeasibility analysis
    from pyomo.util.infeasible import log_infeasible_constraints
    print(f"\n" + "=" * 80)
    print("INFEASIBLE CONSTRAINTS ANALYSIS")
    print("=" * 80)
    log_infeasible_constraints(pyomo_model)
else:
    print(f"⚠️  {results.termination_condition}")
