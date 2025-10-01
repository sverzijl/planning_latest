"""Manufacturing site data model with production capabilities."""

from typing import Optional
from pydantic import BaseModel, Field

from .location import Location, LocationType, StorageMode


class ManufacturingSite(Location):
    """
    Manufacturing site with production capabilities.

    Extends Location with production-specific attributes including
    production capacity, efficiency, and default timing parameters.

    Attributes:
        production_rate: Units produced per labor hour
        max_daily_capacity: Maximum units that can be produced per day
        production_cost_per_unit: Base production cost per unit
        setup_time_hours: Hours required for production setup (if applicable)
        morning_truck_cutoff_hour: Hour by which morning truck production must complete (default: 24, i.e., end of previous day)
        afternoon_truck_cutoff_hour: Hour by which afternoon truck production must complete (default: 12, i.e., noon)
    """

    production_rate: float = Field(
        ...,
        description="Units produced per labor hour",
        gt=0
    )
    max_daily_capacity: Optional[float] = Field(
        None,
        description="Maximum production capacity per day (units)",
        gt=0
    )
    production_cost_per_unit: float = Field(
        default=0.0,
        description="Base production cost per unit",
        ge=0
    )
    setup_time_hours: float = Field(
        default=0.0,
        description="Production setup time in hours",
        ge=0
    )
    morning_truck_cutoff_hour: int = Field(
        default=24,
        description="Hour by which morning truck production must complete (0-24)",
        ge=0,
        le=24
    )
    afternoon_truck_cutoff_hour: int = Field(
        default=12,
        description="Hour by which afternoon truck production must complete (0-24)",
        ge=0,
        le=24
    )

    def __init__(self, **data):
        """Initialize manufacturing site with type validation."""
        if 'type' not in data:
            data['type'] = LocationType.MANUFACTURING
        elif data['type'] != LocationType.MANUFACTURING:
            raise ValueError(f"ManufacturingSite must have type MANUFACTURING, got {data['type']}")
        super().__init__(**data)

    def calculate_labor_hours(self, units: float) -> float:
        """
        Calculate labor hours required to produce given units.

        Args:
            units: Number of units to produce

        Returns:
            Required labor hours (including setup if applicable)
        """
        if units <= 0:
            return 0.0
        return self.setup_time_hours + (units / self.production_rate)

    def calculate_production_units(self, labor_hours: float) -> float:
        """
        Calculate units that can be produced with given labor hours.

        Args:
            labor_hours: Available labor hours

        Returns:
            Number of units that can be produced
        """
        if labor_hours <= self.setup_time_hours:
            return 0.0
        return (labor_hours - self.setup_time_hours) * self.production_rate

    def can_produce_quantity(self, units: float) -> bool:
        """
        Check if quantity can be produced within daily capacity.

        Args:
            units: Number of units to check

        Returns:
            True if quantity is within daily capacity (or if no capacity limit)
        """
        if self.max_daily_capacity is None:
            return True
        return units <= self.max_daily_capacity

    def __str__(self) -> str:
        """String representation."""
        return (
            f"{self.name} ({self.id}) - Manufacturing "
            f"[Rate: {self.production_rate} units/hr, "
            f"Max: {self.max_daily_capacity or 'unlimited'} units/day]"
        )
