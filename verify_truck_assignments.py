"""Verify truck assignments show in Distribution Tab."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import _create_truck_plan_from_optimization
from datetime import timedelta

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(weeks=1)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True
)

print("Solving model...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, tee=False)

# Get shipments
shipments = model.extract_shipments()
assigned = [s for s in shipments if s.assigned_truck_id]

# Create truck plan
truck_plan = _create_truck_plan_from_optimization(model, shipments)

print(f"\n{'=' * 80}")
print("TRUCK ASSIGNMENT FIX VERIFICATION")
print(f"{'=' * 80}")

print(f"\nShipments:")
print(f"  Total: {len(shipments)}")
print(f"  Assigned: {len(assigned)}")
print(f"  Unassigned: {len(shipments) - len(assigned)}")

print(f"\nTruck Plan:")
print(f"  Total loads: {len(truck_plan.loads)}")
print(f"  Unassigned shipments: {len(truck_plan.unassigned_shipments)}")

if len(truck_plan.loads) == 0:
    print(f"\n❌ FAIL: No truck loads created")
else:
    print(f"\n✅ PASS: {len(truck_plan.loads)} truck loads created")

# Show sample loads
if truck_plan.loads:
    print(f"\nSample truck loads (first 3):")
    for load in truck_plan.loads[:3]:
        print(f"\n  {load.truck_name} → {load.destination_id}")
        print(f"    Departure: {load.departure_date} ({load.departure_type})")
        print(f"    Shipments: {len(load.shipments)}")
        print(f"    Total units: {load.total_units:.0f}")
        print(f"    Total pallets: {load.total_pallets}")
        print(f"    Utilization: {load.capacity_utilization * 100:.1f}%")

print(f"\n{'=' * 80}")
print("VERIFICATION COMPLETE")
print(f"{'=' * 80}")
