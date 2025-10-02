"""
Shelf life business rules and validation.

This module contains the business rules for shelf life management,
including expiration checks, breadroom acceptance criteria, and
state transition rules.
"""

from datetime import date, timedelta
from typing import List, Optional
from dataclasses import dataclass

from .state import ProductState, ShelfLifeInfo


@dataclass
class ShelfLifeValidationResult:
    """
    Result of shelf life validation.

    Attributes:
        is_valid: Whether the product passes validation
        reason: Explanation of validation result
        remaining_days: Remaining shelf life days (if applicable)
    """
    is_valid: bool
    reason: str
    remaining_days: Optional[int] = None

    def __str__(self) -> str:
        if self.is_valid:
            return f"Valid ({self.reason}, {self.remaining_days}d remaining)"
        else:
            return f"Invalid ({self.reason})"


class ShelfLifeRules:
    """
    Business rules for shelf life management.

    This class encapsulates all shelf life-related business rules including:
    - Breadroom acceptance criteria (minimum 7 days remaining)
    - Expiration validation
    - State transition validation
    - Transport mode compatibility
    """

    # Business rule: Breadrooms discard stock with less than 7 days remaining
    MIN_BREADROOM_SHELF_LIFE_DAYS = 7

    @staticmethod
    def validate_breadroom_acceptance(shelf_life_info: ShelfLifeInfo) -> ShelfLifeValidationResult:
        """
        Check if product meets breadroom acceptance criteria.

        Breadrooms discard stock with less than 7 days remaining shelf life.

        Args:
            shelf_life_info: Shelf life information for the product

        Returns:
            ShelfLifeValidationResult indicating acceptance or rejection
        """
        remaining = shelf_life_info.remaining_shelf_life_days

        if remaining < 0:
            return ShelfLifeValidationResult(
                is_valid=False,
                reason="Product expired",
                remaining_days=remaining
            )

        if remaining < ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS:
            return ShelfLifeValidationResult(
                is_valid=False,
                reason=f"Insufficient shelf life (minimum {ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS} days required)",
                remaining_days=remaining
            )

        return ShelfLifeValidationResult(
            is_valid=True,
            reason="Meets breadroom acceptance criteria",
            remaining_days=remaining
        )

    @staticmethod
    def validate_expiration(shelf_life_info: ShelfLifeInfo, check_date: date) -> ShelfLifeValidationResult:
        """
        Check if product is expired on a given date.

        Args:
            shelf_life_info: Shelf life information for the product
            check_date: Date to check expiration against

        Returns:
            ShelfLifeValidationResult indicating if product is valid
        """
        expiry_date = shelf_life_info.expiry_date

        if check_date > expiry_date:
            days_expired = (check_date - expiry_date).days
            return ShelfLifeValidationResult(
                is_valid=False,
                reason=f"Product expired {days_expired} day(s) ago",
                remaining_days=-days_expired
            )

        remaining = (expiry_date - check_date).days
        return ShelfLifeValidationResult(
            is_valid=True,
            reason="Product not expired",
            remaining_days=remaining
        )

    @staticmethod
    def can_transition(from_state: ProductState, to_state: ProductState) -> bool:
        """
        Check if a state transition is allowed.

        Valid transitions:
        - FROZEN -> AMBIENT (simple thaw)
        - FROZEN -> THAWED (thaw with shelf life reset)
        - No transitions from AMBIENT or THAWED

        Args:
            from_state: Current state
            to_state: Desired state

        Returns:
            True if transition is allowed, False otherwise
        """
        if from_state == to_state:
            return True

        # FROZEN can transition to AMBIENT or THAWED
        if from_state == ProductState.FROZEN:
            return to_state in (ProductState.AMBIENT, ProductState.THAWED)

        # AMBIENT and THAWED cannot transition
        return False

    @staticmethod
    def is_compatible_with_transport_mode(
        product_state: ProductState,
        transport_mode: str
    ) -> bool:
        """
        Check if product state is compatible with transport mode.

        Args:
            product_state: Current product state
            transport_mode: Transport mode ('frozen' or 'ambient')

        Returns:
            True if compatible, False otherwise
        """
        transport_mode_lower = transport_mode.lower()

        # Frozen products require frozen transport
        if product_state == ProductState.FROZEN:
            return transport_mode_lower == "frozen"

        # Ambient and thawed products require ambient transport
        if product_state in (ProductState.AMBIENT, ProductState.THAWED):
            return transport_mode_lower == "ambient"

        return False

    @staticmethod
    def calculate_required_production_date(
        delivery_date: date,
        transit_days: int,
        state: ProductState = ProductState.AMBIENT,
        include_safety_margin: bool = True
    ) -> date:
        """
        Calculate when production must occur to meet delivery date with valid shelf life.

        Args:
            delivery_date: Target delivery date
            transit_days: Number of days in transit
            state: Expected product state at delivery
            include_safety_margin: If True, ensures MIN_BREADROOM_SHELF_LIFE_DAYS at delivery

        Returns:
            Latest production date to meet requirements
        """
        # Calculate arrival date (delivery_date - 1 typically, but using delivery_date for simplicity)
        arrival_date = delivery_date

        # If safety margin required, product must have 7+ days at arrival
        if include_safety_margin:
            # For ambient: need 17 days total, minus (transit_days + 7 for breadroom)
            # So max age at arrival = 17 - 7 = 10 days
            max_age_at_arrival = state.shelf_life_days - ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS
        else:
            # Product just needs to not be expired (17 days total for ambient)
            max_age_at_arrival = state.shelf_life_days

        # Age at arrival = production to arrival
        # production_date + transit_days = arrival_date
        # production_date = arrival_date - transit_days
        # But we also need: age_at_arrival <= max_age_at_arrival
        # age_at_arrival = (arrival_date - production_date).days = transit_days
        # So: transit_days <= max_age_at_arrival

        # Latest production date = arrival_date - transit_days
        # But we need to ensure we don't exceed max age
        max_transit_with_safety = min(transit_days, max_age_at_arrival)

        production_date = arrival_date - timedelta(days=transit_days)

        return production_date

    @staticmethod
    def get_state_description(state: ProductState) -> str:
        """Get a human-readable description of a product state."""
        descriptions = {
            ProductState.FROZEN: "Frozen storage (120 days shelf life)",
            ProductState.AMBIENT: "Ambient storage (17 days shelf life)",
            ProductState.THAWED: "Thawed from frozen (14 days shelf life from thaw date)",
        }
        return descriptions.get(state, "Unknown state")

    @staticmethod
    def suggest_best_state_for_transit(transit_days: int) -> ProductState:
        """
        Suggest the best product state for a given transit time.

        Args:
            transit_days: Number of days in transit

        Returns:
            Recommended product state
        """
        # If transit is very long, use frozen
        if transit_days > ProductState.AMBIENT.shelf_life_days:
            return ProductState.FROZEN

        # For marginal transit times (close to limit), frozen is better for safety
        # Leave 3-day buffer for production flexibility
        if transit_days + ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS > ProductState.AMBIENT.shelf_life_days - 3:
            return ProductState.FROZEN

        # If transit + breadroom requirement comfortably fits in ambient (17 days), use ambient
        if transit_days + ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS <= ProductState.AMBIENT.shelf_life_days - 3:
            return ProductState.AMBIENT

        return ProductState.FROZEN
