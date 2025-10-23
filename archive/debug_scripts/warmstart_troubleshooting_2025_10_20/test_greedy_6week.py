#!/usr/bin/env python3
"""Test greedy fixing on 6-week horizon - all phases have 0 binary vars (all fixed to 0 or 1)."""

from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from pyomo.environ import value as pyo_value
import time

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
end_date = start_date + timedelta(days=41)

products = sorted(set(e.product_id for e in forecast.entries))
manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

dates_range = []
current = start_date
while current <= end_date:
    dates_range.append(current)
    current += timedelta(days=1)

print("="*80)
print("GREEDY FIXING: 6-WEEK (ALL PHASES HAVE 0 BINARY VARS)")
print("="*80)

fixed_to_zero = set()
phase_history = []
best_cost = float('inf')
best_phase = None

for iteration in range(1, 11):
    print(f"\\nPHASE {iteration}: {len(fixed_to_zero)} fixed to 0, {len(products)*len(dates_range)-len(fixed_to_zero)} fixed to 1 → 0 binary")

    if iteration == 1:
        use_force_all = True
        force_pattern = None
    else:
        use_force_all = False
        force_pattern = {}
        for node_id in manufacturing_nodes_list:
            for product in products:
                for date_val in dates_range:
                    key = (node_id, product, date_val)
                    force_pattern[key] = 0 if key in fixed_to_zero else 1

    start = time.time()
    model = UnifiedNodeModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        labor_calendar=labor_calendar, cost_structure=cost_structure,
        start_date=start_date, end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
        force_all_skus_daily=use_force_all,
        force_sku_pattern=force_pattern,
    )
    result = model.solve(solver_name='appsi_highs', time_limit_seconds=90, mip_gap=0.05, tee=False)
    phase_time = time.time() - start

    print(f"  {phase_time:.1f}s, \${result.objective_value:,.0f}", end="")

    phase_history.append({'iteration': iteration, 'time': phase_time, 'cost': result.objective_value, 'model': model})

    if result.objective_value < best_cost:
        best_cost = result.objective_value
        best_phase = iteration
        print(" ← BEST")
    else:
        print(f" (+\${result.objective_value - best_cost:,.0f}) STOP")
        break

    # Find 20 smallest to fix to 0
    pyomo_model = model.model
    production = {}
    for node_id in manufacturing_nodes_list:
        for product in products:
            for date_val in dates_range:
                key = (node_id, product, date_val)
                if key in fixed_to_zero:
                    continue
                if (node_id, product, date_val) in pyomo_model.production:
                    try:
                        qty = pyo_value(pyomo_model.production[node_id, product, date_val])
                        if qty > 0.01:
                            production[key] = qty
                    except:
                        pass

    if production:
        for key, qty in sorted(production.items(), key=lambda x: x[1])[:20]:
            fixed_to_zero.add(key)

greedy_total = sum(p['time'] for p in phase_history)
print(f"\\nGreedy phases total: {greedy_total:.1f}s")
print(f"Best: Phase {best_phase}, \${best_cost:,.0f}")
print(f"Estimated final (with 200s binary solve): {greedy_total + 200:.1f}s")
