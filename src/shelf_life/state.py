"""
Product state definitions and shelf life data structures.

This module defines the possible states of a product (FROZEN, AMBIENT, THAWED)
and data structures for tracking shelf life information.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Optional


class ProductState(Enum):
    """
    Possible states for a product with different shelf life characteristics.

    - FROZEN: Product stored at frozen temperature (120 days shelf life)
    - AMBIENT: Product stored at ambient temperature (17 days shelf life)
    - THAWED: Product that was frozen and then thawed (14 days shelf life from thaw date)
    """
    FROZEN = "frozen"
    AMBIENT = "ambient"
    THAWED = "thawed"

    @property
    def shelf_life_days(self) -> int:
        """Get the shelf life duration for this state."""
        return {
            ProductState.FROZEN: 120,
            ProductState.AMBIENT: 17,
            ProductState.THAWED: 14,
        }[self]

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ProductState.{self.name}"


@dataclass
class ShelfLifeInfo:
    """
    Tracks shelf life information for a product batch.

    Attributes:
        production_date: Date when the product was produced
        current_state: Current state of the product (FROZEN/AMBIENT/THAWED)
        current_age_days: Age of the product in days from production
        thaw_date: Date when frozen product was thawed (None if never thawed)
        days_since_thaw: Days since thawing (None if never thawed or still frozen)
    """
    production_date: date
    current_state: ProductState
    current_age_days: int
    thaw_date: Optional[date] = None
    days_since_thaw: Optional[int] = None

    def __post_init__(self):
        """Validate consistency of thaw-related fields."""
        if self.current_state == ProductState.THAWED:
            if self.thaw_date is None:
                raise ValueError("THAWED state requires thaw_date to be set")
            if self.days_since_thaw is None:
                raise ValueError("THAWED state requires days_since_thaw to be set")

        if self.current_state == ProductState.FROZEN:
            if self.thaw_date is not None:
                raise ValueError("FROZEN state cannot have thaw_date set")
            if self.days_since_thaw is not None:
                raise ValueError("FROZEN state cannot have days_since_thaw set")

    @property
    def expiry_date(self) -> date:
        """
        Calculate the expiry date based on current state.

        - FROZEN/AMBIENT: production_date + state shelf_life_days
        - THAWED: thaw_date + 14 days
        """
        if self.current_state == ProductState.THAWED:
            if self.thaw_date is None:
                raise ValueError("Cannot calculate expiry for THAWED state without thaw_date")
            return self.thaw_date + timedelta(days=ProductState.THAWED.shelf_life_days)
        else:
            return self.production_date + timedelta(days=self.current_state.shelf_life_days)

    @property
    def remaining_shelf_life_days(self) -> int:
        """
        Calculate remaining shelf life in days.

        - FROZEN/AMBIENT: shelf_life_days - current_age_days
        - THAWED: 14 - days_since_thaw
        """
        if self.current_state == ProductState.THAWED:
            if self.days_since_thaw is None:
                raise ValueError("Cannot calculate remaining shelf life for THAWED state without days_since_thaw")
            return ProductState.THAWED.shelf_life_days - self.days_since_thaw
        else:
            return self.current_state.shelf_life_days - self.current_age_days

    @property
    def is_expired(self) -> bool:
        """Check if the product has expired."""
        return self.remaining_shelf_life_days <= 0

    def age_by_days(self, days: int) -> 'ShelfLifeInfo':
        """
        Age the product by a number of days without changing state.

        Args:
            days: Number of days to age the product

        Returns:
            New ShelfLifeInfo with updated age
        """
        return ShelfLifeInfo(
            production_date=self.production_date,
            current_state=self.current_state,
            current_age_days=self.current_age_days + days,
            thaw_date=self.thaw_date,
            days_since_thaw=self.days_since_thaw + days if self.days_since_thaw is not None else None,
        )

    def transition_to(self, new_state: ProductState, transition_date: Optional[date] = None) -> 'ShelfLifeInfo':
        """
        Transition the product to a new state.

        Args:
            new_state: The new state to transition to
            transition_date: Date of transition (required for FROZEN->THAWED transition)

        Returns:
            New ShelfLifeInfo with updated state

        Raises:
            ValueError: If transition is invalid
        """
        # Validate transition
        if self.current_state == new_state:
            return self  # No-op if already in target state

        # FROZEN can transition to AMBIENT or THAWED
        if self.current_state == ProductState.FROZEN:
            if new_state == ProductState.AMBIENT:
                # Simple thaw - continues aging from production date
                return ShelfLifeInfo(
                    production_date=self.production_date,
                    current_state=ProductState.AMBIENT,
                    current_age_days=self.current_age_days,
                    thaw_date=None,
                    days_since_thaw=None,
                )
            elif new_state == ProductState.THAWED:
                # Thaw with shelf life reset - special case for locations like 6130
                if transition_date is None:
                    raise ValueError("transition_date required for FROZEN�THAWED transition")
                return ShelfLifeInfo(
                    production_date=self.production_date,
                    current_state=ProductState.THAWED,
                    current_age_days=self.current_age_days,
                    thaw_date=transition_date,
                    days_since_thaw=0,
                )

        # AMBIENT cannot transition to other states (once thawed to ambient, stays ambient)
        if self.current_state == ProductState.AMBIENT:
            raise ValueError(f"Cannot transition from AMBIENT to {new_state}")

        # THAWED cannot transition to other states
        if self.current_state == ProductState.THAWED:
            raise ValueError(f"Cannot transition from THAWED to {new_state}")

        raise ValueError(f"Invalid transition from {self.current_state} to {new_state}")

    def __str__(self) -> str:
        if self.current_state == ProductState.THAWED:
            return (f"ShelfLifeInfo(state={self.current_state}, "
                   f"age={self.current_age_days}d, "
                   f"since_thaw={self.days_since_thaw}d, "
                   f"remaining={self.remaining_shelf_life_days}d)")
        else:
            return (f"ShelfLifeInfo(state={self.current_state}, "
                   f"age={self.current_age_days}d, "
                   f"remaining={self.remaining_shelf_life_days}d)")
