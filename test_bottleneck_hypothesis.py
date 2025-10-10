"""Test if Week 2 capacity bottleneck causes the performance cliff.

Hypothesis: The 5.67x slowdown from week 2→3 is caused by Week 2's public holiday
creating a capacity bottleneck (demand 82,893 > max capacity 78,400).

Test:
1. Run 3-week optimization with ORIGINAL Week 2 demand (82,893) → expect timeout
2. Run 3-week optimization with REDUCED Week 2 demand (75,000) → expect fast solve
3. Compare solve times to validate hypothesis

If hypothesis is correct:
- Original: >60s (or timeout)
- Reduced: <5s (similar to weeks 1-2 growth rate)
"""

from datetime import date, timedelta
from copy import deepcopy
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry

def test_3week_optimization(forecast_label, horizon_forecast, locations, routes,
                           labor_calendar, truck_schedules, cost_structure,
                           manufacturing_site, timeout=60):
    """Run 3-week optimization and return results."""

    print(f"\n{'='*70}")
    print(f"TEST: {forecast_label}")
    print(f"{'='*70}")

    # Show demand
    total_demand = sum(e.quantity for e in horizon_forecast.entries)
    print(f"\nTotal demand (3 weeks): {total_demand:,.0f} units")

    # Break down by week
    start = date(2025, 6, 2)
    for week in [1, 2, 3]:
        week_start = start + timedelta(days=(week-1)*7)
        week_end = week_start + timedelta(days=6)
        week_entries = [e for e in horizon_forecast.entries if week_start <= e.forecast_date <= week_end]
        week_demand = sum(e.quantity for e in week_entries)
        print(f"  Week {week}: {week_demand:,.0f} units")

    # Build model
    print(f"\nBuilding model...")
    model_obj = IntegratedProductionDistributionModel(
        forecast=horizon_forecast,
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
    print(f"  Binary variables: {num_binary:,}")

    # Solve with timeout
    print(f"\nSolving (timeout: {timeout}s)...")
    result = model_obj.solve(solver_name='cbc', time_limit_seconds=timeout, mip_gap=0.01, tee=False)

    print(f"\n{'─'*70}")
    print("RESULTS")
    print(f"{'─'*70}")
    print(f"  Status: {result.termination_condition}")
    print(f"  Solve time: {result.solve_time_seconds:.2f}s")
    if result.objective_value:
        print(f"  Objective: ${result.objective_value:,.2f}")
    if result.gap:
        print(f"  Gap: {result.gap*100:.2f}%")

    hit_limit = result.solve_time_seconds >= (timeout - 1)
    if hit_limit:
        print(f"\n  ⚠️  HIT TIME LIMIT")
    else:
        print(f"\n  ✅ Solved within time limit")

    return {
        'label': forecast_label,
        'total_demand': total_demand,
        'solve_time': result.solve_time_seconds,
        'objective': result.objective_value,
        'status': str(result.termination_condition),
        'hit_limit': hit_limit,
        'num_vars': num_vars,
        'num_binary': num_binary
    }

# ============================================================================
# MAIN TEST
# ============================================================================

print("="*70)
print("BOTTLENECK HYPOTHESIS TEST")
print("="*70)

print("\nHypothesis:")
print("  Week 2 capacity bottleneck (demand > capacity) causes the cliff")
print("  by creating temporal symmetry in production timing decisions.")

print("\nPrediction:")
print("  - WITH bottleneck (original demand):    >60s or timeout")
print("  - WITHOUT bottleneck (reduced demand):  <5s (fast)")

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
end_date = start_date + timedelta(days=20)  # 3 weeks

# ============================================================================
# TEST 1: Original forecast (WITH bottleneck)
# ============================================================================

filtered_entries_original = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
forecast_original = Forecast(name="3W_Original", entries=filtered_entries_original, creation_date=date.today())

result_original = test_3week_optimization(
    "ORIGINAL FORECAST (With Week 2 Bottleneck)",
    forecast_original, locations, routes, labor_calendar,
    truck_schedules, cost_structure, manufacturing_site,
    timeout=60
)

# ============================================================================
# TEST 2: Reduced Week 2 demand (NO bottleneck)
# ============================================================================

print(f"\n{'='*70}")
print("MODIFYING FORECAST")
print(f"{'='*70}")

# Calculate Week 2 dates
week2_start = date(2025, 6, 9)
week2_end = date(2025, 6, 15)

# Get Week 2 entries
week2_entries = [e for e in filtered_entries_original if week2_start <= e.forecast_date <= week2_end]
week2_demand_original = sum(e.quantity for e in week2_entries)

# Target: 75,000 units (below 78,400 capacity, no bottleneck)
target_week2_demand = 75000
reduction_factor = target_week2_demand / week2_demand_original

print(f"\nWeek 2 (June 9-15) demand modification:")
print(f"  Original demand:  {week2_demand_original:,.0f} units (exceeds capacity)")
print(f"  Capacity (max):   78,400 units (4 days with OT)")
print(f"  New demand:       {target_week2_demand:,.0f} units (below capacity)")
print(f"  Reduction factor: {reduction_factor:.3f}")

# Create modified forecast
modified_entries = []
for entry in filtered_entries_original:
    if week2_start <= entry.forecast_date <= week2_end:
        # Reduce Week 2 demand proportionally across all locations/products
        modified_entry = ForecastEntry(
            location_id=entry.location_id,
            product_id=entry.product_id,
            forecast_date=entry.forecast_date,
            quantity=int(entry.quantity * reduction_factor)
        )
        modified_entries.append(modified_entry)
    else:
        # Keep Weeks 1 and 3 unchanged
        modified_entries.append(entry)

forecast_modified = Forecast(name="3W_Reduced", entries=modified_entries, creation_date=date.today())

# Verify modification
week2_demand_new = sum(e.quantity for e in modified_entries if week2_start <= e.forecast_date <= week2_end)
print(f"  Actual new demand: {week2_demand_new:,.0f} units")
print(f"  Utilization:       {week2_demand_new/78400*100:.1f}% (no bottleneck ✓)")

result_modified = test_3week_optimization(
    "MODIFIED FORECAST (No Week 2 Bottleneck)",
    forecast_modified, locations, routes, labor_calendar,
    truck_schedules, cost_structure, manufacturing_site,
    timeout=60
)

# ============================================================================
# COMPARISON AND HYPOTHESIS VALIDATION
# ============================================================================

print(f"\n{'='*70}")
print("HYPOTHESIS VALIDATION")
print(f"{'='*70}")

print(f"\n{'Scenario':<40} {'Demand':<15} {'Solve Time':<15} {'Status':<15}")
print("─"*85)
print(f"{'Original (WITH bottleneck)':<40} {result_original['total_demand']:>13,.0f}  {result_original['solve_time']:>12.2f}s  {result_original['status'][:12]:<15}")
print(f"{'Modified (NO bottleneck)':<40} {result_modified['total_demand']:>13,.0f}  {result_modified['solve_time']:>12.2f}s  {result_modified['status'][:12]:<15}")

speedup = result_original['solve_time'] / result_modified['solve_time'] if result_modified['solve_time'] > 0 else 0

print(f"\n{'─'*85}")
print(f"Speedup with bottleneck removed: {speedup:.2f}x")

# Validation
print(f"\n{'='*70}")
print("CONCLUSION")
print(f"{'='*70}")

if speedup > 5:
    print(f"\n✅ HYPOTHESIS CONFIRMED!")
    print(f"\n   Removing the Week 2 capacity bottleneck resulted in {speedup:.1f}x speedup.")
    print(f"   This proves that the bottleneck causes temporal symmetry that")
    print(f"   dramatically increases MIP solution difficulty.")

    print(f"\n   Key evidence:")
    print(f"   - Original (bottleneck):  {result_original['solve_time']:.2f}s")
    print(f"   - Modified (no bottleneck): {result_modified['solve_time']:.2f}s")
    print(f"   - Same number of variables: {result_modified['num_vars']:,}")
    print(f"   - Same number of binary vars: {result_modified['num_binary']}")
    print(f"   - Only difference: Week 2 demand reduced by {(1-reduction_factor)*100:.1f}%")

    print(f"\n   Root cause: Week 2 bottleneck creates multiple equivalent strategies")
    print(f"   for distributing production across 3 weeks, causing solver to explore")
    print(f"   exponentially more branches due to temporal symmetry.")

elif speedup > 2:
    print(f"\n⚠️  HYPOTHESIS PARTIALLY CONFIRMED")
    print(f"\n   Bottleneck has significant impact ({speedup:.1f}x speedup when removed)")
    print(f"   but may not be the only factor contributing to the cliff.")

else:
    print(f"\n❌ HYPOTHESIS REJECTED")
    print(f"\n   Removing bottleneck had minimal impact ({speedup:.1f}x speedup).")
    print(f"   The performance cliff must be caused by other factors.")

print(f"\n{'='*70}")
print("TEST COMPLETE")
print(f"{'='*70}")
