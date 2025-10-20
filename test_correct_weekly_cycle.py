#!/usr/bin/env python3
"""Correctly implemented weekly cycle with pattern variables and linking constraints.

Correct approach using Pyomo:
1. Create 25 binary pattern variables: product_weekday_pattern[product, weekday]
2. Link weekday dates to pattern: product_produced[node, product, date] == pattern[product, weekday]
3. Weekends/holidays: regular binary variables (no linking)

Total binary vars: 25 (pattern) + ~80 (weekends) = ~105 vs 280
"""

from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from pyomo.environ import (
    ConcreteModel, Var, Constraint, ConstraintList, Binary, value as pyo_value
)
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
end_date = start_date + timedelta(days=55)  # 8 weeks

products = sorted(set(e.product_id for e in forecast.entries))
manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

# Categorize dates
dates_range = []
current = start_date
while current <= end_date:
    dates_range.append(current)
    current += timedelta(days=1)

weekday_dates = {i: [] for i in range(5)}  # 0=Mon, 4=Fri
weekend_dates = []

for date_val in dates_range:
    weekday = date_val.weekday()
    labor_day = labor_calendar.get_labor_day(date_val)

    if weekday < 5 and labor_day and labor_day.is_fixed_day:
        weekday_dates[weekday].append(date_val)
    else:
        weekend_dates.append(date_val)

weekday_count = sum(len(dates) for dates in weekday_dates.values())

print("="*80)
print("CORRECT WEEKLY CYCLE IMPLEMENTATION (8-WEEK)")
print("="*80)
print(f"\\nDates: {len(dates_range)} total ({weekday_count} weekdays, {len(weekend_dates)} weekends)")
print(f"Binary variables:")
print(f"  Pattern variables: 25 (5 products × 5 weekdays)")
print(f"  Weekend variables: {5 * len(weekend_dates)} (5 products × {len(weekend_dates)} days)")
print(f"  Total: {25 + 5*len(weekend_dates)} vs {5*len(dates_range)} individual")
print(f"  Reduction: {5*len(dates_range) - (25 + 5*len(weekend_dates))} vars ({100*(1-(25+5*len(weekend_dates))/(5*len(dates_range))):.1f}% fewer)")

# Build model base
from src.optimization.unified_node_model import UnifiedNodeModel

model_obj = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
)

# Build the base Pyomo model
pyomo_model = model_obj.build_model()

print(f"\\nAdding weekly pattern variables and linking constraints...")

# Add weekly pattern binary variables (using Pyomo)
pattern_index = [(prod, wd) for prod in products for wd in range(5)]
pyomo_model.product_weekday_pattern = Var(
    pattern_index,
    within=Binary,
    doc="Weekly production pattern: 1 if product produced on this weekday"
)

print(f"  Created {len(pattern_index)} weekly pattern variables")

# Create ConstraintList for linking constraints (Pyomo best practice)
pyomo_model.weekly_pattern_linking = ConstraintList()

# Add linking constraints for weekday dates
num_linked = 0
for node_id in manufacturing_nodes_list:
    for date_val in dates_range:
        weekday = date_val.weekday()

        # Only link if it's a regular weekday
        if weekday < 5 and date_val not in weekend_dates:
            for product in products:
                # Link: product_produced[node, product, date] == product_weekday_pattern[product, weekday]
                pyomo_model.weekly_pattern_linking.add(
                    pyomo_model.product_produced[node_id, product, date_val] ==
                    pyomo_model.product_weekday_pattern[product, weekday]
                )
                num_linked += 1

print(f"  Added {num_linked} linking constraints")
print(f"  Weekday dates linked to pattern: {weekday_count}")
print(f"  Weekend dates (independent binary): {len(weekend_dates)}")

# Solve weekly cycle model using Pyomo solver directly
print(f"\\nSolving weekly cycle model...")
from pyomo.contrib import appsi

import os

solver = appsi.solvers.Highs()
solver.config.time_limit = 120
solver.config.mip_gap = 0.05

# HiGHS-specific options (CRITICAL for performance)
solver.highs_options['presolve'] = 'on'
solver.highs_options['parallel'] = 'on'
solver.highs_options['threads'] = os.cpu_count() or 4

start = time.time()
results = solver.solve(pyomo_model)
time_weekly = time.time() - start

# Extract objective value
result_weekly_obj = pyo_value(pyomo_model.obj) if hasattr(pyomo_model, 'obj') else None

print(f"\\nWeekly Cycle Results:")
print(f"  Time: {time_weekly:.1f}s")
print(f"  Cost: ${result_weekly_obj:,.0f}")

# Extract pattern
print(f"\\nExtracted weekly pattern:")
for weekday in range(5):
    day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][weekday]
    active_products = []
    for product in products:
        try:
            if pyo_value(pyomo_model.product_weekday_pattern[product, weekday]) > 0.5:
                active_products.append(product[:20])  # Truncate name
        except:
            pass
    print(f"  {day_name}: {len(active_products)} SKUs - {', '.join(active_products) if active_products else 'none'}")

# Extract warmstart for full solve
print(f"\\nExtracting warmstart for full binary solve...")
warmstart = {}
for node_id in manufacturing_nodes_list:
    for product in products:
        for date_val in dates_range:
            key = (node_id, product, date_val)
            if (node_id, product, date_val) in pyomo_model.product_produced:
                try:
                    val = pyo_value(pyomo_model.product_produced[node_id, product, date_val])
                    warmstart[key] = 1 if val > 0.5 else 0
                except:
                    warmstart[key] = 0

num_active = sum(1 for v in warmstart.values() if v == 1)
print(f"  Warmstart: {num_active}/280 active SKUs")

# Final binary solve with warmstart
print(f"\\nFinal binary solve (with weekly pattern warmstart)...")
model_final = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
)

start = time.time()
result_final = model_final.solve(
    solver_name='appsi_highs',
    time_limit_seconds=300,
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

total_time = time_weekly + time_final

print(f"\\n{'='*80}")
print("8-WEEK RESULTS - CORRECT WEEKLY CYCLE")
print(f"{'='*80}")
print(f"Single-phase:               540s timeout, $1,320,057, 25.2% gap")
print(f"Greedy (Phase 6 only):      520s, $1,144,475")
print(f"Weekly cycle + final:       {total_time:.0f}s, ${result_final.objective_value:,.0f}")
print(f"  - Weekly pattern: {time_weekly:.1f}s")
print(f"  - Final binary: {time_final:.1f}s")
print("="*80)
