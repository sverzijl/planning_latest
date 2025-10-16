"""Compare HiGHS vs CBC performance on 14-day and 21-day windows."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
import time
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization import IntegratedProductionDistributionModel

print("=" * 80)
print("SOLVER COMPARISON: HiGHS vs CBC")
print("=" * 80)

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

def test_solver(window_days, solver_name, description):
    """Test a solver on a window size."""
    start_date = date(2025, 6, 2)
    end_date = start_date + __import__('datetime').timedelta(days=window_days - 1)

    forecast_entries = [
        e for e in full_forecast.entries
        if start_date <= e.forecast_date <= end_date
    ]

    test_forecast = Forecast(
        name=f"test_{window_days}d",
        entries=forecast_entries,
        creation_date=full_forecast.creation_date
    )

    model = IntegratedProductionDistributionModel(
        forecast=test_forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    print(f"\n{description}")
    print(f"  Solver: {solver_name}")
    print(f"  Window: {window_days} days")

    start_time = time.time()
    try:
        result = model.solve(
            solver_name=solver_name,
            time_limit_seconds=300,
            tee=False
        )
        solve_time = time.time() - start_time

        if result.is_optimal() or result.is_feasible():
            print(f"  ✅ SOLVED in {solve_time:.2f}s")
            print(f"  Status: {result.termination_condition}")
            if result.objective_value:
                print(f"  Cost: ${result.objective_value:,.2f}")
            return solve_time
        else:
            print(f"  ❌ FAILED after {solve_time:.2f}s")
            print(f"  Status: {result.termination_condition}")
            if result.infeasibility_message:
                print(f"  Message: {result.infeasibility_message[:100]}")
            return None
    except Exception as e:
        solve_time = time.time() - start_time
        print(f"  ❌ EXCEPTION after {solve_time:.2f}s")
        print(f"  Error: {str(e)[:100]}")
        return None

# Test 14-day window
print("\n" + "=" * 80)
print("TEST 1: 14-DAY WINDOW (Baseline)")
print("=" * 80)

cbc_14d = test_solver(14, 'cbc', "CBC on 14-day")
highs_14d = test_solver(14, 'highs', "HiGHS on 14-day")

if highs_14d and cbc_14d:
    speedup = cbc_14d / highs_14d
    print(f"\n  → HiGHS is {speedup:.1f}x faster on 14-day window")

# Test 21-day window
print("\n" + "=" * 80)
print("TEST 2: 21-DAY WINDOW (Challenge)")
print("=" * 80)

cbc_21d = test_solver(21, 'cbc', "CBC on 21-day")
highs_21d = test_solver(21, 'highs', "HiGHS on 21-day")

if highs_21d and highs_21d < 300:
    print(f"\n  🎯 SUCCESS! HiGHS solves 21-day windows in {highs_21d:.2f}s")
    print(f"  → This unlocks hierarchical 3-week configurations!")
elif not highs_14d:
    print(f"\n  ⚠ HiGHS not available or installation issue")
else:
    print(f"\n  → HiGHS also struggles with 21-day windows")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

if highs_14d and cbc_14d and highs_14d < cbc_14d:
    speedup = cbc_14d / highs_14d
    print(f"\n✅ HiGHS is {speedup:.1f}x faster than CBC")
    print(f"   Recommendation: Switch to HiGHS for all solves")

    if highs_21d and highs_21d < 300:
        print(f"\n🎯 HiGHS solves 21-day windows!")
        print(f"   Next step: Test hierarchical 3-week configurations")
        print(f"   Expected outcome: 2-5% cost reduction vs 14-day baseline")
elif not highs_14d:
    print(f"\n⚠ HiGHS not available")
    print(f"   Install with: pip install highspy")
    print(f"   Or apply CBC tuning parameters (see SOLVER_OPTIMIZATION_RECOMMENDATIONS.md)")
else:
    print(f"\n⚠ HiGHS installation may have issues")
    print(f"   Fallback: Use CBC with tuning parameters")

print("\n" + "=" * 80)
print("\nNext Steps:")
print("  1. If HiGHS works: Test 21-day hierarchical (weeks 1-2 daily, week 3 weekly)")
print("  2. If HiGHS unavailable: Apply CBC tuning (see recommendations doc)")
print("  3. Production decision: 14-day/7-day (proven) vs 21-day hierarchical (if HiGHS works)")
print("=" * 80)
