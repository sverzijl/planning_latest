"""Diagnostic test for hierarchical temporal aggregation - 3 weeks only."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.models.time_period import VariableGranularityConfig, BucketGranularity
from src.optimization import RollingHorizonSolver
import time

print("=" * 80)
print("HIERARCHICAL WINDOW DIAGNOSTIC - 3 WEEKS")
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

# Filter to first 3 weeks
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 22)

forecast_entries = [
    e for e in full_forecast.entries
    if start_date <= e.forecast_date <= end_date
]

test_forecast = Forecast(
    name="3_week_test",
    entries=forecast_entries,
    creation_date=full_forecast.creation_date
)

print(f"\nTest Dataset:")
print(f"  Total demand: {sum(e.quantity for e in test_forecast.entries):,.0f} units")
print(f"  Date range: {start_date} to {end_date} (21 days)")

print("\n" + "=" * 80)
print("TEST 1: 21-DAY WINDOW, 14-DAY OVERLAP, ALL DAILY (CONTROL)")
print("=" * 80)

solver1 = RollingHorizonSolver(
    window_size_days=21,
    overlap_days=14,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print("\nSolving with ALL DAILY granularity...")
start_time = time.time()

result1 = solver1.solve(
    forecast=test_forecast,
    granularity_config=None,  # All daily
    solver_name='cbc',
    verbose=True
)

solve_time1 = time.time() - start_time

print(f"\n{'=' * 80}")
print(f"RESULT 1: {'✅ FEASIBLE' if result1.all_feasible else '❌ INFEASIBLE'}")
print(f"  Windows: {result1.num_windows}")
print(f"  Feasible: {result1.num_windows - len(result1.infeasible_windows)}/{result1.num_windows}")
if result1.all_feasible:
    print(f"  Total cost: ${result1.total_cost:,.2f}")
print(f"  Time: {solve_time1:.2f}s")

print("\n" + "=" * 80)
print("TEST 2: 21-DAY WINDOW, 14-DAY OVERLAP, HIERARCHICAL")
print("=" * 80)
print("  Days 1-14: Daily granularity")
print("  Days 15-21: Weekly bucket (7 days)")

granularity_config = VariableGranularityConfig(
    near_term_days=14,
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.WEEKLY
)

solver2 = RollingHorizonSolver(
    window_size_days=21,
    overlap_days=14,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print("\nSolving with HIERARCHICAL granularity...")
start_time = time.time()

result2 = solver2.solve(
    forecast=test_forecast,
    granularity_config=granularity_config,
    solver_name='cbc',
    verbose=True  # VERBOSE to see what's happening
)

solve_time2 = time.time() - start_time

print(f"\n{'=' * 80}")
print(f"RESULT 2: {'✅ FEASIBLE' if result2.all_feasible else '❌ INFEASIBLE'}")
print(f"  Windows: {result2.num_windows}")
print(f"  Feasible: {result2.num_windows - len(result2.infeasible_windows)}/{result2.num_windows}")
if result2.all_feasible:
    print(f"  Total cost: ${result2.total_cost:,.2f}")
print(f"  Time: {solve_time2:.2f}s")

# Comparison
print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)

if result1.all_feasible and result2.all_feasible:
    cost_diff = result2.total_cost - result1.total_cost
    time_diff = solve_time2 - solve_time1

    print(f"\nCost difference: ${cost_diff:,.2f} " +
          ("(hierarchical cheaper)" if cost_diff < 0 else "(daily cheaper)"))
    print(f"Time difference: {time_diff:.2f}s " +
          ("(hierarchical faster)" if time_diff < 0 else "(daily faster)"))

    if abs(cost_diff / result1.total_cost) < 0.01:
        print(f"\n→ Costs are virtually identical (<1% difference)")

    if result2.total_cost < result1.total_cost:
        print(f"\n✅ Hierarchical provides better cost!")
    else:
        print(f"\n⚠ Daily provides better or equal cost")

print("=" * 80)
