"""Test rolling horizon with larger overlap (5 days)."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
from src.parsers.excel_parser import ExcelParser
from src.optimization import RollingHorizonSolver
from src.models.truck_schedule import TruckScheduleCollection
import time

print("=" * 70)
print("ROLLING HORIZON - LARGER OVERLAP TEST (7-DAY WINDOWS, 5-DAY OVERLAP)")
print("=" * 70)

# Load data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
forecast = forecast_parser.parse_forecast()

# Filter to first 3 weeks for testing
forecast_entries = [e for e in forecast.entries if date(2025, 6, 2) <= e.forecast_date <= date(2025, 6, 22)]
from src.models import Forecast
test_forecast = Forecast(
    name="3_week_test",
    entries=forecast_entries,
    creation_date=forecast.creation_date
)

print(f"\nTest Dataset:")
print(f"  Total demand: {sum(e.quantity for e in test_forecast.entries):,.0f} units")
forecast_dates = sorted(set(e.forecast_date for e in test_forecast.entries))
print(f"  Date range: {forecast_dates[0]} to {forecast_dates[-1]} ({len(forecast_dates)} days)")

print("\n" + "=" * 70)
print("CONFIGURATION: 7-day windows, 5-day overlap, 2-day committed")
print("=" * 70)

solver = RollingHorizonSolver(
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    window_size_days=7,
    overlap_days=5,  # INCREASED FROM 3 TO 5
    max_routes_per_destination=5,
    allow_shortages=False,
)

print("\nSolving...")
start_time = time.time()

result = solver.solve(
    forecast=test_forecast,
    solver_name='cbc',
    verbose=True
)

solve_time = time.time() - start_time

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)
print(f"\nStatus: {'✅ FEASIBLE' if result.all_feasible else '❌ INFEASIBLE'}")
print(f"Windows: {result.num_windows}")
print(f"Feasible: {result.num_windows - len(result.infeasible_windows)}")
print(f"Infeasible: {len(result.infeasible_windows)}")
print(f"Total time: {solve_time:.2f}s")

if not result.all_feasible:
    print(f"\nInfeasible windows: {result.infeasible_windows}")
