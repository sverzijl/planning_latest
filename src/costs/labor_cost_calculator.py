"""Labor cost calculator.

Calculates labor costs from production schedule and labor calendar, accounting for:
- Fixed hours at regular rate
- Overtime hours at premium rate
- Non-fixed labor days (weekends/holidays) with minimum hour commitment

IMPORTANT: Uses actual rates from LaborCalendar, not CostStructure defaults.
"""

from typing import Dict
from datetime import date

from src.models.labor_calendar import LaborCalendar
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

    def __init__(self, labor_calendar: LaborCalendar):
        """
        Initialize labor cost calculator.

        Args:
            labor_calendar: Labor calendar with daily rates and fixed hours
        """
        self.labor_calendar = labor_calendar

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
        """
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
        """
        labor_day = self.labor_calendar.get_labor_day(prod_date)
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
