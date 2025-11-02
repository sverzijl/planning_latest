#!/usr/bin/env python3
"""Test: Does model solve with zero Lineage inventory?"""

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

# Parse inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_snapshot = inv_parser.parse()

# MODIFY: Remove Lineage inventory
print("Original inventory entries:", len(inventory_snapshot.entries))
lineage_entries = [e for e in inventory_snapshot.entries if e.storage_location == "4070"]
print(f"Lineage entries (storage_location=4070): {len(lineage_entries)}, {sum(e.quantity for e in lineage_entries):.0f} units")

# Remove Lineage inventory
inventory_snapshot.entries = [e for e in inventory_snapshot.entries if e.storage_location != "4070"]
print(f"After removing Lineage: {len(inventory_snapshot.entries)} entries")

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
    track_batches=True,
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
print("TEST: SlidingWindowModel WITHOUT Lineage inventory")
print("="*80)

result = workflow.execute()

print(f"\nResult: {result.success}")
print(f"Solver status: {result.solver_message}")

if result.success:
    print("✓ OPTIMAL - Lineage inventory was the problem!")
else:
    print("✗ STILL INFEASIBLE - Problem is elsewhere")

print("="*80)
