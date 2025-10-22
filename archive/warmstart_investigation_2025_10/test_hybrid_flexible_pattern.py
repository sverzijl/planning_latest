#!/usr/bin/env python3
"""Test: Hybrid Flexible-Pattern Strategy

Configuration:
- Weeks 1-2: Fully flexible (no pattern constraints)
- Weeks 3-6: Weekly pattern constraints (forced repetition)

Expected Performance: 100-150s (3-5× slower than full pattern, 4-6× faster than no pattern)

Business Value: 33% flexibility where it matters (near-term) with long-term tractability
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


def build_hybrid_flexible_pattern_model(
    model_obj,
    products,
    dates,
    weekday_dates_lists,
    manufacturing_nodes_list,
    labor_calendar,
    flexible_weeks=2
):
    """Build model with flexible near-term + pattern long-term.

    Args:
        model_obj: UnifiedNodeModel instance
        products: List of product IDs
        dates: List of all dates in horizon
        weekday_dates_lists: Dict mapping weekday index → list of dates
        manufacturing_nodes_list: List of manufacturing node IDs
        labor_calendar: LaborCalendar instance
        flexible_weeks: Number of weeks to leave flexible (default: 2)

    Returns:
        Pyomo model with hybrid constraints
    """
    print(f"\n{'='*80}")
    print(f"BUILDING HYBRID MODEL: {flexible_weeks} weeks flexible + remaining weeks pattern")
    print(f"{'='*80}")

    # Build base model
    print("\nBuilding base Pyomo model...")
    build_start = time.time()
    model = model_obj.build_model()
    build_time = time.time() - build_start
    print(f"Base model built in {build_time:.1f}s")

    # Determine flexible vs pattern dates
    start_date = min(dates)
    flexible_end_date = start_date + timedelta(days=flexible_weeks * 7 - 1)

    flexible_dates = [d for d in dates if d <= flexible_end_date]
    pattern_dates = [d for d in dates if d > flexible_end_date]

    print(f"\nDate partitioning:")
    print(f"  Flexible dates (weeks 1-{flexible_weeks}): {len(flexible_dates)} days")
    print(f"  Pattern dates (weeks {flexible_weeks+1}+): {len(pattern_dates)} days")

    # Count production days in each period
    flexible_prod_days = len([d for d in flexible_dates if d.weekday() < 5])
    pattern_prod_days = len([d for d in pattern_dates if d.weekday() < 5])

    print(f"  Flexible production days: {flexible_prod_days}")
    print(f"  Pattern production days: {pattern_prod_days}")

    # Create pattern variables for long-term weeks ONLY
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(
        pattern_index,
        within=pyo.Binary,
        doc="Weekly production pattern for long-term weeks"
    )

    print(f"\nPattern variables created: {len(pattern_index)} (5 products × 5 weekdays)")

    # Add linking constraints ONLY for pattern dates (weeks 3-6)
    model.weekly_pattern_linking = pyo.ConstraintList()

    constraint_count = 0
    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                # Only link dates in pattern weeks
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

    print(f"Pattern linking constraints added: {constraint_count}")

    # CRITICAL: Deactivate conflicting constraints for pattern dates only
    # (Flexible dates keep changeover tracking active)
    deactivated_count = 0
    if hasattr(model, 'num_products_counting_con'):
        # Iterate over the constraint indices directly
        for idx in model.num_products_counting_con:
            node_id, date_val = idx
            if date_val in pattern_dates:
                model.num_products_counting_con[idx].deactivate()
                deactivated_count += 1

    print(f"Changeover constraints deactivated (pattern dates): {deactivated_count}")
    print(f"Changeover constraints active (flexible dates): {len(flexible_dates)}")

    # Count binary variables
    def count_variables(m):
        binary = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_binary())
        integer = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_integer())
        continuous = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_continuous())
        return binary, integer, continuous

    binary_count, integer_count, continuous_count = count_variables(model)

    print(f"\nFinal variable counts:")
    print(f"  Binary: {binary_count:,}")
    print(f"    - Flexible weeks product_produced: ~{flexible_prod_days * len(products)}")
    print(f"    - Pattern weeks product_produced: ~{pattern_prod_days * len(products)}")
    print(f"    - Pattern definitions: {len(pattern_index)}")
    print(f"    - Other binaries: ~{binary_count - flexible_prod_days * len(products) - pattern_prod_days * len(products) - len(pattern_index)}")
    print(f"  Integer: {integer_count:,}")
    print(f"  Continuous: {continuous_count:,}")

    print(f"\nBinary decision breakdown:")
    print(f"  Flexible decisions (weeks 1-{flexible_weeks}): ~{flexible_prod_days * len(products)}")
    print(f"  Pattern decisions (weeks {flexible_weeks+1}+): {len(pattern_index)}")
    print(f"  Total primary decisions: ~{flexible_prod_days * len(products) + len(pattern_index)}")

    return model


def main():
    print("="*80)
    print("HYBRID FLEXIBLE-PATTERN TEST")
    print("="*80)
    print("\nStrategy: 2 weeks flexible + 4 weeks pattern")
    print("Expected: 100-150s (3-5× slower than full pattern)")

    # Load data
    print("\n" + "="*80)
    print("LOADING DATA")
    print("="*80)

    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
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

    print(f"\nConfiguration:")
    print(f"  Horizon: 6 weeks ({(end_date - start_date).days + 1} days)")

    # Get products and manufacturing nodes
    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    print(f"  Products: {len(products)}")
    print(f"  Manufacturing nodes: {len(manufacturing_nodes_list)}")

    # Build date lists
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    weekday_dates_lists = {i: [] for i in range(5)}
    weekend_dates = []

    for date_val in dates_range:
        weekday = date_val.weekday()
        labor_day = labor_calendar.get_labor_day(date_val)

        if weekday < 5 and labor_day and labor_day.is_fixed_day:
            weekday_dates_lists[weekday].append(date_val)
        else:
            weekend_dates.append(date_val)

    # Create model object
    print("\n" + "="*80)
    print("CREATING MODEL OBJECT")
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

    # Build hybrid model
    hybrid_model = build_hybrid_flexible_pattern_model(
        model_obj=model_obj,
        products=products,
        dates=dates_range,
        weekday_dates_lists=weekday_dates_lists,
        manufacturing_nodes_list=manufacturing_nodes_list,
        labor_calendar=labor_calendar,
        flexible_weeks=2  # 2 weeks flexible, 4 weeks pattern
    )

    # Solve
    print("\n" + "="*80)
    print("SOLVING HYBRID MODEL")
    print("="*80)

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 600  # 10 minutes
    solver.config.mip_gap = 0.03   # 3%
    solver.config.stream_solver = False

    print("\nSolver configuration:")
    print(f"  Solver: HiGHS (APPSI interface)")
    print(f"  Time limit: 600s (10 minutes)")
    print(f"  MIP gap: 3%")

    print("\nSolving...")
    solve_start = time.time()

    result = solver.solve(hybrid_model)

    solve_time = time.time() - solve_start

    # Extract results
    hybrid_cost = pyo.value(hybrid_model.obj)
    hybrid_gap = None
    if hasattr(result, 'best_feasible_objective') and hasattr(result, 'best_objective_bound'):
        best_feas = result.best_feasible_objective
        best_bound = result.best_objective_bound
        if best_feas and best_bound and best_feas != 0:
            hybrid_gap = abs((best_feas - best_bound) / best_feas)

    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")

    print(f"\nHybrid Model (2 weeks flexible + 4 weeks pattern):")
    print(f"  Solve time: {solve_time:.1f}s")
    print(f"  Cost: ${hybrid_cost:,.2f}")
    if hybrid_gap is not None:
        print(f"  Gap: {hybrid_gap*100:.3f}%")
    print(f"  Status: {result.termination_condition}")

    # Compare to expected performance
    print(f"\n{'='*80}")
    print("PERFORMANCE ANALYSIS")
    print(f"{'='*80}")

    # Expected from analysis
    full_pattern_time = 28.2  # From diagnostic test
    no_pattern_time = 636     # From baseline

    expected_min = 100
    expected_max = 150

    print(f"\nBaseline comparisons:")
    print(f"  Full pattern (0% flexible): {full_pattern_time:.1f}s")
    print(f"  Hybrid (33% flexible): {solve_time:.1f}s")
    print(f"  No pattern (100% flexible): {no_pattern_time:.1f}s")

    print(f"\nPerformance vs baselines:")
    slowdown_vs_pattern = solve_time / full_pattern_time
    speedup_vs_none = no_pattern_time / solve_time

    print(f"  vs Full pattern: {slowdown_vs_pattern:.2f}× slower")
    print(f"  vs No pattern: {speedup_vs_none:.2f}× faster")

    print(f"\nExpected range: {expected_min}-{expected_max}s")
    if expected_min <= solve_time <= expected_max:
        print(f"  ✅ WITHIN EXPECTED RANGE")
    elif solve_time < expected_min:
        print(f"  ⚡ FASTER THAN EXPECTED (excellent!)")
    else:
        print(f"  ⚠️  SLOWER THAN EXPECTED")

    # Analyze solution structure
    print(f"\n{'='*80}")
    print("SOLUTION STRUCTURE ANALYSIS")
    print(f"{'='*80}")

    # Check if weeks 1-2 have different patterns than weeks 3-6
    print("\nAnalyzing production patterns:")

    # Get week 1-2 production decisions
    week1_2_decisions = {}
    for node_id in manufacturing_nodes_list:
        for product in products:
            week1_2_decisions[product] = []
            for date_val in dates_range[:14]:  # First 2 weeks
                if (node_id, product, date_val) in hybrid_model.product_produced:
                    val = pyo.value(hybrid_model.product_produced[node_id, product, date_val])
                    week1_2_decisions[product].append((date_val.strftime('%a'), val))

    # Get week 3-6 pattern
    week3_6_pattern = {}
    for product in products:
        week3_6_pattern[product] = {}
        for weekday_idx in range(5):
            weekday_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][weekday_idx]
            if (product, weekday_idx) in hybrid_model.product_weekday_pattern:
                val = pyo.value(hybrid_model.product_weekday_pattern[product, weekday_idx])
                week3_6_pattern[product][weekday_name] = val

    print("\nWeeks 3-6 Pattern:")
    for product in products:
        pattern_str = " ".join([f"{day}:{int(week3_6_pattern[product][day])}" for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']])
        print(f"  {product}: {pattern_str}")

    print("\nWeeks 1-2 Decisions (first 5 production days):")
    for product in products:
        decisions = week1_2_decisions[product][:5]  # First 5 days
        decision_str = " ".join([f"{day}:{int(val)}" for day, val in decisions])
        print(f"  {product}: {decision_str}")

    # Check for differences
    print("\nFlexibility utilization:")
    differences = 0
    total_checks = 0
    for product in products:
        for day, val in week1_2_decisions[product]:
            if day in week3_6_pattern[product]:
                pattern_val = week3_6_pattern[product][day]
                if abs(val - pattern_val) > 0.01:  # Different
                    differences += 1
                total_checks += 1

    if total_checks > 0:
        diff_pct = (differences / total_checks) * 100
        print(f"  Weeks 1-2 deviate from weeks 3-6 pattern: {differences}/{total_checks} ({diff_pct:.1f}%)")
        if diff_pct > 10:
            print(f"  ✅ Flexibility is being utilized")
        else:
            print(f"  ℹ️  Pattern was already optimal for weeks 1-2")
    else:
        print(f"  ℹ️  Cannot compare (insufficient data)")

    # Final recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    if solve_time < 180:  # 3 minutes
        print(f"\n✅ RECOMMENDED: Hybrid strategy is practical for 6-week planning")
        print(f"\nBenefits:")
        print(f"  - Solve time acceptable: {solve_time:.0f}s < 3 minutes")
        print(f"  - Weeks 1-2 fully flexible (operational responsiveness)")
        print(f"  - Weeks 3-6 pattern-constrained (long-term tractability)")
        print(f"  - {slowdown_vs_pattern:.1f}× slower than full pattern (acceptable cost)")
        print(f"  - {speedup_vs_none:.1f}× faster than no pattern (avoids timeout risk)")
    elif solve_time < 300:  # 5 minutes
        print(f"\n✓  ACCEPTABLE: Hybrid strategy feasible but slower than expected")
        print(f"\nObservation:")
        print(f"  - Solve time: {solve_time:.0f}s (5 minutes acceptable for planning)")
        print(f"  - Consider reducing flexible window to 1 week (~50-80s expected)")
    else:
        print(f"\n⚠️  SLOWER THAN EXPECTED: Consider alternatives")
        print(f"\nOptions:")
        print(f"  1. Reduce flexible window to 1 week")
        print(f"  2. Use full pattern with soft penalties for emergencies")
        print(f"  3. Investigate solver parameters or presolve issues")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
