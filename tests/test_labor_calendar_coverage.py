"""Integration tests for labor calendar coverage issues.

Tests scenarios where production dates extend beyond labor calendar coverage,
ensuring the system handles missing dates gracefully or fails with clear errors.
"""

import pytest
from datetime import date, timedelta
import warnings

from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.production.scheduler import ProductionSchedule, ProductionBatch
from src.costs import LaborCostCalculator, CostCalculator
from src.models.forecast import Forecast, ForecastEntry
from src.models.shipment import Shipment


@pytest.fixture
def limited_labor_calendar():
    """Labor calendar covering only 5 days (Jan 6-10)."""
    days = []
    for day_offset in range(5):  # Jan 6-10, 2025
        target_date = date(2025, 1, 6) + timedelta(days=day_offset)
        is_weekday = target_date.weekday() < 5

        days.append(
            LaborDay(
                date=target_date,
                fixed_hours=12.0 if is_weekday else 0.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                non_fixed_rate=100.0,
                minimum_hours=0.0 if is_weekday else 4.0,
                is_fixed_day=is_weekday,
            )
        )

    return LaborCalendar(name="Limited Calendar", days=days)


@pytest.fixture
def extended_production_schedule():
    """Production schedule extending before and after calendar coverage."""
    batches = [
        # Before calendar (Jan 4 - Friday)
        ProductionBatch(
            id="BATCH-001",
            product_id="PROD1",
            manufacturing_site_id="6122",
            quantity=5600.0,
            production_date=date(2025, 1, 4),
        ),
        # Within calendar (Jan 7 - Tuesday)
        ProductionBatch(
            id="BATCH-002",
            product_id="PROD1",
            manufacturing_site_id="6122",
            quantity=8400.0,
            production_date=date(2025, 1, 7),
        ),
        # After calendar (Jan 13 - Monday)
        ProductionBatch(
            id="BATCH-003",
            product_id="PROD1",
            manufacturing_site_id="6122",
            quantity=11200.0,
            production_date=date(2025, 1, 13),
        ),
    ]

    return ProductionSchedule(
        manufacturing_site_id="6122",
        production_batches=batches,
        requirements=[],
        total_units=25200.0,
        schedule_start_date=date(2025, 1, 4),
        schedule_end_date=date(2025, 1, 13),
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_labor_hours=0.0,
    )


class TestLaborCalendarCoverageIntegration:
    """Integration tests for labor calendar coverage scenarios."""

    def test_graceful_handling_with_warnings(
        self,
        limited_labor_calendar,
        extended_production_schedule
    ):
        """Test that system handles missing dates with warnings (default mode)."""
        calculator = LaborCostCalculator(limited_labor_calendar)

        # Should produce warnings for missing dates but complete successfully
        with pytest.warns(UserWarning) as warning_list:
            breakdown = calculator.calculate_labor_cost(extended_production_schedule)

        # Should have at least 2 warnings (Jan 4 and Jan 13)
        assert len(warning_list) >= 2

        # Verify warnings mention missing dates
        warning_messages = [str(w.message) for w in warning_list]
        assert any("2025-01-04" in msg for msg in warning_messages)
        assert any("2025-01-13" in msg for msg in warning_messages)

        # Should complete calculation with defaults
        assert breakdown.total_cost > 0
        assert breakdown.total_hours > 0

    def test_strict_validation_fails_fast(
        self,
        limited_labor_calendar,
        extended_production_schedule
    ):
        """Test that strict validation fails fast with clear error."""
        calculator = LaborCostCalculator(
            limited_labor_calendar,
            strict_validation=True
        )

        # Should raise ValueError with clear message
        with pytest.raises(ValueError) as exc_info:
            calculator.calculate_labor_cost(extended_production_schedule)

        error_msg = str(exc_info.value)
        assert "Labor calendar missing" in error_msg
        assert "2025-01-04" in error_msg or "2025-01-13" in error_msg
        assert "production dates" in error_msg

    def test_cost_calculator_integration(self, limited_labor_calendar):
        """Test full cost calculator with labor calendar coverage issues."""
        cost_structure = CostStructure(
            production_cost_per_unit=0.80,
            shortage_penalty_per_unit=1.50,
            waste_cost_multiplier=1.5,
        )

        # Production schedule extending beyond calendar
        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="PROD1",
                manufacturing_site_id="6122",
                quantity=5600.0,
                production_date=date(2025, 1, 13),  # After calendar
            )
        ]
        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            requirements=[],
            total_units=5600.0,
            schedule_start_date=date(2025, 1, 13),
            schedule_end_date=date(2025, 1, 13),
            daily_totals={},
            daily_labor_hours={},
            infeasibilities=[],
            total_labor_hours=0.0,
        )

        # Empty forecast and shipments for minimal test
        forecast = Forecast(name="Test", entries=[])
        shipments = []

        cost_calculator = CostCalculator(cost_structure, limited_labor_calendar)

        # Should complete with warning
        with pytest.warns(UserWarning, match="Labor calendar missing date"):
            total_cost = cost_calculator.calculate_total_cost(
                production_schedule=schedule,
                shipments=shipments,
                forecast=forecast
            )

        # Should have non-zero costs
        assert total_cost.labor.total_cost > 0
        assert total_cost.production.total_cost > 0
        assert total_cost.total_cost > 0

    def test_partial_coverage_accuracy(self, limited_labor_calendar):
        """Test that costs are accurate with partial calendar coverage."""
        # Production on covered date (Jan 7) and uncovered date (Jan 13)
        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="PROD1",
                manufacturing_site_id="6122",
                quantity=5600.0,  # 4 hours
                production_date=date(2025, 1, 7),  # Covered (Tuesday)
            ),
            ProductionBatch(
                id="BATCH-002",
                product_id="PROD2",
                manufacturing_site_id="6122",
                quantity=5600.0,  # 4 hours
                production_date=date(2025, 1, 13),  # Not covered (Monday)
            ),
        ]
        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            requirements=[],
            total_units=11200.0,
            schedule_start_date=date(2025, 1, 7),
            schedule_end_date=date(2025, 1, 13),
            daily_totals={},
            daily_labor_hours={},
            infeasibilities=[],
            total_labor_hours=0.0,
        )

        calculator = LaborCostCalculator(limited_labor_calendar)

        with pytest.warns(UserWarning):
            breakdown = calculator.calculate_labor_cost(schedule)

        # Both should use same rates (both weekdays)
        # 4h + 4h = 8h at $50/h = $400
        assert breakdown.total_hours == 8.0
        assert breakdown.fixed_hours == 8.0
        assert breakdown.total_cost == 400.0

    def test_weekend_default_handling(self, limited_labor_calendar):
        """Test weekend date handling when missing from calendar."""
        # Sunday Jan 12 (not in calendar which ends Jan 10)
        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="PROD1",
                manufacturing_site_id="6122",
                quantity=4200.0,  # 3 hours
                production_date=date(2025, 1, 12),  # Sunday
            )
        ]
        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            requirements=[],
            total_units=4200.0,
            schedule_start_date=date(2025, 1, 12),
            schedule_end_date=date(2025, 1, 12),
            daily_totals={},
            daily_labor_hours={},
            infeasibilities=[],
            total_labor_hours=0.0,
        )

        calculator = LaborCostCalculator(limited_labor_calendar)

        with pytest.warns(UserWarning, match="weekend default rates"):
            breakdown = calculator.calculate_labor_cost(schedule)

        # Should use weekend non-fixed rates with 4h minimum
        assert breakdown.non_fixed_hours == 4.0  # 3h needed, 4h minimum
        assert breakdown.non_fixed_labor_cost == 400.0  # 4h × $100
        assert breakdown.total_cost == 400.0

    def test_multiple_missing_dates_logged_once(self, limited_labor_calendar):
        """Test that each missing date is only logged once even with multiple batches."""
        # Multiple batches on same missing date
        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="PROD1",
                manufacturing_site_id="6122",
                quantity=2800.0,
                production_date=date(2025, 1, 13),
            ),
            ProductionBatch(
                id="BATCH-002",
                product_id="PROD2",
                manufacturing_site_id="6122",
                quantity=2800.0,
                production_date=date(2025, 1, 13),  # Same missing date
            ),
        ]
        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            requirements=[],
            total_units=5600.0,
            schedule_start_date=date(2025, 1, 13),
            schedule_end_date=date(2025, 1, 13),
            daily_totals={},
            daily_labor_hours={},
            infeasibilities=[],
            total_labor_hours=0.0,
        )

        calculator = LaborCostCalculator(limited_labor_calendar)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            breakdown = calculator.calculate_labor_cost(schedule)

            # Should only warn once for the missing date
            labor_warnings = [warning for warning in w
                            if "Labor calendar missing date" in str(warning.message)]
            assert len(labor_warnings) == 1
