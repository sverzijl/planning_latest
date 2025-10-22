#!/usr/bin/env python3
"""Test: 1 Week Flexible + 5 Weeks Pattern

Configuration:
- Week 1: Fully flexible (no pattern constraints)
- Weeks 2-6: Weekly pattern constraints

Binary Decisions:
- Week 1 flexible: ~25 binaries (5 production days × 5 products)
- Weeks 2-6 pattern: 25 binaries (5 products × 5 weekdays)
- Total: ~50 binaries (vs 75 for 2-week flexible)

Search Space Reduction:
- 2-week flexible: 2^75 ≈ 3.8×10^22
- 1-week flexible: 2^50 ≈ 1.1×10^15
- Reduction: 2^25 ≈ 33 million times fewer combinations!

Expected Performance: 50-100s (based on MIP scaling theory)
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


def build_1week_flexible_model(model_obj, products, dates, weekday_dates_lists, manufacturing_nodes_list):
    """Build model with 1 week flexible + 5 weeks pattern."""

    print(f"\n{'='*80}")
    print(f"BUILDING 1-WEEK FLEXIBLE MODEL")
    print(f"{'='*80}")

    # Build base model
    print("\nBuilding base Pyomo model...")
    build_start = time.time()
    model = model_obj.build_model()
    build_time = time.time() - build_start
    print(f"Base model built in {build_time:.1f}s")

    # Determine flexible vs pattern dates
    start_date = min(dates)
    flexible_weeks = 1
    flexible_end_date = start_date + timedelta(days=flexible_weeks * 7 - 1)

    flexible_dates = [d for d in dates if d <= flexible_end_date]
    pattern_dates = [d for d in dates if d > flexible_end_date]

    # Count production days
    flexible_prod_days = sum(1 for d in flexible_dates if d.weekday() < 5)
    pattern_prod_days = sum(1 for d in pattern_dates if d.weekday() < 5)

    print(f"\nDate partitioning:")
    print(f"  Flexible dates (week 1): {len(flexible_dates)} days ({flexible_prod_days} production days)")
    print(f"  Pattern dates (weeks 2-6): {len(pattern_dates)} days ({pattern_prod_days} production days)")

    # Create pattern variables for weeks 2-6
    # NOTE: Pattern does NOT force all products daily!
    # Pattern[product, weekday] ∈ {0,1} means "produce this product on this weekday"
    # Some weekdays might have pattern[product, weekday]=0 (don't produce)

    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(
        pattern_index,
        within=pyo.Binary,
        doc="Weekly production pattern for weeks 2-6 (0=don't produce, 1=produce)"
    )

    print(f"  Pattern variables created: {len(pattern_index)} (5 products × 5 weekdays)")
    print(f"  Note: Pattern does NOT force all products daily (can be 0 or 1)")

    # Link pattern dates only (weeks 2-6)
    model.weekly_pattern_linking = pyo.ConstraintList()

    constraint_count = 0
    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                # Only link dates in pattern weeks (weeks 2-6)
                pattern_week_dates = [
                    d for d in weekday_dates_lists[weekday_idx]
                    if d in pattern_dates
                ]

                for date_val in pattern_week_dates:
                    if (node_id, product, date_val) in model.product_produced:
                        # Link to pattern
                        model.weekly_pattern_linking.add(
                            model.product_produced[node_id, product, date_val] ==
                            model.product_weekday_pattern[product, weekday_idx]
                        )
                        constraint_count += 1

    print(f"  Pattern linking constraints added: {constraint_count}")

    # Deactivate conflicting changeover constraints for pattern dates
    deactivated_count = 0
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            node_id, date_val = idx
            if date_val in pattern_dates:
                model.num_products_counting_con[idx].deactivate()
                deactivated_count += 1

    print(f"  Changeover constraints deactivated (pattern dates): {deactivated_count}")
    print(f"  Changeover constraints active (flexible dates): {flexible_prod_days}")

    # Count binary variables
    def count_variables(m):
        binary = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_binary())
        integer = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_integer())
        continuous = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_continuous())
        return binary, integer, continuous

    binary_count, integer_count, continuous_count = count_variables(model)

    print(f"\nFinal variable counts:")
    print(f"  Binary: {binary_count:,}")
    print(f"  Integer: {integer_count:,}")
    print(f"  Continuous: {continuous_count:,}")

    print(f"\nBinary decision breakdown:")
    print(f"  Week 1 flexible: ~{flexible_prod_days * len(products)} decisions")
    print(f"  Weeks 2-6 pattern: {len(pattern_index)} decisions")
    print(f"  Total primary decisions: ~{flexible_prod_days * len(products) + len(pattern_index)}")
    print(f"  Reduction from 2-week flexible: ~25 fewer decisions")

    return model


def main():
    print("="*80)
    print("1-WEEK FLEXIBLE + 5-WEEK PATTERN TEST")
    print("="*80)
    print("\nStrategy: Reduce flexible window from 2 weeks → 1 week")
    print("Expected: 50-100s (vs 609s for 2-week flexible)")
    print("Reason: 25 fewer binary decisions = 33 million× smaller search space\n")

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

    # Test 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

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

    # Enable freshness incentive
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # Create model
    print("\n" + "="*80)
    print("CREATING MODEL")
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

    # Build 1-week flexible model
    model = build_1week_flexible_model(
        model_obj=model_obj,
        products=products,
        dates=dates_range,
        weekday_dates_lists=weekday_dates_lists,
        manufacturing_nodes_list=manufacturing_nodes_list
    )

    # Solve
    print("\n" + "="*80)
    print("SOLVING")
    print("="*80)

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 600  # 10 minutes
    solver.config.mip_gap = 0.03   # 3%
    solver.config.stream_solver = False

    print("\nSolver configuration:")
    print(f"  Solver: HiGHS")
    print(f"  Time limit: 600s")
    print(f"  MIP gap: 3%")
    print(f"  Freshness: ENABLED ($0.05/unit/day)")

    print("\nSolving...")
    solve_start = time.time()

    result = solver.solve(model)

    solve_time = time.time() - solve_start

    # Extract results
    cost = pyo.value(model.obj)
    gap = None
    if hasattr(result, 'best_feasible_objective') and hasattr(result, 'best_objective_bound'):
        best_feas = result.best_feasible_objective
        best_bound = result.best_objective_bound
        if best_feas and best_bound and best_feas != 0:
            gap = abs((best_feas - best_bound) / best_feas)

    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")

    print(f"\n1-Week Flexible Model:")
    print(f"  Solve time: {solve_time:.1f}s")
    print(f"  Cost: ${cost:,.2f}")
    if gap is not None:
        print(f"  Gap: {gap*100:.3f}%")
    print(f"  Status: {result.termination_condition}")

    # Compare to baselines
    print(f"\n{'='*80}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*80}")

    full_pattern_time = 28.2
    two_week_flex_time = 609.8
    expected_min = 50
    expected_max = 100

    print(f"\nBaseline comparisons:")
    print(f"  Full pattern (0 weeks flexible): {full_pattern_time:.1f}s")
    print(f"  1-week flexible (this test): {solve_time:.1f}s")
    print(f"  2-week flexible (previous): {two_week_flex_time:.1f}s")

    print(f"\nPerformance vs baselines:")
    slowdown_vs_pattern = solve_time / full_pattern_time
    speedup_vs_2week = two_week_flex_time / solve_time

    print(f"  vs Full pattern: {slowdown_vs_pattern:.2f}× slower")
    print(f"  vs 2-week flexible: {speedup_vs_2week:.2f}× faster")

    print(f"\nExpected range: {expected_min}-{expected_max}s")
    if solve_time <= expected_max:
        print(f"  ✅ WITHIN OR BETTER THAN EXPECTED")
    else:
        print(f"  ⚠️  SLOWER THAN EXPECTED")

    # Analyze production pattern
    print(f"\n{'='*80}")
    print("PRODUCTION PATTERN ANALYSIS")
    print(f"{'='*80}")

    print("\nWeeks 2-6 Pattern (Does NOT force 5 SKUs/day):")
    for product in products:
        pattern_days = []
        for weekday_idx in range(5):
            weekday_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][weekday_idx]
            if (product, weekday_idx) in model.product_weekday_pattern:
                val = pyo.value(model.product_weekday_pattern[product, weekday_idx])
                if val > 0.5:  # Produced
                    pattern_days.append(weekday_name)

        pattern_str = ", ".join(pattern_days) if pattern_days else "NONE"
        days_count = len(pattern_days)
        print(f"  {product}: {pattern_str} ({days_count}/5 days)")

    print("\nWeek 1 Flexible Decisions:")
    week1_dates = [d for d in dates if d <= flexible_end_date and d.weekday() < 5]

    for product in products:
        produced_days = []
        for node_id in manufacturing_nodes_list:
            for date_val in week1_dates:
                if (node_id, product, date_val) in model.product_produced:
                    val = pyo.value(model.product_produced[node_id, product, date_val])
                    if val > 0.5:
                        produced_days.append(date_val.strftime('%a'))

        days_str = ", ".join(produced_days) if produced_days else "NONE"
        days_count = len(produced_days)
        print(f"  {product}: {days_str} ({days_count}/5 days)")

    # Check flexibility utilization
    print(f"\n{'='*80}")
    print("FLEXIBILITY UTILIZATION")
    print(f"{'='*80}")

    # Compare week 1 decisions to weeks 2-6 pattern
    differences = 0
    total_checks = 0

    for node_id in manufacturing_nodes_list:
        for product in products:
            for date_val in week1_dates:
                weekday_idx = date_val.weekday()
                if (node_id, product, date_val) in model.product_produced:
                    week1_val = pyo.value(model.product_produced[node_id, product, date_val])
                    if (product, weekday_idx) in model.product_weekday_pattern:
                        pattern_val = pyo.value(model.product_weekday_pattern[product, weekday_idx])
                        if abs(week1_val - pattern_val) > 0.01:
                            differences += 1
                        total_checks += 1

    if total_checks > 0:
        diff_pct = (differences / total_checks) * 100
        print(f"\nWeek 1 deviates from weeks 2-6 pattern: {differences}/{total_checks} ({diff_pct:.1f}%)")
        if diff_pct > 10:
            print(f"✅ Flexibility is being utilized")
        else:
            print(f"ℹ️  Week 1 follows similar pattern to weeks 2-6")

    # Final recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    if solve_time < 120:  # 2 minutes
        print(f"\n✅ HIGHLY RECOMMENDED: 1-week flexible is PRACTICAL")
        print(f"\nBenefits:")
        print(f"  - Excellent solve time: {solve_time:.0f}s < 2 minutes")
        print(f"  - Week 1 fully flexible (operational responsiveness)")
        print(f"  - Weeks 2-6 pattern-constrained (long-term tractability)")
        print(f"  - {slowdown_vs_pattern:.1f}× slower than full pattern (acceptable)")
        print(f"  - {speedup_vs_2week:.1f}× faster than 2-week flexible (huge improvement!)")
        print(f"\nUse case: Weekly replanning with 1-week operational flexibility")
    elif solve_time < 300:  # 5 minutes
        print(f"\n✓  ACCEPTABLE: 1-week flexible is feasible")
        print(f"\nObservation:")
        print(f"  - Solve time: {solve_time:.0f}s (5 minutes acceptable for planning)")
        print(f"  - Much better than 2-week flexible ({speedup_vs_2week:.1f}× faster)")
        print(f"\nDecision: Worth using if week 1 flexibility is valuable")
    else:
        print(f"\n⚠️  STILL TOO SLOW: 1-week flexible not practical")
        print(f"\nOptions:")
        print(f"  1. Use full pattern (28s, proven)")
        print(f"  2. Try campaign-based (15 decisions)")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
