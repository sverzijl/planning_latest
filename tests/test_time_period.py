"""Tests for time period and bucket models."""

import pytest
from datetime import date, timedelta

from src.models.time_period import (
    TimeBucket,
    BucketGranularity,
    VariableGranularityConfig,
    create_daily_buckets,
    create_uniform_buckets,
    create_variable_granularity_buckets,
    get_bucket_for_date,
    calculate_bucket_reduction,
)


class TestBucketGranularity:
    """Tests for BucketGranularity enum."""

    def test_granularity_days(self):
        """Test days property for each granularity."""
        assert BucketGranularity.DAILY.days == 1
        assert BucketGranularity.TWO_DAY.days == 2
        assert BucketGranularity.THREE_DAY.days == 3
        assert BucketGranularity.WEEKLY.days == 7


class TestTimeBucket:
    """Tests for TimeBucket model."""

    def test_create_single_day_bucket(self):
        """Test creating a single-day bucket."""
        bucket = TimeBucket(
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 1),
            granularity=BucketGranularity.DAILY
        )

        assert bucket.start_date == date(2025, 6, 1)
        assert bucket.end_date == date(2025, 6, 1)
        assert bucket.num_days == 1
        assert bucket.representative_date == date(2025, 6, 1)

    def test_create_multi_day_bucket(self):
        """Test creating a multi-day bucket."""
        bucket = TimeBucket(
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            granularity=BucketGranularity.THREE_DAY
        )

        assert bucket.num_days == 3
        assert bucket.representative_date == date(2025, 6, 1)

    def test_contains_date(self):
        """Test date containment check."""
        bucket = TimeBucket(
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            granularity=BucketGranularity.THREE_DAY
        )

        assert bucket.contains_date(date(2025, 6, 1)) is True
        assert bucket.contains_date(date(2025, 6, 2)) is True
        assert bucket.contains_date(date(2025, 6, 3)) is True
        assert bucket.contains_date(date(2025, 5, 31)) is False
        assert bucket.contains_date(date(2025, 6, 4)) is False

    def test_end_before_start_raises_error(self):
        """Test that end_date < start_date raises validation error."""
        with pytest.raises(ValueError, match="must be >= start_date"):
            TimeBucket(
                start_date=date(2025, 6, 3),
                end_date=date(2025, 6, 1),  # Before start!
                granularity=BucketGranularity.DAILY
            )

    def test_str_single_day(self):
        """Test string representation for single-day bucket."""
        bucket = TimeBucket(
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 1),
            granularity=BucketGranularity.DAILY
        )
        assert str(bucket) == "2025-06-01"

    def test_str_multi_day(self):
        """Test string representation for multi-day bucket."""
        bucket = TimeBucket(
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            granularity=BucketGranularity.THREE_DAY
        )
        assert "2025-06-01 to 2025-06-03" in str(bucket)
        assert "3 days" in str(bucket)


class TestVariableGranularityConfig:
    """Tests for VariableGranularityConfig model."""

    def test_create_default_config(self):
        """Test creating config with defaults."""
        config = VariableGranularityConfig()

        assert config.near_term_days == 7
        assert config.near_term_granularity == BucketGranularity.DAILY
        assert config.far_term_granularity == BucketGranularity.TWO_DAY

    def test_create_custom_config(self):
        """Test creating custom configuration."""
        config = VariableGranularityConfig(
            near_term_days=14,
            near_term_granularity=BucketGranularity.DAILY,
            far_term_granularity=BucketGranularity.WEEKLY
        )

        assert config.near_term_days == 14
        assert config.near_term_granularity == BucketGranularity.DAILY
        assert config.far_term_granularity == BucketGranularity.WEEKLY


class TestCreateDailyBuckets:
    """Tests for create_daily_buckets function."""

    def test_create_single_day(self):
        """Test creating buckets for a single day."""
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 1))

        assert len(buckets) == 1
        assert buckets[0].start_date == date(2025, 6, 1)
        assert buckets[0].end_date == date(2025, 6, 1)
        assert buckets[0].granularity == BucketGranularity.DAILY

    def test_create_one_week(self):
        """Test creating buckets for one week."""
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 7))

        assert len(buckets) == 7
        assert buckets[0].start_date == date(2025, 6, 1)
        assert buckets[6].start_date == date(2025, 6, 7)
        assert all(b.granularity == BucketGranularity.DAILY for b in buckets)

    def test_end_before_start_raises_error(self):
        """Test that invalid date range raises error."""
        with pytest.raises(ValueError, match="must be >= start_date"):
            create_daily_buckets(date(2025, 6, 7), date(2025, 6, 1))


class TestCreateUniformBuckets:
    """Tests for create_uniform_buckets function."""

    def test_create_three_day_buckets_exact_fit(self):
        """Test creating 3-day buckets with exact fit."""
        # 21 days = exactly 7 three-day buckets
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 21),
            BucketGranularity.THREE_DAY
        )

        assert len(buckets) == 7
        assert buckets[0].start_date == date(2025, 6, 1)
        assert buckets[0].end_date == date(2025, 6, 3)
        assert buckets[0].num_days == 3
        assert buckets[6].start_date == date(2025, 6, 19)
        assert buckets[6].end_date == date(2025, 6, 21)

    def test_create_three_day_buckets_partial(self):
        """Test creating 3-day buckets with partial last bucket."""
        # 8 days = 2 full buckets + 1 partial (2 days)
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 8),
            BucketGranularity.THREE_DAY
        )

        assert len(buckets) == 3
        assert buckets[0].num_days == 3
        assert buckets[1].num_days == 3
        assert buckets[2].num_days == 2  # Partial bucket
        assert buckets[2].start_date == date(2025, 6, 7)
        assert buckets[2].end_date == date(2025, 6, 8)

    def test_create_weekly_buckets(self):
        """Test creating weekly buckets."""
        # 3 weeks = exactly 3 weekly buckets
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 21),
            BucketGranularity.WEEKLY
        )

        assert len(buckets) == 3
        assert buckets[0].num_days == 7
        assert buckets[1].num_days == 7
        assert buckets[2].num_days == 7

    def test_create_two_day_buckets(self):
        """Test creating 2-day buckets."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 10),
            BucketGranularity.TWO_DAY
        )

        assert len(buckets) == 5  # 2+2+2+2+2 = 10 days
        assert all(b.num_days == 2 for b in buckets)

    def test_daily_granularity_delegates_to_create_daily(self):
        """Test that DAILY granularity uses create_daily_buckets."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.DAILY
        )

        assert len(buckets) == 7
        assert all(b.num_days == 1 for b in buckets)


class TestCreateVariableGranularityBuckets:
    """Tests for create_variable_granularity_buckets function."""

    def test_week1_daily_rest_two_day(self):
        """Test first week daily, remaining in 2-day buckets."""
        config = VariableGranularityConfig(
            near_term_days=7,
            near_term_granularity=BucketGranularity.DAILY,
            far_term_granularity=BucketGranularity.TWO_DAY
        )

        # 21 days total
        buckets = create_variable_granularity_buckets(
            date(2025, 6, 1),
            date(2025, 6, 21),
            config
        )

        # 7 daily buckets + 7 two-day buckets = 14 total
        assert len(buckets) == 14

        # First 7 buckets are daily
        assert all(buckets[i].granularity == BucketGranularity.DAILY for i in range(7))
        assert buckets[0].start_date == date(2025, 6, 1)
        assert buckets[6].start_date == date(2025, 6, 7)

        # Remaining buckets are two-day
        assert all(buckets[i].granularity == BucketGranularity.TWO_DAY for i in range(7, 14))
        assert buckets[7].start_date == date(2025, 6, 8)
        assert buckets[7].num_days == 2

    def test_all_near_term_if_horizon_short(self):
        """Test that short horizon uses only near-term granularity."""
        config = VariableGranularityConfig(
            near_term_days=10,
            near_term_granularity=BucketGranularity.DAILY,
            far_term_granularity=BucketGranularity.WEEKLY
        )

        # Horizon shorter than near_term_days
        buckets = create_variable_granularity_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),  # Only 7 days
            config
        )

        # All buckets are daily (near-term)
        assert len(buckets) == 7
        assert all(b.granularity == BucketGranularity.DAILY for b in buckets)

    def test_month_daily_rest_weekly(self):
        """Test first month daily, remaining weekly."""
        config = VariableGranularityConfig(
            near_term_days=28,
            near_term_granularity=BucketGranularity.DAILY,
            far_term_granularity=BucketGranularity.WEEKLY
        )

        # 8 weeks = 56 days
        buckets = create_variable_granularity_buckets(
            date(2025, 6, 1),
            date(2025, 7, 26),  # 56 days
            config
        )

        # 28 daily buckets + 4 weekly buckets = 32 total
        assert len(buckets) == 32

        # First 28 are daily
        assert sum(1 for b in buckets if b.granularity == BucketGranularity.DAILY) == 28

        # Last 4 are weekly
        assert sum(1 for b in buckets if b.granularity == BucketGranularity.WEEKLY) == 4


class TestGetBucketForDate:
    """Tests for get_bucket_for_date function."""

    def test_find_bucket_in_daily_buckets(self):
        """Test finding bucket for a date in daily buckets."""
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 7))

        bucket = get_bucket_for_date(buckets, date(2025, 6, 3))

        assert bucket is not None
        assert bucket.start_date == date(2025, 6, 3)

    def test_find_bucket_in_multi_day_buckets(self):
        """Test finding bucket in 3-day buckets."""
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 9),
            BucketGranularity.THREE_DAY
        )

        bucket = get_bucket_for_date(buckets, date(2025, 6, 5))

        assert bucket is not None
        assert bucket.start_date == date(2025, 6, 4)
        assert bucket.end_date == date(2025, 6, 6)

    def test_date_not_in_buckets_returns_none(self):
        """Test that date outside bucket range returns None."""
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 7))

        bucket = get_bucket_for_date(buckets, date(2025, 7, 1))

        assert bucket is None


class TestCalculateBucketReduction:
    """Tests for calculate_bucket_reduction function."""

    def test_three_day_buckets_21_days(self):
        """Test reduction calculation for 3-day buckets over 21 days."""
        num_buckets, reduction = calculate_bucket_reduction(21, BucketGranularity.THREE_DAY)

        assert num_buckets == 7  # 21 / 3
        assert reduction == pytest.approx(66.67, rel=0.1)  # (1 - 7/21) * 100

    def test_weekly_buckets_28_days(self):
        """Test reduction calculation for weekly buckets over 28 days."""
        num_buckets, reduction = calculate_bucket_reduction(28, BucketGranularity.WEEKLY)

        assert num_buckets == 4  # 28 / 7
        assert reduction == pytest.approx(85.71, rel=0.1)  # (1 - 4/28) * 100

    def test_daily_buckets_no_reduction(self):
        """Test that daily buckets show 0% reduction."""
        num_buckets, reduction = calculate_bucket_reduction(14, BucketGranularity.DAILY)

        assert num_buckets == 14
        assert reduction == 0.0

    def test_partial_bucket_rounding(self):
        """Test that partial buckets round up."""
        # 8 days with 3-day buckets = 3 buckets (2 full + 1 partial)
        num_buckets, reduction = calculate_bucket_reduction(8, BucketGranularity.THREE_DAY)

        assert num_buckets == 3  # Ceiling of 8/3
        assert reduction == pytest.approx(62.5, rel=0.1)  # (1 - 3/8) * 100
