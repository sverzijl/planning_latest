"""
Test to check if hub can ship without receiving inventory first.

This test specifically checks if the hub can ship on day 1 without any
arrivals from manufacturing.
"""
from datetime import date, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import IntegratedProductionDistributionModel


def main():
    """
    Test scenario: Demand on day 1, but 2-day transit through hub.

    If material balance is correct:
    - Manufacturing must produce on day -1 (before planning horizon starts)
    - OR demand on day 1 cannot be satisfied

    If there's a bug:
    - Hub will ship on day -1 without having received anything
    - This would manifest as "phantom inventory"
    """
    start_date = date(2025, 10, 13)  # Monday
    end_date = start_date + timedelta(days=6)

    print("\n" + "="*80)
    print("PHANTOM INVENTORY TEST")
    print("="*80)
    print(f"Scenario: Demand on DAY 1, but need 2-day transit through hub")
    print(f"Expected: Should be INFEASIBLE or show SHORTAGE (can't ship before producing)")
    print(f"Bug behavior: Hub ships without receiving (phantom inventory)")

    # Locations
    manufacturing = Location(
        id="6122",
        name="Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
    )

    hub = Location(
        id="6125",
        name="VIC Hub",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
        capacity=50000,
    )

    destination = Location(
        id="6123",
        name="Clayton",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
        capacity=35000,
    )

    locations = [manufacturing, hub, destination]

    # Routes: 6122→6125 (1 day) and 6125→6123 (1 day) = 2 days total
    route1 = Route(
        id="R1",
        origin_id="6122",
        destination_id="6125",
        transport_mode=StorageMode.AMBIENT,
        transit_time_days=1.0,
        cost=0.03,
    )

    route2 = Route(
        id="R2",
        origin_id="6125",
        destination_id="6123",
        transport_mode=StorageMode.AMBIENT,
        transit_time_days=1.0,
        cost=0.02,
    )

    routes = [route1, route2]

    # KEY: Demand on FIRST DAY of planning horizon
    # To satisfy this, hub must ship on day 0, which requires arrival on day 0,
    # which requires manufacturing on day -1 (BEFORE planning horizon)
    product_id = "TEST_PRODUCT"
    forecast_entries = [
        ForecastEntry(
            location_id="6123",
            product_id=product_id,
            forecast_date=start_date,  # DAY 1!
            quantity=1000.0,
        )
    ]

    forecast = Forecast(name="Phantom Test", entries=forecast_entries)

    print(f"\nForecast: 1,000 units on {start_date} (FIRST DAY)")

    # Labor calendar
    labor_days = []
    for day_offset in range(7):
        labor_date = start_date + timedelta(days=day_offset)
        weekday = labor_date.weekday()

        labor_days.append(
            LaborDay(
                date=labor_date,
                fixed_hours=12.0 if weekday < 5 else 0.0,
                regular_rate=25.0,
                overtime_rate=37.5,
                non_fixed_rate=50.0,
                minimum_hours=4.0 if weekday >= 5 else 0.0,
            )
        )

    labor_calendar = LaborCalendar(name="Test Calendar", days=labor_days)

    # Manufacturing site
    manufacturing_site = ManufacturingSite(
        id="6122",
        name="Manufacturing",
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=5.0,
    )

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=5.0,
        setup_cost=0.0,
        default_regular_rate=25.0,
        default_overtime_rate=37.5,
        default_non_fixed_rate=50.0,
        storage_cost_frozen_per_unit_day=0.10,
        storage_cost_ambient_per_unit_day=0.002,
        shortage_penalty_per_unit=1000.0,
        waste_cost_multiplier=1.5,
    )

    # Truck schedules (empty)
    truck_schedules = TruckScheduleCollection(schedules=[])

    # Create model WITHOUT initial inventory
    print("\nBuilding model (no initial inventory)...")
    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        start_date=start_date,
        end_date=end_date,
        allow_shortages=True,  # Allow shortages to see if model finds a way
        enforce_shelf_life=True,
        use_batch_tracking=True,
        initial_inventory=None,  # NO initial inventory
    )

    print(f"✓ Model created")

    # Solve
    print("\nSolving...")
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        mip_gap=0.01,
        tee=False,
    )

    print(f"✓ Solved in {result.solve_time_seconds:.2f}s ({result.termination_condition})")

    # Extract solution
    solution = model.get_solution()

    # Analysis
    production = solution.get('production_by_date_product', {})
    shipments_leg = solution.get('shipments_by_leg_product_date', {})
    cohort_inv = solution.get('cohort_inventory', {})
    shortages = solution.get('shortages_by_dest_product_date', {})

    total_prod = sum(production.values())
    total_shortage = sum(shortages.values())

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)

    print(f"\nProduction: {total_prod:,.0f} units")
    for (prod_date, prod), qty in sorted(production.items()):
        if qty > 0.01:
            print(f"  {prod_date}: {qty:,.0f} units")

    print(f"\nShortage on {start_date}: {total_shortage:,.0f} units")

    print("\nShipments:")
    for (leg, prod, arr_date), qty in sorted(shipments_leg.items()):
        if qty > 0.01:
            origin, dest = leg
            dep_date = arr_date - timedelta(days=1)
            print(f"  {origin} → {dest}: depart {dep_date}, arrive {arr_date}, qty {qty:,.0f}")

    print("\nHub inventory on day 1:")
    hub_inv_day1 = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inv.items()
        if loc == "6125" and cd == start_date
    )
    print(f"  {hub_inv_day1:,.0f} units")

    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    if total_shortage >= 999:  # Expected 1000 shortage
        print("\n✓ CORRECT: Model cannot satisfy day-1 demand without initial inventory")
        print("  This proves the material balance is working correctly.")
        print("  Hub cannot ship without first receiving inventory.")
    elif hub_inv_day1 > 0:
        print(f"\n❌ BUG DETECTED: Hub has {hub_inv_day1:,.0f} units on day 1!")
        print("  This is phantom inventory - there's no way for hub to have inventory")
        print("  on day 1 without receiving it from manufacturing on day 0 or earlier.")

        # Show where it came from
        print("\n  Hub inventory details on day 1:")
        for (loc, prod, pd, cd, state), qty in sorted(cohort_inv.items()):
            if loc == "6125" and cd == start_date and qty > 0.01:
                print(f"    Cohort (prod_date={pd}, state={state}): {qty:,.0f} units")
    else:
        print("\n⚠ UNEXPECTED: No shortage but no hub inventory either")
        print("  Need to investigate further")


if __name__ == "__main__":
    main()
