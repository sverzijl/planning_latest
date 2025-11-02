"""Debug LP FEFO feasibility issue."""
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import date, timedelta

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
end = start + timedelta(days=2)  # Just 3 days to simplify
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)

print('=' * 80)
print('LP FEFO FEASIBILITY DIAGNOSTIC')
print('=' * 80)

# Get solution data
solution = model.get_solution()
production = solution.get('production_by_date_product', {})
shipments = solution.get('shipments_by_route_product_date', {})
initial_inv = model.initial_inventory

print(f'\nInitial inventory: {len(initial_inv)} entries, {sum(initial_inv.values()):,.0f} units')
print(f'Production: {len(production)} events, {sum(production.values()):,.0f} units')
print(f'Shipments: {len(shipments)} routes, {sum(shipments.values()):,.0f} units')

# Check material balance
total_supply = sum(initial_inv.values()) + sum(production.values())
total_shipments = sum(shipments.values())

print(f'\nMaterial balance:')
print(f'  Supply (initial + production): {total_supply:,.0f}')
print(f'  Shipments: {total_shipments:,.0f}')
print(f'  Balance: {total_supply - total_shipments:,.0f}')

if total_shipments > total_supply:
    print(f'  ❌ INFEASIBLE: Not enough supply for shipments!')

# Check by product and location
print(f'\nBy product at 6122 (manufacturing):')
for prod in product_ids:
    # Initial at 6122
    init_qty = initial_inv.get(('6122', prod, 'ambient'), 0)

    # Production at 6122
    prod_qty = sum(qty for (node, p, date), qty in production.items() if node == '6122' and p == prod)

    # Shipments FROM 6122
    ship_qty = sum(qty for (origin, dest, p, date), qty in shipments.items() if origin == '6122' and p == prod)

    balance = init_qty + prod_qty - ship_qty

    print(f'  {prod[:30]}:')
    print(f'    Initial: {init_qty:.0f}, Production: {prod_qty:.0f}')
    print(f'    Shipments: {ship_qty:.0f}, Balance: {balance:.0f}')

    if balance < -0.1:
        print(f'    ❌ DEFICIT! Cannot ship {ship_qty:.0f} with only {init_qty + prod_qty:.0f} available')
