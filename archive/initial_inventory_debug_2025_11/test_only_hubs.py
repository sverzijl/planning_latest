#!/usr/bin/env python3
"""Test: Real inventory at hubs only (6104, 6125), no plant, no Lineage."""

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

# Parse real inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_snapshot = inv_parser.parse()
inventory_snapshot.snapshot_date = date(2025, 10, 16)

# Keep ONLY hub inventory (6104, 6125) with storage_location=4000
orig_count = len(inventory_snapshot.entries)
orig_total = sum(e.quantity for e in inventory_snapshot.entries)

inventory_snapshot.entries = [
    e for e in inventory_snapshot.entries
    if e.location_id in ['6104', '6125'] and e.storage_location == '4000'
]

print(f"Original: {orig_count} entries, {orig_total:.0f} units")
print(f"Hubs only (6104, 6125): {len(inventory_snapshot.entries)} entries, {sum(e.quantity for e in inventory_snapshot.entries):.0f} units")

# Create products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products_dict = create_test_products(product_ids)
products_list = list(products_dict.values())

# Wrap truck schedules
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Create config
config = WorkflowConfig(
    workflow_type=WorkflowType.INITIAL,
    planning_horizon_weeks=4,
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
print("TEST: Hub inventory only (6104, 6125)")
print("="*80)

result = workflow.execute()

print(f"\nResult: {result.success}")
print(f"Solver status: {result.solver_message}")

if result.success:
    print("✓ OPTIMAL - Hub inventory works!")
else:
    print("✗ INFEASIBLE - Hub inventory has issues")

print("="*80)
