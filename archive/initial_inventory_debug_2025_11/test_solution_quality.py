#!/usr/bin/env python3
"""Test solution quality with initial inventory."""

from datetime import date, timedelta
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
inventory_snapshot.snapshot_date = date(2025, 10, 16)

# Create products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products_dict = create_test_products(product_ids)
products_list = list(products_dict.values())

# Wrap truck schedules
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

print("="*80)
print("SOLUTION QUALITY TEST")
print("="*80)

# Calculate total demand
start = date(2025, 10, 17)
end = start + timedelta(days=27)
total_demand = sum(e.quantity for e in forecast.entries if start <= e.forecast_date <= end)
print(f"\nTotal demand (4 weeks): {total_demand:,.0f} units")
print(f"Initial inventory: {sum(e.quantity for e in inventory_snapshot.entries):,.0f} units")

# Test WITH initial inventory
print("\n" + "-"*80)
print("WITH INITIAL INVENTORY")
print("-"*80)

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

workflow_with = InitialWorkflow(
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

result_with = workflow_with.execute()

print(f"Success: {result_with.success}")
if result_with.success:
    print(f"  Objective: ${result_with.objective_value:,.2f}")
    print(f"  Solve time: {result_with.solve_time_seconds:.2f}s")
    print(f"  Solver: {result_with.solver_message}")

# Test WITHOUT initial inventory
print("\n" + "-"*80)
print("WITHOUT INITIAL INVENTORY")
print("-"*80)

workflow_without = InitialWorkflow(
    config=config,
    locations=locations,
    routes=routes,
    products=products_list,
    forecast=forecast,
    labor_calendar=labor_calendar,
    truck_schedules=truck_schedules,
    cost_structure=cost_params,
    initial_inventory=None  # NO INITIAL INVENTORY
)

# We need to create empty inventory for InitialWorkflow
from src.models.inventory import InventorySnapshot
empty_inventory = InventorySnapshot(
    snapshot_date=date(2025, 10, 16),
    entries=[],
    source_file="empty"
)

workflow_without = InitialWorkflow(
    config=config,
    locations=locations,
    routes=routes,
    products=products_list,
    forecast=forecast,
    labor_calendar=labor_calendar,
    truck_schedules=truck_schedules,
    cost_structure=cost_params,
    initial_inventory=empty_inventory
)

result_without = workflow_without.execute()

print(f"Success: {result_without.success}")
if result_without.success:
    print(f"  Objective: ${result_without.objective_value:,.2f}")
    print(f"  Solve time: {result_without.solve_time_seconds:.2f}s")
    print(f"  Solver: {result_without.solver_message}")

# Comparison
if result_with.success and result_without.success:
    print("\n" + "="*80)
    print("COMPARISON & VALIDATION")
    print("="*80)

    cost_with = result_with.objective_value
    cost_without = result_without.objective_value

    print(f"\nWith initial inventory: ${cost_with:,.2f}")
    print(f"Without initial inventory: ${cost_without:,.2f}")

    if cost_with < cost_without:
        savings = cost_without - cost_with
        print(f"\nCost reduction from initial inventory:")
        print(f"  ${savings:,.2f} ({savings/cost_without*100:.1f}% savings)")
        print(f"  ✓ PASS: Initial inventory reduces cost")
    elif cost_with == cost_without:
        print(f"\n  Equal cost (initial inventory fully utilized or zero impact)")
    else:
        increase = cost_with - cost_without
        print(f"\n  ✗ FAIL: Cost INCREASES by ${increase:,.2f}")
        print(f"  This suggests disposal penalty may be too high or logic error")

    # Sanity checks
    print(f"\n✓ VALIDATION CHECKS:")
    print(f"  1. Model solves with initial inventory: {'PASS' if result_with.success else 'FAIL'}")
    print(f"  2. Model solves without initial inventory: {'PASS' if result_without.success else 'FAIL'}")
    print(f"  3. Initial inventory reduces or equals cost: {'PASS' if cost_with <= cost_without else 'FAIL'}")

print("\n" + "="*80)

print("\n" + "="*80)
