"""Check what products are in the solution that UI receives."""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils import adapt_optimization_results

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

try:
    initial_inventory = parser.parse_inventory()
    inventory_snapshot_date = initial_inventory.snapshot_date
except:
    initial_inventory = None
    inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)

start = inventory_snapshot_date
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
    inventory_snapshot_date=inventory_snapshot_date,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=True
)

print("=" * 80)
print("UI PRODUCT DISPLAY DIAGNOSTIC")
print("=" * 80)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)
solution = model.get_solution()

print(f"\n1. SOLUTION from model.get_solution():")
print(f"   production_batches: {len(solution.get('production_batches', []))} entries")

products_in_solution = set(b['product'] for b in solution.get('production_batches', []))
print(f"   Products in production_batches: {len(products_in_solution)}")
for prod in sorted(products_in_solution):
    count = sum(1 for b in solution['production_batches'] if b['product'] == prod)
    total_qty = sum(b['quantity'] for b in solution['production_batches'] if b['product'] == prod)
    print(f"     - {prod}: {count} batches, {total_qty:,.0f} units")

# Now adapt for UI
print(f"\n2. ADAPTED RESULTS from adapt_optimization_results():")
adapted = adapt_optimization_results(
    model=model,
    result={'result': result},
    inventory_snapshot_date=inventory_snapshot_date
)

if adapted:
    prod_schedule = adapted['production_schedule']
    print(f"   ProductionSchedule:")
    print(f"     Total batches: {len(prod_schedule.production_batches)}")
    print(f"     Total units: {prod_schedule.total_units:,.0f}")

    products_in_schedule = set(b.product_id for b in prod_schedule.production_batches)
    print(f"     Products in schedule: {len(products_in_schedule)}")
    for prod in sorted(products_in_schedule):
        batches = [b for b in prod_schedule.production_batches if b.product_id == prod]
        total_qty = sum(b.quantity for b in batches)
        print(f"       - {prod}: {len(batches)} batches, {total_qty:,.0f} units")

    # Check if initial inventory is dominating
    init_batches = [b for b in prod_schedule.production_batches if b.id.startswith('INIT-')]
    prod_batches = [b for b in prod_schedule.production_batches if not b.id.startswith('INIT-')]

    print(f"\n     Initial inventory batches: {len(init_batches)}")
    print(f"     Production batches: {len(prod_batches)}")

    if len(prod_batches) > 0:
        products_produced = set(b.product_id for b in prod_batches)
        print(f"     Products PRODUCED (not from inventory): {len(products_produced)}")
        for prod in sorted(products_produced):
            qty = sum(b.quantity for b in prod_batches if b.product_id == prod)
            print(f"       - {prod}: {qty:,.0f} units")
else:
    print("   ERROR: adapted results is None!")

print(f"\n3. DIAGNOSIS:")
if len(products_produced) == 1:
    print(f"   ❌ ONLY 1 PRODUCT PRODUCED: {list(products_produced)[0]}")
    print(f"      This would explain why UI only shows one product")
elif len(products_produced) < len(product_ids):
    print(f"   ⚠️  Only {len(products_produced)}/{len(product_ids)} products produced")
    print(f"      Missing products likely satisfied from initial inventory")
else:
    print(f"   ✅ All {len(products_produced)} products produced")
    print(f"      UI issue must be elsewhere (display filter or bug)")
