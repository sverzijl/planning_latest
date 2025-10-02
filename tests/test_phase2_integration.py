"""End-to-end integration test for Phase 2.

Tests complete pipeline: forecast → production → shipments → trucks → costs
"""

import pytest
from datetime import date, timedelta, time

from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.product import Product
from src.models.forecast import Forecast, ForecastEntry
from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.truck_schedule import TruckSchedule, DayOfWeek, DepartureType
from src.models.cost_structure import CostStructure
from src.network import NetworkGraphBuilder, RouteFinder
from src.production.scheduler import ProductionScheduler
from src.distribution import ShipmentPlanner, TruckLoader
from src.costs import CostCalculator


@pytest.fixture
def locations():
    """Test locations: manufacturing + 3 destinations."""
    return [
        Location(
            id="6122",
            name="Manufacturing QBA",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH,
        ),
        Location(
            id="6125",
            name="Hub VIC/TAS/SA",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
        ),
        Location(
            id="6104",
            name="Hub NSW/ACT",
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
    """Test routes: direct paths to hubs and 2-hop routes to breadrooms."""
    return [
        # Manufacturing to hubs
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6125",
            transport_mode="ambient",
            transit_time_days=1,
            cost=0.30,
        ),
        Route(
            id="R2",
            origin_id="6122",
            destination_id="6104",
            transport_mode="ambient",
            transit_time_days=1,
            cost=0.35,
        ),
        # Hub to breadrooms
        Route(
            id="R3",
            origin_id="6125",
            destination_id="6103",
            transport_mode="ambient",
            transit_time_days=1,
            cost=0.20,
        ),
        Route(
            id="R4",
            origin_id="6104",
            destination_id="6101",
            transport_mode="ambient",
            transit_time_days=1,
            cost=0.25,
        ),
    ]


@pytest.fixture
def products():
    """Test products."""
    return [
        Product(id="PROD1", name="Product 1", sku="SKU-PROD1"),
        Product(id="PROD2", name="Product 2", sku="SKU-PROD2"),
    ]


@pytest.fixture
def forecast():
    """Test forecast: 3 days, 2 products, 2 destinations."""
    entries = []

    # Start from Thursday Oct 9 so production falls on weekdays (Mon-Wed)
    # Delivery Oct 9 = Production Oct 6 (accounting for 2-day transit + 1-day safety)
    # Thursday Oct 9 - Saturday Oct 11, 2025 (3 days)
    for day_offset in range(3):
        forecast_date = date(2025, 10, 9) + timedelta(days=day_offset)

        # VIC breadroom
        entries.append(ForecastEntry(
            location_id="6103",
            product_id="PROD1",
            forecast_date=forecast_date,
            quantity=2000.0,
        ))
        entries.append(ForecastEntry(
            location_id="6103",
            product_id="PROD2",
            forecast_date=forecast_date,
            quantity=1500.0,
        ))

        # NSW breadroom
        entries.append(ForecastEntry(
            location_id="6101",
            product_id="PROD1",
            forecast_date=forecast_date,
            quantity=1800.0,
        ))
        entries.append(ForecastEntry(
            location_id="6101",
            product_id="PROD2",
            forecast_date=forecast_date,
            quantity=1200.0,
        ))

    return Forecast(name="Test Forecast Week 1", entries=entries)


@pytest.fixture
def labor_calendar():
    """Test labor calendar: cover 2 weeks to ensure all production dates are included."""
    days = []
    # Cover from Oct 1 to Oct 15 to ensure all production dates are covered
    for day_offset in range(15):
        labor_date = date(2025, 10, 1) + timedelta(days=day_offset)
        days.append(LaborDay(
            date=labor_date,
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0,
            non_fixed_rate=100.0,
            minimum_hours=0.0,
            is_fixed_day=True,
        ))

    return LaborCalendar(name="Test Calendar", days=days)


@pytest.fixture
def truck_schedules():
    """Test truck schedules: morning to 6125, afternoon Mon/Wed/Fri to 6104."""
    return [
        # Morning truck daily (Mon-Fri) to 6125
        TruckSchedule(
            id="MORNING-DAILY",
            truck_name="Morning Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            destination_id="6125",
            day_of_week=None,  # Daily
            capacity=14080,
            pallet_capacity=44,
        ),
        # Afternoon Monday to 6104
        TruckSchedule(
            id="AFT-MON",
            truck_name="Afternoon Monday",
            departure_type=DepartureType.AFTERNOON,
            departure_time=time(14, 0),
            destination_id="6104",
            day_of_week=DayOfWeek.MONDAY,
            capacity=14080,
            pallet_capacity=44,
        ),
        # Afternoon Wednesday to 6104
        TruckSchedule(
            id="AFT-WED",
            truck_name="Afternoon Wednesday",
            departure_type=DepartureType.AFTERNOON,
            departure_time=time(14, 0),
            destination_id="6104",
            day_of_week=DayOfWeek.WEDNESDAY,
            capacity=14080,
            pallet_capacity=44,
        ),
        # Afternoon Friday to 6104
        TruckSchedule(
            id="AFT-FRI",
            truck_name="Afternoon Friday",
            departure_type=DepartureType.AFTERNOON,
            departure_time=time(14, 0),
            destination_id="6104",
            day_of_week=DayOfWeek.FRIDAY,
            capacity=14080,
            pallet_capacity=44,
        ),
    ]


@pytest.fixture
def manufacturing_site(labor_calendar):
    """Test manufacturing site."""
    return ManufacturingSite(
        id="6122",
        name="Manufacturing QBA",
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,  # units per hour
        labor_calendar=labor_calendar,
        changeover_time_hours=0.5,
        changeover_cost=200.0,
    )


@pytest.fixture
def cost_structure():
    """Test cost structure."""
    return CostStructure(
        production_cost_per_unit=0.80,
        shortage_penalty_per_unit=1.50,
        waste_cost_multiplier=1.5,
    )


class TestPhase2Integration:
    """End-to-end integration test for Phase 2."""

    def test_full_pipeline(
        self,
        locations,
        routes,
        products,
        forecast,
        labor_calendar,
        truck_schedules,
        manufacturing_site,
        cost_structure,
    ):
        """
        Test complete Phase 2 pipeline.

        Flow:
        1. Build network graph
        2. Find routes to all destinations
        3. Create production schedule from forecast
        4. Create shipments from production schedule
        5. Assign shipments to trucks
        6. Calculate total costs

        Assertions:
        - All shipments assigned to trucks
        - No infeasibilities
        - Cost components calculated correctly
        - Total cost = sum of components
        - Realistic cost proportions
        """

        # Step 1: Build network graph
        graph_builder = NetworkGraphBuilder(locations, routes)
        graph = graph_builder.build_graph()

        assert graph is not None
        assert graph.number_of_nodes() == 5
        assert graph.number_of_edges() == 4

        # Step 2: Find routes from manufacturing to all breadrooms
        route_finder = RouteFinder(graph_builder)

        route_to_6103 = route_finder.find_shortest_path("6122", "6103")
        route_to_6101 = route_finder.find_shortest_path("6122", "6101")

        assert route_to_6103 is not None
        assert route_to_6103.path == ["6122", "6125", "6103"]
        assert route_to_6103.total_transit_days == 2

        assert route_to_6101 is not None
        assert route_to_6101.path == ["6122", "6104", "6101"]
        assert route_to_6101.total_transit_days == 2

        # Step 3: Create production schedule from forecast
        scheduler = ProductionScheduler(
            manufacturing_site=manufacturing_site,
            labor_calendar=labor_calendar,
            graph_builder=graph_builder,
        )

        production_schedule = scheduler.schedule_from_forecast(
            forecast=forecast,
        )

        assert production_schedule is not None
        assert len(production_schedule.production_batches) > 0
        assert len(production_schedule.requirements) > 0

        # Verify total quantity matches forecast
        total_forecast = sum(e.quantity for e in forecast.entries)
        total_scheduled = production_schedule.total_units

        assert total_scheduled >= total_forecast * 0.95  # Allow 5% rounding

        # Step 4: Create shipments from production schedule
        shipment_planner = ShipmentPlanner()
        shipments = shipment_planner.create_shipments(production_schedule)

        assert len(shipments) > 0
        assert all(s.quantity > 0 for s in shipments)
        assert all(s.route is not None for s in shipments)

        # Verify shipment total matches production total
        total_shipments = sum(s.quantity for s in shipments)
        assert total_shipments == production_schedule.total_units

        # Step 5: Assign shipments to trucks
        truck_loader = TruckLoader(truck_schedules)
        truck_plan = truck_loader.assign_shipments_to_trucks(
            shipments=shipments,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 15),
        )

        # Verify all shipments assigned
        assert truck_plan.is_feasible(), f"Truck loading infeasible: {truck_plan.infeasibilities}"
        assert len(truck_plan.unassigned_shipments) == 0
        assert truck_plan.total_trucks_used > 0

        # Verify shipment assignments preserved
        assigned_shipments = [s for load in truck_plan.loads for s in load.shipments]
        assert len(assigned_shipments) == len(shipments)

        total_assigned_units = sum(s.quantity for s in assigned_shipments)
        assert total_assigned_units == total_shipments

        # Step 6: Calculate total costs
        cost_calculator = CostCalculator(cost_structure, labor_calendar)
        total_cost = cost_calculator.calculate_total_cost(
            production_schedule=production_schedule,
            shipments=shipments,
            forecast=forecast,
        )

        # Verify cost components calculated
        assert total_cost.labor.total_cost > 0
        assert total_cost.production.total_cost > 0
        assert total_cost.transport.total_cost > 0
        # Waste may be zero if all demand met
        assert total_cost.waste.total_cost >= 0

        # Verify total cost = sum of components
        expected_total = (
            total_cost.labor.total_cost +
            total_cost.production.total_cost +
            total_cost.transport.total_cost +
            total_cost.waste.total_cost
        )
        assert total_cost.total_cost == pytest.approx(expected_total, rel=1e-9)

        # Verify cost per unit calculated
        assert total_cost.cost_per_unit_delivered > 0

        # Verify realistic cost proportions
        proportions = total_cost.get_cost_proportions()

        # Production should be a significant component
        assert 0.40 <= proportions["production"] <= 0.95

        # Transport should be present
        assert 0.02 <= proportions["transport"] <= 0.40

        # Labor should be present
        assert 0.01 <= proportions["labor"] <= 0.40

        # Waste should be reasonable (may be zero if all demand met)
        assert proportions["waste"] <= 0.30

        # All proportions sum to 1.0
        assert sum(proportions.values()) == pytest.approx(1.0, rel=1e-10)

        # Print summary for manual inspection
        print("\n" + "=" * 60)
        print("PHASE 2 INTEGRATION TEST SUMMARY")
        print("=" * 60)
        print(f"Forecast entries: {len(forecast.entries)}")
        print(f"Total forecast quantity: {total_forecast:,.0f} units")
        print(f"\nProduction:")
        print(f"  Batches: {len(production_schedule.production_batches)}")
        print(f"  Total scheduled: {total_scheduled:,.0f} units")
        print(f"  Total labor hours: {production_schedule.total_labor_hours:.1f}h")
        print(f"\nDistribution:")
        print(f"  Shipments created: {len(shipments)}")
        print(f"  Trucks used: {truck_plan.total_trucks_used}")
        print(f"  Average truck utilization: {truck_plan.average_utilization:.1%}")
        print(f"\nCosts:")
        print(f"  Labor:      ${total_cost.labor.total_cost:>10,.2f} ({proportions['labor']:>5.1%})")
        print(f"  Production: ${total_cost.production.total_cost:>10,.2f} ({proportions['production']:>5.1%})")
        print(f"  Transport:  ${total_cost.transport.total_cost:>10,.2f} ({proportions['transport']:>5.1%})")
        print(f"  Waste:      ${total_cost.waste.total_cost:>10,.2f} ({proportions['waste']:>5.1%})")
        print(f"  ----------  " + "-" * 10)
        print(f"  TOTAL:      ${total_cost.total_cost:>10,.2f}")
        print(f"\n  Cost per unit delivered: ${total_cost.cost_per_unit_delivered:.2f}")
        print("=" * 60)
