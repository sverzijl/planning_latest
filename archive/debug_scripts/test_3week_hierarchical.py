"""Test 3-week hierarchical windows: weeks 1-2 daily, week 3 aggregated."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.time_period import VariableGranularityConfig, BucketGranularity
from src.optimization import RollingHorizonSolver
import time
from datetime import datetime

print("=" * 90)
print("3-WEEK HIERARCHICAL WINDOW COMPARISON")
print("=" * 90)
print(f"\nStart time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Load data
print("\nLoading data...")
load_start = time.time()

network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

load_time = time.time() - load_start
print(f"Data loaded in {load_time:.2f}s")

print(f"\nFull Dataset:")
print(f"  Total demand: {sum(e.quantity for e in full_forecast.entries):,.0f} units")
forecast_dates = sorted(set(e.forecast_date for e in full_forecast.entries))
total_days = (forecast_dates[-1] - forecast_dates[0]).days + 1
print(f"  Date range: {forecast_dates[0]} to {forecast_dates[-1]} ({total_days} days)")

# Define configurations
configs = [
    {
        "name": "Baseline: 14d window, 7d overlap, all daily",
        "window_size": 14,
        "overlap": 7,
        "granularity_config": None,
        "description": "Current proven configuration",
    },
    {
        "name": "Option A: 21d window, 14d overlap, hierarchical",
        "window_size": 21,
        "overlap": 14,
        "granularity_config": VariableGranularityConfig(
            near_term_days=14,
            near_term_granularity=BucketGranularity.DAILY,
            far_term_granularity=BucketGranularity.WEEKLY
        ),
        "description": "Weeks 1-2 daily (14d), week 3 weekly bucket (7d), 2-week overlap",
    },
    {
        "name": "Option B: 21d window, 7d overlap, hierarchical",
        "window_size": 21,
        "overlap": 7,
        "granularity_config": VariableGranularityConfig(
            near_term_days=14,
            near_term_granularity=BucketGranularity.DAILY,
            far_term_granularity=BucketGranularity.WEEKLY
        ),
        "description": "Weeks 1-2 daily (14d), week 3 weekly bucket (7d), 1-week overlap",
    },
]

results = []

print("\n" + "=" * 90)
print("TESTING CONFIGURATIONS")
print("=" * 90)

for i, config in enumerate(configs, 1):
    print(f"\n{'=' * 90}")
    print(f"CONFIGURATION {i}/3: {config['name']}")
    print(f"{'=' * 90}")
    print(f"  {config['description']}")
    print(f"  Window size: {config['window_size']} days")
    print(f"  Overlap: {config['overlap']} days")
    print(f"  Committed: {config['window_size'] - config['overlap']} days per window")

    if config['granularity_config']:
        gc = config['granularity_config']
        print(f"  Granularity:")
        print(f"    - First {gc.near_term_days} days: {gc.near_term_granularity.value}")
        print(f"    - Remaining days: {gc.far_term_granularity.value}")
        total_periods = gc.near_term_days + ((config['window_size'] - gc.near_term_days) // gc.far_term_granularity.days)
        print(f"    - Total periods per window: ~{total_periods} (vs {config['window_size']} daily)")
    else:
        print(f"  Granularity: Daily (all {config['window_size']} days)")

    print(f"\nSolving...")

    solver = RollingHorizonSolver(
        window_size_days=config['window_size'],
        overlap_days=config['overlap'],
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    solve_start = time.time()
    result = solver.solve(
        forecast=full_forecast,
        granularity_config=config['granularity_config'],
        solver_name='cbc',
        verbose=False
    )
    solve_time = time.time() - solve_start

    result_data = {
        "name": config['name'],
        "window_size": config['window_size'],
        "overlap": config['overlap'],
        "committed": config['window_size'] - config['overlap'],
        "granularity": "Hierarchical" if config['granularity_config'] else "Daily",
        "num_windows": result.num_windows,
        "feasible_windows": result.num_windows - len(result.infeasible_windows),
        "infeasible_windows": len(result.infeasible_windows),
        "feasibility_rate": (result.num_windows - len(result.infeasible_windows)) / result.num_windows * 100,
        "all_feasible": result.all_feasible,
        "total_cost": result.total_cost if result.all_feasible else None,
        "total_time": solve_time,
        "avg_time_per_window": solve_time / result.num_windows,
    }
    results.append(result_data)

    status = "✅ ALL FEASIBLE" if result.all_feasible else f"❌ {result_data['feasibility_rate']:.0f}% FEASIBLE"
    print(f"\n{'=' * 90}")
    print(f"RESULTS - CONFIGURATION {i}/3")
    print(f"{'=' * 90}")
    print(f"  Status: {status}")
    print(f"  Windows: {result.num_windows}")
    print(f"  Feasible: {result_data['feasible_windows']}/{result.num_windows}")
    if result.all_feasible:
        print(f"  Total cost: ${result.total_cost:,.2f}")
    else:
        print(f"  Infeasible windows: {result.infeasible_windows}")
    print(f"  Total time: {solve_time:.2f}s")
    print(f"  Avg time/window: {result_data['avg_time_per_window']:.2f}s")
    print(f"  Completed at: {datetime.now().strftime('%H:%M:%S')}")

# Results summary
print("\n" + "=" * 90)
print("FINAL COMPARISON")
print("=" * 90)

print(f"\n{'Configuration':<45} {'Windows':<10} {'Feasible':<12} {'Cost':<18} {'Time':<12} {'Status'}")
print("-" * 110)

for r in results:
    name = r['name'][:44]
    windows = str(r['num_windows'])
    feasible = f"{r['feasible_windows']}/{r['num_windows']}"
    cost = f"${r['total_cost']:,.2f}" if r['all_feasible'] else "N/A"
    time_str = f"{r['total_time']:.1f}s"
    status = "✅ 100%" if r['all_feasible'] else f"❌ {r['feasibility_rate']:.0f}%"

    print(f"{name:<45} {windows:<10} {feasible:<12} {cost:<18} {time_str:<12} {status}")

# Analysis
print("\n" + "=" * 90)
print("ANALYSIS")
print("=" * 90)

feasible_results = [r for r in results if r['all_feasible']]

if len(feasible_results) == 0:
    print("\n❌ No feasible configurations! All failed.")
elif len(feasible_results) < len(results):
    print(f"\n⚠ Only {len(feasible_results)}/{len(results)} configurations are fully feasible!")
    print(f"   Feasible: {[r['name'] for r in feasible_results]}")
else:
    print(f"\n✅ All {len(feasible_results)} configurations achieved 100% feasibility!")

if len(feasible_results) >= 2:
    # Cost comparison
    best_cost = min(feasible_results, key=lambda x: x['total_cost'])
    worst_cost = max(feasible_results, key=lambda x: x['total_cost'])

    print(f"\n💰 COST COMPARISON:")
    print(f"   Best: ${best_cost['total_cost']:,.2f} ({best_cost['name']})")
    print(f"   Worst: ${worst_cost['total_cost']:,.2f} ({worst_cost['name']})")

    if best_cost['total_cost'] != worst_cost['total_cost']:
        savings = worst_cost['total_cost'] - best_cost['total_cost']
        savings_pct = (savings / worst_cost['total_cost']) * 100
        print(f"   Savings: ${savings:,.2f} ({savings_pct:.2f}%)")
    else:
        print(f"   All configurations have identical cost!")

    # Time comparison
    fastest = min(feasible_results, key=lambda x: x['total_time'])
    slowest = max(feasible_results, key=lambda x: x['total_time'])

    print(f"\n⚡ SOLVE TIME COMPARISON:")
    print(f"   Fastest: {fastest['total_time']:.1f}s ({fastest['name']})")
    print(f"   Slowest: {slowest['total_time']:.1f}s ({slowest['name']})")

    if fastest['total_time'] != slowest['total_time']:
        time_diff = slowest['total_time'] - fastest['total_time']
        time_pct = (time_diff / slowest['total_time']) * 100
        print(f"   Difference: {time_diff:.1f}s ({time_pct:.1f}% faster)")

    # Window count comparison
    min_windows = min(feasible_results, key=lambda x: x['num_windows'])
    max_windows = max(feasible_results, key=lambda x: x['num_windows'])

    print(f"\n📊 WINDOW COUNT:")
    print(f"   Fewest: {min_windows['num_windows']} windows ({min_windows['name']})")
    print(f"   Most: {max_windows['num_windows']} windows ({max_windows['name']})")

    # Overall recommendation
    print(f"\n{'=' * 90}")
    print("RECOMMENDATION")
    print(f"{'=' * 90}")

    if best_cost == results[0]:
        print(f"\n✅ STAY WITH BASELINE: {results[0]['name']}")
        print(f"   The baseline configuration already provides the best cost.")
        print(f"   Hierarchical configurations add complexity without benefit.")
    else:
        print(f"\n🎯 SWITCH TO: {best_cost['name']}")
        print(f"   Cost savings: ${worst_cost['total_cost'] - best_cost['total_cost']:,.2f}")
        print(f"   Time trade-off: {best_cost['total_time'] - results[0]['total_time']:.1f}s " +
              ("slower" if best_cost['total_time'] > results[0]['total_time'] else "faster"))
        print(f"   Recommendation: {'Worth it' if (worst_cost['total_cost'] - best_cost['total_cost']) > 1000 else 'Marginal benefit'}")

print(f"\n{'=' * 90}")
print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'=' * 90}")
