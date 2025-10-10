"""Time period and bucket models for temporal aggregation.

This module provides data models and utilities for aggregating time periods
in optimization models. Supports variable granularity (daily, multi-day, weekly)
to reduce problem complexity while maintaining solution quality.
"""

from datetime import date as Date, timedelta
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, model_validator


class BucketGranularity(str, Enum):
    """Granularity levels for time bucket aggregation."""

    DAILY = "daily"
    TWO_DAY = "two_day"
    THREE_DAY = "three_day"
    WEEKLY = "weekly"

    @property
    def days(self) -> int:
        """Get number of days in this granularity."""
        return {
            BucketGranularity.DAILY: 1,
            BucketGranularity.TWO_DAY: 2,
            BucketGranularity.THREE_DAY: 3,
            BucketGranularity.WEEKLY: 7,
        }[self]


class TimeBucket(BaseModel):
    """
    Represents an aggregated time period for optimization.

    A time bucket groups multiple consecutive days into a single period,
    reducing the number of time-indexed decision variables in the model.

    Attributes:
        start_date: First date in the bucket (inclusive)
        end_date: Last date in the bucket (inclusive)
        granularity: Type of aggregation used
        representative_date: Date used to index this bucket in optimization
                            (typically start_date or middle of bucket)

    Example:
        # 3-day bucket covering June 1-3
        bucket = TimeBucket(
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            granularity=BucketGranularity.THREE_DAY
        )
        assert bucket.num_days == 3
        assert bucket.representative_date == date(2025, 6, 1)
    """

    start_date: Date = Field(..., description="Start date (inclusive)")
    end_date: Date = Field(..., description="End date (inclusive)")
    granularity: BucketGranularity = Field(..., description="Aggregation granularity")
    representative_date: Optional[Date] = Field(
        None,
        description="Representative date for optimization (defaults to start_date)"
    )

    @model_validator(mode='after')
    def validate_and_set_defaults(self):
        """Validate dates and set representative_date default."""
        # Validate end_date >= start_date
        if self.end_date < self.start_date:
            raise ValueError(f"end_date ({self.end_date}) must be >= start_date ({self.start_date})")

        # Set representative_date to start_date if not provided
        if self.representative_date is None:
            self.representative_date = self.start_date

        return self

    @property
    def num_days(self) -> int:
        """Get number of days in this bucket."""
        return (self.end_date - self.start_date).days + 1

    def contains_date(self, date: Date) -> bool:
        """Check if a date falls within this bucket."""
        return self.start_date <= date <= self.end_date

    def __str__(self) -> str:
        """String representation."""
        if self.num_days == 1:
            return f"{self.start_date}"
        return f"{self.start_date} to {self.end_date} ({self.num_days} days)"

    def __hash__(self) -> int:
        """Make TimeBucket hashable for use in sets/dicts."""
        return hash((self.start_date, self.end_date))


class VariableGranularityConfig(BaseModel):
    """
    Configuration for variable granularity within a planning window.

    Specifies how to vary the time bucket size across the planning horizon,
    typically using finer granularity near-term and coarser granularity long-term.

    Attributes:
        near_term_days: Number of days to use fine granularity (from window start)
        near_term_granularity: Granularity for near-term period (e.g., DAILY)
        far_term_granularity: Granularity for far-term period (e.g., THREE_DAY)

    Example:
        # Week 1 daily, weeks 2-4 in 2-day buckets
        config = VariableGranularityConfig(
            near_term_days=7,
            near_term_granularity=BucketGranularity.DAILY,
            far_term_granularity=BucketGranularity.TWO_DAY
        )
    """

    near_term_days: int = Field(
        7,
        description="Number of days for near-term (fine) granularity",
        ge=1
    )
    near_term_granularity: BucketGranularity = Field(
        BucketGranularity.DAILY,
        description="Granularity for near-term period"
    )
    far_term_granularity: BucketGranularity = Field(
        BucketGranularity.TWO_DAY,
        description="Granularity for far-term period"
    )

    def __str__(self) -> str:
        """String representation."""
        return (
            f"First {self.near_term_days} days: {self.near_term_granularity.value}, "
            f"remaining: {self.far_term_granularity.value}"
        )


def create_daily_buckets(start_date: Date, end_date: Date) -> List[TimeBucket]:
    """
    Create daily time buckets (no aggregation).

    Args:
        start_date: First date in horizon
        end_date: Last date in horizon (inclusive)

    Returns:
        List of TimeBucket objects, one per day

    Example:
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 3))
        assert len(buckets) == 3
        assert buckets[0].start_date == date(2025, 6, 1)
        assert buckets[0].end_date == date(2025, 6, 1)
    """
    if end_date < start_date:
        raise ValueError(f"end_date ({end_date}) must be >= start_date ({start_date})")

    buckets = []
    current = start_date

    while current <= end_date:
        buckets.append(TimeBucket(
            start_date=current,
            end_date=current,
            granularity=BucketGranularity.DAILY
        ))
        current += timedelta(days=1)

    return buckets


def create_uniform_buckets(
    start_date: Date,
    end_date: Date,
    granularity: BucketGranularity
) -> List[TimeBucket]:
    """
    Create uniformly-sized time buckets.

    Args:
        start_date: First date in horizon
        end_date: Last date in horizon (inclusive)
        granularity: Bucket size (DAILY, TWO_DAY, THREE_DAY, WEEKLY)

    Returns:
        List of TimeBucket objects

    Note:
        If horizon length is not divisible by bucket size, the last bucket
        will be smaller (partial bucket).

    Example:
        # Create 3-day buckets for a week
        buckets = create_uniform_buckets(
            date(2025, 6, 1),
            date(2025, 6, 7),
            BucketGranularity.THREE_DAY
        )
        assert len(buckets) == 3  # 3 days + 3 days + 1 day
        assert buckets[0].num_days == 3
        assert buckets[2].num_days == 1  # Partial bucket
    """
    if end_date < start_date:
        raise ValueError(f"end_date ({end_date}) must be >= start_date ({start_date})")

    if granularity == BucketGranularity.DAILY:
        return create_daily_buckets(start_date, end_date)

    buckets = []
    bucket_size = granularity.days
    current = start_date

    while current <= end_date:
        bucket_end = min(current + timedelta(days=bucket_size - 1), end_date)

        buckets.append(TimeBucket(
            start_date=current,
            end_date=bucket_end,
            granularity=granularity
        ))

        current = bucket_end + timedelta(days=1)

    return buckets


def create_variable_granularity_buckets(
    start_date: Date,
    end_date: Date,
    config: VariableGranularityConfig
) -> List[TimeBucket]:
    """
    Create time buckets with variable granularity.

    Uses fine granularity for near-term planning and coarse granularity
    for long-term planning to balance solution quality and solve time.

    Args:
        start_date: First date in horizon
        end_date: Last date in horizon (inclusive)
        config: Variable granularity configuration

    Returns:
        List of TimeBucket objects with mixed granularities

    Example:
        # Week 1 daily, weeks 2-3 in 2-day buckets
        config = VariableGranularityConfig(
            near_term_days=7,
            near_term_granularity=BucketGranularity.DAILY,
            far_term_granularity=BucketGranularity.TWO_DAY
        )
        buckets = create_variable_granularity_buckets(
            date(2025, 6, 1),
            date(2025, 6, 21),  # 3 weeks
            config
        )
        # Result: 7 daily buckets + 7 two-day buckets = 14 buckets total
        assert len(buckets) == 14
        assert buckets[0].granularity == BucketGranularity.DAILY
        assert buckets[7].granularity == BucketGranularity.TWO_DAY
    """
    if end_date < start_date:
        raise ValueError(f"end_date ({end_date}) must be >= start_date ({start_date})")

    buckets = []

    # Near-term buckets (fine granularity)
    near_term_end = start_date + timedelta(days=config.near_term_days - 1)
    if near_term_end > end_date:
        near_term_end = end_date

    near_buckets = create_uniform_buckets(
        start_date,
        near_term_end,
        config.near_term_granularity
    )
    buckets.extend(near_buckets)

    # Far-term buckets (coarse granularity)
    if near_term_end < end_date:
        far_term_start = near_term_end + timedelta(days=1)
        far_buckets = create_uniform_buckets(
            far_term_start,
            end_date,
            config.far_term_granularity
        )
        buckets.extend(far_buckets)

    return buckets


def get_bucket_for_date(buckets: List[TimeBucket], date: Date) -> Optional[TimeBucket]:
    """
    Find which bucket contains a given date.

    Args:
        buckets: List of time buckets
        date: Date to find

    Returns:
        TimeBucket containing the date, or None if not found

    Example:
        buckets = create_daily_buckets(date(2025, 6, 1), date(2025, 6, 7))
        bucket = get_bucket_for_date(buckets, date(2025, 6, 3))
        assert bucket.start_date == date(2025, 6, 3)
    """
    for bucket in buckets:
        if bucket.contains_date(date):
            return bucket
    return None


def calculate_bucket_reduction(
    horizon_days: int,
    granularity: BucketGranularity
) -> tuple[int, float]:
    """
    Calculate complexity reduction from bucketing.

    Args:
        horizon_days: Number of days in planning horizon
        granularity: Bucket granularity

    Returns:
        Tuple of (num_buckets, reduction_percentage)

    Example:
        # 21-day horizon with 3-day buckets
        num_buckets, reduction = calculate_bucket_reduction(21, BucketGranularity.THREE_DAY)
        assert num_buckets == 7  # 21 / 3
        assert reduction == 67.0  # 67% fewer periods
    """
    bucket_size = granularity.days
    num_buckets = (horizon_days + bucket_size - 1) // bucket_size  # Ceiling division
    reduction_pct = (1 - num_buckets / horizon_days) * 100

    return num_buckets, reduction_pct
