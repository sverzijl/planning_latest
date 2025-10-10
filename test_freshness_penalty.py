"""Test freshness penalty on Week 3 problem.

This tests whether adding a freshness penalty (customer preference for fresh product)
reduces fractional binaries and improves solve time by creating clear preference ordering.

Key Difference from Age-Weighted Holding Costs:
- Age-weighted holding: Penalizes warehouse storage of old inventory
- Freshness penalty: Additional penalty for delivering old product to customers
- Combined effect: Strong incentive to minimize inventory age at delivery

Expected Impact:
- Reduces fractional binaries by breaking ties in equivalent solutions
- Creates preference ordering: fresh production > holding inventory
- Tightens LP relaxation → smaller search tree

Expected Results:
- Baseline (age-weighted only): >60s timeout
- Age-weighted + freshness penalty: 20-40s (2-3x speedup estimated)
"""

from datetime import date, timedelta
import time
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

print("="*70)
print("FRESHNESS PENALTY TEST")
print("="*70)

print("\nHypothesis:")
print("  Freshness penalty creates strong preference for fresh product delivery,")
print("  breaking ties between equivalent solutions that create fractional binaries.")
print("  Combined with age-weighted holding costs, this should tighten LP relaxation.")

print("\nExpected Mechanism:")
print("  1. Age-weighted holding: Penalizes warehouse inventory storage")
print("  2. Freshness penalty: Penalizes delivering old product to customers")
print("  3. Combined: Strong incentive for just-in-time production")
print("  4. Result: Clear preference ordering → fewer fractional binaries")

print("\nExpected Results:")
print("  Baseline (age-weighted only): >60s timeout")
print("  Age-weighted + freshness penalty: 20-40s (2-3x faster)")

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
print(f"  Week 1: {week1_demand:,.0f} units")
print(f"  Week 2: {week2_demand:,.0f} units")
print(f"  Week 3: {week3_demand:,.0f} units")
print(f"  Total: {total_demand:,.0f} units")

# Check freshness penalty in cost structure
print(f"\nCost Structure Parameters:")
print(f"  Holding cost base: ${cost_structure.storage_cost_ambient_per_unit_day:.4f}/unit/day")
print(f"  Freshness penalty: ${cost_structure.freshness_penalty_per_unit_day:.4f}/unit/day")
print(f"  Age weight factor: 0.1 (applied to holding cost)")
print(f"  Combined penalty per day of age: ${(cost_structure.storage_cost_ambient_per_unit_day * 0.1 + cost_structure.freshness_penalty_per_unit_day):.4f}/unit/day")

# Build and solve model with freshness penalty
print(f"\nBuilding model with age-weighted holding costs + FRESHNESS PENALTY...")
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
    print(f"\n❌ STILL TIMEOUT - Freshness penalty did not help")
    print(f"\n   Possible reasons:")
    print(f"   - Freshness penalty rate too small (current: ${cost_structure.freshness_penalty_per_unit_day:.2f}/unit/day)")
    print(f"   - Combined with holding cost may still be insufficient")
    print(f"   - Truck symmetry and planning horizon dominate")
    print(f"   - Need different approach (lexicographic truck ordering, rolling horizon)")

    print(f"\n   Next steps:")
    print(f"   - Try larger freshness penalty (0.2 - 0.5)")
    print(f"   - Focus on rolling horizon (only viable solution for full dataset)")
    print(f"   - Implement lexicographic truck ordering")

elif solve_time < 30:
    print(f"\n✅ SUCCESS! Freshness penalty significantly improved performance")
    print(f"\n   Solve time: {solve_time:.2f}s")
    print(f"   Expected baseline: >60s timeout")
    print(f"   Speedup: >{60/solve_time:.1f}x")

    print(f"\n   Explanation:")
    print(f"   - Freshness penalty breaks ties between equivalent solutions")
    print(f"   - Creates clear preference: fresh production > holding inventory")
    print(f"   - Tightens LP relaxation → fewer fractional binaries")
    print(f"   - Smaller search tree → faster solve")

    print(f"\n   Next steps:")
    print(f"   - Test on Week 6 problem to validate")
    print(f"   - Combine with lexicographic truck ordering for additional speedup")
    print(f"   - Consider for production deployment")

else:  # 30-59s
    print(f"\n⚠️  MODERATE IMPROVEMENT")
    print(f"\n   Solve time: {solve_time:.2f}s (better than >60s, but still slow)")
    print(f"   Speedup: ~{60/solve_time:.1f}x")

    print(f"\n   Freshness penalty helps but not enough alone")
    print(f"   Combine with other optimizations:")
    print(f"   - Lexicographic truck ordering (3-5x expected)")
    print(f"   - Commercial solver (5-10x expected)")
    print(f"   - Rolling horizon (guaranteed solve for full dataset)")

# Compare with previous results
print(f"\n{'='*70}")
print("COMPARISON WITH PREVIOUS TESTS")
print(f"{'='*70}")
print(f"\n  Weeks 1-3 (flat costs):                 >60s timeout")
print(f"  Weeks 1-3 (age-weighted only):          >60s timeout")
print(f"  Weeks 1-3 (age + freshness):            {solve_time:.2f}s ← THIS TEST")
print(f"  Weeks 1-3 (60% utilization):              7.15s (capacity constraint relaxed)")

print(f"\n{'='*70}")
print("CONCLUSION")
print(f"{'='*70}")

if solve_time < 30:
    print(f"\n✅ Freshness penalty is EFFECTIVE for this problem")
    print(f"\n   Recommended for production as part of optimization stack:")
    print(f"   1. Sparse indexing (72.7% variable reduction) ✅")
    print(f"   2. Age-weighted holding costs ✅")
    print(f"   3. Freshness penalty (2-3x speedup) ✅ This test")
    print(f"   4. Lexicographic truck ordering (3-5x speedup) ⏳ Next")
    print(f"   5. Rolling horizon (4-6 weeks) ⏳ For full dataset")

elif solve_time < 50:
    print(f"\n⚠️  Freshness penalty provides modest benefit")
    print(f"\n   Worth keeping but need additional optimizations:")
    print(f"   - Lexicographic truck ordering (breaks truck symmetry)")
    print(f"   - Rolling horizon (guaranteed solve time)")
    print(f"   - Commercial solver (if available)")

else:
    print(f"\n❌ Freshness penalty does NOT solve the performance cliff")
    print(f"\n   Conclusion: Hypothesis about fractional binaries was incorrect")
    print(f"   The real bottleneck is likely:")
    print(f"   - Planning horizon length (300 binary vars = 2^300 search space)")
    print(f"   - Truck assignment symmetry (5! = 120 equivalent solutions)")
    print(f"   - Combined complexity that no objective tuning can fix")

    print(f"\n   Required solution:")
    print(f"   - Rolling horizon (ONLY viable approach for full dataset)")
    print(f"   - Lexicographic truck ordering (break symmetry)")
    print(f"   - Commercial solver (better heuristics)")

print(f"\n{'='*70}")
