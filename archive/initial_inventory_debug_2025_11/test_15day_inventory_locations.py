#!/usr/bin/env python3
"""Test 15-day horizon with different inventory location combinations."""

from datetime import date
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.models.inventory import InventorySnapshot
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

# Create config for 15-day test (3 weeks)
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

print("="*80)
print("15-DAY INVENTORY LOCATION TEST")
print("="*80)

# Test different inventory configurations
test_cases = [
    ("Plant only (6122)", ['6122']),
    ("Plant + One hub (6125)", ['6122', '6125']),
    ("Plant + Both hubs (6104, 6125)", ['6122', '6104', '6125']),
    ("All locations except Lineage", [e.location_id for e in inventory_snapshot.entries if e.storage_location != '4070']),
    ("Full inventory", None),  # Keep all
]

for name, keep_locations in test_cases:
    # Filter inventory
    test_inventory = InventorySnapshot(
        snapshot_date=inventory_snapshot.snapshot_date,
        entries=[],
        source_file=inventory_snapshot.source_file
    )

    if keep_locations is None:
        # Keep all
        test_inventory.entries = inventory_snapshot.entries
    else:
        # Filter by location and storage_location
        keep_set = set(keep_locations)
        test_inventory.entries = [
            e for e in inventory_snapshot.entries
            if e.location_id in keep_set and e.storage_location != '4070'  # Exclude Lineage
        ]
        # Add Lineage if explicitly in keep_set
        if 'Lineage' in keep_set:
            test_inventory.entries.extend([
                e for e in inventory_snapshot.entries if e.storage_location == '4070'
            ])

    total_qty = sum(e.quantity for e in test_inventory.entries)

    workflow = InitialWorkflow(
        config=config,
        locations=locations,
        routes=routes,
        products=products_list,
        forecast=forecast,
        labor_calendar=labor_calendar,
        truck_schedules=truck_schedules,
        cost_structure=cost_params,
        initial_inventory=test_inventory
    )

    result = workflow.execute()

    status = "✓ OPTIMAL" if result.success else f"✗ {result.solver_message}"
    print(f"{name:40s} ({total_qty:5.0f} units): {status}")

print("="*80)
