"""Check the actual Pyomo variable values for labor cost variables."""

import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from pyomo.environ import value

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
full_forecast = forecast_parser.parse_forecast()

# Small test
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 8)
products_to_keep = ['168846']
locations_to_keep = ['6104']

test_entries = [
    entry for entry in full_forecast.entries
    if (entry.forecast_date >= start_date and
        entry.forecast_date <= end_date and
        entry.product_id in products_to_keep and
        entry.location_id in locations_to_keep)
]

# Scale down
total_demand = sum(e.quantity for e in test_entries)
scale_factor = 20000 / total_demand if total_demand > 0 else 1.0
for entry in test_entries:
    entry.quantity = entry.quantity * scale_factor

test_forecast = Forecast(name="Pyomo Variables Check", entries=test_entries)

model_obj = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=1,
    allow_shortages=True,
    enforce_shelf_life=False,
)

result = model_obj.solve(solver_name='cbc', time_limit_seconds=60, tee=False)

m = model_obj.model

print("=" * 80)
print("PYOMO LABOR VARIABLE VALUES")
print("=" * 80)

for d in sorted(model_obj.production_dates):
    labor_day = labor_calendar.get_labor_day(d)
    if not labor_day:
        continue

    total_prod = sum(value(m.production[d, p]) for p in m.products)
    if total_prod < 0.01:
        continue

    is_weekend = d.weekday() >= 5
    marker = "🔴" if is_weekend else "✅"

    print(f"\n{marker} {d.strftime('%Y-%m-%d %a')} ({labor_day.is_fixed_day and 'Fixed' or 'Non-fixed'}):")
    print(f"    Production: {total_prod:7.0f} units")
    print(f"    labor_hours: {value(m.labor_hours[d]):.3f}")
    print(f"    production_day (binary): {value(m.production_day[d]):.0f}")
    print(f"    fixed_hours_used: {value(m.fixed_hours_used[d]):.3f}")
    print(f"    overtime_hours_used: {value(m.overtime_hours_used[d]):.3f}")
    print(f"    non_fixed_hours_paid: {value(m.non_fixed_hours_paid[d]):.3f}")

    # Calculate cost based on objective function formula
    if labor_day.is_fixed_day:
        cost = (labor_day.regular_rate * value(m.fixed_hours_used[d]) +
                labor_day.overtime_rate * value(m.overtime_hours_used[d]))
        print(f"    Labor cost: ${cost:.2f}")
        print(f"    Expected: ${labor_day.fixed_hours * labor_day.regular_rate:.2f} (12h @ ${labor_day.regular_rate}/h)")
        if abs(value(m.fixed_hours_used[d]) - labor_day.fixed_hours) < 0.01:
            print(f"    ✅ Correctly charging for all fixed hours!")
        else:
            print(f"    ❌ BUG: fixed_hours_used = {value(m.fixed_hours_used[d]):.2f}, should be {labor_day.fixed_hours}")
    else:
        cost = labor_day.non_fixed_rate * value(m.non_fixed_hours_paid[d])
        print(f"    Labor cost: ${cost:.2f}")
        print(f"    (Paying for {value(m.non_fixed_hours_paid[d]):.2f}h @ ${labor_day.non_fixed_rate}/h)")
