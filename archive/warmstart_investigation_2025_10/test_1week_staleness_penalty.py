#!/usr/bin/env python3
"""Test: 1-Week Flexible with Staleness Penalty

Tests staleness PENALTY formulation (additive) vs previous freshness BONUS (subtractive).

MIP Theory: Additive penalty provides better LP relaxation than subtractive bonus:
- Penalty keeps objective positive → Stronger LP bounds → Lower gap
- Simpler calculation: min(age_days, 17) → Better numerical stability
- Same preference ordering: Avoid old inventory

Configuration:
- Week 1: Fully flexible
- Weeks 2-6: Weekly pattern
- Staleness: PENALTY for old products (not bonus for fresh)

Expected: Better gap convergence → Possible to solve in <600s
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
    model = model_obj.build_model()

    start_date = min(dates)
    flexible_end_date = start_date + timedelta(days=7 - 1)  # 1 week
    pattern_dates = [d for d in dates if d > flexible_end_date]

    # Create pattern variables
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)

    # Link pattern dates only
    model.weekly_pattern_linking = pyo.ConstraintList()
    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                pattern_week_dates = [d for d in weekday_dates_lists[weekday_idx] if d in pattern_dates]
                for date_val in pattern_week_dates:
                    if (node_id, product, date_val) in model.product_produced:
                        model.weekly_pattern_linking.add(
                            model.product_produced[node_id, product, date_val] ==
                            model.product_weekday_pattern[product, weekday_idx]
                        )

    # Deactivate conflicting constraints for pattern dates
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            node_id, date_val = idx
            if date_val in pattern_dates:
                model.num_products_counting_con[idx].deactivate()

    return model


def run_test(penalty_weight, products, dates, weekday_dates_lists, manufacturing_nodes_list, nodes, routes, forecast, labor_calendar, truck_schedules, initial_inventory, inventory_date, start_date, end_date, cost_structure_base):
    """Run test with specific staleness penalty weight."""

    print(f"\n{'='*80}")
    print(f"TESTING: Staleness Penalty = ${penalty_weight:.2f}/unit/day")
    print(f"{'='*80}")

    # Configure staleness penalty
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = penalty_weight

    # Create model
    model_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,
    )

    # Build model
    print("\nBuilding model...")
    build_start = time.time()
    model = build_1week_flexible_model(model_obj, products, dates, weekday_dates_lists, manufacturing_nodes_list)
    build_time = time.time() - build_start
    print(f"Model built in {build_time:.1f}s")

    # Solve
    print("\nSolving...")
    solver = appsi.solvers.Highs()
    solver.config.time_limit = 600
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = False

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

    print(f"\nResults:")
    print(f"  Solve time: {solve_time:.1f}s")
    print(f"  Cost (with staleness): ${cost:,.2f}")
    if gap is not None:
        print(f"  Gap: {gap*100:.3f}%")
    print(f"  Status: {result.termination_condition}")

    return {
        'solve_time': solve_time,
        'cost': cost,
        'gap': gap,
        'status': result.termination_condition
    }


def main():
    print("="*80)
    print("1-WEEK FLEXIBLE WITH STALENESS PENALTY TEST")
    print("="*80)
    print("\nFormulation: PENALTY (additive) not BONUS (subtractive)")
    print("Formula: staleness = min(age_days, 17) × weight × demand_satisfied")
    print("Expected: Better LP relaxation → Lower gap → Faster convergence\n")

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

    # Test multiple penalty weights
    print("\n" + "="*80)
    print("TESTING MULTIPLE PENALTY WEIGHTS")
    print("="*80)

    # TEST 1: Moderate penalty ($0.05)
    result_005 = run_test(
        0.05, products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date, cost_structure_base
    )

    # TEST 2: Higher penalty ($0.20) - only if Test 1 timed out
    if result_005['solve_time'] >= 590:  # Near timeout
        print("\n" + "="*80)
        print("Test 1 approached timeout - trying stronger penalty...")
        print("="*80)

        result_020 = run_test(
            0.20, products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
            nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
            initial_inventory, inventory_date, start_date, end_date, cost_structure_base
        )
    else:
        result_020 = None
        print(f"\n✅ Test 1 solved successfully - no need to test higher penalty")

    # SUMMARY
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    print(f"\nBaseline (freshness BONUS, 1-week flexible):")
    print(f"  Solve time: 611s (timeout)")
    print(f"  Cost: $691,599")
    print(f"  Gap: 5.4%")

    print(f"\nStaleness PENALTY Results:")
    print(f"\n  $0.05 penalty:")
    print(f"    Solve time: {result_005['solve_time']:.1f}s")
    print(f"    Cost: ${result_005['cost']:,.2f}")
    print(f"    Gap: {result_005['gap']*100:.3f}%")

    if result_020:
        print(f"\n  $0.20 penalty:")
        print(f"    Solve time: {result_020['solve_time']:.1f}s")
        print(f"    Cost: ${result_020['cost']:,.2f}")
        print(f"    Gap: {result_020['gap']*100:.3f}%")

    # Recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    best_result = result_005
    best_penalty = 0.05

    if result_020 and result_020['solve_time'] < result_005['solve_time']:
        best_result = result_020
        best_penalty = 0.20

    if best_result['solve_time'] < 300:  # 5 minutes
        print(f"\n🎉 SUCCESS: Staleness penalty WORKS!")
        print(f"\nBest configuration:")
        print(f"  Staleness penalty: ${best_penalty:.2f}/unit/day")
        print(f"  Solve time: {best_result['solve_time']:.0f}s")
        print(f"  Gap: {best_result['gap']*100:.1f}%")
        print(f"\n✅ 1-week flexible is now PRACTICAL for 6-week planning")
    elif best_result['solve_time'] < 600:  # Hit timeout
        print(f"\n⚠️  IMPROVEMENT but still slow")
        print(f"\nResults:")
        print(f"  Solved in {best_result['solve_time']:.0f}s (vs 611s with bonus)")
        improvement = 611 - best_result['solve_time']
        print(f"  Improvement: {improvement:.0f}s faster")
        print(f"\nDecision: Marginal improvement, consider alternatives")
    else:
        print(f"\n❌ Still timing out at 600s")
        print(f"\nConclusion: Even with penalty formulation, hybrid approach too hard")
        print(f"Recommendation: Use full pattern (28s) or reduce to 4-week horizon")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
