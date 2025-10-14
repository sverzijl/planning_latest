"""Minimal test case to isolate material balance bug.

This test uses the simplest possible scenario:
- Single product (HELGAS GFREE WHOLEM 500G)
- Single destination (6110 - direct route from 6122)
- 7-day planning horizon
- No initial inventory
- No intermediate stops
- Simple ambient routing (no frozen/thawed complexity)

If material balance fails here, the bug is fundamental to the model formulation.
If it passes, the bug is related to multi-product, multi-route, or state transition complexity.
"""

import pytest
from datetime import date, timedelta
from typing import Dict, Set
import time

from src.models.forecast import Forecast, ForecastEntry
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.location import StorageMode as TransportMode  # Reuse StorageMode for transport
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.truck_schedule import TruckSchedule, TruckScheduleCollection, DepartureType
from src.optimization import IntegratedProductionDistributionModel


def test_minimal_single_product_single_destination():
    """
    Minimal test: 1 product, 1 destination, 7 days.

    This should have PERFECT material balance:
    Production = Demand Satisfied + Final Inventory (within 1 unit for rounding)
    """

    # Setup dates
    start_date = date(2025, 10, 13)  # Monday
    end_date = start_date + timedelta(days=6)  # 7-day horizon

    print("\n" + "="*80)
    print("MINIMAL MATERIAL BALANCE TEST")
    print("="*80)
    print(f"Planning horizon: {start_date} to {end_date} (7 days)")
    print(f"Scenario: 1 product, 1 destination, direct route, no initial inventory")

    # Create single product
    product_id = "TEST_PRODUCT"

    # Create locations
    manufacturing = Location(
        id="6122",
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
    )

    destination = Location(
        id="6110",
        name="QBA-Burleigh Heads (QLD)",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
        capacity=40000,
    )

    locations = [manufacturing, destination]

    # Create single direct route (6122 → 6110, 1 day transit, ambient)
    route = Route(
        id="R1",
        origin_id="6122",
        destination_id="6110",
        transport_mode=StorageMode.AMBIENT,
        transit_time_days=1.0,
        cost=0.05,
    )

    routes = [route]

    # Create simple demand: 1000 units per day for 7 days at destination 6110
    daily_demand = 1000.0
    forecast_entries = []

    for day_offset in range(7):
        forecast_date = start_date + timedelta(days=day_offset)
        forecast_entries.append(
            ForecastEntry(
                location_id="6110",
                product_id=product_id,
                forecast_date=forecast_date,
                quantity=daily_demand,
                confidence=1.0,
            )
        )

    forecast = Forecast(
        name="Minimal Test Forecast",
        entries=forecast_entries,
    )

    total_demand = sum(e.quantity for e in forecast_entries)
    print(f"\nForecast: {len(forecast_entries)} entries, {total_demand:,.0f} total demand")

    # Create labor calendar (7 days, Mon-Sun)
    labor_days = []
    for day_offset in range(7):
        labor_date = start_date + timedelta(days=day_offset)
        weekday = labor_date.weekday()

        # Mon-Fri: 12h fixed, Sat-Sun: 0h fixed (overtime only)
        if weekday < 5:  # Monday-Friday
            fixed_hours = 12.0
        else:  # Weekend
            fixed_hours = 0.0

        labor_days.append(
            LaborDay(
                date=labor_date,
                fixed_hours=fixed_hours,
                regular_rate=25.0,
                overtime_rate=37.5,
                non_fixed_rate=50.0,
                minimum_hours=4.0 if fixed_hours == 0 else 0.0,
            )
        )

    labor_calendar = LaborCalendar(name="Test Calendar", days=labor_days)

    # Create manufacturing site
    manufacturing_site = ManufacturingSite(
        id="6122",
        name="Manufacturing Site",
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=5.0,
    )

    # Create simple cost structure
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

    # Create simple truck schedule (Tuesday afternoon to 6110)
    truck_schedules = TruckScheduleCollection(
        schedules=[
            TruckSchedule(
                id="TRUCK_TUE_PM_6110",
                truck_name="Tuesday Afternoon to QLD",
                departure_type=DepartureType.AFTERNOON,
                departure_time="14:00",
                destination_id="6110",
                capacity=14080,
                applies_monday=False,
                applies_tuesday=True,
                applies_wednesday=False,
                applies_thursday=False,
                applies_friday=False,
            )
        ]
    )

    print("\n" + "="*80)
    print("MODEL CREATION")
    print("="*80)

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
        initial_inventory=None,  # EXPLICITLY no initial inventory
    )

    print(f"✓ Model created")
    print(f"  Products: {len(model.products)}")
    print(f"  Destinations: {len(model.destinations)}")
    print(f"  Routes enumerated: {len(model.enumerated_routes)}")
    print(f"  Planning days: {len(model.production_dates)}")
    print(f"  Demand entries: {len(model.demand)}")

    # Solve
    print("\n" + "="*80)
    print("SOLVING")
    print("="*80)

    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        mip_gap=0.01,
        tee=False,
    )

    print(f"✓ Solved in {result.solve_time_seconds:.2f}s")
    print(f"  Status: {result.termination_condition}")
    print(f"  Objective: ${result.objective_value:,.2f}")

    # Extract solution
    solution = model.get_solution()
    assert solution is not None

    # Calculate key metrics
    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())

    cohort_inventory = solution.get('cohort_inventory', {})
    cohort_demand = solution.get('cohort_demand_consumption', {})

    shortages = solution.get('shortages_by_dest_product_date', {})
    total_shortage = sum(shortages.values())

    # Calculate inventory on first and last day
    first_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == start_date
    )

    last_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == end_date
    )

    # Calculate actual demand consumption from cohorts
    actual_consumption = sum(cohort_demand.values())

    # Expected demand satisfaction
    expected_satisfied = total_demand - total_shortage

    print("\n" + "="*80)
    print("SOLUTION SUMMARY")
    print("="*80)

    print(f"\nProduction:")
    print(f"  Total produced: {total_production:,.0f} units")
    print(f"  Production days: {len(production_by_date_product)}")

    print(f"\nDemand:")
    print(f"  Total demand: {total_demand:,.0f} units")
    print(f"  Shortage: {total_shortage:,.0f} units")
    print(f"  Satisfied (forecast-shortage): {expected_satisfied:,.0f} units")
    print(f"  Consumed (cohort tracking): {actual_consumption:,.0f} units")

    print(f"\nInventory:")
    print(f"  Day 1 (start): {first_day_inv:,.0f} units")
    print(f"  Day 7 (end): {last_day_inv:,.0f} units")
    print(f"  Net inventory change: {last_day_inv - first_day_inv:+,.0f} units")

    print("\n" + "="*80)
    print("MATERIAL BALANCE CHECK")
    print("="*80)

    # Material balance equation: Initial + Production = Consumption + Final
    supply = first_day_inv + total_production
    usage = actual_consumption + last_day_inv
    balance = supply - usage

    print(f"\nSupply Side:")
    print(f"  Initial inventory: {first_day_inv:,.0f} units")
    print(f"  + Production: {total_production:,.0f} units")
    print(f"  = TOTAL SUPPLY: {supply:,.0f} units")

    print(f"\nUsage Side:")
    print(f"  Demand consumed: {actual_consumption:,.0f} units")
    print(f"  + Final inventory: {last_day_inv:,.0f} units")
    print(f"  = TOTAL USAGE: {usage:,.0f} units")

    print(f"\nMaterial Balance:")
    print(f"  Supply - Usage = {balance:+,.0f} units")

    # ASSERT: Material balance should close (within 1 unit for rounding)
    if abs(balance) <= 1:
        print(f"\n✓ MATERIAL BALANCE IS CORRECT!")
        print(f"  The model has perfect flow conservation in this simple scenario.")
        print(f"  Bug must be related to multi-product, multi-route, or state complexity.")
    else:
        print(f"\n❌ MATERIAL BALANCE VIOLATION!")
        print(f"  Even in this minimal scenario, flow conservation is violated.")
        print(f"  This indicates a fundamental bug in the model formulation.")

        # Detailed breakdown to find the source
        print(f"\n  Investigating source of phantom inventory...")

        # Check if day 1 inventory should be zero
        if first_day_inv > 1:
            print(f"  ⚠ Day 1 has {first_day_inv:,.0f} units but no initial_inventory provided!")
            print(f"    This is phantom inventory appearing on day 1.")

            # Show where it's located
            print(f"\n  Day 1 inventory by location:")
            day1_by_loc = {}
            for (loc, prod, pd, cd, state), qty in cohort_inventory.items():
                if cd == start_date and qty > 0.01:
                    day1_by_loc[loc] = day1_by_loc.get(loc, 0.0) + qty

            for loc, qty in sorted(day1_by_loc.items(), key=lambda x: x[1], reverse=True):
                print(f"    {loc}: {qty:,.0f} units")

        # Check if consumption matches expected
        if abs(actual_consumption - expected_satisfied) > 1:
            print(f"  ⚠ Consumption mismatch:")
            print(f"    Expected (demand - shortage): {expected_satisfied:,.0f}")
            print(f"    Actual (cohort consumption): {actual_consumption:,.0f}")
            print(f"    Difference: {actual_consumption - expected_satisfied:+,.0f}")

    # Final assertion
    assert abs(balance) <= 1, \
        f"Material balance violation: {balance:+,.0f} units (supply: {supply:,.0f}, usage: {usage:,.0f})"

    print("\n" + "="*80)
    print("TEST PASSED ✓")
    print("="*80)


def test_minimal_single_product_with_hub():
    """
    Test with hub routing: 6122 → 6125 → 6123

    This adds one level of complexity (hub-and-spoke) to check if
    multi-leg routing causes the material balance issue.
    """

    start_date = date(2025, 10, 13)
    end_date = start_date + timedelta(days=6)

    print("\n" + "="*80)
    print("MINIMAL TEST WITH HUB ROUTING")
    print("="*80)
    print(f"Planning horizon: {start_date} to {end_date}")
    print(f"Route: 6122 → 6125 (hub) → 6123 (final destination)")

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

    print(f"Forecast: {total_demand:,.0f} units at destination 6123")

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

    # Truck schedules (none for this test - rely on route enumeration)
    truck_schedules = TruckScheduleCollection(schedules=[])

    # Create model
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
        start_date=start_date,
        end_date=end_date,
        allow_shortages=True,
        enforce_shelf_life=True,
        use_batch_tracking=True,
        initial_inventory=None,
    )

    print(f"✓ Model created ({len(model.enumerated_routes)} routes enumerated)")

    # Solve
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        mip_gap=0.01,
        tee=False,
    )

    print(f"✓ Solved in {result.solve_time_seconds:.2f}s ({result.termination_condition})")

    # Extract solution
    solution = model.get_solution()

    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())

    cohort_inventory = solution.get('cohort_inventory', {})
    cohort_demand = solution.get('cohort_demand_consumption', {})

    shortages = solution.get('shortages_by_dest_product_date', {})
    total_shortage = sum(shortages.values())

    # First and last day inventory
    first_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == start_date
    )

    last_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == end_date
    )

    actual_consumption = sum(cohort_demand.values())

    print("\n" + "="*80)
    print("MATERIAL BALANCE")
    print("="*80)

    supply = first_day_inv + total_production
    usage = actual_consumption + last_day_inv
    balance = supply - usage

    print(f"Supply: {first_day_inv:,.0f} (initial) + {total_production:,.0f} (production) = {supply:,.0f}")
    print(f"Usage: {actual_consumption:,.0f} (consumed) + {last_day_inv:,.0f} (final) = {usage:,.0f}")
    print(f"Balance: {balance:+,.0f} units")

    if abs(balance) <= 1:
        print(f"\n✓ Material balance OK with hub routing!")
    else:
        print(f"\n❌ Material balance violation persists with hub routing")
        print(f"  This confirms the bug exists in multi-leg scenarios")

    assert abs(balance) <= 1, f"Material balance violation: {balance:+,.0f} units"

    print("\nTEST PASSED ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
