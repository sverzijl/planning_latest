"""Truck schedule data model for daily departures."""

from enum import Enum
from datetime import time
from typing import Optional, List
from pydantic import BaseModel, Field
import math


class DepartureType(str, Enum):
    """Type of truck departure."""
    MORNING = "morning"
    AFTERNOON = "afternoon"


class DayOfWeek(str, Enum):
    """Day of week for day-specific truck schedules."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class TruckSchedule(BaseModel):
    """
    Represents a scheduled truck departure.

    Supports day-specific routing, multi-stop routes, and packaging constraints.

    Attributes:
        id: Unique truck schedule identifier
        truck_name: Human-readable truck name
        departure_type: Morning or afternoon departure
        departure_time: Time of departure (e.g., "08:00", "14:00")
        destination_id: Fixed destination location ID (None if flexible routing)
        capacity: Maximum capacity in units
        cost_fixed: Fixed cost per departure (regardless of load)
        cost_per_unit: Variable cost per unit transported
        day_of_week: Specific day this schedule applies (None for daily)
        intermediate_stops: List of location IDs for multi-stop routes (e.g., [Lineage, 6125])
        pallet_capacity: Maximum number of pallets truck can carry (default: 44)
        units_per_pallet: Units per pallet (default: 320 = 32 cases × 10 units)
        units_per_case: Units per case (default: 10)
    """
    id: str = Field(..., description="Unique truck schedule identifier")
    truck_name: str = Field(..., description="Truck name")
    departure_type: DepartureType = Field(..., description="Morning or afternoon")
    departure_time: time = Field(..., description="Departure time")
    destination_id: Optional[str] = Field(
        None,
        description="Fixed destination location ID (None for flexible routing)"
    )
    capacity: float = Field(..., description="Truck capacity in units", gt=0)
    cost_fixed: float = Field(
        default=0.0,
        description="Fixed cost per departure",
        ge=0
    )
    cost_per_unit: float = Field(
        default=0.0,
        description="Variable cost per unit",
        ge=0
    )
    day_of_week: Optional[DayOfWeek] = Field(
        None,
        description="Specific day of week (None for daily schedule)"
    )
    intermediate_stops: List[str] = Field(
        default_factory=list,
        description="Intermediate stop location IDs (e.g., Lineage before final destination)"
    )
    pallet_capacity: int = Field(
        default=44,
        description="Maximum pallets truck can carry",
        gt=0
    )
    units_per_pallet: int = Field(
        default=320,
        description="Units per pallet (32 cases × 10 units)",
        gt=0
    )
    units_per_case: int = Field(
        default=10,
        description="Units per case (minimum shipping quantity)",
        gt=0
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True

    def is_fixed_route(self) -> bool:
        """
        Check if truck has a fixed destination.

        Returns:
            True if destination_id is specified (fixed route)
        """
        return self.destination_id is not None

    def is_morning(self) -> bool:
        """Check if this is a morning departure."""
        return self.departure_type == DepartureType.MORNING

    def is_afternoon(self) -> bool:
        """Check if this is an afternoon departure."""
        return self.departure_type == DepartureType.AFTERNOON

    def calculate_cost(self, units: float) -> float:
        """
        Calculate total cost for transporting units.

        Args:
            units: Number of units to transport

        Returns:
            Total cost (fixed + variable)
        """
        if units < 0:
            raise ValueError("Units must be non-negative")
        if units > self.capacity:
            raise ValueError(f"Units {units} exceeds truck capacity {self.capacity}")
        return self.cost_fixed + (self.cost_per_unit * units)

    def calculate_required_pallets(self, units: float) -> int:
        """
        Calculate number of pallets required for given units.

        Partial pallets occupy full pallet space, so this uses ceiling division.

        Args:
            units: Number of units to transport

        Returns:
            Number of pallets required (rounded up)

        Raises:
            ValueError: If units exceeds truck pallet capacity
        """
        if units <= 0:
            return 0

        pallets_needed = math.ceil(units / self.units_per_pallet)

        if pallets_needed > self.pallet_capacity:
            raise ValueError(
                f"Units {units} requires {pallets_needed} pallets, "
                f"exceeds truck capacity {self.pallet_capacity} pallets"
            )

        return pallets_needed

    def calculate_pallet_efficiency(self, units: float) -> float:
        """
        Calculate pallet utilization efficiency as percentage.

        Args:
            units: Number of units to transport

        Returns:
            Efficiency as decimal (0.0 to 1.0)
            Example: 14,080 units = 44 pallets = 100% efficiency
                     13,600 units = 43 pallets = 97.7% efficiency
        """
        if units <= 0:
            return 0.0

        pallets_used = self.calculate_required_pallets(units)
        return pallets_used / self.pallet_capacity

    def validate_case_quantity(self, units: float) -> bool:
        """
        Check if quantity is a valid multiple of case size.

        No partial cases are allowed.

        Args:
            units: Number of units to validate

        Returns:
            True if units is exact multiple of units_per_case

        Example:
            validate_case_quantity(100) -> True (10 cases)
            validate_case_quantity(105) -> False (10.5 cases - invalid)
        """
        if units <= 0:
            return units == 0

        return (units % self.units_per_case) == 0

    def round_to_case_quantity(self, units: float, round_up: bool = True) -> int:
        """
        Round quantity to nearest valid case quantity.

        Args:
            units: Number of units to round
            round_up: If True, round up to next case; if False, round down

        Returns:
            Rounded quantity (multiple of units_per_case)

        Example:
            round_to_case_quantity(105, True) -> 110 (11 cases)
            round_to_case_quantity(105, False) -> 100 (10 cases)
        """
        if units <= 0:
            return 0

        if round_up:
            return math.ceil(units / self.units_per_case) * self.units_per_case
        else:
            return math.floor(units / self.units_per_case) * self.units_per_case

    def has_intermediate_stops(self) -> bool:
        """
        Check if truck has intermediate stops before final destination.

        Returns:
            True if intermediate_stops list is not empty
        """
        return len(self.intermediate_stops) > 0

    def is_day_specific(self) -> bool:
        """
        Check if truck schedule is day-specific.

        Returns:
            True if day_of_week is set (not None)
        """
        return self.day_of_week is not None

    def __str__(self) -> str:
        """String representation."""
        route_info = f"to {self.destination_id}" if self.destination_id else "flexible route"
        day_info = f" ({self.day_of_week.value})" if self.day_of_week else ""
        stops_info = f" via {', '.join(self.intermediate_stops)}" if self.intermediate_stops else ""
        return (
            f"{self.truck_name} - {self.departure_type.value}{day_info} @ {self.departure_time.strftime('%H:%M')} "
            f"{route_info}{stops_info} [{self.pallet_capacity} pallets = {self.capacity:.0f} units]"
        )
