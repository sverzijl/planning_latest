#!/usr/bin/env python3
"""Test: Does model solve WITHOUT initial inventory?"""

from datetime import date
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from tests.conftest import create_test_products

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_params = parser.parse_all()

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
    mip_gap_tolerance=0.01,
    track_batches=False,  # Use SlidingWindowModel
    allow_shortages=True,
)

# Create workflow WITHOUT initial inventory
workflow = InitialWorkflow(
    config=config,
    locations=locations,
    routes=routes,
    products=products_list,
    forecast=forecast,
    labor_calendar=labor_calendar,
    truck_schedules=truck_schedules,
    cost_structure=cost_params,
    initial_inventory=None,  # NO INITIAL INVENTORY
)

print("="*80)
print("TEST: SlidingWindowModel WITHOUT initial inventory")
print("="*80)

result = workflow.execute()

print(f"\nResult: {result.success}")
print(f"Solver status: {result.solver_message}")
print(f"Solve time: {result.solve_time:.2f}s")

if result.success:
    print("✓ OPTIMAL - Model works without initial inventory")
else:
    print("✗ FAILED - Model has other issues beyond initial inventory")

print("="*80)
