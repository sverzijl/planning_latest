"""Tests for UI result adapter utility."""

import pytest
from ui.utils.result_adapter import (
    _create_placeholder_truck_plan,
    _create_production_schedule,
    _create_cost_breakdown,
)
from src.distribution.truck_loader import TruckLoadPlan


class TestPlaceholderTruckPlan:
    """Test placeholder truck plan creation for optimization results."""

    def test_create_placeholder_returns_valid_truck_plan(self):
        """Test that placeholder creates a valid TruckLoadPlan instance."""
        plan = _create_placeholder_truck_plan()

        assert isinstance(plan, TruckLoadPlan)
        assert plan is not None

    def test_placeholder_has_empty_loads(self):
        """Test that placeholder has no truck loads."""
        plan = _create_placeholder_truck_plan()

        assert len(plan.loads) == 0
        assert plan.loads == []

    def test_placeholder_has_no_unassigned_shipments(self):
        """Test that placeholder has no unassigned shipments."""
        plan = _create_placeholder_truck_plan()

        assert len(plan.unassigned_shipments) == 0
        assert plan.unassigned_shipments == []

    def test_placeholder_has_no_infeasibilities(self):
        """Test that placeholder has no infeasibilities."""
        plan = _create_placeholder_truck_plan()

        assert len(plan.infeasibilities) == 0
        assert plan.infeasibilities == []

    def test_placeholder_has_zero_trucks_used(self):
        """Test that placeholder indicates zero trucks used."""
        plan = _create_placeholder_truck_plan()

        assert plan.total_trucks_used == 0

    def test_placeholder_has_zero_shipments(self):
        """Test that placeholder indicates zero shipments."""
        plan = _create_placeholder_truck_plan()

        assert plan.total_shipments == 0

    def test_placeholder_has_zero_utilization(self):
        """Test that placeholder has zero average utilization."""
        plan = _create_placeholder_truck_plan()

        assert plan.average_utilization == 0.0

    def test_placeholder_is_feasible(self):
        """Test that placeholder truck plan is considered feasible."""
        plan = _create_placeholder_truck_plan()

        # Empty plan with no infeasibilities should be feasible
        assert plan.is_feasible()

    def test_multiple_calls_create_independent_instances(self):
        """Test that multiple calls create separate instances."""
        plan1 = _create_placeholder_truck_plan()
        plan2 = _create_placeholder_truck_plan()

        assert plan1 is not plan2
        # Verify they're independent by modifying one
        plan1.loads.append(None)  # type: ignore
        assert len(plan1.loads) == 1
        assert len(plan2.loads) == 0
