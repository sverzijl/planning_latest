#!/usr/bin/env python3
"""
Diagnostic: Check actual labor hours in solved model
"""

from datetime import date, timedelta
from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value

# Load data
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()

forecast_parser = ExcelParser("data/examples/Gfree Forecast.xlsm")
forecast = forecast_parser.parse_forecast(sheet_name="G610_RET")

manufacturing_site = next((loc for loc in locations if loc.type == "manufacturing"), None)

# Create model
start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=27)

model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=3,
    allow_shortages=True,
    enforce_shelf_life=True,
    start_date=start_date,
    end_date=end_date,
    use_batch_tracking=True,
    enable_production_smoothing=False
)

print("Building and solving model...")
result = model.solve(time_limit_seconds=600)

if not result.is_optimal() and not result.is_feasible():
    print(f"❌ Solve failed: {result.termination_condition}")
    exit(1)

print(f"\n✅ Solve completed: {result.termination_condition}")
print(f"   Total cost: ${result.objective_value:,.2f}\n")

# Check labor hours
print("="*70)
print("LABOR HOURS ANALYSIS")
print("="*70)

pyomo_model = model.model

# Get labor calendar data for each date
labor_by_date = {}
for labor_day in labor_calendar.days:
    if start_date <= labor_day.date <= end_date:
        labor_by_date[labor_day.date] = labor_day

violations = []

for d in sorted(model.production_dates):
    # Get actual values
    production_qty = sum(value(pyomo_model.production[d, p]) for p in model.products)
    labor_hours = value(pyomo_model.labor_hours[d])

    # Get labor day info
    labor_day = labor_by_date.get(d)
    fixed_hours = labor_day.fixed_hours if labor_day else 0

    # Determine max hours
    # Weekdays: 12 fixed + 2 OT = 14 max
    # Weekends/holidays: No fixed hours, but should still have reasonable max
    if fixed_hours > 0:
        # Weekday or public holiday with fixed hours
        max_hours = 14.0  # 12 fixed + 2 OT
    else:
        # Weekend or public holiday without fixed hours
        # Should still have a max, let's check what model uses
        max_hours = 14.0  # Same as weekdays for consistency

    day_name = d.strftime("%A")

    # Check for violations
    is_violation = labor_hours > max_hours + 0.01  # Small tolerance for numerical issues

    if production_qty > 0 or is_violation:
        violation_flag = " ⚠️  VIOLATION!" if is_violation else ""
        print(f"\n{d} ({day_name}):")
        print(f"  Production: {production_qty:,.2f} units")
        print(f"  Labor hours: {labor_hours:.2f}h (max: {max_hours:.2f}h){violation_flag}")
        print(f"  Fixed hours: {fixed_hours:.2f}h")

        if is_violation:
            violations.append((d, labor_hours, max_hours))

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

if violations:
    print(f"\n❌ Found {len(violations)} labor hour violations:")
    for d, actual, max_allowed in violations:
        print(f"   {d}: {actual:.2f}h > {max_allowed:.2f}h (excess: {actual - max_allowed:.2f}h)")
else:
    print("\n✅ No labor hour violations found!")
    print("   All days respect the 14-hour maximum.")
