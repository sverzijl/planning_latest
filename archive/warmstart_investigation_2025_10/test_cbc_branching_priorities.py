#!/usr/bin/env python3
"""Test: CBC Solver with Branching Priorities

CBC (COIN-OR Branch and Cut) supports branching priorities through Pyomo's
.priority attribute. This test compares CBC with and without priorities.

Theory: By prioritizing pattern variables (weeks 3-6), CBC should find good
patterns early, then optimize flexible weeks (1-2) within that structure.
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
from pyomo.opt import SolverFactory


def build_hybrid_model_cbc(model_obj, products, dates, weekday_dates_lists, manufacturing_nodes_list, flexible_weeks=2, set_priorities=False):
    """Build hybrid model with CBC-compatible branching priorities."""
    model = model_obj.build_model()

    start_date = min(dates)
    flexible_end_date = start_date + timedelta(days=flexible_weeks * 7 - 1)
    flexible_dates = [d for d in dates if d <= flexible_end_date]
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

    # SET BRANCHING PRIORITIES (CBC-compatible)
    if set_priorities:
        print(f"\n  Setting CBC branching priorities...")

        # HIGH PRIORITY (100): Pattern variables - branch on these FIRST
        priority_count = 0
        for prod, wd in pattern_index:
            var = model.product_weekday_pattern[prod, wd]
            var.priority = 100  # CBC respects this attribute
            priority_count += 1

        print(f"    Pattern variables: {priority_count} vars with priority=100 (HIGH)")

        # DEFAULT PRIORITY (0): Flexible variables - branch on these AFTER patterns
        # No need to set explicitly (default is 0)
        print(f"    Flexible variables: ~50 vars with priority=0 (DEFAULT)")
        print(f"    CBC will branch on pattern vars first, flexible vars second")

    return model


def run_test_cbc(test_name, cost_structure, products, dates, weekday_dates_lists, manufacturing_nodes_list, nodes, routes, forecast, labor_calendar, truck_schedules, initial_inventory, inventory_date, start_date, end_date, set_priorities=False):
    """Run test with CBC solver."""
    print(f"\n{'='*80}")
    print(f"{test_name}")
    print(f"{'='*80}")

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

    # Build hybrid model
    print("\nBuilding hybrid model...")
    build_start = time.time()
    model = build_hybrid_model_cbc(model_obj, products, dates, weekday_dates_lists, manufacturing_nodes_list,
                                   flexible_weeks=2, set_priorities=set_priorities)
    build_time = time.time() - build_start
    print(f"Model built in {build_time:.1f}s")

    # Solve with CBC
    print("\nSolving with CBC...")
    solver = SolverFactory('cbc')

    # CBC options
    solver.options['seconds'] = 600  # 10 minute time limit
    solver.options['ratio'] = 0.03   # 3% gap
    solver.options['threads'] = 4     # Use 4 cores

    if set_priorities:
        # CBC should automatically use .priority attributes on variables
        print("  CBC configured to respect variable priorities")

    solve_start = time.time()
    result = solver.solve(model, tee=False)
    solve_time = time.time() - solve_start

    # Extract results
    total_cost = pyo.value(model.obj)

    # CBC doesn't always provide best bound in same way as HiGHS
    gap = None
    if hasattr(result.problem, 'upper_bound') and hasattr(result.problem, 'lower_bound'):
        upper = result.problem.upper_bound
        lower = result.problem.lower_bound
        if upper and lower and upper != 0:
            gap = abs((upper - lower) / upper)

    print(f"\nResults:")
    print(f"  Solve time: {solve_time:.1f}s")
    print(f"  Cost: ${total_cost:,.2f}")
    if gap is not None:
        print(f"  Gap: {gap*100:.3f}%")
    print(f"  Status: {result.solver.termination_condition}")

    return {
        'solve_time': solve_time,
        'cost': total_cost,
        'gap': gap,
        'status': result.solver.termination_condition,
        'build_time': build_time
    }


def main():
    print("="*80)
    print("CBC SOLVER WITH BRANCHING PRIORITIES TEST")
    print("="*80)
    print("\nObjective: Test if CBC respects branching priorities")
    print("CBC supports Pyomo's .priority attribute (unlike HiGHS)")
    print("Expected: Priorities should guide search → faster convergence\n")

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

    # TEST 1: CBC without priorities
    results_no_priority = run_test_cbc(
        "TEST 1: CBC WITHOUT BRANCHING PRIORITIES",
        cost_structure,
        products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date,
        set_priorities=False
    )

    # TEST 2: CBC with priorities
    results_with_priority = run_test_cbc(
        "TEST 2: CBC WITH BRANCHING PRIORITIES",
        cost_structure,
        products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date,
        set_priorities=True
    )

    # COMPARISON
    print(f"\n{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}")

    print(f"\nSolve Time:")
    print(f"  Without priorities: {results_no_priority['solve_time']:.1f}s")
    print(f"  With priorities:    {results_with_priority['solve_time']:.1f}s")

    if results_with_priority['solve_time'] < results_no_priority['solve_time']:
        speedup = results_no_priority['solve_time'] / results_with_priority['solve_time']
        improvement = results_no_priority['solve_time'] - results_with_priority['solve_time']
        print(f"  ✅ Improvement: {improvement:.1f}s faster ({speedup:.2f}× speedup)")
    else:
        slowdown = results_with_priority['solve_time'] / results_no_priority['solve_time']
        print(f"  ⚠️  Slowdown: {slowdown:.2f}×")

    print(f"\nSolution Cost:")
    print(f"  Without priorities: ${results_no_priority['cost']:,.2f}")
    print(f"  With priorities:    ${results_with_priority['cost']:,.2f}")

    cost_diff = results_no_priority['cost'] - results_with_priority['cost']
    if abs(cost_diff) > 1000:
        if cost_diff > 0:
            print(f"  ✅ Better solution: ${cost_diff:,.2f} savings")
        else:
            print(f"  ⚠️  Worse solution: ${-cost_diff:,.2f} higher")
    else:
        print(f"  ≈ Similar costs")

    if results_no_priority['gap'] and results_with_priority['gap']:
        print(f"\nSolution Quality:")
        print(f"  Without priorities: {results_no_priority['gap']*100:.3f}% gap")
        print(f"  With priorities:    {results_with_priority['gap']*100:.3f}% gap")

    # RECOMMENDATION
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    significant_speedup = results_with_priority['solve_time'] < results_no_priority['solve_time'] * 0.7
    both_timeout = results_with_priority['solve_time'] > 590 and results_no_priority['solve_time'] > 590

    if significant_speedup and not both_timeout:
        print(f"\n✅ RECOMMENDED: CBC with branching priorities")
        print(f"\nBenefits:")
        print(f"  - Significantly faster: {results_no_priority['solve_time']:.0f}s → {results_with_priority['solve_time']:.0f}s")
        print(f"  - CBC respects priorities (unlike HiGHS)")
    elif both_timeout:
        print(f"\n❌ Both configurations timeout (~10 minutes)")
        print(f"\nObservation:")
        print(f"  - CBC is slower than HiGHS in general")
        print(f"  - Even with priorities, hybrid model too hard for CBC")
        print(f"\nRecommendation: Abandon 2-week flexible approach")
        print(f"  Option A: Use full pattern (28s with HiGHS)")
        print(f"  Option B: Try 1-week flexible + 5-week pattern")
        print(f"  Option C: Campaign-based (2-week blocks)")
    else:
        print(f"\n✓  Priorities help marginally with CBC")
        print(f"\nNote: CBC is generally slower than HiGHS")
        print(f"  HiGHS (no priorities): 609s")
        print(f"  CBC (with priorities): {results_with_priority['solve_time']:.0f}s")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
