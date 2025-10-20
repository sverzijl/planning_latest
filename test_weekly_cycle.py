#!/usr/bin/env python3
"""Test weekly production cycle approach: 25 binary vars instead of 210.

Concept:
--------
Instead of binary decision for each day (5 products × 42 days = 210 binary vars),
create a REPEATING WEEKLY PATTERN:
- Binary variables for 5 weekdays: product_weekday[product, weekday] = 25 vars
- Link each weekday to the pattern: Mon_week1 = Mon_week2 = ... = weekly_pattern[Mon]
- Separate binary vars for weekends/holidays (don't repeat)

Result: ~30-40 binary vars total instead of 210

Expected performance:
- Weekly cycle solve: ~20-40s (much easier problem)
- Extract pattern and use as warmstart for full 210-var solve
- Full solve with warmstart: ~150-200s (vs 388s timeout cold)
- Total: ~170-240s vs 388s timeout
"""

from datetime import timedelta, date as Date
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from pyomo.environ import value as pyo_value
import time

# Load data
parser = MultiFileParser('data/examples/Gfree Forecast.xlsm', 'data/examples/Network_Config.xlsx')
forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manuf_loc = [l for l in locations if l.type == LocationType.MANUFACTURING][0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)
converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

start_date = min(e.forecast_date for e in forecast.entries)
end_date = start_date + timedelta(days=41)  # 6 weeks

products = sorted(set(e.product_id for e in forecast.entries))
manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

print("="*80)
print("WEEKLY CYCLE APPROACH")
print("="*80)

# Categorize dates into weekdays vs weekends
dates_range = []
current = start_date
while current <= end_date:
    dates_range.append(current)
    current += timedelta(days=1)

weekday_dates = {}  # {weekday_num: [dates]}
weekend_dates = []

for date_val in dates_range:
    weekday = date_val.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
    labor_day = labor_calendar.get_labor_day(date_val)

    if weekday < 5 and labor_day and labor_day.is_fixed_day:
        # Regular weekday
        if weekday not in weekday_dates:
            weekday_dates[weekday] = []
        weekday_dates[weekday].append(date_val)
    else:
        # Weekend or holiday
        weekend_dates.append(date_val)

weekday_count = sum(len(dates) for dates in weekday_dates.values())
print(f"\\nDate categorization:")
print(f"  Weekdays (Mon-Fri): {weekday_count} days across {len(weekday_dates)} weekday types")
for wd, dates in sorted(weekday_dates.items()):
    print(f"    Weekday {wd}: {len(dates)} days")
print(f"  Weekends/Holidays: {len(weekend_dates)} days")

# Calculate binary variables
weekly_pattern_vars = 5 * 5  # 5 products × 5 weekdays
weekend_vars = 5 * len(weekend_dates)  # 5 products × weekend days
total_weekly_approach = weekly_pattern_vars + weekend_vars

total_individual = 5 * len(dates_range)

print(f"\\nBinary variable comparison:")
print(f"  Individual days: {total_individual} vars (5 products × {len(dates_range)} days)")
print(f"  Weekly cycle: {total_weekly_approach} vars ({weekly_pattern_vars} pattern + {weekend_vars} weekends)")
print(f"  Reduction: {total_individual - total_weekly_approach} vars ({100*(1-total_weekly_approach/total_individual):.1f}% fewer)")

# Build weekly cycle force pattern
# Link all Mondays to same decision, all Tuesdays to same decision, etc.
print(f"\\nBuilding weekly cycle pattern...")

# First, solve with weekly pattern by creating a force pattern
# that links same weekdays together
force_pattern_weekly = {}

# For simplicity in this test, I'll create a hybrid:
# - Fix all weekdays of same type to same value (simulate weekly pattern)
# - Leave weekends as binary

# Actually, for a true test I need to modify UnifiedNodeModel to support
# weekly cycle constraints. For now, let me test the CONCEPT by using
# a simple heuristic pattern

print(f"\\nFor proof of concept, testing with simplified pattern...")
print(f"(Full implementation would require new weekly_cycle constraint in UnifiedNodeModel)")

# Create a simple pattern: alternate SKUs by weekday
weekday_to_product = {
    0: [products[0], products[1]],  # Monday: 2 SKUs
    1: [products[1], products[2]],  # Tuesday: 2 SKUs
    2: [products[2], products[3]],  # Wednesday: 2 SKUs
    3: [products[3], products[4]],  # Thursday: 2 SKUs
    4: [products[0], products[4]],  # Friday: 2 SKUs
}

for node_id in manufacturing_nodes_list:
    for date_val in dates_range:
        weekday = date_val.weekday()

        if weekday < 5:
            # Weekday - use pattern
            for product in products:
                key = (node_id, product, date_val)
                if weekday in weekday_to_product and product in weekday_to_product[weekday]:
                    force_pattern_weekly[key] = 1  # Produce
                else:
                    force_pattern_weekly[key] = 0  # Skip
        # Weekends - leave as binary (not in pattern = binary)

num_fixed = sum(1 for v in force_pattern_weekly.values() if v == 1 or v == 0)
num_binary = 5 * len(dates_range) - num_fixed

print(f"Pattern created: {num_fixed} fixed (weekly pattern), {num_binary} binary (weekends)")

# Solve with weekly pattern
print(f"\\nSolving with weekly pattern constraint...")
start = time.time()
model_weekly = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
    force_sku_pattern=force_pattern_weekly,
)

result_weekly = model_weekly.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.05, tee=False)
time_weekly = time.time() - start

print(f"\\nWeekly pattern solve:")
print(f"  Time: {time_weekly:.1f}s ({num_binary} binary vars)")
print(f"  Cost: ${result_weekly.objective_value:,.0f}")
if result_weekly.gap:
    print(f"  Gap: {result_weekly.gap*100:.2f}%")

# Extract warmstart from weekly solve
print(f"\\nExtracting warmstart from weekly pattern...")
warmstart = {}
for node_id in manufacturing_nodes_list:
    for product in products:
        for date_val in dates_range:
            key = (node_id, product, date_val)
            if key in force_pattern_weekly:
                warmstart[key] = force_pattern_weekly[key]
            elif (node_id, product, date_val) in model_weekly.model.production:
                try:
                    qty = pyo_value(model_weekly.model.production[node_id, product, date_val])
                    warmstart[key] = 1 if qty > 0.01 else 0
                except:
                    warmstart[key] = 0

num_warmstart_active = sum(1 for v in warmstart.values() if v == 1)
print(f"  Warmstart: {num_warmstart_active}/210 active SKUs")

# Final solve with warmstart
print(f"\\nFinal binary solve (with weekly warmstart)...")
start = time.time()
model_final = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
)

result_final = model_final.solve(
    solver_name='appsi_highs',
    time_limit_seconds=240,
    mip_gap=0.03,
    use_warmstart=True,
    warmstart_hints=warmstart,
    tee=False
)
time_final = time.time() - start

print(f"  Time: {time_final:.1f}s")
print(f"  Cost: ${result_final.objective_value:,.0f}")
if result_final.gap:
    print(f"  Gap: {result_final.gap*100:.2f}%")

# Summary
total_weekly_approach = time_weekly + time_final

print(f"\\n{'='*80}")
print("6-WEEK COMPARISON - WEEKLY CYCLE APPROACH")
print(f"{'='*80}")
print(f"Single-phase (cold):              388s timeout, $989,204, 19.8% gap")
print(f"Greedy all-fixed + final:         361s, $805,700, 1.8% gap")
print(f"Weekly cycle + final:             {total_weekly_approach:.0f}s, ${result_final.objective_value:,.0f}, {result_final.gap*100:.1f}% gap" if result_final.gap else f"Weekly cycle + final:             {total_weekly_approach:.0f}s, ${result_final.objective_value:,.0f}")
print(f"  - Weekly pattern phase: {time_weekly:.1f}s")
print(f"  - Final binary phase: {time_final:.1f}s")
print("="*80)
