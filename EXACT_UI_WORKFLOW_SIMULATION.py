"""Simulate EXACT UI workflow execution step-by-step.

This replicates every step the UI does, including all data conversions.
If this shows OPTIMAL but UI shows INFEASIBLE, it's a Streamlit issue.
If this shows INFEASIBLE, we can debug it.
"""
import sys
from datetime import date, timedelta
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("EXACT UI WORKFLOW SIMULATION")
print("=" * 80)

# Step 1: Parse data (as UI does)
print("\nStep 1: Parsing data files...")
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_params = parser.parse_all()

# Step 2: Parse inventory with snapshot date
print("Step 2: Parsing inventory...")
# UI sets snapshot date to 2025-10-16
snapshot_date_from_ui = date(2025, 10, 16)

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

# Override snapshot date if different
if inventory_snapshot.snapshot_date != snapshot_date_from_ui:
    print(f"  NOTE: Overriding snapshot date from {inventory_snapshot.snapshot_date} to {snapshot_date_from_ui}")
    inventory_snapshot.snapshot_date = snapshot_date_from_ui

print(f"  Snapshot date: {inventory_snapshot.snapshot_date}")
print(f"  Inventory entries: {len(inventory_snapshot.entries)}")

# Step 3: Convert products (as UI does)
print("Step 3: Creating products...")
# UI extracts product IDs from forecast
product_ids_from_forecast = sorted(set(entry.product_id for entry in forecast.entries))
print(f"  Product IDs from forecast: {product_ids_from_forecast}")

# Create Product objects (UI does this somehow - check what it actually does)
# For now, use the test helper
from tests.conftest import create_test_products
products_dict = create_test_products(product_ids_from_forecast)
products_list = list(products_dict.values())

print(f"  Products created: {len(products_list)}")
print(f"  Product IDs: {[p.id for p in products_list]}")

# Step 4: Wrap truck schedules
print("Step 4: Wrapping truck schedules...")
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Step 5: Create workflow config (EXACT UI settings)
print("Step 5: Creating workflow config...")
config = WorkflowConfig(
    workflow_type=WorkflowType.INITIAL,
    planning_horizon_weeks=4,
    solve_time_limit=120,
    mip_gap_tolerance=0.01,
    solver_name='appsi_highs',
    allow_shortages=True,  # UI checkbox
    track_batches=True,    # UI checkbox
    use_pallet_costs=False  # UI checkbox - UNCHECKED per your test
)

print(f"  Config: allow_shortages={config.allow_shortages}, use_pallet_costs={config.use_pallet_costs}")

# Step 6: Create workflow
print("Step 6: Creating InitialWorkflow...")
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

print("  Workflow created")

# Step 7: Execute workflow
print("\nStep 7: Executing workflow...")
print("=" * 80)

try:
    result = workflow.execute()

    print("\n" + "=" * 80)
    print("WORKFLOW EXECUTION RESULT")
    print("=" * 80)

    if hasattr(result, 'success'):
        print(f"Success: {result.success}")
        print(f"Solve time: {result.solve_time_seconds}")
        print(f"Solver message: {result.solver_message}")

        if result.success:
            print(f"\nOPTIMAL - Cannot replicate UI infeasibility")
            print(f"  This suggests Streamlit caching or environment issue")
        else:
            print(f"\nFAILED - Issue replicated!")
            print(f"  Error: {result.error_message}")

except Exception as e:
    print(f"\nEXCEPTION during execution:")
    print(f"  {e}")
    import traceback
    traceback.print_exc()
