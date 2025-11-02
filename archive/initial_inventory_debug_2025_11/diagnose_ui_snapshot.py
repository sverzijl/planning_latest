"""Diagnose what UI Daily Snapshot actually receives and displays."""
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from src.analysis.daily_snapshot import DailySnapshotGenerator
from src.models.production_schedule import ProductionSchedule
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
end = start + timedelta(days=2)
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
solution = model.get_solution()

prod_schedule = ProductionSchedule(
    manufacturing_site_id='6122', schedule_start_date=start, schedule_end_date=end,
    production_batches=[], daily_totals={}, daily_labor_hours={},
    infeasibilities=[], total_units=0, total_labor_hours=0
)

locations_dict = {loc.id: loc for loc in locations}

generator = DailySnapshotGenerator(
    production_schedule=prod_schedule, shipments=[], locations_dict=locations_dict,
    forecast=forecast, model_solution=solution
)

print('UI DAILY SNAPSHOT DIAGNOSTIC')
print('=' * 80)

# Generate snapshots for 3 consecutive days
for day_offset in range(3):
    check_date = start + timedelta(days=day_offset)

    print(f'\n📅 DATE: {check_date} (Day {day_offset+1})')
    print('-' * 80)

    snapshot = generator._generate_single_snapshot(check_date)

    # Check 6122
    if '6122' in snapshot.location_inventory:
        loc_inv_6122 = snapshot.location_inventory['6122']
        total_6122 = loc_inv_6122.total_quantity
        batches_6122 = len(loc_inv_6122.batches)

        print(f'  6122 (Manufacturing):')
        print(f'    Total: {total_6122:.0f} units')
        print(f'    Batches: {batches_6122}')

        # Show first 3 batches
        for i, batch_inv in enumerate(loc_inv_6122.batches[:3]):
            print(f'      Batch {i+1}: {batch_inv.product_id[:25]}')
            print(f'        Prod date: {batch_inv.production_date}, Qty: {batch_inv.quantity:.0f}')
    else:
        print(f'  6122: No inventory')

    # Check 6104
    if '6104' in snapshot.location_inventory:
        loc_inv_6104 = snapshot.location_inventory['6104']
        total_6104 = loc_inv_6104.total_quantity
        batches_6104 = len(loc_inv_6104.batches)

        print(f'  6104 (Hub):')
        print(f'    Total: {total_6104:.0f} units')
        print(f'    Batches: {batches_6104}')
    else:
        print(f'  6104: No inventory')

print(f'\n' + '=' * 80)
print('EXPECTED BEHAVIOR:')
print('  6122 should DECREASE over days (shipments depart)')
print('  6104 should INCREASE then DECREASE (arrivals then departures)')
print('')
print('If you see 6122 with same inventory on all days:')
print('  → Batches not being filtered by location on date')
print('  → Check if location_history is being used correctly')
