#!/usr/bin/env python3
"""Test: Minimal Lineage inventory - single product, small quantity."""

from datetime import date
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.models.inventory import InventorySnapshot, InventoryEntry
from src.models.truck_schedule import TruckScheduleCollection
from tests.conftest import create_test_products

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_params = parser.parse_all()

# Create MINIMAL inventory: 320 units (1 pallet) of 1 product at Lineage
minimal_inventory = InventorySnapshot(
    snapshot_date=date(2025, 10, 16),
    entries=[
        InventoryEntry(
            location_id='6122',  # Will be mapped to Lineage via storage_location
            product_id='HELGAS GFREE MIXED GRAIN 500G',
            quantity=320.0,  # Exactly 1 pallet
            storage_location='4070'  # Lineage
        )
    ],
    source_file="minimal_test"
)

print(f"Minimal inventory: {len(minimal_inventory.entries)} entry, {minimal_inventory.get_total_quantity():.0f} units")
print(f"  Product: {minimal_inventory.entries[0].product_id}")
print(f"  Location: {minimal_inventory.entries[0].location_id} (storage_location={minimal_inventory.entries[0].storage_location})")

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
    initial_inventory=minimal_inventory
)

print("\n" + "="*80)
print("TEST: Minimal Lineage inventory (1 pallet, 1 product)")
print("="*80)

result = workflow.execute()

print(f"\nResult: {result.success}")
print(f"Solver status: {result.solver_message}")

if result.success:
    print("✓ OPTIMAL - Even minimal Lineage inventory works!")
    print("→ Bug must be quantity-related or multi-product interaction")
else:
    print("✗ INFEASIBLE - Even 1 pallet at Lineage fails!")
    print("→ Fundamental issue with Lineage frozen inventory")

print("="*80)
