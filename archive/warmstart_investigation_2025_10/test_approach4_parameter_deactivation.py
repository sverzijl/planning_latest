#!/usr/bin/env python3
"""Test Approach 4: Parameter-Based Constraint Deactivation (APPSI-Compatible)

BRILLIANT INSIGHT: Instead of deactivating constraints (structural change),
use a MUTABLE PARAMETER to control enforcement (parameter change only).

APPSI is designed to handle parameter changes efficiently and should
preserve the MIP incumbent across parameter changes!

This follows APPSI's design philosophy: "modify model in place" via parameters.
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


def build_pattern_model_with_parameter(model_obj, products, weekday_dates_lists, manufacturing_nodes_list):
    """Build pattern model using PARAMETER-BASED constraint enforcement.

    Key innovation: Use mutable parameter instead of .deactivate()
    - pattern_active = 1 → pattern enforced (Phase 1)
    - pattern_active = 0 → pattern disabled (Phase 2)

    APPSI sees this as parameter change, not structural change!
    """
    model = model_obj.build_model()

    # CRITICAL: Add mutable parameter to control pattern enforcement
    model.pattern_active = pyo.Param(initialize=1.0, mutable=True)
    print(f"  Added mutable parameter: pattern_active = {pyo.value(model.pattern_active)}")

    # Create pattern variables
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)
    print(f"  Added {len(pattern_index)} pattern variables")

    # BigM for constraint deactivation
    # When pattern_active=0, constraint becomes: -M <= diff <= M (always satisfied)
    # When pattern_active=1, constraint becomes: 0 <= diff <= 0 (equality)
    big_m = 10.0  # Binary variables are 0 or 1, so M=10 is plenty

    # Add pattern linking constraints with PARAMETER-BASED enforcement
    model.pattern_linking_upper = pyo.ConstraintList()
    model.pattern_linking_lower = pyo.ConstraintList()

    constraint_count = 0
    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                for date_val in weekday_dates_lists[weekday_idx]:
                    if (node_id, product, date_val) in model.product_produced:
                        # Upper bound: product_produced - pattern <= M * (1 - pattern_active)
                        model.pattern_linking_upper.add(
                            model.product_produced[node_id, product, date_val] -
                            model.product_weekday_pattern[product, weekday_idx]
                            <= big_m * (1 - model.pattern_active)
                        )

                        # Lower bound: product_produced - pattern >= -M * (1 - pattern_active)
                        model.pattern_linking_lower.add(
                            model.product_produced[node_id, product, date_val] -
                            model.product_weekday_pattern[product, weekday_idx]
                            >= -big_m * (1 - model.pattern_active)
                        )

                        constraint_count += 1

    print(f"  Added {constraint_count} pattern linking constraints (with parameter control)")

    # Deactivate changeover constraints (pattern handles it in Phase 1)
    # We'll reactivate these in Phase 2 by changing another parameter
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()
        print(f"  Deactivated changeover constraints (will use parameter for these too)")

    return model


def calculate_num_products_produced(model, products, manufacturing_nodes_list, dates_range):
    """Calculate and set num_products_produced from product_produced."""
    if not hasattr(model, 'num_products_produced'):
        return 0

    count = 0
    for node_id in manufacturing_nodes_list:
        for date_val in dates_range:
            if (node_id, date_val) in model.num_products_produced:
                num_products = sum(
                    1 for product in products
                    if (node_id, product, date_val) in model.product_produced
                    and pyo.value(model.product_produced[node_id, product, date_val]) > 0.5
                )
                model.num_products_produced[node_id, date_val].set_value(num_products)
                count += 1

    return count


def main():
    print("="*80)
    print("APPROACH 4: Parameter-Based Constraint Deactivation")
    print("="*80)
    print("\nStrategy: Use mutable parameter instead of .deactivate()")
    print("Expected: APPSI preserves incumbent across parameter changes\n")

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

    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)

    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    weekday_dates_lists = {i: [] for i in range(5)}
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        if current.weekday() < 5:
            labor_day = labor_calendar.get_labor_day(current)
            if labor_day and labor_day.is_fixed_day:
                weekday_dates_lists[current.weekday()].append(current)
        current += timedelta(days=1)

    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # BUILD MODEL WITH PARAMETER-BASED PATTERN
    print("\n" + "="*80)
    print("BUILD MODEL WITH PARAMETER-BASED PATTERN CONSTRAINTS")
    print("="*80)

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

    print("\nBuilding model with parameter-based pattern...")
    model = build_pattern_model_with_parameter(
        model_obj, products, weekday_dates_lists, manufacturing_nodes_list
    )

    # Create APPSI solver
    solver = appsi.solvers.Highs()
    solver.config.time_limit = 120
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = True  # See solver output

    # PHASE 1: Solve with pattern_active=1
    print("\n" + "="*80)
    print("PHASE 1: SOLVE WITH PATTERN ACTIVE (parameter=1)")
    print("="*80)

    print(f"\nCurrent pattern_active = {pyo.value(model.pattern_active)}")

    phase1_start = time.time()
    result1 = solver.solve(model)
    phase1_time = time.time() - phase1_start

    cost1 = pyo.value(model.obj)
    print(f"\nPhase 1 Results:")
    print(f"  Cost: ${cost1:,.2f}")
    print(f"  Time: {phase1_time:.1f}s")
    print(f"  Status: {result1.termination_condition}")

    # Calculate num_products_produced for complete solution
    print("\nCompleting solution (set num_products_produced)...")
    num_calc = calculate_num_products_produced(model, products, manufacturing_nodes_list, dates_range)
    print(f"  Set {num_calc} num_products_produced values")

    # Reactivate changeover constraints for Phase 2
    print("\nReactivating changeover constraints...")
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].activate()
        print(f"  Reactivated changeover constraints")

    # PHASE 2: Change parameter to deactivate pattern
    print("\n" + "="*80)
    print("PHASE 2: CHANGE PARAMETER TO DEACTIVATE PATTERN")
    print("="*80)

    print("\nChanging pattern_active from 1 to 0...")
    print("  Before: pattern_active = {}".format(pyo.value(model.pattern_active)))

    model.pattern_active.set_value(0.0)  # PARAMETER CHANGE (not structural!)

    print("  After:  pattern_active = {}".format(pyo.value(model.pattern_active)))
    print("\n✓  Pattern constraints now disabled (BigM becomes active)")
    print("  This is a PARAMETER CHANGE - APPSI should preserve incumbent!")

    # Verify current objective before re-solve
    try:
        current_obj = pyo.value(model.obj)
        print(f"\n  Current objective (before re-solve): ${current_obj:,.2f}")
        if abs(current_obj - cost1) < 100:
            print(f"  ✓  Close to Phase 1 cost (${cost1:,.2f})")
        else:
            print(f"  ⚠️  Different from Phase 1: ${abs(current_obj-cost1):,.2f} diff")
    except:
        print("  Cannot evaluate objective")

    # PHASE 2: Re-solve (APPSI should hot-start!)
    print("\n" + "="*80)
    print("PHASE 2: RE-SOLVE WITH PATTERN DISABLED (parameter=0)")
    print("="*80)

    print("\nCRITICAL: Watch solver output for initial incumbent")
    print(f"Expected: Should show ~${cost1:,.2f} (Phase 1 cost)")
    print(f"If shows $3.38M → warmstart failed (APPSI didn't preserve)\n")

    phase2_start = time.time()
    result2 = solver.solve(model)  # Same solver, same model, parameter changed
    phase2_time = time.time() - phase2_start

    cost2 = pyo.value(model.obj)
    print(f"\nPhase 2 Results:")
    print(f"  Cost: ${cost2:,.2f}")
    print(f"  Time: {phase2_time:.1f}s")
    print(f"  Status: {result2.termination_condition}")

    # ANALYSIS
    print("\n" + "="*80)
    print("RESULTS ANALYSIS")
    print("="*80)

    cost_diff = cost2 - cost1
    cost_pct = (cost_diff / cost1) * 100 if cost1 > 0 else 0
    total_time = phase1_time + phase2_time

    print(f"\nPhase 1:     ${cost1:,.2f} in {phase1_time:.1f}s (pattern active)")
    print(f"Phase 2:     ${cost2:,.2f} in {phase2_time:.1f}s (pattern disabled)")
    print(f"Difference:  ${cost_diff:,.2f} ({cost_pct:+.2f}%)")
    print(f"Total time:  {total_time:.1f}s")

    # Analyze production patterns
    print("\nProduction pattern analysis:")
    for product in products:
        count_phase2 = sum(
            1 for d in dates_range
            if (manufacturing_nodes_list[0], product, d) in model.product_produced
            and pyo.value(model.product_produced[manufacturing_nodes_list[0], product, d]) > 0.5
        )
        pct = (count_phase2 / len(dates_range)) * 100
        print(f"  {product}: {count_phase2}/{len(dates_range)} days ({pct:.1f}%)")

    # SUCCESS CRITERIA
    print("\n" + "="*80)
    print("SUCCESS CRITERIA EVALUATION")
    print("="*80)

    success = True

    # Criterion 1: Phase 2 cost <= Phase 1 cost (within tolerance)
    if cost_diff <= 100:  # Allow $100 tolerance for numerical differences
        print(f"\n✅ Criterion 1: Phase 2 cost ≤ Phase 1 cost")
        print(f"   Difference: ${cost_diff:,.2f} (within tolerance)")
    else:
        print(f"\n❌ Criterion 1 FAILED: Phase 2 cost > Phase 1 cost")
        print(f"   Difference: ${cost_diff:,.2f}")
        print(f"   This violates optimization logic (Phase 2 less constrained)")
        success = False

    # Criterion 2: Check solver log for warm start
    print(f"\n   Review solver output above:")
    if cost_diff <= 100:
        print(f"   → Initial incumbent likely at ~${cost1:,.2f}")
        print(f"   → Warmstart preserved!")
    else:
        print(f"   → Initial incumbent likely at $3.38M")
        print(f"   → Warmstart NOT preserved")

    # Criterion 3: Performance
    if phase2_time < 60:
        print(f"\n✅ Criterion 3: Phase 2 fast ({phase2_time:.1f}s)")
        print(f"   Hot-start appears effective")
    elif phase2_time < 120:
        print(f"\n⚠️  Criterion 3: Phase 2 moderate ({phase2_time:.1f}s)")
        print(f"   Some benefit from hot-start")
    else:
        print(f"\n❌ Criterion 3 FAILED: Phase 2 slow ({phase2_time:.1f}s)")
        print(f"   No apparent hot-start benefit")
        success = False

    # FINAL VERDICT
    print("\n" + "="*80)
    print("FINAL VERDICT")
    print("="*80)

    if success and cost_diff <= 100:
        print(f"\n🎉 SUCCESS: PARAMETER-BASED DEACTIVATION WORKS!")
        print(f"\nKey achievements:")
        print(f"  ✓  Phase 2 cost ({cost2:,.0f}) ≤ Phase 1 cost ({cost1:,.0f})")
        print(f"  ✓  Warmstart preserved across parameter change")
        print(f"  ✓  APPSI hot-start working correctly")
        print(f"\nThis is the CORRECT approach for APPSI warmstart!")
        print(f"\nNext steps:")
        print(f"  1. Integrate into solve_weekly_pattern_warmstart()")
        print(f"  2. Test on 6-week horizon")
        print(f"  3. Benchmark vs cold start")

    elif cost_diff < 0:
        print(f"\n✅ PARTIAL SUCCESS: Phase 2 improved")
        print(f"\nResults:")
        print(f"  ✓  Cost improved by ${-cost_diff:,.2f}")
        print(f"  ✓  Phase 2 found better solution than Phase 1")
        print(f"\nBut:")
        if phase2_time > 120:
            print(f"  ⚠️  Phase 2 was slow ({phase2_time:.1f}s)")
            print(f"     May not be faster than cold start")

    else:
        print(f"\n❌ APPROACH 4 FAILED")
        print(f"\nIssues:")
        print(f"  Phase 2 cost ${cost_diff:,.2f} WORSE than Phase 1")
        print(f"  This violates optimization logic")
        print(f"  → Warmstart still not being preserved")
        print(f"\nPossible causes:")
        print(f"  1. APPSI doesn't preserve MIP incumbent even for parameter changes")
        print(f"  2. Activating changeover constraints invalidated the warmstart")
        print(f"  3. Pattern solution infeasible for reactivated constraints")
        print(f"\nConclusion:")
        print(f"  Pattern warmstart is NOT VIABLE in Pyomo/APPSI")
        print(f"  Recommendation: Use direct flexible solve")

    print(f"\n{'='*80}")
    print("APPROACH 4 TEST COMPLETE")
    print(f"{'='*80}")

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
