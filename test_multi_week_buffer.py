"""Test multi-week scenario to verify buffer stock eliminates weekend work.

Week 1: Sunday work expected (no buffer stock at destination)
Week 2+: Weekend work should disappear as buffer builds up
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
print("MULTI-WEEK TEST: Buffer Stock and Weekend Work")
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

# 4 weeks of demand, moderate volume
# Start on Monday (first demand date) to avoid pre-demand Sunday production
start_date = date(2025, 6, 2)  # Monday (first demand date)
end_date = date(2025, 6, 29)   # Sunday (4 weeks)
products_to_keep = ['168846']
locations_to_keep = ['6104']

test_entries = [
    entry for entry in full_forecast.entries
    if (entry.forecast_date >= start_date and
        entry.forecast_date <= end_date and
        entry.product_id in products_to_keep and
        entry.location_id in locations_to_keep)
]

# Scale to moderate volume: ~3000 units/week = ~430 units/day
# This should be doable with weekdays only after buffer builds up
total_demand = sum(e.quantity for e in test_entries)
target_weekly = 3000
weeks = 4
target_total = target_weekly * weeks
scale_factor = target_total / total_demand if total_demand > 0 else 1.0
for entry in test_entries:
    entry.quantity = entry.quantity * scale_factor

test_forecast = Forecast(name="Multi-Week Buffer Test", entries=test_entries)

print(f"\nForecast setup:")
total_demand = sum(e.quantity for e in test_forecast.entries)
print(f"  Total demand: {total_demand:.0f} units over {weeks} weeks")
print(f"  Average per week: {total_demand/weeks:.0f} units")
print(f"  Dates: {start_date} to {end_date}")
print(f"\nExpected behavior:")
print(f"  With initial buffer stock, NO weekend work should be needed")
print(f"  Weekday production replenishes buffer as it depletes")

# Set initial inventory: 10 days of average demand per dest/product
# This provides substantial buffer to eliminate weekend production
daily_demand = target_total / (weeks * 7)  # Average daily demand
initial_buffer_days = 10  # 10 days of buffer
initial_inventory = {}
for dest_id in locations_to_keep:
    for prod_id in products_to_keep:
        initial_inventory[(dest_id, prod_id)] = daily_demand * initial_buffer_days

print(f"\nInitial buffer stock:")
for (dest, prod), qty in initial_inventory.items():
    print(f"  Dest {dest}, Product {prod}: {qty:.0f} units ({initial_buffer_days} days of demand)")

# Build model with initial inventory
# Force planning horizon to start on first demand date (no pre-demand production)
model = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    start_date=start_date,  # Start on first demand date
    end_date=end_date,
    max_routes_per_destination=1,
    allow_shortages=True,
    enforce_shelf_life=False,
    initial_inventory=initial_inventory,
)

print(f"\nSolving...")
result = model.solve(solver_name='cbc', time_limit_seconds=120, tee=False)

print(f"\n📈 RESULTS:")
print(f"  Status: {result.termination_condition}")
print(f"  Optimal: {result.is_optimal()}")
print(f"  Objective: ${result.objective_value:,.2f}")

# Analyze production by week
m = model.model

print(f"\n🏭 PRODUCTION SCHEDULE BY WEEK:")
week_num = 1
week_start = start_date

weekend_production_by_week = {}

for d in sorted(model.production_dates):
    # Check if we've moved to a new week
    if d >= week_start.replace(day=week_start.day + 7):
        week_num += 1
        week_start = week_start.replace(day=week_start.day + 7)

    total_prod = sum(value(m.production[d, p]) for p in m.products)
    if total_prod < 0.01:
        continue

    hours = value(m.labor_hours[d])
    is_weekend = d.weekday() >= 5

    if is_weekend:
        if week_num not in weekend_production_by_week:
            weekend_production_by_week[week_num] = 0
        weekend_production_by_week[week_num] += total_prod

    marker = "🔴 WEEKEND" if is_weekend else "✅ Weekday"
    print(f"  Week {week_num}: {d.strftime('%Y-%m-%d %a')}: {total_prod:7.0f} units, {hours:5.2f}h {marker}")

print(f"\n📊 WEEKEND PRODUCTION BY WEEK:")
for w in sorted(weekend_production_by_week.keys()):
    print(f"  Week {w}: {weekend_production_by_week[w]:,.0f} units")

if not weekend_production_by_week:
    print(f"  No weekend production! ✅")

print(f"\n📊 INVENTORY ANALYSIS:")
solution = model.get_solution()
inventory_data = solution.get('inventory_by_dest_product_date', {})

# Group inventory by date
inventory_by_date = {}
for (dest, prod, date), qty in inventory_data.items():
    if date not in inventory_by_date:
        inventory_by_date[date] = 0
    inventory_by_date[date] += qty

print(f"  Inventory levels by date:")
for d in sorted(inventory_by_date.keys())[:14]:  # First 2 weeks
    inv = inventory_by_date[d]
    print(f"    {d.strftime('%Y-%m-%d %a')}: {inv:7.0f} units")

print(f"\n💰 COST BREAKDOWN:")
print(f"  Labor Cost:      ${solution['total_labor_cost']:>12,.2f}")
print(f"  Production Cost: ${solution['total_production_cost']:>12,.2f}")
print(f"  Transport Cost:  ${solution['total_transport_cost']:>12,.2f}")
print(f"  Inventory Cost:  ${solution['total_inventory_cost']:>12,.2f}")
print(f"  Shortage Cost:   ${solution['total_shortage_cost']:>12,.2f}")
print(f"  Truck Cost:      ${solution.get('total_truck_cost', 0):>12,.2f}")
print(f"  ---")
print(f"  TOTAL:           ${solution['total_cost']:>12,.2f}")

# Calculate holding cost per unit day
holding_rate = cost_structure.storage_cost_ambient_per_unit_day
print(f"\nInventory holding rate: ${holding_rate:.4f} per unit per day")

# Calculate average weekend labor premium
labor_days = [labor_calendar.get_labor_day(d) for d in sorted(model.production_dates)]
weekend_days = [ld for ld in labor_days if ld and ld.date.weekday() >= 5]
if weekend_days:
    avg_weekend_rate = sum(ld.non_fixed_rate for ld in weekend_days) / len(weekend_days)
    print(f"Weekend labor rate: ${avg_weekend_rate:.2f} per hour")
    print(f"Ratio (weekend labor / holding cost): {avg_weekend_rate / holding_rate if holding_rate > 0 else 'inf'}:1")

print(f"\n✅ VERIFICATION:")
success = True

# With initial inventory, NO weekend work should be needed at all
total_weekend = sum(weekend_production_by_week.values())
if total_weekend > 0:
    print(f"  ❌ FAILED: {total_weekend:.0f} units weekend production across all weeks")
    print(f"     Expected: 0 (initial buffer should eliminate all weekend work)")
    for w, qty in sorted(weekend_production_by_week.items()):
        print(f"       Week {w}: {qty:.0f} units")
    success = False
else:
    print(f"  ✅ PASSED: NO weekend production! Initial buffer working perfectly!")

# Check if demand is met
total_shortage = solution.get('total_shortage_cost', 0) / cost_structure.shortage_penalty_per_unit
if total_shortage > 1:
    print(f"  ⚠️  WARNING: {total_shortage:.0f} units shortage")

if success:
    print(f"\n🎉 TEST PASSED: Buffer stock eliminates weekend work after week 1!")
else:
    print(f"\n❌ TEST FAILED: Weekend work persists beyond week 1")
    print(f"\nPossible causes:")
    print(f"  1. Model doesn't have destination inventory variables")
    print(f"  2. Shelf life constraints prevent buffer building")
    print(f"  3. Cost structure doesn't incentivize buffer stock")
