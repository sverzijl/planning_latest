"""
Tests for LaborCalendar attribute usage to prevent regression.

This test suite specifically prevents the regression where .labor_days was
incorrectly used instead of .days attribute in ui/pages/2_Planning.py:457.

Background:
- Bug: ui/pages/2_Planning.py:457 used `.labor_days` instead of `.days`
- LaborCalendar model has attribute `days: list[LaborDay]`, not `labor_days`
- These tests verify correct attribute usage and defensive patterns
"""

import pytest
from datetime import date, timedelta

from src.models.labor_calendar import LaborCalendar, LaborDay


class TestLaborCalendarAttributes:
    """Test correct attribute naming and usage."""

    def test_labor_calendar_has_days_attribute(self):
        """
        Verify LaborCalendar has .days attribute and NOT .labor_days.

        This test prevents regression of the bug where code incorrectly
        referenced .labor_days instead of .days.
        """
        # Create a LaborCalendar instance
        labor_days = [
            LaborDay(
                date=date(2025, 1, 1),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                is_fixed_day=True
            )
        ]
        calendar = LaborCalendar(name="Test Calendar", days=labor_days)

        # Assert .days attribute exists
        assert hasattr(calendar, 'days'), "LaborCalendar must have .days attribute"
        assert calendar.days == labor_days, "LaborCalendar.days should contain labor day entries"

        # Assert .labor_days does NOT exist (should raise AttributeError)
        with pytest.raises(AttributeError, match="'LaborCalendar' object has no attribute 'labor_days'"):
            _ = calendar.labor_days

    def test_labor_calendar_days_is_list(self):
        """Verify .days attribute is a list type."""
        calendar = LaborCalendar(name="Test", days=[])

        assert isinstance(calendar.days, list), "LaborCalendar.days must be a list"
        assert calendar.days == [], "Empty calendar should have empty days list"

    def test_labor_calendar_days_contains_labor_day_objects(self):
        """Verify .days list contains LaborDay objects."""
        labor_day = LaborDay(
            date=date(2025, 1, 1),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0
        )
        calendar = LaborCalendar(name="Test", days=[labor_day])

        assert len(calendar.days) == 1
        assert isinstance(calendar.days[0], LaborDay)
        assert calendar.days[0] == labor_day


class TestLaborCalendarMaxDateCalculation:
    """Test max date calculation pattern used in Planning UI."""

    def test_labor_calendar_max_date_calculation(self):
        """
        Test max date calculation using correct attribute name.

        This replicates the pattern from ui/pages/2_Planning.py:457
        which should be: max(day.date for day in calendar.days)
        """
        # Create LaborCalendar with multiple LaborDay objects spanning different dates
        labor_days = [
            LaborDay(date=date(2025, 1, 1), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
            LaborDay(date=date(2025, 1, 15), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
            LaborDay(date=date(2025, 2, 28), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
            LaborDay(date=date(2025, 1, 10), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
        ]
        calendar = LaborCalendar(name="Test Calendar", days=labor_days)

        # Calculate max date using CORRECT attribute name
        max_date = max(day.date for day in calendar.days)

        # Verify correct max date returned
        assert max_date == date(2025, 2, 28), "Max date should be 2025-02-28"

    def test_labor_calendar_min_max_date_range(self):
        """Test both min and max date calculations."""
        labor_days = [
            LaborDay(date=date(2025, 1, 1), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
            LaborDay(date=date(2025, 3, 31), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
            LaborDay(date=date(2025, 2, 15), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
        ]
        calendar = LaborCalendar(name="Q1 2025", days=labor_days)

        min_date = min(day.date for day in calendar.days)
        max_date = max(day.date for day in calendar.days)

        assert min_date == date(2025, 1, 1)
        assert max_date == date(2025, 3, 31)
        assert (max_date - min_date).days == 89, "Q1 2025 span should be 89 days"


class TestLaborCalendarEmptyHandling:
    """Test defensive coding patterns for empty calendar."""

    def test_labor_calendar_empty_days_list(self):
        """
        Test that empty days list is handled gracefully.

        Defensive code pattern: if calendar.days: should be False
        """
        # Create LaborCalendar with empty days list
        calendar = LaborCalendar(name="Empty Calendar", days=[])

        # Verify defensive code handles empty list gracefully
        assert calendar.days == []
        assert len(calendar.days) == 0

        # Test defensive pattern: if calendar.days:
        if calendar.days:
            pytest.fail("Empty calendar.days should evaluate to False in boolean context")

        # This should not raise an error
        assert not calendar.days, "Empty list should be falsy"

    def test_labor_calendar_empty_max_raises_value_error(self):
        """Test that max() on empty days raises ValueError."""
        calendar = LaborCalendar(name="Empty", days=[])

        # max() on empty sequence should raise ValueError
        with pytest.raises(ValueError, match="max\\(\\) arg is an empty sequence"):
            _ = max(day.date for day in calendar.days)


class TestLaborCalendarNoneHandling:
    """Test defensive patterns for None labor_calendar objects."""

    def test_labor_calendar_none_handling(self):
        """
        Test defensive pattern when labor_calendar is None.

        Pattern from Planning UI:
        if data.get('labor_calendar') and data['labor_calendar'].days:
        """
        # Simulate data dictionary with None labor_calendar
        data = {'labor_calendar': None}

        # Defensive pattern should handle None gracefully
        if data.get('labor_calendar') and data['labor_calendar'].days:
            pytest.fail("None labor_calendar should not pass defensive check")

        # Verify None is handled correctly
        assert data.get('labor_calendar') is None

    def test_labor_calendar_missing_key_handling(self):
        """Test defensive pattern when labor_calendar key is missing."""
        data = {}

        # Defensive pattern with .get() should handle missing key
        if data.get('labor_calendar') and data['labor_calendar'].days:
            pytest.fail("Missing labor_calendar should not pass defensive check")

        assert data.get('labor_calendar') is None

    def test_labor_calendar_none_or_empty_days(self):
        """Test defensive pattern for None calendar or empty days."""
        # Test None calendar
        data_none = {'labor_calendar': None}
        result_none = data_none.get('labor_calendar') and data_none['labor_calendar'].days
        assert not result_none, "None calendar should fail defensive check"

        # Test empty days
        data_empty = {'labor_calendar': LaborCalendar(name="Empty", days=[])}
        result_empty = data_empty.get('labor_calendar') and data_empty['labor_calendar'].days
        assert not result_empty, "Empty days should fail defensive check"

        # Test populated days
        data_valid = {
            'labor_calendar': LaborCalendar(
                name="Valid",
                days=[LaborDay(date=date(2025, 1, 1), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0)]
            )
        }
        result_valid = data_valid.get('labor_calendar') and data_valid['labor_calendar'].days
        assert result_valid, "Valid calendar with days should pass defensive check"


class TestPlanningHorizonCoverage:
    """Test planning horizon validation against labor calendar coverage."""

    def test_planning_horizon_within_coverage(self):
        """
        Test planning horizon within labor calendar coverage (no warning).

        Create labor calendar covering 100 days, test planning horizon of 50 days.
        """
        # Create labor calendar covering 100 days
        start_date = date(2025, 1, 1)
        labor_days = [
            LaborDay(
                date=start_date + timedelta(days=i),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0
            )
            for i in range(100)
        ]
        calendar = LaborCalendar(name="100 Day Calendar", days=labor_days)

        # Calculate labor calendar end date
        labor_end = max(day.date for day in calendar.days)
        assert labor_end == date(2025, 4, 10), "100 days from 2025-01-01"

        # Test planning horizon of 50 days (within coverage)
        forecast_start = date(2025, 1, 1)
        planning_horizon_weeks = 7  # 49 days
        planning_end = forecast_start + timedelta(days=planning_horizon_weeks * 7)

        # Verify no warning should trigger (planning_end <= labor_end)
        assert planning_end <= labor_end, "Planning horizon should be within labor calendar coverage"
        days_remaining = (labor_end - planning_end).days
        assert days_remaining >= 0, f"Should have {days_remaining} days of buffer"

    def test_planning_horizon_exceeds_coverage(self):
        """
        Test planning horizon exceeding labor calendar coverage (should warn).

        Create labor calendar covering 50 days, test planning horizon of 100 days.
        """
        # Create labor calendar covering only 50 days
        start_date = date(2025, 1, 1)
        labor_days = [
            LaborDay(
                date=start_date + timedelta(days=i),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0
            )
            for i in range(50)
        ]
        calendar = LaborCalendar(name="50 Day Calendar", days=labor_days)

        # Calculate labor calendar end date
        labor_end = max(day.date for day in calendar.days)
        assert labor_end == date(2025, 2, 19), "50 days from 2025-01-01"

        # Test planning horizon of 100 days (exceeds coverage)
        forecast_start = date(2025, 1, 1)
        planning_horizon_weeks = 15  # 105 days
        planning_end = forecast_start + timedelta(days=planning_horizon_weeks * 7)

        # Verify warning condition should trigger (planning_end > labor_end)
        assert planning_end > labor_end, "Planning horizon exceeds labor calendar coverage"
        days_short = (planning_end - labor_end).days
        assert days_short > 0, f"Planning horizon extends {days_short} days beyond labor calendar"

    def test_planning_horizon_exact_coverage(self):
        """Test planning horizon exactly matching labor calendar coverage."""
        # Create labor calendar
        start_date = date(2025, 1, 1)
        num_days = 70  # 10 weeks exactly
        labor_days = [
            LaborDay(
                date=start_date + timedelta(days=i),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0
            )
            for i in range(num_days)
        ]
        calendar = LaborCalendar(name="10 Week Calendar", days=labor_days)

        labor_end = max(day.date for day in calendar.days)

        # Planning horizon exactly matches
        forecast_start = date(2025, 1, 1)
        planning_horizon_weeks = 10
        planning_end = forecast_start + timedelta(days=planning_horizon_weeks * 7 - 1)  # -1 because we count from day 0

        # Should be within coverage (not exceeding)
        assert planning_end <= labor_end, "Planning horizon is within labor calendar coverage"


class TestLaborCalendarIntegration:
    """Integration tests for LaborCalendar usage patterns."""

    def test_correct_attribute_usage_pattern(self):
        """
        Demonstrate correct usage pattern to prevent future regressions.

        This is the CORRECT pattern:
            labor_end = max(day.date for day in data['labor_calendar'].days)

        This is the INCORRECT pattern (bug):
            labor_end = max(day.date for day in data['labor_calendar'].labor_days)
        """
        # Create realistic data structure
        labor_days = [
            LaborDay(date=date(2025, 1, 1), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
            LaborDay(date=date(2025, 1, 2), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
            LaborDay(date=date(2025, 1, 3), fixed_hours=0.0, regular_rate=50.0, overtime_rate=75.0,
                    non_fixed_rate=100.0, minimum_hours=4.0, is_fixed_day=False),
        ]

        data = {
            'labor_calendar': LaborCalendar(name="Production Calendar", days=labor_days)
        }

        # CORRECT usage
        if data.get('labor_calendar') and data['labor_calendar'].days:
            labor_end = max(day.date for day in data['labor_calendar'].days)
            assert labor_end == date(2025, 1, 3)

        # INCORRECT usage should raise AttributeError
        with pytest.raises(AttributeError):
            if data.get('labor_calendar') and data['labor_calendar'].labor_days:
                _ = max(day.date for day in data['labor_calendar'].labor_days)

    def test_full_planning_horizon_check_pattern(self):
        """
        Complete pattern from ui/pages/2_Planning.py with correct attribute.

        This replicates the full defensive pattern with correct .days usage.
        """
        # Setup realistic data
        forecast_start = date(2025, 1, 1)
        planning_horizon_weeks = 4

        labor_days = [
            LaborDay(
                date=forecast_start + timedelta(days=i),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0
            )
            for i in range(21)  # 3 weeks of coverage
        ]

        data = {
            'labor_calendar': LaborCalendar(name="Test", days=labor_days)
        }

        # Replicate Planning UI pattern with CORRECT attribute
        if data.get('labor_calendar') and data['labor_calendar'].days:
            # Calculate planning horizon end
            custom_end_date = forecast_start + timedelta(days=planning_horizon_weeks * 7)

            # Check if labor calendar covers the planning horizon (CORRECT)
            labor_end = max(day.date for day in data['labor_calendar'].days)

            # Determine if warning should be shown
            should_warn = custom_end_date > labor_end

            assert should_warn is True, "4 week planning with 3 week labor coverage should warn"
            assert custom_end_date == date(2025, 1, 29)
            assert labor_end == date(2025, 1, 21)
