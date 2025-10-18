"""Tests for HoldingCostBreakdown model and integration.

Tests that HoldingCostBreakdown dataclass is properly integrated into
TotalCostBreakdown and flows through from model to UI via result_adapter.
"""

import pytest
from datetime import date

from src.costs.cost_breakdown import (
    HoldingCostBreakdown,
    TotalCostBreakdown,
    LaborCostBreakdown,
    ProductionCostBreakdown,
    TransportCostBreakdown,
    WasteCostBreakdown,
)


class TestHoldingCostBreakdown:
    """Test suite for HoldingCostBreakdown dataclass."""

    def test_holding_cost_breakdown_instantiation(self):
        """Test that HoldingCostBreakdown can be instantiated."""
        holding = HoldingCostBreakdown(
            total_cost=150.0,
            frozen_cost=100.0,
            ambient_cost=50.0,
            cost_by_location={'LOC1': 80.0, 'LOC2': 70.0},
            cost_by_date={date(2025, 10, 1): 50.0, date(2025, 10, 2): 100.0},
        )

        assert holding.total_cost == 150.0
        assert holding.frozen_cost == 100.0
        assert holding.ambient_cost == 50.0
        assert holding.cost_by_location == {'LOC1': 80.0, 'LOC2': 70.0}
        assert len(holding.cost_by_date) == 2

    def test_holding_cost_breakdown_defaults(self):
        """Test that HoldingCostBreakdown has proper defaults."""
        holding = HoldingCostBreakdown()

        assert holding.total_cost == 0.0
        assert holding.frozen_cost == 0.0
        assert holding.ambient_cost == 0.0
        assert holding.cost_by_location == {}
        assert holding.cost_by_date == {}

    def test_holding_cost_breakdown_string_representation(self):
        """Test string representation of HoldingCostBreakdown."""
        holding = HoldingCostBreakdown(
            total_cost=150.0,
            frozen_cost=100.0,
            ambient_cost=50.0,
        )

        str_repr = str(holding)
        assert 'Holding Cost' in str_repr
        assert '$150.00' in str_repr
        assert '$100.00' in str_repr
        assert '$50.00' in str_repr
        assert 'frozen' in str_repr
        assert 'ambient' in str_repr


class TestTotalCostBreakdownWithHolding:
    """Test suite for TotalCostBreakdown with holding field."""

    def test_total_cost_breakdown_includes_holding(self):
        """Test that TotalCostBreakdown includes holding field."""
        holding = HoldingCostBreakdown(total_cost=75.0)

        total = TotalCostBreakdown(
            total_cost=500.0,
            labor=LaborCostBreakdown(total_cost=100.0),
            production=ProductionCostBreakdown(total_cost=150.0),
            transport=TransportCostBreakdown(total_cost=125.0),
            holding=holding,
            waste=WasteCostBreakdown(total_cost=50.0),
        )

        assert total.holding is not None
        assert total.holding.total_cost == 75.0
        assert total.total_cost == 500.0

    def test_total_cost_breakdown_holding_default(self):
        """Test that holding field has proper default."""
        total = TotalCostBreakdown()

        assert total.holding is not None
        assert isinstance(total.holding, HoldingCostBreakdown)
        assert total.holding.total_cost == 0.0

    def test_get_cost_proportions_includes_holding(self):
        """Test that get_cost_proportions() includes holding proportion."""
        total = TotalCostBreakdown(
            total_cost=1000.0,
            labor=LaborCostBreakdown(total_cost=200.0),
            production=ProductionCostBreakdown(total_cost=300.0),
            transport=TransportCostBreakdown(total_cost=250.0),
            holding=HoldingCostBreakdown(total_cost=150.0),
            waste=WasteCostBreakdown(total_cost=100.0),
        )

        proportions = total.get_cost_proportions()

        assert 'holding' in proportions
        assert proportions['labor'] == 0.2  # 200/1000
        assert proportions['production'] == 0.3  # 300/1000
        assert proportions['transport'] == 0.25  # 250/1000
        assert proportions['holding'] == 0.15  # 150/1000
        assert proportions['waste'] == 0.1  # 100/1000

        # Sum should equal 1.0
        total_proportion = sum(proportions.values())
        assert abs(total_proportion - 1.0) < 0.0001

    def test_get_cost_proportions_with_zero_total(self):
        """Test get_cost_proportions() with zero total cost."""
        total = TotalCostBreakdown(total_cost=0.0)

        proportions = total.get_cost_proportions()

        assert proportions['labor'] == 0.0
        assert proportions['production'] == 0.0
        assert proportions['transport'] == 0.0
        assert proportions['holding'] == 0.0
        assert proportions['waste'] == 0.0

    def test_total_cost_breakdown_string_includes_holding(self):
        """Test that string representation includes holding cost."""
        total = TotalCostBreakdown(
            total_cost=1000.0,
            holding=HoldingCostBreakdown(total_cost=150.0, frozen_cost=100.0, ambient_cost=50.0),
        )

        str_repr = str(total)

        assert 'Total Cost to Serve' in str_repr
        assert 'Holding Cost' in str_repr
        assert '$150.00' in str_repr


class TestResultAdapterHoldingCost:
    """Test suite for holding cost flow through result_adapter."""

    def test_holding_breakdown_created_in_adapter(self):
        """Test that result_adapter creates holding_breakdown."""
        # This is a structural test - integration test validates actual values

        from ui.utils.result_adapter import _create_cost_breakdown

        # Mock model and solution with holding cost
        class MockModel:
            pass

        mock_model = MockModel()

        mock_solution = {
            'total_labor_cost': 100.0,
            'total_production_cost': 200.0,
            'total_transport_cost': 150.0,
            'total_holding_cost': 75.0,  # KEY: holding cost in solution
            'total_shortage_cost': 25.0,
            'production_by_date_product': {},
            'labor_hours_by_date': {},
            'labor_cost_by_date': {},
        }

        # Execute
        cost_breakdown = _create_cost_breakdown(mock_model, mock_solution)

        # Verify holding breakdown exists
        assert cost_breakdown.holding is not None
        assert cost_breakdown.holding.total_cost == 75.0

    def test_holding_breakdown_with_zero_holding_cost(self):
        """Test that holding_breakdown handles zero holding cost."""
        from ui.utils.result_adapter import _create_cost_breakdown

        class MockModel:
            pass

        mock_solution = {
            'total_labor_cost': 100.0,
            'total_production_cost': 200.0,
            'total_transport_cost': 150.0,
            'total_holding_cost': 0.0,  # Zero holding cost
            'total_shortage_cost': 0.0,
            'production_by_date_product': {},
            'labor_hours_by_date': {},
            'labor_cost_by_date': {},
        }

        cost_breakdown = _create_cost_breakdown(MockModel(), mock_solution)

        assert cost_breakdown.holding.total_cost == 0.0

    def test_holding_breakdown_missing_from_solution(self):
        """Test graceful handling when total_holding_cost missing from solution."""
        from ui.utils.result_adapter import _create_cost_breakdown

        class MockModel:
            pass

        mock_solution = {
            'total_labor_cost': 100.0,
            'total_production_cost': 200.0,
            'total_transport_cost': 150.0,
            # 'total_holding_cost' missing
            'total_shortage_cost': 25.0,
            'production_by_date_product': {},
            'labor_hours_by_date': {},
            'labor_cost_by_date': {},
        }

        cost_breakdown = _create_cost_breakdown(MockModel(), mock_solution)

        # Should default to 0.0 if missing
        assert cost_breakdown.holding.total_cost == 0.0

    def test_total_cost_includes_holding_component(self):
        """Test that total_cost correctly sums all components including holding."""
        from ui.utils.result_adapter import _create_cost_breakdown

        class MockModel:
            pass

        mock_solution = {
            'total_labor_cost': 100.0,
            'total_production_cost': 200.0,
            'total_transport_cost': 150.0,
            'total_truck_cost': 0.0,
            'total_holding_cost': 75.0,
            'total_shortage_cost': 25.0,
            'total_freeze_cost': 0.0,
            'total_thaw_cost': 0.0,
            'production_by_date_product': {},
            'labor_hours_by_date': {},
            'labor_cost_by_date': {},
        }

        cost_breakdown = _create_cost_breakdown(MockModel(), mock_solution)

        # Total should be sum of all components
        expected_total = 100.0 + 200.0 + 150.0 + 75.0 + 25.0
        assert cost_breakdown.total_cost == expected_total

    def test_holding_cost_flows_from_model_to_breakdown(self):
        """Integration test: verify holding cost flows from model → adapter → breakdown.

        This test validates the complete flow:
        1. UnifiedNodeModel.extract_solution() adds 'total_holding_cost' to solution
        2. result_adapter._create_cost_breakdown() reads 'total_holding_cost'
        3. TotalCostBreakdown.holding is populated with correct value
        """
        pytest.skip("Integration test - requires full optimization setup")

        # Would test:
        # 1. Create UnifiedNodeModel with holding costs
        # 2. Solve model
        # 3. Extract solution (should have total_holding_cost)
        # 4. Call adapt_optimization_results()
        # 5. Verify cost_breakdown.holding.total_cost matches solution

    def test_holding_cost_breakdown_detailed_fields(self):
        """Test that holding breakdown can store detailed frozen/ambient breakdown."""
        # Note: Current implementation doesn't populate frozen_cost/ambient_cost separately
        # This test validates the structure is available for future enhancement

        holding = HoldingCostBreakdown(
            total_cost=150.0,
            frozen_cost=100.0,
            ambient_cost=50.0,
            cost_by_location={
                'MFG': 30.0,
                'HUB1': 70.0,
                'HUB2': 50.0,
            },
            cost_by_date={
                date(2025, 10, 1): 20.0,
                date(2025, 10, 2): 40.0,
                date(2025, 10, 3): 90.0,
            }
        )

        # Verify detailed fields are accessible
        assert holding.frozen_cost == 100.0
        assert holding.ambient_cost == 50.0
        assert len(holding.cost_by_location) == 3
        assert len(holding.cost_by_date) == 3
        assert sum(holding.cost_by_date.values()) == 150.0
