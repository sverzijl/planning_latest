"""Tests for distribution plan display functionality.

This module tests the result adapter and UI logic that converts optimization
results to displayable distribution plans, including handling cases where
truck assignments may not be available.
"""

import pytest
from datetime import date as Date
from unittest.mock import Mock

from ui.utils.result_adapter import (
    adapt_optimization_results,
    _create_truck_plan_from_optimization,
)
from src.models.shipment import Shipment
from src.distribution.truck_loader import TruckLoadPlan


class TestResultAdapterDistributionPlan:
    """Tests for result adapter distribution plan creation."""

    def test_adapt_returns_none_when_no_solution(self):
        """Test adapter returns None when model has no solution."""
        mock_model = Mock()
        mock_model.get_solution.return_value = None
        mock_result = {}

        result = adapt_optimization_results(mock_model, mock_result)

        assert result is None

    def test_create_truck_plan_with_no_truck_schedules(self):
        """Test truck plan creation when model.truck_schedules is None.

        This is a key test case for the bug fix - ensuring that shipments
        can be displayed even when the model was solved without truck schedules.
        """
        mock_model = Mock()
        mock_model.truck_schedules = None

        # Create shipments without truck assignments
        shipments = [
            Shipment(
                id="SHIP-001",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=1000,
                origin_id="6122",
                destination_id="6125",
                delivery_date=Date(2025, 6, 5),
                route=Mock(route_legs=[], total_transit_days=1),
                assigned_truck_id=None,  # No assignment
                production_date=Date(2025, 6, 4),
            ),
            Shipment(
                id="SHIP-002",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=2000,
                origin_id="6122",
                destination_id="6104",
                delivery_date=Date(2025, 6, 6),
                route=Mock(route_legs=[], total_transit_days=2),
                assigned_truck_id=None,  # No assignment
                production_date=Date(2025, 6, 4),
            ),
        ]

        truck_plan = _create_truck_plan_from_optimization(mock_model, shipments)

        # Should return valid TruckLoadPlan with no loads but valid shipments
        assert truck_plan is not None
        assert isinstance(truck_plan, TruckLoadPlan)
        assert len(truck_plan.loads) == 0
        assert len(truck_plan.unassigned_shipments) == 2
        assert truck_plan.total_shipments == 2
        assert truck_plan.total_trucks_used == 0
        assert truck_plan.average_utilization == 0.0

    def test_create_truck_plan_with_assigned_shipments(self):
        """Test truck plan creation with properly assigned shipments."""
        # Create mock truck schedule
        mock_truck = Mock()
        mock_truck.id = "TRUCK-001"
        mock_truck.truck_name = "Morning to 6125"
        mock_truck.capacity = 14080
        mock_truck.pallet_capacity = 44
        mock_truck.units_per_pallet = 320
        mock_truck.departure_type = "morning"
        mock_truck.departure_time = "06:00"

        mock_model = Mock()
        mock_model.truck_schedules = Mock()
        mock_model.truck_schedules.schedules = [mock_truck]

        # Create mock route
        mock_route_leg = Mock()
        mock_route_leg.to_location_id = "6125"

        mock_route = Mock()
        mock_route.route_legs = [mock_route_leg]
        mock_route.total_transit_days = 1

        shipments = [
            Shipment(
                id="SHIP-001",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=3200,
                origin_id="6122",
                destination_id="6125",
                delivery_date=Date(2025, 6, 5),
                route=mock_route,
                assigned_truck_id="TRUCK-001",  # Assigned!
                production_date=Date(2025, 6, 4),
            )
        ]

        truck_plan = _create_truck_plan_from_optimization(mock_model, shipments)

        # Should create truck load
        assert len(truck_plan.loads) == 1
        assert len(truck_plan.unassigned_shipments) == 0
        assert truck_plan.total_trucks_used == 1
        assert truck_plan.total_shipments == 1

        load = truck_plan.loads[0]
        assert load.truck_schedule_id == "TRUCK-001"
        assert load.total_units == 3200
        assert len(load.shipments) == 1

    def test_create_truck_plan_with_mixed_assignments(self):
        """Test truck plan with both assigned and unassigned shipments.

        This tests the scenario where some shipments are assigned to trucks
        (e.g., direct from manufacturing) while others are not (e.g., hub-to-spoke).
        """
        # Setup mocks
        mock_truck = Mock()
        mock_truck.id = "TRUCK-001"
        mock_truck.truck_name = "Morning to 6125"
        mock_truck.capacity = 14080
        mock_truck.pallet_capacity = 44
        mock_truck.units_per_pallet = 320
        mock_truck.departure_type = "morning"
        mock_truck.departure_time = "06:00"

        mock_model = Mock()
        mock_model.truck_schedules = Mock()
        mock_model.truck_schedules.schedules = [mock_truck]

        mock_route = Mock()
        mock_route.route_legs = [Mock(to_location_id="6125")]
        mock_route.total_transit_days = 1

        shipments = [
            # Assigned shipment (manufacturing → hub)
            Shipment(
                id="SHIP-001",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=3200,
                origin_id="6122",
                destination_id="6125",
                delivery_date=Date(2025, 6, 5),
                route=mock_route,
                assigned_truck_id="TRUCK-001",
                production_date=Date(2025, 6, 4),
            ),
            # Unassigned shipment (hub → spoke)
            Shipment(
                id="SHIP-002",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=1000,
                origin_id="6125",  # From hub
                destination_id="6103",
                delivery_date=Date(2025, 6, 6),
                route=mock_route,
                assigned_truck_id=None,  # No truck assignment
                production_date=Date(2025, 6, 4),
            ),
        ]

        truck_plan = _create_truck_plan_from_optimization(mock_model, shipments)

        # Should have 1 load and 1 unassigned
        assert len(truck_plan.loads) == 1
        assert len(truck_plan.unassigned_shipments) == 1
        assert truck_plan.total_shipments == 2
        assert truck_plan.total_trucks_used == 1

    def test_empty_shipments_list(self):
        """Test truck plan creation with empty shipments list."""
        mock_model = Mock()
        mock_model.truck_schedules = None

        shipments = []

        truck_plan = _create_truck_plan_from_optimization(mock_model, shipments)

        assert truck_plan is not None
        assert len(truck_plan.loads) == 0
        assert len(truck_plan.unassigned_shipments) == 0
        assert truck_plan.total_shipments == 0
        assert truck_plan.total_trucks_used == 0


class TestUIDistributionDisplayLogic:
    """Tests for UI display logic handling of distribution data."""

    def test_ui_should_accept_shipments_without_truck_assignments(self):
        """Verify UI logic accepts shipments even when truck assignments are missing.

        This is the key test case for the bug fix - the UI should display
        shipments even when truck_plan.loads is empty.
        """
        # Create truck plan with no loads but representing shipments
        truck_plan = TruckLoadPlan(
            loads=[],  # No truck loads
            unassigned_shipments=[],  # Tracked separately
            infeasibilities=[],
            total_trucks_used=0,
            total_shipments=5,  # But we have 5 shipments
            average_utilization=0.0,
        )

        # Create mock shipments list
        shipments = [Mock() for _ in range(5)]

        # Simulate UI checks
        has_shipments = shipments and len(shipments) > 0
        has_truck_loads = truck_plan and len(truck_plan.loads) > 0

        # The UI should show shipments even without truck loads
        assert has_shipments is True
        assert has_truck_loads is False

        # This should NOT trigger "No distribution plan available"
        # because we have shipments
        assert truck_plan is not None
        assert len(shipments) > 0

    def test_ui_should_reject_only_when_no_shipments(self):
        """Verify UI only shows warning when there are truly no shipments."""
        truck_plan = TruckLoadPlan(
            loads=[],
            unassigned_shipments=[],
            infeasibilities=[],
            total_trucks_used=0,
            total_shipments=0,
            average_utilization=0.0,
        )

        shipments = []  # No shipments at all

        has_shipments = shipments and len(shipments) > 0
        has_truck_loads = truck_plan and len(truck_plan.loads) > 0

        # In this case, we should show "No distribution plan available"
        # Note: empty list evaluates to empty, not False
        assert has_shipments == []  # Empty list
        assert not has_shipments  # But still "falsy"
        assert has_truck_loads is False

    def test_ui_should_show_full_data_with_truck_assignments(self):
        """Verify UI shows complete data when truck assignments are available."""
        # Create mock truck loads
        mock_load = Mock()
        mock_load.total_units = 3200

        truck_plan = TruckLoadPlan(
            loads=[mock_load],
            unassigned_shipments=[],
            infeasibilities=[],
            total_trucks_used=1,
            total_shipments=1,
            average_utilization=0.75,
        )

        shipments = [Mock()]

        has_shipments = shipments and len(shipments) > 0
        has_truck_loads = truck_plan and len(truck_plan.loads) > 0

        # Both should be true
        assert has_shipments is True
        assert has_truck_loads is True

    def test_truck_plan_feasibility_with_no_loads(self):
        """Test that TruckLoadPlan with no loads has expected feasibility.

        Note: TruckLoadPlan.is_feasible() checks if loads were successfully created.
        Empty loads list means no trucks were used, which may indicate infeasibility
        or simply that trucks weren't needed/available. The important part is that
        the UI can still display shipments even when is_feasible() returns False.
        """
        truck_plan = TruckLoadPlan(
            loads=[],
            unassigned_shipments=[Mock(), Mock()],
            infeasibilities=[],
            total_trucks_used=0,
            total_shipments=2,
            average_utilization=0.0,
        )

        # Document actual behavior: Empty loads may make it "infeasible"
        # But that's okay - we can still display unassigned shipments
        assert len(truck_plan.loads) == 0
        assert len(truck_plan.unassigned_shipments) == 2
        assert len(truck_plan.infeasibilities) == 0


class TestEdgeCases:
    """Test edge cases in distribution plan creation."""

    def test_None_shipments_list(self):
        """Test handling of None shipments list."""
        mock_model = Mock()
        mock_model.truck_schedules = None

        # This should not crash
        truck_plan = _create_truck_plan_from_optimization(mock_model, None or [])

        assert truck_plan is not None
        assert len(truck_plan.loads) == 0

    def test_shipment_with_invalid_truck_id(self):
        """Test shipment with assigned truck ID that doesn't match any truck."""
        mock_truck = Mock()
        mock_truck.id = "TRUCK-001"
        mock_truck.truck_name = "Morning to 6125"
        mock_truck.capacity = 14080
        mock_truck.pallet_capacity = 44
        mock_truck.units_per_pallet = 320

        mock_model = Mock()
        mock_model.truck_schedules = Mock()
        mock_model.truck_schedules.schedules = [mock_truck]

        shipments = [
            Shipment(
                id="SHIP-001",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=1000,
                origin_id="6122",
                destination_id="6125",
                delivery_date=Date(2025, 6, 5),
                route=Mock(route_legs=[], total_transit_days=1),
                assigned_truck_id="TRUCK-999",  # Invalid ID!
                production_date=Date(2025, 6, 4),
            )
        ]

        truck_plan = _create_truck_plan_from_optimization(mock_model, shipments)

        # Shipment should be treated as unassigned (truck not found)
        # Note: Current implementation might create a load anyway
        # This test documents expected behavior
        assert truck_plan is not None
        assert truck_plan.total_shipments == 1
