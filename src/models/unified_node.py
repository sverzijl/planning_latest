"""Unified node model - replaces separate Location/ManufacturingSite/Storage types.

This module provides a unified node representation where all locations are nodes
with capability flags. This eliminates the need for virtual locations (6122_Storage)
and enables cleaner, more generalizable constraint logic.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class StorageMode(str, Enum):
    """Storage temperature mode for a node."""
    FROZEN = "frozen"
    AMBIENT = "ambient"
    BOTH = "both"  # Supports both frozen and ambient (can freeze/thaw)


class NodeCapabilities(BaseModel):
    """Capabilities that a node can have.

    All capabilities are optional - a node can have any combination.

    Examples:
    - Manufacturing site: can_manufacture=True, can_store=True, requires_truck_schedules=True
    - Hub with demand: has_demand=True, can_store=True
    - Intermediate storage: can_store=True (only)
    - Breadroom: has_demand=True, can_store=True
    """

    # Manufacturing capability
    can_manufacture: bool = Field(
        default=False,
        description="Can produce product"
    )
    production_rate_per_hour: Optional[float] = Field(
        default=None,
        description="Units per hour production rate (required if can_manufacture=True)"
    )

    # Storage capability
    can_store: bool = Field(
        default=True,
        description="Can hold inventory"
    )
    storage_mode: StorageMode = Field(
        default=StorageMode.AMBIENT,
        description="Storage temperature capability"
    )
    storage_capacity: Optional[float] = Field(
        default=None,
        description="Maximum storage capacity in units (None = unlimited)"
    )

    # Demand capability
    has_demand: bool = Field(
        default=False,
        description="Is a demand destination (receives customer orders)"
    )

    # Truck scheduling requirement
    requires_truck_schedules: bool = Field(
        default=False,
        description="Outbound shipments must use scheduled trucks"
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class UnifiedNode(BaseModel):
    """Unified node representation.

    Replaces the separate Location, ManufacturingSite, and virtual location concepts.
    All locations in the network are nodes with capability flags.

    Key Simplifications:
    - No more manufacturing vs storage vs breadroom distinction
    - No virtual 6122_Storage location needed
    - Capabilities are explicit and composable
    - Easier to extend with new capabilities

    Attributes:
        id: Unique node identifier
        name: Human-readable node name
        capabilities: NodeCapabilities defining what this node can do
        latitude: GPS latitude for visualization (optional)
        longitude: GPS longitude for visualization (optional)
    """

    id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Node name")
    capabilities: NodeCapabilities = Field(..., description="Node capabilities")
    latitude: Optional[float] = Field(None, description="GPS latitude", ge=-90, le=90)
    longitude: Optional[float] = Field(None, description="GPS longitude", ge=-180, le=180)

    class Config:
        """Pydantic configuration."""
        use_enum_values = True

    def can_produce(self) -> bool:
        """Check if node can manufacture product."""
        return self.capabilities.can_manufacture

    def has_demand_capability(self) -> bool:
        """Check if node is a demand destination."""
        return self.capabilities.has_demand

    def supports_frozen_storage(self) -> bool:
        """Check if node can store frozen product."""
        return self.capabilities.storage_mode in [StorageMode.FROZEN, StorageMode.BOTH]

    def supports_ambient_storage(self) -> bool:
        """Check if node can store ambient product."""
        return self.capabilities.storage_mode in [StorageMode.AMBIENT, StorageMode.BOTH]

    def can_freeze_thaw(self) -> bool:
        """Check if node supports both frozen and ambient (can perform state transitions)."""
        return self.capabilities.storage_mode == StorageMode.BOTH

    def requires_trucks(self) -> bool:
        """Check if outbound shipments from this node require truck schedules."""
        return self.capabilities.requires_truck_schedules

    def get_production_state(self) -> str:
        """Get the state of product when manufactured at this node.

        Returns:
            'frozen' if node is frozen-only, 'ambient' otherwise
        """
        if self.capabilities.storage_mode == StorageMode.FROZEN:
            return 'frozen'
        else:
            return 'ambient'  # Default: ambient production

    def __str__(self) -> str:
        """String representation."""
        caps = []
        if self.can_produce():
            caps.append(f"MFG({self.capabilities.production_rate_per_hour:.0f}u/h)")
        if self.has_demand_capability():
            caps.append("DEMAND")
        if self.can_freeze_thaw():
            caps.append("FREEZE/THAW")
        elif self.supports_frozen_storage():
            caps.append("FROZEN")
        else:
            caps.append("AMBIENT")
        if self.requires_trucks():
            caps.append("TRUCKS")

        caps_str = ", ".join(caps) if caps else "STORAGE"

        return f"{self.name} ({self.id}) [{caps_str}]"
