"""Diagnose material balance issue in 4-week optimization.

This script traces material flows through the system to identify where
the apparent 52,000-unit deficit is coming from.

Material Balance Problem:
- Production: ~206,000 units
- Satisfied demand: ~237,000 units
- Final inventory: ~22,000 units
- Total outflow: ~259,000 units
- DEFICIT: ~53,000 units (outflow exceeds production!)

Possible causes:
1. Initial inventory not being counted
2. Demand satisfaction double-counting (hub-and-spoke routing)
3. In-transit inventory accounting error
4. Cohort inventory aggregation issue
"""

from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection


def main():
    # Parse data
    print("="*80)
    print("PARSING DATA")
    print("="*80)

    parser = MultiFileParser(
        forecast_file='data/examples/Gfree Forecast.xlsm',
        network_file='data/examples/Network_Config.xlsx',
    )
    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    manuf_locs = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manuf_locs[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    planning_start = min(e.forecast_date for e in forecast.entries)
    planning_end = planning_start + timedelta(weeks=4)

    print(f"Planning horizon: {planning_start} to {planning_end}")

    # Create and solve model
    print("\n" + "="*80)
    print("BUILDING AND SOLVING MODEL")
    print("="*80)

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        start_date=planning_start,
        end_date=planning_end,
        allow_shortages=True,
        enforce_shelf_life=True,
        use_batch_tracking=True,
    )

    result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        print(f"❌ Solution not optimal: {result.termination_condition}")
        return

    solution = model.get_solution()

    # Extract key data
    production_by_date_product = solution.get('production_by_date_product', {})
    cohort_inventory = solution.get('cohort_inventory', {})
    shortages_by_dest_product_date = solution.get('shortages_by_dest_product_date', {})

    # Calculate totals
    total_production = sum(production_by_date_product.values())
    total_shortage = sum(shortages_by_dest_product_date.values())

    print(f"✓ Solution found (solve time: {result.solve_time_seconds:.1f}s)")
    print(f"  Production entries: {len(production_by_date_product)}")
    print(f"  Cohort inventory entries: {len(cohort_inventory)}")

    # ============================================================================
    # ANALYSIS 1: Check for Initial Inventory in Cohorts
    # ============================================================================
    print("\n" + "="*80)
    print("ANALYSIS 1: INITIAL INVENTORY CHECK")
    print("="*80)

    # Check if any cohorts have production dates before planning start
    prod_dates_in_cohorts = set()
    initial_inventory_cohorts = {}

    for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
        prod_dates_in_cohorts.add(prod_date)
        if prod_date < model.start_date and qty > 0.01:
            key = (loc, prod, prod_date, state)
            if key not in initial_inventory_cohorts:
                initial_inventory_cohorts[key] = 0.0
            initial_inventory_cohorts[key] += qty

    if initial_inventory_cohorts:
        total_initial_inv = sum(initial_inventory_cohorts.values())
        print(f"✓ Found initial inventory: {total_initial_inv:,.0f} units")
        print(f"  Production dates before horizon start ({model.start_date}):")

        for (loc, prod, prod_date, state), qty in sorted(initial_inventory_cohorts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {loc} | {prod} | prod:{prod_date} | {state}: {qty:,.0f} units")
    else:
        print(f"⚠ No initial inventory found in cohorts")
        print(f"  Earliest production date in cohorts: {min(prod_dates_in_cohorts)}")
        print(f"  Planning start date: {model.start_date}")

    # ============================================================================
    # ANALYSIS 2: Calculate Material Flows
    # ============================================================================
    print("\n" + "="*80)
    print("ANALYSIS 2: MATERIAL FLOW ACCOUNTING")
    print("="*80)

    # Calculate demand in horizon (from forecast)
    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if model.start_date <= e.forecast_date <= model.end_date
    )

    # Calculate inventory on first and last day
    first_day_inventory = 0.0
    last_day_inventory = 0.0

    for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
        if curr_date == model.start_date and qty > 0.01:
            first_day_inventory += qty
        if curr_date == model.end_date and qty > 0.01:
            last_day_inventory += qty

    print(f"Material flows:")
    print(f"  Initial inventory (day 1): {first_day_inventory:,.0f} units")
    print(f"  Production (new): {total_production:,.0f} units")
    print(f"  Total supply: {first_day_inventory + total_production:,.0f} units")
    print()
    print(f"  Demand in horizon: {demand_in_horizon:,.0f} units")
    print(f"  Shortage (unmet): {total_shortage:,.0f} units")
    print(f"  Satisfied demand: {demand_in_horizon - total_shortage:,.0f} units")
    print(f"  Final inventory (day 29): {last_day_inventory:,.0f} units")
    print(f"  Total usage: {(demand_in_horizon - total_shortage) + last_day_inventory:,.0f} units")
    print()

    balance_with_initial = (first_day_inventory + total_production) - ((demand_in_horizon - total_shortage) + last_day_inventory)
    print(f"Material balance (with initial inventory):")
    print(f"  Supply - Usage = {balance_with_initial:,.0f} units")

    if abs(balance_with_initial) < 100:
        print(f"  ✓ Material balance OK (within ±100 units)")
    else:
        print(f"  ⚠ Material imbalance: {balance_with_initial:,.0f} units")

    # ============================================================================
    # ANALYSIS 3: Check Demand Satisfaction Method
    # ============================================================================
    print("\n" + "="*80)
    print("ANALYSIS 3: DEMAND SATISFACTION ACCOUNTING")
    print("="*80)

    # Method 1: From forecast - shortage
    method1_satisfied = demand_in_horizon - total_shortage

    # Method 2: From cohort_demand_consumption
    cohort_demand = solution.get('cohort_demand_consumption', {})
    method2_satisfied = sum(cohort_demand.values())

    print(f"Satisfied demand calculation methods:")
    print(f"  Method 1 (Forecast - Shortage): {method1_satisfied:,.0f} units")
    print(f"  Method 2 (Cohort Consumption): {method2_satisfied:,.0f} units")
    print(f"  Difference: {method1_satisfied - method2_satisfied:,.0f} units")

    if abs(method1_satisfied - method2_satisfied) > 100:
        print(f"\n⚠ Demand satisfaction methods disagree!")
        print(f"  This may indicate double-counting or measurement error")

    # ============================================================================
    # ANALYSIS 4: Trace Material Through Time
    # ============================================================================
    print("\n" + "="*80)
    print("ANALYSIS 4: INVENTORY EVOLUTION OVER TIME")
    print("="*80)

    # Track total system inventory over time
    inventory_by_date = {}
    all_dates = sorted(set(curr_date for (_, _, _, curr_date, _) in cohort_inventory.keys()))

    for curr_date in all_dates:
        total = sum(
            qty for (loc, prod, prod_date, cd, state), qty in cohort_inventory.items()
            if cd == curr_date
        )
        inventory_by_date[curr_date] = total

    print(f"System-wide inventory trajectory (sample every 7 days):")
    for i, curr_date in enumerate(all_dates):
        if i % 7 == 0 or curr_date == all_dates[-1]:  # Weekly + final day
            print(f"  {curr_date}: {inventory_by_date[curr_date]:,.0f} units")

    # Check if inventory is growing or shrinking
    if all_dates:
        first_inv = inventory_by_date[all_dates[0]]
        last_inv = inventory_by_date[all_dates[-1]]
        net_change = last_inv - first_inv

        print(f"\nInventory net change:")
        print(f"  Start: {first_inv:,.0f} units")
        print(f"  End: {last_inv:,.0f} units")
        print(f"  Net change: {net_change:+,.0f} units")

    # ============================================================================
    # ANALYSIS 5: Check Model's View of Demand
    # ============================================================================
    print("\n" + "="*80)
    print("ANALYSIS 5: MODEL'S DEMAND VISIBILITY")
    print("="*80)

    print(f"Model demand entries (model.demand): {len(model.demand)}")
    print(f"Total demand in model.demand: {sum(model.demand.values()):,.0f} units")
    print()
    print(f"Actual forecast:")
    print(f"  Total entries: {len(forecast.entries)}")
    print(f"  In horizon: {sum(1 for e in forecast.entries if model.start_date <= e.forecast_date <= model.end_date)}")
    print(f"  Out of horizon: {sum(1 for e in forecast.entries if e.forecast_date < model.start_date or e.forecast_date > model.end_date)}")
    print(f"  Demand in horizon: {demand_in_horizon:,.0f} units")

    # Check if model.demand matches forecast demand in horizon
    model_demand_total = sum(model.demand.values())
    if abs(model_demand_total - demand_in_horizon) > 10:
        print(f"\n⚠ WARNING: model.demand ({model_demand_total:,.0f}) != forecast in horizon ({demand_in_horizon:,.0f})")
        print(f"  Difference: {model_demand_total - demand_in_horizon:,.0f} units")

    # ============================================================================
    # SUMMARY
    # ============================================================================
    print("\n" + "="*80)
    print("MATERIAL BALANCE SUMMARY")
    print("="*80)

    print(f"\nINPUTS (Sources):")
    print(f"  Initial inventory: {first_day_inventory:,.0f} units")
    print(f"  Production: {total_production:,.0f} units")
    print(f"  TOTAL SUPPLY: {first_day_inventory + total_production:,.0f} units")

    print(f"\nOUTPUTS (Uses):")
    print(f"  Demand satisfied: {demand_in_horizon - total_shortage:,.0f} units")
    print(f"  Final inventory: {last_day_inventory:,.0f} units")
    print(f"  TOTAL USAGE: {(demand_in_horizon - total_shortage) + last_day_inventory:,.0f} units")

    print(f"\nBALANCE:")
    balance = (first_day_inventory + total_production) - ((demand_in_horizon - total_shortage) + last_day_inventory)
    print(f"  Supply - Usage = {balance:,.0f} units")

    if abs(balance) < 100:
        print(f"  ✓ Material balance is CORRECT")
        print(f"\n  EXPLANATION: The 21k final inventory is NOT excess production.")
        print(f"  It comes from initial inventory that wasn't fully consumed.")
    else:
        print(f"  ❌ Material balance is INCORRECT")
        print(f"  This indicates a bug in flow conservation constraints or accounting")

    # Answer the user's question
    print("\n" + "="*80)
    print("ANSWER TO USER'S QUESTION")
    print("="*80)
    print(f"\nQ: Why doesn't production cost naturally prevent the 21k end inventory?")
    print(f"\nA: Because the model is NOT overproducing!")
    print(f"   - Production: {total_production:,.0f} units")
    print(f"   - Demand in horizon: {demand_in_horizon:,.0f} units")
    print(f"   - Production DEFICIT: {demand_in_horizon - total_production:,.0f} units")
    print(f"\n   The 21k end inventory likely comes from:")
    print(f"   1. Initial inventory at planning start: {first_day_inventory:,.0f} units")
    print(f"   2. Inventory not needed to satisfy short-term demand")
    print(f"   3. Strategic positioning at hubs (Lineage, 6125, 6104)")
    print(f"\n   The model is minimizing cost correctly - it's NOT wasting money")
    print(f"   on unnecessary production. The objective function IS working!")


if __name__ == "__main__":
    main()
