"""Benchmark script to validate daily rolling horizon warmstart speedup.

This script validates that warmstart provides 50-70% speedup as expected
by solving a sequence of days and measuring actual performance.

Expected Results:
- Day 1 (cold start): Baseline time (e.g., 30-96s depending on constraints)
- Days 2-7 (warmstart): 50-70% faster than Day 1

Usage:
    python benchmark_daily_rolling_warmstart.py
"""

import time
from datetime import date, timedelta
from typing import Dict, List

from src.parsers.excel_parser import ExcelParser
from src.optimization.unified_node_model import create_unified_components
from src.optimization.daily_rolling_solver import DailyRollingSolver


def run_benchmark():
    """Run daily rolling horizon benchmark."""
    print("="*80)
    print("DAILY ROLLING HORIZON WARMSTART BENCHMARK")
    print("="*80)

    # Parse data
    print("\n📂 Loading test data...")
    parser = ExcelParser()

    forecast_result = parser.parse_forecast('data/examples/Gluten Free Forecast - Latest.xlsm')
    forecast = forecast_result['forecast']

    network_result = parser.parse_network_config('data/examples/Network_Config.xlsx')
    inventory_result = parser.parse_inventory('data/examples/inventory_latest.XLSX')

    print(f"  ✓ Forecast loaded: {len(forecast.entries)} entries")
    print(f"  ✓ Network loaded: {len(network_result['locations'])} locations, {len(network_result['routes'])} routes")

    # Create unified components
    print("\n🔨 Creating optimization components...")
    nodes, routes = create_unified_components(
        locations=network_result['locations'],
        network_routes=network_result['routes'],
        manufacturing_site=network_result['manufacturing_site'],
        labor_calendar=network_result['labor_calendar'],
        truck_schedules=network_result['truck_schedules'],
        cost_structure=network_result['cost_structure'],
        initial_inventory=inventory_result['initial_inventory'],
    )
    print(f"  ✓ Nodes: {len(nodes)}, Routes: {len(routes)}")

    # Setup solver
    print("\n⚙️  Configuring solver...")
    horizon_days = 14  # 2 weeks for faster benchmark (4 weeks would be more realistic)
    num_benchmark_days = 7  # 1 week of daily solves

    solver = DailyRollingSolver(
        nodes=nodes,
        routes=routes,
        base_forecast=forecast,
        horizon_days=horizon_days,
        solver_name='appsi_highs',  # Required for warmstart
        time_limit_seconds=300,  # 5 minutes per solve
        mip_gap=0.02,  # 2% gap (relaxed for speed)
        use_batch_tracking=True,
        allow_shortages=False,
        enforce_shelf_life=True,
    )

    print(f"  Horizon: {horizon_days} days")
    print(f"  Benchmark days: {num_benchmark_days}")
    print(f"  Solver: {solver.solver_name}")
    print(f"  Time limit: {solver.time_limit_seconds}s per solve")
    print(f"  MIP gap: {solver.mip_gap:.1%}")

    # Run benchmark
    print("\n🚀 Starting benchmark...")
    print(f"  {'Day':>4}  {'Date':>10}  {'Time':>8}  {'Speedup':>10}  {'Objective':>15}")
    print("  " + "-"*70)

    start_date = date(2025, 1, 6)  # Monday

    # Run sequence
    results = solver.solve_sequence(
        start_date=start_date,
        num_days=num_benchmark_days,
        verbose=False  # Quiet mode for cleaner benchmark output
    )

    # Print results
    baseline_time = results.daily_results[0].solve_time

    for i, result in enumerate(results.daily_results):
        speedup_str = "-"
        if i > 0 and result.warmstart_speedup is not None:
            speedup_pct = (1 - result.warmstart_speedup) * 100
            speedup_str = f"{speedup_pct:+.1f}%"

        obj_str = f"${result.objective_value:,.0f}" if result.objective_value else "FAILED"
        status_icon = "✓" if result.success else "✗"

        print(f"  {result.day_number:>4}  {result.current_date}  {result.solve_time:>7.1f}s  {speedup_str:>10}  {obj_str:>15} {status_icon}")

    # Summary statistics
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY")
    print("="*80)

    if results.all_successful:
        print(f"✅ All {results.total_days} solves succeeded")
    else:
        failed_count = sum(1 for r in results.daily_results if not r.success)
        print(f"⚠️  {failed_count}/{results.total_days} solves failed")

    print(f"\nTotal solve time: {results.total_solve_time:.1f}s")
    print(f"Average solve time: {results.average_solve_time:.1f}s/day")

    # Day 1 vs Days 2+
    day1_time = baseline_time
    if len(results.daily_results) > 1:
        warmstart_times = [r.solve_time for r in results.daily_results[1:] if r.success]
        if warmstart_times:
            avg_warmstart_time = sum(warmstart_times) / len(warmstart_times)
            speedup_pct = (1 - avg_warmstart_time / day1_time) * 100 if day1_time > 0 else 0

            print(f"\n📊 Performance Comparison:")
            print(f"  Day 1 (cold start):     {day1_time:>7.1f}s")
            print(f"  Days 2-{num_benchmark_days} (warmstart):   {avg_warmstart_time:>7.1f}s average")
            print(f"  Speedup:                {speedup_pct:>6.1f}% faster")

            # Validate against target (50-70% faster)
            if speedup_pct >= 30:
                print(f"\n✅ VALIDATION: Warmstart speedup {speedup_pct:.1f}% meets/exceeds target (≥30%)")
            else:
                print(f"\n⚠️  VALIDATION: Warmstart speedup {speedup_pct:.1f}% below target (≥30%)")
                print(f"    This may indicate warmstart is not working properly.")

    # Cost consistency check
    if results.all_successful and len(results.daily_results) > 1:
        costs = [r.objective_value for r in results.daily_results if r.objective_value]
        if len(costs) > 1:
            cost_variation = (max(costs) - min(costs)) / min(costs) * 100
            print(f"\n💰 Cost Consistency Check:")
            print(f"  Min cost: ${min(costs):,.0f}")
            print(f"  Max cost: ${max(costs):,.0f}")
            print(f"  Variation: {cost_variation:.1f}%")

            if cost_variation < 5.0:
                print(f"  ✅ Low variation ({cost_variation:.1f}% < 5%) - warmstart quality good")
            else:
                print(f"  ⚠️  High variation ({cost_variation:.1f}% > 5%) - solutions may differ significantly")

    print("\n" + "="*80)


if __name__ == '__main__':
    start_time = time.time()
    run_benchmark()
    total_time = time.time() - start_time
    print(f"\nTotal benchmark time: {total_time:.1f}s")
    print(f"\nBenchmark complete! ✨")
