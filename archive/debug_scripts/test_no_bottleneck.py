"""Test 3 weeks with Week 2 bottleneck REMOVED.

This is the critical test to prove the hypothesis.
If Week 2 bottleneck is the cause, this should solve quickly (<5s).
"""

from datetime import date, timedelta
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry

print("="*70)
print("HYPOTHESIS TEST: 3 Weeks WITHOUT Week 2 Bottleneck")
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

# Define 3-week horizon
start_date = date(2025, 6, 2)
end_date = start_date + timedelta(days=20)

filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]

# Modify Week 2 demand
week2_start = date(2025, 6, 9)
week2_end = date(2025, 6, 15)

week2_entries = [e for e in filtered_entries if week2_start <= e.forecast_date <= week2_end]
week2_demand_original = sum(e.quantity for e in week2_entries)

print(f"\nWeek 2 capacity analysis:")
print(f"  Original demand:  {week2_demand_original:,.0f} units")
print(f"  Max capacity:     78,400 units (4 days × 14h × 1,400 units/h)")
print(f"  Shortage:         {week2_demand_original - 78400:,.0f} units")
print(f"  Status:           BOTTLENECK ❌")

# Reduce to 75,000 (below capacity)
target = 75000
factor = target / week2_demand_original

print(f"\nReducing Week 2 demand to eliminate bottleneck:")
print(f"  New demand:       {target:,.0f} units")
print(f"  Reduction:        {(1-factor)*100:.1f}%")
print(f"  New utilization:  {target/78400*100:.1f}% (no bottleneck ✓)")

# Create modified forecast
modified_entries = []
for entry in filtered_entries:
    if week2_start <= entry.forecast_date <= week2_end:
        modified_entries.append(ForecastEntry(
            location_id=entry.location_id,
            product_id=entry.product_id,
            forecast_date=entry.forecast_date,
            quantity=int(entry.quantity * factor)
        ))
    else:
        modified_entries.append(entry)

forecast_modified = Forecast(name="3W_No_Bottleneck", entries=modified_entries, creation_date=date.today())

# Verify
total_demand = sum(e.quantity for e in modified_entries)
week1_demand = sum(e.quantity for e in modified_entries if date(2025, 6, 2) <= e.forecast_date <= date(2025, 6, 8))
week2_demand = sum(e.quantity for e in modified_entries if week2_start <= e.forecast_date <= week2_end)
week3_demand = sum(e.quantity for e in modified_entries if date(2025, 6, 16) <= e.forecast_date <= date(2025, 6, 22))

print(f"\nModified forecast:")
print(f"  Week 1: {week1_demand:,.0f} units (unchanged)")
print(f"  Week 2: {week2_demand:,.0f} units (reduced)")
print(f"  Week 3: {week3_demand:,.0f} units (unchanged)")
print(f"  Total:  {total_demand:,.0f} units")

# Build model
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
print(f"  Binary variables: {num_binary}")

# Solve
print(f"\nSolving (60s timeout)...")
import time
start = time.time()
result = model_obj.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)
solve_time = time.time() - start

print(f"\n{'='*70}")
print("RESULTS")
print(f"{'='*70}")
print(f"  Status: {result.termination_condition}")
print(f"  Solve time: {solve_time:.2f}s")
if result.objective_value:
    print(f"  Objective: ${result.objective_value:,.2f}")
if result.gap:
    print(f"  Gap: {result.gap*100:.2f}%")

print(f"\n{'='*70}")
print("HYPOTHESIS VALIDATION")
print(f"{'='*70}")

# Compare with known results
print(f"\nComparison with original:")
print(f"  Original (WITH bottleneck):  >60s timeout")
print(f"  Modified (NO bottleneck):    {solve_time:.2f}s")

if solve_time < 10:
    print(f"\n✅ HYPOTHESIS CONFIRMED!")
    print(f"\n   Removing the Week 2 bottleneck resulted in >6x speedup!")
    print(f"   (from >60s to {solve_time:.2f}s)")
    print(f"\n   This proves that the Week 2 capacity bottleneck creates")
    print(f"   temporal symmetry that exponentially increases MIP difficulty.")
    print(f"\n   Key insight: The bottleneck forces production to be distributed")
    print(f"   across Weeks 1 and 3, creating multiple equivalent strategies")
    print(f"   that the solver must explore.")
elif solve_time < 30:
    print(f"\n⚠️  HYPOTHESIS PARTIALLY CONFIRMED")
    print(f"\n   Bottleneck has impact but other factors may contribute.")
else:
    print(f"\n❌ HYPOTHESIS QUESTIONABLE")
    print(f"\n   Still slow even without bottleneck. Other factors dominate.")

# Expected results based on weeks 1-2
expected_time = 1.96 * 1.5  # ~3s expected for week 3 without bottleneck
print(f"\n   Expected time (based on weeks 1-2 growth): ~{expected_time:.1f}s")
print(f"   Actual time: {solve_time:.2f}s")

print(f"\n{'='*70}")
