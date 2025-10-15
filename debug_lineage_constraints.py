"""Debug Lineage frozen cohort balance constraints."""

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
    print("LINEAGE CONSTRAINT DEBUG")
    print("="*80)

    # Create model
    model_obj = IntegratedProductionDistributionModel(
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

    # Build model (don't solve yet)
    pyomo_model = model_obj.build_model()

    print(f"\nChecking frozen cohort balance constraints for Lineage...")
    print(f"Cohort frozen index has {len(pyomo_model.cohort_frozen_index)} entries")

    # Find Lineage frozen cohort balance constraints
    lineage_frozen_constraints = [
        (loc, prod, pd, cd) for (loc, prod, pd, cd) in pyomo_model.cohort_frozen_index
        if loc == "Lineage"
    ]

    print(f"Found {len(lineage_frozen_constraints)} frozen cohort balance constraints for Lineage")

    if lineage_frozen_constraints:
        # Check constraint on a date with both arrivals and departures
        # Production on Oct 13, arrives at Lineage Oct 14, departs Oct 14, arrives 6130 Oct 17
        test_constraint = ('Lineage', product_id, start_date, start_date + timedelta(days=2))  # Oct 15
        if test_constraint in lineage_frozen_constraints:
            loc, prod, pd, cd = test_constraint
            print(f"\nChecking Lineage constraint on {cd}:")
            print(f"  Location: {loc}, Product: {prod}, Prod_date: {pd}, Curr_date: {cd}")

            # Check if constraint exists
            constraint = pyomo_model.inventory_frozen_cohort_balance_con
            if (loc, prod, pd, cd) in constraint:
                print(f"  Constraint exists: ✓")
                expr = constraint[loc, prod, pd, cd].expr
                print(f"  Constraint expression:")
                print(f"    {expr}")
            else:
                print(f"  Constraint MISSING: ❌")
        else:
            # Use first available
            loc, prod, pd, cd = lineage_frozen_constraints[5]  # Try 6th constraint
            print(f"\nChecking Lineage constraint: {loc}, {prod}, {pd}, {cd}")
            constraint = pyomo_model.inventory_frozen_cohort_balance_con
            if (loc, prod, pd, cd) in constraint:
                print(f"  Constraint exists: ✓")
                expr = constraint[loc, prod, pd, cd].expr
                print(f"  Constraint expression:")
                print(f"    {expr}")
            else:
                print(f"  Constraint MISSING: ❌")

    print(f"\nChecking shipment_leg_cohort variables...")
    leg1 = ("6122", "Lineage")
    leg2 = ("Lineage", "6130")

    leg1_vars = [
        (leg, prod, pd, dd) for (leg, prod, pd, dd) in pyomo_model.cohort_shipment_index
        if leg == leg1
    ]
    leg2_vars = [
        (leg, prod, pd, dd) for (leg, prod, pd, dd) in pyomo_model.cohort_shipment_index
        if leg == leg2
    ]

    print(f"  Leg {leg1}: {len(leg1_vars)} variables")
    print(f"  Leg {leg2}: {len(leg2_vars)} variables")

    if leg1_vars:
        leg, prod, pd, dd = leg1_vars[0]
        print(f"\n  Checking first {leg1} variable: prod_date={pd}, delivery_date={dd}")
        var = pyomo_model.shipment_leg_cohort[leg, prod, pd, dd]
        print(f"    Variable: {var}")
        print(f"    Bounds: [{var.lb}, {var.ub}]")

    print(f"\nChecking ambient cohort balance at 6130...")
    # Check a demand date: Oct 18 (day 5)
    demand_date = start_date + timedelta(days=5)
    ambient_6130_constraints = [
        (loc, prod, pd, cd) for (loc, prod, pd, cd) in pyomo_model.cohort_ambient_index
        if loc == "6130" and cd == demand_date
    ]

    print(f"Found {len(ambient_6130_constraints)} ambient cohort constraints at 6130 on {demand_date}")

    if ambient_6130_constraints:
        loc, prod, pd, cd = ambient_6130_constraints[0]
        print(f"\nChecking 6130 ambient constraint:")
        print(f"  Location: {loc}, Product: {prod}, Prod_date: {pd}, Curr_date: {cd}")

        constraint = pyomo_model.inventory_ambient_cohort_balance_con
        if (loc, prod, pd, cd) in constraint:
            print(f"  Constraint exists: ✓")
            expr = constraint[loc, prod, pd, cd].expr
            print(f"  Constraint expression:")
            print(f"    {expr}")
        else:
            print(f"  Constraint MISSING: ❌")


if __name__ == "__main__":
    main()
