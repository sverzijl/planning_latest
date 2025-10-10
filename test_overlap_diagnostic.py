"""Diagnostic test for large overlap infeasibility - investigate inventory handoff."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization import RollingHorizonSolver
import time

print("=" * 80)
print("OVERLAP DIAGNOSTIC: 11-DAY OVERLAP (3-DAY COMMITTED)")
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

# Filter to first 3 weeks only for faster diagnosis
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 22)  # 21 days = 3 weeks

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
print("CONFIGURATION: 14-DAY WINDOW, 11-DAY OVERLAP (3-DAY COMMITTED)")
print("=" * 80)
print(f"  Window size: 14 days")
print(f"  Overlap: 11 days")
print(f"  Committed: 3 days per window")
print(f"  Expected windows: ~{(len(forecast_dates) // 3) + 1}")

print("\n" + "=" * 80)
print("WINDOW STRUCTURE ANALYSIS")
print("=" * 80)

# Manually calculate expected windows to understand structure
window_size = 14
overlap = 11
committed = window_size - overlap  # 3 days

current = start_date
window_num = 0
print(f"\nExpected window boundaries:")
while current <= end_date:
    window_num += 1
    window_end = min(current + timedelta(days=window_size - 1), end_date)

    is_last = window_end >= end_date
    if not is_last:
        overlap_start = window_end - timedelta(days=overlap - 1)
        committed_end = overlap_start - timedelta(days=1)
    else:
        overlap_start = None
        committed_end = window_end

    actual_committed = (committed_end - current).days + 1

    print(f"  Window {window_num}:")
    print(f"    Full window: {current} to {window_end} ({(window_end - current).days + 1} days)")
    print(f"    Committed:   {current} to {committed_end} ({actual_committed} days)")
    if overlap_start:
        print(f"    Overlap:     {overlap_start} to {window_end} ({(window_end - overlap_start).days + 1} days)")
        print(f"    Inventory handoff: from {committed_end} to Window {window_num + 1}")

    # Next window starts at current + committed days
    current = current + timedelta(days=committed)

    if window_num >= 8:  # Limit output
        print(f"  ...")
        break

print("\n" + "=" * 80)
print("SOLVING WITH VERBOSE OUTPUT")
print("=" * 80)

solver = RollingHorizonSolver(
    window_size_days=14,
    overlap_days=11,
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
    verbose=True  # VERBOSE to see window-by-window details
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

    # Check if there's a pattern
    if len(infeasible_nums) > 1:
        gaps = [infeasible_nums[i+1] - infeasible_nums[i] for i in range(len(infeasible_nums) - 1)]
        print(f"  Gaps between infeasible windows: {gaps}")
        if len(set(gaps)) == 1:
            print(f"  → Regular pattern: every {gaps[0]} windows")

print(f"\nTotal time: {solve_time:.2f}s")
print(f"Avg time per window: {solve_time / result.num_windows:.2f}s")

print("\n" + "=" * 80)
print("HYPOTHESIS")
print("=" * 80)
print("""
With 11-day overlap and 3-day committed region:

Window 1: Days 0-13 (committed 0-2, overlap 3-13)
  - Solves for all 14 days
  - Commits production/shipments for days 0-2
  - Extracts inventory from day 2 (committed_end_date)
  - Days 3-13 plan is DISCARDED

Window 2: Days 3-16 (committed 3-5, overlap 6-16)
  - Starts with inventory from day 2
  - Must satisfy demand for days 3-16
  - BUT: May need production from day 2 (D-1 production for day 3 morning truck)
  - Production from day 2 was not committed in Window 1!
  - → INFEASIBLE due to insufficient starting inventory + production lead time

If this is correct, we would expect Window 2 or 3 to fail first.
""")

print("=" * 80)
