"""Test 1: Minimal case - Verify weekend avoidance with low demand.

This test uses minimal demand that can easily be satisfied with weekday
production only. The model should NOT use weekend production.

Expected behavior:
- No weekend production (Saturday/Sunday should have 0 hours)
- All demand met with weekday fixed hours only
- No overtime needed
- Total labor cost should be minimal
"""

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

print("=" * 80)
print("TEST 1: MINIMAL - WEEKEND AVOIDANCE")
print("=" * 80)

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

# Minimal test: 1 week, low demand (should fit in weekday capacity)
# Weekday capacity: 5 days × 12 hours × 1400 units/hour = 84,000 units
# Target: ~40,000 units (well within capacity, no overtime/weekend needed)
start_date = date(2025, 6, 2)  # Monday
end_date = date(2025, 6, 8)    # Sunday (1 week)
products_to_keep = ['168846']  # Just one product
locations_to_keep = ['6104']   # Just one destination

test_entries = [
    entry for entry in full_forecast.entries
    if (entry.forecast_date >= start_date and
        entry.forecast_date <= end_date and
        entry.product_id in products_to_keep and
        entry.location_id in locations_to_keep)
]

# Scale down demand to ensure it fits comfortably in weekday capacity
total_demand = sum(e.quantity for e in test_entries)
scale_factor = 20000 / total_demand if total_demand > 0 else 1.0
for entry in test_entries:
    entry.quantity = entry.quantity * scale_factor

test_forecast = Forecast(name="Minimal Weekend Test", entries=test_entries)

print(f"\nForecast subset:")
total_demand = sum(e.quantity for e in test_forecast.entries)
print(f"  Total demand: {total_demand:.0f} units")
print(f"  Dates: {start_date} to {end_date} (7 days)")
print(f"  Products: {products_to_keep}")
print(f"  Locations: {locations_to_keep}")
print(f"\nWeekday capacity: 5 days × 12h × 1400 units/h = 84,000 units")
print(f"Demand / Capacity ratio: {100*total_demand/84000:.1f}%")
print(f"Expected: NO weekend work needed")

# Build model
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

print(f"\nBuilding model...")
result = model.solve(solver_name='cbc', time_limit_seconds=60, tee=False)

print(f"\n📈 RESULTS:")
print(f"  Status: {result.termination_condition}")
print(f"  Optimal: {result.is_optimal()}")
print(f"  Objective: ${result.objective_value:,.2f}")

# Analyze labor usage
m = model.model
solution = model.get_solution()
production = solution.get('production_by_date', {})

print(f"\n🏭 PRODUCTION SCHEDULE:")
weekend_production = 0
weekday_production = 0
weekend_hours = 0
weekday_hours = 0

for date in sorted(model.production_dates):
    day_name = date.strftime('%a')
    is_weekend = date.weekday() >= 5  # Saturday=5, Sunday=6

    total_prod = sum(value(m.production[date, p]) for p in m.products)
    hours = value(m.labor_hours[date]) if total_prod > 0.01 else 0

    if total_prod > 0.01 or hours > 0.01:
        marker = "🔴 WEEKEND" if is_weekend else "✅ Weekday"
        print(f"  {date.strftime('%Y-%m-%d')} ({day_name}): {total_prod:7.0f} units, {hours:5.2f} hours {marker}")

        if is_weekend:
            weekend_production += total_prod
            weekend_hours += hours
        else:
            weekday_production += total_prod
            weekday_hours += hours

print(f"\n📊 LABOR SUMMARY:")
print(f"  Weekday production: {weekday_production:,.0f} units in {weekday_hours:.1f} hours")
print(f"  Weekend production: {weekend_production:,.0f} units in {weekend_hours:.1f} hours")

# Check for overtime
overtime_days = 0
for date in sorted(model.production_dates):
    if date.weekday() < 5:  # Weekday
        labor_day = labor_calendar.get_labor_day(date)
        if labor_day:
            hours = value(m.labor_hours[date])
            if hours > labor_day.fixed_hours + 0.01:
                overtime_days += 1
                ot_hours = hours - labor_day.fixed_hours
                print(f"  ⚠️  Overtime on {date.strftime('%Y-%m-%d')}: {ot_hours:.2f} hours")

print(f"\n✅ VERIFICATION:")
success = True

if weekend_production > 0.01:
    print(f"  ❌ FAILED: Weekend production = {weekend_production:.0f} units (expected 0)")
    success = False
else:
    print(f"  ✅ PASSED: No weekend production")

if overtime_days > 0:
    print(f"  ⚠️  WARNING: {overtime_days} days with overtime (unexpected for low demand)")
else:
    print(f"  ✅ PASSED: No overtime needed")

# Verify all demand met
total_prod = sum(value(m.production[d, p]) for d in model.production_dates for p in m.products)
demand_met = abs(total_prod - total_demand) < 1.0

if demand_met:
    print(f"  ✅ PASSED: Demand met ({total_prod:.0f} / {total_demand:.0f} units)")
else:
    print(f"  ❌ FAILED: Demand not met ({total_prod:.0f} / {total_demand:.0f} units)")
    success = False

if success:
    print(f"\n🎉 TEST PASSED: Model avoids weekend work when not needed!")
else:
    print(f"\n❌ TEST FAILED: Model used weekend work unnecessarily or missed demand")
