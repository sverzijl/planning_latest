#!/usr/bin/env python3
"""Test: Comprehensive Staleness Penalty Comparison

Compares:
1. Full pattern (0 weeks flexible) - baseline at 28s
2. 1-week flexible with $0.05 staleness penalty - proven at 343s
3. 1-week flexible with $0.20 staleness penalty - test if stronger gradient helps
4. 1-week flexible with NO staleness - control test

All tests with freshness_incentive_weight parameter (now used as staleness penalty).
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


def build_full_pattern_model(model_obj, products, weekday_dates_lists, manufacturing_nodes_list):
    """Build full weekly pattern model (all 6 weeks)."""
    model = model_obj.build_model()

    # Create pattern variables for ALL weeks
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

    # Deactivate all changeover constraints (all dates follow pattern)
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()

    return model


def build_1week_flexible_model(model_obj, products, dates, weekday_dates_lists, manufacturing_nodes_list):
    """Build 1-week flexible + 5-week pattern model."""
    model = model_obj.build_model()

    start_date = min(dates)
    flexible_end_date = start_date + timedelta(days=7 - 1)
    pattern_dates = [d for d in dates if d > flexible_end_date]

    # Create pattern variables
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)

    # Link pattern dates only (weeks 2-6)
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

    # Deactivate changeover constraints for pattern dates only
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            node_id, date_val = idx
            if date_val in pattern_dates:
                model.num_products_counting_con[idx].deactivate()

    return model


def run_test(test_name, model_type, staleness_weight, products, dates, weekday_dates_lists, manufacturing_nodes_list, nodes, routes, forecast, labor_calendar, truck_schedules, initial_inventory, inventory_date, start_date, end_date, cost_structure_base):
    """Run a single test configuration."""

    print(f"\n{'='*80}")
    print(f"{test_name}")
    print(f"{'='*80}")

    # Configure cost structure
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = staleness_weight

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

    # Build appropriate model
    print(f"\nBuilding {model_type} model...")
    build_start = time.time()

    if model_type == "full_pattern":
        model = build_full_pattern_model(model_obj, products, weekday_dates_lists, manufacturing_nodes_list)
    elif model_type == "1week_flexible":
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
    print(f"  Cost: ${cost:,.2f}")
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
    print("COMPREHENSIVE STALENESS PENALTY COMPARISON")
    print("="*80)
    print("\nTests:")
    print("  1. Full pattern (baseline) - 0% flexible, expected 28s")
    print("  2. 1-week flex + NO staleness - control")
    print("  3. 1-week flex + $0.05 staleness - proven 343s")
    print("  4. 1-week flex + $0.20 staleness - test stronger gradient\n")

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

    results = {}

    # TEST 1: Full pattern (baseline)
    results['full_pattern'] = run_test(
        "TEST 1: FULL PATTERN (Baseline)",
        "full_pattern", 0.05,
        products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date, cost_structure_base
    )

    # TEST 2: 1-week flexible with NO staleness
    results['1week_no_staleness'] = run_test(
        "TEST 2: 1-WEEK FLEXIBLE + NO STALENESS (Control)",
        "1week_flexible", 0.0,
        products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date, cost_structure_base
    )

    # TEST 3: 1-week flexible with $0.05 staleness
    results['1week_005'] = run_test(
        "TEST 3: 1-WEEK FLEXIBLE + $0.05 STALENESS",
        "1week_flexible", 0.05,
        products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date, cost_structure_base
    )

    # TEST 4: 1-week flexible with $0.20 staleness
    results['1week_020'] = run_test(
        "TEST 4: 1-WEEK FLEXIBLE + $0.20 STALENESS",
        "1week_flexible", 0.20,
        products, dates_range, weekday_dates_lists, manufacturing_nodes_list,
        nodes, unified_routes, forecast, labor_calendar, unified_truck_schedules,
        initial_inventory, inventory_date, start_date, end_date, cost_structure_base
    )

    # COMPREHENSIVE COMPARISON
    print(f"\n{'='*80}")
    print("COMPREHENSIVE COMPARISON")
    print(f"{'='*80}")

    print(f"\n{'Configuration':<40} {'Time':>10} {'Gap':>10} {'Status':>15}")
    print(f"{'-'*80}")

    for key, label in [
        ('full_pattern', 'Full pattern (0 flex, $0.05)'),
        ('1week_no_staleness', '1-week flex (no staleness)'),
        ('1week_005', '1-week flex ($0.05 staleness)'),
        ('1week_020', '1-week flex ($0.20 staleness)'),
    ]:
        r = results[key]
        status_str = str(r['status']).replace('TerminationCondition.', '')
        gap_str = f"{r['gap']*100:.2f}%" if r['gap'] else "N/A"
        print(f"{label:<40} {r['solve_time']:>8.1f}s {gap_str:>10} {status_str:>15}")

    # Find best 1-week flexible configuration
    print(f"\n{'='*80}")
    print("BEST 1-WEEK FLEXIBLE CONFIGURATION")
    print(f"{'='*80}")

    best_1week = min(
        [results['1week_no_staleness'], results['1week_005'], results['1week_020']],
        key=lambda x: x['solve_time']
    )

    if best_1week == results['1week_no_staleness']:
        print(f"\n✅ Best: NO staleness penalty")
        print(f"  Time: {best_1week['solve_time']:.0f}s, Gap: {best_1week['gap']*100:.2f}%")
    elif best_1week == results['1week_005']:
        print(f"\n✅ Best: $0.05 staleness penalty")
        print(f"  Time: {best_1week['solve_time']:.0f}s, Gap: {best_1week['gap']*100:.2f}%")
    else:
        print(f"\n✅ Best: $0.20 staleness penalty")
        print(f"  Time: {best_1week['solve_time']:.0f}s, Gap: {best_1week['gap']*100:.2f}%")

    # Compare best 1-week to full pattern
    print(f"\n{'='*80}")
    print("FLEXIBILITY vs PERFORMANCE TRADE-OFF")
    print(f"{'='*80}")

    full = results['full_pattern']
    best = best_1week

    slowdown = best['solve_time'] / full['solve_time']

    print(f"\nFull pattern (0% flexible):")
    print(f"  Time: {full['solve_time']:.1f}s")
    print(f"  Gap: {full['gap']*100:.2f}%")

    print(f"\n1-week flexible (17% flexible):")
    print(f"  Time: {best['solve_time']:.1f}s")
    print(f"  Gap: {best['gap']*100:.2f}%")
    print(f"  Cost of flexibility: {slowdown:.1f}× slower ({best['solve_time'] - full['solve_time']:.0f}s)")

    # Final recommendation
    print(f"\n{'='*80}")
    print("FINAL RECOMMENDATION")
    print(f"{'='*80}")

    if best['solve_time'] < 120:  # 2 minutes
        print(f"\n🎉 RECOMMENDED: Use 1-week flexible for 6-week planning")
        print(f"\nConfiguration:")
        if best == results['1week_no_staleness']:
            print(f"  - No staleness penalty needed")
        elif best == results['1week_005']:
            print(f"  - Staleness penalty: $0.05/unit/day")
        else:
            print(f"  - Staleness penalty: $0.20/unit/day")
        print(f"  - Week 1: Fully flexible")
        print(f"  - Weeks 2-6: Weekly pattern")
        print(f"\nPerformance:")
        print(f"  - Solve time: {best['solve_time']:.0f}s ({best['solve_time']/60:.1f} minutes)")
        print(f"  - {slowdown:.1f}× slower than full pattern (acceptable)")
        print(f"\nValue:")
        print(f"  - Operational flexibility in week 1")
        print(f"  - Long-term tractability in weeks 2-6")
    elif best['solve_time'] < 360:  # 6 minutes
        print(f"\n✓  1-week flexible is ACCEPTABLE but slower than ideal")
        print(f"\nPerformance:")
        print(f"  - Solve time: {best['solve_time']:.0f}s ({best['solve_time']/60:.1f} minutes)")
        print(f"  - {slowdown:.1f}× slower than full pattern")
        print(f"\nDecision:")
        print(f"  - Use if week 1 flexibility is critical")
        print(f"  - Otherwise stick with full pattern (28s)")
    else:
        print(f"\n⚠️  Full pattern is still better choice")
        print(f"\nReason: 1-week flexible too slow ({best['solve_time']:.0f}s)")
        print(f"Recommendation: Use full pattern (28s) with manual overrides")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
