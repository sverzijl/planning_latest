"""
Diagnostic script to understand hub inventory flow in detail.
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
    """Test hub routing with detailed diagnostics."""
    start_date = date(2025, 10, 13)
    end_date = start_date + timedelta(days=6)

    print("\n" + "="*80)
    print("HUB ROUTING DIAGNOSTIC")
    print("="*80)
    print(f"Route: 6122 → 6125 (hub) → 6123 (destination)")
    print(f"Planning horizon: {start_date} to {end_date}")

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

    # Routes: 6122→6125 (1 day) and 6125→6123 (1 day)
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

    # Forecast: 500 units/day at 6123 for 7 days
    product_id = "TEST_PRODUCT"
    daily_demand = 500.0
    forecast_entries = []

    for day_offset in range(7):
        forecast_date = start_date + timedelta(days=day_offset)
        forecast_entries.append(
            ForecastEntry(
                location_id="6123",
                product_id=product_id,
                forecast_date=forecast_date,
                quantity=daily_demand,
            )
        )

    forecast = Forecast(name="Hub Test", entries=forecast_entries)
    total_demand = sum(e.quantity for e in forecast_entries)

    print(f"Total demand: {total_demand:,.0f} units at 6123")

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

    # Create model
    print("\nBuilding model...")
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
        allow_shortages=True,
        enforce_shelf_life=True,
        use_batch_tracking=True,
        initial_inventory=None,
    )

    print(f"✓ Model created")
    print(f"  Enumerated routes: {len(model.enumerated_routes)}")
    if isinstance(model.enumerated_routes, dict):
        for route_id, route_info in model.enumerated_routes.items():
            print(f"    {route_id}: {' → '.join(route_info['path'])}")
    else:
        for route in model.enumerated_routes:
            print(f"    {route}")

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

    print("\n" + "="*80)
    print("DETAILED SOLUTION ANALYSIS")
    print("="*80)

    # Production
    production = solution.get('production_by_date_product', {})
    print("\n1. PRODUCTION:")
    total_prod = 0
    for (prod_date, prod), qty in sorted(production.items()):
        if qty > 0.01:
            print(f"   {prod_date}: {qty:,.0f} units")
            total_prod += qty
    print(f"   TOTAL: {total_prod:,.0f} units")

    # Shipments
    shipments_leg = solution.get('shipments_by_leg_product_date', {})
    print("\n2. SHIPMENTS BY LEG:")
    for (leg, prod, arr_date), qty in sorted(shipments_leg.items()):
        if qty > 0.01:
            origin, dest = leg
            print(f"   {origin} → {dest} arriving {arr_date}: {qty:,.0f} units")

    # Cohort inventory
    cohort_inv = solution.get('cohort_inventory', {})
    print("\n3. INVENTORY BY LOCATION AND DATE:")

    # Organize by location and date
    inv_by_loc_date = {}
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if qty > 0.01:
            key = (loc, curr_date)
            if key not in inv_by_loc_date:
                inv_by_loc_date[key] = 0
            inv_by_loc_date[key] += qty

    # Group by location
    locations_with_inv = set(loc for loc, _ in inv_by_loc_date.keys())
    for loc in sorted(locations_with_inv):
        print(f"\n   Location {loc}:")
        for curr_date in sorted(set(d for l, d in inv_by_loc_date.keys() if l == loc)):
            qty = inv_by_loc_date.get((loc, curr_date), 0)
            print(f"     {curr_date}: {qty:,.0f} units")

    # Hub flow analysis (detailed)
    print("\n4. HUB (6125) DETAILED FLOW ANALYSIS:")
    print("\n   Checking each date for arrivals, departures, and inventory:")

    for day_offset in range(7):
        curr_date = start_date + timedelta(days=day_offset)
        print(f"\n   Date: {curr_date}")

        # Check arrivals at hub
        arrivals = 0
        for (leg, prod, arr_date), qty in shipments_leg.items():
            origin, dest = leg
            if dest == "6125" and arr_date == curr_date and qty > 0.01:
                arrivals += qty
                print(f"     Arrival from {origin}: {qty:,.0f} units")

        # Check departures from hub
        departures = 0
        for (leg, prod, arr_date), qty in shipments_leg.items():
            origin, dest = leg
            if origin == "6125" and qty > 0.01:
                # Calculate departure date from arrival date and transit time
                # For 1-day transit, if arrival is arr_date, departure is arr_date - 1
                dep_date = arr_date - timedelta(days=1)
                if dep_date == curr_date:
                    departures += qty
                    print(f"     Departure to {dest} (arrives {arr_date}): {qty:,.0f} units")

        # Check inventory at hub
        inv = inv_by_loc_date.get(("6125", curr_date), 0)
        print(f"     Inventory at EOD: {inv:,.0f} units")

        # Material balance check for this date
        prev_date = curr_date - timedelta(days=1)
        prev_inv = inv_by_loc_date.get(("6125", prev_date), 0) if day_offset > 0 else 0

        balance = prev_inv + arrivals - departures - inv
        print(f"     Balance: {prev_inv:,.0f} (prev) + {arrivals:,.0f} (arr) - {departures:,.0f} (dep) - {inv:,.0f} (eod) = {balance:+,.0f}")

        if abs(balance) > 0.01:
            print(f"     ⚠ IMBALANCE DETECTED!")

    # Demand consumption
    demand_consumption = solution.get('cohort_demand_consumption', {})
    shortages = solution.get('shortages_by_dest_product_date', {})

    print("\n5. DEMAND SATISFACTION:")
    total_consumed = 0
    total_shortage = 0
    for day_offset in range(7):
        curr_date = start_date + timedelta(days=day_offset)
        consumed = sum(qty for (loc, prod, pd, cd), qty in demand_consumption.items()
                      if loc == "6123" and cd == curr_date)
        shortage = shortages.get(("6123", product_id, curr_date), 0)
        total_consumed += consumed
        total_shortage += shortage
        print(f"   {curr_date}: {consumed:,.0f} consumed, {shortage:,.0f} shortage")

    print(f"\n   TOTAL: {total_consumed:,.0f} consumed, {total_shortage:,.0f} shortage")
    print(f"   Fill rate: {(total_consumed / total_demand * 100):.1f}%")

    # Material balance
    print("\n" + "="*80)
    print("OVERALL MATERIAL BALANCE")
    print("="*80)

    first_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inv.items()
        if cd == start_date
    )

    last_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inv.items()
        if cd == end_date
    )

    supply = first_day_inv + total_prod
    usage = total_consumed + last_day_inv
    balance = supply - usage

    print(f"Supply: {first_day_inv:,.0f} (initial) + {total_prod:,.0f} (production) = {supply:,.0f}")
    print(f"Usage: {total_consumed:,.0f} (consumed) + {last_day_inv:,.0f} (final) = {usage:,.0f}")
    print(f"Balance: {balance:+,.0f} units")

    if abs(balance) <= 1:
        print("\n✓ Material balance is correct!")
    else:
        print(f"\n❌ Material balance violation: {balance:+,.0f} units")


if __name__ == "__main__":
    main()
