#!/usr/bin/env python3
"""Test: Full inventory but remove all demand (set to zero)."""

from datetime import date
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry
from tests.conftest import create_test_products

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_params = parser.parse_all()

# MODIFY forecast: set all demand to ZERO
print(f"Original demand entries: {len(forecast.entries)}")
total_demand_orig = sum(e.quantity for e in forecast.entries)
print(f"Original total demand: {total_demand_orig:,.0f} units")

# Modify in place
for entry in forecast.entries:
    entry.quantity = 0.0

print(f"Modified to zero demand")

# Parse FULL real inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_snapshot = inv_parser.parse()
inventory_snapshot.snapshot_date = date(2025, 10, 16)

print(f"Full inventory: {sum(e.quantity for e in inventory_snapshot.entries):.0f} units")

# Create products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products_dict = create_test_products(product_ids)
products_list = list(products_dict.values())

# Wrap truck schedules
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

print("\n" + "="*80)
print("TEST: Full inventory, ZERO demand, 3-week horizon")
print("="*80)

config = WorkflowConfig(
    workflow_type=WorkflowType.INITIAL,
    planning_horizon_weeks=3,
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
    forecast=forecast,  # ZERO DEMAND (modified in place)
    labor_calendar=labor_calendar,
    truck_schedules=truck_schedules,
    cost_structure=cost_params,
    initial_inventory=inventory_snapshot
)

result = workflow.execute()

print(f"\nResult: {result.success}")
print(f"Solver status: {result.solver_message}")

if result.success:
    print("✓ OPTIMAL - Demand was causing the issue!")
else:
    print("✗ INFEASIBLE - Issue is not demand-related")

print("="*80)
