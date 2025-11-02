#!/usr/bin/env python3
"""Test: Only plant (6122) ambient inventory, no Lineage."""

from datetime import date
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.models.inventory import InventorySnapshot, InventoryEntry
from src.models.truck_schedule import TruckScheduleCollection
from tests.conftest import create_test_products

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_params = parser.parse_all()

# Create minimal inventory at plant: 320 units (1 pallet) ambient
plant_inventory = InventorySnapshot(
    snapshot_date=date(2025, 10, 16),
    entries=[
        InventoryEntry(
            location_id='6122',
            product_id='HELGAS GFREE MIXED GRAIN 500G',
            quantity=320.0,
            storage_location='4000'  # At plant (not Lineage)
        )
    ],
    source_file="plant_test"
)

print(f"Plant inventory: {len(plant_inventory.entries)} entry, {plant_inventory.get_total_quantity():.0f} units")

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
    initial_inventory=plant_inventory
)

print("\n" + "="*80)
print("TEST: Plant ambient inventory only (no Lineage)")
print("="*80)

result = workflow.execute()

print(f"\nResult: {result.success}")
print(f"Solver status: {result.solver_message}")

if result.success:
    print("✓ OPTIMAL - Plant ambient inventory works!")
    print("→ Issue is specific to Lineage frozen inventory")
else:
    print("✗ INFEASIBLE - Even plant ambient inventory fails!")
    print("→ General initial inventory bug")

print("="*80)
