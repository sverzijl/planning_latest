#!/usr/bin/env python3
"""Test: Full inventory with increasing day counts."""

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

# Create products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products_dict = create_test_products(product_ids)
products_list = list(products_dict.values())

# Wrap truck schedules
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

print("="*80)
print("DAY-BY-DAY SWEEP (full real inventory)")
print("="*80)

# Test 7, 14, 15, 16, 17, 18, 21, 28 days
for days in [7, 14, 15, 16, 17, 18, 21, 28]:
    weeks = (days + 6) // 7  # Round up to weeks

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
    print(f"{days:2d} days: {status}")

print("="*80)
