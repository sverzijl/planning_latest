"""
Test rolling horizon on full 29-week dataset with 14-day windows (NO temporal aggregation).

This avoids the truck schedule infeasibility issue while keeping windows small enough
to solve in reasonable time.

Configuration:
- Window size: 14 days (2 weeks)
- Overlap: 7 days (1 week)
- Committed per window: 7 days
- Granularity: Daily (no aggregation)
- Expected windows: ~29 windows for 204-day horizon
- Expected solve time: Variable per window, Week 3 may be slower
"""

from datetime import date
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver
import time

print("=" * 70)
print("ROLLING HORIZON - FULL 29-WEEK DATASET (14-DAY WINDOWS)")
print("=" * 70)

print("\nLoading data...")
start_time = time.time()

# Load all data
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
print(f"  Forecast entries: {len(full_forecast.entries):,}")
print(f"  Start date: {min(e.forecast_date for e in full_forecast.entries)}")
print(f"  End date: {max(e.forecast_date for e in full_forecast.entries)}")
forecast_dates = sorted(set(e.forecast_date for e in full_forecast.entries))
total_days = (forecast_dates[-1] - forecast_dates[0]).days + 1
print(f"  Total days: {total_days}")
print(f"  Total demand: {sum(e.quantity for e in full_forecast.entries):,.0f} units")
print(f"  Load time: {load_time:.1f}s")

print("\n" + "=" * 70)
print("CONFIGURATION")
print("=" * 70)

print("\nRolling Horizon Configuration:")
print("  Window size: 14 days (2 weeks)")
print("  Overlap: 7 days (1 week)")
print("  Committed days per window: 7")
print(f"  Expected windows: ~{total_days // 7} (approximate)")
print("  Temporal aggregation: NO (daily granularity)")
print("  Reason: Avoids truck schedule infeasibility")

print("\n" + "=" * 70)
print("SOLVING FULL 29-WEEK PROBLEM")
print("=" * 70)

print("\nInitializing rolling horizon solver...")
solver = RollingHorizonSolver(
    window_size_days=14,
    overlap_days=7,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print("\nSolving...")
print("(This will show progress for each window)")

solve_start = time.time()

result = solver.solve(
    forecast=full_forecast,
    granularity_config=None,  # NO temporal aggregation
    solver_name='cbc',
    verbose=True
)

solve_time = time.time() - solve_start

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)

print(f"\nSolution status:")
print(f"  All windows feasible: {'✅ YES' if result.all_feasible else '❌ NO'}")
print(f"  Number of windows: {result.num_windows}")
print(f"  Total solve time: {result.total_solve_time:.1f}s")
print(f"  Wall clock time: {solve_time:.1f}s")
print(f"  Average per window: {result.total_solve_time / result.num_windows:.1f}s")

if not result.all_feasible:
    print(f"\n❌ Some windows infeasible: {result.infeasible_windows}")
else:
    print(f"\n✅ All windows solved successfully!")
    print(f"\nTotal cost: ${result.total_cost:,.2f}")
    print(f"  Production plan entries: {len(result.complete_production_plan)}")
    print(f"  Shipment plan entries: {len(result.complete_shipment_plan)}")

# Window-by-window breakdown
print(f"\n" + "=" * 70)
print("WINDOW-BY-WINDOW BREAKDOWN")
print("=" * 70)

for i, window_result in enumerate(result.window_results, 1):
    status_icon = "✅" if window_result.is_feasible() else "❌"
    opt_status = "OPTIMAL" if window_result.is_optimal() else "FEASIBLE" if window_result.is_feasible() else "INFEASIBLE"

    print(f"\nWindow {i}: {window_result.window_id}")
    print(f"  Status: {status_icon} {opt_status}")
    print(f"  Solve time: {window_result.solve_time_seconds:.1f}s")
    if window_result.is_feasible():
        print(f"  Cost: ${window_result.total_cost:,.2f}")
        print(f"  Production entries: {len(window_result.production_plan)}")
        print(f"  Shipments: {len(window_result.shipments)}")

print("\n" + "=" * 70)
print("PERFORMANCE SUMMARY")
print("=" * 70)

# Find slowest and fastest windows
if result.window_results:
    times = [(i+1, w.window_id, w.solve_time_seconds) for i, w in enumerate(result.window_results)]
    times_sorted = sorted(times, key=lambda x: x[2], reverse=True)

    print(f"\nSlowest windows:")
    for i, (idx, wid, t) in enumerate(times_sorted[:5], 1):
        print(f"  {i}. Window {idx} ({wid}): {t:.1f}s")

    print(f"\nFastest windows:")
    for i, (idx, wid, t) in enumerate(reversed(times_sorted[-5:]), 1):
        print(f"  {i}. Window {idx} ({wid}): {t:.1f}s")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)

if result.all_feasible:
    print(f"\n✅ SUCCESS!")
    print(f"   Full 29-week problem solved with rolling horizon")
    print(f"   Total time: {solve_time:.1f}s ({solve_time/60:.1f} minutes)")
    print(f"   Average per window: {result.total_solve_time / result.num_windows:.1f}s")

    if result.total_solve_time > 600:
        print(f"\n⚠️  Note: Total solve time > 10 minutes")
        print(f"   Consider further optimization if needed")
else:
    print(f"\n❌ Some windows infeasible")
    print(f"   Infeasible windows: {result.infeasible_windows}")
    print(f"   Debug needed")

print("\n" + "=" * 70)
