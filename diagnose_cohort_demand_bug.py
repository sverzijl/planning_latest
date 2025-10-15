"""
Diagnose the cohort-based demand satisfaction bug.

Theory: The cohort demand satisfaction constraint allows inventory to exist at a location
without being used to satisfy demand at that same location.

We'll examine:
1. Locations with both demand and end inventory
2. Whether cohort inventory is "reachable" for demand satisfaction
3. The specific constraint that's failing to connect inventory to demand
"""

from pathlib import Path
from datetime import date
from collections import defaultdict

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.location import LocationType
from src.models.manufacturing import ManufacturingSite
from src.models.truck_schedule import TruckScheduleCollection


def main():
    print("="*80)
    print("COHORT DEMAND SATISFACTION BUG DIAGNOSIS")
    print("="*80)

    # Load data
    data_dir = Path("data/examples")
    parser = MultiFileParser(
        forecast_file=data_dir / "Gfree Forecast.xlsm",
        network_file=data_dir / "Network_Config.xlsx",
        inventory_file=data_dir / "inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)

    model = IntegratedProductionDistributionModel(
        forecast=forecast, labor_calendar=labor_calendar, manufacturing_site=manufacturing_site,
        cost_structure=cost_structure, locations=locations, routes=routes,
        truck_schedules=truck_schedules, max_routes_per_destination=5,
        allow_shortages=True, enforce_shelf_life=True,
        initial_inventory=inventory_snapshot.to_optimization_dict(),
        inventory_snapshot_date=inventory_snapshot.snapshot_date,
        start_date=inventory_snapshot.snapshot_date, end_date=date(2025, 11, 3),
        use_batch_tracking=True,
    )

    result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01,
                        use_aggressive_heuristics=True, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        print("Solution not feasible")
        return

    solution = model.get_solution()
    cohort_inv = solution.get('cohort_inventory', {})

    # Find locations with both demand and end inventory
    print(f"\n{'='*80}")
    print("STEP 1: Find locations with BOTH demand AND end inventory")
    print(f"{'='*80}")

    # Get demand by location
    demand_by_location = defaultdict(float)
    for (loc, prod, d), qty in model.demand.items():
        demand_by_location[loc] += qty

    # Get end inventory by location
    end_inv_by_location = defaultdict(float)
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if curr_date == model.end_date and qty > 0.01:
            end_inv_by_location[loc] += qty

    # Find overlaps
    locations_with_both = []
    for loc in demand_by_location.keys():
        if loc in end_inv_by_location and end_inv_by_location[loc] > 100:
            locations_with_both.append(loc)

    if not locations_with_both:
        print("✓ No locations have both demand and significant end inventory")
        print("  The issue must be temporal or routing-related")
        return

    print(f"Found {len(locations_with_both)} locations with BOTH demand and end inventory:")
    for loc in locations_with_both:
        print(f"  {loc}: {demand_by_location[loc]:,.0f} demand, {end_inv_by_location[loc]:,.0f} end inventory")

    # Pick the location with most end inventory for detailed analysis
    target_loc = max(locations_with_both, key=lambda l: end_inv_by_location[l])

    print(f"\n{'='*80}")
    print(f"STEP 2: Detailed analysis of location {target_loc}")
    print(f"{'='*80}")

    # Get all inventory at this location over time
    inventory_timeline = defaultdict(lambda: {'total': 0, 'by_cohort': []})
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if loc == target_loc and qty > 0.01:
            inventory_timeline[curr_date]['total'] += qty
            inventory_timeline[curr_date]['by_cohort'].append({
                'product': prod,
                'prod_date': prod_date,
                'state': state,
                'qty': qty
            })

    # Get demand at this location over time
    demand_timeline = defaultdict(float)
    for (loc, prod, d), qty in model.demand.items():
        if loc == target_loc:
            demand_timeline[d] += qty

    # Get shortage at this location over time
    shortage_timeline = defaultdict(float)
    if 'shortage' in solution:
        for (loc, prod, d), qty in solution['shortage'].items():
            if loc == target_loc and qty > 0.01:
                shortage_timeline[d] += qty

    print(f"\nInventory, Demand, and Shortage timeline for {target_loc}:")
    print(f"{'Date':<12} {'Inventory':>12} {'Demand':>12} {'Shortage':>12} {'Issue?':<10}")
    print("-"*60)

    all_dates = sorted(set(inventory_timeline.keys()) | set(demand_timeline.keys()))

    problematic_dates = []
    for d in all_dates:
        inv = inventory_timeline[d]['total']
        dem = demand_timeline.get(d, 0)
        short = shortage_timeline.get(d, 0)

        issue = ''
        if inv > 100 and dem > 0:
            issue = '⚠️ BOTH'
            problematic_dates.append(d)
        elif short > 0:
            issue = 'Shortage'

        if inv > 0.01 or dem > 0.01:
            print(f"{d} {inv:>12,.0f} {dem:>12,.0f} {short:>12,.0f} {issue:<10}")

    if not problematic_dates:
        print("\n✓ No dates with simultaneous inventory and demand")
        print("  Inventory arrives AFTER all demand is satisfied")
        return

    print(f"\n⚠️ Found {len(problematic_dates)} dates with BOTH inventory and demand!")
    print(f"This should be impossible - inventory should satisfy demand.")

    # Examine the first problematic date in detail
    problem_date = problematic_dates[0]

    print(f"\n{'='*80}")
    print(f"STEP 3: Deep dive into {problem_date} at {target_loc}")
    print(f"{'='*80}")

    # Get cohort details on this date
    cohorts_on_date = inventory_timeline[problem_date]['by_cohort']
    demand_on_date = demand_timeline[problem_date]

    print(f"\nInventory cohorts available on {problem_date}:")
    print(f"{'Product':<35} {'Prod Date':<12} {'State':<10} {'Quantity':>12}")
    print("-"*75)

    total_cohort_inv = 0
    for cohort in sorted(cohorts_on_date, key=lambda c: c['qty'], reverse=True):
        print(f"{cohort['product']:<35} {cohort['prod_date']} {cohort['state']:<10} {cohort['qty']:>12,.0f}")
        total_cohort_inv += cohort['qty']

    print(f"{'-'*75}")
    print(f"{'TOTAL':<35} {'':<12} {'':<10} {total_cohort_inv:>12,.0f}")

    print(f"\nDemand on {problem_date}: {demand_on_date:,.0f} units")
    print(f"Shortage on {problem_date}: {shortage_timeline.get(problem_date, 0):,.0f} units")

    # Check cohort demand consumption
    cohort_consumption_on_date = defaultdict(float)
    cohort_demand_consumption = solution.get('cohort_demand_consumption', {})

    for (loc, prod, prod_date, demand_date), qty in cohort_demand_consumption.items():
        if loc == target_loc and demand_date == problem_date:
            cohort_consumption_on_date[(prod, prod_date)] += qty

    if cohort_consumption_on_date:
        print(f"\nCohort consumption for demand on {problem_date}:")
        print(f"{'Product':<35} {'Prod Date':<12} {'Consumed':>12}")
        print("-"*65)

        total_consumed = 0
        for (prod, prod_date), qty in sorted(cohort_consumption_on_date.items(), key=lambda x: x[1], reverse=True):
            print(f"{prod:<35} {prod_date} {qty:>12,.0f}")
            total_consumed += qty

        print(f"{'-'*65}")
        print(f"{'TOTAL CONSUMED':<35} {'':<12} {total_consumed:>12,.0f}")
    else:
        print(f"\n⚠️ NO cohort consumption recorded for this demand!")
        print(f"   This indicates the demand satisfaction constraint is not working.")

    # Key diagnosis
    print(f"\n{'='*80}")
    print("DIAGNOSIS")
    print(f"{'='*80}")

    if total_cohort_inv > demand_on_date and shortage_timeline.get(problem_date, 0) > 0:
        print(f"\n✓✓✓ BUG CONFIRMED ✓✓✓")
        print(f"On {problem_date} at {target_loc}:")
        print(f"  Available inventory: {total_cohort_inv:,.0f} units")
        print(f"  Demand: {demand_on_date:,.0f} units")
        print(f"  Shortage: {shortage_timeline.get(problem_date, 0):,.0f} units")
        print(f"\nInventory is AVAILABLE but not being used to satisfy demand!")
        print(f"This is a bug in the cohort demand satisfaction constraint.")

        # Check if it's a cohort reachability issue
        print(f"\nPossible causes:")
        print(f"1. Cohort reachability check is too restrictive")
        print(f"2. demand_from_cohort variable is not properly linked to inventory")
        print(f"3. Cohort index set excludes available cohorts")

    elif total_cohort_inv < demand_on_date:
        print(f"\n✓ Inventory is insufficient on this date")
        print(f"  Available: {total_cohort_inv:,.0f}, Demand: {demand_on_date:,.0f}")
        print(f"  Shortage is expected")
    else:
        print(f"\n? Inventory and demand both exist, no shortage")
        print(f"  This may be working correctly - check other dates")

    # Check if the issue is at END of horizon only
    if problem_date == model.end_date:
        print(f"\n⚠️ NOTE: This is the FINAL DAY of the planning horizon")
        print(f"Inventory on the final day cannot satisfy future demand (no future exists)")
        print(f"But if demand exists ON the final day, inventory should be consumed.")

        # Check if there's actually demand on the final day
        final_day_demand = demand_timeline.get(model.end_date, 0)
        if final_day_demand > 0:
            print(f"\n✓ Demand DOES exist on final day: {final_day_demand:,.0f} units")
            print(f"  This inventory should be consumed - BUG CONFIRMED")
        else:
            print(f"\n✓ NO demand on final day")
            print(f"  End inventory is expected (produced for earlier days but not consumed)")


if __name__ == "__main__":
    main()
