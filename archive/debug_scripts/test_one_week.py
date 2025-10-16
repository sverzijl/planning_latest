"""Test with just one week of data to isolate infeasibility."""

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

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

# Filter to just first week (June 2-8, 2025 = Mon-Sun)
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 8)

from src.models.forecast import Forecast, ForecastEntry
filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
one_week_forecast = Forecast(
    name="One Week Test",
    entries=filtered_entries,
    creation_date=date.today()
)

print(f"Filtered forecast: {len(filtered_entries)} entries ({start_date} to {end_date})")
print(f"Destinations: {len(set(e.location_id for e in filtered_entries))}")
print(f"Products: {len(set(e.product_id for e in filtered_entries))}")

# Build model
print(f"\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=one_week_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,  # Should make it feasible!
    enforce_shelf_life=True,
)

print(f"  Routes enumerated: {len(model.enumerated_routes)}")
print(f"  Production dates: {min(model.production_dates)} to {max(model.production_dates)} ({len(model.production_dates)} days)")

# Solve
print(f"\nSolving...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.01,
    tee=True  # Show solver output
)

print(f"\nResult: {result.termination_condition}")
print(f"Success: {result.success}")
if result.objective_value:
    print(f"Objective: ${result.objective_value:,.2f}")
else:
    print(f"Objective: N/A")

if result.is_feasible():
    print(f"\n✅ ONE WEEK TEST PASSED - Model is feasible")
else:
    print(f"\n❌ ONE WEEK TEST FAILED - Model is infeasible even with shortages allowed!")
    print(f"   This indicates a fundamental bug in the model constraints")
