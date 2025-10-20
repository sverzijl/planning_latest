#!/usr/bin/env python3
"""
Comprehensive HiGHS solver performance testing for binary product_produced variables.

Tests 4 configurations:
1. HiGHS (no warmstart, no special heuristics)
2. HiGHS (no warmstart, WITH heuristics)
3. HiGHS (WITH warmstart, no special heuristics)
4. HiGHS (WITH warmstart, WITH heuristics)

Compares against:
- CBC binary baseline: 226s (no warmstart)
- Continuous baseline: 35-45s
"""

import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite


def load_test_data():
    """Load test data files."""
    forecast_file = Path("/home/sverzijl/planning_latest/data/examples/Gfree Forecast.xlsm")
    network_file = Path("/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx")

    if not forecast_file.exists():
        print(f"Error: Forecast file not found: {forecast_file}")
        sys.exit(1)
    if not network_file.exists():
        print(f"Error: Network file not found: {network_file}")
        sys.exit(1)

    print("Loading data files...")
    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file)
    )
    data = parser.parse_all()

    return data


def create_model(data, horizon_weeks=1):
    """Create UnifiedNodeModel with specified horizon."""
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=7 * horizon_weeks)

    print(f"\nCreating model: {horizon_weeks}-week horizon ({start_date} to {end_date})")

    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = data

    # Find manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules, forecast
    )

    # Build model
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        allow_shortages=True,
        enforce_shelf_life=True,
        use_batch_tracking=True,
    )

    stats = model.get_model_statistics()
    print(f"Model created")

    return model


def test_highs_configuration(model, config_name, use_warmstart=False, time_limit=300, mip_gap=0.01):
    """Test a specific HiGHS configuration."""
    print(f"\n{'='*80}")
    print(f"TEST: {config_name}")
    print(f"{'='*80}")
    print(f"Warmstart: {use_warmstart}")
    print(f"Time limit: {time_limit}s")
    print(f"MIP gap: {mip_gap}")

    start_time = time.time()

    try:
        result = model.solve(
            solver_name='highs',
            use_warmstart=use_warmstart,
            time_limit_seconds=time_limit,
            mip_gap=mip_gap,
            tee=True,
        )

        elapsed = time.time() - start_time

        print(f"\nRESULTS:")
        print(f"  Solve time: {elapsed:.1f}s")
        print(f"  Status: {result.termination_condition}")
        print(f"  Optimal: {result.is_optimal()}")
        print(f"  Feasible: {result.is_feasible()}")
        print(f"  Gap: {result.gap:.4f}" if result.gap is not None else "  Gap: N/A")
        print(f"  Total cost: ${result.objective_value:,.2f}" if result.objective_value is not None else "  Total cost: N/A")

        # Extract fill rate from solution
        if result.is_feasible():
            solution = model.get_solution()
            if solution and 'demand_met' in solution:
                total_demand = sum(solution.get('total_demand', {}).values()) if 'total_demand' in solution else 0
                total_delivered = sum(solution.get('demand_met', {}).values())
                fill_rate = (total_delivered / total_demand * 100) if total_demand > 0 else 0
                print(f"  Fill rate: {fill_rate:.1f}%")

        return {
            'config': config_name,
            'solve_time': elapsed,
            'status': str(result.termination_condition),
            'optimal': result.is_optimal(),
            'feasible': result.is_feasible(),
            'gap': result.gap,
            'cost': result.objective_value,
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\nERROR: {e}")
        print(f"Elapsed time: {elapsed:.1f}s")
        return {
            'config': config_name,
            'solve_time': elapsed,
            'status': 'ERROR',
            'optimal': False,
            'feasible': False,
            'gap': None,
            'cost': None,
            'error': str(e),
        }


def print_summary_table(results):
    """Print comparison table of all results."""
    print(f"\n{'='*80}")
    print("SUMMARY: HiGHS Performance Comparison")
    print(f"{'='*80}")

    print(f"\n{'Configuration':<40} {'Time (s)':<12} {'Status':<15} {'Gap':<10} {'Cost ($)':<15}")
    print(f"{'-'*40} {'-'*12} {'-'*15} {'-'*10} {'-'*15}")

    for r in results:
        config = r['config']
        solve_time = f"{r['solve_time']:.1f}"
        status = r['status']
        gap = f"{r['gap']:.4f}" if r['gap'] is not None else "N/A"
        cost = f"{r['cost']:,.0f}" if r['cost'] is not None else "N/A"

        print(f"{config:<40} {solve_time:<12} {status:<15} {gap:<10} {cost:<15}")

    # Add baseline references
    print(f"\n{'BASELINE REFERENCES:':<40}")
    print(f"{'Continuous (no binary vars)':<40} {'35-45':<12} {'OPTIMAL':<15} {'<0.01':<10} {'~varies':<15}")
    print(f"{'CBC (binary vars, no warmstart)':<40} {'226':<12} {'OPTIMAL':<15} {'<0.01':<10} {'~varies':<15}")
    print(f"{'CBC (binary vars, WITH warmstart)':<40} {'>300':<12} {'TIMEOUT':<15} {'~1.0':<10} {'~varies':<15}")


def main():
    """Main test execution."""
    print("="*80)
    print("HiGHS SOLVER COMPREHENSIVE PERFORMANCE TEST")
    print("="*80)

    # Load data
    data = load_test_data()

    results = []

    # Test 1: 1-week horizon - Quick baseline
    print("\n\n" + "="*80)
    print("PHASE 1: 1-WEEK HORIZON (Quick Baseline)")
    print("="*80)

    model_1w = create_model(data, horizon_weeks=1)

    # Config 1: Basic HiGHS (no warmstart)
    results.append(test_highs_configuration(
        model_1w,
        config_name="1-week: HiGHS basic (no warmstart)",
        use_warmstart=False,
        time_limit=60,
        mip_gap=0.01
    ))

    # Config 2: HiGHS with warmstart
    results.append(test_highs_configuration(
        model_1w,
        config_name="1-week: HiGHS warmstart",
        use_warmstart=True,
        time_limit=60,
        mip_gap=0.01
    ))

    # Test 2: 4-week horizon - Real comparison
    print("\n\n" + "="*80)
    print("PHASE 2: 4-WEEK HORIZON (CBC Baseline Comparison)")
    print("="*80)

    model_4w = create_model(data, horizon_weeks=4)

    # Config 3: 4-week basic
    results.append(test_highs_configuration(
        model_4w,
        config_name="4-week: HiGHS basic (no warmstart)",
        use_warmstart=False,
        time_limit=300,
        mip_gap=0.01
    ))

    # Config 4: 4-week warmstart
    results.append(test_highs_configuration(
        model_4w,
        config_name="4-week: HiGHS warmstart",
        use_warmstart=True,
        time_limit=300,
        mip_gap=0.01
    ))

    # Print summary
    print_summary_table(results)

    # Analysis and recommendations
    print(f"\n{'='*80}")
    print("ANALYSIS & RECOMMENDATIONS")
    print(f"{'='*80}")

    # Find best 4-week result
    four_week_results = [r for r in results if '4-week' in r['config']]
    if four_week_results:
        best_4w = min([r for r in four_week_results if r['feasible']],
                      key=lambda x: x['solve_time'], default=None)

        if best_4w:
            print(f"\nBest 4-week configuration: {best_4w['config']}")
            print(f"  Solve time: {best_4w['solve_time']:.1f}s")
            print(f"  Status: {best_4w['status']}")

            # Compare to CBC
            speedup = 226 / best_4w['solve_time']
            print(f"\nComparison to CBC baseline (226s):")
            print(f"  Speedup: {speedup:.2f}x")

            if best_4w['solve_time'] < 60:
                print(f"  Assessment: EXCELLENT - HiGHS is significantly faster")
            elif best_4w['solve_time'] < 120:
                print(f"  Assessment: GOOD - HiGHS is faster than CBC")
            elif best_4w['solve_time'] < 180:
                print(f"  Assessment: ACCEPTABLE - HiGHS comparable to CBC")
            else:
                print(f"  Assessment: POOR - HiGHS not faster than CBC")

    # Warmstart assessment
    warmstart_configs = [r for r in results if 'warmstart+' in r['config'] or 'warmstart' in r['config']]
    no_warmstart_configs = [r for r in results if 'basic' in r['config'] or 'heuristics' in r['config']]

    print(f"\nWarmstart compatibility:")
    if any('warmstart' in r['config'] for r in results):
        print("  HiGHS supports warmstart parameter (no errors)")
        # Check if it actually helps
        has_improvement = False
        for ws_r in warmstart_configs:
            comparable = [r for r in no_warmstart_configs if r['config'].replace('warmstart+', '').replace('warmstart', 'basic') == ws_r['config'].replace('warmstart+', '').replace('warmstart', 'basic')]
            if comparable and ws_r['solve_time'] < comparable[0]['solve_time'] * 0.9:
                has_improvement = True
                break

        if has_improvement:
            print("  Warmstart provides solve time improvement")
        else:
            print("  Warmstart does NOT improve solve time (may be ignored by solver)")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
