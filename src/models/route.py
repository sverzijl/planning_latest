"""Route data model for supply chain connections."""

from typing import Optional
from pydantic import BaseModel, Field

from .location import StorageMode


class Route(BaseModel):
    """
    Represents a transport route between two locations.

    A route is a single leg in the supply chain network, connecting
    an origin to a destination with specific transport characteristics.

    Attributes:
        id: Unique identifier for the route
        origin_id: ID of the origin location
        destination_id: ID of the destination location
        transport_mode: Temperature mode during transport (frozen or ambient)
        transit_time_days: Time required for transport in days
        cost: Optional cost per unit for this route
        capacity: Optional maximum capacity per shipment
    """
    id: str = Field(..., description="Unique route identifier")
    origin_id: str = Field(..., description="Origin location ID")
    destination_id: str = Field(..., description="Destination location ID")
    transport_mode: StorageMode = Field(..., description="Transport temperature mode")
    transit_time_days: float = Field(..., description="Transit time in days", ge=0)
    cost: Optional[float] = Field(None, description="Cost per unit", ge=0)
    capacity: Optional[float] = Field(None, description="Maximum capacity per shipment", ge=0)

    class Config:
        """Pydantic configuration."""
        use_enum_values = True

    @property
    def from_location(self) -> str:
        """Alias for origin_id for backward compatibility."""
        return self.origin_id

    @property
    def to_location(self) -> str:
        """Alias for destination_id for backward compatibility."""
        return self.destination_id

    @property
    def transit_days(self) -> float:
        """Alias for transit_time_days for backward compatibility."""
        return self.transit_time_days

    @property
    def cost_per_unit(self) -> Optional[float]:
        """Alias for cost for backward compatibility."""
        return self.cost

    @property
    def intermediate_stops(self) -> list:
        """Empty list for compatibility (Phase 1 doesn't support intermediate stops)."""
        return []

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Route {self.id}: {self.origin_id} → {self.destination_id} "
            f"[{self.transport_mode.value}, {self.transit_time_days}d]"
        )
