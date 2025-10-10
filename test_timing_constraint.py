"""Quick test of D-1/D0 timing constraint."""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
forecast = forecast_parser.parse_forecast()

print('Building model...')
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print(f'✓ Model built successfully!')
print(f'  Routes: {len(model.enumerated_routes)}')
print(f'  Production dates: {len(model.production_dates)}')
print(f'  Trucks: {len(model.truck_indices)}')

# Try to solve with short time limit
print('\n⚡ Solving (60s timeout, 5% gap)...')
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
    # Extract weekend production stats
    solution = model.get_solution()
    production = solution.get('production_by_date_product', {})
    labor_hours = solution.get('labor_hours_by_date', {})

    weekend_production = 0
    weekday_production = 0

    for (d, p), qty in production.items():
        labor_day = labor_calendar.get_labor_day(d)
        if labor_day and not labor_day.is_fixed_day:
            weekend_production += qty
        else:
            weekday_production += qty

    total = weekend_production + weekday_production

    print(f'\n📦 PRODUCTION BREAKDOWN:')
    print(f'  Weekday: {weekday_production:,.0f} units ({weekday_production/total*100:.1f}%)')
    print(f'  Weekend: {weekend_production:,.0f} units ({weekend_production/total*100:.1f}%)')
    print(f'  Total: {total:,.0f} units')
