"""Debug script to check if Lineage routing is properly enumerated."""

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
        storage_mode=StorageMode.AMBIENT,  # Stores ambient/thawed, not frozen!
        capacity=15000,
    )

    locations = [manufacturing, frozen_storage, thawing_destination]

    # Routes
    # Route 1: 6122 → Lineage (frozen, 1 day)
    route1 = Route(
        id="R1_6122_Lineage",
        origin_id="6122",
        destination_id="Lineage",
        transport_mode=StorageMode.FROZEN,
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

    print("="*80)
    print("DEBUGGING LINEAGE ROUTING")
    print("="*80)
    print(f"\nInput routes:")
    for r in routes:
        mode = r.transport_mode.value if hasattr(r.transport_mode, 'value') else r.transport_mode
        print(f"  {r.origin_id} → {r.destination_id} (mode={mode}, transit={r.transit_time_days}d)")

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
    print(f"\nEnumerated routes ({len(model.enumerated_routes)}):")
    for route_path in model.enumerated_routes:
        legs = route_path['legs']
        origin = route_path['origin']
        destination = route_path['destination']
        total_transit = route_path['total_transit_time']

        leg_str = " → ".join([leg['origin'] for leg in legs] + [legs[-1]['destination']])
        print(f"  {origin} → {destination}: {leg_str} (transit={total_transit}d)")

        for leg in legs:
            print(f"    Leg: {leg['origin']} → {leg['destination']} "
                  f"(mode={leg['transport_mode']}, transit={leg['transit_time_days']}d, "
                  f"arrival_state={leg.get('arrival_state', 'N/A')})")

    print(f"\nLeg keys ({len(model.leg_keys)}):")
    for leg in sorted(model.leg_keys):
        print(f"  {leg}")

    print(f"\nLegs from each location:")
    for loc in sorted(model.legs_from_location.keys()):
        legs = model.legs_from_location[loc]
        print(f"  {loc}: {legs}")

    print(f"\nLegs to each location:")
    for loc in sorted(model.legs_to_location.keys()):
        legs = model.legs_to_location[loc]
        print(f"  {loc}: {legs}")

    print(f"\nLeg states:")
    print(f"  Departure states:")
    for leg in sorted(model.leg_departure_state.keys()):
        state = model.leg_departure_state[leg]
        print(f"    {leg}: {state}")

    print(f"  Arrival states:")
    for leg in sorted(model.leg_arrival_state.keys()):
        state = model.leg_arrival_state[leg]
        print(f"    {leg}: {state}")

    print(f"\nIntermediate storage locations: {model.intermediate_storage}")
    print(f"Frozen storage locations: {model.locations_frozen_storage}")
    print(f"Ambient storage locations: {model.locations_ambient_storage}")

    print(f"\nDemand entries:")
    for (loc, prod, dt), qty in model.demand.items():
        print(f"  {loc}, {prod}, {dt}: {qty}")

    print(f"\nDestinations: {model.destinations}")


if __name__ == "__main__":
    main()
