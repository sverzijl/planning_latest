#!/usr/bin/env python3
"""Test pallet warmstart fix: Phase 2 should now get pallet variable initialization.

Expected results:
- Phase 1: ~45-71s, optimal
- Phase 2: <250s (was 400s timeout), <10% gap (was 73%), cost similar to Phase 1 (was 3-5× worse)
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

print("="*80)
print("PALLET WARMSTART FIX VALIDATION TEST")
print("="*80)

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX',
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
inventory_snapshot = parser.parse_inventory(snapshot_date=None)

manuf_loc = [l for l in locations if l.type == LocationType.MANUFACTURING][0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_trucks = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

# Test 6-week horizon (42 days)
start_date = date(2025, 10, 20)  # Monday
end_date = start_date + timedelta(days=41)

print(f"\nTest Configuration:")
print(f"  Horizon: {start_date} to {end_date} (42 days, 6 weeks)")
print(f"  Initial inventory: {inventory_snapshot.snapshot_date if inventory_snapshot else 'None'}")
print(f"  Solver: HiGHS (APPSI)")
print(f"  MIP gap: 2%")
print(f"  Time limits: Phase 1=180s, Phase 2=400s")
print("="*80)

result = solve_weekly_pattern_warmstart(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=inventory_snapshot.to_optimization_dict() if inventory_snapshot else None,
    inventory_snapshot_date=inventory_snapshot.snapshot_date if inventory_snapshot else None,
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
    solver_name='appsi_highs',
    time_limit_phase1=180,
    time_limit_phase2=400,
    mip_gap=0.02,
)

print("\n" + "="*80)
print("VALIDATION RESULTS")
print("="*80)

# Extract phase times and costs from metadata
phase1_time = result.metadata.get('phase1_time', 0) if result.metadata else 0
phase2_time = result.metadata.get('phase2_time', 0) if result.metadata else 0
phase1_cost = result.metadata.get('phase1_cost', 0) if result.metadata else 0
phase2_cost = result.objective_value

print(f"\nPhase 1:")
print(f"  Time: {phase1_time:.1f}s")
print(f"  Cost: ${phase1_cost:,.2f}")

print(f"\nPhase 2:")
print(f"  Time: {phase2_time:.1f}s")
print(f"  Cost: ${phase2_cost:,.2f}")
if result.gap:
    print(f"  Gap: {result.gap*100:.2f}%")
print(f"  Status: {result.termination_condition.name if hasattr(result.termination_condition, 'name') else str(result.termination_condition)}")

print(f"\nTotal: {result.solve_time_seconds:.1f}s")

# Validation checks
print("\n" + "="*80)
print("VALIDATION CHECKS")
print("="*80)

checks_passed = 0
checks_total = 4

# Check 1: Phase 2 time < 250s
if phase2_time < 250:
    print("✅ CHECK 1: Phase 2 time < 250s ({:.1f}s)".format(phase2_time))
    checks_passed += 1
else:
    print("❌ CHECK 1: Phase 2 time >= 250s ({:.1f}s) - EXPECTED <250s".format(phase2_time))

# Check 2: Gap < 10%
if result.gap and result.gap < 0.10:
    print("✅ CHECK 2: MIP gap < 10% ({:.2f}%)".format(result.gap*100))
    checks_passed += 1
elif not result.gap:
    print("✅ CHECK 2: Optimal solution (0% gap)")
    checks_passed += 1
else:
    print("❌ CHECK 2: MIP gap >= 10% ({:.2f}%) - EXPECTED <10%".format(result.gap*100))

# Check 3: Cost ratio reasonable (Phase 2 within 2× of Phase 1)
if phase1_cost > 0:
    cost_ratio = phase2_cost / phase1_cost
    if cost_ratio < 2.0:
        print("✅ CHECK 3: Phase 2 cost within 2× of Phase 1 ({:.1f}×)".format(cost_ratio))
        checks_passed += 1
    else:
        print("❌ CHECK 3: Phase 2 cost {:.1f}× worse than Phase 1 - EXPECTED <2×".format(cost_ratio))
else:
    print("⚠️  CHECK 3: Cannot validate (Phase 1 cost = 0)")
    checks_total -= 1

# Check 4: Solution found (not timeout with no solution)
if result.success or (result.gap and result.gap < 1.0):
    print("✅ CHECK 4: Solution found (success={})".format(result.success))
    checks_passed += 1
else:
    print("❌ CHECK 4: No solution found - timeout or infeasible")

print("\n" + "="*80)
if checks_passed == checks_total:
    print("✅ ALL CHECKS PASSED ({}/{})".format(checks_passed, checks_total))
    print("Pallet warmstart fix is working correctly!")
else:
    print("⚠️  SOME CHECKS FAILED ({}/{})".format(checks_passed, checks_total))
    print("Pallet warmstart may need further investigation")
print("="*80)
