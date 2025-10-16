"""Test if 3 weeks is feasible as a single window."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
from src.parsers.excel_parser import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models import Forecast
from src.models.truck_schedule import TruckScheduleCollection
import time

print("=" * 70)
print("SINGLE WINDOW TEST: 3 weeks (Jun 2-22)")
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

# Filter to 3 weeks
forecast_entries = [e for e in forecast.entries if date(2025, 6, 2) <= e.forecast_date <= date(2025, 6, 22)]
test_forecast = Forecast(
    name="3_week_test",
    entries=forecast_entries,
    creation_date=forecast.creation_date
)

print(f"\nDataset:")
print(f"  Total demand: {sum(e.quantity for e in test_forecast.entries):,.0f} units")
forecast_dates = sorted(set(e.forecast_date for e in test_forecast.entries))
print(f"  Date range: {forecast_dates[0]} to {forecast_dates[-1]} ({len(forecast_dates)} days)")

print("\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=False,
)

print(f"Planning horizon: {model.start_date} to {model.end_date}")
print(f"Production dates: {len(model.production_dates)} days")

print("\nSolving...")
start = time.time()
result = model.solve('cbc', time_limit_seconds=600)
solve_time = time.time() - start

print(f"\nResult: {'✅ FEASIBLE' if result.success else '❌ INFEASIBLE'}")
print(f"Solve time: {solve_time:.2f}s")

if result.success:
    solution = model.get_solution()
    print(f"Total cost: ${solution['total_cost']:,.2f}")
else:
    print(f"Infeasibility: {result.infeasibility_message}")
