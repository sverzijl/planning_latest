"""Example: Daily rolling horizon with warmstart for production planning.

This script demonstrates how to use the DailyRollingSolver for daily
re-optimization with warmstart to achieve 50-70% faster solve times.

Usage:
    python example_daily_rolling_horizon.py
"""

from datetime import date
from src.parsers.excel_parser import ExcelParser
from src.optimization.unified_node_model import create_unified_components
from src.optimization.daily_rolling_solver import DailyRollingSolver


def main():
    """Example daily rolling horizon workflow."""

    print("=" * 80)
    print("DAILY ROLLING HORIZON EXAMPLE")
    print("=" * 80)

    # Load data
    print("\n1. Loading data...")
    parser = ExcelParser()

    forecast_result = parser.parse_forecast('data/examples/Gluten Free Forecast - Latest.xlsm')
    network_result = parser.parse_network_config('data/examples/Network_Config.xlsx')
    inventory_result = parser.parse_inventory('data/examples/inventory_latest.XLSX')

    print("   ✓ Data loaded")

    # Create optimization components
    print("\n2. Creating optimization components...")
    nodes, routes = create_unified_components(
        locations=network_result['locations'],
        network_routes=network_result['routes'],
        manufacturing_site=network_result['manufacturing_site'],
        labor_calendar=network_result['labor_calendar'],
        truck_schedules=network_result['truck_schedules'],
        cost_structure=network_result['cost_structure'],
        initial_inventory=inventory_result['initial_inventory'],
    )
    print(f"   ✓ Created {len(nodes)} nodes, {len(routes)} routes")

    # Setup daily rolling solver
    print("\n3. Configuring solver...")
    solver = DailyRollingSolver(
        nodes=nodes,
        routes=routes,
        base_forecast=forecast_result['forecast'],
        horizon_days=14,  # 2-week horizon (faster for demo)
        solver_name='appsi_highs',  # Required for warmstart
        time_limit_seconds=180,  # 3 minutes max per solve
        mip_gap=0.02,  # 2% gap (relaxed for speed)
        use_batch_tracking=True,
        allow_shortages=False,
        enforce_shelf_life=True,
    )
    print("   ✓ Solver configured (2-week horizon, APPSI HiGHS)")

    # Solve 3 days to demonstrate warmstart
    print("\n4. Solving 3 days with warmstart...")
    print("   (Day 1 = cold start, Days 2-3 = warmstart)")
    print()

    results = solver.solve_sequence(
        start_date=date(2025, 1, 6),  # Monday
        num_days=3,
        verbose=True  # Show detailed progress
    )

    # Show results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    if results.all_successful:
        print("\n✅ All solves succeeded!")

        # Performance summary
        day1_time = results.daily_results[0].solve_time
        if len(results.daily_results) > 1:
            avg_warmstart = sum(r.solve_time for r in results.daily_results[1:]) / (len(results.daily_results) - 1)
            speedup_pct = (1 - avg_warmstart / day1_time) * 100 if day1_time > 0 else 0

            print(f"\n📊 Performance:")
            print(f"   Day 1 (cold start): {day1_time:>6.1f}s")
            print(f"   Days 2-3 (warmstart): {avg_warmstart:>6.1f}s average")
            print(f"   Speedup: {speedup_pct:>6.1f}% faster")

            if speedup_pct >= 30:
                print(f"\n✨ Excellent! Warmstart achieved {speedup_pct:.1f}% speedup (target: ≥30%)")
            else:
                print(f"\n⚠️  Speedup {speedup_pct:.1f}% below target (≥30%)")

        # Cost summary
        print(f"\n💰 Costs:")
        for r in results.daily_results:
            print(f"   Day {r.day_number} ({r.current_date}): ${r.objective_value:,.0f}")
    else:
        print("\n❌ Some solves failed")
        for r in results.daily_results:
            status = "✓" if r.success else "✗"
            print(f"   Day {r.day_number}: {status} {r.termination_condition}")

    print("\n" + "=" * 80)
    print("\nNext steps:")
    print("  • Run benchmark_daily_rolling_warmstart.py for full validation")
    print("  • See docs/features/daily_rolling_horizon.md for usage guide")
    print("  • Integrate into your daily planning workflow")
    print()


if __name__ == '__main__':
    main()
