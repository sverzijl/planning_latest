"""Labor calendar data model for daily labor availability and costs."""

from datetime import date as Date
from typing import Optional
from pydantic import BaseModel, Field


class LaborDay(BaseModel):
    """
    Represents labor availability and costs for a specific day.

    Attributes:
        date: The calendar date
        fixed_hours: Allocated fixed labor hours (at regular rate)
        regular_rate: Hourly rate for fixed labor hours ($/hour)
        overtime_rate: Hourly rate for overtime (hours beyond fixed_hours) ($/hour)
        non_fixed_rate: Hourly rate for non-fixed labor days ($/hour)
        minimum_hours: Minimum hours that must be paid on non-fixed days
        is_fixed_day: True if this is a fixed labor day, False if non-fixed
    """
    date: Date = Field(..., description="Calendar date")
    fixed_hours: float = Field(
        default=0.0,
        description="Fixed labor hours allocated",
        ge=0
    )
    regular_rate: float = Field(
        ...,
        description="Regular hourly rate ($/hour)",
        ge=0
    )
    overtime_rate: float = Field(
        ...,
        description="Overtime hourly rate ($/hour)",
        ge=0
    )
    non_fixed_rate: Optional[float] = Field(
        None,
        description="Non-fixed day hourly rate ($/hour)",
        ge=0
    )
    minimum_hours: float = Field(
        default=0.0,
        description="Minimum hours commitment on non-fixed days",
        ge=0
    )
    is_fixed_day: bool = Field(
        default=True,
        description="True if fixed labor day, False if non-fixed"
    )

    def calculate_labor_cost(self, actual_hours: float) -> float:
        """
        Calculate total labor cost for given actual hours worked.

        Business Rules:
        - Fixed day: regular_rate for hours up to fixed_hours, overtime_rate for excess
        - Non-fixed day: non_fixed_rate × max(actual_hours, minimum_hours)

        Args:
            actual_hours: Actual labor hours worked

        Returns:
            Total labor cost

        Raises:
            ValueError: If non_fixed_rate is None on a non-fixed day
        """
        if actual_hours < 0:
            raise ValueError("Actual hours must be non-negative")

        if self.is_fixed_day:
            # Fixed labor day
            if actual_hours <= self.fixed_hours:
                # All hours at regular rate
                return actual_hours * self.regular_rate
            else:
                # Fixed hours at regular rate + overtime
                regular_cost = self.fixed_hours * self.regular_rate
                overtime_hours = actual_hours - self.fixed_hours
                overtime_cost = overtime_hours * self.overtime_rate
                return regular_cost + overtime_cost
        else:
            # Non-fixed labor day
            if self.non_fixed_rate is None:
                raise ValueError("non_fixed_rate must be specified for non-fixed days")
            # Must pay for at least minimum_hours
            billable_hours = max(actual_hours, self.minimum_hours)
            return billable_hours * self.non_fixed_rate

    def get_available_hours(self) -> Optional[float]:
        """
        Get available labor hours for this day.

        Returns:
            Fixed hours if fixed day, None if non-fixed day (unlimited but expensive)
        """
        if self.is_fixed_day:
            return self.fixed_hours
        return None  # Non-fixed days can run unlimited hours (at higher cost)

    def is_zero_allocation_day(self) -> bool:
        """
        Check if this is a zero allocation day (no fixed labor).

        Returns:
            True if fixed_hours is 0 on a fixed day, or if non-fixed day
        """
        return (self.is_fixed_day and self.fixed_hours == 0) or not self.is_fixed_day

    def __str__(self) -> str:
        """String representation."""
        if self.is_fixed_day:
            return (
                f"{self.date}: Fixed day - {self.fixed_hours}h @ ${self.regular_rate}/h "
                f"(OT: ${self.overtime_rate}/h)"
            )
        else:
            return (
                f"{self.date}: Non-fixed day - ${self.non_fixed_rate}/h "
                f"(min: {self.minimum_hours}h)"
            )


class LaborCalendar(BaseModel):
    """
    Container for multiple labor days.

    Attributes:
        name: Calendar name (e.g., "Q4 2025 Labor Calendar")
        days: List of labor day entries
    """
    name: str = Field(..., description="Calendar name")
    days: list[LaborDay] = Field(
        default_factory=list,
        description="List of labor days"
    )

    def get_labor_day(self, target_date: Date) -> Optional[LaborDay]:
        """
        Get labor day entry for a specific date.

        Args:
            target_date: Date to query

        Returns:
            LaborDay if found, None otherwise
        """
        for day in self.days:
            if day.date == target_date:
                return day
        return None

    def calculate_period_cost(self, hours_by_date: dict[Date, float]) -> float:
        """
        Calculate total labor cost across multiple dates.

        Args:
            hours_by_date: Dictionary mapping dates to actual hours worked

        Returns:
            Total labor cost across all dates
        """
        total_cost = 0.0
        for target_date, hours in hours_by_date.items():
            labor_day = self.get_labor_day(target_date)
            if labor_day:
                total_cost += labor_day.calculate_labor_cost(hours)
            else:
                # No labor day entry - could raise warning or use default
                pass
        return total_cost

    def __str__(self) -> str:
        """String representation."""
        return f"LaborCalendar '{self.name}' with {len(self.days)} days"
