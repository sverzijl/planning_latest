"""Diagnostic test for small overlap infeasibility - investigate inventory handoff."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization import RollingHorizonSolver
import time

print("=" * 80)
print("OVERLAP DIAGNOSTIC: 3-DAY OVERLAP (11-DAY COMMITTED)")
print("=" * 80)

# Load data
print("\nLoading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Filter to first 3 weeks for faster diagnosis
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 22)  # 21 days

forecast_entries = [
    e for e in full_forecast.entries
    if start_date <= e.forecast_date <= end_date
]

test_forecast = Forecast(
    name="3_week_diagnostic",
    entries=forecast_entries,
    creation_date=full_forecast.creation_date
)

print(f"\nTest Dataset:")
print(f"  Total demand: {sum(e.quantity for e in test_forecast.entries):,.0f} units")
forecast_dates = sorted(set(e.forecast_date for e in test_forecast.entries))
print(f"  Date range: {forecast_dates[0]} to {forecast_dates[-1]} ({len(forecast_dates)} days)")

print("\n" + "=" * 80)
print("CONFIGURATION: 14-DAY WINDOW, 3-DAY OVERLAP (11-DAY COMMITTED)")
print("=" * 80)
print(f"  Window size: 14 days")
print(f"  Overlap: 3 days")
print(f"  Committed: 11 days per window")

print("\n" + "=" * 80)
print("SOLVING WITH VERBOSE OUTPUT")
print("=" * 80)

solver = RollingHorizonSolver(
    window_size_days=14,
    overlap_days=3,  # Small overlap, large committed
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)

solve_start = time.time()
result = solver.solve(
    forecast=test_forecast,
    solver_name='cbc',
    verbose=True
)
solve_time = time.time() - solve_start

print("\n" + "=" * 80)
print("DIAGNOSTIC RESULTS")
print("=" * 80)

print(f"\nStatus: {'✅ ALL FEASIBLE' if result.all_feasible else '❌ SOME INFEASIBLE'}")
print(f"Windows: {result.num_windows}")
print(f"Feasible: {result.num_windows - len(result.infeasible_windows)}")
print(f"Infeasible: {len(result.infeasible_windows)}")

if not result.all_feasible:
    print(f"\nInfeasible windows: {result.infeasible_windows}")
    print(f"\nInfeasibility pattern analysis:")

    infeasible_nums = [int(w.replace('window_', '')) for w in result.infeasible_windows]
    print(f"  First infeasible: window_{min(infeasible_nums)}")
    print(f"  Last infeasible: window_{max(infeasible_nums)}")

print(f"\nTotal time: {solve_time:.2f}s")
print(f"Avg time per window: {solve_time / result.num_windows:.2f}s")

print("\n" + "=" * 80)
print("HYPOTHESIS")
print("=" * 80)
print("""
With 3-day overlap and 11-day committed region:

Window 1: Days 0-13 (committed 0-10, overlap 11-13)
  - Commits 11 days of production/shipments
  - Extracts inventory from day 10 (committed_end_date)

Window 2: Days 11-24 (committed 11-21, overlap 22-24)
  - Starts with inventory from day 10
  - First committed day is day 11
  - BUT: Inventory is from END of day 10 = START of day 11
  - Should be OK... unless there's insufficient lookahead

If infeasible, it's because the 3-day overlap doesn't provide enough
lookahead visibility to make inventory buildup decisions.
""")

print("=" * 80)
