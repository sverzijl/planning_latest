"""Unified truck schedule model - works for ANY route (not just manufacturing).

Key improvement: Truck schedules can now constrain routes from any origin node,
not just manufacturing. This enables hub-to-spoke truck scheduling.
"""

from enum import Enum
from typing import Optional, List
from datetime import time, date as Date
from pydantic import BaseModel, Field
import math


class DayOfWeek(str, Enum):
    """Day of week for day-specific truck schedules."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class DepartureType(str, Enum):
    """Type of truck departure."""
    MORNING = "morning"
    AFTERNOON = "afternoon"


class UnifiedTruckSchedule(BaseModel):
    """Generalized truck schedule for ANY route.

    Key differences from legacy TruckSchedule:
    - Explicit origin_node_id (not implicit manufacturing)
    - Works for hub-to-spoke routes (e.g., 6125 → 6123)
    - Cleaner integration with unified node model

    Attributes:
        id: Unique truck schedule identifier
        origin_node_id: Origin node (can be manufacturing, hub, or any node)
        destination_node_id: Destination node
        departure_type: Morning or afternoon departure
        departure_time: Time of departure
        day_of_week: Specific day (None = runs every day)
        capacity: Maximum capacity in units
        cost_fixed: Fixed cost per departure
        cost_per_unit: Variable cost per unit
        intermediate_stops: List of intermediate stop node IDs
        pallet_capacity: Maximum pallets
        units_per_pallet: Units per pallet (default 320)
        units_per_case: Units per case (default 10)
    """

    id: str = Field(..., description="Unique truck schedule identifier")
    origin_node_id: str = Field(..., description="Origin node ID")
    destination_node_id: str = Field(..., description="Destination node ID")
    departure_type: DepartureType = Field(..., description="Morning or afternoon")
    departure_time: time = Field(..., description="Departure time")
    day_of_week: Optional[DayOfWeek] = Field(
        None,
        description="Specific day of week (None = runs every day)"
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
    intermediate_stops: List[str] = Field(
        default_factory=list,
        description="Intermediate stop node IDs"
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

    def is_day_specific(self) -> bool:
        """Check if truck schedule is day-specific."""
        return self.day_of_week is not None

    def applies_on_date(self, check_date: Date) -> bool:
        """Check if this truck schedule applies on a given date.

        Args:
            check_date: Date to check

        Returns:
            True if truck runs on this date
        """
        if not self.day_of_week:
            # Daily schedule - applies every day
            return True

        # Map day of week enum to Python's weekday() values (0=Monday, 6=Sunday)
        day_map = {
            DayOfWeek.MONDAY: 0,
            DayOfWeek.TUESDAY: 1,
            DayOfWeek.WEDNESDAY: 2,
            DayOfWeek.THURSDAY: 3,
            DayOfWeek.FRIDAY: 4,
            DayOfWeek.SATURDAY: 5,
            DayOfWeek.SUNDAY: 6,
        }

        return check_date.weekday() == day_map[self.day_of_week]

    def is_morning(self) -> bool:
        """Check if this is a morning departure."""
        return self.departure_type == DepartureType.MORNING

    def is_afternoon(self) -> bool:
        """Check if this is an afternoon departure."""
        return self.departure_type == DepartureType.AFTERNOON

    def has_intermediate_stops(self) -> bool:
        """Check if truck has intermediate stops."""
        return len(self.intermediate_stops) > 0

    def calculate_required_pallets(self, units: float) -> int:
        """Calculate number of pallets required for given units.

        Partial pallets occupy full pallet space (ceiling division).

        Args:
            units: Number of units

        Returns:
            Number of pallets required
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

    def __str__(self) -> str:
        """String representation."""
        day_info = f" ({self.day_of_week.value})" if self.day_of_week else " (daily)"
        stops_info = f" via {', '.join(self.intermediate_stops)}" if self.intermediate_stops else ""

        return (
            f"{self.id}: {self.origin_node_id} → {self.destination_node_id}{stops_info} "
            f"- {self.departure_type.value}{day_info} @ {self.departure_time.strftime('%H:%M')} "
            f"[{self.pallet_capacity}pal = {self.capacity:.0f}u]"
        )
