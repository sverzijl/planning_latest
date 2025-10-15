"""Test to diagnose phantom inventory on day 1."""

import pytest
from datetime import date, timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection


def test_diagnose_phantom_inventory():
    """Diagnose source of phantom inventory on day 1."""

    # Parse data
    data_dir = Path(__file__).parent.parent / "data" / "examples"
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    # Use MultiFileParser (matches UI workflow)
    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=None,  # No initial inventory
    )

    # Parse all data
    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site from locations
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found in locations")

    manuf_loc = manufacturing_locations[0]

    # Create ManufacturingSite from the manufacturing location
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

    # Convert truck schedules list to TruckScheduleCollection
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    # Calculate planning horizon (4 weeks from first forecast date)
    inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)
    planning_start_date = inventory_snapshot_date
    planning_end_date = planning_start_date + timedelta(weeks=4)

    print(f"\nPlanning horizon: {planning_start_date} to {planning_end_date}")
    print(f"No initial inventory provided")

    # Create model
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
        initial_inventory=None,  # No initial inventory
        inventory_snapshot_date=inventory_snapshot_date,
        start_date=planning_start_date,
        end_date=planning_end_date,
        use_batch_tracking=True,
    )

    # Build model to access internal structures
    model.build_model()

    print(f"\n{'='*80}")
    print("COHORT SHIPMENT INDEX ANALYSIS")
    print(f"{'='*80}")

    # Check if any shipments in cohort_shipment_index_set have departure before start_date
    day1 = model.start_date
    pre_horizon_arrivals = []

    for (leg, prod, prod_date, delivery_date) in model.cohort_shipment_index_set:
        transit_days = model.leg_transit_days.get(leg, 0)
        departure_date = delivery_date - timedelta(days=transit_days)

        # Check if this would arrive on day 1 but depart before start
        if delivery_date == day1 and departure_date < model.start_date:
            pre_horizon_arrivals.append({
                'leg': leg,
                'product': prod,
                'prod_date': prod_date,
                'delivery_date': delivery_date,
                'departure_date': departure_date,
                'transit_days': transit_days,
            })

    if pre_horizon_arrivals:
        print(f"\n❌ FOUND {len(pre_horizon_arrivals)} PRE-HORIZON ARRIVALS ON DAY 1:")
        print(f"These would create phantom inventory!\n")
        for arr in pre_horizon_arrivals[:10]:  # Show first 10
            print(f"  Leg: {arr['leg'][0]} → {arr['leg'][1]}")
            print(f"  Product: {arr['product']}")
            print(f"  Production date: {arr['prod_date']}")
            print(f"  Departure: {arr['departure_date']} (BEFORE START: {model.start_date})")
            print(f"  Arrival: {arr['delivery_date']} (DAY 1)")
            print(f"  Transit: {arr['transit_days']} days")
            print()
    else:
        print("\n✓ No pre-horizon arrivals found in cohort_shipment_index_set")

    # Check if no_phantom_cohort_shipments constraint would catch these
    print(f"\n{'='*80}")
    print("CONSTRAINT VERIFICATION")
    print(f"{'='*80}")

    if pre_horizon_arrivals:
        print("\nThe no_phantom_cohort_shipments constraint should force these to 0.")
        print("But they shouldn't even be in the cohort_shipment_index_set!")
        print("\nBUG LOCATION: Cohort index creation logic (lines 1143-1161)")
        print("FIX NEEDED: Filter out shipments where departure_date < start_date")
    else:
        print("\nCohort index creation appears correct.")
        print("Issue must be elsewhere (arrivals, departures, or production logic).")

    # Check cohort_ambient_index_set for day 1 at 6122_Storage
    print(f"\n{'='*80}")
    print("DAY 1 AMBIENT COHORTS AT 6122_Storage")
    print(f"{'='*80}")

    day1_cohorts = []
    for (loc, prod, prod_date, curr_date) in model.cohort_ambient_index_set:
        if loc == '6122_Storage' and curr_date == day1:
            day1_cohorts.append({
                'location': loc,
                'product': prod,
                'prod_date': prod_date,
                'curr_date': curr_date,
            })

    print(f"\nFound {len(day1_cohorts)} ambient cohorts at 6122_Storage on day 1")
    if day1_cohorts:
        print("\nFirst 5 cohorts:")
        for cohort in day1_cohorts[:5]:
            print(f"  Product: {cohort['product']}, Prod date: {cohort['prod_date']}")

        # Check if any have prod_date < start_date
        pre_start = [c for c in day1_cohorts if c['prod_date'] < model.start_date]
        if pre_start:
            print(f"\n❌ FOUND {len(pre_start)} COHORTS WITH PROD_DATE BEFORE START!")
            print("This indicates pre-horizon production dates are being included.")
            for cohort in pre_start[:5]:
                print(f"  Product: {cohort['product']}, Prod date: {cohort['prod_date']} (before {model.start_date})")
        else:
            print(f"\n✓ All cohorts have prod_date >= {model.start_date}")

    print(f"\n{'='*80}")
    print("SUMMARY (COHORT INDEX ANALYSIS)")
    print(f"{'='*80}")
    print(f"Start date: {model.start_date}")
    print(f"Pre-horizon shipment arrivals on day 1: {len(pre_horizon_arrivals)}")
    print(f"Day 1 cohorts at 6122_Storage: {len(day1_cohorts)}")

    # The cohort indices look correct, so solve the model to see the actual phantom inventory
    print(f"\n{'='*80}")
    print("SOLVING MODEL TO CHECK ACTUAL INVENTORY")
    print(f"{'='*80}")

    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    print(f"✓ Solved: {result.termination_condition}")

    # Get solution
    solution = model.get_solution()

    # Check day 1 inventory
    cohort_inv = solution.get('cohort_inventory', {})
    day1_inv = {}
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if curr_date == day1 and qty > 0.01:
            if loc not in day1_inv:
                day1_inv[loc] = []
            day1_inv[loc].append({
                'product': prod,
                'prod_date': prod_date,
                'state': state,
                'quantity': qty,
            })

    print(f"\nDay 1 ({day1}) Inventory:")
    if day1_inv:
        for loc, items in day1_inv.items():
            total_loc = sum(item['quantity'] for item in items)
            print(f"\n  {loc}: {total_loc:,.0f} units")
            for item in items[:3]:  # Show first 3
                print(f"    {item['product'][:30]}: {item['quantity']:.0f} units (prod {item['prod_date']}, {item['state']})")
            if len(items) > 3:
                print(f"    ... and {len(items) - 3} more items")

        total_day1_inv = sum(sum(item['quantity'] for item in items) for items in day1_inv.values())
        print(f"\n  TOTAL DAY 1 INVENTORY: {total_day1_inv:,.0f} units")

        if total_day1_inv > 100:
            print(f"\n  ❌ PHANTOM INVENTORY DETECTED: {total_day1_inv:,.0f} units on day 1!")
            print(f"     No initial inventory was provided, so day 1 should have 0 units")
            print(f"     (except production on day 1)")

            # Check production on day 1
            production_day1 = sum(
                solution.get('production_by_date_product', {}).get((day1, p), 0)
                for p in model.products
            )
            print(f"\n  Production on day 1: {production_day1:,.0f} units")

            # Check if inventory exceeds production
            excess = total_day1_inv - production_day1
            if excess > 100:
                print(f"  Excess inventory (not from day 1 production): {excess:,.0f} units")
                print(f"  \n  THIS IS THE PHANTOM INVENTORY BUG!")
            else:
                print(f"  Day 1 inventory ({total_day1_inv:,.0f}) is less than day 1 production ({production_day1:,.0f})")
                print(f"  This is CORRECT - inventory is leftover after consumption/shipments")
    else:
        print("  No inventory on day 1")

    # Check overall material balance
    print(f"\n{'='*80}")
    print("MATERIAL BALANCE CHECK")
    print(f"{'='*80}")

    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())

    cohort_demand_consumption = solution.get('cohort_demand_consumption', {})
    total_consumption = sum(cohort_demand_consumption.values())

    # Final day inventory
    final_day = model.end_date
    final_inv = sum(
        qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items()
        if curr_date == final_day and qty > 0.01
    )

    # In-transit beyond horizon
    shipments = model.get_shipment_plan() or []
    in_transit_beyond = sum(s.quantity for s in shipments if s.delivery_date > final_day)

    print(f"Production (all dates): {total_production:,.0f} units")
    print(f"Consumption (demand satisfied): {total_consumption:,.0f} units")
    print(f"Final day inventory: {final_inv:,.0f} units")
    print(f"In-transit beyond horizon: {in_transit_beyond:,.0f} units")
    print(f"Total outflow: {total_consumption + final_inv + in_transit_beyond:,.0f} units")
    print(f"Balance: {total_production - (total_consumption + final_inv + in_transit_beyond):+,.0f} units")

    balance_error = total_production - (total_consumption + final_inv + in_transit_beyond)
    if abs(balance_error) > 100:
        print(f"\n❌ MATERIAL BALANCE VIOLATION: {balance_error:+,.0f} units")
        print(f"   Production cannot satisfy consumption + final inventory!")
        print(f"   This indicates a flow conservation bug in the constraints.")

        # Try to identify where the phantom consumption is coming from
        print(f"\n{'='*80}")
        print("DETAILED FLOW ANALYSIS FOR FIRST 3 DAYS")
        print(f"{'='*80}")

        for offset in range(3):
            check_date = day1 + timedelta(days=offset)
            if check_date > final_day:
                break

            prod_on_date = sum(
                production_by_date_product.get((check_date, p), 0)
                for p in model.products
            )

            inv_start = 0
            inv_end = 0
            consumption_on_date = 0

            for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
                if curr_date == check_date and qty > 0.01:
                    inv_end += qty
                prev_date = check_date - timedelta(days=1)
                if curr_date == prev_date and qty > 0.01:
                    inv_start += qty

            for (loc, prod, prod_date, curr_date), qty in cohort_demand_consumption.items():
                if curr_date == check_date:
                    consumption_on_date += qty

            # Outflows (shipments departing on this date)
            departures_on_date = sum(
                s.quantity for s in shipments
                if s.departure_date == check_date
            )

            # Inflows (shipments arriving on this date)
            arrivals_on_date = sum(
                s.quantity for s in shipments
                if s.delivery_date == check_date
            )

            print(f"\n{check_date} (Day {offset + 1}):")
            if offset == 0:
                print(f"  Inventory start: {inv_start:,.0f} units (should be 0 - no initial inventory)")
            else:
                print(f"  Inventory start: {inv_start:,.0f} units")
            print(f"  Production: {prod_on_date:,.0f} units")
            print(f"  Arrivals: {arrivals_on_date:,.0f} units")
            print(f"  Consumption: {consumption_on_date:,.0f} units")
            print(f"  Departures: {departures_on_date:,.0f} units")
            print(f"  Inventory end: {inv_end:,.0f} units")

            # Check balance for this day
            expected_inv_end = inv_start + prod_on_date + arrivals_on_date - consumption_on_date - departures_on_date
            day_balance = inv_end - expected_inv_end
            if abs(day_balance) > 10:
                print(f"  ⚠ DAY BALANCE ERROR: {day_balance:+,.0f} units")
    else:
        print(f"\n✓ Material balance is correct (within {abs(balance_error):.0f} units)")

    # The test should fail if we find pre-horizon arrivals
    assert len(pre_horizon_arrivals) == 0, \
        f"Found {len(pre_horizon_arrivals)} shipments that arrive on day 1 but depart before planning horizon!"
