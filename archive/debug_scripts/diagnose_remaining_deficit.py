"""Diagnose remaining -33k material balance deficit using simple scenarios.

Test progression from working (Test 5) to failing (Test 6):
- Test 5: 1 prod, 1 dest (WA), 1 week → Balance = 0 ✅
- Test 6: 5 prods, 8 dests, 4 weeks → Balance = -33k ❌

Progressive tests to isolate:
A. 1 prod, WA, 2 weeks (extend time)
B. 2 prods, WA, 1 week (add product)
C. 1 prod, 2 dests (WA + one other), 1 week (add destination)

This will pinpoint what combination triggers the deficit.
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry
from src.optimization import IntegratedProductionDistributionModel

# Parse real network
parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx',
)

full_forecast, locations, routes, labor, trucks_list, costs = parser.parse_all()

manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=costs.production_cost_per_unit,
)

trucks = TruckScheduleCollection(schedules=trucks_list)

all_products = list(set(e.product_id for e in full_forecast.entries))
all_destinations = list(set(e.location_id for e in full_forecast.entries))

print("="*80)
print("REMAINING DEFICIT ISOLATION")
print("="*80)
print(f"Starting from Test 5 (works) → Test 6 (fails)")
print()

def run_test(products, destinations, num_weeks, test_name):
    """Run test and return balance."""
    start_date = date(2025, 10, 13)
    end_date = start_date + timedelta(weeks=num_weeks) - timedelta(days=1)

    forecast_entries = []
    daily_demand = 100.0

    for dest in destinations:
        for prod in products:
            for day_offset in range(4, num_weeks * 7):  # Start day 4 (allow WA transit)
                forecast_entries.append(
                    ForecastEntry(
                        location_id=dest,
                        product_id=prod,
                        forecast_date=start_date + timedelta(days=day_offset),
                        quantity=daily_demand,
                    )
                )

    forecast = Forecast(name=test_name, entries=forecast_entries)
    total_demand = sum(e.quantity for e in forecast_entries)

    model = IntegratedProductionDistributionModel(
        forecast=forecast, labor_calendar=labor, manufacturing_site=manufacturing_site,
        cost_structure=costs, locations=locations, routes=routes,
        truck_schedules=trucks, start_date=start_date, end_date=end_date,
        allow_shortages=True, enforce_shelf_life=True, use_batch_tracking=True,
        initial_inventory=None,
    )

    result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        print(f"{test_name}: INFEASIBLE")
        return None

    solution = model.get_solution()
    production = sum(solution.get('production_by_date_product', {}).values())
    consumption = sum(solution.get('cohort_demand_consumption', {}).values())

    cohort_inv = solution.get('cohort_inventory', {})
    first_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == start_date)
    last_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == end_date)

    supply = first_day + production
    usage = consumption + last_day
    balance = supply - usage

    status = "✅" if abs(balance) <= 10 else "❌"
    print(f"{test_name}:")
    print(f"  {len(products)}p × {len(destinations)}d × {num_weeks}w | Demand={total_demand:>6,.0f} | Prod={production:>6,.0f} | Balance={balance:>7.0f} {status}")

    return balance

# Progressive isolation
print("A. Extend time from Test 5:")
run_test([all_products[0]], ["6130"], 1, "  1 prod, WA, 1 week (baseline)")
run_test([all_products[0]], ["6130"], 2, "  1 prod, WA, 2 weeks")
run_test([all_products[0]], ["6130"], 3, "  1 prod, WA, 3 weeks")

print()
print("B. Add products:")
run_test([all_products[0]], ["6130"], 1, "  1 prod, WA, 1 week (baseline)")
run_test(all_products[:2], ["6130"], 1, "  2 prods, WA, 1 week")
run_test(all_products[:3], ["6130"], 1, "  3 prods, WA, 1 week")

print()
print("C. Add destinations:")
run_test([all_products[0]], ["6130"], 1, "  1 prod, WA only, 1 week (baseline)")
run_test([all_products[0]], ["6130", "6110"], 1, "  1 prod, WA + QLD, 1 week")
run_test([all_products[0]], ["6130", "6110", "6104"], 1, "  1 prod, 3 dests, 1 week")

print()
print("D. Combination:")
run_test([all_products[0]], ["6130"], 2, "  1 prod, WA, 2 weeks")
run_test(all_products[:2], ["6130"], 2, "  2 prods, WA, 2 weeks")
run_test(all_products[:2], ["6130", "6110"], 2, "  2 prods, 2 dests, 2 weeks")

print()
print("="*80)
print("CONCLUSION")
print("="*80)
print("The first test showing deficit reveals the trigger")
