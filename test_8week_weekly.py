#!/usr/bin/env python3
"""8-week weekly cycle approach."""
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

print('8-WEEK WEEKLY CYCLE')

# Create weekly pattern (alternate 2 SKUs per weekday)
weekday_to_product = {
    0: [products[0], products[1]], 1: [products[1], products[2]],
    2: [products[2], products[3]], 3: [products[3], products[4]],
    4: [products[0], products[4]],
}

pattern = {}
for node_id in manufacturing_nodes_list:
    for date_val in dates_range:
        weekday = date_val.weekday()
        if weekday < 5:
            for product in products:
                key = (node_id, product, date_val)
                pattern[key] = 1 if (weekday in weekday_to_product and product in weekday_to_product[weekday]) else 0

num_binary = 5 * len(dates_range) - len([v for v in pattern.values() if v in [0,1]])
print(f'Phase 1: Weekly pattern ({num_binary} binary for weekends)')

start = time.time()
model_weekly = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False, force_sku_pattern=pattern,
)
result_weekly = model_weekly.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.05, tee=False)
time_weekly = time.time() - start

print(f'  {time_weekly:.1f}s, ${result_weekly.objective_value:,.0f}')

# Extract warmstart
warmstart = {}
for n in manufacturing_nodes_list:
    for p in products:
        for d in dates_range:
            key = (n,p,d)
            if key in pattern:
                warmstart[key] = pattern[key]
            elif (n,p,d) in model_weekly.model.production:
                try:
                    qty = pyo_value(model_weekly.model.production[n,p,d])
                    warmstart[key] = 1 if qty > 0.01 else 0
                except:
                    warmstart[key] = 0

# Final binary
print(f'Phase 2: Final binary (with warmstart)')
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
time_final = time.time() - start

print(f'  {time_final:.1f}s, ${result_final.objective_value:,.0f}')
print(f'\\nWeekly total: {time_weekly + time_final:.1f}s')
