#!/usr/bin/env python3
"""Detailed validation of demand satisfaction vs inventory consumption.

Properly accounts for ALL flows (arrivals, departures, production) and identifies
which specific cohorts have allocation != consumption mismatch.
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

# Load and solve (same as forensics)
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

print("Building and solving model...")
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

print(f"Solved: {result.termination_condition} in {result.solve_time_seconds:.1f}s\n")

# DETAILED VALIDATION FOR DAY 28
day_28 = planning_end
day_27 = day_28 - timedelta(days=1)

print("="*80)
print(f"DETAILED FLOW ANALYSIS FOR DAY 28 ({day_28})")
print("="*80)

# Extract demand_from_cohort for day 28
print("\n[1] Demand Allocation (demand_from_cohort)...")
demand_by_cohort = {}
total_demand_allocated = 0

for (node, prod, prod_date, demand_date) in model.demand_cohort_index_set:
    if demand_date == day_28:
        val = value(pyomo_model.demand_from_cohort[node, prod, prod_date, demand_date])
        if val > 0.01:
            key = (node, prod, prod_date)
            demand_by_cohort[key] = val
            total_demand_allocated += val

print(f"  Total allocated: {total_demand_allocated:,.0f} units from {len(demand_by_cohort)} cohorts")

# Extract actual inventory flows
print("\n[2] Inventory Flows...")

cohort_inv = solution.get('cohort_inventory', {})

# Get all cohorts that exist on day 27 or day 28
relevant_cohorts = set()
for (n, p, pd, cd, s), qty in cohort_inv.items():
    if cd in [day_27, day_28] and qty > 0.01:
        relevant_cohorts.add((n, p, pd, s))

print(f"  Relevant cohorts: {len(relevant_cohorts)}")

# For each cohort, calculate the flow
flows = []
total_actual_consumption = 0

for (node, prod, prod_date, state) in relevant_cohorts:
    # Get inventory values
    inv_27 = cohort_inv.get((node, prod, prod_date, day_27, state), 0)
    inv_28 = cohort_inv.get((node, prod, prod_date, day_28, state), 0)

    # Calculate change
    change = inv_27 - inv_28

    # Check if this is a demand node
    node_obj = next((n for n in nodes if n.id == node), None)
    is_demand_node = node_obj and node_obj.has_demand_capability()

    # Check if demand exists on day 28 for this node
    has_demand_day28 = (node, prod, day_28) in model.demand

    # Check if cohort can satisfy demand
    in_demand_index = (node, prod, prod_date, day_28) in model.demand_cohort_index_set

    # Get allocated demand for this cohort
    allocated = demand_by_cohort.get((node, prod, prod_date), 0)

    if is_demand_node and has_demand_day28 and in_demand_index and allocated > 0.01:
        # This cohort should be consuming demand
        flows.append({
            'node': node,
            'prod': prod,
            'prod_date': prod_date,
            'state': state,
            'inv_27': inv_27,
            'inv_28': inv_28,
            'change': change,
            'allocated': allocated,
            'gap': allocated - change,
        })
        total_actual_consumption += change

print(f"  Total inventory consumed: {total_actual_consumption:,.0f} units")

# Find gaps
print(f"\n[3] Cohort-Level Gaps...")
gaps_found = [f for f in flows if abs(f['gap']) > 0.01]

if gaps_found:
    print(f"  Found {len(gaps_found)} cohorts with allocation ≠ consumption:")
    for f in gaps_found[:10]:  # Show first 10
        print(f"    {f['node']}/{f['prod']}/{f['prod_date']} state={f['state']}: "
              f"allocated={f['allocated']:.0f}, consumed={f['change']:.0f}, gap={f['gap']:.0f}")

    total_gap = sum(abs(f['gap']) for f in gaps_found)
    print(f"\n  Total gap: {total_gap:,.0f} units")
else:
    print("  ✓ No cohort-level gaps found")

# Overall validation
print(f"\n[4] Overall Validation:")
print(f"  Demand allocated: {total_demand_allocated:,.0f} units")
print(f"  Inventory consumed: {total_actual_consumption:,.0f} units")
print(f"  Difference: {total_demand_allocated - total_actual_consumption:,.0f} units")

if abs(total_demand_allocated - total_actual_consumption) > 100:
    print(f"\n  ❌ MISMATCH CONFIRMED")
else:
    print(f"\n  ✓ Allocation matches consumption")

print("\n" + "="*80)
