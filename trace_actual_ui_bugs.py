"""Trace EXACT bugs user is seeing - no more guessing.

Run this and compare output to what user sees in UI.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
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
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# EXACT UI configuration
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)
solution = model.get_solution()

# Adapt for UI (EXACT code path)
adapted = adapt_optimization_results(
    model=model,
    result={'result': result},
    inventory_snapshot_date=inventory.snapshot_date
)

print('=' * 80)
print('TRACING USER BUGS')
print('=' * 80)

# BUG 1: No labor hours in Production tab
print('\n1. LABOR HOURS:')
prod_schedule = adapted['production_schedule']
print(f'   daily_labor_hours: {prod_schedule.daily_labor_hours}')
print(f'   total_labor_hours: {prod_schedule.total_labor_hours}')
if not prod_schedule.daily_labor_hours or prod_schedule.total_labor_hours == 0:
    print('   ❌ BUG CONFIRMED: No labor hours!')
else:
    print('   ✅ Labor hours present')

# BUG 2: Labeling shows "Unknown" destinations
print('\n2. LABELING - Route states:')
has_route_state = hasattr(model, 'route_arrival_state')
print(f'   model.route_arrival_state exists: {has_route_state}')
if has_route_state:
    print(f'   Routes with states: {len(model.route_arrival_state)}')
    for (origin, dest), state in list(model.route_arrival_state.items())[:3]:
        print(f'     {origin}→{dest}: {state}')

# BUG 3: Truck assignments
print('\n3. TRUCK ASSIGNMENTS:')
shipments = adapted['shipments']
assigned = [s for s in shipments if s.assigned_truck_id]
unassigned = [s for s in shipments if not s.assigned_truck_id]
print(f'   Total shipments: {len(shipments)}')
print(f'   Assigned: {len(assigned)}')
print(f'   Unassigned: {len(unassigned)}')
pct = len(unassigned) / len(shipments) * 100 if shipments else 0
print(f'   Unassigned %: {pct:.1f}%')
if pct > 60:
    print(f'   ❌ BUG CONFIRMED: {pct:.1f}% unassigned')

# BUG 4: Waste 97.9% of cost
print('\n4. COST BREAKDOWN:')
cost_breakdown = adapted['cost_breakdown']
print(f'   Total cost: ${cost_breakdown.total_cost:,.2f}')
print(f'   Labor: ${cost_breakdown.labor.total:,.2f} ({cost_breakdown.labor.total/cost_breakdown.total_cost*100:.1f}%)')
print(f'   Production: ${cost_breakdown.production.total:,.2f} ({cost_breakdown.production.total/cost_breakdown.total_cost*100:.1f}%)')
print(f'   Holding: ${cost_breakdown.holding.total:,.2f} ({cost_breakdown.holding.total/cost_breakdown.total_cost*100:.1f}%)')
print(f'   Waste: ${cost_breakdown.waste.total:,.2f} ({cost_breakdown.waste.total/cost_breakdown.total_cost*100:.1f}%)')
if cost_breakdown.waste.total / cost_breakdown.total_cost > 0.5:
    print(f'   ❌ BUG CONFIRMED: Waste is {cost_breakdown.waste.total/cost_breakdown.total_cost*100:.1f}% of cost!')

# BUG 5-7: Daily Snapshot issues
print('\n5. DAILY SNAPSHOT:')
from src.analysis.daily_snapshot import DailySnapshotGenerator

locations_dict = {loc.id: loc for loc in locations}
generator = DailySnapshotGenerator(
    production_schedule=prod_schedule,
    shipments=shipments,
    locations_dict=locations_dict,
    forecast=forecast,
    model_solution=solution
)

# Check day 2
day2 = start + timedelta(days=1)
snapshot = generator._generate_single_snapshot(day2)

print(f'   Production activity day 2: {len(snapshot.production_activity)}')
for prod_batch in snapshot.production_activity[:3]:
    print(f'     Product: {prod_batch.product_id}')

print(f'   Inflows day 2: {len(snapshot.inflows)}')
for flow in snapshot.inflows[:3]:
    print(f'     {flow.flow_type}: Product={flow.product_id} at {flow.location_id}')
    if flow.product_id == 'UNKNOWN':
        print(f'       ❌ BUG: Unknown product!')

print(f'   Outflows day 2: {len(snapshot.outflows)}')
print(f'   Demand satisfied day 2: {len(snapshot.demand_satisfied)}')

print('\n' + '=' * 80)
print('Run this script to see ACTUAL bugs, not guesses')
