"""Cost structure data model for comprehensive cost tracking."""

from typing import Optional
from pydantic import BaseModel, Field


class CostStructure(BaseModel):
    """
    Comprehensive cost structure for the supply chain.

    Captures all cost components used in the optimization objective:
    minimize total cost to serve = labor + production + transport + storage + waste

    Attributes:
        # Production costs (typically in $/unit)
        production_cost_per_unit: Base production cost per unit
        setup_cost: Cost per production run/setup

        # Labor costs (typically in $/hour)
        # Note: Labor rates may vary by day; these are defaults
        default_regular_rate: Default regular labor rate
        default_overtime_rate: Default overtime labor rate
        default_non_fixed_rate: Default non-fixed day labor rate

        # Transport costs (typically in $/unit or $/unit/km)
        transport_cost_frozen_per_unit: Cost per unit for frozen transport
        transport_cost_ambient_per_unit: Cost per unit for ambient transport
        truck_fixed_cost: Fixed cost per truck departure

        # Storage costs (typically in $/unit/day)
        storage_cost_frozen_per_unit_day: Holding cost for frozen storage per unit per day
        storage_cost_ambient_per_unit_day: Holding cost for ambient storage per unit per day

        # Waste/penalty costs
        waste_cost_multiplier: Multiplier on production cost for wasted units (e.g., 1.5 = 150% of production cost)
        shortage_penalty_per_unit: Penalty for unmet demand per unit
    """

    # Production costs
    production_cost_per_unit: float = Field(
        default=0.0,
        description="Base production cost per unit ($/unit)",
        ge=0
    )
    setup_cost: float = Field(
        default=0.0,
        description="Cost per production setup ($/run)",
        ge=0
    )

    # Default labor costs
    default_regular_rate: float = Field(
        default=20.0,
        description="Default regular labor rate ($/hour)",
        ge=0
    )
    default_overtime_rate: float = Field(
        default=30.0,
        description="Default overtime labor rate ($/hour)",
        ge=0
    )
    default_non_fixed_rate: float = Field(
        default=40.0,
        description="Default non-fixed day labor rate ($/hour)",
        ge=0
    )

    # Transport costs
    transport_cost_frozen_per_unit: float = Field(
        default=0.5,
        description="Frozen transport cost per unit ($/unit)",
        ge=0
    )
    transport_cost_ambient_per_unit: float = Field(
        default=0.3,
        description="Ambient transport cost per unit ($/unit)",
        ge=0
    )
    truck_fixed_cost: float = Field(
        default=100.0,
        description="Fixed cost per truck departure ($)",
        ge=0
    )

    # Storage costs (unit-based - legacy)
    storage_cost_frozen_per_unit_day: float = Field(
        default=0.05,
        description="Frozen storage cost per unit per day ($/unit/day)",
        ge=0
    )
    storage_cost_ambient_per_unit_day: float = Field(
        default=0.02,
        description="Ambient storage cost per unit per day ($/unit/day)",
        ge=0
    )

    # Storage costs (pallet-based - new preferred method)
    storage_cost_fixed_per_pallet: Optional[float] = Field(
        default=None,
        description="Fixed cost per pallet when entering storage ($/pallet)",
        ge=0
    )
    storage_cost_per_pallet_day_frozen: Optional[float] = Field(
        default=None,
        description="Daily holding cost per pallet in frozen storage ($/pallet/day)",
        ge=0
    )
    storage_cost_per_pallet_day_ambient: Optional[float] = Field(
        default=None,
        description="Daily holding cost per pallet in ambient storage ($/pallet/day)",
        ge=0
    )

    # Waste and penalty costs
    waste_cost_multiplier: float = Field(
        default=1.5,
        description="Multiplier on production cost for waste (e.g., 1.5 = 150%)",
        ge=0
    )
    shortage_penalty_per_unit: float = Field(
        default=10.0,
        description="Penalty for unmet demand per unit ($/unit)",
        ge=0
    )

    def calculate_waste_cost(self, units: float, unit_production_cost: Optional[float] = None) -> float:
        """
        Calculate cost of wasted units.

        Args:
            units: Number of wasted units
            unit_production_cost: Production cost per unit (uses default if None)

        Returns:
            Total waste cost
        """
        cost_per_unit = unit_production_cost or self.production_cost_per_unit
        return units * cost_per_unit * self.waste_cost_multiplier

    def calculate_storage_cost(
        self,
        units: float,
        days: float,
        is_frozen: bool
    ) -> float:
        """
        Calculate storage/holding cost.

        Args:
            units: Number of units in storage
            days: Number of days in storage
            is_frozen: True for frozen storage, False for ambient

        Returns:
            Total storage cost
        """
        rate = (
            self.storage_cost_frozen_per_unit_day
            if is_frozen
            else self.storage_cost_ambient_per_unit_day
        )
        return units * days * rate

    def calculate_transport_cost(
        self,
        units: float,
        is_frozen: bool,
        include_truck_fixed: bool = False
    ) -> float:
        """
        Calculate transport cost.

        Args:
            units: Number of units transported
            is_frozen: True for frozen transport, False for ambient
            include_truck_fixed: Whether to include truck fixed cost

        Returns:
            Total transport cost
        """
        rate = (
            self.transport_cost_frozen_per_unit
            if is_frozen
            else self.transport_cost_ambient_per_unit
        )
        variable_cost = units * rate
        fixed_cost = self.truck_fixed_cost if include_truck_fixed else 0.0
        return variable_cost + fixed_cost

    def calculate_shortage_cost(self, shortage_units: float) -> float:
        """
        Calculate shortage penalty cost.

        Args:
            shortage_units: Number of units short

        Returns:
            Total shortage penalty
        """
        return shortage_units * self.shortage_penalty_per_unit

    def __str__(self) -> str:
        """String representation."""
        return (
            f"CostStructure: Prod=${self.production_cost_per_unit}/unit, "
            f"Labor=${self.default_regular_rate}/h (reg), "
            f"Waste={self.waste_cost_multiplier}x prod cost"
        )
