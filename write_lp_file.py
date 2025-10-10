"""Write LP file for inspection."""

from datetime import date
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry

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

# Filter to just 2 days to make LP file smaller
start_date = date(2025, 6, 2)  # Monday
end_date = date(2025, 6, 3)    # Tuesday

filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
tiny_forecast = Forecast(
    name="Two Day Test",
    entries=filtered_entries,
    creation_date=date.today()
)

print(f"Forecast: {len(filtered_entries)} entries")

# Build model
model = IntegratedProductionDistributionModel(
    forecast=tiny_forecast,
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

pyomo_model = model.build_model()

# Write LP file
pyomo_model.write('debug_model.lp', io_options={'symbolic_solver_labels': True})
print(f"\nLP file written to: debug_model.lp")
print(f"Variables: {pyomo_model.nvariables()}")
print(f"Constraints: {pyomo_model.nconstraints()}")
print(f"\nInspect the file to find conflicting constraints")
