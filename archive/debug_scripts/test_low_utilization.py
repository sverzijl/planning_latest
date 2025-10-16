"""Test 3 weeks with LOW utilization across all weeks.

If this solves quickly, it proves that TIGHT CAPACITY (not just bottlenecks)
causes the performance cliff.
"""

from datetime import date, timedelta
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry

print("="*70)
print("TEST: 3 Weeks with LOW UTILIZATION (60-70%)")
print("="*70)

# Load data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Define 3-week horizon
start_date = date(2025, 6, 2)
end_date = start_date + timedelta(days=20)
filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]

# Current demand
current_total = sum(e.quantity for e in filtered_entries)
print(f"\nOriginal 3-week demand: {current_total:,.0f} units")

# Target: ~60% utilization across all weeks
# 3 weeks, capacity ~84,000/week → 252,000 total
# Target 60% → ~150,000 total
target_total = 150000
reduction_factor = target_total / current_total

print(f"Target demand: {target_total:,.0f} units (60% avg utilization)")
print(f"Reduction factor: {reduction_factor:.3f} ({(1-reduction_factor)*100:.1f}% reduction)")

# Reduce ALL demand proportionally
modified_entries = []
for entry in filtered_entries:
    modified_entries.append(ForecastEntry(
        location_id=entry.location_id,
        product_id=entry.product_id,
        forecast_date=entry.forecast_date,
        quantity=int(entry.quantity * reduction_factor)
    ))

forecast_modified = Forecast(name="3W_Low_Util", entries=modified_entries, creation_date=date.today())

# Verify by week
week1_demand = sum(e.quantity for e in modified_entries if date(2025, 6, 2) <= e.forecast_date <= date(2025, 6, 8))
week2_demand = sum(e.quantity for e in modified_entries if date(2025, 6, 9) <= e.forecast_date <= date(2025, 6, 15))
week3_demand = sum(e.quantity for e in modified_entries if date(2025, 6, 16) <= e.forecast_date <= date(2025, 6, 22))

print(f"\nModified demand by week:")
print(f"  Week 1: {week1_demand:,} units → {week1_demand/84000*100:.1f}% utilization")
print(f"  Week 2: {week2_demand:,} units → {week2_demand/67200*100:.1f}% utilization (4 days)")
print(f"  Week 3: {week3_demand:,} units → {week3_demand/84000*100:.1f}% utilization")
print(f"  Total:  {sum([week1_demand, week2_demand, week3_demand]):,} units")

# Build and solve
print(f"\nBuilding model...")
model_obj = IntegratedProductionDistributionModel(
    forecast=forecast_modified,
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
print(f"  Binary: {num_binary}")

print(f"\nSolving (30s timeout)...")
import time
start = time.time()
result = model_obj.solve(solver_name='cbc', time_limit_seconds=30, mip_gap=0.01, tee=False)
solve_time = time.time() - start

print(f"\n{'='*70}")
print("RESULTS")
print(f"{'='*70}")
print(f"Status: {result.termination_condition}")
print(f"Solve time: {solve_time:.2f}s")
if result.objective_value:
    print(f"Objective: ${result.objective_value:,.2f}")

print(f"\n{'='*70}")
print("ANALYSIS")
print(f"{'='*70}")

if solve_time < 5:
    print(f"\n✅ LOW UTILIZATION SOLVES QUICKLY!")
    print(f"\n   With 60% utilization: {solve_time:.2f}s")
    print(f"   With 99% utilization: >60s timeout")
    print(f"\n   CONCLUSION: TIGHT CAPACITY causes the cliff, not just bottlenecks")
    print(f"\n   When capacity is tight (90-100%), the solver must carefully")
    print(f"   balance production timing, overtime decisions, and truck")
    print(f"   assignments. This creates many fractional binary variables")
    print(f"   in the LP relaxation, leading to exponential search trees.")
    print(f"\n   When capacity is comfortable (60-70%), production decisions")
    print(f"   are more relaxed and the solver finds solutions quickly.")
elif solve_time < 15:
    print(f"\n⚠️  MODERATE IMPROVEMENT")
    print(f"\n   Lower utilization helps but doesn't eliminate the cliff.")
    print(f"   Other factors (problem size, symmetry) also contribute.")
else:
    print(f"\n❌ STILL SLOW")
    print(f"\n   The issue is fundamental to 3-week problems, not capacity.")

print(f"\n{'='*70}")
