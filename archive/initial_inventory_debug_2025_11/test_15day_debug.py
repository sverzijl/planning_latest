#!/usr/bin/env python3
"""Debug: What happens on day 15?"""

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
print("15-DAY DEBUG TEST")
print("="*80)
print("Day 1 = Oct 17, Day 15 = Oct 31")
print("Thawed shelf life = 14 days")
print("On day 15, thawed init_inv should NOT be in Q (expired)")
print("="*80)

weeks = 3  # 15+ days

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

print(f"\nResult: {result.success}")
print(f"Solver status: {result.solver_message}")

print("="*80)
