"""Test with small data subset to verify D-1/D0 timing constraint."""

import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry

# Parse network data (full)
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

# Parse full forecast
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
full_forecast = forecast_parser.parse_forecast()

# Create SMALL subset: Only 2 weeks, 2 products, 2 destinations
# Use destinations that trucks serve DIRECTLY from manufacturing (6122):
# - 6104: NSW/ACT hub (direct truck destination)
# - 6110: QLD direct
# - 6125: VIC/TAS/SA hub (direct truck destination)
# Note: 6103 is served via 6104 (multi-leg: 6122→6104→6103), not direct
start_date = date(2025, 6, 2)  # Monday
end_date = date(2025, 6, 15)   # Sunday (2 weeks)
products_to_keep = ['168846', '168847']  # First 2 products
locations_to_keep = ['6104', '6110']  # Direct truck destinations from 6122

# Filter forecast
small_entries = [
    entry for entry in full_forecast.entries
    if (entry.forecast_date >= start_date and
        entry.forecast_date <= end_date and
        entry.product_id in products_to_keep and
        entry.location_id in locations_to_keep)
]

small_forecast = Forecast(name="Small Test Forecast", entries=small_entries)

print(f'Small forecast: {len(small_entries)} entries')
print(f'  Dates: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)')
print(f'  Products: {products_to_keep}')
print(f'  Locations: {locations_to_keep}')

print('\nBuilding model...')
model = IntegratedProductionDistributionModel(
    forecast=small_forecast,
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

print(f'  Routes: {len(model.enumerated_routes)}')
print(f'  Production dates: {len(model.production_dates)}')
print(f'  Trucks: {len(model.truck_indices)}')

print('\n⚡ Solving (60s timeout, 5% gap)...')
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.05,
    tee=False,
)

print(f'\n📈 RESULTS:')
print(f'  Status: {result.termination_condition}')
if result.objective_value:
    print(f'  Objective: ${result.objective_value:,.2f}')
print(f'  Solve time: {result.solve_time_seconds:.1f}s')

if result.is_optimal() or result.is_feasible():
    # Extract weekend production stats
    solution = model.get_solution()
    production = solution.get('production_by_date_product', {})

    weekend_production = 0
    weekday_production = 0

    for (d, p), qty in production.items():
        labor_day = labor_calendar.get_labor_day(d)
        if labor_day and not labor_day.is_fixed_day:
            weekend_production += qty
        else:
            weekday_production += qty

    total = weekend_production + weekday_production

    print(f'\n📦 PRODUCTION BREAKDOWN:')
    print(f'  Weekday: {weekday_production:,.0f} units ({weekday_production/total*100:.1f}%)')
    print(f'  Weekend: {weekend_production:,.0f} units ({weekend_production/total*100:.1f}%)')
    print(f'  Total: {total:,.0f} units')

    # Show daily production
    print(f'\n📅 DAILY PRODUCTION:')
    dates_sorted = sorted(set(d for (d, p) in production.keys()))
    for d in dates_sorted:
        labor_day = labor_calendar.get_labor_day(d)
        day_type = "WEEKEND" if (labor_day and not labor_day.is_fixed_day) else "weekday"
        day_total = sum(qty for (dt, p), qty in production.items() if dt == d)
        if day_total > 0:
            print(f'  {d} ({d.strftime("%a")}): {day_total:6,.0f} units [{day_type}]')
