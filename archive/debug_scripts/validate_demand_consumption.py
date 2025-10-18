#!/usr/bin/env python3
"""Validate that demand_from_cohort matches actual inventory consumption.

Tests user's hypothesis: Demand might be "satisfied" on paper but inventory not consumed.
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from pyomo.environ import value

# Load and solve model (same as forensics)
data_dir = Path("data/examples")
parser = MultiFileParser(
    forecast_file=str(data_dir / "Gfree Forecast.xlsm"),
    network_file=str(data_dir / "Network_Config.xlsx"),
    inventory_file=None,
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

converter = LegacyToUnifiedConverter()
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

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

print("="*80)
print("DEMAND-CONSUMPTION VALIDATION")
print("="*80)

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
pyomo_model = model.model

print(f"\nModel solved: {result.termination_condition} in {result.solve_time_seconds:.1f}s")

# Extract demand_from_cohort values for day 28
print(f"\n[1] Extracting demand_from_cohort for day 28 ({planning_end})...")

demand_satisfied_day28 = 0.0
demand_satisfied_by_node = defaultdict(float)

for (node, prod, prod_date, demand_date) in model.demand_cohort_index_set:
    if demand_date == planning_end:
        try:
            val = value(pyomo_model.demand_from_cohort[node, prod, prod_date, demand_date])
            if val > 0.01:
                demand_satisfied_day28 += val
                demand_satisfied_by_node[node] += val
        except:
            pass

print(f"  Total demand satisfied (from demand_from_cohort): {demand_satisfied_day28:,.0f} units")
print(f"\n  By location:")
for node in sorted(demand_satisfied_by_node.keys(), key=lambda x: demand_satisfied_by_node[x], reverse=True):
    print(f"    {node}: {demand_satisfied_by_node[node]:,.0f} units")

# Extract actual demand on day 28
demand_day28 = sum(qty for (n, p, d), qty in model.demand.items() if d == planning_end)
print(f"\n  Actual demand on day 28: {demand_day28:,.0f} units")

# Extract inventory change day 27 → day 28
print(f"\n[2] Calculating actual inventory consumption...")

cohort_inv = solution.get('cohort_inventory', {})

inv_day_27 = sum(qty for (n, p, pd, cd, s), qty in cohort_inv.items() if cd == planning_end - timedelta(days=1))
inv_day_28 = sum(qty for (n, p, pd, cd, s), qty in cohort_inv.items() if cd == planning_end)

# Calculate what was consumed (inv decrease) accounting for production/arrivals/departures
# Simplified: just look at inventory change
inventory_decrease = inv_day_27 - inv_day_28

print(f"  Inventory day 27: {inv_day_27:,.0f} units")
print(f"  Inventory day 28: {inv_day_28:,.0f} units")
print(f"  Inventory decrease: {inventory_decrease:,.0f} units")

# Check for production/arrivals on day 28 that would increase inventory
prod_day_28 = sum(qty for (d, p), qty in solution.get('production_by_date_product', {}).items() if d == planning_end)
print(f"  Production day 28: {prod_day_28:,.0f} units")

# Net consumption = decrease + production
net_consumption = inventory_decrease + prod_day_28
print(f"  Net consumption (decrease + prod): {net_consumption:,.0f} units")

# THE TEST
print(f"\n[3] Validation:")
print(f"  Demand satisfied (demand_from_cohort):  {demand_satisfied_day28:,.0f} units")
print(f"  Inventory consumed (balance equation): {net_consumption:,.0f} units")
print(f"  Difference: {demand_satisfied_day28 - net_consumption:,.0f} units")

if abs(demand_satisfied_day28 - net_consumption) > 100:
    print(f"\n  ❌ BUG CONFIRMED: Demand satisfied but inventory not consumed!")
    print(f"     This explains the {inv_day_28:,.0f} units of excess inventory")
else:
    print(f"\n  ✓ Demand satisfaction and consumption match")
    print(f"     Excess inventory has a different cause")

print("\n" + "="*80)
