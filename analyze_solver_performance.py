"""Analyze solver performance across different planning horizons.

This script:
1. Runs optimization for 1, 2, 3, 4, 6 week horizons
2. Measures solve time and model size for each
3. Graphs the results
4. Extrapolates to estimate full dataset (29 weeks) solve time
"""

import json
from datetime import date, timedelta
from typing import Dict, List, Tuple
import numpy as np
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

def run_horizon_test(
    horizon_weeks: int,
    network_parser: ExcelParser,
    full_forecast: Forecast,
    locations, routes, labor_calendar, truck_schedules, cost_structure, manufacturing_site
) -> Dict:
    """Run optimization for a specific time horizon."""

    # Calculate date range
    start_date = date(2025, 6, 2)  # First forecast date (Monday)
    end_date = start_date + timedelta(days=horizon_weeks * 7 - 1)

    # Filter forecast
    filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
    horizon_forecast = Forecast(
        name=f"{horizon_weeks} Week Test",
        entries=filtered_entries,
        creation_date=date.today()
    )

    print(f"\n{'='*70}")
    print(f"Testing {horizon_weeks} week horizon ({start_date} to {end_date})")
    print(f"{'='*70}")
    print(f"Forecast entries: {len(filtered_entries)}")

    # Build model
    print("Building model...")
    model = IntegratedProductionDistributionModel(
        forecast=horizon_forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        max_routes_per_destination=5,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    planning_days = len(model.production_dates)
    print(f"Planning days: {planning_days}")
    print(f"Routes enumerated: {len(model.enumerated_routes)}")

    # Solve
    print("Solving...")
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=120,  # 2 minute limit per test
        mip_gap=0.01,
        tee=False
    )

    print(f"Status: {result.termination_condition}")
    print(f"Solve time: {result.solve_time_seconds:.2f}s")
    if result.objective_value:
        print(f"Objective: ${result.objective_value:,.2f}")
    if result.gap:
        print(f"Gap: {result.gap*100:.2f}%")
    print(f"Variables: {result.num_variables:,}")
    print(f"Constraints: {result.num_constraints:,}")
    print(f"Integer vars: {result.num_integer_vars:,}")

    # Check if hit time limit
    hit_time_limit = result.solve_time_seconds >= 119  # Within 1 second of limit
    if hit_time_limit:
        print(f"⚠️  HIT TIME LIMIT - solver may not have finished")

    return {
        'horizon_weeks': horizon_weeks,
        'horizon_days': (end_date - start_date).days + 1,
        'planning_days': planning_days,
        'forecast_entries': len(filtered_entries),
        'solve_time_seconds': result.solve_time_seconds,
        'num_variables': result.num_variables,
        'num_constraints': result.num_constraints,
        'num_integer_vars': result.num_integer_vars,
        'objective_value': result.objective_value,
        'gap': result.gap,
        'status': result.termination_condition,
        'success': result.success,
        'hit_time_limit': hit_time_limit
    }

def main():
    print("="*70)
    print("SOLVER PERFORMANCE ANALYSIS")
    print("="*70)

    # Load data
    print("\nLoading data...")
    network_parser = ExcelParser('data/examples/Network_Config.xlsx')
    forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

    locations = network_parser.parse_locations()
    routes = network_parser.parse_routes()
    labor_calendar = network_parser.parse_labor_calendar()
    truck_schedules_list = network_parser.parse_truck_schedules()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
    cost_structure = network_parser.parse_cost_structure()
    manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
    full_forecast = forecast_parser.parse_forecast()

    # Get full forecast info
    forecast_dates = [e.forecast_date for e in full_forecast.entries]
    min_date = min(forecast_dates)
    max_date = max(forecast_dates)
    full_days = (max_date - min_date).days + 1
    full_weeks = full_days / 7.0

    print(f"Full forecast: {min_date} to {max_date}")
    print(f"Full dataset: {full_days} days ({full_weeks:.1f} weeks)")
    print(f"Total entries: {len(full_forecast.entries)}")

    # Test horizons
    horizons = [1, 2, 3, 4, 6]
    results = []

    for weeks in horizons:
        result = run_horizon_test(
            weeks, network_parser, full_forecast,
            locations, routes, labor_calendar, truck_schedules, cost_structure, manufacturing_site
        )
        results.append(result)

        # Stop if we hit time limit - larger horizons will definitely timeout
        if result['hit_time_limit']:
            print(f"\n⚠️  {weeks} week test hit time limit. Skipping larger horizons.")
            print(f"   Will extrapolate from available data points.")
            break

    # Save raw results
    with open('solver_performance_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✅ Raw results saved to: solver_performance_results.json")

    # Analyze and extrapolate
    print(f"\n{'='*70}")
    print("PERFORMANCE ANALYSIS")
    print(f"{'='*70}")

    # Extract data for analysis
    weeks_tested = [r['horizon_weeks'] for r in results]
    solve_times = [r['solve_time_seconds'] for r in results]
    num_vars = [r['num_variables'] for r in results]
    num_constraints = [r['num_constraints'] for r in results]

    # Fit polynomial models based on available data points
    # Need at least 2 points for linear, 3 for quadratic, 4 for cubic
    num_points = len(weeks_tested)

    if num_points >= 3:
        time_poly2 = np.polyfit(weeks_tested, solve_times, 2)
    else:
        time_poly2 = None

    if num_points >= 4:
        time_poly3 = np.polyfit(weeks_tested, solve_times, 3)
    else:
        time_poly3 = None

    # Also try exponential fit: time = a * exp(b * weeks)
    # Transform to linear: log(time) = log(a) + b * weeks
    log_times = np.log(solve_times)
    exp_fit = np.polyfit(weeks_tested, log_times, 1)
    exp_a = np.exp(exp_fit[1])
    exp_b = exp_fit[0]

    # Predict for full dataset
    full_weeks_rounded = int(np.ceil(full_weeks))

    pred_poly2 = np.polyval(time_poly2, full_weeks_rounded) if time_poly2 is not None else None
    pred_poly3 = np.polyval(time_poly3, full_weeks_rounded) if time_poly3 is not None else None
    pred_exp = exp_a * np.exp(exp_b * full_weeks_rounded)

    print(f"\nSolve Times by Horizon:")
    print(f"  {'Weeks':<8} {'Days':<8} {'Time (s)':<12} {'Variables':<12} {'Constraints':<12}")
    print(f"  {'-'*60}")
    for r in results:
        print(f"  {r['horizon_weeks']:<8} {r['horizon_days']:<8} {r['solve_time_seconds']:<12.2f} {r['num_variables']:<12,} {r['num_constraints']:<12,}")

    print(f"\n{'='*70}")
    print(f"EXTRAPOLATION TO FULL DATASET ({full_weeks_rounded} weeks)")
    print(f"{'='*70}")

    print(f"\nModel Predictions:")
    if pred_poly2 is not None:
        print(f"  Quadratic (degree 2):  {pred_poly2:.1f} seconds ({pred_poly2/60:.1f} minutes)")
    else:
        print(f"  Quadratic (degree 2):  N/A (need 3+ data points)")
    if pred_poly3 is not None:
        print(f"  Cubic (degree 3):      {pred_poly3:.1f} seconds ({pred_poly3/60:.1f} minutes)")
    else:
        print(f"  Cubic (degree 3):      N/A (need 4+ data points)")
    print(f"  Exponential:           {pred_exp:.1f} seconds ({pred_exp/60:.1f} minutes)")

    # Determine best model (use R-squared)
    def r_squared(actual, predicted):
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        return 1 - (ss_res / ss_tot)

    candidates = []

    if pred_poly2 is not None:
        pred_poly2_fitted = np.polyval(time_poly2, weeks_tested)
        r2_poly2 = r_squared(np.array(solve_times), pred_poly2_fitted)
        candidates.append(('Quadratic', pred_poly2, r2_poly2))
    else:
        r2_poly2 = None

    if pred_poly3 is not None:
        pred_poly3_fitted = np.polyval(time_poly3, weeks_tested)
        r2_poly3 = r_squared(np.array(solve_times), pred_poly3_fitted)
        candidates.append(('Cubic', pred_poly3, r2_poly3))
    else:
        r2_poly3 = None

    pred_exp_fitted = exp_a * np.exp(exp_b * np.array(weeks_tested))
    r2_exp = r_squared(np.array(solve_times), pred_exp_fitted)
    candidates.append(('Exponential', pred_exp, r2_exp))

    print(f"\nModel Fit Quality (R²):")
    if r2_poly2 is not None:
        print(f"  Quadratic:   {r2_poly2:.4f}")
    if r2_poly3 is not None:
        print(f"  Cubic:       {r2_poly3:.4f}")
    print(f"  Exponential: {r2_exp:.4f}")

    best_model = max(candidates, key=lambda x: x[2])

    print(f"\n🏆 Best Model: {best_model[0]} (R² = {best_model[2]:.4f})")
    print(f"   Estimated time: {best_model[1]:.1f} seconds ({best_model[1]/60:.1f} minutes)")

    if best_model[1] > 3600:
        print(f"                   {best_model[1]/3600:.1f} hours")

    # Variable and constraint scaling
    var_per_week = np.polyfit(weeks_tested, num_vars, 1)[0]
    const_per_week = np.polyfit(weeks_tested, num_constraints, 1)[0]

    est_vars = var_per_week * full_weeks_rounded + np.polyfit(weeks_tested, num_vars, 1)[1]
    est_constraints = const_per_week * full_weeks_rounded + np.polyfit(weeks_tested, num_constraints, 1)[1]

    print(f"\nEstimated Model Size for Full Dataset:")
    print(f"  Variables:   {est_vars:,.0f}")
    print(f"  Constraints: {est_constraints:,.0f}")

    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    if best_model[1] < 600:  # < 10 minutes
        print("✅ Full dataset should solve in reasonable time with CBC")
    elif best_model[1] < 1800:  # < 30 minutes
        print("⚠️  Full dataset may take significant time. Consider:")
        print("   - Using commercial solver (Gurobi/CPLEX) for 5-10x speedup")
        print("   - Increasing MIP gap tolerance (e.g., 2-5%)")
    else:
        print("❌ Full dataset will likely take too long. Strongly recommend:")
        print("   - Commercial solver (Gurobi/CPLEX) for 5-10x speedup")
        print("   - Rolling horizon planning (optimize 4-6 weeks at a time)")
        print("   - Increase MIP gap tolerance to 5-10%")
        print("   - Consider problem decomposition strategies")

    # Create visualizations
    print(f"\n{'='*70}")
    print("CREATING VISUALIZATIONS")
    print(f"{'='*70}")

    try:
        import matplotlib.pyplot as plt

        # Generate smooth prediction curves
        weeks_smooth = np.linspace(1, full_weeks_rounded, 100)
        pred_poly2_smooth = np.polyval(time_poly2, weeks_smooth) if time_poly2 is not None else None
        pred_poly3_smooth = np.polyval(time_poly3, weeks_smooth) if time_poly3 is not None else None
        pred_exp_smooth = exp_a * np.exp(exp_b * weeks_smooth)

        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        # Plot 1: Solve Time vs Horizon
        ax1 = axes[0, 0]
        ax1.scatter(weeks_tested, solve_times, s=100, color='blue', zorder=5, label='Actual')
        if pred_poly2_smooth is not None:
            ax1.plot(weeks_smooth, pred_poly2_smooth, '--', label=f'Quadratic (R²={r2_poly2:.3f})', alpha=0.7)
        if pred_poly3_smooth is not None:
            ax1.plot(weeks_smooth, pred_poly3_smooth, '--', label=f'Cubic (R²={r2_poly3:.3f})', alpha=0.7)
        ax1.plot(weeks_smooth, pred_exp_smooth, '--', label=f'Exponential (R²={r2_exp:.3f})', alpha=0.7)
        ax1.scatter([full_weeks_rounded], [best_model[1]], s=200, color='red', marker='*',
                   zorder=10, label=f'Predicted ({full_weeks_rounded}w: {best_model[1]/60:.1f}min)')
        ax1.set_xlabel('Planning Horizon (weeks)', fontsize=12)
        ax1.set_ylabel('Solve Time (seconds)', fontsize=12)
        ax1.set_title('Solver Performance vs Planning Horizon', fontsize=14, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Variables vs Horizon
        ax2 = axes[0, 1]
        ax2.scatter(weeks_tested, num_vars, s=100, color='green', zorder=5)
        var_fit = np.polyfit(weeks_tested, num_vars, 1)
        ax2.plot(weeks_smooth, np.polyval(var_fit, weeks_smooth), '--', alpha=0.7, color='green')
        ax2.scatter([full_weeks_rounded], [est_vars], s=200, color='red', marker='*',
                   zorder=10, label=f'Predicted: {est_vars:,.0f}')
        ax2.set_xlabel('Planning Horizon (weeks)', fontsize=12)
        ax2.set_ylabel('Number of Variables', fontsize=12)
        ax2.set_title('Model Variables vs Planning Horizon', fontsize=14, fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Plot 3: Constraints vs Horizon
        ax3 = axes[1, 0]
        ax3.scatter(weeks_tested, num_constraints, s=100, color='orange', zorder=5)
        const_fit = np.polyfit(weeks_tested, num_constraints, 1)
        ax3.plot(weeks_smooth, np.polyval(const_fit, weeks_smooth), '--', alpha=0.7, color='orange')
        ax3.scatter([full_weeks_rounded], [est_constraints], s=200, color='red', marker='*',
                   zorder=10, label=f'Predicted: {est_constraints:,.0f}')
        ax3.set_xlabel('Planning Horizon (weeks)', fontsize=12)
        ax3.set_ylabel('Number of Constraints', fontsize=12)
        ax3.set_title('Model Constraints vs Planning Horizon', fontsize=14, fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Plot 4: Solve Time (log scale)
        ax4 = axes[1, 1]
        ax4.scatter(weeks_tested, solve_times, s=100, color='blue', zorder=5, label='Actual')
        if pred_poly2_smooth is not None:
            ax4.plot(weeks_smooth, pred_poly2_smooth, '--', label='Quadratic', alpha=0.7)
        if pred_poly3_smooth is not None:
            ax4.plot(weeks_smooth, pred_poly3_smooth, '--', label='Cubic', alpha=0.7)
        ax4.plot(weeks_smooth, pred_exp_smooth, '--', label='Exponential', alpha=0.7)
        ax4.scatter([full_weeks_rounded], [best_model[1]], s=200, color='red', marker='*',
                   zorder=10, label=f'Predicted: {best_model[1]/60:.1f}min')
        ax4.set_xlabel('Planning Horizon (weeks)', fontsize=12)
        ax4.set_ylabel('Solve Time (seconds, log scale)', fontsize=12)
        ax4.set_title('Solver Performance (Log Scale)', fontsize=14, fontweight='bold')
        ax4.set_yscale('log')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('solver_performance_analysis.png', dpi=150, bbox_inches='tight')
        print("✅ Saved visualization: solver_performance_analysis.png")

    except ImportError:
        print("⚠️  matplotlib not available, skipping visualization")

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
