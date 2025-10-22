#!/usr/bin/env python3
"""Test: Soft Pattern Penalties vs Hard Pattern Constraints

Demonstrates flexibility strategy from BINARY_VS_INTEGER_MIP_ANALYSIS.md:
- Hard constraints: product_produced[date] = pattern[weekday] (fast but rigid)
- Soft penalties: Allow deviation with cost penalty (flexible but slower)

Expected Results:
- Hard constraints: ~28s, 0% flexibility, optimal within pattern
- Soft penalties: ~60-120s, 100% flexibility, optimal across all choices

This validates the MIP expert recommendation that soft penalties provide
flexibility at moderate performance cost.
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


def main():
    print("="*80)
    print("SOFT PATTERN PENALTIES TEST")
    print("="*80)
    print("\nObjective: Compare hard pattern constraints vs soft penalty approach")
    print("\nStrategy (from MIP analysis):")
    print("  Hard: product_produced[date] == pattern[weekday]")
    print("  Soft: minimize cost + penalty * |product_produced[date] - pattern[weekday]|")

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

    # Test 4-week horizon (manageable for comparison)
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)

    print(f"\nConfiguration:")
    print(f"  Horizon: 4 weeks ({(end_date - start_date).days + 1} days)")

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

    # TEST 1: Hard Pattern Constraints (Baseline)
    print("\n" + "="*80)
    print("TEST 1: HARD PATTERN CONSTRAINTS (Baseline)")
    print("="*80)
    print("\nConstraint: product_produced[date] == pattern[weekday]")
    print("Expected: ~28-35s, optimal within pattern space")

    build_start = time.time()

    model_hard_obj = UnifiedNodeModel(
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

    build_time = time.time() - build_start
    print(f"\nModel created in {build_time:.1f}s")

    pyomo_build_start = time.time()
    hard_model = model_hard_obj.build_model()
    pyomo_build_time = time.time() - pyomo_build_start
    print(f"Pyomo model built in {pyomo_build_time:.1f}s")

    # Add hard pattern constraints
    from pyomo.environ import Var, ConstraintList, Binary

    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    hard_model.product_weekday_pattern = Var(
        pattern_index,
        within=Binary,
        doc="Weekly production pattern"
    )

    hard_model.weekly_pattern_linking = ConstraintList()

    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx, date_list in weekday_dates_lists.items():
                for date_val in date_list:
                    if (node_id, product, date_val) in hard_model.product_produced:
                        # HARD CONSTRAINT: Equality
                        hard_model.weekly_pattern_linking.add(
                            hard_model.product_produced[node_id, product, date_val] ==
                            hard_model.product_weekday_pattern[product, weekday_idx]
                        )

    # Count variables
    from pyomo.environ import Var as PyomoVar

    def count_variables(model):
        binary = sum(1 for v in model.component_data_objects(ctype=PyomoVar, active=True) if v.is_binary())
        integer = sum(1 for v in model.component_data_objects(ctype=PyomoVar, active=True) if v.is_integer())
        continuous = sum(1 for v in model.component_data_objects(ctype=PyomoVar, active=True) if v.is_continuous())
        return binary, integer, continuous

    hard_binary, hard_integer, hard_continuous = count_variables(hard_model)
    print(f"\nVariable counts:")
    print(f"  Binary: {hard_binary:,}")
    print(f"  Integer: {hard_integer:,}")
    print(f"  Continuous: {hard_continuous:,}")

    # Solve hard constraint model
    print("\nSolving...")

    from pyomo.contrib import appsi

    solve_start = time.time()

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 600
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = False

    result_hard = solver.solve(hard_model)

    hard_time = time.time() - solve_start

    from pyomo.environ import value as pyo_value

    hard_cost = pyo_value(hard_model.obj)
    hard_gap = None
    if hasattr(result_hard, 'best_feasible_objective') and hasattr(result_hard, 'best_objective_bound'):
        best_feas = result_hard.best_feasible_objective
        best_bound = result_hard.best_objective_bound
        if best_feas and best_bound and best_feas != 0:
            hard_gap = abs((best_feas - best_bound) / best_feas)

    print(f"\nHard Constraint Results:")
    print(f"  Solve time: {hard_time:.1f}s")
    print(f"  Cost: ${hard_cost:,.2f}")
    if hard_gap is not None:
        print(f"  Gap: {hard_gap*100:.3f}%")

    # TEST 2: Soft Pattern Penalties
    print("\n" + "="*80)
    print("TEST 2: SOFT PATTERN PENALTIES")
    print("="*80)
    print("\nApproach: Allow deviation with $1000/deviation penalty")
    print("Expected: ~60-120s, optimal across all choices")

    build_start = time.time()

    model_soft_obj = UnifiedNodeModel(
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

    build_time = time.time() - build_start
    print(f"\nModel created in {build_time:.1f}s")

    pyomo_build_start = time.time()
    soft_model = model_soft_obj.build_model()
    pyomo_build_time = time.time() - pyomo_build_start
    print(f"Pyomo model built in {pyomo_build_time:.1f}s")

    # Add soft pattern with penalties
    from pyomo.environ import Var, Constraint, NonNegativeReals, Objective, minimize

    # Pattern variables (same as hard)
    soft_model.product_weekday_pattern = Var(
        pattern_index,
        within=Binary,
        doc="Suggested weekly production pattern"
    )

    # Deviation variables (NEW: track how much we deviate from pattern)
    deviation_index = [
        (node_id, product, date_val)
        for node_id in manufacturing_nodes_list
        for product in products
        for date_val in dates_range
        if (node_id, product, date_val) in soft_model.product_produced
    ]

    soft_model.pattern_deviation = Var(
        deviation_index,
        within=NonNegativeReals,
        doc="Absolute deviation from weekly pattern"
    )

    # Deviation constraints: deviation >= |produced - pattern|
    soft_model.deviation_constraint_list = ConstraintList()

    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx, date_list in weekday_dates_lists.items():
                for date_val in date_list:
                    if (node_id, product, date_val) in soft_model.product_produced:
                        produced = soft_model.product_produced[node_id, product, date_val]
                        pattern = soft_model.product_weekday_pattern[product, weekday_idx]
                        deviation = soft_model.pattern_deviation[node_id, product, date_val]

                        # deviation >= (produced - pattern)
                        soft_model.deviation_constraint_list.add(
                            deviation >= produced - pattern
                        )
                        # deviation >= (pattern - produced)
                        soft_model.deviation_constraint_list.add(
                            deviation >= pattern - produced
                        )

    # Add penalty to objective
    DEVIATION_PENALTY = 1000.0  # $1000 per deviation

    deviation_cost = sum(
        DEVIATION_PENALTY * soft_model.pattern_deviation[idx]
        for idx in deviation_index
    )

    # Deactivate original objective
    soft_model.obj.deactivate()

    # Create new objective with penalty
    soft_model.obj_with_penalty = Objective(
        expr=soft_model.obj.expr + deviation_cost,
        sense=minimize
    )

    print(f"\nSoft penalty configuration:")
    print(f"  Deviation penalty: ${DEVIATION_PENALTY:,.0f} per deviation")
    print(f"  Deviation variables: {len(deviation_index):,}")

    soft_binary, soft_integer, soft_continuous = count_variables(soft_model)
    print(f"\nVariable counts:")
    print(f"  Binary: {soft_binary:,}")
    print(f"  Integer: {soft_integer:,}")
    print(f"  Continuous: {soft_continuous:,} (+{soft_continuous - hard_continuous:,} deviation vars)")

    # Solve soft penalty model
    print("\nSolving...")

    solve_start = time.time()

    solver_soft = appsi.solvers.Highs()
    solver_soft.config.time_limit = 600
    solver_soft.config.mip_gap = 0.03
    solver_soft.config.stream_solver = False

    result_soft = solver_soft.solve(soft_model)

    soft_time = time.time() - solve_start

    soft_cost = pyo_value(soft_model.obj_with_penalty)
    soft_base_cost = pyo_value(soft_model.obj)
    soft_penalty_cost = soft_cost - soft_base_cost

    soft_gap = None
    if hasattr(result_soft, 'best_feasible_objective') and hasattr(result_soft, 'best_objective_bound'):
        best_feas = result_soft.best_feasible_objective
        best_bound = result_soft.best_objective_bound
        if best_feas and best_bound and best_feas != 0:
            soft_gap = abs((best_feas - best_bound) / best_feas)

    # Count actual deviations
    total_deviations = sum(
        pyo_value(soft_model.pattern_deviation[idx])
        for idx in deviation_index
    )

    print(f"\nSoft Penalty Results:")
    print(f"  Solve time: {soft_time:.1f}s")
    print(f"  Base cost: ${soft_base_cost:,.2f}")
    print(f"  Penalty cost: ${soft_penalty_cost:,.2f}")
    print(f"  Total cost: ${soft_cost:,.2f}")
    print(f"  Total deviations: {total_deviations:.1f}")
    if soft_gap is not None:
        print(f"  Gap: {soft_gap*100:.3f}%")

    # COMPARISON
    print("\n" + "="*80)
    print("COMPARISON")
    print("="*80)

    print(f"\nPerformance:")
    print(f"  Hard constraints: {hard_time:.1f}s")
    print(f"  Soft penalties: {soft_time:.1f}s")
    print(f"  Slowdown: {soft_time / hard_time:.2f}×")

    print(f"\nCost (base operations, excluding penalties):")
    print(f"  Hard constraints: ${hard_cost:,.2f}")
    print(f"  Soft penalties: ${soft_base_cost:,.2f}")
    cost_improvement = hard_cost - soft_base_cost
    cost_improvement_pct = (cost_improvement / hard_cost) * 100
    print(f"  Improvement: ${cost_improvement:,.2f} ({cost_improvement_pct:+.2f}%)")

    print(f"\nFlexibility:")
    print(f"  Hard constraints: 0% (must follow pattern)")
    print(f"  Soft penalties: 100% (can deviate with penalty)")
    print(f"  Actual deviations: {total_deviations:.0f} deviations chosen")

    # ANALYSIS
    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    if soft_time < 120:
        print(f"\n✅ Soft penalties are PRACTICAL ({soft_time:.0f}s < 120s target)")
    else:
        print(f"\n⚠️  Soft penalties exceeded target ({soft_time:.0f}s > 120s)")

    if cost_improvement > 0:
        print(f"✅ Soft penalties found BETTER solution (${cost_improvement:,.0f} savings)")
        print(f"   Flexibility enabled cost optimization beyond pattern constraints")
    else:
        print(f"✓  Hard constraints were already optimal")
        print(f"   Pattern space contained best solution")

    if total_deviations > 0:
        avg_deviation_cost = soft_penalty_cost / total_deviations if total_deviations > 0 else 0
        print(f"\n📊 Deviation Analysis:")
        print(f"   Total deviations: {total_deviations:.0f}")
        print(f"   Average cost per deviation: ${avg_deviation_cost:,.2f}")
        print(f"   → Deviations were worth the penalty cost")
    else:
        print(f"\n📊 No deviations chosen → Pattern was optimal")

    # RECOMMENDATION
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)

    slowdown_acceptable = soft_time < 120
    flexibility_used = total_deviations > 0
    cost_improved = cost_improvement > 0

    if slowdown_acceptable and (flexibility_used or cost_improved):
        print(f"\n✅ RECOMMENDED: Use soft pattern penalties for production planning")
        print(f"\nBenefits:")
        print(f"  - Solve time acceptable: {soft_time:.0f}s")
        print(f"  - Flexibility utilized: {total_deviations:.0f} beneficial deviations")
        if cost_improved:
            print(f"  - Cost improved: ${cost_improvement:,.0f} ({cost_improvement_pct:+.2f}%)")
        print(f"\nTrade-off: {soft_time / hard_time:.2f}× slower but finds better solutions")
    elif slowdown_acceptable:
        print(f"\n✓  Soft penalties are FEASIBLE but pattern was already optimal")
        print(f"\nObservation:")
        print(f"  - No deviations chosen (pattern space contained optimum)")
        print(f"  - Recommendation: Use hard constraints (faster, equivalent result)")
    else:
        print(f"\n⚠️  Soft penalties TOO SLOW for this problem size")
        print(f"\nRecommendation:")
        print(f"  - Use hard constraints for 4+ week horizons")
        print(f"  - Consider soft penalties for 1-2 week tactical planning")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
