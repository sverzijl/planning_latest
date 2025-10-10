"""
Test that initial_inventory is being set correctly
"""
import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

# Filter to 3 days
start_date = date(2025, 10, 13)
end_date = date(2025, 10, 15)
filtered_entries = [e for e in forecast.entries if start_date <= e.forecast_date <= end_date]
forecast.entries = filtered_entries

product_ids = sorted(set(e.product_id for e in forecast.entries))[:2]
forecast.entries = [e for e in forecast.entries if e.product_id in product_ids]

# Create initial inventory
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122', pid, 'ambient')] = 10000.0

print(f"Initial inventory dict: {initial_inv}")

model_obj = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

print(f"\nModel initial_inventory attribute: {model_obj.initial_inventory}")
print(f"\nFirst production date: {min(model_obj.production_dates)}")
