"""
Tests for shelf life calculation engine.

This module tests product state tracking, shelf life rules,
and route-based aging simulation.
"""

import pytest
from datetime import date, timedelta

from src.shelf_life import (
    ProductState,
    ShelfLifeInfo,
    ShelfLifeRules,
    ShelfLifeValidationResult,
    ShelfLifeTracker,
    RouteLeg,
    RouteSegmentState,
)


class TestProductState:
    """Tests for ProductState enum."""

    def test_shelf_life_days(self):
        """Test shelf life days for each state."""
        assert ProductState.FROZEN.shelf_life_days == 120
        assert ProductState.AMBIENT.shelf_life_days == 17
        assert ProductState.THAWED.shelf_life_days == 14

    def test_string_representation(self):
        """Test string conversion."""
        assert str(ProductState.FROZEN) == "frozen"
        assert str(ProductState.AMBIENT) == "ambient"
        assert str(ProductState.THAWED) == "thawed"


class TestShelfLifeInfo:
    """Tests for ShelfLifeInfo dataclass."""

    def test_ambient_creation(self):
        """Test creating ambient product info."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=0,
        )
        assert info.production_date == date(2025, 1, 1)
        assert info.current_state == ProductState.AMBIENT
        assert info.current_age_days == 0
        assert info.thaw_date is None
        assert info.days_since_thaw is None

    def test_thawed_creation_valid(self):
        """Test creating thawed product info with valid data."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.THAWED,
            current_age_days=10,
            thaw_date=date(2025, 1, 11),
            days_since_thaw=0,
        )
        assert info.current_state == ProductState.THAWED
        assert info.thaw_date == date(2025, 1, 11)
        assert info.days_since_thaw == 0

    def test_thawed_creation_missing_thaw_date(self):
        """Test that THAWED state requires thaw_date."""
        with pytest.raises(ValueError, match="THAWED state requires thaw_date"):
            ShelfLifeInfo(
                production_date=date(2025, 1, 1),
                current_state=ProductState.THAWED,
                current_age_days=10,
            )

    def test_frozen_creation_with_thaw_data(self):
        """Test that FROZEN state cannot have thaw data."""
        with pytest.raises(ValueError, match="FROZEN state cannot have thaw_date"):
            ShelfLifeInfo(
                production_date=date(2025, 1, 1),
                current_state=ProductState.FROZEN,
                current_age_days=10,
                thaw_date=date(2025, 1, 11),
            )

    def test_expiry_date_ambient(self):
        """Test expiry date calculation for ambient product."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=0,
        )
        assert info.expiry_date == date(2025, 1, 18)  # +17 days

    def test_expiry_date_frozen(self):
        """Test expiry date calculation for frozen product."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.FROZEN,
            current_age_days=0,
        )
        assert info.expiry_date == date(2025, 5, 1)  # +120 days

    def test_expiry_date_thawed(self):
        """Test expiry date calculation for thawed product."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.THAWED,
            current_age_days=10,
            thaw_date=date(2025, 1, 11),
            days_since_thaw=0,
        )
        assert info.expiry_date == date(2025, 1, 25)  # thaw_date + 14 days

    def test_remaining_shelf_life_ambient(self):
        """Test remaining shelf life for ambient product."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=5,
        )
        assert info.remaining_shelf_life_days == 12  # 17 - 5

    def test_remaining_shelf_life_thawed(self):
        """Test remaining shelf life for thawed product."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.THAWED,
            current_age_days=10,
            thaw_date=date(2025, 1, 11),
            days_since_thaw=3,
        )
        assert info.remaining_shelf_life_days == 11  # 14 - 3

    def test_is_expired(self):
        """Test expiration check."""
        # Not expired
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=10,
        )
        assert not info.is_expired

        # Expired
        info_expired = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=20,
        )
        assert info_expired.is_expired

    def test_age_by_days(self):
        """Test aging product by days."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=5,
        )
        aged_info = info.age_by_days(3)
        assert aged_info.current_age_days == 8
        assert aged_info.remaining_shelf_life_days == 9  # 17 - 8

    def test_age_by_days_thawed(self):
        """Test aging thawed product by days."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.THAWED,
            current_age_days=10,
            thaw_date=date(2025, 1, 11),
            days_since_thaw=2,
        )
        aged_info = info.age_by_days(3)
        assert aged_info.current_age_days == 13
        assert aged_info.days_since_thaw == 5
        assert aged_info.remaining_shelf_life_days == 9  # 14 - 5

    def test_transition_frozen_to_ambient(self):
        """Test transition from FROZEN to AMBIENT."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.FROZEN,
            current_age_days=10,
        )
        transitioned = info.transition_to(ProductState.AMBIENT)
        assert transitioned.current_state == ProductState.AMBIENT
        assert transitioned.current_age_days == 10
        assert transitioned.thaw_date is None

    def test_transition_frozen_to_thawed(self):
        """Test transition from FROZEN to THAWED with shelf life reset."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.FROZEN,
            current_age_days=30,
        )
        thaw_date = date(2025, 1, 31)
        transitioned = info.transition_to(ProductState.THAWED, transition_date=thaw_date)
        assert transitioned.current_state == ProductState.THAWED
        assert transitioned.thaw_date == thaw_date
        assert transitioned.days_since_thaw == 0
        assert transitioned.remaining_shelf_life_days == 14

    def test_transition_frozen_to_thawed_no_date(self):
        """Test that FROZEN->THAWED requires transition_date."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.FROZEN,
            current_age_days=10,
        )
        with pytest.raises(ValueError, match="transition_date required"):
            info.transition_to(ProductState.THAWED)

    def test_transition_ambient_invalid(self):
        """Test that AMBIENT cannot transition to other states."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=5,
        )
        with pytest.raises(ValueError, match="Cannot transition from AMBIENT"):
            info.transition_to(ProductState.FROZEN)

    def test_transition_thawed_invalid(self):
        """Test that THAWED cannot transition to other states."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.THAWED,
            current_age_days=10,
            thaw_date=date(2025, 1, 11),
            days_since_thaw=3,
        )
        with pytest.raises(ValueError, match="Cannot transition from THAWED"):
            info.transition_to(ProductState.AMBIENT)


class TestShelfLifeRules:
    """Tests for ShelfLifeRules business logic."""

    def test_validate_breadroom_acceptance_valid(self):
        """Test breadroom acceptance with valid shelf life."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=5,
        )
        result = ShelfLifeRules.validate_breadroom_acceptance(info)
        assert result.is_valid
        assert result.remaining_days == 12  # 17 - 5

    def test_validate_breadroom_acceptance_exactly_7_days(self):
        """Test breadroom acceptance with exactly 7 days remaining."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=10,  # 17 - 10 = 7 days remaining
        )
        result = ShelfLifeRules.validate_breadroom_acceptance(info)
        assert result.is_valid
        assert result.remaining_days == 7

    def test_validate_breadroom_acceptance_insufficient(self):
        """Test breadroom rejection with insufficient shelf life."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=11,  # 17 - 11 = 6 days remaining (< 7)
        )
        result = ShelfLifeRules.validate_breadroom_acceptance(info)
        assert not result.is_valid
        assert result.remaining_days == 6
        assert "Insufficient shelf life" in result.reason

    def test_validate_breadroom_acceptance_expired(self):
        """Test breadroom rejection with expired product."""
        info = ShelfLifeInfo(
            production_date=date(2025, 1, 1),
            current_state=ProductState.AMBIENT,
            current_age_days=20,
        )
        result = ShelfLifeRules.validate_breadroom_acceptance(info)
        assert not result.is_valid
        assert "expired" in result.reason.lower()

    def test_can_transition_frozen_to_ambient(self):
        """Test valid transition FROZEN�AMBIENT."""
        assert ShelfLifeRules.can_transition(ProductState.FROZEN, ProductState.AMBIENT)

    def test_can_transition_frozen_to_thawed(self):
        """Test valid transition FROZEN�THAWED."""
        assert ShelfLifeRules.can_transition(ProductState.FROZEN, ProductState.THAWED)

    def test_can_transition_ambient_invalid(self):
        """Test invalid transitions from AMBIENT."""
        assert not ShelfLifeRules.can_transition(ProductState.AMBIENT, ProductState.FROZEN)
        assert not ShelfLifeRules.can_transition(ProductState.AMBIENT, ProductState.THAWED)

    def test_can_transition_same_state(self):
        """Test that same-state transitions are allowed."""
        assert ShelfLifeRules.can_transition(ProductState.FROZEN, ProductState.FROZEN)
        assert ShelfLifeRules.can_transition(ProductState.AMBIENT, ProductState.AMBIENT)

    def test_is_compatible_with_transport_mode(self):
        """Test transport mode compatibility."""
        # Frozen requires frozen transport
        assert ShelfLifeRules.is_compatible_with_transport_mode(ProductState.FROZEN, "frozen")
        assert not ShelfLifeRules.is_compatible_with_transport_mode(ProductState.FROZEN, "ambient")

        # Ambient requires ambient transport
        assert ShelfLifeRules.is_compatible_with_transport_mode(ProductState.AMBIENT, "ambient")
        assert not ShelfLifeRules.is_compatible_with_transport_mode(ProductState.AMBIENT, "frozen")

        # Thawed requires ambient transport
        assert ShelfLifeRules.is_compatible_with_transport_mode(ProductState.THAWED, "ambient")
        assert not ShelfLifeRules.is_compatible_with_transport_mode(ProductState.THAWED, "frozen")

    def test_suggest_best_state_for_transit_short(self):
        """Test state suggestion for short transit (fits in ambient)."""
        # 3 days transit + 7 days breadroom = 10 days total, fits in 17 days ambient
        suggested = ShelfLifeRules.suggest_best_state_for_transit(3)
        assert suggested == ProductState.AMBIENT

    def test_suggest_best_state_for_transit_long(self):
        """Test state suggestion for very long transit (frozen required)."""
        # 30 days transit exceeds ambient shelf life
        suggested = ShelfLifeRules.suggest_best_state_for_transit(30)
        assert suggested == ProductState.FROZEN

    def test_suggest_best_state_for_transit_marginal(self):
        """Test state suggestion for marginal transit time."""
        # 9 days transit + 7 days breadroom = 16 days (close to 17 limit)
        # Should suggest frozen for safety
        suggested = ShelfLifeRules.suggest_best_state_for_transit(9)
        assert suggested == ProductState.FROZEN


class TestShelfLifeTracker:
    """Tests for ShelfLifeTracker."""

    def test_simple_ambient_route(self):
        """Test tracking through simple ambient route."""
        tracker = ShelfLifeTracker()
        production_date = date(2025, 1, 1)

        route_legs = [
            RouteLeg(
                from_location_id="6122",
                to_location_id="6125",
                transit_days=2,
                transport_mode="ambient",
            ),
            RouteLeg(
                from_location_id="6125",
                to_location_id="6103",
                transit_days=1,
                transport_mode="ambient",
            ),
        ]

        states = tracker.track_through_route(
            production_date=production_date,
            initial_state=ProductState.AMBIENT,
            route_legs=route_legs,
        )

        assert len(states) == 2

        # First leg: 2 days transit to 6125
        assert states[0].location_id == "6125"
        assert states[0].arrival_date == date(2025, 1, 3)
        assert states[0].shelf_life_info.current_age_days == 2
        assert states[0].shelf_life_info.remaining_shelf_life_days == 15  # 17 - 2
        assert states[0].is_valid

        # Second leg: 1 day transit to 6103 (total 3 days)
        assert states[1].location_id == "6103"
        assert states[1].arrival_date == date(2025, 1, 4)
        assert states[1].shelf_life_info.current_age_days == 3
        assert states[1].shelf_life_info.remaining_shelf_life_days == 14  # 17 - 3
        assert states[1].is_valid
        assert states[1].validation_result is not None
        assert states[1].validation_result.is_valid

    def test_frozen_to_thawed_transition(self):
        """Test WA route with frozen�thawed transition at 6130."""
        tracker = ShelfLifeTracker()
        production_date = date(2025, 1, 1)

        route_legs = [
            RouteLeg(
                from_location_id="6122",
                to_location_id="Lineage",
                transit_days=3,
                transport_mode="frozen",
            ),
            RouteLeg(
                from_location_id="Lineage",
                to_location_id="6130",
                transit_days=4,
                transport_mode="frozen",
                triggers_thaw=True,  # Thaws at 6130
            ),
        ]

        states = tracker.track_through_route(
            production_date=production_date,
            initial_state=ProductState.FROZEN,
            route_legs=route_legs,
        )

        assert len(states) == 2

        # First leg: Frozen transit to Lineage
        assert states[0].location_id == "Lineage"
        assert states[0].shelf_life_info.current_state == ProductState.FROZEN
        assert states[0].shelf_life_info.current_age_days == 3

        # Second leg: Thaws at 6130 (shelf life resets to 14 days)
        assert states[1].location_id == "6130"
        assert states[1].shelf_life_info.current_state == ProductState.THAWED
        assert states[1].shelf_life_info.days_since_thaw == 0
        assert states[1].shelf_life_info.remaining_shelf_life_days == 14
        assert states[1].is_valid

    def test_breadroom_rejection_insufficient_shelf_life(self):
        """Test breadroom rejection when arriving with <7 days remaining."""
        tracker = ShelfLifeTracker()
        production_date = date(2025, 1, 1)

        # Long ambient route: 12 days transit leaves only 5 days at arrival
        route_legs = [
            RouteLeg(
                from_location_id="6122",
                to_location_id="6103",
                transit_days=12,
                transport_mode="ambient",
            ),
        ]

        states = tracker.track_through_route(
            production_date=production_date,
            initial_state=ProductState.AMBIENT,
            route_legs=route_legs,
        )

        assert len(states) == 1
        assert states[0].shelf_life_info.remaining_shelf_life_days == 5  # 17 - 12
        assert not states[0].is_valid  # Rejected by breadroom
        assert states[0].validation_result is not None
        assert not states[0].validation_result.is_valid

    def test_validate_route_feasibility_valid(self):
        """Test route feasibility validation for valid route."""
        tracker = ShelfLifeTracker()

        route_legs = [
            RouteLeg("6122", "6125", transit_days=2, transport_mode="ambient"),
            RouteLeg("6125", "6103", transit_days=1, transport_mode="ambient"),
        ]

        is_feasible, reason = tracker.validate_route_feasibility(
            route_legs=route_legs,
            initial_state=ProductState.AMBIENT,
        )

        assert is_feasible
        assert "feasible" in reason.lower()

    def test_validate_route_feasibility_too_long(self):
        """Test route feasibility validation for route that's too long."""
        tracker = ShelfLifeTracker()

        # 15 days transit + 7 days breadroom = 22 days (> 17 days ambient shelf life)
        route_legs = [
            RouteLeg("6122", "6103", transit_days=15, transport_mode="ambient"),
        ]

        is_feasible, reason = tracker.validate_route_feasibility(
            route_legs=route_legs,
            initial_state=ProductState.AMBIENT,
        )

        assert not is_feasible
        assert "22 days" in reason

    def test_find_latest_production_date(self):
        """Test finding latest production date for delivery."""
        tracker = ShelfLifeTracker()
        delivery_date = date(2025, 1, 15)

        route_legs = [
            RouteLeg("6122", "6125", transit_days=2, transport_mode="ambient"),
            RouteLeg("6125", "6103", transit_days=1, transport_mode="ambient"),
        ]

        latest_prod_date, states = tracker.find_latest_production_date(
            delivery_date=delivery_date,
            route_legs=route_legs,
            initial_state=ProductState.AMBIENT,
        )

        # Transit is 3 days, need 7 days at breadroom, so max age at arrival = 10 days
        # Latest production = delivery_date - 3 days (transit)
        # But need to check if remaining >= 7 at delivery
        # delivery_date - production_date - 7 >= 7
        # Expected: Jan 15 - 3 days transit = Jan 12, but need 7 days remaining
        # So age at arrival can be max 10 days (17 - 7)
        # But transit is only 3 days, so production can be Jan 12 (arrival Jan 15, age 3 days, 14 days remaining)

        assert states[-1].validation_result.is_valid
        assert states[-1].shelf_life_info.remaining_shelf_life_days >= 7
        assert states[-1].arrival_date == delivery_date

    def test_auto_transition_frozen_to_ambient(self):
        """Test auto-transition from frozen to ambient when transport mode changes."""
        tracker = ShelfLifeTracker()
        production_date = date(2025, 1, 1)

        # Frozen product on ambient transport should auto-transition
        route_legs = [
            RouteLeg("6122", "6125", transit_days=2, transport_mode="ambient"),
        ]

        states = tracker.track_through_route(
            production_date=production_date,
            initial_state=ProductState.FROZEN,
            route_legs=route_legs,
        )

        # Should have auto-transitioned to AMBIENT
        assert states[0].shelf_life_info.current_state == ProductState.AMBIENT
        assert states[0].is_valid


class TestRouteLeg:
    """Tests for RouteLeg dataclass."""

    def test_route_leg_creation(self):
        """Test creating a route leg."""
        leg = RouteLeg(
            from_location_id="6122",
            to_location_id="6125",
            transit_days=2,
            transport_mode="ambient",
        )
        assert leg.from_location_id == "6122"
        assert leg.to_location_id == "6125"
        assert leg.transit_days == 2
        assert leg.transport_mode == "ambient"
        assert not leg.triggers_thaw

    def test_route_leg_with_thaw(self):
        """Test creating a route leg that triggers thawing."""
        leg = RouteLeg(
            from_location_id="Lineage",
            to_location_id="6130",
            transit_days=4,
            transport_mode="frozen",
            triggers_thaw=True,
        )
        assert leg.triggers_thaw
        assert "THAWS" in str(leg)
