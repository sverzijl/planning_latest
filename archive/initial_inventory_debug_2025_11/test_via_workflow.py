"""Test through the WORKFLOW layer (not direct model call).

This replicates how the UI actually calls the model, going through
the InitialWorkflow class instead of calling SlidingWindowModel directly.
"""
from datetime import timedelta, date
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("TEST VIA WORKFLOW LAYER (How UI Actually Works)")
print("=" * 80)

# Parse data
print("\n1. Parsing data...")
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Parse inventory
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

print(f"   Snapshot date: {inventory_snapshot.snapshot_date}")
print(f"   Inventory: {len(inventory_snapshot.entries)} entries")

# Get products (UI pattern)
from tests.conftest import create_test_products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products_list = [create_test_products(product_ids)[pid] for pid in product_ids]

# Truck schedules as collection
if isinstance(truck_schedules, list):
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules)

# Create workflow config (EXACT UI settings)
print(f"\n2. Creating workflow config (EXACT UI settings)...")
config = WorkflowConfig(
    workflow_type=WorkflowType.INITIAL,
    planning_horizon_weeks=4,
    solve_time_limit=120,
    mip_gap_tolerance=0.01,
    solver_name='appsi_highs',
    allow_shortages=True,  # UI checkbox
    track_batches=True,    # UI checkbox
    use_pallet_costs=True  # UI checkbox
)

print(f"   allow_shortages: {config.allow_shortages}")
print(f"   track_batches: {config.track_batches}")
print(f"   use_pallet_costs: {config.use_pallet_costs}")

# Create workflow (THIS IS HOW UI DOES IT)
print(f"\n3. Creating workflow (via InitialWorkflow class)...")
workflow = InitialWorkflow(
    config=config,
    locations=locations,
    routes=routes,
    products=products_list,
    forecast=forecast,
    labor_calendar=labor_calendar,
    truck_schedules=truck_schedules,
    cost_structure=cost_params,
    initial_inventory=inventory_snapshot  # Pass InventorySnapshot object
)

print(f"   Workflow created")

# Execute workflow (THIS IS WHAT UI CALLS)
print(f"\n4. Executing workflow...")
print(f"   (This goes through workflow._build_model() and workflow._solve_model())")

try:
    result = workflow.execute()

    print(f"\n" + "=" * 80)
    print("WORKFLOW RESULT")
    print("=" * 80)
    print(f"Success: {result.get('success', False)}")
    print(f"Solve time: {result.get('solve_time_seconds', 'N/A')}")
    print(f"Objective: ${result.get('objective_value', 0):,.2f}")

    if result.get('success'):
        print(f"\n✅ WORKFLOW SUCCEEDS")
        print(f"   Model is feasible via workflow layer")
    else:
        print(f"\n❌ WORKFLOW FAILS")
        print(f"   Error: {result.get('error_message', 'Unknown')}")
        print(f"\n   This replicates the UI issue!")

except Exception as e:
    print(f"\n❌ WORKFLOW EXCEPTION")
    print(f"   Error: {e}")
    print(f"\n   This replicates the UI issue!")
    import traceback
    traceback.print_exc()
