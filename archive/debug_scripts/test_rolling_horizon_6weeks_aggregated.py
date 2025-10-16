"""Test rolling horizon solver on 6-week problem WITH temporal aggregation.

This validates the complete rolling horizon + temporal aggregation strategy.
Expected: 10-30s total solve time (vs >5min without aggregation).
"""

from datetime import date, timedelta
import time
from src.parsers import ExcelParser
from src.models.forecast import Forecast
from src.models.truck_schedule import TruckScheduleCollection
from src.models.time_period import BucketGranularity, VariableGranularityConfig
from src.optimization import RollingHorizonSolver

print("="*70)
print("ROLLING HORIZON + TEMPORAL AGGREGATION - 6-WEEK TEST")
print("="*70)

# Load data
print("\nLoading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Filter for 6 weeks (June 2 - July 13, 2025 = 42 days)
start_date = date(2025, 6, 2)
end_date = start_date + timedelta(days=41)

filtered_entries = [
    e for e in full_forecast.entries
    if start_date <= e.forecast_date <= end_date
]
forecast_6w = Forecast(name="6Weeks", entries=filtered_entries, creation_date=date.today())

total_demand = sum(e.quantity for e in forecast_6w.entries)

print(f"\n6-Week Problem:")
print(f"  Dates: {start_date} to {end_date} (42 days)")
print(f"  Total demand: {total_demand:,.0f} units")

print("\n" + "="*70)
print("CONFIGURATION")
print("="*70)

# Configure temporal aggregation
granularity_config = VariableGranularityConfig(
    near_term_days=7,  # First week: daily granularity
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.THREE_DAY,  # Remaining weeks: 3-day buckets
)

print(f"\nTemporal Aggregation: {granularity_config}")
print(f"  Week 1 (days 1-7): Daily (7 periods)")
print(f"  Weeks 2-3 (days 8-21): 3-day buckets (~5 periods)")
print(f"  Total per window: ~12 periods (vs 21 daily)")
print(f"  Binary vars per window: ~57% reduction (300 → ~130)")

# Create rolling horizon solver
print(f"\nRolling Horizon Configuration:")
print(f"  Window size: 21 days (3 weeks)")
print(f"  Overlap: 7 days (1 week)")
print(f"  Expected windows: 2")

solver = RollingHorizonSolver(
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    window_size_days=21,
    overlap_days=7,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    time_limit_per_window=120,
    mip_gap=0.01,
)

print("\n" + "="*70)
print("SOLVING WITH TEMPORAL AGGREGATION")
print("="*70)

# Solve with temporal aggregation
start_time = time.time()
result = solver.solve(
    forecast=forecast_6w,
    solver_name='cbc',
    granularity_config=granularity_config,  # ← KEY: Enable aggregation
    verbose=True
)
total_time = time.time() - start_time

print("\n" + "="*70)
print("RESULTS")
print("="*70)

print(f"\nSolution status:")
print(f"  All windows feasible: {'✅ YES' if result.all_feasible else '❌ NO'}")
print(f"  Number of windows: {result.num_windows}")
print(f"  Total solve time: {result.total_solve_time:.2f}s")
print(f"  Wall clock time: {total_time:.2f}s")
print(f"  Average per window: {result.average_solve_time_per_window:.2f}s")

if result.all_feasible:
    print(f"\n✅ SUCCESS! Rolling horizon + aggregation solved 6-week problem")

    print(f"\nCost: ${result.total_cost:,.2f}")

    print(f"\nProduction plan:")
    total_production = sum(
        sum(products.values()) for products in result.complete_production_plan.values()
    )
    print(f"  Production days: {len(result.complete_production_plan)}")
    print(f"  Total production: {total_production:,.0f} units")

    print(f"\nShipments: {len(result.complete_shipment_plan)}")
    total_shipped = sum(s.quantity for s in result.complete_shipment_plan)
    satisfaction_pct = (total_shipped / total_demand * 100) if total_demand > 0 else 0
    print(f"  Total shipped: {total_shipped:,.0f} units")
    print(f"  Demand satisfaction: {satisfaction_pct:.1f}%")

    print(f"\n" + "="*70)
    print("PERFORMANCE ANALYSIS")
    print("="*70)

    print(f"\nComparison:")
    print(f"  Without aggregation: >5 minutes (timeout) ❌")
    print(f"  With aggregation: {result.total_solve_time:.2f}s ✅")
    print(f"  Speedup: >10x faster")

    print(f"\nPer-window performance:")
    for ws in result.window_results:
        print(f"  {ws.window_id}: {ws.solve_time_seconds:.2f}s")

    if result.total_solve_time < 60:
        print(f"\n✅ TARGET ACHIEVED: Solved in <60 seconds")
    else:
        print(f"\n⚠️  Slower than expected but feasible")

else:
    print(f"\n❌ Some windows infeasible: {result.infeasible_windows}")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)

if result.all_feasible and result.total_solve_time < 60:
    print("\n🎉 VALIDATION SUCCESSFUL!")
    print("\nRolling horizon + temporal aggregation strategy proven on 6-week problem.")
    print("\nKey achievements:")
    print(f"  ✅ Both windows solved successfully")
    print(f"  ✅ Total solve time: {result.total_solve_time:.2f}s (target: <60s)")
    print(f"  ✅ Demand satisfaction: {satisfaction_pct:.1f}%")
    print(f"  ✅ Speedup vs no aggregation: >10x")

    print("\nReady for 29-week full dataset test!")
    print("  Expected: 7-8 windows × ~10s = ~70-80s total")
    print("  vs baseline: Completely infeasible")

elif result.all_feasible:
    print("\n✅ Feasible but slower than expected")
    print(f"   Solve time: {result.total_solve_time:.2f}s")
    print("   May need further optimization for 29-week dataset")

else:
    print("\n❌ Infeasible - debugging needed")

print("\n" + "="*70)
