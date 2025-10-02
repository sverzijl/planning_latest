"""
Tests for product changeover time management and campaign scheduling.

This module tests:
- ProductChangeoverMatrix operations
- Campaign scheduling and sequencing
- Labor hours calculation with changeovers
- Multi-product day scheduling
"""

import pytest
from datetime import date, timedelta

from src.production.changeover import (
    ProductChangeoverMatrix,
    ProductChangeoverTime,
    create_simple_changeover_matrix,
)
from src.production.scheduler import ProductionScheduler
from src.models.forecast import Forecast, ForecastEntry
from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.network import NetworkGraphBuilder


@pytest.fixture
def manufacturing_site():
    """Create manufacturing site with changeover times."""
    return ManufacturingSite(
        id="6122",
        name="Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
        max_daily_capacity=19600.0,
        production_cost_per_unit=1.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.5,
        default_changeover_hours=1.0,
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
    ]


@pytest.fixture
def routes():
    """Create test routes."""
    return [
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6125",
            transit_time_days=2,
            transport_mode=StorageMode.AMBIENT,
            cost=0.50,
        ),
        Route(
            id="R2",
            origin_id="6125",
            destination_id="6103",
            transit_time_days=1,
            transport_mode=StorageMode.AMBIENT,
            cost=0.25,
        ),
    ]


@pytest.fixture
def labor_calendar():
    """Create labor calendar for testing."""
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


class TestProductChangeoverMatrix:
    """Tests for ProductChangeoverMatrix class."""

    def test_create_empty_matrix(self):
        """Test creating an empty changeover matrix."""
        matrix = ProductChangeoverMatrix(default_changeover_hours=1.0)

        assert matrix.default_changeover_hours == 1.0
        assert len(matrix.matrix) == 0

    def test_add_changeover(self):
        """Test adding a changeover time."""
        matrix = ProductChangeoverMatrix(default_changeover_hours=1.0)
        matrix.add_changeover("PROD_A", "PROD_B", 0.5)

        assert matrix.has_changeover("PROD_A", "PROD_B")
        assert matrix.get_changeover_time("PROD_A", "PROD_B") == 0.5

    def test_add_changeover_negative_hours(self):
        """Test adding negative changeover hours raises error."""
        matrix = ProductChangeoverMatrix()

        with pytest.raises(ValueError):
            matrix.add_changeover("PROD_A", "PROD_B", -1.0)

    def test_same_product_zero_changeover(self):
        """Test same product has zero changeover time."""
        matrix = ProductChangeoverMatrix(default_changeover_hours=1.0)

        assert matrix.get_changeover_time("PROD_A", "PROD_A") == 0.0

    def test_first_product_zero_changeover(self):
        """Test first product of day (None) has zero changeover."""
        matrix = ProductChangeoverMatrix(default_changeover_hours=1.0)

        assert matrix.get_changeover_time(None, "PROD_A") == 0.0

    def test_undefined_pair_uses_default(self):
        """Test undefined product pair uses default time."""
        matrix = ProductChangeoverMatrix(default_changeover_hours=1.5)

        assert matrix.get_changeover_time("PROD_A", "PROD_B") == 1.5

    def test_sequence_dependent_changeover(self):
        """Test that A→B can differ from B→A."""
        matrix = ProductChangeoverMatrix()
        matrix.add_changeover("PROD_A", "PROD_B", 0.5)
        matrix.add_changeover("PROD_B", "PROD_A", 1.5)

        assert matrix.get_changeover_time("PROD_A", "PROD_B") == 0.5
        assert matrix.get_changeover_time("PROD_B", "PROD_A") == 1.5

    def test_get_all_changeovers(self):
        """Test retrieving all defined changeovers."""
        matrix = ProductChangeoverMatrix()
        matrix.add_changeover("PROD_A", "PROD_B", 0.5)
        matrix.add_changeover("PROD_B", "PROD_C", 1.0)

        changeovers = matrix.get_all_changeovers()

        assert len(changeovers) == 2
        assert any(c.from_product_id == "PROD_A" and c.to_product_id == "PROD_B" for c in changeovers)


class TestSimpleChangeoverMatrix:
    """Tests for create_simple_changeover_matrix helper."""

    def test_create_simple_matrix(self):
        """Test creating simple brand-based matrix."""
        products = ["HELGAS WHITE", "HELGAS MIXED", "WONDER WHITE"]
        matrix = create_simple_changeover_matrix(products)

        # Same brand - should be fast
        assert matrix.get_changeover_time("HELGAS WHITE", "HELGAS MIXED") == 0.25

        # Different brand - should be slow
        assert matrix.get_changeover_time("HELGAS WHITE", "WONDER WHITE") == 1.0

    def test_simple_matrix_same_product(self):
        """Test simple matrix handles same product correctly."""
        products = ["HELGAS WHITE", "WONDER WHITE"]
        matrix = create_simple_changeover_matrix(products)

        assert matrix.get_changeover_time("HELGAS WHITE", "HELGAS WHITE") == 0.0

    def test_simple_matrix_custom_times(self):
        """Test simple matrix with custom times."""
        products = ["HELGAS WHITE", "HELGAS MIXED"]
        matrix = create_simple_changeover_matrix(
            products,
            same_brand_hours=0.1,
            different_brand_hours=2.0
        )

        assert matrix.get_changeover_time("HELGAS WHITE", "HELGAS MIXED") == 0.1


class TestCampaignScheduling:
    """Tests for campaign scheduling (product sequencing)."""

    def test_single_product_day(self, manufacturing_site, labor_calendar, graph_builder):
        """Test scheduling with single product."""
        scheduler = ProductionScheduler(
            manufacturing_site, labor_calendar, graph_builder
        )

        delivery_date = date.today() + timedelta(days=15)
        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=1000.0,
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        batch = schedule.production_batches[0]
        assert batch.sequence_number == 1
        assert batch.changeover_from_product is None
        assert batch.changeover_time_hours == 0.0

    def test_multiple_products_sequenced(self, manufacturing_site, labor_calendar, graph_builder):
        """Test multiple products are sequenced on same day."""
        scheduler = ProductionScheduler(
            manufacturing_site, labor_calendar, graph_builder
        )

        delivery_date = date.today() + timedelta(days=15)
        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_C",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_A",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_B",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # Should have 3 batches, sequenced alphabetically (campaigns)
        assert len(schedule.production_batches) == 3

        batches = sorted(schedule.production_batches, key=lambda b: b.sequence_number)
        assert batches[0].product_id == "PROD_A"
        assert batches[1].product_id == "PROD_B"
        assert batches[2].product_id == "PROD_C"

        # Check sequence numbers
        assert batches[0].sequence_number == 1
        assert batches[1].sequence_number == 2
        assert batches[2].sequence_number == 3

    def test_changeover_from_product_set(self, manufacturing_site, labor_calendar, graph_builder):
        """Test changeover_from_product is set correctly."""
        scheduler = ProductionScheduler(
            manufacturing_site, labor_calendar, graph_builder
        )

        delivery_date = date.today() + timedelta(days=15)
        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_A",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_B",
                    forecast_date=delivery_date,
                    quantity=500.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        batches = sorted(schedule.production_batches, key=lambda b: b.sequence_number)

        # First batch: no previous product
        assert batches[0].changeover_from_product is None

        # Second batch: previous was PROD_A
        assert batches[1].changeover_from_product == "PROD_A"


class TestLaborHoursWithChangeovers:
    """Tests for labor hours calculation including changeovers."""

    def test_single_batch_labor_hours(self, manufacturing_site, labor_calendar, graph_builder):
        """Test labor hours for single batch includes startup and shutdown."""
        scheduler = ProductionScheduler(
            manufacturing_site, labor_calendar, graph_builder
        )

        delivery_date = date.today() + timedelta(days=15)
        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD1",
                    forecast_date=delivery_date,
                    quantity=1400.0,  # 1 hour production
                )
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        batch = schedule.production_batches[0]
        # Production (1.0h) + startup (0.5h) + shutdown (0.5h) + changeover (0.0h) = 2.0h
        assert batch.labor_hours_used == 2.0

    def test_multiple_batches_labor_hours(self, manufacturing_site, labor_calendar, graph_builder):
        """Test labor hours distributed across multiple batches."""
        # Create custom changeover matrix
        matrix = ProductChangeoverMatrix(default_changeover_hours=1.0)

        scheduler = ProductionScheduler(
            manufacturing_site, labor_calendar, graph_builder, matrix
        )

        delivery_date = date.today() + timedelta(days=15)
        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_A",
                    forecast_date=delivery_date,
                    quantity=1400.0,  # 1.0h production
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_B",
                    forecast_date=delivery_date,
                    quantity=1400.0,  # 1.0h production
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        batches = sorted(schedule.production_batches, key=lambda b: b.sequence_number)

        # First batch: startup + production
        # 0.5 (startup) + 1.0 (production) + 0.0 (changeover) = 1.5h
        assert batches[0].labor_hours_used == 1.5

        # Second batch: changeover + production + shutdown
        # 1.0 (changeover) + 1.0 (production) + 0.5 (shutdown) = 2.5h
        assert batches[1].labor_hours_used == 2.5

        # Total: 4.0h
        assert sum(b.labor_hours_used for b in batches) == 4.0

    def test_daily_totals_include_overhead(self, manufacturing_site, labor_calendar, graph_builder):
        """Test daily labor hour totals include all overhead."""
        matrix = ProductChangeoverMatrix(default_changeover_hours=1.0)
        scheduler = ProductionScheduler(
            manufacturing_site, labor_calendar, graph_builder, matrix
        )

        delivery_date = date.today() + timedelta(days=15)
        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_A",
                    forecast_date=delivery_date,
                    quantity=1400.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="PROD_B",
                    forecast_date=delivery_date,
                    quantity=1400.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        prod_date = schedule.production_batches[0].production_date
        daily_hours = schedule.daily_labor_hours[prod_date]

        # Startup (0.5) + Prod A (1.0) + Changeover (1.0) + Prod B (1.0) + Shutdown (0.5) = 4.0h
        assert daily_hours == 4.0


class TestBrandBasedSequencing:
    """Tests for brand-based changeover optimization."""

    def test_brand_based_changeover_times(self, manufacturing_site, labor_calendar, graph_builder):
        """Test brand-based changeover matrix."""
        products = ["HELGAS WHITE", "HELGAS MIXED", "WONDER WHITE"]
        matrix = create_simple_changeover_matrix(products)

        scheduler = ProductionScheduler(
            manufacturing_site, labor_calendar, graph_builder, matrix
        )

        delivery_date = date.today() + timedelta(days=15)
        forecast = Forecast(
            name="Test",
            entries=[
                ForecastEntry(
                    location_id="6103",
                    product_id="HELGAS WHITE",
                    forecast_date=delivery_date,
                    quantity=1400.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="HELGAS MIXED",
                    forecast_date=delivery_date,
                    quantity=1400.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="WONDER WHITE",
                    forecast_date=delivery_date,
                    quantity=1400.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # Products should be sequenced alphabetically: HELGAS MIXED, HELGAS WHITE, WONDER WHITE
        batches = sorted(schedule.production_batches, key=lambda b: b.sequence_number)

        # HELGAS MIXED → HELGAS WHITE: same brand (0.25h)
        assert batches[1].changeover_time_hours == 0.25

        # HELGAS WHITE → WONDER WHITE: different brand (1.0h)
        assert batches[2].changeover_time_hours == 1.0

    def test_campaign_scheduling_saves_time(self, manufacturing_site, labor_calendar, graph_builder):
        """Test that campaign scheduling (grouping by product) saves changeover time."""
        products = ["HELGAS WHITE", "WONDER WHITE"]
        matrix = create_simple_changeover_matrix(
            products,
            same_brand_hours=0.25,
            different_brand_hours=1.0
        )

        scheduler = ProductionScheduler(
            manufacturing_site, labor_calendar, graph_builder, matrix
        )

        delivery_date = date.today() + timedelta(days=15)

        # Produce each product twice (simulates campaign opportunity)
        forecast = Forecast(
            name="Test",
            entries=[
                # First batch of each
                ForecastEntry(
                    location_id="6103",
                    product_id="HELGAS WHITE",
                    forecast_date=delivery_date,
                    quantity=700.0,
                ),
                ForecastEntry(
                    location_id="6103",
                    product_id="WONDER WHITE",
                    forecast_date=delivery_date,
                    quantity=700.0,
                ),
            ],
        )

        schedule = scheduler.schedule_from_forecast(forecast)

        # Alphabetical sequencing groups same products together
        batches = sorted(schedule.production_batches, key=lambda b: b.sequence_number)

        # Only one changeover (HELGAS → WONDER), not alternating
        total_changeover = sum(b.changeover_time_hours for b in batches)

        # Should be 1.0h (one changeover between brands)
        assert total_changeover == 1.0

        # If we had alternated, would have been 2.0h (two changeovers)
