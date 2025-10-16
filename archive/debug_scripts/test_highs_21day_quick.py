"""Quick test: Does HiGHS scale better than CBC on 21-day windows?"""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
import time
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization import IntegratedProductionDistributionModel

# Load data
print("Loading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# 21-day window
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 22)

forecast_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
test_forecast = Forecast(name='test_21d', entries=forecast_entries, creation_date=full_forecast.creation_date)

print(f"21-day window: {start_date} to {end_date}")
print(f"Total demand: {sum(e.quantity for e in test_forecast.entries):,.0f} units")

print('\n' + '=' * 80)
print('21-DAY WINDOW SCALING TEST')
print('=' * 80)

# Test CBC with timeout
print('\n[1/2] CBC on 21-day window (60s timeout)...')
model_cbc = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)

start = time.time()
result_cbc = model_cbc.solve(solver_name='cbc', time_limit_seconds=60, tee=False)
cbc_time = time.time() - start

if result_cbc.is_feasible():
    print(f'  ✅ CBC SOLVED in {cbc_time:.2f}s')
    print(f'  Cost: ${result_cbc.objective_value:,.2f}')
else:
    print(f'  ❌ CBC failed/timeout after {cbc_time:.2f}s')
    print(f'  Status: {result_cbc.termination_condition}')

# Test HiGHS with timeout
print('\n[2/2] HiGHS on 21-day window (60s timeout)...')
model_highs = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)

start = time.time()
result_highs = model_highs.solve(solver_name='highs', time_limit_seconds=60, tee=False)
highs_time = time.time() - start

if result_highs.is_feasible():
    print(f'  ✅ HiGHS SOLVED in {highs_time:.2f}s')
    print(f'  Cost: ${result_highs.objective_value:,.2f}')
else:
    print(f'  ❌ HiGHS failed/timeout after {highs_time:.2f}s')
    print(f'  Status: {result_highs.termination_condition}')

# Results
print('\n' + '=' * 80)
print('RESULTS')
print('=' * 80)

cbc_solved = result_cbc.is_feasible()
highs_solved = result_highs.is_feasible()

print(f'\nCBC:   {cbc_time:>6.2f}s  {"✓ solved" if cbc_solved else "✗ timeout"}')
print(f'HiGHS: {highs_time:>6.2f}s  {"✓ solved" if highs_solved else "✗ timeout"}')

if highs_solved and not cbc_solved:
    print('\n🎯 SUCCESS! HiGHS solves 21-day windows where CBC fails!')
    print('   → HiGHS has better scaling despite slower baseline performance')
    print('   → This unlocks hierarchical 3-week configurations')
elif cbc_solved and highs_solved:
    if highs_time < cbc_time:
        print(f'\n✓ Both solve, HiGHS is {cbc_time/highs_time:.1f}x faster on 21-day')
    else:
        print(f'\n✓ Both solve, CBC is {highs_time/cbc_time:.1f}x faster on 21-day')
elif cbc_solved and not highs_solved:
    print('\n→ CBC solves but HiGHS times out')
    print('   CBC has better performance for this problem')
else:
    print('\n✗ Both solvers timeout on 21-day windows')
    print('   Neither CBC nor HiGHS can handle 21-day windows efficiently')
    print('   Stick with 14-day/7-day configuration')

print('\n' + '=' * 80)
