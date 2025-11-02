"""Standalone test that mimics EXACTLY what the UI does.

Run this to see if the model is working correctly outside of Streamlit.
This will show us if the problem is in the model or in the UI.

Usage:
    python test_ui_workflow_standalone.py
"""

import sys
from pathlib import Path
import logging

# Setup logging to see everything
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    stream=sys.stdout
)

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*80)
print("STANDALONE UI WORKFLOW TEST")
print("="*80)

from datetime import date, timedelta
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.parsers.excel_parser import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection

# Step 1: Load data (same as UI)
print("\n1. Loading data files...")
data_dir = Path("data/examples")
config_file = data_dir / "Network_Config.xlsx"
forecast_file = data_dir / "Gluten Free Forecast - Latest.xlsm"
inventory_file = data_dir / "inventory_latest.XLSX"

print(f"   Config: {config_file.exists()}")
print(f"   Forecast: {forecast_file.exists()}")
print(f"   Inventory: {inventory_file.exists()}")

try:
    parser = ExcelParser(config_file)
    locations = parser.parse_locations()
    routes = parser.parse_routes()  # No parameters needed
    labor_calendar = parser.parse_labor_calendar()
    truck_schedules_list = parser.parse_truck_schedules()
    cost_structure = parser.parse_cost_structure()

    parser_forecast = ExcelParser(forecast_file)
    forecast = parser_forecast.parse_forecast()

    parser_inv = ExcelParser(inventory_file)
    initial_inventory = parser_inv.parse_inventory(locations)

    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    # Get products from forecast
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    from tests.conftest import create_test_products
    products = create_test_products(product_ids)

    print(f"   ✅ Data loaded:")
    print(f"      Locations: {len(locations)}")
    print(f"      Routes: {len(routes)}")
    print(f"      Products: {len(products)}")
    print(f"      Forecast entries: {len(forecast.entries)}")

except Exception as e:
    print(f"   ❌ Failed to load data: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Create workflow (EXACTLY like UI)
print("\n2. Creating workflow...")
try:
    workflow_config = WorkflowConfig(
        workflow_type=WorkflowType.INITIAL,
        planning_horizon_weeks=4,  # 4 weeks for faster testing
        solve_time_limit=120,
        mip_gap_tolerance=0.02,
        solver_name='appsi_highs',
        allow_shortages=True,
        track_batches=True,
        use_pallet_costs=True,
    )

    workflow = InitialWorkflow(
        config=workflow_config,
        locations=locations,
        routes=routes,
        products=products,
        forecast=forecast,
        labor_calendar=labor_calendar,
        truck_schedules=truck_schedules,
        cost_structure=cost_structure,
        initial_inventory=initial_inventory,
    )

    print(f"   ✅ Workflow created")

except Exception as e:
    print(f"   ❌ Failed to create workflow: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Execute workflow
print("\n3. Executing workflow (solving model)...")
try:
    result = workflow.execute()

    print(f"\n   Result:")
    print(f"   - Success: {result.success}")
    print(f"   - Objective: ${result.objective_value:,.2f}" if result.objective_value else "   - Objective: None")
    print(f"   - Solve time: {result.solve_time_seconds:.1f}s")
    print(f"   - Solver status: {result.solver_status}")

    if not result.success:
        print(f"\n   ❌ SOLVE FAILED!")
        print(f"   Message: {result.infeasibility_message}")
        if 'extraction_error' in result.metadata:
            print(f"   Extraction error: {result.metadata['extraction_error']}")
        sys.exit(1)

except Exception as e:
    print(f"   ❌ Workflow execution failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Check solution object
print("\n4. Checking solution object...")
try:
    model = result.model
    if not model:
        print(f"   ❌ result.model is None!")
        sys.exit(1)

    solution = model.get_solution()

    if not solution:
        print(f"   ❌ solution is None!")
        sys.exit(1)

    print(f"   ✅ Solution exists: {type(solution).__name__}")
    print(f"   - Model type: {solution.model_type}")
    print(f"   - Production batches: {len(solution.production_batches)}")
    print(f"   - Shipments: {len(solution.shipments)}")
    print(f"   - Labor hours dates: {len(solution.labor_hours_by_date)}")
    print(f"   - Total production: {solution.total_production:.0f}")
    print(f"   - Fill rate: {solution.fill_rate:.1%}")

    if len(solution.production_batches) == 0:
        print(f"\n   ⚠️  WARNING: No production batches!")

    if len(solution.shipments) == 0:
        print(f"\n   ⚠️  WARNING: No shipments!")

    # Show first few batches
    if solution.production_batches:
        print(f"\n   First 5 production batches:")
        for batch in solution.production_batches[:5]:
            print(f"      {batch.date}: {batch.product} @ {batch.node} - {batch.quantity:.0f} units")

    # Show first few shipments
    if solution.shipments:
        print(f"\n   First 5 shipments:")
        for shipment in solution.shipments[:5]:
            print(f"      {shipment.origin} → {shipment.destination}: {shipment.product} - {shipment.quantity:.0f} units (deliver: {shipment.delivery_date})")

except Exception as e:
    print(f"   ❌ Failed to check solution: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Check result adapter
print("\n5. Testing result adapter (what UI uses)...")
try:
    from ui.utils.result_adapter import adapt_optimization_results

    adapted = adapt_optimization_results(
        model=model,
        result=result.metadata,
        inventory_snapshot_date=initial_inventory.snapshot_date if initial_inventory else None
    )

    if not adapted:
        print(f"   ❌ adapt_optimization_results returned None!")
        sys.exit(1)

    print(f"   ✅ Adapted results:")
    print(f"   - production_schedule: {adapted['production_schedule']}")
    print(f"   - Batches: {len(adapted['production_schedule'].production_batches)}")
    print(f"   - Shipments: {len(adapted['shipments'])}")
    print(f"   - Daily totals: {len(adapted['production_schedule'].daily_totals)}")

    # Check daily totals
    prod_schedule = adapted['production_schedule']
    print(f"\n   Daily production totals:")
    for prod_date, qty in sorted(list(prod_schedule.daily_totals.items())[:7]):
        print(f"      {prod_date}: {qty:.0f} units")

    # Count INIT vs OPT batches
    init_batches = [b for b in prod_schedule.production_batches if b.id.startswith('INIT-')]
    opt_batches = [b for b in prod_schedule.production_batches if not b.id.startswith('INIT-')]

    print(f"\n   Batch breakdown:")
    print(f"      INIT batches: {len(init_batches)}")
    print(f"      OPT batches: {len(opt_batches)}")

    if len(opt_batches) == 0:
        print(f"\n   ❌ CRITICAL: No OPT batches! All batches are INIT!")
        print(f"   This means solution.production_batches was empty.")

except Exception as e:
    print(f"   ❌ Result adapter failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("✅ ALL CHECKS PASSED")
print("="*80)
print("\nThe model is working correctly.")
print("If UI still shows empty data, the problem is in the UI display layer,")
print("not in the model or result adapter.")
