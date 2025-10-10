"""Test 1: Minimal truck assignment test - Direct routes only.

Tests truck assignment with the simplest possible scenario:
- 2 weeks of data
- 2 products only
- 2 direct destinations (6104 NSW, 6110 QLD) - NO hub routing
- Direct trucks: Monday, Wednesday, Friday to 6104; Tuesday, Thursday to 6110

Expected: 100% truck assignment (all shipments from manufacturing should be assigned)
"""

import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

# Parse network data (full - includes all trucks and routes)
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

# Parse full forecast
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
full_forecast = forecast_parser.parse_forecast()

# Create MINIMAL subset: 2 weeks, 2 products, 2 DIRECT destinations only
start_date = date(2025, 6, 2)  # Monday
end_date = date(2025, 6, 15)   # Sunday (2 weeks)
products_to_keep = ['168846', '168847']  # First 2 products
# ONLY keep destinations with DIRECT truck service from 6122 (no hubs)
# 6104 (NSW) - Direct afternoon trucks: Mon, Wed, Fri
# 6110 (QLD) - Direct afternoon trucks: Tue, Thu, Fri
locations_to_keep = ['6104', '6110']

# Filter forecast
test_entries = [
    entry for entry in full_forecast.entries
    if (entry.forecast_date >= start_date and
        entry.forecast_date <= end_date and
        entry.product_id in products_to_keep and
        entry.location_id in locations_to_keep)
]

test_forecast = Forecast(name="Minimal Test - Direct Routes Only", entries=test_entries)

print("="*80)
print("TEST 1: MINIMAL - DIRECT ROUTES ONLY")
print("="*80)
print(f'\nForecast subset: {len(test_entries)} entries')
print(f'  Dates: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)')
print(f'  Products: {products_to_keep}')
print(f'  Locations: {locations_to_keep} (DIRECT trucks only - no hubs)')

print('\nBuilding model...')
model = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=1,  # Only direct routes
    allow_shortages=True,
    enforce_shelf_life=False,  # Disable for simplicity
)

print(f'  Routes: {len(model.enumerated_routes)}')
print(f'  Production dates: {len(model.production_dates)}')
print(f'  Trucks: {len(model.truck_indices)}')
print(f'  Destinations: {len(model.destinations)}')

# Show enumerated routes
print(f'\n  Enumerated routes:')
for route_idx in model.route_indices:
    route = model.route_enumerator.get_route(route_idx)
    if route:
        print(f'    Route {route_idx}: {route.origin_id} → {route.destination_id} '
              f'({route.total_transit_days} days, {len(route.path)} hops)')

print('\n⚡ Solving (60s timeout)...')
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.05,
    tee=False,
)

print(f'\n📈 RESULTS:')
print(f'  Status: {result.termination_condition}')
if result.objective_value:
    print(f'  Objective: ${result.objective_value:,.2f}')
print(f'  Solve time: {result.solve_time_seconds:.1f}s')

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    # Check truck loads
    truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
    print(f'\n🚚 TRUCK LOADS:')
    print(f'  Total truck load entries: {len(truck_loads)}')

    if truck_loads:
        print(f'  Sample truck loads:')
        for i, ((truck_idx, dest, prod, date), qty) in enumerate(list(truck_loads.items())[:5]):
            truck = model.truck_by_index[truck_idx]
            print(f'    Truck {truck.truck_name} ({truck.departure_type}) → {dest}: '
                  f'{qty:.0f} units of {prod} on {date.strftime("%a %Y-%m-%d")}')

    # Get shipments
    shipments = model.get_shipment_plan()
    print(f'\n📦 SHIPMENTS:')
    print(f'  Total shipments: {len(shipments)}')

    # Filter to manufacturing shipments
    manufacturing_id = model.manufacturing_site.location_id
    mfg_shipments = [s for s in shipments if s.origin_id == manufacturing_id]
    assigned = [s for s in mfg_shipments if s.assigned_truck_id is not None]
    unassigned = [s for s in mfg_shipments if s.assigned_truck_id is None]

    print(f'  From manufacturing: {len(mfg_shipments)}')
    print(f'  Assigned to trucks: {len(assigned)}')
    print(f'  Unassigned: {len(unassigned)}')

    if assigned:
        print(f'\n  Sample assigned shipments:')
        for i, s in enumerate(assigned[:5]):
            print(f'    {s.id}: {s.quantity:.0f} units {s.product_id} → {s.destination_id} '
                  f'on {s.delivery_date}, truck {s.assigned_truck_id}, '
                  f'first_leg_dest={s.first_leg_destination}')

    if unassigned:
        print(f'\n  ⚠️  Sample UNASSIGNED shipments (need to diagnose):')
        for i, s in enumerate(unassigned[:5]):
            print(f'    {s.id}: {s.quantity:.0f} units {s.product_id} → {s.destination_id} '
                  f'on {s.delivery_date}, prod_date={s.production_date}, '
                  f'first_leg_dest={s.first_leg_destination}')

    # Calculate assignment percentage
    if mfg_shipments:
        assignment_pct = 100 * len(assigned) / len(mfg_shipments)
        print(f'\n📊 ASSIGNMENT RATE: {assignment_pct:.1f}%')

        if assignment_pct < 100:
            print(f'\n❌ FAILED: Expected 100% assignment for direct routes, got {assignment_pct:.1f}%')
            print(f'   This indicates truck assignment matching logic has issues.')
        else:
            print(f'\n✅ PASSED: All shipments assigned to trucks!')
    else:
        print(f'\n⚠️  No manufacturing shipments found')
else:
    print(f'\n❌ No feasible solution')
