"""Tests for date filter component."""

import pytest
import pandas as pd
from datetime import datetime, date, timedelta
from ui.components.date_filter import (
    get_quick_range_dates,
    apply_date_filter,
    calculate_date_stats,
)


class TestGetQuickRangeDates:
    """Tests for get_quick_range_dates function."""

    def test_all_range_returns_min_max(self):
        """Test that 'all' range returns min and max dates."""
        min_date = datetime(2025, 1, 1)
        max_date = datetime(2025, 12, 31)

        start, end = get_quick_range_dates("all", min_date, max_date)

        assert start == min_date
        assert end == max_date

    def test_week_range_from_today(self):
        """Test that 'week' range returns 7 days from reference."""
        min_date = datetime(2025, 1, 1)
        max_date = datetime(2025, 12, 31)
        reference = datetime(2025, 1, 15)

        start, end = get_quick_range_dates("week", min_date, max_date, reference)

        assert start == reference
        assert end == datetime(2025, 1, 21)  # 7 days later (6 days added)
        assert (end - start).days == 6

    def test_two_weeks_range_from_today(self):
        """Test that '2weeks' range returns 14 days from reference."""
        min_date = datetime(2025, 1, 1)
        max_date = datetime(2025, 12, 31)
        reference = datetime(2025, 1, 15)

        start, end = get_quick_range_dates("2weeks", min_date, max_date, reference)

        assert start == reference
        assert end == datetime(2025, 1, 28)  # 14 days later (13 days added)
        assert (end - start).days == 13

    def test_month_range_from_today(self):
        """Test that 'month' range returns 30 days from reference."""
        min_date = datetime(2025, 1, 1)
        max_date = datetime(2025, 12, 31)
        reference = datetime(2025, 1, 15)

        start, end = get_quick_range_dates("month", min_date, max_date, reference)

        assert start == reference
        assert end == datetime(2025, 2, 13)  # 30 days later (29 days added)
        assert (end - start).days == 29

    def test_range_capped_at_max_date(self):
        """Test that ranges don't exceed max_date."""
        min_date = datetime(2025, 1, 1)
        max_date = datetime(2025, 1, 10)
        reference = datetime(2025, 1, 5)

        start, end = get_quick_range_dates("month", min_date, max_date, reference)

        assert start == reference
        assert end == max_date  # Capped at max_date, not 30 days later

    def test_reference_before_min_uses_min_date(self):
        """Test that reference before min_date uses min_date as start."""
        min_date = datetime(2025, 1, 10)
        max_date = datetime(2025, 12, 31)
        reference = datetime(2025, 1, 1)  # Before min_date

        start, end = get_quick_range_dates("week", min_date, max_date, reference)

        assert start == min_date  # Should use min_date, not reference
        assert end == datetime(2025, 1, 16)

    def test_reference_after_max_uses_min_date(self):
        """Test that reference after max_date uses min_date as start."""
        min_date = datetime(2025, 1, 1)
        max_date = datetime(2025, 1, 10)
        reference = datetime(2025, 2, 1)  # After max_date

        start, end = get_quick_range_dates("week", min_date, max_date, reference)

        assert start == min_date  # Should use min_date when reference is out of range
        # End is min_date + 6 days (week), or max_date if that's earlier
        assert end == min(datetime(2025, 1, 7), max_date)

    def test_no_reference_defaults_to_today(self):
        """Test that no reference uses today's date."""
        min_date = datetime(2020, 1, 1)
        max_date = datetime(2030, 12, 31)

        start, end = get_quick_range_dates("week", min_date, max_date)

        # Should be close to today
        today = datetime.now()
        assert abs((start - today).days) <= 1  # Within 1 day of today

    def test_handles_date_objects(self):
        """Test that function handles date objects (not just datetime)."""
        min_date = date(2025, 1, 1)
        max_date = date(2025, 12, 31)

        start, end = get_quick_range_dates("week", min_date, max_date)

        assert isinstance(start, datetime)
        assert isinstance(end, datetime)

    def test_custom_range_returns_full_range(self):
        """Test that 'custom' range returns min to max."""
        min_date = datetime(2025, 1, 1)
        max_date = datetime(2025, 12, 31)

        start, end = get_quick_range_dates("custom", min_date, max_date)

        assert start == min_date
        assert end == max_date


class TestApplyDateFilter:
    """Tests for apply_date_filter function."""

    def test_filters_dataframe_by_date_range(self):
        """Test that DataFrame is correctly filtered by date range."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-05', '2025-01-10', '2025-01-15']),
            'value': [100, 200, 300, 400]
        })

        start = datetime(2025, 1, 5)
        end = datetime(2025, 1, 10)

        filtered = apply_date_filter(df, 'date', start, end)

        assert len(filtered) == 2
        assert filtered['value'].tolist() == [200, 300]

    def test_includes_boundary_dates(self):
        """Test that start and end dates are inclusive."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-05', '2025-01-10']),
            'value': [100, 200, 300]
        })

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 10)

        filtered = apply_date_filter(df, 'date', start, end)

        assert len(filtered) == 3
        assert filtered['value'].tolist() == [100, 200, 300]

    def test_empty_dataframe_returns_empty(self):
        """Test that empty DataFrame returns empty."""
        df = pd.DataFrame({'date': pd.to_datetime([]), 'value': []})

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 10)

        filtered = apply_date_filter(df, 'date', start, end)

        assert len(filtered) == 0

    def test_missing_date_column_returns_original(self):
        """Test that missing date column returns original DataFrame."""
        df = pd.DataFrame({'value': [100, 200, 300]})

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 10)

        filtered = apply_date_filter(df, 'date', start, end)

        assert len(filtered) == 3

    def test_handles_date_objects_as_parameters(self):
        """Test that function handles date objects (not just datetime)."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-05', '2025-01-10']),
            'value': [100, 200, 300]
        })

        start = date(2025, 1, 5)
        end = date(2025, 1, 10)

        filtered = apply_date_filter(df, 'date', start, end)

        assert len(filtered) == 2
        assert filtered['value'].tolist() == [200, 300]

    def test_converts_non_datetime_column(self):
        """Test that non-datetime date column is converted."""
        df = pd.DataFrame({
            'date': ['2025-01-01', '2025-01-05', '2025-01-10'],
            'value': [100, 200, 300]
        })

        start = datetime(2025, 1, 5)
        end = datetime(2025, 1, 10)

        filtered = apply_date_filter(df, 'date', start, end)

        assert len(filtered) == 2
        assert filtered['value'].tolist() == [200, 300]

    def test_returns_copy_of_dataframe(self):
        """Test that function returns a copy, not a view."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-05', '2025-01-10']),
            'value': [100, 200, 300]
        })

        start = datetime(2025, 1, 5)
        end = datetime(2025, 1, 10)

        filtered = apply_date_filter(df, 'date', start, end)

        # Modify filtered DataFrame
        filtered.loc[filtered.index[0], 'value'] = 999

        # Original should be unchanged
        assert df['value'].tolist() == [100, 200, 300]

    def test_no_matching_dates_returns_empty(self):
        """Test that no matching dates returns empty DataFrame."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-05', '2025-01-10']),
            'value': [100, 200, 300]
        })

        start = datetime(2025, 2, 1)
        end = datetime(2025, 2, 10)

        filtered = apply_date_filter(df, 'date', start, end)

        assert len(filtered) == 0


class TestCalculateDateStats:
    """Tests for calculate_date_stats function."""

    def test_calculates_basic_stats(self):
        """Test calculation of basic statistics."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-05', '2025-01-10']),
            'quantity': [100, 200, 300]
        })

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 10)

        stats = calculate_date_stats(df, 'date', start, end, 'quantity')

        assert stats['num_records'] == 3
        assert stats['num_days'] == 10
        assert stats['start_date'] == start
        assert stats['end_date'] == end
        assert stats['unique_dates'] == 3
        assert stats['total_quantity'] == 600
        assert stats['avg_per_day'] == 60.0

    def test_handles_no_quantity_column(self):
        """Test handling when quantity column is not provided."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-05', '2025-01-10']),
            'value': [100, 200, 300]
        })

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 10)

        stats = calculate_date_stats(df, 'date', start, end)

        assert stats['num_records'] == 3
        assert stats['num_days'] == 10
        assert 'total_quantity' not in stats
        assert 'avg_per_day' not in stats

    def test_handles_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame({
            'date': pd.to_datetime([]),
            'quantity': []
        })

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 10)

        stats = calculate_date_stats(df, 'date', start, end, 'quantity')

        assert stats['num_records'] == 0
        assert stats['num_days'] == 10
        assert 'unique_dates' not in stats

    def test_handles_missing_date_column(self):
        """Test handling when date column is missing."""
        df = pd.DataFrame({
            'quantity': [100, 200, 300]
        })

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 10)

        stats = calculate_date_stats(df, 'date', start, end, 'quantity')

        assert stats['num_records'] == 3
        assert stats['num_days'] == 10
        assert 'unique_dates' not in stats

    def test_handles_single_day_range(self):
        """Test handling of single-day date range."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-01', '2025-01-01']),
            'quantity': [100, 200, 300]
        })

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 1)

        stats = calculate_date_stats(df, 'date', start, end, 'quantity')

        assert stats['num_records'] == 3
        assert stats['num_days'] == 1
        assert stats['unique_dates'] == 1
        assert stats['total_quantity'] == 600
        assert stats['avg_per_day'] == 600.0


# Integration tests would go here for render_date_range_filter
# These require Streamlit session state which is harder to test in unit tests
# Recommend manual testing in the UI for these components

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_min_date_equals_max_date(self):
        """Test handling when min_date equals max_date."""
        min_date = datetime(2025, 1, 1)
        max_date = datetime(2025, 1, 1)

        start, end = get_quick_range_dates("all", min_date, max_date)

        assert start == min_date
        assert end == max_date

    def test_very_large_date_range(self):
        """Test handling of very large date ranges."""
        min_date = datetime(2000, 1, 1)
        max_date = datetime(2050, 12, 31)

        start, end = get_quick_range_dates("all", min_date, max_date)

        assert start == min_date
        assert end == max_date

    def test_leap_year_handling(self):
        """Test correct handling of leap year dates."""
        min_date = datetime(2024, 2, 28)
        max_date = datetime(2024, 3, 10)
        reference = datetime(2024, 2, 28)

        start, end = get_quick_range_dates("week", min_date, max_date, reference)

        assert start == datetime(2024, 2, 28)
        assert end == datetime(2024, 3, 5)  # Should handle Feb 29 correctly

    def test_year_boundary_crossing(self):
        """Test date ranges that cross year boundaries."""
        min_date = datetime(2024, 12, 20)
        max_date = datetime(2025, 1, 20)
        reference = datetime(2024, 12, 28)

        start, end = get_quick_range_dates("week", min_date, max_date, reference)

        assert start == datetime(2024, 12, 28)
        assert end == datetime(2025, 1, 3)  # Crosses year boundary
