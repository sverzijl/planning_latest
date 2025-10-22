#!/usr/bin/env python3
"""Test: APPSI Warmstart with Same Model Instance (RECOMMENDED APPROACH)

Strategy:
1. Build ONE model instance
2. Add weekly pattern constraints
3. Solve with pattern (~20s)
4. DEACTIVATE pattern constraints (don't rebuild model)
5. Re-solve (APPSI should automatically hot-start from previous solution)

Expected: APPSI's persistent solver connection enables automatic hot-start
without explicit .set_value() calls. This is the recommended pattern.
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

import pyomo.environ as pyo
from pyomo.contrib import appsi


def add_weekly_pattern_constraints(model, products, weekday_dates_lists, manufacturing_nodes_list):
    """Add weekly pattern constraints to existing model.

    Returns list of constraint objects for later deactivation.
    """
    print("\nAdding weekly pattern constraints...")

    # Create pattern variables for ALL 4 weeks
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)

    # Link ALL production dates to pattern
    model.weekly_pattern_linking = pyo.ConstraintList()
    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                for date_val in weekday_dates_lists[weekday_idx]:
                    if (node_id, product, date_val) in model.product_produced:
                        model.weekly_pattern_linking.add(
                            model.product_produced[node_id, product, date_val] ==
                            model.product_weekday_pattern[product, weekday_idx]
                        )

    # Deactivate all changeover constraints (pattern handles it)
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()

    print(f"  Added {len(pattern_index)} pattern variables")
    print(f"  Added {len(model.weekly_pattern_linking)} linking constraints")

    return model.weekly_pattern_linking


def analyze_solution(model, products, dates_range, manufacturing_nodes_list, phase_name):
    """Analyze which SKUs are produced when."""
    print(f"\n{phase_name} SOLUTION ANALYSIS:")

    production_days = {prod: 0 for prod in products}

    for node_id in manufacturing_nodes_list:
        for product in products:
            for date_val in dates_range:
                if (node_id, product, date_val) in model.product_produced:
                    val = pyo.value(model.product_produced[node_id, product, date_val])
                    if val and val > 0.5:
                        production_days[product] += 1

    print(f"\nProduction days per product (out of {len(dates_range)} days):")
    for product, days in sorted(production_days.items()):
        pct = (days / len(dates_range)) * 100
        print(f"  {product}: {days} days ({pct:.1f}%)")

    all_products_daily = all(days == len(dates_range) for days in production_days.values())
    return production_days, all_products_daily


def main():
    print("="*80)
    print("TEST: APPSI SAME-INSTANCE WARMSTART (RECOMMENDED APPROACH)")
    print("="*80)
    print("\nStrategy: Solve → Deactivate constraints → Re-solve same instance")
    print("Expected: APPSI automatically hot-starts from previous solution\n")

    # Load data
    print("="*80)
    print("LOADING DATA")
    print("="*80)

    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure_base = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure_base.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # 4-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)

    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    # Build date lists
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    weekday_dates_lists = {i: [] for i in range(5)}
    for date_val in dates_range:
        weekday = date_val.weekday()
        labor_day = labor_calendar.get_labor_day(date_val)
        if weekday < 5 and labor_day and labor_day.is_fixed_day:
            weekday_dates_lists[weekday].append(date_val)

    # Configure with staleness penalty
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # BUILD SINGLE MODEL INSTANCE
    print("\n" + "="*80)
    print("BUILD SINGLE MODEL INSTANCE")
    print("="*80)

    print("\nCreating UnifiedNodeModel...")
    model_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,
    )

    print("\nBuilding Pyomo model...")
    build_start = time.time()
    model = model_obj.build_model()
    build_time = time.time() - build_start
    print(f"Model built in {build_time:.1f}s")

    # Add weekly pattern constraints to the model
    pattern_constraints = add_weekly_pattern_constraints(
        model, products, weekday_dates_lists, manufacturing_nodes_list
    )

    # Create APPSI solver (persistent connection)
    print("\nCreating APPSI solver (persistent connection)...")
    solver = appsi.solvers.Highs()
    solver.config.time_limit = 300  # 5 minutes
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = True  # See solver output

    # PHASE 1: Solve with pattern
    print("\n" + "="*80)
    print("PHASE 1: SOLVE WITH WEEKLY PATTERN")
    print("="*80)

    phase1_start = time.time()
    result_phase1 = solver.solve(model)
    phase1_time = time.time() - phase1_start

    phase1_cost = pyo.value(model.obj)
    print(f"\nPhase 1 Results:")
    print(f"  Solve time: {phase1_time:.1f}s")
    print(f"  Objective: ${phase1_cost:,.2f}")
    print(f"  Termination: {result_phase1.termination_condition}")

    # Analyze pattern solution
    prod_days_phase1, all_daily_phase1 = analyze_solution(
        model, products, dates_range, manufacturing_nodes_list, "PHASE 1"
    )

    # PHASE 2: Deactivate pattern, re-solve
    print("\n" + "="*80)
    print("PHASE 2: DEACTIVATE PATTERN, RE-SOLVE SAME INSTANCE")
    print("="*80)

    print("\nDeactivating pattern constraints...")
    # Deactivate pattern linking constraints
    pattern_constraints.deactivate()

    # Reactivate changeover constraints
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].activate()

    # Fix pattern variables to 0 (remove them from problem)
    for idx in model.product_weekday_pattern:
        model.product_weekday_pattern[idx].fix(0)

    print("  Pattern constraints deactivated")
    print("  Changeover constraints reactivated")
    print("  Pattern variables fixed to 0")

    print("\n" + "="*80)
    print("SOLVING FLEXIBLE MODEL (SAME INSTANCE)")
    print("="*80)
    print("\nDIAGNOSTIC: APPSI should automatically hot-start from Phase 1")
    print("           Watch for fast convergence or early incumbent")

    phase2_start = time.time()
    result_phase2 = solver.solve(model)  # Same solver, same model = automatic hot start!
    phase2_time = time.time() - phase2_start

    phase2_cost = pyo.value(model.obj)
    print(f"\nPhase 2 Results:")
    print(f"  Solve time: {phase2_time:.1f}s")
    print(f"  Objective: ${phase2_cost:,.2f}")
    print(f"  Termination: {result_phase2.termination_condition}")

    # Analyze flexible solution
    prod_days_phase2, all_daily_phase2 = analyze_solution(
        model, products, dates_range, manufacturing_nodes_list, "PHASE 2"
    )

    # RESULTS COMPARISON
    print("\n" + "="*80)
    print("RESULTS COMPARISON")
    print("="*80)

    total_time = phase1_time + phase2_time

    print(f"\nPhase 1 (Pattern):  ${phase1_cost:,.2f} in {phase1_time:.1f}s")
    print(f"Phase 2 (Flexible): ${phase2_cost:,.2f} in {phase2_time:.1f}s")
    print(f"Total time:         {total_time:.1f}s")

    cost_diff = phase2_cost - phase1_cost
    cost_pct = (cost_diff / phase1_cost) * 100 if phase1_cost > 0 else 0

    print(f"\nCost change: ${cost_diff:,.2f} ({cost_pct:+.2f}%)")

    if cost_diff < 0:
        print(f"✅ Phase 2 IMPROVED: ${-cost_diff:,.2f} savings")
        print(f"   Expected behavior: Flexible model should find better solution")
    else:
        print(f"⚠️  Phase 2 WORSE: ${cost_diff:,.2f} increase")
        print(f"   Unexpected! Flexible should be better (fewer constraints)")

    # Production pattern comparison
    print(f"\nProduction pattern changes:")
    for product in products:
        days1 = prod_days_phase1[product]
        days2 = prod_days_phase2[product]
        change = days2 - days1
        if change != 0:
            print(f"  {product}: {days1} → {days2} days ({change:+d})")

    # DIAGNOSTIC ANALYSIS
    print("\n" + "="*80)
    print("DIAGNOSTIC ANALYSIS")
    print("="*80)

    print(f"\n1. WARMSTART MECHANISM:")
    print(f"   Approach: Same model instance + APPSI persistent solver")
    print(f"   Expected: Automatic hot-start (no explicit .set_value())")
    print(f"   Phase 2 time: {phase2_time:.1f}s")

    if phase2_time < 60:
        print(f"   ✓  Very fast! Suggests hot-start working")
    elif phase2_time < 180:
        print(f"   ?  Moderate speed, uncertain if hot-start helped")
    else:
        print(f"   ⚠️  Slow, hot-start may not be working")

    print(f"\n2. SOLUTION QUALITY:")
    if all_daily_phase1:
        print(f"   Phase 1: ALL products every day (forced by pattern)")
    else:
        print(f"   Phase 1: Selective production")

    if all_daily_phase2:
        print(f"   Phase 2: Still producing all products daily")
        print(f"   ⚠️  Pattern may have 'locked in' suboptimal solution")
    else:
        print(f"   Phase 2: Optimized production schedule")
        print(f"   ✓  Flexible model found better production pattern")

    if cost_diff > 0:
        print(f"\n3. COST INCREASE ANALYSIS:")
        print(f"   Phase 2 cost is ${cost_diff:,.2f} higher than Phase 1")

        if all_daily_phase1 and all_daily_phase2:
            print(f"   Hypothesis: Both phases produce all SKUs daily")
            print(f"   → Phase 2 may have slightly different distribution")
            print(f"   → Cost difference may be numerical noise or sub-optimality")
        elif all_daily_phase1 and not all_daily_phase2:
            print(f"   ✓  Phase 2 reduced some SKUs (good!)")
            print(f"   ?  But cost increased (unexpected)")
            print(f"   → May indicate solver stopped at local optimum")
        else:
            print(f"   ?  Unexpected cost increase needs investigation")

    # RECOMMENDATION
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)

    if cost_diff < -1000:  # Saved at least $1000
        print(f"\n✅ SUCCESS: Same-instance approach works well!")
        print(f"\nBenefits:")
        print(f"  - Cost improved by ${-cost_diff:,.2f}")
        print(f"  - Total time: {total_time:.1f}s")
        print(f"  - APPSI hot-start appears effective")
        print(f"\nNext steps:")
        print(f"  1. Replace separate-instance warmstart with this approach")
        print(f"  2. Test on 6-week horizon")
        print(f"  3. Consider tuning pattern to be less restrictive")

    elif abs(cost_diff) < 1000 and phase2_time < 60:
        print(f"\n✓  PARTIAL SUCCESS: Fast solve, similar cost")
        print(f"\nObservations:")
        print(f"  - Phase 2 solved quickly ({phase2_time:.1f}s) - hot-start working")
        print(f"  - Cost similar (${abs(cost_diff):,.2f} difference)")
        print(f"  - May indicate pattern already near-optimal")
        print(f"\nNext steps:")
        print(f"  1. Compare with cold-start flexible solve")
        print(f"  2. If faster than cold, use this approach")
        print(f"  3. If not faster, skip pattern phase")

    else:
        print(f"\n⚠️  APPROACH NEEDS REFINEMENT")
        print(f"\nIssues:")
        if cost_diff > 0:
            print(f"  - Cost increased by ${cost_diff:,.2f}")
        if phase2_time > 180:
            print(f"  - Phase 2 slow ({phase2_time:.1f}s)")
        print(f"\nPossible causes:")
        print(f"  1. Pattern solution is poor quality (all SKUs daily)")
        print(f"  2. Hot-start not effective for this problem")
        print(f"  3. Need to improve pattern quality (less restrictive)")
        print(f"\nNext steps:")
        print(f"  1. Test cold-start flexible solve for comparison")
        print(f"  2. Try partial pattern (only some products)")
        print(f"  3. Consider LP relaxation warmstart instead")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
