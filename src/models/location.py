"""Location data model for the supply chain network."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class LocationType(str, Enum):
    """Type of location in the supply chain."""
    MANUFACTURING = "manufacturing"
    STORAGE = "storage"
    BREADROOM = "breadroom"


class StorageMode(str, Enum):
    """Storage temperature mode."""
    AMBIENT = "ambient"
    FROZEN = "frozen"
    BOTH = "both"  # Supports both modes


class Location(BaseModel):
    """
    Represents a location in the supply chain network.

    Attributes:
        id: Unique identifier for the location
        name: Human-readable name
        type: Type of location (manufacturing, storage, or breadroom)
        storage_mode: Temperature mode supported (ambient, frozen, or both)
        capacity: Optional storage capacity in units
        latitude: Optional GPS latitude for visualization
        longitude: Optional GPS longitude for visualization
    """
    id: str = Field(..., description="Unique location identifier")
    name: str = Field(..., description="Location name")
    type: LocationType = Field(..., description="Location type")
    storage_mode: StorageMode = Field(..., description="Supported storage mode")
    capacity: Optional[float] = Field(None, description="Storage capacity in units", ge=0)
    latitude: Optional[float] = Field(None, description="GPS latitude", ge=-90, le=90)
    longitude: Optional[float] = Field(None, description="GPS longitude", ge=-180, le=180)

    class Config:
        """Pydantic configuration."""
        use_enum_values = True

    def can_store_mode(self, mode: StorageMode) -> bool:
        """
        Check if location can store products in the given mode.

        Args:
            mode: Storage mode to check

        Returns:
            True if location supports the storage mode
        """
        if self.storage_mode == StorageMode.BOTH:
            return True
        return self.storage_mode == mode

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} ({self.id}) - {self.type.value} [{self.storage_mode.value}]"
