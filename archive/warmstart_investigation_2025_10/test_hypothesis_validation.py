#!/usr/bin/env python3
"""Systematic hypothesis testing - validate claims with evidence.

H1: Phase 2 cost explosion is from shortage penalties (not warmstart issues)
H2: Warmstart hurts performance (Phase 2 better WITHOUT warmstart)
H3: 6-week is just too hard (single-phase also struggles)
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart, UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

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

start_date = date(2025, 10, 20)
end_date = start_date + timedelta(days=41)  # 6 weeks

print("="*80)
print("HYPOTHESIS VALIDATION - EVIDENCE-BASED TESTING")
print("="*80)

# ============================================================================
# H1: Check if Phase 2 has shortage penalties
# ============================================================================
print("\n" + "="*80)
print("H1: Phase 2 cost explosion is from SHORTAGE PENALTIES")
print("="*80)

result_warmstart = solve_weekly_pattern_warmstart(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=inventory_snapshot.to_optimization_dict() if inventory_snapshot else None,
    inventory_snapshot_date=inventory_snapshot.snapshot_date if inventory_snapshot else None,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    solver_name='appsi_highs',
    time_limit_phase1=180,
    time_limit_phase2=400,
    mip_gap=0.02,
)

print(f"\nPhase 2 (with warmstart) Results:")
print(f"  Cost: ${result_warmstart.objective_value:,.2f}")
print(f"  Time: {result_warmstart.solve_time_seconds:.1f}s")
print(f"  Gap: {result_warmstart.gap*100:.1f}%" if result_warmstart.gap else "  Gap: 0%")

# Extract shortage information
if hasattr(result_warmstart, 'production_schedule') and result_warmstart.production_schedule:
    total_shortage = 0
    for sched in result_warmstart.production_schedule:
        if hasattr(sched, 'shortage_units'):
            total_shortage += sched.shortage_units or 0

    shortage_cost = total_shortage * (cost_structure.shortage_penalty_per_unit or 10000)
    shortage_pct = (shortage_cost / result_warmstart.objective_value * 100) if result_warmstart.objective_value > 0 else 0

    print(f"\nShortage Analysis:")
    print(f"  Total shortage: {total_shortage:,.0f} units")
    print(f"  Shortage cost: ${shortage_cost:,.2f}")
    print(f"  % of total cost: {shortage_pct:.1f}%")

    if shortage_pct > 50:
        print(f"  ✅ H1 CONFIRMED: Shortages explain {shortage_pct:.0f}% of cost explosion")
    else:
        print(f"  ❌ H1 REJECTED: Shortages only {shortage_pct:.0f}% of cost")
else:
    print(f"  ⚠️  Cannot extract shortage data from result")

# ============================================================================
# H2: Does warmstart help or hurt?
# ============================================================================
print("\n" + "="*80)
print("H2: Warmstart HURTS performance (better without it)")
print("="*80)

print("\nTesting Phase 2 WITHOUT warmstart (cold start)...")

model_no_warmstart = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=inventory_snapshot.to_optimization_dict() if inventory_snapshot else None,
    inventory_snapshot_date=inventory_snapshot.snapshot_date if inventory_snapshot else None,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
)

result_no_warmstart = model_no_warmstart.solve(
    solver_name='appsi_highs',
    time_limit_seconds=400,
    mip_gap=0.02,
)

print(f"\nPhase 2 (NO warmstart) Results:")
print(f"  Cost: ${result_no_warmstart.objective_value:,.2f}")
print(f"  Time: {result_no_warmstart.solve_time_seconds:.1f}s")
print(f"  Gap: {result_no_warmstart.gap*100:.1f}%" if result_no_warmstart.gap else "  Gap: 0%")

print(f"\nComparison:")
print(f"  With warmstart:    ${result_warmstart.objective_value:,.0f}, gap={result_warmstart.gap*100:.1f}%")
print(f"  Without warmstart: ${result_no_warmstart.objective_value:,.0f}, gap={result_no_warmstart.gap*100:.1f}%")

if result_no_warmstart.objective_value < result_warmstart.objective_value * 0.9:
    print(f"  ✅ H2 CONFIRMED: No warmstart is {result_warmstart.objective_value/result_no_warmstart.objective_value:.1f}× better!")
    print(f"     Warmstart is HURTING performance")
elif result_warmstart.objective_value < result_no_warmstart.objective_value * 0.9:
    print(f"  ❌ H2 REJECTED: Warmstart is {result_no_warmstart.objective_value/result_warmstart.objective_value:.1f}× better")
    print(f"     Warmstart is HELPING performance")
else:
    print(f"  ⚠️  INCONCLUSIVE: Both similar, warmstart has minimal effect")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("EVIDENCE-BASED CONCLUSIONS")
print("="*80)

print("\nValidated findings:")
print("1. Shortage analysis: [See H1 results above]")
print("2. Warmstart impact: [See H2 results above]")
print("\nNext steps depend on validated hypotheses.")
