"""Quick test to diagnose integration test timeout."""
import time
from pathlib import Path
from datetime import timedelta, date

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection

# Parse data
data_dir = Path("data/examples")
inventory_file = data_dir / "inventory.xlsx" if (data_dir / "inventory.xlsx").exists() else None

parser = MultiFileParser(
    forecast_file=data_dir / "Gfree Forecast.xlsm",
    network_file=data_dir / "Network_Config.xlsx",
    inventory_file=inventory_file,
)

print("Parsing data...")
start = time.time()
forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
print(f"✓ Parsed in {time.time() - start:.2f}s")

# Create manufacturing site
manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id,
    name=manuf_loc.name,
    storage_mode=manuf_loc.storage_mode,
    production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
    daily_startup_hours=getattr(manuf_loc, 'daily_startup_hours', 0.5),
    daily_shutdown_hours=getattr(manuf_loc, 'daily_shutdown_hours', 0.25),
    default_changeover_hours=getattr(manuf_loc, 'default_changeover_hours', 0.5),
    production_cost_per_unit=cost_structure.production_cost_per_unit,
)

print(f"Manufacturing overhead: startup={manufacturing_site.daily_startup_hours}h, " +
      f"shutdown={manufacturing_site.daily_shutdown_hours}h, " +
      f"changeover={manufacturing_site.default_changeover_hours}h")

# Parse inventory
initial_inventory = None
inventory_snapshot_date = None
if inventory_file:
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot
    inventory_snapshot_date = inventory_snapshot.snapshot_date
    print(f"✓ Inventory snapshot: {inventory_snapshot_date}")
else:
    # Use earliest forecast date
    inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)
    print(f"⚠ No inventory file, using earliest forecast date: {inventory_snapshot_date}")

# Convert to unified format
converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

print(f"✓ Nodes: {len(nodes)}, Routes: {len(unified_routes)}, Truck schedules: {len(unified_truck_schedules)}")

# Check pallet storage costs
print(f"\nStorage costs:")
print(f"  Fixed per pallet: ${cost_structure.storage_cost_fixed_per_pallet:.2f}")
print(f"  Per pallet/day (frozen): ${cost_structure.storage_cost_per_pallet_day_frozen:.2f}")
print(f"  Per pallet/day (ambient): ${cost_structure.storage_cost_per_pallet_day_ambient:.2f}")

# Create model with 1-week horizon first
print("\n" + "="*80)
print("Testing 1-week horizon")
print("="*80)

planning_start = inventory_snapshot_date
planning_end = planning_start + timedelta(weeks=1)

print(f"Planning horizon: {planning_start} to {planning_end}")

model_start = time.time()
model = UnifiedNodeModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=planning_start,
    end_date=planning_end,
    truck_schedules=unified_truck_schedules,
    initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
    inventory_snapshot_date=inventory_snapshot_date,
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)
print(f"✓ Model built in {time.time() - model_start:.2f}s")

solve_start = time.time()
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False,  # Don't show solver output for now
)
solve_time = time.time() - solve_start

print(f"\n✓ Solved in {solve_time:.2f}s")
print(f"  Status: {result.termination_condition}")
print(f"  Objective: ${result.objective_value:,.2f}" if result.objective_value else "  Objective: N/A")

solution = model.get_solution()
print(f"\nSolution summary:")
print(f"  Labor cost: ${solution.get('total_labor_cost', 0):,.2f}")
print(f"  Production cost: ${solution.get('total_production_cost', 0):,.2f}")
print(f"  Transport cost: ${solution.get('total_transport_cost', 0):,.2f}")
print(f"  Holding cost: ${solution.get('total_holding_cost', 0):,.2f}")
print(f"  Shortage cost: ${solution.get('total_shortage_cost', 0):,.2f}")

# Check if 1-week succeeded
if solve_time < 60 and result.is_optimal():
    print("\n✓ 1-week test PASSED - now testing 4-week horizon...")
    
    # Try 4-week horizon
    planning_end_4week = planning_start + timedelta(weeks=4)
    print(f"\nPlanning horizon (4-week): {planning_start} to {planning_end_4week}")
    
    model_start = time.time()
    model_4week = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start,
        end_date=planning_end_4week,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )
    print(f"✓ Model built in {time.time() - model_start:.2f}s")
    
    solve_start = time.time()
    result_4week = model_4week.solve(
        solver_name='cbc',
        time_limit_seconds=180,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )
    solve_time_4week = time.time() - solve_start
    
    print(f"\n✓ 4-week solved in {solve_time_4week:.2f}s")
    print(f"  Status: {result_4week.termination_condition}")
    print(f"  Objective: ${result_4week.objective_value:,.2f}" if result_4week.objective_value else "  Objective: N/A")
    
    if solve_time_4week >= 180:
        print(f"\n⚠ WARNING: 4-week solve hit time limit ({solve_time_4week:.2f}s)")
    elif solve_time_4week >= 60:
        print(f"\n⚠ WARNING: 4-week solve time ({solve_time_4week:.2f}s) exceeds 60s threshold")
    else:
        print(f"\n✓ 4-week test PASSED (solve time: {solve_time_4week:.2f}s)")

