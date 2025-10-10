"""Analyze labor costs in detail to understand why weekend work is chosen."""

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
start_date = date(2025, 6, 2)  # Monday
end_date = date(2025, 6, 8)    # Sunday
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

test_forecast = Forecast(name="Labor Cost Analysis", entries=test_entries)

model = IntegratedProductionDistributionModel(
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

result = model.solve(solver_name='cbc', time_limit_seconds=60, tee=False)

m = model.model

print("=" * 80)
print("LABOR COST ANALYSIS")
print("=" * 80)

# Show labor calendar
print("\n📅 LABOR CALENDAR:")
for d in sorted(model.production_dates):
    labor_day = labor_calendar.get_labor_day(d)
    if labor_day:
        day_type = "Fixed" if labor_day.is_fixed_day else "Non-fixed"
        print(f"  {d.strftime('%Y-%m-%d %a')}: {day_type}")
        if labor_day.is_fixed_day:
            print(f"    Fixed hours: {labor_day.fixed_hours}h @ ${labor_day.regular_rate}/h")
            print(f"    OT rate: ${labor_day.overtime_rate}/h")
        else:
            print(f"    Non-fixed rate: ${labor_day.non_fixed_rate}/h")
            print(f"    Minimum hours: {labor_day.minimum_hours}h")

# Show production and costs
print("\n💰 PRODUCTION & COSTS:")
total_labor_cost = 0

for d in sorted(model.production_dates):
    labor_day = labor_calendar.get_labor_day(d)
    if not labor_day:
        continue

    total_prod = sum(value(m.production[d, p]) for p in m.products)
    hours = value(m.labor_hours[d])

    if total_prod < 0.01 and hours < 0.01:
        continue

    # Calculate labor cost
    if labor_day.is_fixed_day:
        if hours <= labor_day.fixed_hours:
            labor_cost = hours * labor_day.regular_rate
        else:
            fixed_cost = labor_day.fixed_hours * labor_day.regular_rate
            ot_hours = hours - labor_day.fixed_hours
            ot_cost = ot_hours * labor_day.overtime_rate
            labor_cost = fixed_cost + ot_cost
    else:
        # Non-fixed day (weekend/holiday)
        actual_hours = max(hours, labor_day.minimum_hours)
        labor_cost = actual_hours * labor_day.non_fixed_rate

    total_labor_cost += labor_cost

    is_weekend = d.weekday() >= 5
    marker = "🔴" if is_weekend else "✅"

    print(f"\n{marker} {d.strftime('%Y-%m-%d %a')}:")
    print(f"    Production: {total_prod:7.0f} units in {hours:5.2f} hours")
    print(f"    Labor cost: ${labor_cost:,.2f}")

    if labor_day.is_fixed_day:
        print(f"    (Fixed: {labor_day.fixed_hours}h @ ${labor_day.regular_rate}/h = ${labor_day.fixed_hours * labor_day.regular_rate:.2f})")
        if hours > labor_day.fixed_hours:
            print(f"    (OT: {hours - labor_day.fixed_hours:.2f}h @ ${labor_day.overtime_rate}/h = ${(hours - labor_day.fixed_hours) * labor_day.overtime_rate:.2f})")
    else:
        print(f"    (Non-fixed: {actual_hours:.2f}h @ ${labor_day.non_fixed_rate}/h, min {labor_day.minimum_hours}h)")

# Show cost breakdown
solution = model.get_solution()
print(f"\n📊 COST BREAKDOWN:")
print(f"  Labor cost (calculated): ${total_labor_cost:,.2f}")
print(f"  Total objective: ${result.objective_value:,.2f}")
print(f"  Shortage cost: ${solution.get('total_shortage_cost', 0):,.2f}")

# Check why demand not met
print(f"\n🔍 DEMAND ANALYSIS:")
total_demand = sum(e.quantity for e in test_forecast.entries)
total_prod = sum(value(m.production[d, p]) for d in model.production_dates for p in m.products)
print(f"  Total demand: {total_demand:.0f} units")
print(f"  Total production: {total_prod:.0f} units")
print(f"  Shortfall: {total_demand - total_prod:.0f} units")

# Show shortage penalty
print(f"\n💸 SHORTAGE PENALTY:")
print(f"  Shortage penalty per unit: ${cost_structure.shortage_penalty_per_unit}/unit")
shortfall_cost = (total_demand - total_prod) * cost_structure.shortage_penalty_per_unit
print(f"  Cost of {total_demand - total_prod:.0f} unit shortfall: ${shortfall_cost:,.2f}")
