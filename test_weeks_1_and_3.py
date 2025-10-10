"""Test weeks 1 and 3 ONLY (skip week 2 bottleneck entirely).

This tests if the issue is:
- Simply "3 weeks of dates" (21 days vs 14 days)
- Or specifically "Week 2 bottleneck in the middle"

If this solves quickly (~3s like 2-week test), then Week 2 is the problem.
If this is also slow (>10s), then it's about the number of days/variables.
"""

from datetime import date, timedelta
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

print("="*70)
print("TEST: Weeks 1 and 3 ONLY (Skip Week 2)")
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

# Get Week 1 and Week 3 only
week1_start = date(2025, 6, 2)
week1_end = date(2025, 6, 8)
week3_start = date(2025, 6, 16)
week3_end = date(2025, 6, 22)

filtered_entries = [e for e in full_forecast.entries
                   if (week1_start <= e.forecast_date <= week1_end) or
                      (week3_start <= e.forecast_date <= week3_end)]

forecast_test = Forecast(name="W1+W3", entries=filtered_entries, creation_date=date.today())

week1_demand = sum(e.quantity for e in filtered_entries if e.forecast_date <= week1_end)
week3_demand = sum(e.quantity for e in filtered_entries if e.forecast_date >= week3_start)
total = week1_demand + week3_demand

print(f"\nForecast:")
print(f"  Week 1 (Jun 2-8):   {week1_demand:,.0f} units (99% utilization)")
print(f"  Week 2 (SKIPPED)")
print(f"  Week 3 (Jun 16-22): {week3_demand:,.0f} units (99% utilization)")
print(f"  Total: {total:,.0f} units across 14 days (non-consecutive)")

print(f"\n Comparison:")
print(f"  Normal 2-week test: 14 consecutive days")
print(f"  This test: 14 days with 7-day gap in middle")

# Build model
print(f"\nBuilding model...")
model_obj = IntegratedProductionDistributionModel(
    forecast=forecast_test,
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

print(f"\nComparison with other tests:")
print(f"  Week 1-2 (consecutive, no bottleneck):  ~2-3s")
print(f"  Week 1+3 (gap, no bottleneck):          {solve_time:.2f}s")
print(f"  Week 1-3 (consecutive, WITH bottleneck): >60s")

if solve_time < 5:
    print(f"\n✅ SOLVES QUICKLY!")
    print(f"\n   This proves Week 2 bottleneck is the primary issue.")
    print(f"   Without Week 2, even with 14 days of demand, it's fast.")
else:
    print(f"\n⚠️  STILL SLOW")
    print(f"\n   This suggests the issue is not JUST Week 2, but also:")
    print(f"   - Problem size (variables, dates)")
    print(f"   - Symmetry in truck assignments")
    print(f"   - Tight capacity utilization")

print(f"\n{'='*70}")
