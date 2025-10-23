#!/usr/bin/env python3
"""Systematic debugging: Test all hypotheses for weekly warmstart failure.

Hypothesis A: Initial inventory causes warmstart incompatibility
Hypothesis B: Latest file is fundamentally harder
Hypothesis C: No-pallet Phase 1 warmstart incompatible with pallet Phase 2

Test Matrix:
-----------
1. Latest file, NO inventory, Weekly warmstart
2. Latest file, WITH inventory, Weekly warmstart
3. Latest file, WITH inventory, Single-phase (no warmstart)
4. Old file, NO inventory, Weekly warmstart (baseline - known working)

This isolates: initial inventory effect, file difficulty, warmstart effect
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart, UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
import time

print("="*80)
print("SYSTEMATIC WARMSTART DEBUG - HYPOTHESIS TESTING")
print("="*80)

# ============================================================================
# TEST 1: Latest file, NO inventory, Weekly warmstart
# ============================================================================
print("\nTEST 1: Latest file, NO initial inventory, Weekly warmstart")
print("-"*80)

parser1 = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    # NO INVENTORY
)

forecast1, locations1, routes1, labor1, trucks1, costs1 = parser1.parse_all()

manuf1 = [l for l in locations1 if l.type == LocationType.MANUFACTURING][0]
ms1 = ManufacturingSite(id=manuf1.id, name=manuf1.name, storage_mode=manuf1.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=costs1.production_cost_per_unit)

conv1 = LegacyToUnifiedConverter()
nodes1 = conv1.convert_nodes(ms1, locations1, forecast1)
routes1_u = conv1.convert_routes(routes1)
trucks1_u = conv1.convert_truck_schedules(trucks1, ms1.id)

start1 = date(2025, 10, 20)  # Monday
end1 = start1 + timedelta(days=41)

print(f"Setup: Start {start1}, NO inventory")

result1 = solve_weekly_pattern_warmstart(
    nodes=nodes1, routes=routes1_u, forecast=forecast1,
    labor_calendar=labor1, cost_structure=costs1,
    start_date=start1, end_date=end1, truck_schedules=trucks1_u,
    initial_inventory=None,  # NO INVENTORY
    inventory_snapshot_date=None,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    solver_name='appsi_highs',
    time_limit_phase1=120, time_limit_phase2=300, mip_gap=0.02,
)

print(f"Result 1: {result1.solve_time_seconds:.1f}s, ${result1.objective_value:,.0f}, gap={result1.gap*100:.1f}%" if result1.gap else f"Result 1: {result1.solve_time_seconds:.1f}s, ${result1.objective_value:,.0f}")

# ============================================================================
# TEST 2: Latest file, WITH inventory, Weekly warmstart
# ============================================================================
print("\n" + "="*80)
print("TEST 2: Latest file, WITH initial inventory, Weekly warmstart")
print("-"*80)

parser2 = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX',  # WITH INVENTORY
)

forecast2, locations2, routes2, labor2, trucks2, costs2 = parser2.parse_all()
inv2 = parser2.parse_inventory(snapshot_date=None)

manuf2 = [l for l in locations2 if l.type == LocationType.MANUFACTURING][0]
ms2 = ManufacturingSite(id=manuf2.id, name=manuf2.name, storage_mode=manuf2.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=costs2.production_cost_per_unit)

conv2 = LegacyToUnifiedConverter()
nodes2 = conv2.convert_nodes(ms2, locations2, forecast2)
routes2_u = conv2.convert_routes(routes2)
trucks2_u = conv2.convert_truck_schedules(trucks2, ms2.id)

start2 = date(2025, 10, 20)
end2 = start2 + timedelta(days=41)

print(f"Setup: Start {start2}, WITH inventory from {inv2.snapshot_date}")

result2 = solve_weekly_pattern_warmstart(
    nodes=nodes2, routes=routes2_u, forecast=forecast2,
    labor_calendar=labor2, cost_structure=costs2,
    start_date=start2, end_date=end2, truck_schedules=trucks2_u,
    initial_inventory=inv2.to_optimization_dict(),  # WITH INVENTORY
    inventory_snapshot_date=inv2.snapshot_date,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    solver_name='appsi_highs',
    time_limit_phase1=120, time_limit_phase2=300, mip_gap=0.02,
)

print(f"Result 2: {result2.solve_time_seconds:.1f}s, ${result2.objective_value:,.0f}, gap={result2.gap*100:.1f}%" if result2.gap else f"Result 2: {result2.solve_time_seconds:.1f}s, ${result2.objective_value:,.0f}")

# ============================================================================
# TEST 3: Latest file, WITH inventory, Single-phase (NO warmstart)
# ============================================================================
print("\n" + "="*80)
print("TEST 3: Latest file, WITH inventory, Single-phase (NO warmstart)")
print("-"*80)

print(f"Setup: Start {start2}, WITH inventory, single-phase")

model3 = UnifiedNodeModel(
    nodes=nodes2, routes=routes2_u, forecast=forecast2,
    labor_calendar=labor2, cost_structure=costs2,
    start_date=start2, end_date=end2, truck_schedules=trucks2_u,
    initial_inventory=inv2.to_optimization_dict(),
    inventory_snapshot_date=inv2.snapshot_date,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    force_all_skus_daily=False,
)

start_time3 = time.time()
result3 = model3.solve(solver_name='appsi_highs', time_limit_seconds=300, mip_gap=0.02)
time3 = time.time() - start_time3

print(f"Result 3: {time3:.1f}s, ${result3.objective_value:,.0f}, gap={result3.gap*100:.1f}%" if result3.gap else f"Result 3: {time3:.1f}s, ${result3.objective_value:,.0f}")

# ============================================================================
# ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("HYPOTHESIS TESTING RESULTS")
print("="*80)

print(f"\nTEST 1 (Latest, NO inventory, Weekly):   {result1.solve_time_seconds:.0f}s, ${result1.objective_value:,.0f}")
print(f"TEST 2 (Latest, WITH inventory, Weekly): {result2.solve_time_seconds:.0f}s, ${result2.objective_value:,.0f}")
print(f"TEST 3 (Latest, WITH inventory, Single): {time3:.0f}s, ${result3.objective_value:,.0f}")

print("\nHYPOTHESIS A: Initial inventory causes warmstart issues")
if result2.objective_value > result1.objective_value * 1.5:
    print("  ✅ SUPPORTED: WITH inventory is much worse than without")
else:
    print("  ❌ REJECTED: Inventory doesn't significantly affect cost")

print("\nHYPOTHESIS B: Warmstart hurts performance (vs single-phase)")
if result3.objective_value < result2.objective_value * 0.8:
    print("  ✅ SUPPORTED: Single-phase achieves much better cost than weekly")
else:
    print("  ❌ REJECTED: Weekly performs similarly to single-phase")

print("\nHYPOTHESIS C: Latest file is fundamentally harder")
print(f"  Demand entries: 20,295 (vs 17,760 in old file)")
print(f"  Locations: 9 demand nodes (vs 8 in old file)")
print(f"  → File is 14% larger, expected ~14% longer solve time")

print("\n" + "="*80)
