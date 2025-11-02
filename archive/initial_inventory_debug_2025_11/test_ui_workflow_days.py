#!/usr/bin/env python3
"""Test exact UI workflow with specific day counts."""

from datetime import date
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.models.truck_schedule import TruckScheduleCollection
from tests.conftest import create_test_products
import sys

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_params = parser.parse_all()

# Parse inventory
snapshot_date_from_ui = date(2025, 10, 16)
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_snapshot = inv_parser.parse()
inventory_snapshot.snapshot_date = snapshot_date_from_ui

# Create products
product_ids_from_forecast = sorted(set(entry.product_id for entry in forecast.entries))
products_dict = create_test_products(product_ids_from_forecast)
products_list = list(products_dict.values())

# Wrap truck schedules
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

print("="*80)
print("UI WORKFLOW DAY SWEEP (with truck pallet tracking)")
print("="*80)

# Test specific day counts
for days in [13, 14, 15, 16, 17, 18, 21]:
    weeks = (days + 6) // 7

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

    result = workflow.execute()

    status = "✓ OPTIMAL" if result.success else f"✗ {result.solver_message}"
    print(f"{days:2d} days ({weeks} weeks): {status}")

print("="*80)
