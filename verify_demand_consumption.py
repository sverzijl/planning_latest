"""Verify Daily Snapshot shows demand consumption instead of all shortage."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from src.analysis.daily_snapshot import DailySnapshotGenerator
from ui.utils.result_adapter import adapt_optimization_results
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
solution = model.get_solution()

# Test Daily Snapshot
adapted = adapt_optimization_results(model=model, result={'result': result}, inventory_snapshot_date=inventory.snapshot_date)
prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']

locations_dict = {loc.id: loc for loc in locations}
generator = DailySnapshotGenerator(
    production_schedule=prod_schedule,
    shipments=shipments,
    locations_dict=locations_dict,
    forecast=forecast,
    model_solution=solution
)

print(f"\n{'=' * 80}")
print("DEMAND CONSUMPTION FIX VERIFICATION")
print(f"{'=' * 80}")

# Check multiple days
total_consumed = 0
total_shortage = 0

for day_offset in range(1, 4):
    day = start + timedelta(days=day_offset)
    snapshot = generator._generate_single_snapshot(day)

    consumed_count = sum(1 for r in snapshot.demand_satisfied if r.supplied_quantity > 0.01)
    shortage_count = sum(1 for r in snapshot.demand_satisfied if r.shortage_quantity > 0.01)

    total_consumed += consumed_count
    total_shortage += shortage_count

    print(f"\nDay {day_offset} ({day}):")
    print(f"  Demand records: {len(snapshot.demand_satisfied)}")
    print(f"  With consumption: {consumed_count}")
    print(f"  With shortage: {shortage_count}")

print(f"\nSummary (3 days):")
print(f"  Total records with consumption: {total_consumed}")
print(f"  Total records with shortage: {total_shortage}")

if total_consumed == 0:
    print(f"\n❌ FAIL: No demand consumption tracked")
elif total_shortage > total_consumed * 2:
    print(f"\n⚠️ WARNING: More shortages than consumption (may indicate issue)")
else:
    print(f"\n✅ PASS: Demand consumption tracked correctly")

# Show sample consumption record
day2 = start + timedelta(days=1)
snapshot = generator._generate_single_snapshot(day2)
consumed_records = [r for r in snapshot.demand_satisfied if r.supplied_quantity > 0.01]

if consumed_records:
    print(f"\nSample consumption record:")
    rec = consumed_records[0]
    print(f"  Location: {rec.destination_id}")
    print(f"  Product: {rec.product_id}")
    print(f"  Demand: {rec.demand_quantity:.0f} units")
    print(f"  Supplied: {rec.supplied_quantity:.0f} units")
    print(f"  Shortage: {rec.shortage_quantity:.0f} units")

print(f"\n{'=' * 80}")
print("VERIFICATION COMPLETE")
print(f"{'=' * 80}")
