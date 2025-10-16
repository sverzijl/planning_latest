#!/usr/bin/env python3
"""
Diagnostic script to investigate the flow conservation bug.

This script runs the integration test and extracts detailed information about:
1. In-transit inventory on day 1
2. Shipment cohorts that arrive on day 1
3. Production dates of inventory on day 1
4. Detailed material balance accounting
"""

import sys
import os

# Add src to path
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_path)

from datetime import datetime, timedelta, date
from pathlib import Path
from parsers.excel_parser import ExcelParser
from optimization.integrated_model import IntegratedProductionDistributionModel
from optimization.solver_config import SolverConfig

# Test file path
test_file = Path("data/examples/Gfree Forecast.xlsm")

print("="*80)
print("FLOW CONSERVATION BUG DIAGNOSTIC")
print("="*80)

# Parse input data
print("\n1. Loading test data...")
parser = ExcelParser()
forecast, locations_map, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_excel(
    str(test_file)
)

# Extract manufacturing site
manufacturing_site = None
for loc in locations_map.values():
    if loc.location_type == 'manufacturing':
        manufacturing_site = loc
        break

# Settings
inventory_snapshot_date = date(2025, 10, 6)
planning_start_date = date(2025, 10, 7)
planning_end_date = date(2025, 11, 4)

initial_inventory = {
    ('6104', 'GFREE_01'): 494,
    ('6125', 'GFREE_01'): 1700,
}

print(f"  Inventory snapshot date: {inventory_snapshot_date}")
print(f"  Planning horizon: {planning_start_date} to {planning_end_date}")
print(f"  Initial inventory: {sum(initial_inventory.values())} units at {len(initial_inventory)} locations")

# Build model
print("\n2. Building optimization model...")
solver_config = SolverConfig(
    solver_name='cbc',
    mip_gap=0.01,
    time_limit_seconds=120,
)

model = IntegratedProductionDistributionModel(
    solver_config=solver_config,
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    routes=routes,
    locations=list(locations_map.values()),
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory=initial_inventory,
    inventory_snapshot_date=inventory_snapshot_date,
    start_date=planning_start_date,
    end_date=planning_end_date,
    use_batch_tracking=True,
)

print(f"  Model built: {len(model.pyomo_model.production)} production variables")
print(f"  Planning dates: {len(list(model.pyomo_model.dates))} days")

# Solve
print("\n3. Solving model...")
result = model.solve()

if result['status'] != 'optimal':
    print(f"  ❌ Solver failed: {result['status']}")
    sys.exit(1)

print(f"  ✓ Optimal solution found")
print(f"  Total cost: ${result['objective_value']:,.2f}")

# Extract solution
solution = result

# Analyze first day
print("\n4. Analyzing first day of planning horizon...")
print("="*80)

first_day = model.start_date
pyomo_model = model.pyomo_model

# Get all shipments (leg-based)
shipments = solution.get('shipments', [])
cohort_shipments = solution.get('batch_shipments', [])

print(f"\nTotal shipments in solution: {len(shipments)}")
print(f"Total cohort shipments: {len(cohort_shipments)}")

# Find shipments arriving on day 1
print(f"\n{'='*80}")
print(f"SHIPMENTS ARRIVING ON DAY 1 ({first_day})")
print(f"{'='*80}")

day1_arrivals = []
for shipment in shipments:
    if shipment['delivery_date'] == first_day and shipment['quantity'] > 0.01:
        # Calculate departure date
        leg = (shipment['origin'], shipment['destination'])
        transit_days = model.leg_transit_days.get(leg, 0)
        departure_date = shipment['delivery_date'] - timedelta(days=transit_days)

        shipment_info = {
            'origin': shipment['origin'],
            'destination': shipment['destination'],
            'product': shipment['product'],
            'quantity': shipment['quantity'],
            'delivery_date': shipment['delivery_date'],
            'departure_date': departure_date,
            'transit_days': transit_days,
            'within_horizon': departure_date >= model.start_date,
        }
        day1_arrivals.append(shipment_info)

print(f"\nFound {len(day1_arrivals)} shipments arriving on day 1")

# Categorize by departure timing
pre_horizon_arrivals = [s for s in day1_arrivals if not s['within_horizon']]
within_horizon_arrivals = [s for s in day1_arrivals if s['within_horizon']]

print(f"  Pre-horizon departures: {len(pre_horizon_arrivals)}")
print(f"  Within-horizon departures: {len(within_horizon_arrivals)}")

if pre_horizon_arrivals:
    print(f"\n⚠ PRE-HORIZON SHIPMENTS (departed before {model.start_date}):")
    total_pre_horizon = 0.0
    for s in pre_horizon_arrivals:
        print(f"  {s['origin']:15s} → {s['destination']:15s}: {s['quantity']:8,.0f} units "
              f"(departed {s['departure_date']}, transit {s['transit_days']}d)")
        total_pre_horizon += s['quantity']
    print(f"  TOTAL PRE-HORIZON ARRIVALS: {total_pre_horizon:,.0f} units")
    print(f"\n  ❌ BUG: These shipments should be ZERO or accounted for in initial_inventory!")
else:
    print(f"\n✓ No pre-horizon shipments found (good!)")

# Analyze cohort shipments arriving on day 1
print(f"\n{'='*80}")
print(f"COHORT SHIPMENTS ARRIVING ON DAY 1")
print(f"{'='*80}")

day1_cohort_arrivals = []
for cohort_ship in cohort_shipments:
    if cohort_ship['delivery_date'] == first_day and cohort_ship['quantity'] > 0.01:
        leg = (cohort_ship['origin'], cohort_ship['destination'])
        transit_days = model.leg_transit_days.get(leg, 0)
        departure_date = cohort_ship['delivery_date'] - timedelta(days=transit_days)

        cohort_info = {
            'origin': cohort_ship['origin'],
            'destination': cohort_ship['destination'],
            'product': cohort_ship['product'],
            'production_date': cohort_ship['production_date'],
            'delivery_date': cohort_ship['delivery_date'],
            'quantity': cohort_ship['quantity'],
            'departure_date': departure_date,
            'transit_days': transit_days,
            'within_horizon': departure_date >= model.start_date,
        }
        day1_cohort_arrivals.append(cohort_info)

print(f"\nFound {len(day1_cohort_arrivals)} cohort shipments arriving on day 1")

if day1_cohort_arrivals:
    print(f"\nCohort breakdown:")
    for s in day1_cohort_arrivals:
        print(f"  {s['origin']:15s} → {s['destination']:15s}: {s['quantity']:8,.0f} units "
              f"(prod {s['production_date']}, departed {s['departure_date']})")

# Analyze inventory on day 1
print(f"\n{'='*80}")
print(f"INVENTORY ON DAY 1 ({first_day})")
print(f"{'='*80}")

cohort_inv = solution.get('cohort_inventory', {})
day1_inventory = {}

for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
    if curr_date == first_day and qty > 0.01:
        key = (loc, prod, prod_date, state)
        day1_inventory[key] = qty

print(f"\nTotal inventory cohorts on day 1: {len(day1_inventory)}")
total_day1_inv = sum(day1_inventory.values())
print(f"Total inventory on day 1: {total_day1_inv:,.0f} units")

# Breakdown by production date
print(f"\nInventory by production date:")
by_prod_date = {}
for (loc, prod, prod_date, state), qty in day1_inventory.items():
    if prod_date not in by_prod_date:
        by_prod_date[prod_date] = 0.0
    by_prod_date[prod_date] += qty

for prod_date in sorted(by_prod_date.keys()):
    qty = by_prod_date[prod_date]
    is_before_horizon = prod_date < first_day
    marker = "⚠ PRE-HORIZON" if is_before_horizon else "✓ WITHIN HORIZON"
    print(f"  {prod_date}: {qty:8,.0f} units  {marker}")

# Material balance check
print(f"\n{'='*80}")
print(f"MATERIAL BALANCE")
print(f"{'='*80}")

# Production
production_batches = solution.get('production_batches', [])
total_production = sum(b['quantity'] for b in production_batches)

# Cohort demand consumption
cohort_demand_consumption = solution.get('cohort_demand_consumption', {})
total_consumption = sum(cohort_demand_consumption.values())

# Final day inventory
final_day = model.end_date
final_inventory = sum(
    qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items()
    if curr_date == final_day
)

# Calculate supply and usage
supply_from_initial = total_day1_inv
supply_from_production = total_production
total_supply = supply_from_initial + supply_from_production

usage_from_demand = total_consumption
usage_from_final_inv = final_inventory
total_usage = usage_from_demand + usage_from_final_inv

print(f"\nSUPPLY SIDE:")
print(f"  Initial inventory (day 1): {supply_from_initial:12,.0f} units")
print(f"  Production (within horizon): {supply_from_production:12,.0f} units")
print(f"  {'='*40}")
print(f"  TOTAL SUPPLY:                {total_supply:12,.0f} units")

print(f"\nUSAGE SIDE:")
print(f"  Demand satisfied (cohorts):  {usage_from_demand:12,.0f} units")
print(f"  Final inventory (day {final_day}): {usage_from_final_inv:12,.0f} units")
print(f"  {'='*40}")
print(f"  TOTAL USAGE:                 {total_usage:12,.0f} units")

balance = total_supply - total_usage
print(f"\nBALANCE: {balance:+,.0f} units")

if abs(balance) > 100:
    print(f"\n❌ MATERIAL BALANCE VIOLATION!")
    print(f"  Model is {'creating' if balance < 0 else 'destroying'} {abs(balance):,.0f} units!")
else:
    print(f"\n✓ Material balance OK")

# Try to find the source of phantom inventory
if balance < -1000:
    print(f"\n{'='*80}")
    print(f"INVESTIGATING PHANTOM INVENTORY SOURCE")
    print(f"{'='*80}")

    # Check if day 1 inventory has pre-horizon production dates
    pre_horizon_inv = sum(
        qty for (loc, prod, prod_date, state), qty in day1_inventory.items()
        if prod_date < first_day
    )

    print(f"\nDay 1 inventory with pre-horizon production dates: {pre_horizon_inv:,.0f} units")

    if pre_horizon_inv > 0:
        print(f"\n⚠ Hypothesis: This inventory should come from initial_inventory input")
        print(f"  But model may be allowing additional sources:")
        print(f"    - Shipments arriving on day 1 that departed before horizon")
        print(f"    - Cohort tracking creating inventory from thin air")

    # Check aggregate shipment total
    total_shipped = sum(s['quantity'] for s in shipments)
    print(f"\nTotal shipments (aggregate): {total_shipped:,.0f} units")

    # Check cohort shipment total
    total_cohort_shipped = sum(s['quantity'] for s in cohort_shipments)
    print(f"Total shipments (cohort): {total_cohort_shipped:,.0f} units")

    if abs(total_shipped - total_cohort_shipped) > 100:
        print(f"⚠ Mismatch: {abs(total_shipped - total_cohort_shipped):,.0f} units")
        print(f"  This suggests aggregate and cohort constraints are not properly linked!")

print(f"\n{'='*80}")
print(f"DIAGNOSTIC COMPLETE")
print(f"{'='*80}")
