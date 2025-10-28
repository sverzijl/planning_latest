"""Diagnose: Why production on weekends when weekday capacity available?

Check if labor cost model correctly prefers weekdays (free fixed hours).
"""
from datetime import date, timedelta
from pyomo.core.base import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

try:
    initial_inventory = parser.parse_inventory()
    inventory_snapshot_date = initial_inventory.snapshot_date
except:
    initial_inventory = None
    inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)

start = inventory_snapshot_date
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("=" * 80)
print("WEEKEND PRODUCTION ANALYSIS")
print("=" * 80)

# Check labor calendar
print(f"\nLabor calendar for first 14 days:")
for i in range(14):
    check_date = start + timedelta(days=i)
    labor_day = labor_calendar.get_labor_day(check_date)
    if labor_day:
        is_weekend = check_date.weekday() >= 5
        day_type = "WEEKEND" if is_weekend else "WEEKDAY"
        print(f"  {check_date} ({day_type}):")
        print(f"    Fixed hours: {labor_day.fixed_hours}h (free!)")
        print(f"    Regular rate: ${labor_day.regular_rate}/h")
        print(f"    Overtime rate: ${labor_day.overtime_rate}/h")
        print(f"    Non-fixed rate: ${labor_day.non_fixed_rate}/h")

# Solve model
model_wrapper = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
    inventory_snapshot_date=inventory_snapshot_date,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=True
)

result = model_wrapper.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)
solved_model = model_wrapper.model
solution = model_wrapper.get_solution()

print(f"\nSolve complete: {result.termination_condition}")
print(f"Total production: {solution['total_production']:,.0f} units")

print(f"\n" + "=" * 80)
print("PRODUCTION BY DAY TYPE")
print("=" * 80)

weekday_production = 0
weekend_production = 0
weekday_hours = 0
weekend_hours = 0

labor_hours = solution.get('labor_hours_by_date', {})

for (node_id, prod, prod_date), qty in solution['production_by_date_product'].items():
    is_weekend = prod_date.weekday() >= 5
    if is_weekend:
        weekend_production += qty
    else:
        weekday_production += qty

for prod_date, hours in labor_hours.items():
    is_weekend = prod_date.weekday() >= 5
    if is_weekend:
        weekend_hours += hours
    else:
        weekday_hours += hours

print(f"\nWeekday production: {weekday_production:,.0f} units ({weekday_hours:.1f}h)")
print(f"Weekend production: {weekend_production:,.0f} units ({weekend_hours:.1f}h)")

if weekend_production > 0:
    print(f"\n⚠️  ISSUE: {weekend_production:,.0f} units on weekends!")

# Check labor costs
labor_costs = solution.get('labor_cost_by_date', {})
print(f"\n" + "=" * 80)
print("LABOR COST BY DAY")
print("=" * 80)

for i in range(min(14, len(list(labor_costs.keys())))):
    if i >= len(list(labor_costs.keys())):
        break
    check_date = sorted(labor_costs.keys())[i]
    cost = labor_costs[check_date]
    hours = labor_hours.get(check_date, 0)
    labor_day = labor_calendar.get_labor_day(check_date)
    is_weekend = check_date.weekday() >= 5

    day_type = "WEEKEND" if is_weekend else "WEEKDAY"
    print(f"\n  {check_date} ({day_type}):")
    print(f"    Hours: {hours:.1f}h")
    print(f"    Cost: ${cost:.2f}")
    print(f"    Rate: ${cost/hours:.2f}/h" if hours > 0 else "    Rate: N/A")

    if labor_day:
        print(f"    Fixed hours (free): {labor_day.fixed_hours}h")
        print(f"    Regular rate: ${labor_day.regular_rate}/h")

        if is_weekend:
            print(f"    ⚠️  Weekend: All hours cost ${labor_day.non_fixed_rate}/h!")
        else:
            print(f"    ✅ Weekday: First {labor_day.fixed_hours}h are FREE")

# Diagnosis
print(f"\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)

if weekend_production > 0 and weekday_production < weekday_hours * 1400:
    print(f"❌ LABOR COST MODEL ISSUE:")
    print(f"   Weekday capacity: {weekday_hours * 1400:,.0f} units available")
    print(f"   Weekday production: {weekday_production:,.0f} units")
    print(f"   Weekday unused: {(weekday_hours * 1400 - weekday_production):,.0f} units")
    print(f"   Weekend production: {weekend_production:,.0f} units")
    print(f"\n   Model should prefer weekdays (12h free fixed labor!)")
    print(f"   But it's producing on weekends (all hours cost money)")
    print(f"\n   Likely issue: Labor cost not differentiating fixed vs overtime correctly")
