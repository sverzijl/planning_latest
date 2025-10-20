#!/usr/bin/env python3
"""8-week greedy all-fixed approach."""
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
end_date = start_date + timedelta(days=55)
products = sorted(set(e.product_id for e in forecast.entries))
manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]
dates_range = []
current = start_date
while current <= end_date:
    dates_range.append(current)
    current += timedelta(days=1)

print('8-WEEK GREEDY: All-fixed phases')
fixed_to_zero = set()
phases = []
best_cost = float('inf')
best_phase = None

for iteration in range(1, 8):
    if iteration == 1:
        pattern = None
        use_force_all = True
    else:
        pattern = {(n, p, d): (0 if (n, p, d) in fixed_to_zero else 1)
                   for n in manufacturing_nodes_list for p in products for d in dates_range}
        use_force_all = False

    start = time.time()
    model = UnifiedNodeModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        labor_calendar=labor_calendar, cost_structure=cost_structure,
        start_date=start_date, end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
        force_all_skus_daily=use_force_all, force_sku_pattern=pattern,
    )
    result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.05, tee=False)
    phase_time = time.time() - start

    phases.append({'time': phase_time, 'cost': result.objective_value, 'model': model})
    print(f'Phase {iteration}: {phase_time:.1f}s, ${result.objective_value:,.0f}', end='')

    if result.objective_value < best_cost:
        best_cost = result.objective_value
        best_phase = iteration
        print(' ← BEST')
    else:
        print(f' (+${result.objective_value - best_cost:,.0f}) STOP')
        break

    # Find smallest 20 to fix to 0
    production = {}
    for n in manufacturing_nodes_list:
        for p in products:
            for d in dates_range:
                if (n,p,d) in fixed_to_zero:
                    continue
                if (n,p,d) in model.model.production:
                    try:
                        qty = pyo_value(model.model.production[n,p,d])
                        if qty > 0.01:
                            production[(n,p,d)] = qty
                    except:
                        pass
    if production:
        for key, qty in sorted(production.items(), key=lambda x: x[1])[:20]:
            fixed_to_zero.add(key)

greedy_time = sum(p['time'] for p in phases)

# Extract warmstart from best phase
best_model = phases[best_phase-1]['model']
warmstart = {}
for n in manufacturing_nodes_list:
    for p in products:
        for d in dates_range:
            if (n,p,d) in fixed_to_zero:
                warmstart[(n,p,d)] = 0
            elif (n,p,d) in best_model.model.production:
                try:
                    qty = pyo_value(best_model.model.production[n,p,d])
                    warmstart[(n,p,d)] = 1 if qty > 0.01 else 0
                except:
                    warmstart[(n,p,d)] = 1

# Final binary
print(f'\\nFinal binary (with warmstart)...')
start = time.time()
model_final = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
)
result_final = model_final.solve(solver_name='appsi_highs', time_limit_seconds=300, mip_gap=0.03, use_warmstart=True, warmstart_hints=warmstart, tee=False)
final_time = time.time() - start

print(f'Greedy total: {greedy_time + final_time:.1f}s ({greedy_time:.1f}s greedy + {final_time:.1f}s final)')
print(f'Final cost: ${result_final.objective_value:,.0f}, Gap: {result_final.gap*100:.1f}%' if result_final.gap else f'Final cost: ${result_final.objective_value:,.0f}')
