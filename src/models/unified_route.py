"""Unified route model - connects nodes in the supply chain network.

Routes in the unified model are simpler than legacy routes:
- Connect any two nodes
- Have transit time (0 = instant, 0.5 = half day, 1.0 = one day, etc.)
- Have transport mode (frozen or ambient)
- No special handling needed - state transitions happen at destination nodes
"""

from enum import Enum
from pydantic import BaseModel, Field


class TransportMode(str, Enum):
    """Transport temperature mode."""
    FROZEN = "frozen"
    AMBIENT = "ambient"


class UnifiedRoute(BaseModel):
    """Route connecting two nodes in the supply chain.

    Attributes:
        id: Unique route identifier
        origin_node_id: Origin node ID
        destination_node_id: Destination node ID
        transit_days: Transit time in days (0 = instant, 0.5 = half day, 1.0 = one day)
        transport_mode: Temperature mode during transport
        cost_per_unit: Variable cost per unit shipped
    """

    id: str = Field(..., description="Unique route identifier")
    origin_node_id: str = Field(..., description="Origin node ID")
    destination_node_id: str = Field(..., description="Destination node ID")
    transit_days: float = Field(..., description="Transit time in days", ge=0)
    transport_mode: TransportMode = Field(
        default=TransportMode.AMBIENT,
        description="Temperature mode during transport"
    )
    cost_per_unit: float = Field(
        default=0.0,
        description="Variable cost per unit shipped",
        ge=0
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True

    def is_frozen_transport(self) -> bool:
        """Check if route uses frozen transport."""
        return self.transport_mode == TransportMode.FROZEN

    def is_ambient_transport(self) -> bool:
        """Check if route uses ambient transport."""
        return self.transport_mode == TransportMode.AMBIENT

    def is_instant_transfer(self) -> bool:
        """Check if route is instant (zero transit time)."""
        return self.transit_days == 0.0

    def __str__(self) -> str:
        """String representation."""
        mode_icon = "❄️" if self.is_frozen_transport() else "🌤️"
        transit_str = "instant" if self.is_instant_transfer() else f"{self.transit_days}d"

        return (
            f"{self.id}: {self.origin_node_id} → {self.destination_node_id} "
            f"({mode_icon} {self.transport_mode.value}, {transit_str}, "
            f"${self.cost_per_unit:.2f}/unit)"
        )
