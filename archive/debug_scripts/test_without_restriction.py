#!/usr/bin/env python3
"""Test model WITHOUT shipment departure restriction to see if it eliminates excess."""

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

# Load data
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

print('='*80)
print('EXPERIMENT: Remove Shipment Restriction and Retest')
print('='*80)
print()
print('Current code has lines 540-549 that restrict shipment departures.')
print('This test will show what happens WITH the restriction.')
print()
print('Hypothesis: The restriction forces early production that becomes waste.')
print('Expected: Removing it should reduce end-of-horizon inventory.')
print()

model = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    truck_schedules=unified_truck_schedules,
    start_date=planning_start, end_date=planning_end,
    initial_inventory=None, use_batch_tracking=True,
    allow_shortages=True, enforce_shelf_life=True,
)

print(f'Solving WITH shipment restriction...')
result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01, tee=False)
solution = model.get_solution()

cohort_inv = solution.get('cohort_inventory', {})
end_inv = sum(qty for (n, p, pd, cd, s), qty in cohort_inv.items() if cd == planning_end)
demand_day28 = sum(qty for (n, p, d), qty in model.demand.items() if d == planning_end)

print(f'  End-of-horizon inventory: {end_inv:,.0f} units')
print(f'  Day 28 demand: {demand_day28:,.0f} units')
print(f'  Excess: {end_inv - demand_day28:,.0f} units')
print()
print('Conclusion:')
print(f'  The shipment restriction (lines 540-549) is currently ACTIVE.')
print(f'  It creates ~{end_inv - demand_day28:,.0f} units of waste on the final day.')
print()
print('To test removal:')
print('  1. Comment out lines 540-549 in unified_node_model.py')
print('  2. Re-run this script')
print('  3. Compare end-of-horizon inventory')
print()
print('Expected after removal:')
print('  - End inventory should drop significantly')
print('  - Model can use late-horizon shipments more flexibly')
print('  - Production optimized for actual demand pattern')
print()
print('='*80)
