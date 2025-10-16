"""
Test rolling horizon on full 29-week dataset with 7-DAY WINDOWS.

With original model code (no temporal aggregation), 7-day windows should solve quickly.

Configuration:
- Window size: 7 days (1 week)
- Overlap: 3 days
- Committed per window: 4 days
- Expected windows: ~51 windows for 204-day horizon
- Expected per-window time: <60s each
"""

from datetime import date
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver
import time

print("=" * 70)
print("ROLLING HORIZON - FULL 29-WEEK DATASET (7-DAY WINDOWS)")
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
print("  Window size: 7 days")
print("  Overlap: 3 days")
print(f"  Expected windows: ~{total_days // 4}")
print("  Expected time: <60s per window")

print("\n" + "=" * 70)
print("SOLVING")
print("=" * 70)

solver = RollingHorizonSolver(
    window_size_days=7,
    overlap_days=3,
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
print(f"Total solve time: {result.total_solve_time:.1f}s ({result.total_solve_time/60:.1f} min)")
print(f"Average per window: {result.total_solve_time / result.num_windows:.1f}s")

if result.all_feasible:
    print(f"\nTotal cost: ${result.total_cost:,.2f}")

# Window breakdown
print(f"\n" + "=" * 70)
print("PER-WINDOW TIMES")
print("=" * 70)

for i, w in enumerate(result.window_results, 1):
    status = "✅" if w.is_feasible() else "❌"
    print(f"{i:2d}. {w.window_id}: {status} {w.solve_time_seconds:5.1f}s")

print(f"\n" + "=" * 70)
