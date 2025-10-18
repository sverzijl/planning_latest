#!/usr/bin/env python3
"""Trace where the 6,535 excess units came from."""

import sys
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from pyomo.environ import value
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

# Load
data_dir = Path('data/examples')
parser = MultiFileParser(str(data_dir / 'Gfree Forecast.xlsm'), str(data_dir / 'Network_Config.xlsx'), None)
forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

converter = LegacyToUnifiedConverter()
manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

planning_start = min(e.forecast_date for e in forecast.entries)
planning_end = planning_start + timedelta(days=27)

# Solve
print("Solving model...")
model = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    truck_schedules=unified_truck_schedules,
    start_date=planning_start, end_date=planning_end,
    initial_inventory=None, use_batch_tracking=True,
    allow_shortages=True, enforce_shelf_life=True,
)

result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01, tee=False)
solution = model.get_solution()

print(f"Solved in {result.solve_time_seconds:.1f}s\n")

print('='*80)
print('TRACE: Production Source of Day 28 Inventory')
print('='*80)

cohort_inv = solution.get('cohort_inventory', {})

# Extract day 28 inventory by production date
day_28_inv_by_prod_date = defaultdict(float)
for (node, prod, prod_date, curr_date, state), qty in cohort_inv.items():
    if curr_date == planning_end and qty > 0.01:
        day_28_inv_by_prod_date[prod_date] += qty

# Extract demand consumption for day 28 by production date
demand_consumed_by_prod_date = defaultdict(float)
for (n, p, pd, dd), qty in solution.get('cohort_demand_consumption', {}).items():
    if dd == planning_end and qty > 0.01:
        demand_consumed_by_prod_date[pd] += qty

total_inv = sum(day_28_inv_by_prod_date.values())
total_consumed = sum(demand_consumed_by_prod_date.values())

print(f'\nDay 28 totals:')
print(f'  Inventory: {total_inv:,.0f} units')
print(f'  Consumed:  {total_consumed:,.0f} units')
print(f'  Excess:    {total_inv - total_consumed:,.0f} units')

print(f'\nBreakdown by production date:')
print(f'  Prod Date     Inventory    Consumed      Excess')
print(f'  -----------  ----------  ----------  ----------')

all_dates = sorted(set(day_28_inv_by_prod_date.keys()) | set(demand_consumed_by_prod_date.keys()))
for prod_date in all_dates:
    inv = day_28_inv_by_prod_date.get(prod_date, 0)
    consumed = demand_consumed_by_prod_date.get(prod_date, 0)
    excess = inv - consumed
    if inv > 0.01 or consumed > 0.01:
        age = (planning_end - prod_date).days
        print(f'  {prod_date}  {inv:10,.0f}  {consumed:10,.0f}  {excess:10,.0f}  (age {age}d)')

print(f'\nConclusion:')
excess = total_inv - total_consumed
if excess > 100:
    print(f'  {excess:,.0f} units cost ${excess * 5:,.0f} to produce')
    print(f'  They satisfy ZERO demand (model has perfect foresight)')
    print(f'  This violates cost minimization')
    print(f'  → CONSTRAINT BUG forcing unnecessary production')

print('\n' + '='*80)
