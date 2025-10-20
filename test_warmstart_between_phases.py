#!/usr/bin/env python3
"""Test if warmstart between greedy phases speeds up later iterations."""

from datetime import timedelta
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
end_date = start_date + timedelta(days=27)

products = sorted(set(e.product_id for e in forecast.entries))
manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

dates_range = []
current = start_date
while current <= end_date:
    dates_range.append(current)
    current += timedelta(days=1)

print("="*80)
print("TEST: Warmstart Impact on Later Phases")
print("="*80)

# ============================================================================
# Phase 1: Solve with 80 fixed, 60 binary (simulating late greedy phase)
# ============================================================================
print("\nPhase 1: 80 fixed, 60 binary (NO warmstart - cold start)")
print("-"*80)

force_pattern_phase1 = {}
for i, (node_id, product, date_val) in enumerate(
    [(n, p, d) for n in manufacturing_nodes_list for p in products for d in dates_range]
):
    force_pattern_phase1[(node_id, product, date_val)] = (i >= 60)  # First 60 binary, rest fixed

model1 = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
    force_sku_pattern=force_pattern_phase1,
)

start_time = time.time()
result1 = model1.solve(solver_name='appsi_highs', time_limit_seconds=90, mip_gap=0.06, tee=False)
time1 = time.time() - start_time

print(f"Results: {time1:.1f}s, ${result1.objective_value:,.0f}, {result1.termination_condition.name if hasattr(result1.termination_condition, 'name') else str(result1.termination_condition)}")

# Extract warmstart hints from Phase 1
print("\nExtracting warmstart from Phase 1...")
warmstart_hints = {}
pyomo_model1 = model1.model

for node_id in manufacturing_nodes_list:
    for product in products:
        for date_val in dates_range:
            if (node_id, product, date_val) in pyomo_model1.production:
                try:
                    qty = pyo_value(pyomo_model1.production[node_id, product, date_val])
                    warmstart_hints[(node_id, product, date_val)] = 1 if qty > 0.01 else 0
                except:
                    warmstart_hints[(node_id, product, date_val)] = 0

num_warmstart = sum(1 for v in warmstart_hints.values() if v == 1)
print(f"  Extracted {len(warmstart_hints)} hints ({num_warmstart} with production)")

# ============================================================================
# Phase 2a: Solve with 70 fixed, 70 binary (NO warmstart)
# ============================================================================
print("\n" + "="*80)
print("Phase 2a: 70 fixed, 70 binary (NO warmstart)")
print("-"*80)

force_pattern_phase2 = {}
for i, (node_id, product, date_val) in enumerate(
    [(n, p, d) for n in manufacturing_nodes_list for p in products for d in dates_range]
):
    force_pattern_phase2[(node_id, product, date_val)] = (i >= 70)  # First 70 binary, rest fixed

model2a = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
    force_sku_pattern=force_pattern_phase2,
)

start_time = time.time()
result2a = model2a.solve(solver_name='appsi_highs', time_limit_seconds=90, mip_gap=0.06, use_warmstart=False, tee=False)
time2a = time.time() - start_time

print(f"Results (NO warmstart): {time2a:.1f}s, ${result2a.objective_value:,.0f}, {result2a.termination_condition.name if hasattr(result2a.termination_condition, 'name') else str(result2a.termination_condition)}")

# ============================================================================
# Phase 2b: Solve with 70 fixed, 70 binary (WITH warmstart from Phase 1)
# ============================================================================
print("\n" + "="*80)
print("Phase 2b: 70 fixed, 70 binary (WITH warmstart from Phase 1)")
print("-"*80)

model2b = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
    force_sku_pattern=force_pattern_phase2,
)

start_time = time.time()
result2b = model2b.solve(solver_name='appsi_highs', time_limit_seconds=90, mip_gap=0.06, use_warmstart=True, warmstart_hints=warmstart_hints, tee=False)
time2b = time.time() - start_time

print(f"Results (WITH warmstart): {time2b:.1f}s, ${result2b.objective_value:,.0f}, {result2b.termination_condition.name if hasattr(result2b.termination_condition, 'name') else str(result2b.termination_condition)}")

# ============================================================================
# COMPARISON
# ============================================================================
print("\n" + "="*80)
print("WARMSTART IMPACT")
print("="*80)
print(f"Phase 2a (no warmstart):   {time2a:.1f}s")
print(f"Phase 2b (with warmstart): {time2b:.1f}s")

if time2b < time2a:
    speedup = time2a / time2b
    time_saved = time2a - time2b
    print(f"\n✅ Warmstart is {speedup:.2f}x faster (saved {time_saved:.1f}s)")
else:
    print(f"\n⚠️  Warmstart didn't help (or made it worse)")

print("\nCONCLUSION:")
if time2b < time2a * 0.8:
    print("  Warmstart provides significant speedup - should be used between phases")
elif time2b < time2a:
    print("  Warmstart provides modest speedup - may be worth using")
else:
    print("  Warmstart doesn't help for this problem structure")
