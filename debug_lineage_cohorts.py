"""Debug cohort creation for Lineage routing."""

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
    start_date = date(2025, 10, 13)
    end_date = start_date + timedelta(days=13)

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

    # Forecast
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

    print("="*80)
    print("LINEAGE COHORT DEBUG")
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

    # Solve to trigger model building
    print(f"\nManufacturing site ID: {model.manufacturing_site.location_id}")
    print(f"Manufacturing site storage_mode: {model.manufacturing_site.storage_mode}")
    print(f"Inventory locations: {model.inventory_locations}")
    print(f"'6122' in inventory_locations: {'6122' in model.inventory_locations}")
    print(f"Locations with frozen storage: {model.locations_frozen_storage}")
    print(f"'6122' in locations_frozen_storage: {'6122' in model.locations_frozen_storage}")

    print(f"\nChecking _cohort_is_reachable('6122', 'TEST_FROZEN_PRODUCT', start_date, start_date+1):")
    is_reachable = model._cohort_is_reachable('6122', product_id, start_date, start_date + timedelta(days=1))
    print(f"  Result: {is_reachable}")

    print("\nSolving model...")
    result = model.solve(solver_name='cbc', time_limit_seconds=10, mip_gap=0.01, tee=False)
    print(f"Solved: {result.termination_condition}")

    print("\n" + "="*80)
    print("FROZEN COHORT INVENTORY AT LINEAGE")
    print("="*80)

    # Check if frozen cohorts exist at Lineage
    lineage_frozen_cohorts = [
        (loc, prod, pd, cd) for (loc, prod, pd, cd) in model.cohort_frozen_index_set
        if loc == "Lineage"
    ]

    if lineage_frozen_cohorts:
        print(f"Found {len(lineage_frozen_cohorts)} frozen cohorts at Lineage:")
        for (loc, prod, pd, cd) in sorted(lineage_frozen_cohorts)[:10]:
            age = (cd - pd).days
            print(f"  prod_date={pd}, curr_date={cd}, age={age}d")
    else:
        print("NO frozen cohorts at Lineage!")
        print("This means Lineage cannot hold frozen inventory")

    print("\n" + "="*80)
    print("SHIPMENT COHORTS FOR LINEAGE LEGS")
    print("="*80)

    # Check shipment cohorts for 6122 → Lineage
    leg1 = ("6122", "Lineage")
    leg1_cohorts = [
        (leg, prod, pd, dd) for (leg, prod, pd, dd) in model.cohort_shipment_index_set
        if leg == leg1
    ]
    print(f"\nLeg {leg1}: {len(leg1_cohorts)} shipment cohorts")
    if leg1_cohorts:
        for item in sorted(leg1_cohorts)[:5]:
            print(f"  {item}")

    # Check shipment cohorts for Lineage → 6130
    leg2 = ("Lineage", "6130")
    leg2_cohorts = [
        (leg, prod, pd, dd) for (leg, prod, pd, dd) in model.cohort_shipment_index_set
        if leg == leg2
    ]
    print(f"\nLeg {leg2}: {len(leg2_cohorts)} shipment cohorts")
    if leg2_cohorts:
        for item in sorted(leg2_cohorts)[:5]:
            print(f"  {item}")
    else:
        print("  NO shipment cohorts for Lineage → 6130!")
        print("  This is the BUG - frozen departures cannot be constrained without these cohorts")

    print("\n" + "="*80)
    print("DEMAND COHORTS AT 6130")
    print("="*80)

    demand_cohorts_6130 = [
        (loc, prod, pd, dd) for (loc, prod, pd, dd) in model.cohort_demand_index_set
        if loc == "6130"
    ]
    print(f"Found {len(demand_cohorts_6130)} demand cohorts at 6130:")
    if demand_cohorts_6130:
        for item in sorted(demand_cohorts_6130)[:5]:
            print(f"  {item}")

    print("\n" + "="*80)
    print("AMBIENT COHORTS AT 6130")
    print("="*80)

    ambient_cohorts_6130 = [
        (loc, prod, pd, cd) for (loc, prod, pd, cd) in model.cohort_ambient_index_set
        if loc == "6130"
    ]
    print(f"Found {len(ambient_cohorts_6130)} ambient cohorts at 6130:")
    if ambient_cohorts_6130:
        for item in sorted(ambient_cohorts_6130)[:5]:
            print(f"  {item}")

    print("\n" + "="*80)
    print("FROZEN COHORTS AT 6122 (Manufacturing)")
    print("="*80)

    frozen_cohorts_6122 = [
        (loc, prod, pd, cd) for (loc, prod, pd, cd) in model.cohort_frozen_index_set
        if loc == "6122"
    ]
    print(f"Found {len(frozen_cohorts_6122)} frozen cohorts at 6122:")
    if frozen_cohorts_6122:
        for item in sorted(frozen_cohorts_6122)[:5]:
            print(f"  {item}")
    else:
        print("  NO frozen cohorts at manufacturing site!")
        print("  This is the BUG: Frozen shipments from 6122 have no material source!")
        print("  ")
        print("  Why no frozen cohorts at 6122?")
        print(f"    - '6122' in locations_frozen_storage: {'6122' in model.locations_frozen_storage}")
        print(f"    - '6122' is_reachable: {model._cohort_is_reachable('6122', product_id, start_date, start_date)}")
        print("  ")
        print("  Checking _build_cohort_indices logic...")
        print("    Line 1155: if loc in self.locations_frozen_storage and age_days <= FROZEN_SHELF_LIFE:")
        print("    Line 1156:     if self._cohort_is_reachable(loc, prod, prod_date, curr_date):")
        print("  ")
        print("  Both conditions should be True for '6122', so why no cohorts?")


if __name__ == "__main__":
    main()
