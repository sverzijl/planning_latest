"""Compare different overlap configurations for 14-day windows to find optimal cost."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver
import time
from datetime import datetime

print("=" * 80)
print("OVERLAP COMPARISON: 14-DAY WINDOWS WITH VARYING OVERLAP")
print("=" * 80)
print(f"\nStart time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Load data once
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

# Define configurations to test
configs = [
    {"overlap": 3, "committed": 11, "description": "Minimal overlap"},
    {"overlap": 5, "committed": 9, "description": "Small overlap"},
    {"overlap": 7, "committed": 7, "description": "Current baseline"},
    {"overlap": 9, "committed": 5, "description": "Large overlap"},
    {"overlap": 11, "committed": 3, "description": "Very large overlap"},
]

results = []

print("\n" + "=" * 80)
print("TESTING CONFIGURATIONS")
print("=" * 80)

for i, config in enumerate(configs, 1):
    overlap = config["overlap"]
    committed = config["committed"]
    desc = config["description"]

    print(f"\n{'=' * 80}")
    print(f"CONFIGURATION {i}/5: {overlap}-DAY OVERLAP ({desc})")
    print(f"{'=' * 80}")
    print(f"  Window size: 14 days")
    print(f"  Overlap: {overlap} days")
    print(f"  Committed: {committed} days per window")
    print(f"  Expected windows: ~{total_days // committed}")
    print(f"\nSolving...")

    solver = RollingHorizonSolver(
        window_size_days=14,
        overlap_days=overlap,
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
        solver_name='cbc',
        verbose=False  # Suppress per-window output for cleaner comparison
    )
    solve_time = time.time() - solve_start

    # Store results
    result_data = {
        "overlap": overlap,
        "committed": committed,
        "description": desc,
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

    # Print immediate results
    print(f"\n{'=' * 80}")
    print(f"RESULTS - CONFIGURATION {i}/5")
    print(f"{'=' * 80}")
    print(f"  Status: {'✅ ALL FEASIBLE' if result.all_feasible else '❌ SOME INFEASIBLE'}")
    print(f"  Windows: {result.num_windows}")
    print(f"  Feasible: {result.num_windows - len(result.infeasible_windows)} ({result_data['feasibility_rate']:.1f}%)")
    print(f"  Infeasible: {len(result.infeasible_windows)}")
    if result.all_feasible:
        print(f"  Total cost: ${result.total_cost:,.2f}")
    else:
        print(f"  Total cost: N/A (infeasible)")
        print(f"  Infeasible windows: {result.infeasible_windows}")
    print(f"  Total time: {solve_time:.2f}s")
    print(f"  Avg time/window: {result_data['avg_time_per_window']:.2f}s")
    print(f"  Completed at: {datetime.now().strftime('%H:%M:%S')}")

# Final comparison
print("\n" + "=" * 80)
print("FINAL COMPARISON - ALL CONFIGURATIONS")
print("=" * 80)

print(f"\n{'Overlap':<8} {'Committed':<10} {'Windows':<9} {'Feasible':<10} {'Total Cost':<18} {'Total Time':<12} {'Avg Time/Win':<12} {'Status':<10}")
print("-" * 120)

for r in results:
    overlap_str = f"{r['overlap']}d"
    committed_str = f"{r['committed']}d"
    windows_str = f"{r['num_windows']}"
    feasible_str = f"{r['feasible_windows']}/{r['num_windows']}"
    cost_str = f"${r['total_cost']:,.2f}" if r['all_feasible'] else "N/A"
    time_str = f"{r['total_time']:.2f}s"
    avg_time_str = f"{r['avg_time_per_window']:.2f}s"
    status_str = "✅ 100%" if r['all_feasible'] else f"❌ {r['feasibility_rate']:.0f}%"

    print(f"{overlap_str:<8} {committed_str:<10} {windows_str:<9} {feasible_str:<10} {cost_str:<18} {time_str:<12} {avg_time_str:<12} {status_str:<10}")

# Find optimal configuration
feasible_results = [r for r in results if r['all_feasible']]

if feasible_results:
    print("\n" + "=" * 80)
    print("OPTIMIZATION SUMMARY")
    print("=" * 80)

    # Best cost
    best_cost = min(feasible_results, key=lambda x: x['total_cost'])
    print(f"\n✅ BEST COST: {best_cost['overlap']}-day overlap")
    print(f"   Cost: ${best_cost['total_cost']:,.2f}")
    print(f"   Windows: {best_cost['num_windows']}")
    print(f"   Time: {best_cost['total_time']:.2f}s ({best_cost['avg_time_per_window']:.2f}s/window)")

    # Fastest solve
    fastest = min(feasible_results, key=lambda x: x['total_time'])
    print(f"\n⚡ FASTEST SOLVE: {fastest['overlap']}-day overlap")
    print(f"   Time: {fastest['total_time']:.2f}s ({fastest['avg_time_per_window']:.2f}s/window)")
    print(f"   Cost: ${fastest['total_cost']:,.2f}")

    # Cost comparison
    if len(feasible_results) > 1:
        worst_cost = max(feasible_results, key=lambda x: x['total_cost'])
        cost_range = worst_cost['total_cost'] - best_cost['total_cost']
        cost_pct = (cost_range / worst_cost['total_cost']) * 100

        print(f"\n📊 COST VARIANCE:")
        print(f"   Best: ${best_cost['total_cost']:,.2f} ({best_cost['overlap']}-day overlap)")
        print(f"   Worst: ${worst_cost['total_cost']:,.2f} ({worst_cost['overlap']}-day overlap)")
        print(f"   Range: ${cost_range:,.2f} ({cost_pct:.2f}% variation)")

    print(f"\n{'=' * 80}")
    print(f"RECOMMENDATION: Use {best_cost['overlap']}-day overlap for optimal cost")
    print(f"{'=' * 80}")
else:
    print("\n❌ No fully feasible configurations found!")

print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
