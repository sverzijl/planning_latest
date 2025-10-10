#!/usr/bin/env python3
"""
Diagnostic: Check initial inventory creation when snapshot date = Oct 8.

This mimics what happens in the UI when user sets initial inventory date.
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

# Set dates as user would in UI
inventory_snapshot_date = date(2025, 10, 8)
planning_start_date = date(2025, 10, 13)
planning_end_date = planning_start_date + timedelta(days=27)  # 4 weeks

print(f"\nConfiguration:")
print(f"  Initial inventory date: {inventory_snapshot_date}")
print(f"  Planning horizon: {planning_start_date} to {planning_end_date}")

# Load initial inventory from forecast on snapshot date
# This is what the UI does
print(f"\nLoading initial inventory from forecast on {inventory_snapshot_date}...")

initial_inventory = {}
for entry in forecast.entries:
    if entry.forecast_date == inventory_snapshot_date:
        key = (entry.location_id, entry.product_id)
        initial_inventory[key] = entry.quantity

print(f"  Found initial inventory at {len(initial_inventory)} (location, product) combinations")

# Show total by location
from collections import defaultdict
by_location = defaultdict(float)
for (loc, prod), qty in initial_inventory.items():
    by_location[loc] += qty

print(f"\nInitial inventory by location:")
for loc_id in sorted(by_location.keys()):
    loc_name = next((l.name for l in locations if l.id == loc_id), loc_id)
    print(f"  {loc_id} ({loc_name}): {by_location[loc_id]:,.0f} units")

# Create model with initial inventory
print(f"\nBuilding model with initial inventory...")

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
    use_batch_tracking=True,
    enable_production_smoothing=False,
    initial_inventory=initial_inventory
)

print(f"\nSolving...")
result = model.solve(time_limit_seconds=600)

if not result.is_optimal() and not result.is_feasible():
    print(f"❌ Solve failed: {result.termination_condition}")
    exit(1)

print(f"✅ Solve completed: {result.termination_condition}")
print(f"   Total cost: ${result.objective_value:,.2f}")

# Get solution and create production schedule
solution = model.get_solution()
shipments = model.get_shipment_plan() or []

# Create production schedule (this is what result_adapter does)
from src.production.scheduler import ProductionSchedule, ProductionBatch

batches = []

# CREATE BATCHES FROM INITIAL INVENTORY
if model.initial_inventory and inventory_snapshot_date:
    for (location_id, product_id), quantity in model.initial_inventory.items():
        if quantity > 0:
            batch = ProductionBatch(
                id=f"INIT-{location_id}-{product_id}",
                product_id=product_id,
                manufacturing_site_id=location_id,
                production_date=inventory_snapshot_date - timedelta(days=1),  # Oct 7
                quantity=quantity,
                labor_hours_used=0,
                production_cost=0,
            )
            batches.append(batch)

print(f"\nInitial inventory batches created: {len(batches)}")
print(f"Sample (first 5):")
for batch in batches[:5]:
    print(f"  {batch.id}: {batch.quantity:,.0f} units at {batch.manufacturing_site_id}, prod_date={batch.production_date}")

# Add actual production batches
for idx, batch_dict in enumerate(solution.get('production_batches', [])):
    batch = ProductionBatch(
        id=f"OPT-BATCH-{idx+1:04d}",
        product_id=batch_dict['product'],
        manufacturing_site_id=model.manufacturing_site.location_id,
        production_date=batch_dict['date'],
        quantity=batch_dict['quantity'],
        labor_hours_used=0,
        production_cost=batch_dict['quantity'] * model.cost_structure.production_cost_per_unit,
    )
    batches.append(batch)

print(f"\nTotal batches (initial + production): {len(batches)}")

# Create production schedule
production_schedule = ProductionSchedule(
    manufacturing_site_id=model.manufacturing_site.location_id,
    schedule_start_date=inventory_snapshot_date,  # Use snapshot date as start
    schedule_end_date=model.end_date,
    production_batches=batches,
    daily_totals={},
    daily_labor_hours={},
    infeasibilities=[],
    total_units=0,
    total_labor_hours=0,
    requirements=None,
)

# Create daily snapshot generator (LEGACY MODE - no model solution)
locations_dict = {loc.id: loc for loc in locations}

generator = DailySnapshotGenerator(
    production_schedule=production_schedule,
    shipments=shipments,
    locations_dict=locations_dict,
    forecast=forecast,
    model_solution=None,  # Force LEGACY MODE like UI does
    verbose=False
)

# Generate snapshots for Oct 8-12 (before planning starts)
print(f"\n{'='*70}")
print(f"DAILY SNAPSHOTS (Oct 8-12 - before planning starts)")
print(f"{'='*70}")

for day_offset in range(5):  # Oct 8, 9, 10, 11, 12
    check_date = inventory_snapshot_date + timedelta(days=day_offset)
    snapshot = generator._generate_single_snapshot(check_date)

    # Get inventory at 6122
    loc_6122 = snapshot.location_inventory.get('6122')
    inv_6122 = loc_6122.total_quantity if loc_6122 else 0

    print(f"\n{check_date} ({check_date.strftime('%A')}):")
    print(f"  6122 - Manufacturing: {inv_6122:,.0f} units")

    if loc_6122 and loc_6122.batches:
        print(f"  Batches at 6122:")
        for batch in sorted(loc_6122.batches, key=lambda b: b.production_date):
            print(f"    {batch.batch_id}: {batch.quantity:,.0f} units (prod_date={batch.production_date}, age={batch.age_days}d)")

    # Show production activity
    if snapshot.production_activity:
        print(f"  Production on {check_date}:")
        for batch in snapshot.production_activity:
            print(f"    {batch.batch_id}: {batch.quantity:,.0f} units")

    # Show departures
    departures = [f for f in snapshot.outflows if f.flow_type == 'departure']
    if departures:
        print(f"  Departures from 6122:")
        for flow in departures:
            if flow.location_id == '6122':
                print(f"    {flow.quantity:,.0f} units to {flow.counterparty}")

print(f"\n{'='*70}")
print(f"DIAGNOSIS")
print(f"{'='*70}")

print(f"\nExpected behavior:")
print(f"  - Oct 8: Show initial inventory (snapshot date)")
print(f"  - Oct 9-12: Show same inventory unless shipments depart")
print(f"  - Oct 13+: Production starts, inventory changes")

print(f"\nUser reported:")
print(f"  - Oct 8: 27,478 units at 6122")
print(f"  - Oct 9: 41,231 units at 6122 (INCREASE of 13,753 units)")
print(f"\nIf values match above, UI is correct.")
print(f"If values differ, there's a bug in snapshot calculation.")
