"""
Tests for truck loading and shipment planning.

This module tests:
- Shipment creation from production schedules
- Shipment planning and grouping
- Truck loading assignments
- D-1 vs D0 production timing
- Capacity constraints
- Day-specific routing
"""

import pytest
from datetime import date, timedelta, time

from src.models.shipment import Shipment
from src.models.truck_schedule import TruckSchedule, DepartureType, DayOfWeek
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.forecast import Forecast, ForecastEntry
from src.network import NetworkGraphBuilder, RoutePath
from src.shelf_life import RouteLeg
from src.production.scheduler import ProductionScheduler
from src.distribution.shipment_planner import ShipmentPlanner
from src.distribution.truck_loader import TruckLoader, TruckLoad, TruckLoadPlan


def create_simple_route(origin: str, destination: str, transit_days: int = 2, cost: float = 0.50):
    """Helper to create a simple one-hop route for testing."""
    return RoutePath(
        path=[origin, destination],
        total_transit_days=transit_days,
        total_cost=cost,
        transport_modes=["ambient"],
        route_legs=[
            RouteLeg(
                from_location_id=origin,
                to_location_id=destination,
                transit_days=transit_days,
                transport_mode="ambient"
            )
        ],
        intermediate_stops=[]
    )


@pytest.fixture
def manufacturing_site():
    """Create manufacturing site."""
    return ManufacturingSite(
        id="6122",
        name="Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
        max_daily_capacity=19600.0,
        production_cost_per_unit=1.0,
    )


@pytest.fixture
def locations():
    """Create test locations."""
    return [
        Location(
            id="6122",
            name="Manufacturing",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH,
        ),
        Location(
            id="6125",
            name="Hub VIC",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
        ),
        Location(
            id="6104",
            name="Hub NSW",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
        ),
        Location(
            id="6103",
            name="Breadroom VIC",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
        ),
        Location(
            id="6101",
            name="Breadroom NSW",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
        ),
    ]


@pytest.fixture
def routes():
    """Create test routes."""
    return [
        # Manufacturing → Hub VIC
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6125",
            transit_time_days=2,
            transport_mode=StorageMode.AMBIENT,
            cost=0.50,
        ),
        # Hub VIC → Breadroom VIC
        Route(
            id="R2",
            origin_id="6125",
            destination_id="6103",
            transit_time_days=1,
            transport_mode=StorageMode.AMBIENT,
            cost=0.25,
        ),
        # Manufacturing → Hub NSW
        Route(
            id="R3",
            origin_id="6122",
            destination_id="6104",
            transit_time_days=2,
            transport_mode=StorageMode.AMBIENT,
            cost=0.60,
        ),
        # Hub NSW → Breadroom NSW
        Route(
            id="R4",
            origin_id="6104",
            destination_id="6101",
            transit_time_days=1,
            transport_mode=StorageMode.AMBIENT,
            cost=0.30,
        ),
    ]


@pytest.fixture
def labor_calendar():
    """Create labor calendar."""
    start_date = date.today() + timedelta(days=10)
    days = []

    for i in range(7):
        day_date = start_date + timedelta(days=i)
        days.append(
            LaborDay(
                date=day_date,
                fixed_hours=12.0,
                regular_rate=25.0,
                overtime_rate=37.5,
                is_fixed_day=True,
            )
        )

    return LaborCalendar(name="Test Calendar", days=days)


@pytest.fixture
def graph_builder(locations, routes):
    """Create network graph builder."""
    return NetworkGraphBuilder(locations, routes)


@pytest.fixture
def truck_schedules():
    """Create truck schedules."""
    return [
        # Morning truck (daily Mon-Fri) → 6125 (VIC Hub)
        TruckSchedule(
            id="TRUCK_MORNING_VIC",
            truck_name="Morning VIC",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            destination_id="6125",
            capacity=14080.0,
            pallet_capacity=44,
        ),
        # Afternoon Monday → 6104 (NSW Hub)
        TruckSchedule(
            id="TRUCK_AFT_MON_NSW",
            truck_name="Afternoon Monday NSW",
            departure_type=DepartureType.AFTERNOON,
            departure_time=time(14, 0),
            destination_id="6104",
            capacity=14080.0,
            pallet_capacity=44,
            day_of_week=DayOfWeek.MONDAY,
        ),
    ]


class TestShipment:
    """Tests for Shipment model."""

    def test_shipment_creation(self):
        """Test creating a shipment."""
        route_path = create_simple_route("6122", "6125")

        shipment = Shipment(
            id="SHIP1",
            batch_id="BATCH1",
            product_id="PROD1",
            quantity=1000.0,
            origin_id="6122",
            destination_id="6103",
            delivery_date=date(2025, 1, 20),
            route=route_path,
            production_date=date(2025, 1, 15),
        )

        assert shipment.id == "SHIP1"
        assert shipment.quantity == 1000.0
        assert shipment.first_leg_destination == "6125"
        assert shipment.total_transit_days == 2

    def test_shipment_d1_d0_check(self):
        """Test D-1 and D0 production checks."""
        route_path = create_simple_route("6122", "6125")

        shipment = Shipment(
            id="SHIP1",
            batch_id="BATCH1",
            product_id="PROD1",
            quantity=1000.0,
            origin_id="6122",
            destination_id="6103",
            delivery_date=date(2025, 1, 20),
            route=route_path,
            production_date=date(2025, 1, 15),
        )

        # Truck departs Jan 16 - production on Jan 15 is D-1
        assert shipment.is_d1_production(date(2025, 1, 16))
        assert not shipment.is_d0_production(date(2025, 1, 16))

        # Truck departs Jan 15 - production on Jan 15 is D0
        assert not shipment.is_d1_production(date(2025, 1, 15))
        assert shipment.is_d0_production(date(2025, 1, 15))


class TestShipmentPlanner:
    """Tests for ShipmentPlanner."""

    def test_create_shipments_from_schedule(
        self, manufacturing_site, labor_calendar, graph_builder
    ):
        """Test creating shipments from production schedule."""
        scheduler = ProductionScheduler(manufacturing_site, labor_calendar, graph_builder)

        delivery_date = date.today() + timedelta(days=15)
        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=1000.0,
                ),
                ForecastEntry(
                    location_id="6101",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # Create shipments
        planner = ShipmentPlanner()
        shipments = planner.create_shipments(schedule)

        # Should have 2 shipments (one per destination)
        assert len(shipments) == 2

        # Check destinations
        destinations = {s.destination_id for s in shipments}
        assert destinations == {"6103", "6101"}

        # Check quantities
        vic_shipment = next(s for s in shipments if s.destination_id == "6103")
        nsw_shipment = next(s for s in shipments if s.destination_id == "6101")
        assert vic_shipment.quantity == 1000.0
        assert nsw_shipment.quantity == 500.0

    def test_group_shipments_by_destination(self):
        """Test grouping shipments by first leg destination."""
        route_vic = create_simple_route("6122", "6125", transit_days=2, cost=0.50)
        route_nsw = create_simple_route("6122", "6104", transit_days=2, cost=0.60)

        shipments = [
            Shipment(
                id="S1",
                batch_id="B1",
                product_id="P1",
                quantity=1000,
                origin_id="6122",
                destination_id="6103",
                delivery_date=date(2025, 1, 20),
                route=route_vic,
                production_date=date(2025, 1, 15),
            ),
            Shipment(
                id="S2",
                batch_id="B1",
                product_id="P1",
                quantity=500,
                origin_id="6122",
                destination_id="6101",
                delivery_date=date(2025, 1, 20),
                route=route_nsw,
                production_date=date(2025, 1, 15),
            ),
        ]

        planner = ShipmentPlanner()
        grouped = planner.get_shipments_by_destination(shipments)

        assert len(grouped) == 2
        assert "6125" in grouped  # VIC hub
        assert "6104" in grouped  # NSW hub
        assert len(grouped["6125"]) == 1
        assert len(grouped["6104"]) == 1


class TestTruckLoader:
    """Tests for TruckLoader."""

    def test_get_trucks_for_date(self, truck_schedules):
        """Test getting trucks for specific date."""
        loader = TruckLoader(truck_schedules)

        # Monday should have both morning (daily) and afternoon (Monday-specific)
        monday = date(2025, 1, 6)  # A Monday
        trucks = loader.get_trucks_for_date(monday)
        assert len(trucks) == 2

        # Tuesday should have only morning (daily)
        tuesday = date(2025, 1, 7)
        trucks = loader.get_trucks_for_date(tuesday)
        assert len(trucks) == 1
        assert trucks[0].departure_type == DepartureType.MORNING

    def test_assign_single_shipment(self, truck_schedules):
        """Test assigning a single shipment to truck."""
        route = create_simple_route("6122", "6125")

        # Production on Jan 15, truck departs Jan 16 (D-1)
        shipment = Shipment(
            id="S1",
            batch_id="B1",
            product_id="P1",
            quantity=1000,
            origin_id="6122",
            destination_id="6103",
            delivery_date=date(2025, 1, 20),
            route=route,
            production_date=date(2025, 1, 15),
        )

        loader = TruckLoader(truck_schedules)
        plan = loader.assign_shipments_to_trucks(
            [shipment],
            start_date=date(2025, 1, 16),
            end_date=date(2025, 1, 16)
        )

        assert plan.is_feasible()
        assert len(plan.loads) == 1
        assert plan.loads[0].total_units == 1000
        assert shipment.is_assigned()

    def test_morning_truck_d1_only(self, truck_schedules):
        """Test that morning trucks only load D-1 production."""
        route = create_simple_route("6122", "6125")

        # D0 shipment (same day as truck departure)
        shipment_d0 = Shipment(
            id="S_D0",
            batch_id="B1",
            product_id="P1",
            quantity=1000,
            origin_id="6122",
            destination_id="6103",
            delivery_date=date(2025, 1, 20),
            route=route,
            production_date=date(2025, 1, 16),  # Same as truck departure
        )

        loader = TruckLoader(truck_schedules)
        plan = loader.assign_shipments_to_trucks(
            [shipment_d0],
            start_date=date(2025, 1, 16),
            end_date=date(2025, 1, 16)
        )

        # Morning truck won't load D0
        assert not plan.is_feasible()
        assert len(plan.unassigned_shipments) == 1

    def test_afternoon_truck_d1_and_d0(self, truck_schedules):
        """Test that afternoon trucks can load both D-1 and D0."""
        route = create_simple_route("6122", "6104", transit_days=2, cost=0.60)

        monday = date(2025, 1, 6)  # A Monday

        # D-1 shipment (day before truck)
        shipment_d1 = Shipment(
            id="S_D1",
            batch_id="B1",
            product_id="P1",
            quantity=1000,
            origin_id="6122",
            destination_id="6101",
            delivery_date=date(2025, 1, 20),
            route=route,
            production_date=monday - timedelta(days=1),
        )

        # D0 shipment (same day as truck)
        shipment_d0 = Shipment(
            id="S_D0",
            batch_id="B2",
            product_id="P1",
            quantity=500,
            origin_id="6122",
            destination_id="6101",
            delivery_date=date(2025, 1, 20),
            route=route,
            production_date=monday,
        )

        loader = TruckLoader(truck_schedules)
        plan = loader.assign_shipments_to_trucks(
            [shipment_d1, shipment_d0],
            start_date=monday,
            end_date=monday
        )

        # Afternoon truck on Monday should load both
        assert plan.is_feasible()
        assert len(plan.loads) == 1
        assert plan.loads[0].total_units == 1500.0

    def test_capacity_constraint(self, truck_schedules):
        """Test that capacity constraints are respected."""
        route = create_simple_route("6122", "6125")

        # Create shipments exceeding truck capacity (14,080 units)
        shipments = [
            Shipment(
                id=f"S{i}",
                batch_id=f"B{i}",
                product_id="P1",
                quantity=7000,
                origin_id="6122",
                destination_id="6103",
                delivery_date=date(2025, 1, 20),
                route=route,
                production_date=date(2025, 1, 15),
            )
            for i in range(3)  # 3 × 7000 = 21,000 > 14,080
        ]

        loader = TruckLoader(truck_schedules)
        plan = loader.assign_shipments_to_trucks(
            shipments,
            start_date=date(2025, 1, 16),
            end_date=date(2025, 1, 16)
        )

        # Should assign 2 shipments (14,000) and leave 1 unassigned
        assert not plan.is_feasible()
        assert len(plan.unassigned_shipments) == 1
        assert plan.loads[0].total_units == 14000.0

    def test_destination_matching(self, truck_schedules):
        """Test that shipments only go on trucks serving their destination."""
        route_vic = create_simple_route("6122", "6125", transit_days=2, cost=0.50)
        route_nsw = create_simple_route("6122", "6104", transit_days=2, cost=0.60)

        # VIC shipment (first leg to 6125)
        shipment_vic = Shipment(
            id="S_VIC",
            batch_id="B1",
            product_id="P1",
            quantity=1000,
            origin_id="6122",
            destination_id="6103",
            delivery_date=date(2025, 1, 20),
            route=route_vic,
            production_date=date(2025, 1, 5),  # Sunday (D-1 for Monday truck)
        )

        # NSW shipment (first leg to 6104)
        shipment_nsw = Shipment(
            id="S_NSW",
            batch_id="B2",
            product_id="P1",
            quantity=500,
            origin_id="6122",
            destination_id="6101",
            delivery_date=date(2025, 1, 20),
            route=route_nsw,
            production_date=date(2025, 1, 5),  # Sunday (D-1 for Monday truck)
        )

        loader = TruckLoader(truck_schedules)
        monday = date(2025, 1, 6)

        plan = loader.assign_shipments_to_trucks(
            [shipment_vic, shipment_nsw],
            start_date=monday,
            end_date=monday
        )

        # Monday has: morning truck to 6125, afternoon truck to 6104
        # VIC shipment should go on morning truck
        # NSW shipment should go on afternoon truck
        assert len(plan.loads) == 2

        morning_load = next(l for l in plan.loads if l.departure_type == "morning")
        afternoon_load = next(l for l in plan.loads if l.departure_type == "afternoon")

        assert morning_load.destination_id == "6125"
        assert morning_load.total_units == 1000  # VIC

        assert afternoon_load.destination_id == "6104"
        assert afternoon_load.total_units == 500  # NSW

    def test_pallet_utilization(self, truck_schedules):
        """Test pallet utilization calculation."""
        route = create_simple_route("6122", "6125")

        # 320 units = 1 pallet exactly
        shipment = Shipment(
            id="S1",
            batch_id="B1",
            product_id="P1",
            quantity=320,
            origin_id="6122",
            destination_id="6103",
            delivery_date=date(2025, 1, 20),
            route=route,
            production_date=date(2025, 1, 15),
        )

        loader = TruckLoader(truck_schedules)
        plan = loader.assign_shipments_to_trucks(
            [shipment],
            start_date=date(2025, 1, 16),
            end_date=date(2025, 1, 16)
        )

        load = plan.loads[0]
        assert load.total_pallets == 1
        assert load.capacity_utilization == pytest.approx(1 / 44)

    def test_empty_shipments_list(self, truck_schedules):
        """Test handling empty shipments list."""
        loader = TruckLoader(truck_schedules)
        plan = loader.assign_shipments_to_trucks(
            [],
            start_date=date(2025, 1, 16),
            end_date=date(2025, 1, 16)
        )

        assert plan.is_feasible()
        assert len(plan.loads) == 0
        assert plan.total_trucks_used == 0
