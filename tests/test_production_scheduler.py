"""
Tests for production scheduler.

This module tests production scheduling from forecasts,
including route selection, backward scheduling, and capacity validation.
"""

import pytest
from datetime import date, timedelta

from src.production.scheduler import (
    ProductionScheduler,
    ProductionSchedule,
    ProductionRequirement,
)
from src.models.forecast import Forecast, ForecastEntry
from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.network import NetworkGraphBuilder
from src.shelf_life import ProductState


@pytest.fixture
def manufacturing_site():
    """Create manufacturing site for testing."""
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
            id="6103",
            name="Breadroom VIC",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
        ),
        Location(
            id="6104",
            name="Hub NSW",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
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
        # Direct: Manufacturing -> Hub VIC (2 days)
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6125",
            transit_time_days=2,
            transport_mode=StorageMode.AMBIENT,
            cost=0.50,
        ),
        # Hub VIC -> Breadroom VIC (1 day)
        Route(
            id="R2",
            origin_id="6125",
            destination_id="6103",
            transit_time_days=1,
            transport_mode=StorageMode.AMBIENT,
            cost=0.25,
        ),
        # Direct: Manufacturing -> Hub NSW (2 days)
        Route(
            id="R3",
            origin_id="6122",
            destination_id="6104",
            transit_time_days=2,
            transport_mode=StorageMode.AMBIENT,
            cost=0.60,
        ),
        # Hub NSW -> Breadroom NSW (1 day)
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
    """Create labor calendar for testing."""
    # Create a week of labor days starting from a future date
    start_date = date.today() + timedelta(days=10)
    days = []

    for i in range(7):
        day_date = start_date + timedelta(days=i)
        # Weekdays: 12h fixed
        if i < 5:
            days.append(
                LaborDay(
                    date=day_date,
                    fixed_hours=12.0,
                    regular_rate=25.0,
                    overtime_rate=37.5,
                    is_fixed_day=True,
                )
            )
        # Weekends: non-fixed
        else:
            days.append(
                LaborDay(
                    date=day_date,
                    fixed_hours=0.0,
                    regular_rate=25.0,
                    overtime_rate=37.5,
                    non_fixed_rate=50.0,
                    minimum_hours=4.0,
                    is_fixed_day=False,
                )
            )

    return LaborCalendar(name="Test Calendar", days=days)


@pytest.fixture
def graph_builder(locations, routes):
    """Create network graph builder."""
    return NetworkGraphBuilder(locations, routes)


@pytest.fixture
def scheduler(manufacturing_site, labor_calendar, graph_builder):
    """Create production scheduler."""
    return ProductionScheduler(manufacturing_site, labor_calendar, graph_builder)


class TestProductionRequirement:
    """Tests for ProductionRequirement dataclass."""

    def test_creation(self):
        """Test creating a production requirement."""
        req = ProductionRequirement(
            production_date=date(2025, 1, 15),
            product_id="PROD1",
            total_quantity=1000.0,
        )

        assert req.production_date == date(2025, 1, 15)
        assert req.product_id == "PROD1"
        assert req.total_quantity == 1000.0
        assert len(req.demand_details) == 0


class TestProductionSchedule:
    """Tests for ProductionSchedule dataclass."""

    def test_is_feasible(self, manufacturing_site):
        """Test feasibility checking."""
        schedule = ProductionSchedule(
            manufacturing_site_id=manufacturing_site.location_id,
            schedule_start_date=date(2025, 1, 1),
            schedule_end_date=date(2025, 1, 10),
            production_batches=[],
            daily_totals={},
            daily_labor_hours={},
            infeasibilities=[],
            total_units=0.0,
            total_labor_hours=0.0,
        )

        assert schedule.is_feasible()

        schedule.infeasibilities.append("Some issue")
        assert not schedule.is_feasible()


class TestBasicScheduling:
    """Tests for basic scheduling scenarios."""

    def test_single_demand_entry(self, scheduler):
        """Test scheduling with single demand entry."""
        # Delivery date in future
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test Forecast",
            entries=[
                ForecastEntry(
                    location_id="6103",  # Breadroom VIC
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=1005.0,  # Will round to 1010
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        assert schedule.total_units == 1010.0  # Rounded to case increment
        assert len(schedule.production_batches) == 1
        assert schedule.is_feasible()

        batch = schedule.production_batches[0]
        assert batch.product_id == "PROD1"
        assert batch.quantity == 1010.0

        # Production date should be delivery_date - transit_days (3: 2+1) - safety (1) = delivery_date - 4
        expected_prod_date = delivery_date - timedelta(days=4)
        assert batch.production_date == expected_prod_date

    def test_multiple_demands_same_date(self, scheduler):
        """Test multiple demands for same delivery date."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test Forecast",
            entries=[
                ForecastEntry(
                    location_id="6103",  # VIC
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
                ForecastEntry(
                    location_id="6101",  # NSW
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # Both should aggregate to same production date
        # (since both are 3-day transit + 1 safety = 4 days before)
        assert len(schedule.production_batches) == 1
        assert schedule.production_batches[0].quantity == 1000.0

    def test_different_products(self, scheduler):
        """Test multiple products on same date."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test Forecast",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD2",
                    forecast_date=delivery_date,
                    quantity=300.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # Should create separate batches for different products
        assert len(schedule.production_batches) == 2
        products = {batch.product_id for batch in schedule.production_batches}
        assert products == {"PROD1", "PROD2"}


class TestBackwardScheduling:
    """Tests for backward scheduling logic."""

    def test_production_date_calculation(self, scheduler):
        """Test production date is calculated correctly."""
        # VIC route: 2 + 1 = 3 days transit, +1 safety = 4 days before delivery
        delivery_date = date.today() + timedelta(days=20)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=100.0,
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        batch = schedule.production_batches[0]
        expected_prod_date = delivery_date - timedelta(days=4)
        assert batch.production_date == expected_prod_date

    def test_skip_past_dates(self, scheduler):
        """Test that past production dates are skipped."""
        # Delivery date very soon (would require production in past)
        delivery_date = date.today() + timedelta(days=2)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=100.0,
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # Should have no batches (production date would be in past)
        assert len(schedule.production_batches) == 0


class TestAggregation:
    """Tests for production aggregation."""

    def test_quantity_rounding(self, scheduler):
        """Test quantities are rounded to case increments."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=1005.0,  # Should round to 1010
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        assert schedule.production_batches[0].quantity == 1010.0

    def test_multiple_entries_aggregate(self, scheduler):
        """Test multiple forecast entries aggregate correctly."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=300.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=450.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # 300 + 450 = 750, rounds to 750 (already multiple of 10)
        assert len(schedule.production_batches) == 1
        assert schedule.production_batches[0].quantity == 750.0


class TestCapacityValidation:
    """Tests for capacity validation."""

    def test_feasible_schedule(self, scheduler):
        """Test feasible schedule is validated correctly."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=10000.0,  # Within capacity
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        assert schedule.is_feasible()
        assert len(schedule.infeasibilities) == 0

    def test_infeasible_schedule(self, scheduler):
        """Test infeasible schedule is flagged."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=25000.0,  # Exceeds capacity
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        assert not schedule.is_feasible()
        assert len(schedule.infeasibilities) > 0


class TestBatchCreation:
    """Tests for batch creation."""

    def test_batch_attributes(self, scheduler, manufacturing_site):
        """Test batch has correct attributes."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=1400.0,
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        batch = schedule.production_batches[0]
        assert batch.product_id == "PROD1"
        assert batch.quantity == 1400.0
        assert batch.manufacturing_site_id == manufacturing_site.location_id

        # Labor hours: production (1.0h) + startup (0.5h) + shutdown (0.5h) = 2.0 hours
        # Since this is the only batch of the day, it gets both startup and shutdown
        assert batch.labor_hours_used == 2.0

        # Production cost: 1400 units x $1/unit = $1400
        assert batch.production_cost == 1400.0

        # Sequence information
        assert batch.sequence_number == 1
        assert batch.changeover_from_product is None
        assert batch.changeover_time_hours == 0.0

    def test_labor_hours_calculation(self, scheduler):
        """Test labor hours are calculated correctly."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=7000.0,  # 7000 / 1400 = 5 hours
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        batch = schedule.production_batches[0]
        # Labor hours: production (5.0h) + startup (0.5h) + shutdown (0.5h) = 6.0 hours
        assert batch.labor_hours_used == 6.0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_forecast(self, scheduler):
        """Test scheduling with empty forecast."""
        forecast = Forecast(name="Empty", entries=[])

        schedule = scheduler.schedule_from_forecast(forecast)

        assert len(schedule.production_batches) == 0
        assert schedule.total_units == 0.0
        assert schedule.is_feasible()

    def test_no_feasible_route(self, scheduler):
        """Test handling of location with no route."""
        delivery_date = date.today() + timedelta(days=15)

        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="INVALID_LOC",  # No route to this location
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=1000.0,
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # Should skip entries with no route
        assert len(schedule.production_batches) == 0
