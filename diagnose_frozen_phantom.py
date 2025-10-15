#!/usr/bin/env python3
"""Diagnose phantom inventory in frozen routing scenario."""

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
    start_date = date(2025, 10, 13)  # Monday
    end_date = start_date + timedelta(days=13)  # 14 days

    print("="*80)
    print("FROZEN ROUTING PHANTOM INVENTORY DIAGNOSTIC")
    print("="*80)
    print(f"Planning horizon: {start_date} to {end_date}")
    print(f"Route: 6122 → Lineage (frozen) → 6130 (thaws on arrival)")

    # Locations
    manufacturing = Location(
        id="6122",
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
    )

    frozen_storage = Location(
        id="Lineage",
        name="Lineage Frozen Storage",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.FROZEN,
        capacity=50000,
    )

    thawing_destination = Location(
        id="6130",
        name="QBA-Canning Vale (WA Thawing)",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
        capacity=15000,
    )

    locations = [manufacturing, frozen_storage, thawing_destination]

    # Routes
    route1 = Route(
        id="R1_6122_Lineage",
        origin_id="6122",
        destination_id="Lineage",
        transport_mode=StorageMode.FROZEN,
        transit_time_days=1.0,
        cost=0.05,
    )

    route2 = Route(
        id="R2_Lineage_6130",
        origin_id="Lineage",
        destination_id="6130",
        transport_mode=StorageMode.FROZEN,
        transit_time_days=3.0,
        cost=0.10,
    )

    routes = [route1, route2]

    # Forecast: 500 units/day at 6130 for days 5-14
    product_id = "TEST_FROZEN_PRODUCT"
    forecast_entries = []

    for day_offset in range(5, 14):
        forecast_date = start_date + timedelta(days=day_offset)
        forecast_entries.append(
            ForecastEntry(
                location_id="6130",
                product_id=product_id,
                forecast_date=forecast_date,
                quantity=500.0,
            )
        )

    forecast = Forecast(name="Frozen Route Test", entries=forecast_entries)

    # Labor calendar
    labor_days = []
    for day_offset in range(14):
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

    truck_schedules = TruckScheduleCollection(schedules=[])

    # Create model
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

    print(f"\n✓ Model created")
    print(f"  Enumerated routes: {len(model.enumerated_routes)}")
    print(f"  Destinations: {model.destinations}")
    print(f"  Is 6130 in destinations? {('6130' in model.destinations)}")

    # Check leg states
    print(f"\n  Leg states:")
    for leg_key in sorted(model.leg_keys):
        origin, dest = leg_key
        departure_state = model.leg_departure_state.get(leg_key, 'UNKNOWN')
        arrival_state = model.leg_arrival_state.get(leg_key, 'UNKNOWN')
        print(f"    {origin} → {dest}: departs={departure_state}, arrives={arrival_state}")

    # Check legs TO 6130
    legs_to_6130 = model.legs_to_location.get('6130', [])
    print(f"\n  Legs TO 6130: {legs_to_6130}")

    # Check if Lineage → 6130 leg exists
    if ('Lineage', '6130') in model.leg_keys:
        print(f"    ✓ Lineage → 6130 leg EXISTS in leg_keys")
    else:
        print(f"    ❌ Lineage → 6130 leg MISSING from leg_keys!")

    # Solve first to build model
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        mip_gap=0.01,
        tee=False,
    )

    print(f"\n✓ Solved in {result.solve_time_seconds:.2f}s ({result.termination_condition})")

    # Check cohort indices for 6130 after solve
    print(f"\n  Checking 6130 cohort indices (after solve):")
    pyomo_model = model.model  # Access the Pyomo model
    ambient_6130 = [(prod, pd, cd) for (loc, prod, pd, cd) in pyomo_model.cohort_ambient_index
                    if loc == '6130']
    demand_6130 = [(prod, pd, cd) for (loc, prod, pd, cd) in pyomo_model.cohort_demand_index
                   if loc == '6130']

    print(f"    Ambient cohorts at 6130: {len(ambient_6130)}")
    if ambient_6130:
        print(f"      Sample (first 3): {ambient_6130[:3]}")
    print(f"    Demand cohorts at 6130: {len(demand_6130)}")
    if demand_6130:
        print(f"      Sample (first 3): {demand_6130[:3]}")

    if len(demand_6130) > len(ambient_6130):
        print(f"    ⚠ WARNING: More demand cohorts ({len(demand_6130)}) than ambient cohorts ({len(ambient_6130)})!")
        print(f"      This allows phantom inventory: demand without corresponding balance constraint")
    elif len(demand_6130) == 0:
        print(f"    ⚠ WARNING: NO demand cohorts created for 6130!")
        print(f"      Demand cannot be satisfied (infeasible)")

    # Check if balance constraints exist for demand cohorts
    print(f"\n  Checking balance constraints for demand cohorts:")
    missing_balance_constraints = []
    ambient_6130_set = set(ambient_6130)
    for (prod, pd, cd) in demand_6130:
        ambient_tuple = (prod, pd, cd)
        if ambient_tuple not in ambient_6130_set:
            missing_balance_constraints.append((prod, pd, cd))

    if missing_balance_constraints:
        print(f"    ❌ {len(missing_balance_constraints)} demand cohorts have NO ambient balance constraint!")
        print(f"       This is the smoking gun - demand without inventory enforcement!")
        for cohort in missing_balance_constraints[:5]:
            print(f"         Missing: {cohort}")
    else:
        print(f"    ✓ All demand cohorts have corresponding ambient balance constraints")

    # Check demand_from_cohort values
    print(f"\n  Checking demand_from_cohort variable values:")
    demand_values = []
    for (loc, prod, pd, cd) in pyomo_model.cohort_demand_index:
        if loc == '6130':
            val = pyomo_model.demand_from_cohort[loc, prod, pd, cd].value
            if val and val > 0.01:
                demand_values.append((pd, cd, val))

    if demand_values:
        print(f"    {len(demand_values)} non-zero demand_from_cohort values:")
        for (pd, cd, val) in demand_values[:5]:
            print(f"      prod_date={pd}, demand_date={cd}, qty={val:,.0f}")

    # Check inventory_ambient_cohort values for consumed cohorts
    print(f"\n  Checking inventory_ambient_cohort values for consumed cohorts:")
    for (pd, cd, demand_val) in demand_values[:3]:
        loc = '6130'
        prod = 'TEST_FROZEN_PRODUCT'
        inv_val = pyomo_model.inventory_ambient_cohort[loc, prod, pd, cd].value
        print(f"    Cohort (prod={pd}, curr={cd}): inventory={inv_val:,.2f}, demand={demand_val:,.0f}")
        # Check previous day
        prev_date = cd - timedelta(days=1)
        if (loc, prod, pd, prev_date) in pyomo_model.cohort_ambient_index:
            prev_inv = pyomo_model.inventory_ambient_cohort[loc, prod, pd, prev_date].value
            print(f"      Previous day ({prev_date}): inventory={prev_inv:,.2f}")
        else:
            print(f"      Previous day ({prev_date}): NO COHORT (must be first day)")

        # Check shipment arrivals for this cohort
        leg = ('Lineage', '6130')
        shipment_key = (leg, prod, pd, cd)
        if shipment_key in pyomo_model.cohort_shipment_index:
            shipment_val = pyomo_model.shipment_leg_cohort[shipment_key].value
            print(f"      Shipment arrival from Lineage: {shipment_val:,.2f} units")

            # Check if Lineage has frozen inventory for this cohort
            # Shipment departs on delivery_date - transit_days
            transit_days = 3  # Lineage → 6130 is 3 days
            departure_date = cd - timedelta(days=transit_days)
            lineage_frozen_key = ('Lineage', prod, pd, departure_date)
            if lineage_frozen_key in pyomo_model.cohort_frozen_index:
                lineage_inv = pyomo_model.inventory_frozen_cohort[lineage_frozen_key].value
                print(f"        Lineage frozen inventory on {departure_date}: {lineage_inv:,.2f} units")

                # Check if Lineage frozen balance includes this departure
                # The departure should be in cohort_shipment_index as (leg, prod, pd, delivery_date)
                departure_shipment_key = (leg, prod, pd, cd)  # delivery_date = cd
                if departure_shipment_key in pyomo_model.cohort_shipment_index:
                    print(f"          ✓ Shipment cohort EXISTS in frozen balance calculation")

                    # Check arrivals from 6122/6122_Storage to Lineage on this departure date
                    arrival_legs = [('6122', 'Lineage'), ('6122_Storage', 'Lineage')]
                    for arrival_leg in arrival_legs:
                        # Arrivals on departure_date (when shipment leaves Lineage)
                        arrival_key = (arrival_leg, prod, pd, departure_date)
                        if arrival_key in pyomo_model.cohort_shipment_index:
                            arrival_val = pyomo_model.shipment_leg_cohort[arrival_key].value
                            if arrival_val > 0.01:
                                print(f"          Arrival from {arrival_leg[0]} to Lineage: {arrival_val:,.0f} units")
                                print(f"            ⚠ Lineage receiving AND sending on same day!")
                                print(f"            This creates phantom inventory (no buffering)")
                else:
                    print(f"          ❌ Shipment cohort MISSING from frozen balance!")
                    print(f"             This means frozen departures = 0 (bug!)")
            else:
                print(f"        NO Lineage frozen cohort for prod_date={pd}, dept_date={departure_date}")
        else:
            print(f"      NO shipment cohort index for {shipment_key}")
            print(f"        Leg ('Lineage', '6130') arrival_state: {model.leg_arrival_state.get(leg)}")

    # Extract solution
    solution = model.get_solution()

    production_by_date_product = solution.get('production_by_date_product', {})
    shipments = solution.get('shipments_by_leg', {})
    cohort_inventory = solution.get('cohort_inventory', {})
    cohort_demand = solution.get('cohort_demand_consumption', {})
    cohort_shipments = solution.get('cohort_shipments', {})

    total_production = sum(production_by_date_product.values())
    actual_consumption = sum(cohort_demand.values())

    print(f"\n" + "="*80)
    print("PRODUCTION ANALYSIS")
    print("="*80)
    print(f"Total production: {total_production:,.0f} units")

    if total_production > 0:
        print(f"\nProduction by date:")
        for (dt, prod), qty in sorted(production_by_date_product.items()):
            if qty > 0.01:
                print(f"  {dt}: {qty:>6,.0f} units")
    else:
        print(f"\n⚠ NO PRODUCTION occurred!")

    print(f"\n" + "="*80)
    print("SHIPMENT ANALYSIS")
    print("="*80)

    # Aggregate shipments (non-cohort)
    print(f"\nAggregate shipments by leg:")
    for (origin, dest), leg_shipments in sorted(shipments.items()):
        total_leg_qty = sum(leg_shipments.values())
        if total_leg_qty > 0.01:
            print(f"  {origin} → {dest}: {total_leg_qty:,.0f} units total")
            for dt, qty in sorted(leg_shipments.items()):
                if qty > 0.01:
                    print(f"    {dt}: {qty:>6,.0f} units")

    # Cohort shipments
    print(f"\nCohort shipments:")
    for (origin, dest, prod, prod_date, delivery_date), qty in sorted(cohort_shipments.items()):
        if qty > 0.01:
            print(f"  {origin} → {dest}: prod_date={prod_date}, delivery={delivery_date}, qty={qty:,.0f}")

    print(f"\n" + "="*80)
    print("INVENTORY ANALYSIS")
    print("="*80)

    # Inventory at each location
    for loc_id in ['6122_Storage', 'Lineage', '6130']:
        loc_inventory = [(cd, state, qty) for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
                         if loc == loc_id and qty > 0.01]

        if loc_inventory:
            print(f"\n{loc_id} inventory:")
            for cd, state, qty in sorted(loc_inventory)[:10]:  # First 10 entries
                print(f"  {cd} ({state}): {qty:>6,.0f} units")
        else:
            print(f"\n{loc_id}: No inventory")

    print(f"\n" + "="*80)
    print("DEMAND CONSUMPTION ANALYSIS")
    print("="*80)
    print(f"Total consumption: {actual_consumption:,.0f} units")

    if cohort_demand:
        print(f"\nConsumption by cohort:")
        for (loc, prod, prod_date, demand_date), qty in sorted(cohort_demand.items()):
            if qty > 0.01:
                print(f"  {demand_date} at {loc}: {qty:,.0f} units (prod_date={prod_date})")

    print(f"\n" + "="*80)
    print("MATERIAL BALANCE")
    print("="*80)

    first_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == start_date
    )

    last_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == end_date
    )

    supply = first_day_inv + total_production
    usage = actual_consumption + last_day_inv
    balance = supply - usage

    print(f"Supply: {first_day_inv:,.0f} (initial) + {total_production:,.0f} (production) = {supply:,.0f}")
    print(f"Usage: {actual_consumption:,.0f} (consumed) + {last_day_inv:,.0f} (final) = {usage:,.0f}")
    print(f"Balance: {balance:+,.0f} units")

    if abs(balance) > 1:
        print(f"\n❌ MATERIAL BALANCE VIOLATION!")
        print(f"  Phantom inventory created: {-balance:,.0f} units")
    else:
        print(f"\n✓ Material balance is correct!")


if __name__ == "__main__":
    main()
