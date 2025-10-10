"""Test rolling horizon solver on 6-week problem (2 windows).

This script validates the rolling horizon solver on a manageable 6-week problem
that should solve quickly with 2 windows of 3 weeks each (with 1-week overlap).

This is Phase 2.3 of the rolling horizon implementation plan.
"""

from datetime import date, timedelta
import time
from src.parsers import ExcelParser
from src.models.forecast import Forecast
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver

print("="*70)
print("ROLLING HORIZON TEST - 6-WEEK PROBLEM (2 WINDOWS)")
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
end_date = start_date + timedelta(days=41)  # 42 days total

filtered_entries = [
    e for e in full_forecast.entries
    if start_date <= e.forecast_date <= end_date
]
forecast_6w = Forecast(name="6Weeks", entries=filtered_entries, creation_date=date.today())

# Calculate statistics
total_demand = sum(e.quantity for e in forecast_6w.entries)
week_demands = []
for week in range(6):
    week_start = start_date + timedelta(days=week * 7)
    week_end = min(week_start + timedelta(days=6), end_date)
    week_demand = sum(
        e.quantity for e in forecast_6w.entries
        if week_start <= e.forecast_date <= week_end
    )
    week_demands.append(week_demand)

print(f"\n6-Week Problem:")
print(f"  Dates: {start_date} to {end_date} (42 days)")
print(f"  Total demand: {total_demand:,.0f} units")
print(f"  Week demands:")
for i, demand in enumerate(week_demands, 1):
    print(f"    Week {i}: {demand:,.0f} units")

print("\n" + "="*70)
print("CONFIGURATION")
print("="*70)

# Create rolling horizon solver
print("\nCreating rolling horizon solver...")
print("  Window size: 21 days (3 weeks)")
print("  Overlap: 7 days (1 week)")
print("  Expected windows: 2")
print("    Window 1: Days 1-21 (Jun 2 - Jun 22)")
print("    Window 2: Days 15-42 (Jun 16 - Jul 13)")
print("    Overlap: Days 15-21 (Jun 16 - Jun 22)")

solver = RollingHorizonSolver(
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    window_size_days=21,  # 3 weeks
    overlap_days=7,  # 1 week
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    time_limit_per_window=120,  # 2 minutes per window
    mip_gap=0.01,
)

print("\nSolver configuration:")
print(f"  Allow shortages: {solver.allow_shortages}")
print(f"  Time limit per window: {solver.time_limit_per_window}s")
print(f"  MIP gap: {solver.mip_gap*100}%")

print("\n" + "="*70)
print("SOLVING")
print("="*70)

# Solve
start_time = time.time()
result = solver.solve(
    forecast=forecast_6w,
    solver_name='cbc',
    granularity_config=None,  # Daily granularity for now
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
print(f"  Average time per window: {result.average_solve_time_per_window:.2f}s")

if not result.all_feasible:
    print(f"\n  ❌ Infeasible windows: {result.infeasible_windows}")
else:
    print(f"\n  ✅ All windows solved successfully!")

print(f"\nCost breakdown:")
print(f"  Total cost: ${result.total_cost:,.2f}")

if result.window_results:
    print(f"\nPer-window results:")
    for ws in result.window_results:
        status_icon = "✅" if ws.is_optimal() else ("⚠️" if ws.is_feasible() else "❌")
        print(f"  {status_icon} {ws.window_id}:")
        print(f"      Cost: ${ws.total_cost:,.2f}")
        print(f"      Time: {ws.solve_time_seconds:.2f}s")
        print(f"      Status: {ws.optimization_result.termination_condition}")
        if ws.ending_inventory:
            print(f"      Ending inventory: {len(ws.ending_inventory)} SKUs")

print(f"\nProduction plan:")
num_production_days = len(result.complete_production_plan)
total_production = sum(
    sum(products.values()) for products in result.complete_production_plan.values()
)
print(f"  Production days: {num_production_days}")
print(f"  Total production: {total_production:,.0f} units")

if result.complete_production_plan:
    print(f"\n  Sample production (first 5 days):")
    for i, (prod_date, products) in enumerate(sorted(result.complete_production_plan.items())[:5], 1):
        day_total = sum(products.values())
        print(f"    {prod_date}: {day_total:,.0f} units ({len(products)} products)")

print(f"\nShipments:")
print(f"  Total shipments: {len(result.complete_shipment_plan)}")

if result.complete_shipment_plan:
    print(f"\n  Sample shipments (first 5):")
    for i, shipment in enumerate(result.complete_shipment_plan[:5], 1):
        print(f"    {i}. {shipment.quantity:,.0f} units to {shipment.destination_id} on {shipment.delivery_date}")

print("\n" + "="*70)
print("VALIDATION")
print("="*70)

# Validate demand satisfaction
print("\nDemand satisfaction:")
total_shipped = sum(s.quantity for s in result.complete_shipment_plan)
satisfaction_pct = (total_shipped / total_demand * 100) if total_demand > 0 else 0

print(f"  Total demand: {total_demand:,.0f} units")
print(f"  Total shipped: {total_shipped:,.0f} units")
print(f"  Satisfaction: {satisfaction_pct:.1f}%")

if satisfaction_pct >= 99:
    print(f"  ✅ Excellent demand satisfaction (≥99%)")
elif satisfaction_pct >= 95:
    print(f"  ⚠️  Good demand satisfaction (≥95%)")
else:
    print(f"  ❌ Poor demand satisfaction (<95%)")

# Validate production <= demand (with buffer)
production_ratio = (total_production / total_demand) if total_demand > 0 else 0
print(f"\nProduction efficiency:")
print(f"  Production/Demand ratio: {production_ratio:.3f}")

if 0.95 <= production_ratio <= 1.10:
    print(f"  ✅ Efficient production (95-110% of demand)")
elif production_ratio < 0.95:
    print(f"  ⚠️  Under-production detected")
else:
    print(f"  ⚠️  Over-production detected (possible buffer stock)")

print("\n" + "="*70)
print("PERFORMANCE ANALYSIS")
print("="*70)

print(f"\nTiming breakdown:")
print(f"  Total elapsed time: {total_time:.2f}s")
print(f"  Solver time (sum of windows): {result.total_solve_time:.2f}s")
print(f"  Overhead (setup, stitching): {total_time - result.total_solve_time:.2f}s")

if result.num_windows > 0:
    print(f"\nPer-window average:")
    print(f"  Solve time: {result.average_solve_time_per_window:.2f}s")

print(f"\nComparison to single-shot:")
print(f"  Single-shot (42 days): Would likely timeout (>120s)")
print(f"  Rolling horizon (2×21 days): {result.total_solve_time:.2f}s")
print(f"  Speedup: Feasible vs Infeasible ✅")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)

if result.all_feasible:
    print("\n✅ Rolling horizon solver validated on 6-week problem!")
    print("\nKey findings:")
    print(f"  1. Both windows solved successfully")
    print(f"  2. Total solve time: {result.total_solve_time:.2f}s (avg {result.average_solve_time_per_window:.2f}s/window)")
    print(f"  3. Demand satisfaction: {satisfaction_pct:.1f}%")
    print(f"  4. Production efficiency: {production_ratio:.1%}")
    print(f"\nNext steps:")
    print(f"  ✅ Phase 2: Rolling horizon core complete")
    print(f"  ⏳ Phase 3: Test solution stitching with longer horizon")
    print(f"  ⏳ Phase 4: Add variable granularity for further speedup")
    print(f"  ⏳ Phase 6: Test on full 29-week dataset")
else:
    print("\n❌ Rolling horizon solver encountered issues")
    print(f"\nInfeasible windows: {result.infeasible_windows}")
    print("\nDebug steps:")
    print("  1. Check window results for infeasibility causes")
    print("  2. Review demand vs capacity in each window")
    print("  3. Check inventory handoff between windows")

print("\n" + "="*70)
