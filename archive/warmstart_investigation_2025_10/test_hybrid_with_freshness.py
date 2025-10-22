#!/usr/bin/env python3
"""Test: Hybrid Model with Freshness Incentive

Compares hybrid flexible-pattern model performance:
1. WITHOUT freshness incentive (baseline: 611s timeout)
2. WITH freshness incentive (expected: 150-300s with better convergence)

Theory (MIP expert): Freshness incentive breaks symmetry by providing preference
ordering for inventory cohorts, guiding solver toward better solutions faster.
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


def build_hybrid_model(model_obj, products, dates, weekday_dates_lists, manufacturing_nodes_list, flexible_weeks=2):
    """Build hybrid model (2 weeks flexible + 4 weeks pattern)."""
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

    return model


def run_test(test_name, cost_structure, products, dates, weekday_dates_lists, manufacturing_nodes_list, nodes, routes, forecast, labor_calendar, truck_schedules, initial_inventory, inventory_date, start_date, end_date):
    """Run a single test configuration."""
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
    model = build_hybrid_model(model_obj, products, dates, weekday_dates_lists, manufacturing_nodes_list, flexible_weeks=2)
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
    print(f"  Cost: ${cost:,.2f}")
    if gap is not None:
        print(f"  Gap: {gap*100:.3f}%")
    print(f"  Status: {result.termination_condition}")

    return {
        'solve_time': solve_time,
        'cost': cost,
        'gap': gap,
        'status': result.termination_condition,
        'build_time': build_time
    }


def main():
    print("="*80)
    print("HYBRID MODEL WITH FRESHNESS INCENTIVE TEST")
    print("="*80)
    print("\nObjective: Test if freshness incentive improves hybrid model performance")
    print("Baseline: 611s (timeout) without freshness")
    print("Expected: 150-300s with freshness (2-4× faster)")

    # Load data
    print("\n" + "="*80)
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

    # TEST 1: WITHOUT freshness incentive (baseline)
    cost_structure_no_fresh = cost_structure_base.model_copy()
    cost_structure_no_fresh.freshness_incentive_weight = 0.0

    results_baseline = run_test(
        "TEST 1: WITHOUT FRESHNESS INCENTIVE (Baseline)",
        cost_structure_no_fresh,
        products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date
    )

    # TEST 2: WITH freshness incentive
    cost_structure_with_fresh = cost_structure_base.model_copy()
    cost_structure_with_fresh.freshness_incentive_weight = 0.05  # $0.05 per unit per day remaining

    results_freshness = run_test(
        "TEST 2: WITH FRESHNESS INCENTIVE ($0.05/unit/day)",
        cost_structure_with_fresh,
        products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date
    )

    # COMPARISON
    print(f"\n{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}")

    print(f"\nSolve Time:")
    print(f"  Without freshness: {results_baseline['solve_time']:.1f}s")
    print(f"  With freshness:    {results_freshness['solve_time']:.1f}s")

    if results_freshness['solve_time'] < results_baseline['solve_time']:
        speedup = results_baseline['solve_time'] / results_freshness['solve_time']
        improvement = results_baseline['solve_time'] - results_freshness['solve_time']
        print(f"  Improvement: {improvement:.1f}s faster ({speedup:.2f}× speedup)")
        print(f"  ✅ Freshness incentive IMPROVED performance!")
    else:
        slowdown = results_freshness['solve_time'] / results_baseline['solve_time']
        print(f"  Slowdown: {slowdown:.2f}×")
        print(f"  ⚠️  Freshness incentive did not help")

    print(f"\nSolution Quality:")
    print(f"  Without freshness: ${results_baseline['cost']:,.2f} ({results_baseline['gap']*100:.3f}% gap)")
    print(f"  With freshness:    ${results_freshness['cost']:,.2f} ({results_freshness['gap']*100:.3f}% gap)")

    # Cost comparison (note: freshness changes objective, so absolute cost not directly comparable)
    print(f"\n  Note: Costs not directly comparable (freshness changes objective function)")

    # RECOMMENDATION
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    if results_freshness['solve_time'] < 300 and results_freshness['solve_time'] < results_baseline['solve_time']:
        print(f"\n✅ RECOMMENDED: Enable freshness incentive for hybrid model")
        print(f"\nBenefits:")
        print(f"  - Faster solve time: {results_freshness['solve_time']:.0f}s vs {results_baseline['solve_time']:.0f}s")
        print(f"  - Better convergence: {results_freshness['gap']*100:.2f}% gap")
        print(f"  - Business value: Encourages FIFO/FEFO behavior")
        print(f"\nConfiguration: freshness_incentive_weight = 0.05")
    elif results_freshness['solve_time'] < results_baseline['solve_time']:
        print(f"\n✓  Freshness incentive helps but solution still slow")
        print(f"\nObservation:")
        print(f"  - Improved from {results_baseline['solve_time']:.0f}s to {results_freshness['solve_time']:.0f}s")
        print(f"  - Still slower than target (<300s)")
        print(f"\nConsider: Reduce flexible window to 1 week")
    else:
        print(f"\n❌ Freshness incentive did NOT improve performance")
        print(f"\nPossible reasons:")
        print(f"  - Freshness coefficient too large (adding numerical difficulty)")
        print(f"  - Problem structure doesn't benefit from freshness gradient")
        print(f"\nTry: Lower freshness weight (0.01 instead of 0.05)")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
