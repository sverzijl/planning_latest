#!/usr/bin/env python3
"""Test: Full real inventory, 4-week horizon."""

from datetime import date
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.models.truck_schedule import TruckScheduleCollection
from tests.conftest import create_test_products

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_params = parser.parse_all()

# Parse FULL real inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_snapshot = inv_parser.parse()
inventory_snapshot.snapshot_date = date(2025, 10, 16)

print(f"Full inventory: {len(inventory_snapshot.entries)} entries, {sum(e.quantity for e in inventory_snapshot.entries):.0f} units")

# Get unique locations
locs_with_inv = set()
for entry in inventory_snapshot.entries:
    if entry.storage_location == '4070':
        locs_with_inv.add('Lineage')
    else:
        locs_with_inv.add(entry.location_id)

print(f"Locations: {sorted(locs_with_inv)}")

# Create products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products_dict = create_test_products(product_ids)
products_list = list(products_dict.values())

# Wrap truck schedules
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Create config
import sys
weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 4

config = WorkflowConfig(
    workflow_type=WorkflowType.INITIAL,
    planning_horizon_weeks=weeks,
    solve_time_limit=120,
    mip_gap_tolerance=0.01,
    solver_name='appsi_highs',
    allow_shortages=True,
    track_batches=False,
    use_pallet_costs=False
)

# Create workflow
workflow = InitialWorkflow(
    config=config,
    locations=locations,
    routes=routes,
    products=products_list,
    forecast=forecast,
    labor_calendar=labor_calendar,
    truck_schedules=truck_schedules,
    cost_structure=cost_params,
    initial_inventory=inventory_snapshot
)

print("\n" + "="*80)
print(f"TEST: FULL real inventory, {weeks}-week horizon")
print("="*80)

result = workflow.execute()

print(f"\nResult: {result.success}")
print(f"Solver status: {result.solver_message}")

if result.success:
    print("✓✓✓ OPTIMAL - PROBLEM SOLVED! ✓✓✓")
    # Extract solution details
    if result.solution:
        print(f"\nSolution summary:")
        print(f"  Objective: ${result.solution.get('total_cost', 0):,.2f}")
        print(f"  Fill rate: {result.solution.get('fill_rate', 0)*100:.1f}%")
else:
    print("✗ STILL INFEASIBLE")

print("="*80)
