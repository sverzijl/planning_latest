"""Labor cost calculator.

Calculates labor costs from production schedule and labor calendar, accounting for:
- Fixed hours at regular rate
- Overtime hours at premium rate
- Non-fixed labor days (weekends/holidays) with minimum hour commitment

IMPORTANT: Uses actual rates from LaborCalendar, not CostStructure defaults.
"""

from typing import Dict, List, Optional
from datetime import date
import warnings

from src.models.labor_calendar import LaborCalendar, LaborDay
from src.production.scheduler import ProductionSchedule
from .cost_breakdown import LaborCostBreakdown


class LaborCostCalculator:
    """
    Calculates labor costs from production schedule and calendar.

    Uses production hours from schedule and rates from labor calendar to compute:
    - Fixed hours cost (regular rate × fixed hours allocated)
    - Overtime cost (overtime rate × hours beyond fixed)
    - Non-fixed labor cost (non-fixed rate × hours on weekends/holidays)

    Example:
        calculator = LaborCostCalculator(labor_calendar)
        breakdown = calculator.calculate_labor_cost(production_schedule)
        print(f"Total labor cost: ${breakdown.total_cost:,.2f}")
    """

    # Production rate constant
    UNITS_PER_HOUR = 1400

    def __init__(self, labor_calendar: LaborCalendar, strict_validation: bool = False):
        """
        Initialize labor cost calculator.

        Args:
            labor_calendar: Labor calendar with daily rates and fixed hours
            strict_validation: If True, raise error on missing dates. If False, use defaults with warning.
        """
        self.labor_calendar = labor_calendar
        self.strict_validation = strict_validation
        self._missing_dates_logged: set[date] = set()  # Track logged warnings

        # Extract default rates from first available labor day
        self._default_rates = self._get_default_rates()

    def calculate_labor_cost(self, schedule: ProductionSchedule) -> LaborCostBreakdown:
        """
        Calculate total labor cost from production schedule.

        For each production date:
        1. Get labor day from calendar
        2. Calculate production hours needed
        3. Allocate hours to fixed/overtime/non-fixed categories
        4. Apply appropriate rates
        5. Aggregate across all dates

        Args:
            schedule: Production schedule with batches

        Returns:
            Detailed labor cost breakdown

        Raises:
            ValueError: If strict_validation=True and labor calendar missing dates
        """
        # Validate labor coverage if strict mode enabled
        if self.strict_validation:
            self._validate_labor_coverage(schedule)

        breakdown = LaborCostBreakdown()

        # Group batches by production date
        daily_production: Dict[date, float] = {}
        for batch in schedule.production_batches:
            prod_date = batch.production_date
            if prod_date not in daily_production:
                daily_production[prod_date] = 0.0
            daily_production[prod_date] += batch.quantity

        # Calculate cost for each date
        for prod_date, quantity in daily_production.items():
            labor_day = self.labor_calendar.get_labor_day(prod_date)

            # Handle missing labor day with smart default
            if labor_day is None:
                labor_day = self._get_default_labor_day(prod_date)
                if prod_date not in self._missing_dates_logged:
                    warnings.warn(
                        f"Labor calendar missing date {prod_date}. "
                        f"Using {'weekday' if labor_day.is_fixed_day else 'weekend'} default rates. "
                        f"Extend labor calendar to avoid approximations.",
                        UserWarning
                    )
                    self._missing_dates_logged.add(prod_date)

            # Calculate hours needed
            hours_needed = quantity / self.UNITS_PER_HOUR

            # Calculate cost components
            if labor_day.is_fixed_day:
                # Fixed labor day (weekday)
                fixed_hours = min(hours_needed, labor_day.fixed_hours)
                overtime_hours = max(0.0, hours_needed - labor_day.fixed_hours)

                fixed_cost = fixed_hours * labor_day.regular_rate
                overtime_cost = overtime_hours * labor_day.overtime_rate

                # Update breakdown
                breakdown.fixed_hours += fixed_hours
                breakdown.fixed_hours_cost += fixed_cost
                breakdown.overtime_hours += overtime_hours
                breakdown.overtime_cost += overtime_cost

                # Daily breakdown
                breakdown.daily_breakdown[prod_date] = {
                    "total_hours": hours_needed,
                    "fixed_hours": fixed_hours,
                    "overtime_hours": overtime_hours,
                    "fixed_cost": fixed_cost,
                    "overtime_cost": overtime_cost,
                    "non_fixed_cost": 0.0,
                    "total_cost": fixed_cost + overtime_cost,
                }

            else:
                # Non-fixed labor day (weekend/holiday)
                # Must pay for minimum hours even if production requires less
                hours_paid = max(hours_needed, labor_day.minimum_hours)
                non_fixed_cost = hours_paid * labor_day.non_fixed_rate

                # Update breakdown
                breakdown.non_fixed_hours += hours_paid
                breakdown.non_fixed_labor_cost += non_fixed_cost

                # Daily breakdown
                breakdown.daily_breakdown[prod_date] = {
                    "total_hours": hours_needed,
                    "fixed_hours": 0.0,
                    "overtime_hours": 0.0,
                    "fixed_cost": 0.0,
                    "overtime_cost": 0.0,
                    "non_fixed_cost": non_fixed_cost,
                    "total_cost": non_fixed_cost,
                }

        # Calculate totals
        breakdown.total_hours = breakdown.fixed_hours + breakdown.overtime_hours + breakdown.non_fixed_hours
        breakdown.total_cost = breakdown.fixed_hours_cost + breakdown.overtime_cost + breakdown.non_fixed_labor_cost

        return breakdown

    def calculate_daily_labor_cost(
        self,
        prod_date: date,
        quantity: float
    ) -> Dict[str, float]:
        """
        Calculate labor cost for a single production day.

        Args:
            prod_date: Production date
            quantity: Units produced on this date

        Returns:
            Dictionary with cost breakdown:
                - total_cost
                - fixed_cost
                - overtime_cost
                - non_fixed_cost
                - hours_needed
                - hours_paid

        Raises:
            ValueError: If strict_validation=True and labor date missing
        """
        labor_day = self.labor_calendar.get_labor_day(prod_date)

        # Handle missing labor day
        if labor_day is None:
            if self.strict_validation:
                raise ValueError(
                    f"Labor calendar missing date {prod_date}. "
                    f"Extend calendar to cover all production dates."
                )
            labor_day = self._get_default_labor_day(prod_date)
            if prod_date not in self._missing_dates_logged:
                warnings.warn(
                    f"Labor calendar missing date {prod_date}. Using defaults.",
                    UserWarning
                )
                self._missing_dates_logged.add(prod_date)

        hours_needed = quantity / self.UNITS_PER_HOUR

        if labor_day.is_fixed_day:
            # Fixed labor day
            fixed_hours = min(hours_needed, labor_day.fixed_hours)
            overtime_hours = max(0.0, hours_needed - labor_day.fixed_hours)

            fixed_cost = fixed_hours * labor_day.regular_rate
            overtime_cost = overtime_hours * labor_day.overtime_rate

            return {
                "total_cost": fixed_cost + overtime_cost,
                "fixed_cost": fixed_cost,
                "overtime_cost": overtime_cost,
                "non_fixed_cost": 0.0,
                "hours_needed": hours_needed,
                "hours_paid": hours_needed,
            }
        else:
            # Non-fixed labor day
            hours_paid = max(hours_needed, labor_day.minimum_hours)
            non_fixed_cost = hours_paid * labor_day.non_fixed_rate

            return {
                "total_cost": non_fixed_cost,
                "fixed_cost": 0.0,
                "overtime_cost": 0.0,
                "non_fixed_cost": non_fixed_cost,
                "hours_needed": hours_needed,
                "hours_paid": hours_paid,
            }

    def _get_default_rates(self) -> Dict[str, float]:
        """
        Extract default rates from labor calendar for use when dates are missing.

        Returns:
            Dictionary with default rates:
                - regular_rate
                - overtime_rate
                - non_fixed_rate
                - minimum_hours

        Raises:
            ValueError: If labor calendar is empty
        """
        if not self.labor_calendar.days:
            raise ValueError("Labor calendar is empty. Cannot calculate costs.")

        # Use first labor day as source for default rates
        first_day = self.labor_calendar.days[0]
        return {
            "regular_rate": first_day.regular_rate,
            "overtime_rate": first_day.overtime_rate,
            "non_fixed_rate": first_day.non_fixed_rate or first_day.overtime_rate,
            "minimum_hours": 4.0,  # Standard minimum for non-fixed days
        }

    def _get_default_labor_day(self, target_date: date) -> LaborDay:
        """
        Create a default labor day for a missing date.

        Uses weekday to determine if fixed or non-fixed day:
        - Monday-Friday: Fixed day with 12h fixed hours
        - Saturday-Sunday: Non-fixed day with 4h minimum

        Args:
            target_date: Date to create default for

        Returns:
            Default LaborDay with appropriate rates
        """
        is_weekday = target_date.weekday() < 5  # 0=Monday, 4=Friday

        if is_weekday:
            # Weekday: Fixed labor day
            return LaborDay(
                date=target_date,
                fixed_hours=12.0,  # Standard fixed hours
                regular_rate=self._default_rates["regular_rate"],
                overtime_rate=self._default_rates["overtime_rate"],
                non_fixed_rate=self._default_rates["non_fixed_rate"],
                minimum_hours=0.0,
                is_fixed_day=True,
            )
        else:
            # Weekend: Non-fixed labor day
            return LaborDay(
                date=target_date,
                fixed_hours=0.0,
                regular_rate=self._default_rates["regular_rate"],
                overtime_rate=self._default_rates["overtime_rate"],
                non_fixed_rate=self._default_rates["non_fixed_rate"],
                minimum_hours=self._default_rates["minimum_hours"],
                is_fixed_day=False,
            )

    def _validate_labor_coverage(self, schedule: ProductionSchedule) -> None:
        """
        Validate that labor calendar covers all production dates.

        Args:
            schedule: Production schedule to validate

        Raises:
            ValueError: If labor calendar missing critical dates
        """
        missing_dates: List[date] = []

        for batch in schedule.production_batches:
            if self.labor_calendar.get_labor_day(batch.production_date) is None:
                missing_dates.append(batch.production_date)

        if missing_dates:
            missing_dates.sort()
            raise ValueError(
                f"Labor calendar missing {len(missing_dates)} production dates. "
                f"Date range: {missing_dates[0]} to {missing_dates[-1]}. "
                f"First 5 missing: {missing_dates[:5]}. "
                f"Extend labor calendar to cover {schedule.schedule_start_date} to {schedule.schedule_end_date}."
            )
