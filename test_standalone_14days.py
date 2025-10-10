"""Test standalone 14-day window (June 2-15) to compare with rolling horizon."""

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.models.forecast import Forecast
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import IntegratedProductionDistributionModel
import time

print("Testing standalone 14-day window: June 2-15, 2025")
print("="*70)

# Load data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Filter for June 2-15 (14 days) - same as window 1
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 15)
filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
forecast = Forecast(name="14days", entries=filtered_entries, creation_date=date.today())

print(f"\nForecast: {start_date} to {end_date}")
print(f"  Entries: {len(forecast.entries)}")
print(f"  Total demand: {sum(e.quantity for e in forecast.entries):,.0f}")

# Build model
print("\nBuilding model...")
build_start = time.time()
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)
build_time = time.time() - build_start
print(f"  Build time: {build_time:.1f}s")
print(f"  Production dates: {len(model.production_dates)}")

# Solve
print("\nSolving with CBC (60s timeout)...")
solve_start = time.time()
result = model.solve(solver_name='cbc', time_limit_seconds=60)
solve_time = time.time() - solve_start

print(f"\n{'='*70}")
print(f"RESULT")
print(f"{'='*70}")
print(f"  Success: {result.success}")
print(f"  Termination: {result.termination_condition}")
print(f"  Solve time: {solve_time:.1f}s")

if result.success:
    print(f"  Objective: ${result.objective_value:,.2f}")
    print("\n✅ 14-day window solved successfully in <60s")
elif solve_time >= 59:
    print("\n❌ TIMEOUT - Did not complete in 60s")
    print("   This matches the rolling horizon behavior")
else:
    print(f"\n❌ INFEASIBLE or ERROR")
    if result.infeasibility_message:
        print(f"   Message: {result.infeasibility_message}")
