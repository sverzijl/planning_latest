"""Test if shelf life enforcement is the bottleneck for 21-day windows."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization import IntegratedProductionDistributionModel
import time

print("=" * 80)
print("21-DAY WINDOW: SHELF LIFE ENFORCEMENT TEST")
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

# Filter to 21 days
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 22)

forecast_entries = [
    e for e in full_forecast.entries
    if start_date <= e.forecast_date <= end_date
]

test_forecast = Forecast(
    name="21_day_test",
    entries=forecast_entries,
    creation_date=full_forecast.creation_date
)

print(f"\nTest Dataset:")
print(f"  Date range: {start_date} to {end_date} (21 days)")
print(f"  Total demand: {sum(e.quantity for e in test_forecast.entries):,.0f} units")

print("\n" + "=" * 80)
print("TEST 1: WITH SHELF LIFE ENFORCEMENT (Expected: Timeout)")
print("=" * 80)

model1 = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,  # ENFORCED
)

print("\nBuilding and solving with shelf life enforcement...")
start_time = time.time()

try:
    result1 = model1.solve(
        solver_name='cbc',
        time_limit_seconds=30,  # 30 second timeout
        tee=False
    )
    solve_time1 = time.time() - start_time

    print(f"\n✅ SOLVED in {solve_time1:.2f}s")
    print(f"   Status: {result1.status}")
    print(f"   Cost: ${result1.objective_value:,.2f}" if result1.objective_value else "   No solution")
except Exception as e:
    solve_time1 = time.time() - start_time
    print(f"\n⏱ TIMEOUT/ERROR after {solve_time1:.2f}s")

print("\n" + "=" * 80)
print("TEST 2: WITHOUT SHELF LIFE ENFORCEMENT (Can this solve quickly?)")
print("=" * 80)

model2 = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=False,  # DISABLED
)

print("\nBuilding and solving WITHOUT shelf life enforcement...")
start_time = time.time()

try:
    result2 = model2.solve(
        solver_name='cbc',
        time_limit_seconds=30,  # 30 second timeout
        tee=False
    )
    solve_time2 = time.time() - start_time

    print(f"\n✅ SOLVED in {solve_time2:.2f}s")
    print(f"   Status: {result2.status}")
    print(f"   Cost: ${result2.objective_value:,.2f}" if result2.objective_value else "   No solution")
except Exception as e:
    solve_time2 = time.time() - start_time
    print(f"\n⏱ TIMEOUT/ERROR after {solve_time2:.2f}s")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

print(f"\nTest 1 (WITH shelf life): {solve_time1:.2f}s")
print(f"Test 2 (WITHOUT shelf life): {solve_time2:.2f}s")

if solve_time2 < 10 and solve_time1 >= 60:
    print(f"\n🎯 SHELF LIFE IS THE BOTTLENECK!")
    print(f"   Without shelf life constraints, 21-day window solves in {solve_time2:.2f}s")
    print(f"   With shelf life constraints, it times out")
    print(f"\n   → Longer horizons create tighter shelf life constraints")
    print(f"   → This makes the feasible region harder to explore")
elif solve_time1 < 60 and solve_time2 < 60:
    print(f"\n✓ Both configurations solve quickly")
    print(f"   Shelf life is NOT the bottleneck")
else:
    print(f"\n⚠ Both configurations struggle")
    print(f"   Problem is elsewhere (CBC limitations, other constraints)")

print("=" * 80)
