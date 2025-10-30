"""Verify Daily Costs graph shows data instead of empty."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
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

adapted = adapt_optimization_results(model=model, result={'result': result}, inventory_snapshot_date=inventory.snapshot_date)

cost_breakdown = adapted['cost_breakdown']

print(f"\n{'=' * 80}")
print("DAILY COSTS GRAPH FIX VERIFICATION")
print(f"{'=' * 80}")

print(f"\nCost Breakdown:")
print(f"  Total cost: ${cost_breakdown.total_cost:,.2f}")
print(f"  Labor total: ${cost_breakdown.labor.total:,.2f}")

print(f"\nDaily Breakdown for Labor:")
print(f"  Exists: {cost_breakdown.labor.daily_breakdown is not None}")

if not cost_breakdown.labor.daily_breakdown:
    print(f"\n❌ FAIL: No daily breakdown data")
elif len(cost_breakdown.labor.daily_breakdown) == 0:
    print(f"\n❌ FAIL: Daily breakdown is empty")
else:
    print(f"  Entries: {len(cost_breakdown.labor.daily_breakdown)}")
    print(f"\n✅ PASS: Daily cost data available for chart")

    print(f"\nSample daily costs:")
    for date_val, data in sorted(cost_breakdown.labor.daily_breakdown.items())[:3]:
        print(f"  {date_val}:")
        print(f"    Total cost: ${data['total_cost']:,.2f}")
        print(f"    Total hours: {data['total_hours']:.1f}")

print(f"\n{'=' * 80}")
print("VERIFICATION COMPLETE")
print(f"{'=' * 80}")
