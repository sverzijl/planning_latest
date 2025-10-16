"""Test fine-grained overlap values around 7-day to find the feasibility boundary."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver
import time
from datetime import datetime

print("=" * 80)
print("FINE-GRAINED OVERLAP COMPARISON: 14-DAY WINDOWS (4-10 DAY OVERLAPS)")
print("=" * 80)
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

# Test overlaps from 4 to 10 days to find the boundary
configs = [
    {"overlap": 4, "committed": 10},
    {"overlap": 5, "committed": 9},
    {"overlap": 6, "committed": 8},
    {"overlap": 7, "committed": 7},  # Known to work
    {"overlap": 8, "committed": 6},
    {"overlap": 9, "committed": 5},
    {"overlap": 10, "committed": 4},
]

results = []

print("\n" + "=" * 80)
print("TESTING CONFIGURATIONS")
print("=" * 80)

for i, config in enumerate(configs, 1):
    overlap = config["overlap"]
    committed = config["committed"]

    print(f"\n{'=' * 80}")
    print(f"CONFIGURATION {i}/7: {overlap}-DAY OVERLAP ({committed}-DAY COMMITTED)")
    print(f"{'=' * 80}")

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
        verbose=False
    )
    solve_time = time.time() - solve_start

    result_data = {
        "overlap": overlap,
        "committed": committed,
        "num_windows": result.num_windows,
        "feasible_windows": result.num_windows - len(result.infeasible_windows),
        "infeasible_windows": len(result.infeasible_windows),
        "feasibility_rate": (result.num_windows - len(result.infeasible_windows)) / result.num_windows * 100,
        "all_feasible": result.all_feasible,
        "total_cost": result.total_cost if result.all_feasible else None,
        "total_time": solve_time,
    }
    results.append(result_data)

    status = "✅ ALL FEASIBLE" if result.all_feasible else f"❌ {result_data['feasibility_rate']:.0f}% FEASIBLE"
    print(f"  Result: {status}")
    print(f"  Windows: {result.num_windows} ({result_data['feasible_windows']} feasible, {result_data['infeasible_windows']} infeasible)")
    if result.all_feasible:
        print(f"  Cost: ${result.total_cost:,.2f}")
    print(f"  Time: {solve_time:.2f}s")
    print(f"  Completed at: {datetime.now().strftime('%H:%M:%S')}")

# Results table
print("\n" + "=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)

print(f"\n{'Overlap':<10} {'Committed':<12} {'Windows':<10} {'Feasible':<12} {'Cost':<18} {'Status':<15}")
print("-" * 90)

for r in results:
    overlap_str = f"{r['overlap']}d"
    committed_str = f"{r['committed']}d"
    windows_str = str(r['num_windows'])
    feasible_str = f"{r['feasible_windows']}/{r['num_windows']}"
    cost_str = f"${r['total_cost']:,.2f}" if r['all_feasible'] else "N/A"
    status_str = "✅ 100%" if r['all_feasible'] else f"❌ {r['feasibility_rate']:.0f}%"

    print(f"{overlap_str:<10} {committed_str:<12} {windows_str:<10} {feasible_str:<12} {cost_str:<18} {status_str:<15}")

# Find feasibility boundary
print("\n" + "=" * 80)
print("FEASIBILITY BOUNDARY ANALYSIS")
print("=" * 80)

feasible_overlaps = [r['overlap'] for r in results if r['all_feasible']]
infeasible_overlaps = [r['overlap'] for r in results if not r['all_feasible']]

if feasible_overlaps:
    print(f"\n✅ Feasible overlaps: {feasible_overlaps}")
    print(f"   Min: {min(feasible_overlaps)}-day")
    print(f"   Max: {max(feasible_overlaps)}-day")

    if len(feasible_overlaps) == 1:
        print(f"\n🎯 UNIQUE SOLUTION: Only {feasible_overlaps[0]}-day overlap achieves 100% feasibility!")
    else:
        print(f"\n📊 FEASIBILITY RANGE: {min(feasible_overlaps)}-{max(feasible_overlaps)} day overlaps work")

if infeasible_overlaps:
    print(f"\n❌ Infeasible overlaps: {infeasible_overlaps}")

# Cost comparison if multiple feasible
feasible_results = [r for r in results if r['all_feasible']]
if len(feasible_results) > 1:
    best_cost = min(feasible_results, key=lambda x: x['total_cost'])
    worst_cost = max(feasible_results, key=lambda x: x['total_cost'])

    print(f"\n💰 COST COMPARISON AMONG FEASIBLE CONFIGS:")
    print(f"   Best cost: ${best_cost['total_cost']:,.2f} ({best_cost['overlap']}-day overlap)")
    print(f"   Worst cost: ${worst_cost['total_cost']:,.2f} ({worst_cost['overlap']}-day overlap)")
    cost_diff = worst_cost['total_cost'] - best_cost['total_cost']
    cost_pct = (cost_diff / worst_cost['total_cost']) * 100
    print(f"   Difference: ${cost_diff:,.2f} ({cost_pct:.2f}%)")

print(f"\n{'=' * 80}")
print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
