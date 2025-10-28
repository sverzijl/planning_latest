"""Test what Daily Snapshot actually displays for each date."""
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
end = start + timedelta(days=3)
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

# Create dummy production schedule
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

print('=' * 80)
print('DAILY SNAPSHOT DISPLAY TEST')
print('=' * 80)

for day_offset in range(4):
    check_date = start + timedelta(days=day_offset)

    print(f'\n📸 Snapshot for {check_date} (Day {day_offset+1}):')
    print('-' * 80)

    snapshot = generator._generate_single_snapshot(check_date)

    # Check 6122 specifically
    if '6122' in snapshot.location_inventory:
        loc_inv = snapshot.location_inventory['6122']
        print(f'  6122 (Manufacturing): {loc_inv.total_quantity:.0f} units ({len(loc_inv.batches)} batches)')

        # Show batch production dates
        prod_dates = set(b.production_date for b in loc_inv.batches)
        print(f'    Production dates in batches: {sorted(prod_dates)}')

        # Check for future dates
        future = [d for d in prod_dates if d > check_date]
        if future:
            print(f'    ❌ FUTURE production dates: {future} (should not see these on {check_date}!)')
        else:
            print(f'    ✅ No future dates')

    # Check another location
    if '6104' in snapshot.location_inventory:
        loc_inv = snapshot.location_inventory['6104']
        print(f'  6104 (Hub): {loc_inv.total_quantity:.0f} units ({len(loc_inv.batches)} batches)')

print(f'\n' + '=' * 80)
print('EXPECTED: Inventory at each location should change as date slider moves')
print('ISSUE: If same batches/quantities on all dates, filtering not working')
