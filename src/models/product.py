"""Product data model with shelf life rules."""

from enum import Enum
from pydantic import BaseModel, Field


class ProductState(str, Enum):
    """Current state of the product affecting shelf life."""
    AMBIENT = "ambient"
    FROZEN = "frozen"
    THAWED = "thawed"  # Previously frozen, now ambient


class Product(BaseModel):
    """
    Represents a product with shelf life characteristics.

    Business Rules:
    - Ambient shelf life: 17 days
    - Frozen shelf life: 120 days
    - Thawed shelf life: 14 days (reset after thawing)
    - Breadrooms discard stock with <7 days remaining

    Attributes:
        id: Unique product identifier
        name: Product name
        sku: Stock keeping unit code
        ambient_shelf_life_days: Shelf life when stored ambient (default: 17)
        frozen_shelf_life_days: Shelf life when stored frozen (default: 120)
        thawed_shelf_life_days: Shelf life after thawing (default: 14)
        min_acceptable_shelf_life_days: Minimum days before discard (default: 7)
    """
    id: str = Field(..., description="Unique product identifier")
    name: str = Field(..., description="Product name")
    sku: str = Field(..., description="SKU code")
    ambient_shelf_life_days: float = Field(
        default=17.0,
        description="Shelf life when stored ambient",
        ge=0
    )
    frozen_shelf_life_days: float = Field(
        default=120.0,
        description="Shelf life when stored frozen",
        ge=0
    )
    thawed_shelf_life_days: float = Field(
        default=14.0,
        description="Shelf life after thawing",
        ge=0
    )
    min_acceptable_shelf_life_days: float = Field(
        default=7.0,
        description="Minimum acceptable shelf life for breadrooms",
        ge=0
    )

    def get_shelf_life(self, state: ProductState) -> float:
        """
        Get shelf life in days for a given product state.

        Args:
            state: Current product state

        Returns:
            Shelf life in days
        """
        if state == ProductState.AMBIENT:
            return self.ambient_shelf_life_days
        elif state == ProductState.FROZEN:
            return self.frozen_shelf_life_days
        else:  # THAWED
            return self.thawed_shelf_life_days

    def is_acceptable(self, remaining_shelf_life_days: float) -> bool:
        """
        Check if product is still acceptable for breadrooms.

        Args:
            remaining_shelf_life_days: Days of shelf life remaining

        Returns:
            True if acceptable (>= minimum threshold)
        """
        return remaining_shelf_life_days >= self.min_acceptable_shelf_life_days

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} ({self.sku})"
