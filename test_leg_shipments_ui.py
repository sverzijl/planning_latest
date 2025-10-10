"""
Quick test to verify leg-based shipments work with UI result adapter.
"""
import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from ui.utils.result_adapter import adapt_optimization_results

print("=" * 80)
print("LEG-BASED SHIPMENTS → UI TEST")
print("=" * 80)

print("\nLoading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

# Use just first week for quick test
forecast_dates = [e.forecast_date for e in forecast.entries]
start_date = min(forecast_dates)
end_date = start_date + timedelta(days=6)  # 7 days

print(f"Dataset: {start_date} to {end_date} (7 days)")

print("\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=3,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print(f"\nSolving (20s limit)...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=20,
    mip_gap=0.1,  # 10% gap for speed
    tee=False
)

print(f"\nSolver Result:")
print(f"  Success: {result.success}")
print(f"  Status: {result.termination_condition}")

if result.success:
    print(f"  Objective: ${result.objective_value:,.2f}")

    # Test get_shipment_plan()
    print(f"\nTesting get_shipment_plan()...")
    shipments = model.get_shipment_plan()

    if shipments:
        print(f"  ✅ Got {len(shipments)} shipments")
        print(f"\n  Sample shipments:")
        for shipment in shipments[:5]:
            print(f"    {shipment.id}: {shipment.origin_id} → {shipment.destination_id}, {shipment.quantity:.0f} units, {shipment.product_id}")
    else:
        print(f"  ❌ No shipments returned!")

    # Test UI adapter
    print(f"\nTesting UI result adapter...")
    adapted_result = adapt_optimization_results(model, result.__dict__)

    if adapted_result:
        ui_shipments = adapted_result['shipments']
        ui_truck_plan = adapted_result['truck_plan']

        print(f"  ✅ Adapter returned results")
        print(f"    Shipments: {len(ui_shipments)}")
        print(f"    Truck loads: {len(ui_truck_plan.loads)}")
        print(f"    Unassigned shipments: {len(ui_truck_plan.unassigned_shipments)}")

        # This is what the UI checks
        has_shipments = ui_shipments and len(ui_shipments) > 0
        print(f"\n  UI Check: has_shipments = {has_shipments}")

        if has_shipments:
            print(f"  ✅ UI WILL SHOW DISTRIBUTION PLAN!")
        else:
            print(f"  ❌ UI will show 'No distribution plan available'")
    else:
        print(f"  ❌ Adapter returned None!")

else:
    print(f"  ❌ Solve failed: {result.termination_condition}")

print("=" * 80)
