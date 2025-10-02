"""
Shelf life tracker for route-based aging.

This module tracks product shelf life as it moves through the distribution network,
handling aging, state transitions, and special cases like the WA route (6130) thawing.
"""

from datetime import date, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass

from .state import ProductState, ShelfLifeInfo
from .rules import ShelfLifeRules, ShelfLifeValidationResult


@dataclass
class RouteLeg:
    """
    Represents one leg of a multi-leg route.

    Attributes:
        from_location_id: Source location ID
        to_location_id: Destination location ID
        transit_days: Transit time in days
        transport_mode: 'frozen' or 'ambient'
        triggers_thaw: If True, product thaws with shelf life reset at destination (e.g., 6130)
    """
    from_location_id: str
    to_location_id: str
    transit_days: int
    transport_mode: str
    triggers_thaw: bool = False

    def __str__(self) -> str:
        thaw_str = " [THAWS]" if self.triggers_thaw else ""
        return f"{self.from_location_id}->{self.to_location_id} ({self.transit_days}d, {self.transport_mode}){thaw_str}"


@dataclass
class RouteSegmentState:
    """
    Shelf life state at a specific point in a route.

    Attributes:
        location_id: Location ID where this state applies
        arrival_date: Date of arrival at this location
        shelf_life_info: Shelf life information at this point
        is_valid: Whether product is valid at this point (not expired, compatible mode)
        validation_result: Detailed validation result if this is final destination
    """
    location_id: str
    arrival_date: date
    shelf_life_info: ShelfLifeInfo
    is_valid: bool
    validation_result: Optional[ShelfLifeValidationResult] = None

    def __str__(self) -> str:
        valid_str = "" if self.is_valid else ""
        return f"{valid_str} {self.location_id} on {self.arrival_date}: {self.shelf_life_info}"


class ShelfLifeTracker:
    """
    Tracks shelf life through multi-leg routes with state transitions.

    This class simulates product aging through the distribution network,
    handling:
    - Transit time aging
    - State transitions (frozen�ambient, frozen�thawed)
    - Special thawing locations (e.g., 6130 in WA)
    - Breadroom acceptance validation
    """

    def __init__(self, rules: Optional[ShelfLifeRules] = None):
        """
        Initialize shelf life tracker.

        Args:
            rules: ShelfLifeRules instance (uses default if None)
        """
        self.rules = rules or ShelfLifeRules()

    def track_through_route(
        self,
        production_date: date,
        initial_state: ProductState,
        route_legs: List[RouteLeg],
        departure_date: Optional[date] = None
    ) -> List[RouteSegmentState]:
        """
        Track shelf life through a multi-leg route.

        Args:
            production_date: Date product was produced
            initial_state: Initial product state at production
            route_legs: List of route legs to traverse
            departure_date: Date product departs from source (defaults to production_date)

        Returns:
            List of RouteSegmentState showing shelf life at each location

        Raises:
            ValueError: If route legs are invalid or state transitions are impossible
        """
        if not route_legs:
            raise ValueError("Route must have at least one leg")

        if departure_date is None:
            departure_date = production_date

        # Initialize starting state
        current_shelf_life = ShelfLifeInfo(
            production_date=production_date,
            current_state=initial_state,
            current_age_days=0,
            thaw_date=None,
            days_since_thaw=None,
        )

        current_date = departure_date
        segment_states: List[RouteSegmentState] = []

        # Track through each leg
        for i, leg in enumerate(route_legs):
            is_final_leg = (i == len(route_legs) - 1)

            # Validate transport mode compatibility
            if not self.rules.is_compatible_with_transport_mode(
                current_shelf_life.current_state, leg.transport_mode
            ):
                # Handle state transition if needed
                if current_shelf_life.current_state == ProductState.FROZEN:
                    if leg.transport_mode.lower() == "ambient":
                        # Auto-transition frozen to ambient for ambient transport
                        current_shelf_life = current_shelf_life.transition_to(ProductState.AMBIENT)

            # Age during transit
            current_date = current_date + timedelta(days=leg.transit_days)
            current_shelf_life = current_shelf_life.age_by_days(leg.transit_days)

            # Handle thawing at destination (e.g., location 6130)
            if leg.triggers_thaw and current_shelf_life.current_state == ProductState.FROZEN:
                current_shelf_life = current_shelf_life.transition_to(
                    ProductState.THAWED,
                    transition_date=current_date
                )

            # Validate state at this point
            is_valid = not current_shelf_life.is_expired

            # If final destination (breadroom), check acceptance criteria
            validation_result = None
            if is_final_leg:
                validation_result = self.rules.validate_breadroom_acceptance(current_shelf_life)
                is_valid = is_valid and validation_result.is_valid

            segment_state = RouteSegmentState(
                location_id=leg.to_location_id,
                arrival_date=current_date,
                shelf_life_info=current_shelf_life,
                is_valid=is_valid,
                validation_result=validation_result,
            )

            segment_states.append(segment_state)

        return segment_states

    def find_latest_production_date(
        self,
        delivery_date: date,
        route_legs: List[RouteLeg],
        initial_state: ProductState = ProductState.AMBIENT,
    ) -> Tuple[date, List[RouteSegmentState]]:
        """
        Find the latest production date that meets breadroom acceptance at delivery.

        Uses binary search to find the latest production date where product
        arrives with at least 7 days remaining shelf life.

        Args:
            delivery_date: Target delivery date at final destination
            route_legs: List of route legs to traverse
            initial_state: Initial product state at production

        Returns:
            Tuple of (latest_production_date, route_segment_states)

        Raises:
            ValueError: If no valid production date exists (route too long)
        """
        # Calculate total transit time
        total_transit_days = sum(leg.transit_days for leg in route_legs)

        # Calculate earliest possible production date (based on shelf life limit)
        max_shelf_life = initial_state.shelf_life_days
        earliest_possible = delivery_date - timedelta(days=max_shelf_life)

        # Calculate latest possible production date (based on delivery date - transit)
        latest_possible = delivery_date - timedelta(days=total_transit_days)

        # Binary search for latest valid production date
        left = earliest_possible
        right = latest_possible
        best_date = None
        best_states = None

        while left <= right:
            mid = left + (right - left) // 2

            try:
                states = self.track_through_route(
                    production_date=mid,
                    initial_state=initial_state,
                    route_legs=route_legs,
                    departure_date=mid,  # Assume same-day departure
                )

                # Check if final destination is valid
                final_state = states[-1]
                if final_state.is_valid and final_state.validation_result and final_state.validation_result.is_valid:
                    # Valid - try later production date
                    best_date = mid
                    best_states = states
                    left = mid + timedelta(days=1)
                else:
                    # Invalid - try earlier production date
                    right = mid - timedelta(days=1)

            except (ValueError, Exception):
                # Invalid transition or other error - try earlier
                right = mid - timedelta(days=1)

        if best_date is None or best_states is None:
            raise ValueError(
                f"No valid production date found for delivery on {delivery_date}. "
                f"Route requires {total_transit_days} days transit, "
                f"plus {ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS} days breadroom minimum. "
                f"Total required: {total_transit_days + ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS} days, "
                f"but max shelf life is {max_shelf_life} days."
            )

        return best_date, best_states

    def validate_route_feasibility(
        self,
        route_legs: List[RouteLeg],
        initial_state: ProductState = ProductState.AMBIENT,
    ) -> Tuple[bool, str]:
        """
        Check if a route is theoretically feasible given shelf life constraints.

        Args:
            route_legs: List of route legs to check
            initial_state: Initial product state

        Returns:
            Tuple of (is_feasible, reason)
        """
        total_transit_days = sum(leg.transit_days for leg in route_legs)
        max_shelf_life = initial_state.shelf_life_days
        required_days = total_transit_days + ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS

        if required_days > max_shelf_life:
            return False, (
                f"Route requires {required_days} days "
                f"(transit {total_transit_days} + breadroom {ShelfLifeRules.MIN_BREADROOM_SHELF_LIFE_DAYS}), "
                f"but {initial_state} shelf life is only {max_shelf_life} days"
            )

        # Check for invalid state transitions
        current_state = initial_state
        for leg in route_legs:
            if not self.rules.is_compatible_with_transport_mode(current_state, leg.transport_mode):
                # Check if transition is possible
                if current_state == ProductState.FROZEN and leg.transport_mode.lower() == "ambient":
                    current_state = ProductState.AMBIENT  # Auto-transition
                else:
                    return False, (
                        f"Incompatible transport mode: {current_state} product "
                        f"cannot use {leg.transport_mode} transport on leg {leg}"
                    )

            if leg.triggers_thaw and current_state == ProductState.FROZEN:
                current_state = ProductState.THAWED

        return True, "Route is feasible"

    def compare_routes(
        self,
        production_date: date,
        initial_state: ProductState,
        route_options: List[List[RouteLeg]],
        route_names: Optional[List[str]] = None,
    ) -> List[Tuple[str, bool, Optional[RouteSegmentState]]]:
        """
        Compare multiple route options for the same production batch.

        Args:
            production_date: Production date
            initial_state: Initial product state
            route_options: List of route leg lists to compare
            route_names: Optional names for routes (defaults to "Route 1", "Route 2", etc.)

        Returns:
            List of tuples: (route_name, is_valid, final_segment_state)
        """
        if route_names is None:
            route_names = [f"Route {i+1}" for i in range(len(route_options))]

        if len(route_names) != len(route_options):
            raise ValueError("route_names must match route_options length")

        results = []

        for name, route_legs in zip(route_names, route_options):
            try:
                states = self.track_through_route(
                    production_date=production_date,
                    initial_state=initial_state,
                    route_legs=route_legs,
                )
                final_state = states[-1]
                is_valid = final_state.is_valid
                results.append((name, is_valid, final_state))
            except Exception as e:
                # Route failed
                results.append((name, False, None))

        return results
