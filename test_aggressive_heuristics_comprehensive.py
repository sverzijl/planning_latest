"""Comprehensive test of aggressive heuristics on 21-day windows.

Tests:
1. Different overlap configurations (7d, 10d, 14d) with 21-day windows
2. Full 29-week dataset
3. Cost comparison with 14-day/7-day baseline
"""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver
import time

print("=" * 80)
print("COMPREHENSIVE AGGRESSIVE HEURISTICS TEST")
print("=" * 80)
print()

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

print(f"Dataset: {sum(e.quantity for e in full_forecast.entries):,.0f} units across {len(set(e.forecast_date for e in full_forecast.entries))} days")
print()

# Test configurations
configurations = [
    # Baseline (for comparison)
    {
        'name': '14d/7d Baseline (No Heuristics)',
        'window': 14,
        'overlap': 7,
        'heuristics': False,
    },
    {
        'name': '14d/7d with Aggressive Heuristics',
        'window': 14,
        'overlap': 7,
        'heuristics': True,
    },
    # 21-day windows with different overlaps
    {
        'name': '21d/7d with Aggressive Heuristics',
        'window': 21,
        'overlap': 7,
        'heuristics': True,
    },
    {
        'name': '21d/10d with Aggressive Heuristics',
        'window': 21,
        'overlap': 10,
        'heuristics': True,
    },
    {
        'name': '21d/14d with Aggressive Heuristics',
        'window': 21,
        'overlap': 14,
        'heuristics': True,
    },
]

results = []

for i, config in enumerate(configurations, 1):
    print("=" * 80)
    print(f"TEST {i}/{len(configurations)}: {config['name']}")
    print("=" * 80)
    print(f"  Window: {config['window']} days")
    print(f"  Overlap: {config['overlap']} days")
    print(f"  Committed region: {config['window'] - config['overlap']} days")
    print(f"  Aggressive heuristics: {'YES' if config['heuristics'] else 'NO'}")
    print()

    solver = RollingHorizonSolver(
        window_size_days=config['window'],
        overlap_days=config['overlap'],
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        allow_shortages=True,
        enforce_shelf_life=True,
        time_limit_per_window=120,  # 2 min per window
    )

    print(f"Solving full 29-week dataset...")
    start_time = time.time()

    result = solver.solve(
        forecast=full_forecast,
        granularity_config=None,
        solver_name='cbc',
        use_aggressive_heuristics=config['heuristics'],
        verbose=True
    )

    total_time = time.time() - start_time

    print()
    print(f"Results:")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"  Windows: {result.num_windows}")
    print(f"  Feasible: {result.num_windows - len(result.infeasible_windows)}/{result.num_windows}")

    if result.all_feasible:
        print(f"  ✅ ALL FEASIBLE")
        print(f"  Total cost: ${result.total_cost:,.2f}")
        print(f"  Avg time/window: {total_time/result.num_windows:.1f}s")

        results.append({
            'name': config['name'],
            'window': config['window'],
            'overlap': config['overlap'],
            'heuristics': config['heuristics'],
            'feasible': True,
            'cost': result.total_cost,
            'time': total_time,
            'windows': result.num_windows,
        })
    else:
        print(f"  ❌ INFEASIBLE")
        print(f"  Infeasible windows: {result.infeasible_windows}")

        results.append({
            'name': config['name'],
            'window': config['window'],
            'overlap': config['overlap'],
            'heuristics': config['heuristics'],
            'feasible': False,
            'cost': None,
            'time': total_time,
            'windows': result.num_windows,
        })

    print()

# Summary
print("=" * 80)
print("SUMMARY OF ALL TESTS")
print("=" * 80)
print()

# Table header
print(f"{'Configuration':<45} {'Feasible':<10} {'Cost':<15} {'Time':<10}")
print("-" * 80)

baseline_cost = None
for r in results:
    feasible_str = "✅ Yes" if r['feasible'] else "❌ No"
    cost_str = f"${r['cost']:,.0f}" if r['cost'] else "-"
    time_str = f"{r['time']:.0f}s"

    print(f"{r['name']:<45} {feasible_str:<10} {cost_str:<15} {time_str:<10}")

    # Save baseline cost
    if '14d/7d Baseline' in r['name'] and r['feasible']:
        baseline_cost = r['cost']

# Cost comparison
print()
print("=" * 80)
print("COST COMPARISON vs BASELINE")
print("=" * 80)
print()

if baseline_cost:
    for r in results:
        if r['feasible'] and r['cost'] and r['cost'] != baseline_cost:
            diff = r['cost'] - baseline_cost
            pct = (diff / baseline_cost) * 100
            symbol = "↑" if diff > 0 else "↓"
            print(f"{r['name']:<45} {symbol} ${abs(diff):>10,.0f} ({pct:>+6.2f}%)")

# Recommendations
print()
print("=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print()

# Find best 21-day configuration
best_21d = None
for r in results:
    if r['window'] == 21 and r['feasible']:
        if best_21d is None or r['cost'] < best_21d['cost']:
            best_21d = r

if best_21d:
    print("✅ 21-DAY WINDOWS ARE FEASIBLE with aggressive heuristics!")
    print()
    print(f"Best 21-day configuration: {best_21d['name']}")
    print(f"  Cost: ${best_21d['cost']:,.2f}")
    print(f"  Time: {best_21d['time']:.0f}s ({best_21d['time']/60:.1f} min)")

    if baseline_cost:
        diff = best_21d['cost'] - baseline_cost
        pct = (diff / baseline_cost) * 100
        if abs(pct) < 1:
            print(f"  Cost vs baseline: ≈ Same (within 1%)")
        elif diff > 0:
            print(f"  Cost vs baseline: +${diff:,.0f} (+{pct:.2f}% more expensive)")
        else:
            print(f"  Cost vs baseline: -${abs(diff):,.0f} ({pct:.2f}% cheaper)")

    print()
    print("→ Can now use hierarchical 3-week configurations for better lookahead")
else:
    print("❌ No 21-day configuration achieved 100% feasibility")
    print("→ Stick with 14-day/7-day baseline")

print()
print("=" * 80)
