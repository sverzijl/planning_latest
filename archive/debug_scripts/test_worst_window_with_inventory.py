"""
Test the worst-case window (Oct 6 - Nov 3) WITH initial inventory.

The diagnostic showed this window has:
- Highest end inventory (7,949 units WITHOUT initial inventory)
- Front-loaded demand (only 3.6% in last 3 days)
- Strong negative correlation with late demand

This test adds initial inventory to see if we can replicate the 11k+ issue.
"""

from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.location import LocationType


def main():
    print("="*80)
    print("WORST-CASE WINDOW TEST: Oct 6 - Nov 3 WITH INITIAL INVENTORY")
    print("="*80)

    # Load data files
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory.XLSX"  # Note: uppercase extension

    print(f"\nLoading data from:")
    print(f"  Forecast: {forecast_file}")
    print(f"  Network: {network_file}")
    print(f"  Inventory: {inventory_file}")

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=inventory_file if inventory_file.exists() else None,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Create manufacturing site
    from src.models.manufacturing import ManufacturingSite
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")

    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=manuf_loc.production_rate if hasattr(manuf_loc, 'production_rate') and manuf_loc.production_rate else 1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Convert truck schedules
    from src.models.truck_schedule import TruckScheduleCollection
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    # Parse initial inventory
    initial_inventory = None
    inventory_snapshot_date = None

    if inventory_file.exists():
        inventory_snapshot = parser.parse_inventory(snapshot_date=None)
        initial_inventory = inventory_snapshot
        inventory_snapshot_date = inventory_snapshot.snapshot_date

        total_init_inventory = sum(initial_inventory.to_optimization_dict().values())
        print(f"\n✓ Initial inventory: {total_init_inventory:,.0f} units at {inventory_snapshot_date}")
    else:
        print(f"\n⚠ No initial inventory file found")

    # Define the worst-case window (Oct 6 - Nov 3)
    planning_start_date = date(2025, 10, 6)
    planning_end_date = date(2025, 11, 3)

    print(f"\n{'='*80}")
    print(f"PLANNING HORIZON: {planning_start_date} to {planning_end_date}")
    print(f"{'='*80}")

    # Note: inventory snapshot date is Oct 13, which is AFTER planning start (Oct 6)
    # This is intentional - we're testing if the model handles this correctly
    if inventory_snapshot_date and inventory_snapshot_date > planning_start_date:
        print(f"\n⚠ WARNING: Inventory snapshot date ({inventory_snapshot_date}) is AFTER planning start ({planning_start_date})")
        print(f"  This means we're trying to plan backward in time")
        print(f"  Adjusting planning start to match inventory snapshot date...")
        planning_start_date = inventory_snapshot_date

    # Create model WITH initial inventory
    print(f"\n{'='*80}")
    print("MODEL CREATION")
    print(f"{'='*80}")

    model_start = time.time()

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        max_routes_per_destination=5,
        allow_shortages=True,
        enforce_shelf_life=True,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        start_date=planning_start_date,
        end_date=planning_end_date,
        use_batch_tracking=True,
    )

    model_build_time = time.time() - model_start

    print(f"✓ Model built in {model_build_time:.2f}s")
    print(f"  Routes enumerated: {len(model.enumerated_routes)}")
    print(f"  Planning horizon: {len(model.production_dates)} days")
    print(f"  Actual dates: {model.start_date} to {model.end_date}")

    # Solve
    print(f"\n{'='*80}")
    print("SOLVING OPTIMIZATION")
    print(f"{'='*80}")

    solve_start = time.time()

    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    solve_time = time.time() - solve_start

    print(f"✓ Solved in {solve_time:.2f}s")
    print(f"  Status: {result.termination_condition}")
    print(f"  Objective value: ${result.objective_value:,.2f}")

    if not (result.is_optimal() or result.is_feasible()):
        print(f"\n⚠ Solution not feasible - stopping analysis")
        return

    # Extract solution
    solution = model.get_solution()
    if not solution:
        print(f"\n⚠ No solution available - stopping analysis")
        return

    # Calculate metrics
    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())
    total_shortage = solution.get('total_shortage_units', 0)

    # Demand in horizon
    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if model.start_date <= e.forecast_date <= model.end_date
    )

    fill_rate = 100 * (1 - total_shortage / demand_in_horizon) if demand_in_horizon > 0 else 100

    # Cost breakdown
    print(f"\n{'='*80}")
    print("COST BREAKDOWN")
    print(f"{'='*80}")
    print(f"Labor cost:      ${solution.get('total_labor_cost', 0):>12,.2f}")
    print(f"Production cost: ${solution.get('total_production_cost', 0):>12,.2f}")
    print(f"Transport cost:  ${solution.get('total_transport_cost', 0):>12,.2f}")
    print(f"Inventory cost:  ${solution.get('total_inventory_cost', 0):>12,.2f}")
    print(f"Shortage cost:   ${solution.get('total_shortage_cost', 0):>12,.2f}")

    # Final day inventory
    final_day_inventory = 0.0
    final_day_by_location = {}
    final_day_by_product = {}

    if 'cohort_inventory' in solution:
        cohort_inv = solution['cohort_inventory']

        for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
            if curr_date == model.end_date and qty > 0.01:
                final_day_inventory += qty
                if loc not in final_day_by_location:
                    final_day_by_location[loc] = 0.0
                final_day_by_location[loc] += qty

                if prod not in final_day_by_product:
                    final_day_by_product[prod] = 0.0
                final_day_by_product[prod] += qty

    # Shipments beyond horizon
    shipments = model.get_shipment_plan() or []
    shipments_after_horizon = [s for s in shipments if s.delivery_date > model.end_date]
    total_in_transit_beyond = sum(s.quantity for s in shipments_after_horizon)

    # Material balance
    cohort_demand_consumption = solution.get('cohort_demand_consumption', {})
    actual_consumption = sum(cohort_demand_consumption.values())
    total_outflow = actual_consumption + final_day_inventory + total_in_transit_beyond
    material_balance = total_production - total_outflow

    # Initial inventory usage
    if initial_inventory:
        total_init_inv = sum(initial_inventory.to_optimization_dict().values())
        inventory_contribution = total_init_inv
    else:
        inventory_contribution = 0.0

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Demand in horizon:    {demand_in_horizon:>12,.0f} units")
    print(f"Initial inventory:    {inventory_contribution:>12,.0f} units")
    print(f"Total production:     {total_production:>12,.0f} units")
    print(f"Available supply:     {inventory_contribution + total_production:>12,.0f} units")
    print(f"Fill rate:            {fill_rate:>12.1f}%")
    print(f"Shortage:             {total_shortage:>12,.0f} units")
    print(f"")
    print(f"Actual consumption:   {actual_consumption:>12,.0f} units")
    print(f"Final day inventory:  {final_day_inventory:>12,.0f} units")
    print(f"In-transit beyond:    {total_in_transit_beyond:>12,.0f} units")
    print(f"Material balance:     {material_balance:>12,.0f} units")

    print(f"\n{'='*80}")
    print("END INVENTORY ANALYSIS")
    print(f"{'='*80}")

    if final_day_inventory > 0.01:
        print(f"\nTotal end inventory: {final_day_inventory:,.0f} units")
        print(f"Cost of end inventory: ${final_day_inventory * cost_structure.production_cost_per_unit:,.2f}")

        print(f"\nBy location:")
        for loc, qty in sorted(final_day_by_location.items(), key=lambda x: x[1], reverse=True):
            if qty > 0.01:
                pct = 100 * qty / final_day_inventory
                print(f"  {loc}: {qty:>10,.0f} units ({pct:>5.1f}%)")

        print(f"\nBy product:")
        for prod, qty in sorted(final_day_by_product.items(), key=lambda x: x[1], reverse=True):
            if qty > 0.01:
                pct = 100 * qty / final_day_inventory
                print(f"  {prod}: {qty:>10,.0f} units ({pct:>5.1f}%)")

        # Compare to scenario without initial inventory
        print(f"\n{'='*80}")
        print("COMPARISON TO SCENARIO WITHOUT INITIAL INVENTORY")
        print(f"{'='*80}")
        print(f"End inventory WITHOUT initial inv: 7,949 units (from diagnostic)")
        print(f"End inventory WITH initial inv:    {final_day_inventory:,.0f} units")
        print(f"Difference:                        {final_day_inventory - 7949:+,.0f} units")

        if final_day_inventory > 10000:
            print(f"\n✓ REPLICATED 11k+ END INVENTORY BUG!")
        elif final_day_inventory > 7949:
            print(f"\n⚠ End inventory INCREASED with initial inventory")
        else:
            print(f"\n✓ End inventory DECREASED with initial inventory (unexpected)")
    else:
        print(f"\n✓ No significant end inventory")

    # Check if initial inventory was actually used
    if initial_inventory and 'cohort_inventory' in solution:
        cohort_inv = solution['cohort_inventory']

        # Count cohorts from initial inventory date
        initial_inv_cohorts = sum(
            qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items()
            if prod_date == inventory_snapshot_date and curr_date > inventory_snapshot_date
        )

        print(f"\n{'='*80}")
        print("INITIAL INVENTORY UTILIZATION")
        print(f"{'='*80}")
        print(f"Initial inventory provided: {inventory_contribution:,.0f} units")
        print(f"Initial inventory used:     {inventory_contribution - sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items() if prod_date == inventory_snapshot_date and curr_date == model.end_date):,.0f} units")

        # Check if initial inventory is still sitting at locations
        initial_inv_at_end = sum(
            qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items()
            if prod_date == inventory_snapshot_date and curr_date == model.end_date
        )

        if initial_inv_at_end > 0.01:
            print(f"Initial inventory remaining at end: {initial_inv_at_end:,.0f} units")
            print(f"  → Part of end inventory is UNUSED initial inventory")
        else:
            print(f"Initial inventory fully consumed ✓")


if __name__ == "__main__":
    main()
