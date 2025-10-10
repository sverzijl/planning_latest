"""Forecast aggregation utilities for temporal bucketing.

This module provides functions to aggregate forecast data into time buckets,
reducing the number of time periods in optimization models while preserving
demand information.
"""

from datetime import date as Date
from typing import List, Dict, Tuple
from collections import defaultdict

from src.models.forecast import Forecast, ForecastEntry
from src.models.time_period import TimeBucket, get_bucket_for_date


def aggregate_forecast_to_buckets(
    forecast: Forecast,
    buckets: List[TimeBucket]
) -> Forecast:
    """
    Aggregate forecast entries into time buckets.

    Groups forecast entries by time bucket, summing demand within each bucket
    while preserving destination and product granularity.

    Args:
        forecast: Original forecast with daily or fine-grained demand
        buckets: Time buckets to aggregate into

    Returns:
        New Forecast with aggregated entries (one per bucket-destination-product)

    Raises:
        ValueError: If forecast contains dates not covered by any bucket

    Example:
        # Original forecast: Daily demand for 7 days
        forecast = Forecast(name="Daily", entries=[
            ForecastEntry(location_id="6103", product_id="P1", forecast_date=date(2025, 6, 1), quantity=100),
            ForecastEntry(location_id="6103", product_id="P1", forecast_date=date(2025, 6, 2), quantity=150),
            ForecastEntry(location_id="6103", product_id="P1", forecast_date=date(2025, 6, 3), quantity=120),
        ])

        # Aggregate into 3-day bucket
        buckets = create_uniform_buckets(date(2025, 6, 1), date(2025, 6, 3), BucketGranularity.THREE_DAY)
        aggregated = aggregate_forecast_to_buckets(forecast, buckets)

        # Result: Single entry with quantity=370 (100+150+120) for the 3-day bucket
        assert len(aggregated.entries) == 1
        assert aggregated.entries[0].quantity == 370
        assert aggregated.entries[0].forecast_date == date(2025, 6, 1)  # Representative date
    """
    # Build bucket lookup for fast date->bucket mapping
    bucket_map: Dict[Date, TimeBucket] = {}
    for bucket in buckets:
        # Map each day in the bucket to the bucket itself
        current = bucket.start_date
        while current <= bucket.end_date:
            bucket_map[current] = bucket
            current = current + __import__('datetime').timedelta(days=1)

    # Aggregate demand by (bucket, destination, product)
    aggregated_demand: Dict[Tuple[TimeBucket, str, str], float] = defaultdict(float)

    for entry in forecast.entries:
        # Find which bucket this date belongs to
        if entry.forecast_date not in bucket_map:
            raise ValueError(
                f"Forecast date {entry.forecast_date} not covered by any bucket. "
                f"Bucket range: {buckets[0].start_date} to {buckets[-1].end_date}"
            )

        bucket = bucket_map[entry.forecast_date]
        key = (bucket, entry.location_id, entry.product_id)
        aggregated_demand[key] += entry.quantity

    # Create aggregated forecast entries
    aggregated_entries = []
    for (bucket, location_id, product_id), total_quantity in aggregated_demand.items():
        aggregated_entries.append(ForecastEntry(
            location_id=location_id,
            product_id=product_id,
            forecast_date=bucket.representative_date,  # Use bucket's representative date
            quantity=total_quantity
        ))

    # Sort entries by date, location, product for consistency
    aggregated_entries.sort(
        key=lambda e: (e.forecast_date, e.location_id, e.product_id)
    )

    return Forecast(
        name=f"{forecast.name}_aggregated",
        entries=aggregated_entries,
        creation_date=forecast.creation_date
    )


def validate_aggregation(
    original: Forecast,
    aggregated: Forecast
) -> Dict[str, any]:
    """
    Validate that aggregation preserved total demand.

    Args:
        original: Original forecast before aggregation
        aggregated: Aggregated forecast

    Returns:
        Dictionary with validation results:
        - valid: bool - True if aggregation is valid
        - total_demand_original: Total demand in original
        - total_demand_aggregated: Total demand in aggregated
        - by_destination: Dict mapping destination to demand difference
        - by_product: Dict mapping product to demand difference

    Example:
        original = Forecast(...)
        aggregated = aggregate_forecast_to_buckets(original, buckets)
        validation = validate_aggregation(original, aggregated)

        assert validation['valid'] is True
        assert validation['total_demand_original'] == validation['total_demand_aggregated']
    """
    # Calculate total demand by destination
    original_by_dest: Dict[str, float] = defaultdict(float)
    aggregated_by_dest: Dict[str, float] = defaultdict(float)

    for entry in original.entries:
        original_by_dest[entry.location_id] += entry.quantity

    for entry in aggregated.entries:
        aggregated_by_dest[entry.location_id] += entry.quantity

    # Calculate total demand by product
    original_by_product: Dict[str, float] = defaultdict(float)
    aggregated_by_product: Dict[str, float] = defaultdict(float)

    for entry in original.entries:
        original_by_product[entry.product_id] += entry.quantity

    for entry in aggregated.entries:
        aggregated_by_product[entry.product_id] += entry.quantity

    # Calculate total demand
    total_original = sum(original_by_dest.values())
    total_aggregated = sum(aggregated_by_dest.values())

    # Check differences (allow small floating point errors)
    tolerance = 1e-6
    total_diff = abs(total_original - total_aggregated)
    valid = total_diff < tolerance

    dest_diffs = {
        dest: abs(original_by_dest.get(dest, 0) - aggregated_by_dest.get(dest, 0))
        for dest in set(original_by_dest.keys()) | set(aggregated_by_dest.keys())
    }

    product_diffs = {
        prod: abs(original_by_product.get(prod, 0) - aggregated_by_product.get(prod, 0))
        for prod in set(original_by_product.keys()) | set(aggregated_by_product.keys())
    }

    # Check if any destination or product has significant difference
    if any(diff > tolerance for diff in dest_diffs.values()):
        valid = False
    if any(diff > tolerance for diff in product_diffs.values()):
        valid = False

    return {
        'valid': valid,
        'total_demand_original': total_original,
        'total_demand_aggregated': total_aggregated,
        'total_difference': total_diff,
        'by_destination_diff': dest_diffs,
        'by_product_diff': product_diffs,
    }


def disaggregate_to_daily(
    aggregated_plan: Dict[Date, Dict[str, float]],
    original_forecast: Forecast,
    buckets: List[TimeBucket]
) -> Dict[Date, Dict[str, float]]:
    """
    Disaggregate production plan from buckets back to daily schedule.

    Distributes production quantities from aggregated buckets back to individual
    days, proportional to the original daily demand within each bucket.

    Args:
        aggregated_plan: Production plan indexed by bucket representative dates
                        Format: {bucket_date: {product_id: quantity}}
        original_forecast: Original daily forecast (used for proportions)
        buckets: Time buckets used in aggregation

    Returns:
        Daily production plan
        Format: {date: {product_id: quantity}}

    Example:
        # Aggregated plan: 300 units for 3-day bucket
        aggregated_plan = {
            date(2025, 6, 1): {"P1": 300}  # Representative date for June 1-3 bucket
        }

        # Original demand: Day1=100, Day2=150, Day3=50 (total=300)
        # Result: Proportional distribution
        daily = disaggregate_to_daily(aggregated_plan, original_forecast, buckets)
        # daily[date(2025, 6, 1)]["P1"] = 100 (100/300 * 300)
        # daily[date(2025, 6, 2)]["P1"] = 150 (150/300 * 300)
        # daily[date(2025, 6, 3)]["P1"] = 50 (50/300 * 300)
    """
    # Build bucket lookup
    bucket_lookup = {bucket.representative_date: bucket for bucket in buckets}

    # Calculate daily demand proportions within each bucket
    bucket_daily_demand: Dict[TimeBucket, Dict[Date, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )

    for entry in original_forecast.entries:
        # Find bucket for this date
        bucket = get_bucket_for_date(buckets, entry.forecast_date)
        if bucket is None:
            continue

        bucket_daily_demand[bucket][entry.forecast_date][entry.product_id] += entry.quantity

    # Disaggregate production to daily
    daily_plan: Dict[Date, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for bucket_date, production_by_product in aggregated_plan.items():
        if bucket_date not in bucket_lookup:
            # No bucket found - assign entire production to this date
            for product_id, quantity in production_by_product.items():
                daily_plan[bucket_date][product_id] += quantity
            continue

        bucket = bucket_lookup[bucket_date]

        # Calculate total demand in bucket by product
        bucket_total_demand: Dict[str, float] = defaultdict(float)
        for date in bucket_daily_demand[bucket]:
            for product_id, qty in bucket_daily_demand[bucket][date].items():
                bucket_total_demand[product_id] += qty

        # Distribute production proportionally across days in bucket
        for product_id, total_production in production_by_product.items():
            total_demand = bucket_total_demand.get(product_id, 0)

            if total_demand < 1e-6:
                # No demand for this product - distribute evenly across bucket days
                days_in_bucket = (bucket.end_date - bucket.start_date).days + 1
                production_per_day = total_production / days_in_bucket

                current = bucket.start_date
                while current <= bucket.end_date:
                    daily_plan[current][product_id] += production_per_day
                    current = current + __import__('datetime').timedelta(days=1)
            else:
                # Distribute proportional to demand
                for date, demand_by_product in bucket_daily_demand[bucket].items():
                    demand_this_day = demand_by_product.get(product_id, 0)
                    proportion = demand_this_day / total_demand
                    daily_plan[date][product_id] += total_production * proportion

    return dict(daily_plan)
