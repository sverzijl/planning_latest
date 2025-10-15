"""Systematic complexity testing to find where phantom inventory appears.

Test progression:
1. ✅ 1 product, 1 destination, 1 week (baseline - should work)
2. ALL 5 products, 1 destination, 1 week (multi-product test)
3. 1 product, 1 destination, 4 weeks (extended horizon test)
4. ALL 5 products, 1 destination, 4 weeks (product + horizon)
5. ALL 5 products, ALL 9 destinations, 1 week (multi-destination test)
6. ALL 5 products, ALL 9 destinations, 4 weeks (full scenario - expect ~50k deficit)

This will pinpoint EXACTLY what combination causes the phantom inventory.
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

full_forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Setup common objects
manuf_locs = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manuf_locs[0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Get all products from real forecast
all_products = list(set(e.product_id for e in full_forecast.entries))
all_destinations = list(set(e.location_id for e in full_forecast.entries))

print(f"Real data: {len(all_products)} products, {len(all_destinations)} destinations")
print(f"Products: {all_products}")
print(f"Destinations: {all_destinations}")
print()

def run_test(products, destinations, num_weeks, test_name):
    """Run test with specified products, destinations, and horizon."""
    start_date = date(2025, 10, 13)
    end_date = start_date + timedelta(weeks=num_weeks) - timedelta(days=1)

    # Create minimal forecast
    forecast_entries = []
    daily_demand = 100.0  # Small amount per destination per day

    for dest in destinations:
        for prod in products:
            # Start demand from day 2 (allow transit time)
            for day_offset in range(2, num_weeks * 7):
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

    print("="*80)
    print(test_name.upper())
    print("="*80)
    print(f"Products: {len(products)}, Destinations: {len(destinations)}, Weeks: {num_weeks}")
    print(f"Total demand: {total_demand:,.0f} units")

    # Create model
    model = IntegratedProductionDistributionModel(
        forecast=forecast, labor_calendar=labor_calendar, manufacturing_site=manufacturing_site,
        cost_structure=cost_structure, locations=locations, routes=routes,
        truck_schedules=truck_schedules, start_date=start_date, end_date=end_date,
        allow_shortages=True, enforce_shelf_life=True, use_batch_tracking=True,
        initial_inventory=None,
    )

    # Solve
    result = model.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        print(f"❌ Not feasible: {result.termination_condition}")
        return None

    solution = model.get_solution()

    production = sum(solution.get('production_by_date_product', {}).values())
    consumption = sum(solution.get('cohort_demand_consumption', {}).values())
    shortage = sum(solution.get('shortages_by_dest_product_date', {}).values())

    cohort_inv = solution.get('cohort_inventory', {})
    first_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == start_date)
    last_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == end_date)

    # Material balance
    supply = first_day + production
    usage = consumption + last_day
    balance = supply - usage

    print(f"Production: {production:,.0f} | Consumption: {consumption:,.0f} | Shortage: {shortage:,.0f}")
    print(f"Day 1 inv: {first_day:,.0f} | Last day inv: {last_day:,.0f}")
    print(f"Material Balance: {balance:+,.0f} units", end="")

    if abs(balance) <= 1:
        print(" ✅ OK")
    else:
        print(f" ❌ DEFICIT")

        if first_day > 1:
            print(f"  → Day 1 phantom inventory: {first_day:,.0f} units")

    print()
    return balance


# Run test progression
print("\\n" + "="*80)
print("TEST PROGRESSION")
print("="*80)
print()

# Test 1: Baseline (1 product, 1 dest, 1 week)
run_test(
    products=[all_products[0]],
    destinations=["6110"],
    num_weeks=1,
    test_name="Test 1: 1 Product, 1 Dest, 1 Week (Baseline)"
)

# Test 2: All products (5 products, 1 dest, 1 week)
run_test(
    products=all_products,
    destinations=["6110"],
    num_weeks=1,
    test_name="Test 2: 5 Products, 1 Dest, 1 Week"
)

# Test 3: Extended horizon (1 product, 1 dest, 4 weeks)
run_test(
    products=[all_products[0]],
    destinations=["6110"],
    num_weeks=4,
    test_name="Test 3: 1 Product, 1 Dest, 4 Weeks"
)

# Test 4: Multi-destination (1 product, 3 dests, 1 week)
run_test(
    products=[all_products[0]],
    destinations=["6110", "6104", "6125"],  # Direct + both hubs
    num_weeks=1,
    test_name="Test 4: 1 Product, 3 Dests, 1 Week"
)

# Test 5: Include Lineage route (1 product, WA only, 1 week)
run_test(
    products=[all_products[0]],
    destinations=["6130"],  # WA - goes through Lineage
    num_weeks=1,
    test_name="Test 5: 1 Product, WA (Lineage route), 1 Week"
)

# Test 6: Full complexity (5 products, all dests, 4 weeks)
run_test(
    products=all_products,
    destinations=all_destinations,
    num_weeks=4,
    test_name="Test 6: 5 Products, 9 Dests, 4 Weeks (FULL)"
)

print("="*80)
print("CONCLUSION")
print("="*80)
print("The test that first shows material balance violation reveals the bug source")
