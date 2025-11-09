"""Write model to LP file for inspection.

This will write the EXACT model constraints to a file.
We can then compare LP files between UI and script to find the difference.
"""
from datetime import date, timedelta
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.models.truck_schedule import TruckScheduleCollection

# Parse
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

# Get products
from tests.conftest import create_test_products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products_list = [create_test_products(product_ids)[pid] for pid in product_ids]

# Truck schedules
if isinstance(truck_schedules, list):
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules)

# Create workflow config (EXACT UI)
config = WorkflowConfig(
    workflow_type=WorkflowType.INITIAL,
    planning_horizon_weeks=4,
    solve_time_limit=120,
    mip_gap_tolerance=0.01,
    solver_name='appsi_highs',
    allow_shortages=True,
    track_batches=True,
    use_pallet_costs=True
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
    initial_inventory=inventory_snapshot
)

# Build model (calls _build_model internally)
print("Building model via workflow...")
input_data = workflow.prepare_input_data()
workflow._build_model(input_data)

# Write model to file
print("Writing model to LP file...")
workflow.model.model.write('model_from_workflow.lp', format='lp')
print("Model written to: model_from_workflow.lp")

print(f"\nYou can inspect this file to see all constraints.")
print(f"If UI is different from script, the LP files will show why.")
