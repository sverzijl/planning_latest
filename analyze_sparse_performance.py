"""Performance analysis with sparse indexing - compare with baseline."""

import json
from datetime import date, timedelta
import numpy as np
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

def test_horizon(weeks, network_parser, full_forecast, locations, routes, labor_calendar,
                 truck_schedules, cost_structure, manufacturing_site, timeout=120):
    """Test a single horizon."""

    start_date = date(2025, 6, 2)
    end_date = start_date + timedelta(days=weeks * 7 - 1)

    filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
    horizon_forecast = Forecast(
        name=f"{weeks}W", entries=filtered_entries, creation_date=date.today()
    )

    print(f"\n{'='*70}")
    print(f"{weeks} WEEK TEST ({start_date} to {end_date})")
    print(f"{'='*70}")
    print(f"Forecast entries: {len(filtered_entries)}")

    # Build model
    model_obj = IntegratedProductionDistributionModel(
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

    pyomo_model = model_obj.build_model()

    # Get model stats
    num_vars = pyomo_model.nvariables()
    num_cons = pyomo_model.nconstraints()
    num_int = sum(1 for v in pyomo_model.component_data_objects(Var) if v.is_binary())
    truck_load_vars = sum(1 for v in pyomo_model.component_data_objects(Var) if 'truck_load' in str(v))

    print(f"Model size: {num_vars:,} vars, {num_cons:,} constraints, {num_int:,} binary")
    print(f"  truck_load: {truck_load_vars:,} vars")

    # Solve
    print(f"Solving (timeout: {timeout}s)...")
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=timeout,
        mip_gap=0.01,
        tee=False
    )

    print(f"Status: {result.termination_condition}")
    print(f"Solve time: {result.solve_time_seconds:.2f}s")
    if result.objective_value:
        print(f"Objective: ${result.objective_value:,.2f}")
    if result.gap:
        print(f"Gap: {result.gap*100:.2f}%")

    hit_limit = result.solve_time_seconds >= (timeout - 1)
    if hit_limit:
        print(f"⚠️  HIT TIME LIMIT")

    return {
        'weeks': weeks,
        'time': result.solve_time_seconds,
        'vars': num_vars,
        'constraints': num_cons,
        'truck_load_vars': truck_load_vars,
        'objective': result.objective_value,
        'status': str(result.termination_condition),
        'hit_limit': hit_limit
    }

# Load data
print("="*70)
print("SPARSE INDEXING PERFORMANCE ANALYSIS")
print("="*70)

network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

forecast_dates = [e.forecast_date for e in full_forecast.entries]
full_weeks = (max(forecast_dates) - min(forecast_dates)).days / 7.0
print(f"\nFull dataset: {full_weeks:.1f} weeks (204 days)")

# Test horizons with 60s timeout each
print(f"\nTesting with 60s timeout per horizon...")
horizons = [1, 2, 3, 4]
results = []

for weeks in horizons:
    result = test_horizon(weeks, network_parser, full_forecast, locations, routes,
                         labor_calendar, truck_schedules, cost_structure, manufacturing_site, timeout=60)
    results.append(result)

    if result['hit_limit'] and weeks >= 3:
        print(f"\n⚠️  {weeks} week test hit limit. Stopping here to save time...")
        break

# Save results
with open('sparse_performance_results.json', 'w') as f:
    json.dump({'results': results}, f, indent=2, default=str)

print(f"\n{'='*70}")
print("PERFORMANCE SUMMARY")
print(f"{'='*70}")

print(f"\n{'Weeks':<8} {'Time (s)':<12} {'Variables':<12} {'truck_load':<12} {'Status':<12}")
print(f"{'-'*60}")
for r in results:
    status_str = 'optimal' if 'optimal' in r['status'] else ('time_limit' if r['hit_limit'] else r['status'][:10])
    print(f"{r['weeks']:<8} {r['time']:<12.2f} {r['vars']:<12,} {r['truck_load_vars']:<12,} {status_str:<12}")

# Load baseline (if exists)
baseline_file = 'solver_performance_results.json'
try:
    with open(baseline_file, 'r') as f:
        baseline_data = json.load(f)
        baseline_results = baseline_data.get('results', [])

    print(f"\n{'='*70}")
    print("COMPARISON WITH BASELINE (Dense Indexing)")
    print(f"{'='*70}")

    print(f"\n{'Weeks':<8} {'Dense Vars':<12} {'Sparse Vars':<12} {'Reduction':<12} {'Dense Time':<12} {'Sparse Time':<12} {'Speedup':<10}")
    print(f"{'-'*90}")

    for r in results:
        # Find matching baseline
        baseline = next((b for b in baseline_results if b.get('horizon_weeks') == r['weeks']), None)
        if baseline:
            dense_vars = baseline.get('num_variables', 0)
            sparse_vars = r['vars']
            var_reduction = ((dense_vars - sparse_vars) / dense_vars * 100) if dense_vars > 0 else 0

            dense_time = baseline.get('solve_time_seconds', 0)
            sparse_time = r['time']
            speedup = dense_time / sparse_time if sparse_time > 0 else 0

            print(f"{r['weeks']:<8} {dense_vars:<12,} {sparse_vars:<12,} {var_reduction:<11.1f}% "
                  f"{dense_time:<12.2f} {sparse_time:<12.2f} {speedup:<9.2f}x")

except FileNotFoundError:
    print(f"\nℹ️  No baseline file found at {baseline_file}")
    print(f"   Run the original analysis first to compare")

# Extrapolate
print(f"\n{'='*70}")
print("EXTRAPOLATION TO 29 WEEKS")
print(f"{'='*70}")

weeks_list = [r['weeks'] for r in results if not r['hit_limit']]
times_list = [r['time'] for r in results if not r['hit_limit']]

if len(times_list) >= 2:
    # Fit exponential
    log_times = np.log(times_list)
    exp_fit = np.polyfit(weeks_list, log_times, 1)
    a = np.exp(exp_fit[1])
    b = exp_fit[0]

    pred_29 = a * np.exp(b * 29)

    r2 = 1 - np.sum((np.array(times_list) - a * np.exp(b * np.array(weeks_list)))**2) / np.sum((np.array(times_list) - np.mean(times_list))**2)

    print(f"\nExponential fit: time = {a:.3f} × exp({b:.3f} × weeks)")
    print(f"R² = {r2:.4f}")
    print(f"\nPredicted solve time for 29 weeks:")
    print(f"  {pred_29:.0f} seconds")
    print(f"  {pred_29/60:.1f} minutes")
    if pred_29 > 3600:
        print(f"  {pred_29/3600:.2f} hours")

    # Compare with baseline if available
    try:
        baseline_pred = 11557813982587  # From earlier analysis
        improvement = baseline_pred / pred_29
        print(f"\nImprovement over baseline:")
        print(f"  Baseline prediction: {baseline_pred/3600:.0f} hours")
        print(f"  Sparse prediction:   {pred_29/3600:.2f} hours")
        print(f"  Improvement factor:  {improvement:.1e}x")
    except:
        pass

    # Recommendations
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    if pred_29 < 600:
        print(f"\n✅ 29 weeks may be solvable in <10 minutes")
        print(f"   Sparse indexing makes full dataset feasible with CBC!")
    elif pred_29 < 1800:
        print(f"\n⚠️  29 weeks estimated at {pred_29/60:.0f} minutes")
        print(f"   Consider:")
        print(f"   - Commercial solver (Gurobi/CPLEX) for 5-10x speedup")
        print(f"   - Rolling horizon (4-6 weeks) for guaranteed solve time")
    else:
        print(f"\n❌ 29 weeks still too long ({pred_29/3600:.1f} hours)")
        print(f"   Strongly recommend:")
        print(f"   - Rolling horizon (4-6 weeks): ~4-6 minutes total")
        print(f"   - Add symmetry breaking for additional 3-5x speedup")
        print(f"   - Commercial solver for best performance")
else:
    print(f"\n⚠️  Not enough data points for reliable extrapolation")

print(f"\n{'='*70}")
print(f"✅ Analysis complete!")
print(f"   Results saved to: sparse_performance_results.json")
print(f"{'='*70}")
