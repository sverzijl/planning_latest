"""Quick solver performance analysis with aggressive timeouts."""

import json
from datetime import date, timedelta
import numpy as np
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

def test_horizon(weeks, network_parser, full_forecast, locations, routes, labor_calendar,
                 truck_schedules, cost_structure, manufacturing_site, timeout=60):
    """Test a single horizon with aggressive timeout."""

    start_date = date(2025, 6, 2)
    end_date = start_date + timedelta(days=weeks * 7 - 1)

    filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
    horizon_forecast = Forecast(
        name=f"{weeks}W", entries=filtered_entries, creation_date=date.today()
    )

    print(f"\n{weeks} week: ", end='', flush=True)

    model = IntegratedProductionDistributionModel(
        forecast=horizon_forecast, labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site, cost_structure=cost_structure,
        locations=locations, routes=routes, truck_schedules=truck_schedules,
        max_routes_per_destination=5, allow_shortages=True, enforce_shelf_life=True,
    )

    result = model.solve(solver_name='cbc', time_limit_seconds=timeout, mip_gap=0.01, tee=False)

    print(f"{result.solve_time_seconds:.1f}s ({result.termination_condition})", flush=True)

    return {
        'weeks': weeks,
        'time': result.solve_time_seconds,
        'vars': result.num_variables,
        'constraints': result.num_constraints,
        'hit_limit': result.solve_time_seconds >= (timeout - 1)
    }

# Load data
print("Loading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

print(f"Full dataset: 204 days (29.1 weeks)")

# Test with aggressive timeouts
results = []
for weeks in [1, 2, 3, 4]:
    result = test_horizon(weeks, network_parser, full_forecast, locations, routes,
                         labor_calendar, truck_schedules, cost_structure, manufacturing_site, timeout=60)
    results.append(result)
    if result['hit_limit']:
        print(f"   ⚠️  Hit time limit, stopping at {weeks} weeks")
        break

# Analyze
print(f"\n{'='*70}")
weeks_list = [r['weeks'] for r in results]
times_list = [r['time'] for r in results]

# Fit exponential: time = a * exp(b * weeks)
log_times = np.log(times_list)
exp_fit = np.polyfit(weeks_list, log_times, 1)
a = np.exp(exp_fit[1])
b = exp_fit[0]

# Predict 29 weeks
pred_29 = a * np.exp(b * 29)

print(f"Solve Times:")
for r in results:
    print(f"  {r['weeks']:2}w: {r['time']:6.1f}s  ({r['vars']:,} vars, {r['constraints']:,} constraints)")

print(f"\nExponential fit: time = {a:.3f} * exp({b:.3f} * weeks)")
print(f"R² = {1 - np.sum((np.array(times_list) - a * np.exp(b * np.array(weeks_list)))**2) / np.sum((np.array(times_list) - np.mean(times_list))**2):.4f}")

print(f"\n{'='*70}")
print(f"EXTRAPOLATION TO 29 WEEKS")
print(f"{'='*70}")
print(f"Predicted time: {pred_29:.0f} seconds ({pred_29/60:.1f} minutes, {pred_29/3600:.2f} hours)")

if pred_29 < 600:
    print("\n✅ Should solve in <10 minutes")
elif pred_29 < 3600:
    print(f"\n⚠️  May take {pred_29/60:.0f} minutes. Recommendations:")
    print("   - Use commercial solver (Gurobi/CPLEX) for 5-10x speedup")
    print("   - Increase MIP gap to 2-5%")
else:
    print(f"\n❌ Estimated {pred_29/3600:.1f} hours is too long. Strongly recommend:")
    print("   - Commercial solver (Gurobi: 5-10x faster)")
    print("   - Rolling horizon (4-6 week windows)")
    print("   - Increase MIP gap to 5-10%")

# Visualization
try:
    import matplotlib.pyplot as plt

    weeks_smooth = np.linspace(1, 29, 100)
    pred_smooth = a * np.exp(b * weeks_smooth)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Linear scale
    ax1.scatter(weeks_list, times_list, s=100, color='blue', zorder=5, label='Actual')
    ax1.plot(weeks_smooth, pred_smooth, '--', color='orange', label=f'Exponential fit (R²={(1 - np.sum((np.array(times_list) - a * np.exp(b * np.array(weeks_list)))**2) / np.sum((np.array(times_list) - np.mean(times_list))**2)):.3f})')
    ax1.scatter([29], [pred_29], s=200, color='red', marker='*', zorder=10, label=f'29w prediction: {pred_29/60:.1f}min')
    ax1.set_xlabel('Planning Horizon (weeks)', fontsize=12)
    ax1.set_ylabel('Solve Time (seconds)', fontsize=12)
    ax1.set_title('Solver Performance vs Planning Horizon', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Log scale
    ax2.scatter(weeks_list, times_list, s=100, color='blue', zorder=5, label='Actual')
    ax2.plot(weeks_smooth, pred_smooth, '--', color='orange', label='Exponential fit')
    ax2.scatter([29], [pred_29], s=200, color='red', marker='*', zorder=10, label=f'29w: {pred_29/60:.1f}min')
    ax2.set_xlabel('Planning Horizon (weeks)', fontsize=12)
    ax2.set_ylabel('Solve Time (seconds, log scale)', fontsize=12)
    ax2.set_title('Solver Performance (Log Scale)', fontsize=14, fontweight='bold')
    ax2.set_yscale('log')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('solver_performance.png', dpi=150)
    print(f"\n✅ Saved: solver_performance.png")
except ImportError:
    print("\n⚠️  matplotlib not available")

# Save results
with open('solver_performance.json', 'w') as f:
    json.dump({
        'results': results,
        'fit': {'a': a, 'b': b},
        'prediction_29w': {'seconds': pred_29, 'minutes': pred_29/60, 'hours': pred_29/3600}
    }, f, indent=2)
print(f"✅ Saved: solver_performance.json")
