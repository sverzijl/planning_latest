"""
Tests for production feasibility checker.

This module tests capacity validation, labor constraints,
and packaging requirements.
"""

import pytest
from datetime import date, timedelta

from src.production.feasibility import (
    ProductionFeasibilityChecker,
    FeasibilityResult,
    PackagingAnalysis,
)
from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.location import LocationType, StorageMode


@pytest.fixture
def manufacturing_site():
    """Create a manufacturing site for testing."""
    return ManufacturingSite(
        id="6122",
        location_id="6122",
        name="QBA Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,  # units per hour
        max_daily_capacity=19600.0,  # max with 2h OT
        production_cost_per_unit=1.0,
    )


@pytest.fixture
def labor_calendar():
    """Create a labor calendar for testing."""
    # Week starting Monday 2025-01-06
    days = [
        # Monday: Fixed day, 12h + 2h OT
        LaborDay(
            date=date(2025, 1, 6),
            fixed_hours=12.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            is_fixed_day=True,
        ),
        # Tuesday: Fixed day, 12h + 2h OT
        LaborDay(
            date=date(2025, 1, 7),
            fixed_hours=12.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            is_fixed_day=True,
        ),
        # Wednesday: Fixed day, 12h + 2h OT
        LaborDay(
            date=date(2025, 1, 8),
            fixed_hours=12.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            is_fixed_day=True,
        ),
        # Saturday: Non-fixed day, 4h minimum
        LaborDay(
            date=date(2025, 1, 11),
            fixed_hours=0.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            non_fixed_rate=50.0,
            minimum_hours=4.0,
            is_fixed_day=False,
        ),
        # Sunday: Non-fixed day, 4h minimum
        LaborDay(
            date=date(2025, 1, 12),
            fixed_hours=0.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            non_fixed_rate=50.0,
            minimum_hours=4.0,
            is_fixed_day=False,
        ),
    ]

    return LaborCalendar(name="Test Calendar", days=days)


class TestPackagingAnalysis:
    """Tests for packaging analysis."""

    def test_perfect_pallet_alignment(self):
        """Test units that perfectly fill pallets."""
        checker = ProductionFeasibilityChecker(
            manufacturing_site=ManufacturingSite(
                id="test",
                location_id="test",
                name="Test",
                type=LocationType.MANUFACTURING,
                storage_mode=StorageMode.BOTH,
                production_rate=1400.0,
            ),
            labor_calendar=LaborCalendar(name="Test", days=[])
        )

        analysis = checker.analyze_packaging(320 * 5)  # 5 pallets exactly

        assert analysis.units == 1600
        assert analysis.cases == 160
        assert analysis.pallets == 5
        assert analysis.is_case_aligned
        assert analysis.is_pallet_aligned
        assert not analysis.partial_pallet_warning
        assert analysis.pallet_utilization == 100.0

    def test_partial_pallet(self):
        """Test units with partial pallet."""
        checker = ProductionFeasibilityChecker(
            manufacturing_site=ManufacturingSite(
                id="test",
                location_id="test",
                name="Test",
                type=LocationType.MANUFACTURING,
                storage_mode=StorageMode.BOTH,
                production_rate=1400.0,
            ),
            labor_calendar=LaborCalendar(name="Test", days=[])
        )

        analysis = checker.analyze_packaging(500)  # 50 cases = 1.56 pallets

        assert analysis.units == 500
        assert analysis.cases == 50
        assert analysis.pallets == 2  # Rounds up
        assert analysis.is_case_aligned
        assert not analysis.is_pallet_aligned
        assert analysis.partial_pallet_warning
        assert analysis.pallet_utilization < 100.0

    def test_non_case_aligned(self):
        """Test units not aligned to case boundaries."""
        checker = ProductionFeasibilityChecker(
            manufacturing_site=ManufacturingSite(
                id="test",
                location_id="test",
                name="Test",
                type=LocationType.MANUFACTURING,
                storage_mode=StorageMode.BOTH,
                production_rate=1400.0,
            ),
            labor_calendar=LaborCalendar(name="Test", days=[])
        )

        analysis = checker.analyze_packaging(325)  # Not divisible by 10

        assert analysis.units == 325
        assert analysis.cases == 32  # Floor division
        assert not analysis.is_case_aligned


class TestPackagingConstraints:
    """Tests for packaging constraints validation."""

    def test_valid_case_increment(self, manufacturing_site, labor_calendar):
        """Test valid packaging in 10-unit increments."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        result = checker.check_packaging_constraints(1000)
        assert result.is_feasible
        assert "100 cases" in result.reason

    def test_invalid_case_increment(self, manufacturing_site, labor_calendar):
        """Test invalid packaging (not 10-unit increment)."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        result = checker.check_packaging_constraints(1005)
        assert not result.is_feasible
        assert "10-unit" in result.reason

    def test_zero_production(self, manufacturing_site, labor_calendar):
        """Test zero production is valid."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        result = checker.check_packaging_constraints(0)
        assert result.is_feasible


class TestDailyCapacity:
    """Tests for daily capacity checking."""

    def test_within_fixed_hours(self, manufacturing_site, labor_calendar):
        """Test production within fixed labor hours."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        # 10,000 units = 10000/1400 = 7.14 hours (within 12h fixed)
        result = checker.check_daily_capacity(date(2025, 1, 6), 10000)

        assert result.is_feasible
        assert result.required_hours < 12.0
        assert result.available_hours == 14.0  # 12 fixed + 2 OT

    def test_requires_overtime(self, manufacturing_site, labor_calendar):
        """Test production requiring overtime."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        # 18,000 units = 18000/1400 = 12.86 hours (needs OT)
        result = checker.check_daily_capacity(date(2025, 1, 6), 18000)

        assert result.is_feasible
        assert result.required_hours > 12.0
        assert result.required_hours <= 14.0

    def test_exceeds_max_capacity(self, manufacturing_site, labor_calendar):
        """Test production exceeding max daily capacity."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        # 25,000 units exceeds both hours (17.9h > 14h) and max capacity (25,000 > 19,600)
        result = checker.check_daily_capacity(date(2025, 1, 6), 25000)

        assert not result.is_feasible
        # Either failure reason is valid (hours check happens first)
        assert ("max daily capacity" in result.reason.lower()) or ("available" in result.reason.lower())

    def test_exceeds_available_hours(self, manufacturing_site, labor_calendar):
        """Test production exceeding available hours."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        # 20,000 units = 20000/1400 = 14.29 hours (> 14h max)
        result = checker.check_daily_capacity(date(2025, 1, 6), 20000)

        assert not result.is_feasible
        assert result.required_hours > result.available_hours

    def test_non_fixed_day_allowed(self, manufacturing_site, labor_calendar):
        """Test production on non-fixed day (weekend)."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        # 5,000 units on Saturday (non-fixed day)
        result = checker.check_daily_capacity(date(2025, 1, 11), 5000, allow_non_fixed_days=True)

        assert result.is_feasible

    def test_non_fixed_day_not_allowed(self, manufacturing_site, labor_calendar):
        """Test production not allowed on non-fixed day."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        result = checker.check_daily_capacity(date(2025, 1, 11), 5000, allow_non_fixed_days=False)

        assert not result.is_feasible
        assert "non-fixed day" in result.reason.lower()

    def test_overtime_not_allowed(self, manufacturing_site, labor_calendar):
        """Test production with overtime not allowed."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        # 18,000 units requires OT
        result = checker.check_daily_capacity(date(2025, 1, 6), 18000, allow_overtime=False)

        assert not result.is_feasible
        assert result.available_hours == 12.0  # No OT

    def test_no_labor_calendar_entry(self, manufacturing_site):
        """Test date with no labor calendar entry."""
        calendar = LaborCalendar(name="Empty", days=[])
        checker = ProductionFeasibilityChecker(manufacturing_site, calendar)

        result = checker.check_daily_capacity(date(2025, 1, 1), 10000)

        assert not result.is_feasible
        assert "no labor calendar entry" in result.reason.lower()


class TestWeeklyCapacity:
    """Tests for weekly capacity checking."""

    def test_feasible_week(self, manufacturing_site, labor_calendar):
        """Test feasible weekly production."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        daily_quantities = {
            date(2025, 1, 6): 16000,  # Mon
            date(2025, 1, 7): 16000,  # Tue
            date(2025, 1, 8): 16000,  # Wed
        }

        result = checker.check_weekly_capacity(date(2025, 1, 6), daily_quantities)

        assert result.is_feasible

    def test_infeasible_day_in_week(self, manufacturing_site, labor_calendar):
        """Test week with infeasible individual day."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        daily_quantities = {
            date(2025, 1, 6): 16000,  # Mon - OK
            date(2025, 1, 7): 25000,  # Tue - Exceeds capacity!
        }

        result = checker.check_weekly_capacity(date(2025, 1, 6), daily_quantities)

        assert not result.is_feasible
        assert "infeasible" in result.reason.lower()


class TestMaximumProducible:
    """Tests for maximum producible calculation."""

    def test_fixed_day_with_overtime(self, manufacturing_site, labor_calendar):
        """Test max on fixed day with overtime."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        max_units = checker.get_maximum_producible(date(2025, 1, 6), allow_overtime=True)

        # 14 hours � 1400 units/h = 19,600 units (= max_daily_capacity)
        assert max_units == 19600

    def test_fixed_day_no_overtime(self, manufacturing_site, labor_calendar):
        """Test max on fixed day without overtime."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        max_units = checker.get_maximum_producible(date(2025, 1, 6), allow_overtime=False)

        # 12 hours � 1400 units/h = 16,800 units
        assert max_units == 16800

    def test_non_fixed_day(self, manufacturing_site, labor_calendar):
        """Test max on non-fixed day."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        max_units = checker.get_maximum_producible(date(2025, 1, 11), allow_non_fixed_days=True)

        # 12 hours practical limit � 1400 units/h = 16,800 units
        assert max_units == 16800

    def test_non_fixed_day_not_allowed(self, manufacturing_site, labor_calendar):
        """Test max when non-fixed days not allowed."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        max_units = checker.get_maximum_producible(date(2025, 1, 11), allow_non_fixed_days=False)

        assert max_units == 0


class TestProductionSplit:
    """Tests for production split suggestions."""

    def test_single_day_sufficient(self, manufacturing_site, labor_calendar):
        """Test split when single day is sufficient."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        allocation = checker.suggest_production_split(
            total_units=10000,
            preferred_dates=[date(2025, 1, 6)],
        )

        assert len(allocation) == 1
        assert allocation[date(2025, 1, 6)] == 10000

    def test_split_across_days(self, manufacturing_site, labor_calendar):
        """Test split across multiple days."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        allocation = checker.suggest_production_split(
            total_units=50000,  # Requires multiple days
            preferred_dates=[
                date(2025, 1, 6),
                date(2025, 1, 7),
                date(2025, 1, 8),
            ],
        )

        assert len(allocation) >= 2
        total_allocated = sum(allocation.values())
        assert total_allocated <= 50000  # May not allocate all if capacity insufficient

    def test_case_alignment_in_split(self, manufacturing_site, labor_calendar):
        """Test that split respects case alignment."""
        checker = ProductionFeasibilityChecker(manufacturing_site, labor_calendar)

        allocation = checker.suggest_production_split(
            total_units=30000,
            preferred_dates=[
                date(2025, 1, 6),
                date(2025, 1, 7),
            ],
        )

        # All allocations should be multiples of 10
        for qty in allocation.values():
            assert qty % 10 == 0
