"""
Production feasibility checking and capacity validation.

This module validates production schedules against capacity constraints,
labor availability, and packaging requirements.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import math

from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar, LaborDay


@dataclass
class FeasibilityResult:
    """
    Result of a feasibility check.

    Attributes:
        is_feasible: Whether the production is feasible
        reason: Explanation of result
        max_capacity: Maximum capacity available (if applicable)
        required_hours: Labor hours required
        available_hours: Labor hours available
    """
    is_feasible: bool
    reason: str
    max_capacity: Optional[float] = None
    required_hours: Optional[float] = None
    available_hours: Optional[float] = None

    def __str__(self) -> str:
        if self.is_feasible:
            return f"Feasible: {self.reason}"
        else:
            return f"Infeasible: {self.reason}"


@dataclass
class PackagingAnalysis:
    """
    Analysis of packaging efficiency.

    Attributes:
        units: Number of units
        cases: Number of cases (units / 10)
        pallets: Number of pallets (cases / 32, rounded up)
        is_case_aligned: True if units is multiple of 10
        is_pallet_aligned: True if units is multiple of 320
        partial_pallet_warning: True if last pallet is partial
        pallet_utilization: Percentage of pallet capacity used
    """
    units: int
    cases: int
    pallets: int
    is_case_aligned: bool
    is_pallet_aligned: bool
    partial_pallet_warning: bool
    pallet_utilization: float

    def __str__(self) -> str:
        warning_str = " [!] Partial pallet" if self.partial_pallet_warning else ""
        return f"{self.units} units = {self.cases} cases = {self.pallets} pallets ({self.pallet_utilization:.1f}%){warning_str}"


class ProductionFeasibilityChecker:
    """
    Validates production feasibility against capacity and packaging constraints.

    This class checks:
    - Daily production capacity based on labor hours
    - Packaging constraints (10-unit case increments)
    - Pallet efficiency (320-unit pallet multiples)
    - Weekly capacity aggregates
    """

    # Constants
    UNITS_PER_CASE = 10
    CASES_PER_PALLET = 32
    UNITS_PER_PALLET = 320  # 32 cases � 10 units
    PALLETS_PER_TRUCK = 44
    UNITS_PER_TRUCK = 14080  # 44 pallets � 320 units

    def __init__(
        self,
        manufacturing_site: ManufacturingSite,
        labor_calendar: LaborCalendar
    ):
        """
        Initialize feasibility checker.

        Args:
            manufacturing_site: Manufacturing site with production capabilities
            labor_calendar: Labor calendar with daily labor availability
        """
        self.manufacturing_site = manufacturing_site
        self.labor_calendar = labor_calendar

    def check_daily_capacity(
        self,
        production_date: date,
        units: float,
        allow_overtime: bool = True,
        allow_non_fixed_days: bool = True
    ) -> FeasibilityResult:
        """
        Check if production quantity is feasible for a given date.

        Args:
            production_date: Date of production
            units: Number of units to produce
            allow_overtime: Allow overtime hours on fixed days
            allow_non_fixed_days: Allow production on non-fixed days (weekends/holidays)

        Returns:
            FeasibilityResult indicating feasibility
        """
        if units <= 0:
            return FeasibilityResult(
                is_feasible=True,
                reason="Zero production",
                max_capacity=0,
                required_hours=0,
                available_hours=0
            )

        # Get labor day
        labor_day = self.labor_calendar.get_labor_day(production_date)
        if labor_day is None:
            return FeasibilityResult(
                is_feasible=False,
                reason=f"No labor calendar entry for {production_date}",
                max_capacity=0,
                required_hours=0,
                available_hours=0
            )

        # Check if non-fixed day is allowed
        if not labor_day.is_fixed_day and not allow_non_fixed_days:
            return FeasibilityResult(
                is_feasible=False,
                reason=f"Non-fixed day (weekend/holiday) and non-fixed days not allowed",
                max_capacity=0,
                required_hours=self.manufacturing_site.calculate_labor_hours(units),
                available_hours=0
            )

        # Calculate required hours
        required_hours = self.manufacturing_site.calculate_labor_hours(units)

        # Determine available hours
        if labor_day.is_fixed_day:
            # Fixed day: can use fixed hours + OT (if allowed)
            if allow_overtime:
                # Max is fixed_hours + 2 hours OT for weekdays
                # (from CLAUDE.md: "12 hours fixed labor, max 2 hours overtime")
                max_ot_hours = 2.0
                available_hours = labor_day.fixed_hours + max_ot_hours
            else:
                available_hours = labor_day.fixed_hours

            if required_hours > available_hours:
                return FeasibilityResult(
                    is_feasible=False,
                    reason=f"Requires {required_hours:.1f}h but only {available_hours:.1f}h available",
                    max_capacity=self.manufacturing_site.calculate_production_units(available_hours),
                    required_hours=required_hours,
                    available_hours=available_hours
                )

        else:
            # Non-fixed day: theoretically unlimited hours, but practically limited
            # Let's use a reasonable max (e.g., 12 hours on weekend/holiday)
            practical_max_hours = 12.0
            available_hours = practical_max_hours

            if required_hours > available_hours:
                return FeasibilityResult(
                    is_feasible=False,
                    reason=f"Requires {required_hours:.1f}h but practical limit is {available_hours:.1f}h on non-fixed day",
                    max_capacity=self.manufacturing_site.calculate_production_units(available_hours),
                    required_hours=required_hours,
                    available_hours=available_hours
                )

        # Check against max daily capacity (if defined)
        if self.manufacturing_site.max_daily_capacity is not None:
            if units > self.manufacturing_site.max_daily_capacity:
                return FeasibilityResult(
                    is_feasible=False,
                    reason=f"Exceeds max daily capacity of {self.manufacturing_site.max_daily_capacity} units",
                    max_capacity=self.manufacturing_site.max_daily_capacity,
                    required_hours=required_hours,
                    available_hours=available_hours
                )

        # Feasible
        return FeasibilityResult(
            is_feasible=True,
            reason=f"Within capacity ({required_hours:.1f}h / {available_hours:.1f}h available)",
            max_capacity=self.manufacturing_site.calculate_production_units(available_hours),
            required_hours=required_hours,
            available_hours=available_hours
        )

    def check_packaging_constraints(self, units: float) -> FeasibilityResult:
        """
        Check if units meets packaging constraints (10-unit case increments).

        Args:
            units: Number of units

        Returns:
            FeasibilityResult indicating if valid
        """
        if units <= 0:
            return FeasibilityResult(
                is_feasible=True,
                reason="Zero production",
            )

        # Must be in 10-unit (case) increments
        if units % self.UNITS_PER_CASE != 0:
            return FeasibilityResult(
                is_feasible=False,
                reason=f"Must be in {self.UNITS_PER_CASE}-unit (case) increments. Got {units} units."
            )

        return FeasibilityResult(
            is_feasible=True,
            reason=f"Valid: {units} units = {int(units / self.UNITS_PER_CASE)} cases"
        )

    def analyze_packaging(self, units: float) -> PackagingAnalysis:
        """
        Analyze packaging efficiency for a quantity.

        Args:
            units: Number of units

        Returns:
            PackagingAnalysis with detailed breakdown
        """
        units_int = int(units)

        # Calculate cases
        cases = units_int // self.UNITS_PER_CASE
        is_case_aligned = (units_int % self.UNITS_PER_CASE == 0)

        # Calculate pallets (round up)
        pallets = math.ceil(cases / self.CASES_PER_PALLET)
        is_pallet_aligned = (units_int % self.UNITS_PER_PALLET == 0)

        # Check for partial pallet
        cases_on_last_pallet = cases % self.CASES_PER_PALLET
        partial_pallet_warning = (cases_on_last_pallet > 0)

        # Calculate utilization
        if pallets > 0:
            actual_cases = cases
            max_cases = pallets * self.CASES_PER_PALLET
            pallet_utilization = (actual_cases / max_cases) * 100
        else:
            pallet_utilization = 0

        return PackagingAnalysis(
            units=units_int,
            cases=cases,
            pallets=pallets,
            is_case_aligned=is_case_aligned,
            is_pallet_aligned=is_pallet_aligned,
            partial_pallet_warning=partial_pallet_warning,
            pallet_utilization=pallet_utilization
        )

    def check_weekly_capacity(
        self,
        week_start: date,
        daily_quantities: Dict[date, float]
    ) -> FeasibilityResult:
        """
        Check if weekly production is feasible.

        Args:
            week_start: Start date of week (Monday)
            daily_quantities: Dict mapping date to production quantity

        Returns:
            FeasibilityResult for the week
        """
        total_units = sum(daily_quantities.values())
        total_required_hours = sum(
            self.manufacturing_site.calculate_labor_hours(qty)
            for qty in daily_quantities.values()
        )

        # Calculate available hours for the week
        total_available_hours = 0.0
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            labor_day = self.labor_calendar.get_labor_day(day_date)
            if labor_day:
                if labor_day.is_fixed_day:
                    # Fixed day: fixed hours + 2h OT
                    total_available_hours += labor_day.fixed_hours + 2.0
                else:
                    # Non-fixed: practical limit of 12h
                    total_available_hours += 12.0

        # Check individual days
        infeasible_days = []
        for prod_date, qty in daily_quantities.items():
            result = self.check_daily_capacity(prod_date, qty)
            if not result.is_feasible:
                infeasible_days.append((prod_date, result.reason))

        if infeasible_days:
            reasons = "; ".join([f"{d}: {r}" for d, r in infeasible_days])
            return FeasibilityResult(
                is_feasible=False,
                reason=f"Some days infeasible: {reasons}",
                max_capacity=None,
                required_hours=total_required_hours,
                available_hours=total_available_hours
            )

        if total_required_hours > total_available_hours:
            return FeasibilityResult(
                is_feasible=False,
                reason=f"Weekly hours exceed capacity: {total_required_hours:.1f}h required vs {total_available_hours:.1f}h available",
                max_capacity=None,
                required_hours=total_required_hours,
                available_hours=total_available_hours
            )

        return FeasibilityResult(
            is_feasible=True,
            reason=f"Weekly production feasible: {total_units} units in {total_required_hours:.1f}h / {total_available_hours:.1f}h available",
            max_capacity=self.manufacturing_site.calculate_production_units(total_available_hours),
            required_hours=total_required_hours,
            available_hours=total_available_hours
        )

    def get_maximum_producible(
        self,
        production_date: date,
        allow_overtime: bool = True,
        allow_non_fixed_days: bool = True
    ) -> float:
        """
        Get maximum units that can be produced on a given date.

        Args:
            production_date: Date of production
            allow_overtime: Allow overtime hours
            allow_non_fixed_days: Allow non-fixed days

        Returns:
            Maximum units producible (0 if day not available)
        """
        labor_day = self.labor_calendar.get_labor_day(production_date)
        if labor_day is None:
            return 0.0

        if not labor_day.is_fixed_day and not allow_non_fixed_days:
            return 0.0

        if labor_day.is_fixed_day:
            if allow_overtime:
                max_hours = labor_day.fixed_hours + 2.0
            else:
                max_hours = labor_day.fixed_hours
        else:
            # Non-fixed day practical limit
            max_hours = 12.0

        max_units = self.manufacturing_site.calculate_production_units(max_hours)

        # Apply daily capacity limit if defined
        if self.manufacturing_site.max_daily_capacity is not None:
            max_units = min(max_units, self.manufacturing_site.max_daily_capacity)

        return max_units

    def suggest_production_split(
        self,
        total_units: float,
        preferred_dates: List[date],
        allow_overtime: bool = True
    ) -> Dict[date, float]:
        """
        Suggest how to split production across multiple days.

        Args:
            total_units: Total units to produce
            preferred_dates: Preferred production dates (in order)
            allow_overtime: Allow overtime

        Returns:
            Dict mapping date to suggested production quantity
        """
        remaining = total_units
        allocation: Dict[date, float] = {}

        for prod_date in preferred_dates:
            if remaining <= 0:
                break

            max_on_day = self.get_maximum_producible(
                prod_date,
                allow_overtime=allow_overtime,
                allow_non_fixed_days=False  # Prefer fixed days
            )

            # Allocate up to max, rounded down to case increments
            allocated = min(remaining, max_on_day)
            allocated = math.floor(allocated / self.UNITS_PER_CASE) * self.UNITS_PER_CASE

            if allocated > 0:
                allocation[prod_date] = allocated
                remaining -= allocated

        return allocation
