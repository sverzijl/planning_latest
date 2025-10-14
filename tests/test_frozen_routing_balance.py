"""Test material balance for frozen and thawed routing scenarios.

This test focuses on the complex frozen/thawed routes:
1. 6122 → Lineage (frozen storage)
2. Lineage → 6130 (frozen transit, thaws on arrival)

These routes are the most complex because:
- Product changes state during transit
- Lineage is frozen STORAGE (intermediate)
- 6130 is ambient BREADROOM (thaws on arrival)
- arrival_state differs from departure state
"""

import pytest
from datetime import date, timedelta

from src.models.forecast import Forecast, ForecastEntry
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import IntegratedProductionDistributionModel


def test_frozen_storage_to_thawing_destination():
    """
    Test the complex Lineage → 6130 route where product thaws on arrival.

    Route: 6122 → Lineage (frozen, 1 day) → 6130 (thaws on arrival, 3 days)

    This tests if frozen inventory balance at Lineage properly subtracts
    departures to 6130, even though 6130 arrival_state is 'ambient' (thawed).

    CRITICAL: Departure should be subtracted from Lineage frozen inventory
    regardless of arrival state at 6130.
    """

    start_date = date(2025, 10, 13)  # Monday
    end_date = start_date + timedelta(days=13)  # 14 days (need longer for 4-day total transit)

    print("\n" + "="*80)
    print("FROZEN STORAGE → THAWING DESTINATION TEST")
    print("="*80)
    print(f"Planning horizon: {start_date} to {end_date} (14 days)")
    print(f"Route: 6122 → Lineage (frozen) → 6130 (thaws on arrival)")
    print(f"Total transit: 4 days (1+3)")

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
        storage_mode=StorageMode.BOTH,  # Supports BOTH to enable freezing upon arrival
        capacity=50000,
    )

    thawing_destination = Location(
        id="6130",
        name="QBA-Canning Vale (WA Thawing)",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,  # Stores ambient/thawed, not frozen!
        capacity=15000,
    )

    locations = [manufacturing, frozen_storage, thawing_destination]

    # Routes
    # Route 1: 6122 → Lineage (AMBIENT transport, freezes upon arrival at Lineage)
    route1 = Route(
        id="R1_6122_Lineage",
        origin_id="6122",
        destination_id="Lineage",
        transport_mode=StorageMode.AMBIENT,  # Ships ambient, freezes at Lineage!
        transit_time_days=1.0,
        cost=0.05,
    )

    # Route 2: Lineage → 6130 (frozen transit, thaws on arrival, 3 days)
    route2 = Route(
        id="R2_Lineage_6130",
        origin_id="Lineage",
        destination_id="6130",
        transport_mode=StorageMode.FROZEN,  # Ships frozen
        transit_time_days=3.0,
        cost=0.10,
    )

    routes = [route1, route2]

    # Forecast: 500 units/day at 6130 for days 5-14 (allows 4-day transit)
    product_id = "TEST_FROZEN_PRODUCT"
    forecast_entries = []

    for day_offset in range(5, 14):  # Days 5-14 (first 4 days impossible due to transit)
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
    total_demand = sum(e.quantity for e in forecast_entries)

    print(f"Forecast: {len(forecast_entries)} entries, {total_demand:,.0f} total demand at 6130")
    print(f"Demand dates: day 5-14 (allows 4-day transit from manufacturing)")

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

    labor_calendar = LaborCalendar(name="Frozen Test Calendar", days=labor_days)

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

    # No truck schedules
    truck_schedules = TruckScheduleCollection(schedules=[])

    print("\n" + "="*80)
    print("BUILDING AND SOLVING MODEL")
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
        initial_inventory=None,
    )

    print(f"✓ Model created")
    print(f"  Routes enumerated: {len(model.enumerated_routes)}")
    print(f"  Locations with inventory tracking: {len(model.inventory_locations)}")
    print(f"    - Frozen storage locations: {model.locations_frozen_storage}")
    print(f"    - Ambient storage locations: {model.locations_ambient_storage}")
    print(f"    - Intermediate storage: {model.intermediate_storage}")

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

    actual_consumption = sum(cohort_demand.values())

    # Check inventory at Lineage (frozen storage)
    lineage_inventory_by_day = {}
    for (loc, prod, pd, cd, state), qty in cohort_inventory.items():
        if loc == "Lineage" and qty > 0.01:
            if cd not in lineage_inventory_by_day:
                lineage_inventory_by_day[cd] = {'frozen': 0.0, 'ambient': 0.0, 'thawed': 0.0, 'total': 0.0}
            lineage_inventory_by_day[cd][state] += qty
            lineage_inventory_by_day[cd]['total'] += qty

    print("\n" + "="*80)
    print("LINEAGE FROZEN STORAGE ANALYSIS")
    print("="*80)

    if lineage_inventory_by_day:
        print(f"Lineage inventory by day (first 7 days):")
        for day in sorted(lineage_inventory_by_day.keys())[:7]:
            inv = lineage_inventory_by_day[day]
            print(f"  {day}: Total={inv['total']:>6,.0f} (frozen={inv['frozen']:>6,.0f}, ambient={inv['ambient']:>6,.0f})")
    else:
        print("⚠ No inventory at Lineage across planning horizon")
        print("  This could indicate:")
        print("    1. Products flowing through Lineage without being stored (good)")
        print("    2. Lineage cohorts not being created (bug)")

    # Check inventory on first and last day
    first_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == start_date
    )

    last_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == end_date
    )

    print("\n" + "="*80)
    print("MATERIAL BALANCE CHECK")
    print("="*80)

    supply = first_day_inv + total_production
    usage = actual_consumption + last_day_inv
    balance = supply - usage

    print(f"Supply Side:")
    print(f"  Initial inventory (day 1): {first_day_inv:,.0f} units")
    print(f"  Production: {total_production:,.0f} units")
    print(f"  TOTAL SUPPLY: {supply:,.0f} units")

    print(f"\nUsage Side:")
    print(f"  Demand consumed: {actual_consumption:,.0f} units")
    print(f"  Final inventory (day 14): {last_day_inv:,.0f} units")
    print(f"  TOTAL USAGE: {usage:,.0f} units")

    print(f"\nMaterial Balance:")
    print(f"  Supply - Usage = {balance:+,.0f} units")

    if abs(balance) <= 1:
        print(f"\n✓ MATERIAL BALANCE IS CORRECT!")
        print(f"  The model properly handles frozen storage → thawing destination")
        print(f"  Lineage frozen departures are correctly subtracted even though 6130 thaws on arrival")
    else:
        print(f"\n❌ MATERIAL BALANCE VIOLATION!")
        print(f"  Bug persists in frozen/thawed routing")
        print(f"  Lineage frozen inventory may not be properly constrained")

        # Diagnose the issue
        if first_day_inv > 1:
            print(f"\n  Day 1 phantom inventory: {first_day_inv:,.0f} units")
            print(f"    This suggests inventory appearing without production")

        if total_production == 0:
            print(f"\n  NO PRODUCTION occurred!")
            print(f"    Yet {actual_consumption:,.0f} units were consumed")
            print(f"    This proves phantom inventory is being created")

    # ASSERT: Material balance must close
    assert abs(balance) <= 1, f"Material balance violation: {balance:+,.0f} units"

    print("\nTEST PASSED ✓")


def test_frozen_direct_to_manufacturing():
    """
    Test frozen routing from manufacturing directly to frozen storage.

    Route: 6122 → Lineage (frozen, 1 day)
    Demand: At Lineage itself (simulates using Lineage as buffer for future WA demand)

    This tests if frozen routing works correctly without the thawing complexity.
    """

    start_date = date(2025, 10, 13)
    end_date = start_date + timedelta(days=6)  # 7 days

    print("\n" + "="*80)
    print("FROZEN DIRECT ROUTE TEST")
    print("="*80)
    print(f"Planning horizon: {start_date} to {end_date}")
    print(f"Route: 6122 → Lineage (frozen storage)")

    # Locations
    manufacturing = Location(
        id="6122",
        name="Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
    )

    frozen_storage = Location(
        id="Lineage",
        name="Lineage Frozen Storage",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.BOTH,  # Supports BOTH to enable freezing upon arrival
        capacity=50000,
    )

    locations = [manufacturing, frozen_storage]

    # Route: 6122 → Lineage (frozen, 1 day)
    route = Route(
        id="R1",
        origin_id="6122",
        destination_id="Lineage",
        transport_mode=StorageMode.FROZEN,
        transit_time_days=1.0,
        cost=0.05,
    )

    routes = [route]

    # Forecast: 1000 units/day at Lineage for days 2-7 (day 1 impossible due to 1-day transit)
    product_id = "FROZEN_TEST"
    forecast_entries = []

    for day_offset in range(2, 7):  # Days 2-6
        forecast_date = start_date + timedelta(days=day_offset)
        forecast_entries.append(
            ForecastEntry(
                location_id="Lineage",
                product_id=product_id,
                forecast_date=forecast_date,
                quantity=1000.0,
            )
        )

    forecast = Forecast(name="Frozen Direct Test", entries=forecast_entries)
    total_demand = sum(e.quantity for e in forecast_entries)

    print(f"Forecast: {total_demand:,.0f} units at Lineage (days 2-6)")

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

    labor_calendar = LaborCalendar(name="Frozen Test Calendar", days=labor_days)

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

    print(f"\n✓ Model created ({len(model.enumerated_routes)} routes)")

    # Solve
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        mip_gap=0.01,
        tee=False,
    )

    print(f"✓ Solved in {result.solve_time_seconds:.2f}s")

    # Extract solution
    solution = model.get_solution()

    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())

    cohort_inventory = solution.get('cohort_inventory', {})
    cohort_demand = solution.get('cohort_demand_consumption', {})

    shortages = solution.get('shortages_by_dest_product_date', {})
    total_shortage = sum(shortages.values())

    actual_consumption = sum(cohort_demand.values())

    # First and last day
    first_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == start_date
    )

    last_day_inv = sum(
        qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
        if cd == end_date
    )

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
        print(f"\n✓ MATERIAL BALANCE CORRECT for frozen routing!")
    else:
        print(f"\n❌ Material balance violation in frozen routing")

    assert abs(balance) <= 1, f"Material balance violation: {balance:+,.0f} units"

    print("\nTEST PASSED ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
