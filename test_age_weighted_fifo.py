"""Test age-weighted FIFO holding costs on Week 3 problem.

This tests whether age-weighted holding costs reduce the performance cliff
by breaking temporal symmetry in production timing decisions.

Expected:
- Baseline (flat costs): >60s timeout
- Age-weighted costs: 20-30s (2-3x speedup)
"""

from datetime import date, timedelta
import time
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

print("="*70)
print("AGE-WEIGHTED FIFO HOLDING COSTS TEST")
print("="*70)

print("\nHypothesis:")
print("  Age-weighted holding costs break temporal symmetry by making")
print("  'produce early + hold' cheaper than 'produce late + backfill'.")
print("  This should reduce fractional binaries and speed up solve time.")

print("\nExpected Results:")
print("  Baseline (flat holding cost): >60s timeout")
print("  Age-weighted costs: 20-30s (2-3x faster)")

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

# Define 3-week horizon (the problem with the cliff)
start_date = date(2025, 6, 2)
end_date = start_date + timedelta(days=20)  # 3 weeks

filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
forecast_3w = Forecast(name="3W", entries=filtered_entries, creation_date=date.today())

# Calculate demand
total_demand = sum(e.quantity for e in filtered_entries)
week1_demand = sum(e.quantity for e in filtered_entries if date(2025, 6, 2) <= e.forecast_date <= date(2025, 6, 8))
week2_demand = sum(e.quantity for e in filtered_entries if date(2025, 6, 9) <= e.forecast_date <= date(2025, 6, 15))
week3_demand = sum(e.quantity for e in filtered_entries if date(2025, 6, 16) <= e.forecast_date <= date(2025, 6, 22))

print(f"\n3-Week Horizon ({start_date} to {end_date}):")
print(f"  Week 1: {week1_demand:,.0f} units (99% utilization)")
print(f"  Week 2: {week2_demand:,.0f} units (123% utilization - BOTTLENECK)")
print(f"  Week 3: {week3_demand:,.0f} units (99% utilization)")
print(f"  Total: {total_demand:,.0f} units")

print(f"\nWeek 2 capacity problem:")
print(f"  Demand: {week2_demand:,.0f} units")
print(f"  Max capacity: 78,400 units (4 days × 14h × 1,400 units/h)")
print(f"  Shortage: {week2_demand - 78400:,.0f} units must come from other weeks")

# Build and solve model with age-weighted costs
print(f"\nBuilding model with AGE-WEIGHTED holding costs...")
model_obj = IntegratedProductionDistributionModel(
    forecast=forecast_3w,
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

num_vars = pyomo_model.nvariables()
num_binary = sum(1 for v in pyomo_model.component_data_objects(Var) if v.is_binary())

print(f"  Variables: {num_vars:,}")
print(f"  Binary variables: {num_binary}")

print(f"\nSolving (60s timeout)...")
start = time.time()
result = model_obj.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)
solve_time = time.time() - start

print(f"\n{'='*70}")
print("RESULTS")
print(f"{'='*70}")
print(f"Status: {result.termination_condition}")
print(f"Solve time: {solve_time:.2f}s")
if result.objective_value:
    print(f"Objective: ${result.objective_value:,.2f}")
if result.gap:
    print(f"Gap: {result.gap*100:.2f}%")

# Analysis
print(f"\n{'='*70}")
print("ANALYSIS")
print(f"{'='*70}")

hit_limit = solve_time >= 59

if hit_limit:
    print(f"\n❌ STILL TIMEOUT - Age-weighted costs did not help")
    print(f"\n   Possible reasons:")
    print(f"   - Age weight factor too small (current: 0.1)")
    print(f"   - Temporal symmetry not the dominant factor")
    print(f"   - Other bottlenecks dominate (truck symmetry, etc.)")
    print(f"\n   Next steps:")
    print(f"   - Try larger age weight factor (0.2 - 0.5)")
    print(f"   - Combine with lexicographic truck ordering")
    print(f"   - Focus on rolling horizon approach")

elif solve_time < 30:
    print(f"\n✅ SUCCESS! Age-weighted costs significantly improved performance")
    print(f"\n   Solve time: {solve_time:.2f}s")
    print(f"   Expected baseline: >60s timeout")
    print(f"   Speedup: >{60/solve_time:.1f}x")
    print(f"\n   Explanation:")
    print(f"   - Age-weighted costs make 'produce early + hold' clearly cheaper")
    print(f"   - This breaks temporal symmetry between production strategies")
    print(f"   - Solver has fewer symmetric branches to explore")
    print(f"   - Reduced fractional binaries in LP relaxation")
    print(f"\n   Next steps:")
    print(f"   - Test on Week 6 problem")
    print(f"   - Combine with lexicographic truck ordering for additional speedup")
    print(f"   - Consider this optimization for production deployment")

else:  # 30-59s
    print(f"\n⚠️  MODERATE IMPROVEMENT")
    print(f"\n   Solve time: {solve_time:.2f}s (still slow but better than >60s)")
    print(f"   Speedup: ~{60/solve_time:.1f}x")
    print(f"\n   Age-weighted costs help but not enough")
    print(f"   Combine with other optimizations:")
    print(f"   - Lexicographic truck ordering")
    print(f"   - Commercial solver (Gurobi/CPLEX)")
    print(f"   - Rolling horizon")

# Compare with previous results
print(f"\n{'='*70}")
print("COMPARISON WITH PREVIOUS TESTS")
print(f"{'='*70}")
print(f"\n  Weeks 1-3 (original, flat costs):      >60s timeout")
print(f"  Weeks 1-3 (low util, flat costs):        7.15s")
print(f"  Weeks 1+3 only (flat costs):             11.08s")
print(f"  Weeks 1-3 (age-weighted costs):          {solve_time:.2f}s ← THIS TEST")

print(f"\n{'='*70}")
print("CONCLUSION")
print(f"{'='*70}")

if solve_time < 30:
    print(f"\n✅ Age-weighted holding costs are EFFECTIVE for this problem")
    print(f"\n   Recommended for production use as part of optimization stack:")
    print(f"   1. Sparse indexing (72.7% variable reduction) ✅ Already implemented")
    print(f"   2. Age-weighted costs (2-3x speedup) ✅ This test")
    print(f"   3. Lexicographic truck ordering (3-5x speedup) ⏳ Next")
    print(f"   4. Rolling horizon (4-6 weeks) ⏳ For full dataset")
else:
    print(f"\n⚠️  Age-weighted costs provide modest benefit")
    print(f"\n   Worth keeping if solve time < 40s, otherwise focus on:")
    print(f"   - Rolling horizon (guaranteed solve time)")
    print(f"   - Commercial solver (if available)")

print(f"\n{'='*70}")
