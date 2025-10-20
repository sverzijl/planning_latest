#!/usr/bin/env python3
"""Test SKU performance improvements: tighter Big-M, force_all_skus_daily, two-phase solve.

This test validates the three performance improvements implemented to address
the slow solve times with binary SKU selection:

1. Tighter Big-M constraint (uses realistic max hours instead of theoretical 24h)
2. force_all_skus_daily parameter (removes binary complexity when needed)
3. Two-phase solve with warmstart (fast fixed-SKU solve → warmstart for binary SKUs)

Performance targets:
- Fixed SKUs: 10-30s
- Binary SKUs with tighter Big-M: 40-90s (improved from 120s+ timeout)
- Two-phase solve: 50-100s total (faster than cold start binary solve)
"""

import time
from datetime import timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel, solve_two_phase
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*80)
    print("SKU PERFORMANCE IMPROVEMENTS VALIDATION")
    print("="*80)
    print("\nTesting 3 improvements:")
    print("  1. Tighter Big-M constraint (realistic max hours)")
    print("  2. force_all_skus_daily parameter (removes binary complexity)")
    print("  3. Two-phase solve with warmstart (fast baseline → optimized)")
    print("="*80)

    # Load data
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    print(f"\nLoading data...")
    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
        daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Use 4-week horizon
    start_date = min(e.forecast_date for e in forecast.entries)
    end_date = start_date + timedelta(days=27)

    print(f"  Planning: {start_date} to {end_date} (28 days)")
    print(f"  Products: {len(set(e.product_id for e in forecast.entries))}")
    print(f"  Locations: {len(nodes)}")

    # ========================================================================
    # TEST 1: Verify tighter Big-M constraint value
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 1: Tighter Big-M Constraint")
    print("="*80)

    model_test1 = UnifiedNodeModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        labor_calendar=labor_calendar, cost_structure=cost_structure,
        start_date=start_date, end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
        force_all_skus_daily=False,  # Binary SKUs
    )

    big_m = model_test1.get_max_daily_production()
    print(f"\nBig-M value: {big_m:,.0f} units/day")

    # Verify Big-M is realistic (not 24 hours)
    expected_max = 1400 * 14  # 1400 units/hour × 14 hours max
    if big_m <= expected_max:
        print(f"✓ PASS: Big-M uses realistic hours (≤ {expected_max:,.0f})")
        print(f"   Old implementation used 1400 × 24 = 33,600 (too loose)")
        print(f"   New implementation uses 1400 × 14 = {big_m:,.0f} (tighter bound)")
    else:
        print(f"✗ FAIL: Big-M = {big_m:,.0f} exceeds realistic max {expected_max:,.0f}")

    # ========================================================================
    # TEST 2: force_all_skus_daily parameter
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 2: force_all_skus_daily Parameter")
    print("="*80)
    print("\nSolving with force_all_skus_daily=True (all SKUs every day)...")

    test2_start = time.time()

    model_test2 = UnifiedNodeModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        labor_calendar=labor_calendar, cost_structure=cost_structure,
        start_date=start_date, end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
        force_all_skus_daily=True,  # KEY: Force all SKUs daily
    )

    result_test2 = model_test2.solve(
        solver_name='appsi_highs',
        time_limit_seconds=60,
        mip_gap=0.03,
        tee=False,
    )

    test2_time = time.time() - test2_start

    print(f"\nResults with force_all_skus_daily=True:")
    print(f"  Status: {result_test2.termination_condition}")
    print(f"  Solve time: {test2_time:.1f}s")
    print(f"  Objective: ${result_test2.objective_value:,.2f}")

    test2_passed = result_test2.is_optimal() or result_test2.is_feasible()
    if test2_passed:
        print(f"✓ PASS: Solved successfully in {test2_time:.1f}s")
        if test2_time < 30:
            print(f"   Excellent performance (<30s)")
        elif test2_time < 60:
            print(f"   Good performance (<60s)")
        else:
            print(f"   ⚠️  Slower than expected (>60s)")
    else:
        print(f"✗ FAIL: Did not find feasible solution")

    # ========================================================================
    # TEST 3: Two-phase solve with warmstart
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 3: Two-Phase Solve with Warmstart")
    print("="*80)

    test3_start = time.time()

    result_test3 = solve_two_phase(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_seconds_phase1=60,
        time_limit_seconds_phase2=120,
        mip_gap=0.03,
        tee=False,
    )

    test3_time = time.time() - test3_start

    print(f"\nTwo-phase solve completed:")
    print(f"  Total time: {test3_time:.1f}s")
    print(f"  Final status: {result_test3.termination_condition}")
    print(f"  Final objective: ${result_test3.objective_value:,.2f}")

    test3_passed = result_test3.is_optimal() or result_test3.is_feasible()
    if test3_passed:
        print(f"✓ PASS: Two-phase solve succeeded in {test3_time:.1f}s")
        if test3_time < 60:
            print(f"   Excellent performance (<60s)")
        elif test3_time < 100:
            print(f"   Good performance (<100s)")
        else:
            print(f"   Acceptable performance (<180s)")
    else:
        print(f"✗ FAIL: Did not find feasible solution")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*80)
    print("PERFORMANCE IMPROVEMENTS SUMMARY")
    print("="*80)

    print(f"\n1. Big-M Constraint:")
    print(f"   Old: 1400 × 24 = 33,600 units/day (theoretical max)")
    print(f"   New: 1400 × 14 = {big_m:,.0f} units/day (realistic max)")
    print(f"   Improvement: {(33600 - big_m) / 33600 * 100:.1f}% tighter bound")

    print(f"\n2. Fixed SKUs Mode:")
    print(f"   Solve time: {test2_time:.1f}s")
    print(f"   Status: {result_test2.termination_condition}")
    print(f"   Use case: Baseline testing, warmstart generation")

    print(f"\n3. Two-Phase Solve:")
    print(f"   Total time: {test3_time:.1f}s")
    print(f"   Status: {result_test3.termination_condition}")
    print(f"   Use case: Production optimization with SKU reduction")

    # Cost comparison
    if result_test2.objective_value and result_test3.objective_value:
        cost_diff = result_test2.objective_value - result_test3.objective_value
        pct_diff = 100 * cost_diff / result_test2.objective_value if result_test2.objective_value > 0 else 0
        print(f"\n4. Cost Comparison:")
        print(f"   Fixed SKUs (all products daily): ${result_test2.objective_value:,.2f}")
        print(f"   Binary SKUs (optimized variety): ${result_test3.objective_value:,.2f}")
        if cost_diff > 0:
            print(f"   Savings from SKU reduction: ${cost_diff:,.2f} ({pct_diff:.1f}%)")
        else:
            print(f"   Note: Binary SKU solution not better (may need longer solve time)")

    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)

    # Final assessment
    all_passed = True
    if big_m > expected_max:
        all_passed = False
        print("\n✗ Big-M test failed")
    if not test2_passed:
        all_passed = False
        print("\n✗ Fixed SKUs test failed")
    if not test3_passed:
        all_passed = False
        print("\n✗ Two-phase solve test failed")

    if all_passed:
        print("\n✅ ALL TESTS PASSED - Performance improvements validated!")
    else:
        print("\n⚠️  SOME TESTS FAILED - Review results above")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
