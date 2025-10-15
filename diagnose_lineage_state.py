#!/usr/bin/env python3
"""
Diagnostic: Check if model tracks Lineage inventory as frozen.

This verifies:
1. Model solution contains 'frozen' state for Lineage
2. Daily snapshot extracts it correctly
"""

from datetime import date, timedelta
from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.analysis.daily_snapshot import DailySnapshotGenerator

# Load data
print("Loading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()

forecast_parser = ExcelParser("data/examples/Gfree Forecast.xlsm")
forecast = forecast_parser.parse_forecast(sheet_name="G610_RET")

manufacturing_site = next((loc for loc in locations if loc.type == "manufacturing"), None)

# Set up model with batch tracking
planning_start_date = date(2025, 10, 13)
planning_end_date = planning_start_date + timedelta(days=13)  # 2 weeks

print(f"\nBuilding model with batch tracking...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=3,
    allow_shortages=True,
    enforce_shelf_life=True,
    start_date=planning_start_date,
    end_date=planning_end_date,
    use_batch_tracking=True,  # Enable batch tracking
)

print(f"\nSolving...")
result = model.solve(time_limit_seconds=180)

if not result.is_optimal() and not result.is_feasible():
    print(f"❌ Solve failed: {result.termination_condition}")
    exit(1)

print(f"✅ Solve completed: {result.termination_condition}")
print(f"   Total cost: ${result.objective_value:,.2f}")

# Get solution
solution = model.get_solution()
shipments = model.get_shipment_plan() or []

# Check cohort_inventory for Lineage
print(f"\n{'='*70}")
print(f"CHECKING MODEL SOLUTION FOR LINEAGE INVENTORY")
print(f"{'='*70}")

cohort_inventory = solution.get('cohort_inventory', {})
print(f"\nTotal cohort_inventory entries: {len(cohort_inventory)}")

# Filter for Lineage location
lineage_cohorts = {
    k: v for k, v in cohort_inventory.items()
    if k[0] == 'Lineage' and v > 0.01
}

print(f"\nLineage cohort inventory entries: {len(lineage_cohorts)}")

if lineage_cohorts:
    print(f"\nLineage inventory breakdown:")
    for (loc, prod, prod_date, curr_date, state), qty in sorted(lineage_cohorts.items()):
        print(f"  {state.upper()}: {qty:,.0f} units | prod={prod_date}, curr={curr_date}, product={prod}")
else:
    print(f"\n⚠️  No inventory found at Lineage in model solution")

# Now check Daily Snapshot extraction
print(f"\n{'='*70}")
print(f"CHECKING DAILY SNAPSHOT EXTRACTION")
print(f"{'='*70}")

# Create production schedule
from src.production.scheduler import ProductionSchedule, ProductionBatch

batches = []
for idx, batch_dict in enumerate(solution.get('production_batches', [])):
    batch = ProductionBatch(
        id=f"BATCH-{idx+1:04d}",
        product_id=batch_dict['product'],
        manufacturing_site_id=model.manufacturing_site.location_id,
        production_date=batch_dict['date'],
        quantity=batch_dict['quantity'],
        labor_hours_used=0,
        production_cost=batch_dict['quantity'] * model.cost_structure.production_cost_per_unit,
    )
    batches.append(batch)

production_schedule = ProductionSchedule(
    manufacturing_site_id=model.manufacturing_site.location_id,
    schedule_start_date=model.start_date,
    schedule_end_date=model.end_date,
    production_batches=batches,
    daily_totals={},
    daily_labor_hours={},
    infeasibilities=[],
    total_units=0,
    total_labor_hours=0,
    requirements=None,
)

# Create snapshot generator with MODEL MODE
locations_dict = {loc.id: loc for loc in locations}

generator = DailySnapshotGenerator(
    production_schedule=production_schedule,
    shipments=shipments,
    locations_dict=locations_dict,
    forecast=forecast,
    model_solution=solution,  # Enable MODEL MODE
    verbose=False
)

print(f"\nSnapshot generator mode: {'MODEL' if generator.use_model_inventory else 'LEGACY'}")

# Generate snapshot for a date in the middle of the plan
check_date = planning_start_date + timedelta(days=7)
snapshot = generator._generate_single_snapshot(check_date)

# Check Lineage inventory in snapshot
lineage_inv = snapshot.location_inventory.get('Lineage')

if lineage_inv and lineage_inv.total_quantity > 0:
    print(f"\nLineage inventory in snapshot on {check_date}:")
    print(f"  Total: {lineage_inv.total_quantity:,.0f} units")
    print(f"\n  Batches:")
    for batch in lineage_inv.batches:
        print(f"    {batch.batch_id}: {batch.quantity:,.0f} units | state={batch.state} | age={batch.age_days}d")
else:
    print(f"\n⚠️  No inventory at Lineage in snapshot on {check_date}")

print(f"\n{'='*70}")
print(f"DIAGNOSIS COMPLETE")
print(f"{'='*70}")
