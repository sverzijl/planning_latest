"""Tests for forecast aggregation utilities."""

import pytest
from datetime import date, timedelta

from src.models.forecast import Forecast, ForecastEntry
from src.models.time_period import (
    TimeBucket,
    BucketGranularity,
    create_daily_buckets,
    create_uniform_buckets,
)
from src.models.forecast_aggregator import (
    aggregate_forecast_to_buckets,
    validate_aggregation,
    disaggregate_to_daily,
)


@pytest.fixture
def simple_daily_forecast():
    """Create a simple 7-day forecast with single destination and product."""
    entries = [
        ForecastEntry(
            location_id="6103",
            product_id="P1",
            forecast_date=date(2025, 6, 1),
            quantity=100
        ),
        ForecastEntry(
            location_id="6103",
            product_id="P1",
            forecast_date=date(2025, 6, 2),
            quantity=150
        ),
        ForecastEntry(
            location_id="6103",
            product_id="P1",
            forecast_date=date(2025, 6, 3),
            quantity=120
        ),
        ForecastEntry(
            location_id="6103",
            product_id="P1",
            forecast_date=date(2025, 6, 4),
            quantity=130
        ),
        ForecastEntry(
            location_id="6103",
            product_id="P1",
            forecast_date=date(2025, 6, 5),
            quantity=140
        ),
        ForecastEntry(
            location_id="6103",
            product_id="P1",
            forecast_date=date(2025, 6, 6),
            quantity=110
        ),
        ForecastEntry(
            location_id="6103",
            product_id="P1",
            forecast_date=date(2025, 6, 7),
            quantity=160
        ),
    ]
    return Forecast(name="Simple Weekly", entries=entries, creation_date=date.today())


@pytest.fixture
def multi_destination_forecast():
    """Create forecast with multiple destinations and products."""
    entries = []
    for day in range(1, 8):
        # Destination 1, Product 1
        entries.append(ForecastEntry(
            location_id="6103",
            product_id="P1",
            forecast_date=date(2025, 6, day),
            quantity=100 + day * 10
        ))
        # Destination 1, Product 2
        entries.append(ForecastEntry(
            location_id="6103",
            product_id="P2",
            forecast_date=date(2025, 6, day),
            quantity=50 + day * 5
        ))
        # Destination 2, Product 1
        entries.append(ForecastEntry(
            location_id="6105",
            product_id="P1",
            forecast_date=date(2025, 6, day),
            quantity=80 + day * 8
        ))

    return Forecast(name="Multi-Dest", entries=entries, creation_date=date.today())


class TestAggregateForecastToBuckets:
    """Tests for aggregate_forecast_to_buckets function."""

    def test_aggregate_daily_to_three_day(self, simple_daily_forecast):
        """Test aggregating daily forecast into 3-day buckets."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.THREE_DAY
        )

        aggregated = aggregate_forecast_to_buckets(simple_daily_forecast, buckets)

        # Should have 3 entries (one per bucket) for single dest/product
        assert len(aggregated.entries) == 3

        # First bucket: Days 1-3 (100 + 150 + 120 = 370)
        assert aggregated.entries[0].quantity == 370
        assert aggregated.entries[0].forecast_date == date(2025, 6, 1)

        # Second bucket: Days 4-6 (130 + 140 + 110 = 380)
        assert aggregated.entries[1].quantity == 380
        assert aggregated.entries[1].forecast_date == date(2025, 6, 4)

        # Third bucket: Day 7 only (160)
        assert aggregated.entries[2].quantity == 160
        assert aggregated.entries[2].forecast_date == date(2025, 6, 7)

    def test_aggregate_daily_to_weekly(self, simple_daily_forecast):
        """Test aggregating daily forecast into weekly bucket."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.WEEKLY
        )

        aggregated = aggregate_forecast_to_buckets(simple_daily_forecast, buckets)

        # Should have 1 entry (single week)
        assert len(aggregated.entries) == 1

        # Total: 100+150+120+130+140+110+160 = 910
        assert aggregated.entries[0].quantity == 910
        assert aggregated.entries[0].location_id == "6103"
        assert aggregated.entries[0].product_id == "P1"

    def test_aggregate_preserves_destinations_and_products(self, multi_destination_forecast):
        """Test that aggregation preserves destination and product granularity."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.WEEKLY
        )

        aggregated = aggregate_forecast_to_buckets(multi_destination_forecast, buckets)

        # Should have 3 entries: 2 dest × 2 products - 1 (6105 doesn't have P2)
        # 6103-P1, 6103-P2, 6105-P1
        assert len(aggregated.entries) == 3

        # Check all combinations are present
        combinations = {
            (e.location_id, e.product_id) for e in aggregated.entries
        }
        assert ("6103", "P1") in combinations
        assert ("6103", "P2") in combinations
        assert ("6105", "P1") in combinations

    def test_aggregate_to_daily_buckets_no_change(self, simple_daily_forecast):
        """Test that aggregating to daily buckets preserves original forecast."""
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 7))

        aggregated = aggregate_forecast_to_buckets(simple_daily_forecast, buckets)

        # Should have same number of entries
        assert len(aggregated.entries) == len(simple_daily_forecast.entries)

        # Quantities should match original
        for i, entry in enumerate(aggregated.entries):
            assert entry.quantity == simple_daily_forecast.entries[i].quantity

    def test_date_not_in_buckets_raises_error(self, simple_daily_forecast):
        """Test that forecast dates outside bucket range raise error."""
        # Create buckets that don't cover all dates
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 5))  # Only 5 days

        with pytest.raises(ValueError, match="not covered by any bucket"):
            aggregate_forecast_to_buckets(simple_daily_forecast, buckets)

    def test_empty_forecast_returns_empty(self):
        """Test that empty forecast returns empty aggregated forecast."""
        empty_forecast = Forecast(name="Empty", entries=[], creation_date=date.today())
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 7))

        aggregated = aggregate_forecast_to_buckets(empty_forecast, buckets)

        assert len(aggregated.entries) == 0
        assert aggregated.name == "Empty_aggregated"


class TestValidateAggregation:
    """Tests for validate_aggregation function."""

    def test_validation_passes_for_correct_aggregation(self, simple_daily_forecast):
        """Test that validation passes for correct aggregation."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.THREE_DAY
        )

        aggregated = aggregate_forecast_to_buckets(simple_daily_forecast, buckets)
        validation = validate_aggregation(simple_daily_forecast, aggregated)

        assert validation['valid'] is True
        assert validation['total_demand_original'] == validation['total_demand_aggregated']
        assert validation['total_difference'] < 1e-6

    def test_validation_detects_total_mismatch(self, simple_daily_forecast):
        """Test that validation detects total demand mismatch."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.WEEKLY
        )

        aggregated = aggregate_forecast_to_buckets(simple_daily_forecast, buckets)

        # Manually corrupt the aggregated forecast
        aggregated.entries[0].quantity += 100

        validation = validate_aggregation(simple_daily_forecast, aggregated)

        assert validation['valid'] is False
        assert abs(validation['total_difference'] - 100) < 1e-6

    def test_validation_by_destination(self, multi_destination_forecast):
        """Test validation provides per-destination differences."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.WEEKLY
        )

        aggregated = aggregate_forecast_to_buckets(multi_destination_forecast, buckets)
        validation = validate_aggregation(multi_destination_forecast, aggregated)

        assert 'by_destination_diff' in validation
        assert '6103' in validation['by_destination_diff']
        assert '6105' in validation['by_destination_diff']

        # All differences should be near zero for correct aggregation
        for dest, diff in validation['by_destination_diff'].items():
            assert diff < 1e-6


class TestDisaggregateToDaily:
    """Tests for disaggregate_to_daily function."""

    def test_disaggregate_single_bucket_proportional(self, simple_daily_forecast):
        """Test disaggregation distributes proportional to demand."""
        # Create 3-day bucket
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 3),
            BucketGranularity.THREE_DAY
        )

        # Aggregated production plan: 300 units for the 3-day bucket
        aggregated_plan = {
            date(2025, 6, 1): {"P1": 300}  # Representative date
        }

        # Original demand: Day1=100, Day2=150, Day3=120 (total=370)
        # Expected proportions: 100/370, 150/370, 120/370
        daily_plan = disaggregate_to_daily(aggregated_plan, simple_daily_forecast, buckets)

        # Check proportional distribution
        assert daily_plan[date(2025, 6, 1)]["P1"] == pytest.approx(300 * 100/370, rel=0.01)
        assert daily_plan[date(2025, 6, 2)]["P1"] == pytest.approx(300 * 150/370, rel=0.01)
        assert daily_plan[date(2025, 6, 3)]["P1"] == pytest.approx(300 * 120/370, rel=0.01)

        # Total should sum to aggregated quantity
        total = sum(daily_plan[date(2025, 6, d)]["P1"] for d in range(1, 4))
        assert total == pytest.approx(300, rel=0.001)

    def test_disaggregate_even_distribution_when_no_demand(self):
        """Test that production is distributed evenly when there's no demand pattern."""
        # Empty forecast
        empty_forecast = Forecast(name="Empty", entries=[], creation_date=date.today())

        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 3),
            BucketGranularity.THREE_DAY
        )

        # Aggregated plan: 300 units
        aggregated_plan = {
            date(2025, 6, 1): {"P1": 300}
        }

        daily_plan = disaggregate_to_daily(aggregated_plan, empty_forecast, buckets)

        # Should distribute evenly across 3 days = 100 per day
        assert daily_plan[date(2025, 6, 1)]["P1"] == pytest.approx(100, rel=0.01)
        assert daily_plan[date(2025, 6, 2)]["P1"] == pytest.approx(100, rel=0.01)
        assert daily_plan[date(2025, 6, 3)]["P1"] == pytest.approx(100, rel=0.01)

    def test_disaggregate_multiple_buckets(self, simple_daily_forecast):
        """Test disaggregation works across multiple buckets."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 6),
            BucketGranularity.THREE_DAY
        )

        # Two 3-day buckets
        aggregated_plan = {
            date(2025, 6, 1): {"P1": 300},  # Bucket 1 (days 1-3)
            date(2025, 6, 4): {"P1": 400},  # Bucket 2 (days 4-6)
        }

        daily_plan = disaggregate_to_daily(aggregated_plan, simple_daily_forecast, buckets)

        # Should have 6 days of production
        assert len(daily_plan) == 6

        # Bucket 1 total
        bucket1_total = sum(daily_plan[date(2025, 6, d)]["P1"] for d in range(1, 4))
        assert bucket1_total == pytest.approx(300, rel=0.001)

        # Bucket 2 total
        bucket2_total = sum(daily_plan[date(2025, 6, d)]["P1"] for d in range(4, 7))
        assert bucket2_total == pytest.approx(400, rel=0.001)

    def test_disaggregate_multiple_products(self, multi_destination_forecast):
        """Test disaggregation handles multiple products correctly."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.WEEKLY
        )

        # Production for both products
        aggregated_plan = {
            date(2025, 6, 1): {
                "P1": 1000,
                "P2": 500
            }
        }

        daily_plan = disaggregate_to_daily(aggregated_plan, multi_destination_forecast, buckets)

        # Should have production for both products on each day
        for day in range(1, 8):
            assert "P1" in daily_plan[date(2025, 6, day)]
            assert "P2" in daily_plan[date(2025, 6, day)]

        # Total production should match aggregated
        total_p1 = sum(daily_plan[date(2025, 6, d)]["P1"] for d in range(1, 8))
        total_p2 = sum(daily_plan[date(2025, 6, d)]["P2"] for d in range(1, 8))

        assert total_p1 == pytest.approx(1000, rel=0.001)
        assert total_p2 == pytest.approx(500, rel=0.001)
