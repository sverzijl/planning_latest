"""Test with two weeks of data to verify feasibility fix."""

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Filter to just first 2 weeks (June 2-15, 2025)
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 15)

filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
two_week_forecast = Forecast(
    name="Two Week Test",
    entries=filtered_entries,
    creation_date=date.today()
)

print(f"Forecast: {len(filtered_entries)} entries ({start_date} to {end_date})")

# Build model
print(f"\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=two_week_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print(f"  Planning horizon: {min(model.production_dates)} to {max(model.production_dates)} ({len(model.production_dates)} days)")

# Solve
print(f"\nSolving (60s limit)...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.01,
    tee=False
)

print(f"\nResult: {result.termination_condition}")
print(f"Success: {result.success}")
if result.objective_value:
    print(f"Objective: ${result.objective_value:,.2f}")
if result.gap:
    print(f"Gap: {result.gap*100:.2f}%")

if result.is_optimal():
    print(f"\n✅ TWO WEEK TEST PASSED - Optimal solution found!")
elif result.is_feasible():
    print(f"\n✅ TWO WEEK TEST PASSED - Feasible solution found (not optimal, but model is feasible)")
else:
    print(f"\n❌ TWO WEEK TEST FAILED - Model is still infeasible")
