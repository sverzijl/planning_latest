#!/usr/bin/env python3
"""Analyze if excess inventory exists throughout the horizon or just accumulates on day 28."""

import sys
from datetime import timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

# Quick solve
data_dir = Path('data/examples')
parser = MultiFileParser(str(data_dir / 'Gfree Forecast.xlsm'), str(data_dir / 'Network_Config.xlsx'), None)
forecast, locations, _, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

converter = LegacyToUnifiedConverter()
manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(list(parser.parse_routes()))
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

planning_start = min(e.forecast_date for e in forecast.entries)
planning_end = planning_start + timedelta(days=27)

model = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    truck_schedules=unified_truck_schedules,
    start_date=planning_start, end_date=planning_end,
    initial_inventory=None, use_batch_tracking=True,
    allow_shortages=True, enforce_shelf_life=True,
)

print("Solving...")
result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01, tee=False)
solution = model.get_solution()
print(f"Solved in {result.solve_time_seconds:.1f}s\n")

print('='*80)
print('DAILY EXCESS INVENTORY ANALYSIS')
print('='*80)

cohort_inv = solution.get('cohort_inventory', {})
cohort_demand = solution.get('cohort_demand_consumption', {})

# For each day, calculate total inventory vs demand consumed
print(f'\nDay-by-day breakdown (last 14 days):')
print(f'  Date          Inventory    Consumed    Demand      Excess')
print(f'  -----------  ----------  ----------  ----------  ----------')

for day_offset in range(14, 28):
    curr_date = planning_start + timedelta(days=day_offset)

    # Total inventory on this day
    inv_total = sum(qty for (n, p, pd, cd, s), qty in cohort_inv.items() if cd == curr_date)

    # Demand consumed on this day
    consumed = sum(qty for (n, p, pd, dd), qty in cohort_demand.items() if dd == curr_date)

    # Actual demand on this day
    demand_qty = sum(qty for (n, p, d), qty in model.demand.items() if d == curr_date)

    # Excess = inventory that exists but isn't being consumed for today's demand
    # Note: some inventory is "pipeline" for future days
    excess = inv_total - consumed

    print(f'  {curr_date}  {inv_total:10,.0f}  {consumed:10,.0f}  {demand_qty:10,.0f}  {excess:10,.0f}')

print(f'\nPattern Analysis:')
print(f'  - If excess grows over time: systematic overproduction')
print(f'  - If excess is constant: pipeline inventory for multi-echelon distribution')
print(f'  - If excess jumps on final day: end-of-horizon artifact')

print('\n' + '='*80)
