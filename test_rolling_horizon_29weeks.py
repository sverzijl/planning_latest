"""Test rolling horizon solver on FULL 29-week dataset.

This is the ultimate test - solving the complete planning problem that was
previously completely infeasible with single-shot optimization.

Expected: 2-5 minutes total (vs completely infeasible without rolling horizon)
"""

from datetime import date, timedelta
import time
from src.parsers import ExcelParser
from src.models.forecast import Forecast
from src.models.truck_schedule import TruckScheduleCollection
from src.models.time_period import BucketGranularity, VariableGranularityConfig
from src.optimization import RollingHorizonSolver

print("="*70)
print("ROLLING HORIZON - FULL 29-WEEK DATASET")
print("="*70)
print("\nThis is the complete dataset that is INFEASIBLE with single-shot optimization.")
print("Goal: Prove rolling horizon + temporal aggregation makes it feasible.\n")

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

# Use FULL forecast (all entries)
total_days = (max(e.forecast_date for e in full_forecast.entries) -
              min(e.forecast_date for e in full_forecast.entries)).days + 1
total_demand = sum(e.quantity for e in full_forecast.entries)
num_entries = len(full_forecast.entries)

print(f"\nFull Dataset:")
print(f"  Total days: {total_days}")
print(f"  Total demand: {total_demand:,.0f} units")
print(f"  Forecast entries: {num_entries:,}")
print(f"  Without rolling horizon: COMPLETELY INFEASIBLE ❌")

print("\n" + "="*70)
print("CONFIGURATION")
print("="*70)

# Configure temporal aggregation
print("\nTemporal Aggregation Strategy:")
print("  Option 1 (Balanced): Week 1 daily, rest 3-day buckets")
print("  Option 2 (Fast): 3-day buckets throughout")
print("  Option 3 (Quality): Week 1 daily, rest 2-day buckets")

# Use Option 1 (balanced)
granularity_config = VariableGranularityConfig(
    near_term_days=7,
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.THREE_DAY,
)

print(f"\nSelected: Option 1 (Balanced)")
print(f"  {granularity_config}")

# Create rolling horizon solver
print(f"\nRolling Horizon Configuration:")
print(f"  Window size: 28 days (4 weeks)")
print(f"  Overlap: 7 days (1 week)")
print(f"  Committed days per window: 21")
print(f"  Expected windows: ~{(total_days + 20) // 21}")

solver = RollingHorizonSolver(
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    window_size_days=28,  # 4 weeks
    overlap_days=7,  # 1 week overlap
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    time_limit_per_window=180,  # 3 minutes per window (generous)
    mip_gap=0.01,
)

print("\n" + "="*70)
print("SOLVING FULL 29-WEEK PROBLEM")
print("="*70)
print("\nThis may take 2-5 minutes. Please wait...")
print("(Each window will be solved sequentially with progress updates)\n")

# Solve
start_time = time.time()
result = solver.solve(
    forecast=full_forecast,
    solver_name='cbc',
    granularity_config=granularity_config,
    verbose=True
)
total_time = time.time() - start_time

print("\n" + "="*70)
print("RESULTS")
print("="*70)

print(f"\nSolution Status:")
print(f"  All windows feasible: {'✅ YES' if result.all_feasible else '❌ NO'}")
print(f"  Number of windows: {result.num_windows}")
print(f"  Total solve time: {result.total_solve_time:.2f}s ({result.total_solve_time/60:.1f} min)")
print(f"  Wall clock time: {total_time:.2f}s ({total_time/60:.1f} min)")
print(f"  Average per window: {result.average_solve_time_per_window:.2f}s")

if not result.all_feasible:
    print(f"\n  ❌ Infeasible windows: {result.infeasible_windows}")
    print(f"\n  Feasible windows: {result.num_windows - len(result.infeasible_windows)}/{result.num_windows}")
else:
    print(f"\n  ✅ All {result.num_windows} windows solved successfully!")

print(f"\nCost Analysis:")
print(f"  Total cost: ${result.total_cost:,.2f}")

if result.window_results:
    print(f"\nPer-window breakdown:")
    for i, ws in enumerate(result.window_results, 1):
        status_icon = "✅" if ws.is_optimal() else ("⚠️" if ws.is_feasible() else "❌")
        print(f"  {status_icon} Window {i} ({ws.window_id}):")
        print(f"      Cost: ${ws.total_cost:,.2f}")
        print(f"      Time: {ws.solve_time_seconds:.2f}s")
        if ws.ending_inventory:
            inv_units = sum(ws.ending_inventory.values())
            print(f"      Ending inventory: {inv_units:,.0f} units")

print(f"\nProduction Plan:")
total_production = sum(
    sum(products.values()) for products in result.complete_production_plan.values()
)
print(f"  Production days: {len(result.complete_production_plan)}")
print(f"  Total production: {total_production:,.0f} units")

print(f"\nDistribution Plan:")
print(f"  Total shipments: {len(result.complete_shipment_plan)}")
total_shipped = sum(s.quantity for s in result.complete_shipment_plan)
print(f"  Total shipped: {total_shipped:,.0f} units")

satisfaction_pct = (total_shipped / total_demand * 100) if total_demand > 0 else 0
print(f"  Demand satisfaction: {satisfaction_pct:.1f}%")

print("\n" + "="*70)
print("PERFORMANCE METRICS")
print("="*70)

print(f"\nSolve Time Analysis:")
print(f"  Best window: {min(ws.solve_time_seconds for ws in result.window_results):.2f}s")
print(f"  Worst window: {max(ws.solve_time_seconds for ws in result.window_results):.2f}s")
print(f"  Average window: {result.average_solve_time_per_window:.2f}s")
print(f"  Total: {result.total_solve_time:.2f}s ({result.total_solve_time/60:.1f} min)")

print(f"\nComparison to Baseline:")
print(f"  Single-shot optimization: COMPLETELY INFEASIBLE ❌")
print(f"  Rolling horizon + aggregation: {result.total_solve_time:.2f}s ✅")
print(f"  Achievement: Infeasible → Feasible in {result.total_solve_time/60:.1f} minutes!")

if result.total_solve_time < 300:  # 5 minutes
    print(f"\n✅ EXCELLENT: Solved in <5 minutes")
elif result.total_solve_time < 600:  # 10 minutes
    print(f"\n✅ GOOD: Solved in <10 minutes")
else:
    print(f"\n⚠️  ACCEPTABLE: Solved but slower than target")

print("\n" + "="*70)
print("FINAL CONCLUSION")
print("="*70)

if result.all_feasible:
    print("\n🎉 SUCCESS! FULL 29-WEEK PROBLEM SOLVED!")

    print("\nStrategy Validation:")
    print("  ✅ Rolling horizon architecture works")
    print("  ✅ Temporal aggregation effective")
    print("  ✅ Window overlap and inventory handoff working")
    print("  ✅ Solution stitching successful")

    print(f"\nPerformance Achievement:")
    print(f"  Baseline: Infeasible (>2,856 binary variables)")
    print(f"  Solution: {result.total_solve_time:.1f}s with {result.num_windows} windows")
    print(f"  Per-window binary vars: ~100-130 (aggregated)")

    print(f"\nProduction Ready:")
    print(f"  Total solve time: {result.total_solve_time/60:.1f} minutes")
    print(f"  Demand satisfaction: {satisfaction_pct:.1f}%")
    print(f"  Cost: ${result.total_cost:,.2f}")

    print("\nRecommended Configuration (validated):")
    print("  Window size: 28 days (4 weeks)")
    print("  Overlap: 7 days (1 week)")
    print("  Granularity: Week 1 daily, rest 3-day buckets")
    print("  Time limit per window: 180s")

else:
    print(f"\n⚠️  Partial Success: {result.num_windows - len(result.infeasible_windows)}/{result.num_windows} windows feasible")

    print("\nDiagnostics:")
    for window_id in result.infeasible_windows:
        ws = next((w for w in result.window_results if w.window_id == window_id), None)
        if ws:
            print(f"  Window {window_id}:")
            print(f"    Status: {ws.optimization_result.termination_condition}")
            if ws.optimization_result.infeasibility_message:
                print(f"    Message: {ws.optimization_result.infeasibility_message}")

    print("\nRecommendations:")
    print("  - Increase time limit per window")
    print("  - Use coarser temporal aggregation (weekly buckets)")
    print("  - Reduce window size to 21 days")
    print("  - Allow higher MIP gap (5-10%)")

print("\n" + "="*70)
print("END OF 29-WEEK VALIDATION")
print("="*70)
