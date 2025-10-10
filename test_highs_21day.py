"""Test if HiGHS scales better than CBC on 21-day windows."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date, timedelta
import time
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization import IntegratedProductionDistributionModel
from pyomo.environ import SolverFactory

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

print(f"\n21-day window: {start_date} to {end_date}")
print(f"Total demand: {sum(e.quantity for e in test_forecast.entries):,.0f} units")

model = IntegratedProductionDistributionModel(
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

print("\nBuilding model...")
pyomo_model = model.build_model()
print(f"Model built: {pyomo_model.nvariables()} variables, {pyomo_model.nconstraints()} constraints")

print('\n' + '=' * 80)
print('21-DAY WINDOW SCALING TEST: CBC vs HiGHS')
print('=' * 80)

# Test CBC (expected to timeout)
print('\nTest 1: CBC on 21-day window')
print('  Timeout: 5 minutes')
solver_cbc = SolverFactory('cbc')
start = time.time()
results_cbc = solver_cbc.solve(pyomo_model, tee=False, symbolic_solver_labels=False, load_solutions=False)
cbc_time = time.time() - start

if cbc_time < 300:
    print(f'  ✅ SOLVED in {cbc_time:.2f}s')
    print(f'  Termination: {results_cbc.solver.termination_condition}')
else:
    print(f'  ⏱ Timeout after {cbc_time:.2f}s')

# Test HiGHS (the key test!)
print('\nTest 2: HiGHS on 21-day window')
print('  Timeout: 5 minutes')
solver_highs = SolverFactory('highs')
start = time.time()
results_highs = solver_highs.solve(pyomo_model, tee=False, symbolic_solver_labels=False, load_solutions=False)
highs_time = time.time() - start

if highs_time < 300:
    print(f'  ✅ SOLVED in {highs_time:.2f}s')
    print(f'  Termination: {results_highs.solver.termination_condition}')
else:
    print(f'  ⏱ Timeout after {highs_time:.2f}s')

# Results
print('\n' + '=' * 80)
print('RESULTS')
print('=' * 80)

print(f'\nCBC (21-day):   {cbc_time:.2f}s {"✓ solved" if cbc_time < 300 else "✗ timeout"}')
print(f'HiGHS (21-day): {highs_time:.2f}s {"✓ solved" if highs_time < 300 else "✗ timeout"}')

if highs_time < 300 and cbc_time >= 300:
    print('\n🎯 SUCCESS! HiGHS solves 21-day windows where CBC times out!')
    print('   → HiGHS has better scaling properties')
    print('   → This unlocks hierarchical 3-week configurations')
elif cbc_time < 300 and highs_time < 300:
    speedup = cbc_time / highs_time
    if speedup > 1:
        print(f'\n✓ Both solve, HiGHS is {speedup:.1f}x faster')
    else:
        print(f'\n✓ Both solve, CBC is {1/speedup:.1f}x faster')
else:
    print('\n✗ Both solvers timeout on 21-day windows')
    print('   Neither CBC nor HiGHS can handle 21-day windows efficiently')

print('=' * 80)
