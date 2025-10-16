"""Test rolling horizon with 14-day windows (Quick Win - zero code changes)."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver
import time

print("=" * 70)
print("ROLLING HORIZON - 14-DAY WINDOWS (2 WEEKS)")
print("=" * 70)

print("\nLoading data...")
start_time = time.time()

network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

load_time = time.time() - start_time

print(f"\nFull Dataset:")
print(f"  Total demand: {sum(e.quantity for e in full_forecast.entries):,.0f} units")
forecast_dates = sorted(set(e.forecast_date for e in full_forecast.entries))
total_days = (forecast_dates[-1] - forecast_dates[0]).days + 1
print(f"  Date range: {forecast_dates[0]} to {forecast_dates[-1]} ({total_days} days)")

print("\n" + "=" * 70)
print("CONFIGURATION")
print("=" * 70)

print("\nRolling Horizon:")
print("  Window size: 14 days (2 weeks)")
print("  Overlap: 7 days (1 week)")
print("  Committed: 7 days per window")
print(f"  Expected windows: ~{total_days // 7}")
print("  Expected time: 2-10s per window (longer than 7-day)")

print("\n" + "=" * 70)
print("SOLVING")
print("=" * 70)

solver = RollingHorizonSolver(
    window_size_days=14,  # DOUBLED from 7
    overlap_days=7,       # DOUBLED from 3
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
    forecast=full_forecast,
    solver_name='cbc',
    verbose=True
)
solve_time = time.time() - solve_start

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\nStatus: {'✅ FEASIBLE' if result.all_feasible else '❌ INFEASIBLE'}")
print(f"Windows: {result.num_windows}")
print(f"Feasible: {result.num_windows - len(result.infeasible_windows)}")
print(f"Infeasible: {len(result.infeasible_windows)}")
print(f"Total time: {solve_time:.2f}s")
print(f"Avg time per window: {solve_time / result.num_windows:.2f}s")
print(f"Total cost: ${result.total_cost:,.2f}")

if not result.all_feasible:
    print(f"\nInfeasible windows: {result.infeasible_windows}")
    print(f"Infeasibility rate: {len(result.infeasible_windows) / result.num_windows * 100:.1f}%")

print("\n" + "=" * 70)
print("COMPARISON TO 7-DAY WINDOWS")
print("=" * 70)
print("\n7-day windows (baseline):")
print("  - Windows: 51")
print("  - Feasible: 30 (59%)")
print("  - Infeasible: 21 (41%)")
print("  - Avg time: 0.75s/window")
print("  - Total time: ~38s")

print(f"\n14-day windows (this test):")
print(f"  - Windows: {result.num_windows}")
print(f"  - Feasible: {result.num_windows - len(result.infeasible_windows)} ({(result.num_windows - len(result.infeasible_windows)) / result.num_windows * 100:.0f}%)")
print(f"  - Infeasible: {len(result.infeasible_windows)} ({len(result.infeasible_windows) / result.num_windows * 100:.0f}%)")
print(f"  - Avg time: {solve_time / result.num_windows:.2f}s/window")
print(f"  - Total time: {solve_time:.0f}s")

if len(result.infeasible_windows) < 21:
    improvement = 21 - len(result.infeasible_windows)
    print(f"\n✅ IMPROVEMENT: {improvement} fewer infeasible windows with 2-week lookahead!")
elif len(result.infeasible_windows) == 21:
    print(f"\n⚠ NO CHANGE: Same infeasibility rate (lookahead didn't help)")
else:
    print(f"\n❌ WORSE: More infeasible windows (unexpected)")

print("\n" + "=" * 70)
