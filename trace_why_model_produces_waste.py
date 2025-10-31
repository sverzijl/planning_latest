"""Trace why model produces units that become waste.

If waste penalty is $13/unit and 18,282 units remain:
  Waste cost = $237,666

Why doesn't model just produce 18,282 fewer units?

Hypothesis to test:
1. Pallet rounding forces overproduction
2. Production committed early, can't undo later
3. Constraint forces minimum production
4. Other cost (labor/changeover) makes production cheaper than waste
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import timedelta, date

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
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params,
    start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)
solution = model.get_solution()

print('TRACING WHY MODEL PRODUCES WASTE')
print('='*70)

# Check production in last few days
last_date_val = date(2025, 11, 27)
prod_last_3_days = {}

for day_offset in [1, 2, 3]:
    check_date = last_date_val - timedelta(days=day_offset)
    prod_qty = sum(
        qty for (n, p, d), qty in solution.production_by_date_product.items()
        if d == check_date
    )
    prod_last_3_days[check_date] = prod_qty

print('\\nProduction in last 3 days:')
for dt in sorted(prod_last_3_days.keys(), reverse=True):
    print(f'  {dt}: {prod_last_3_days[dt]:,.0f} units')

total_last_3 = sum(prod_last_3_days.values())
print(f'  Total last 3 days: {total_last_3:,.0f}')

# Check if this production is in pallets
print(f'\\nPallet rounding check:')
UNITS_PER_MIX = 415  # Typical batch size

for dt, qty in sorted(prod_last_3_days.items(), reverse=True):
    if qty > 0:
        mixes = qty / UNITS_PER_MIX
        print(f'  {dt}: {qty:.0f} units = {mixes:.2f} mixes')

        # Check if it's close to integer mixes
        if abs(mixes - round(mixes)) < 0.01:
            print(f'    ✅ Exact integer mixes ({round(mixes)})')
        else:
            print(f'    ⚠️ Fractional mixes - pallet rounding?')

# Check end inventory
end_inv_total = sum(qty for (node, prod, state, dt), qty in solution.inventory_state.items() if dt == last_date_val)

print(f'\\nEnd inventory breakdown:')
for (node, prod, state, dt), qty in solution.inventory_state.items():
    if dt == last_date_val and qty > 0.01:
        print(f'  {node}/{prod[:25]:25s}: {qty:8.0f} units')

print('')
print('='*70)
print('HYPOTHESIS: Check if this is pallet/mix rounding')
print(f'  Mix size: {UNITS_PER_MIX} units')
print(f'  End inventory: {end_inv_total:.0f}')
print(f'  In mixes: {end_inv_total / UNITS_PER_MIX:.2f}')

if end_inv_total % UNITS_PER_MIX < 50:
    print(f'  ⚠️ End inventory is close to mix multiple')
    print(f'     Possible: Mix constraints forcing overproduction')
