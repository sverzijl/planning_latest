"""UI Integration Tests for Pydantic Model Interface.

This module tests that UI components correctly handle OptimizationSolution
(Pydantic model) instead of dicts, catching AttributeErrors before deployment.

These tests should have caught the bugs found during deployment:
- solution.get() → AttributeError
- cost_breakdown.labor.total_cost → AttributeError (should be .total)
- optimization_result.keys() → AttributeError
- Missing helper methods

Run: pytest tests/test_ui_integration.py -v
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.optimization.result_schema import (
    OptimizationSolution,
    ProductionBatchResult,
    LaborHoursBreakdown,
    ShipmentResult,
    TotalCostBreakdown,
    LaborCostBreakdown,
    ProductionCostBreakdown,
    TransportCostBreakdown,
    HoldingCostBreakdown,
    WasteCostBreakdown,
    StorageState,
)


@pytest.fixture
def mock_optimization_solution():
    """Create a mock OptimizationSolution for testing."""
    return OptimizationSolution(
        model_type="sliding_window",
        production_batches=[
            ProductionBatchResult(
                node="6122",
                product="PROD1",
                date=date(2025, 10, 1),
                quantity=1000.0
            ),
            ProductionBatchResult(
                node="6122",
                product="PROD2",
                date=date(2025, 10, 2),
                quantity=500.0
            )
        ],
        labor_hours_by_date={
            date(2025, 10, 1): LaborHoursBreakdown(
                used=12.0,
                paid=12.0,
                fixed=12.0,
                overtime=0.0,
                non_fixed=0.0
            ),
            date(2025, 10, 2): LaborHoursBreakdown(
                used=8.0,
                paid=8.0,
                fixed=8.0,
                overtime=0.0,
                non_fixed=0.0
            )
        },
        shipments=[
            ShipmentResult(
                origin="6122",
                destination="6104",
                product="PROD1",
                quantity=500.0,
                delivery_date=date(2025, 10, 3),
                state=StorageState.AMBIENT
            )
        ],
        costs=TotalCostBreakdown(
            total_cost=1000.0,
            labor=LaborCostBreakdown(total=200.0),
            production=ProductionCostBreakdown(
                total=300.0,
                unit_cost=0.2,
                total_units=1500.0,
                changeover_cost=50.0
            ),
            transport=TransportCostBreakdown(total=200.0),
            holding=HoldingCostBreakdown(
                total=200.0,
                frozen_storage=100.0,
                ambient_storage=100.0
            ),
            waste=WasteCostBreakdown(total=100.0, shortage_penalty=100.0)
        ),
        total_cost=1000.0,
        fill_rate=0.95,
        total_production=1500.0,
        total_shortage_units=50.0,
        has_aggregate_inventory=True,
        inventory_state={
            ("6122", "PROD1", "ambient", date(2025, 10, 1)): 500.0
        },
        production_by_date_product={
            ("6122", "PROD1", date(2025, 10, 1)): 1000.0,
            ("6122", "PROD2", date(2025, 10, 2)): 500.0
        }
    )


class TestResultAdapterWithPydantic:
    """Test result_adapter.py with Pydantic models."""

    def test_adapt_optimization_results_accepts_pydantic(self, mock_optimization_solution):
        """Test that adapt_optimization_results accepts OptimizationSolution."""
        from ui.utils.result_adapter import adapt_optimization_results

        # Create mock model
        mock_model = MagicMock()
        mock_model.get_solution.return_value = mock_optimization_solution
        mock_model.manufacturing_nodes = ["6122"]
        mock_model.start_date = date(2025, 10, 1)
        mock_model.end_date = date(2025, 10, 7)
        mock_model.cost_structure = MagicMock()
        mock_model.cost_structure.production_cost_per_unit = 1.0
        mock_model.extract_shipments.return_value = []

        # Should not raise AttributeError
        result = adapt_optimization_results(mock_model, {}, None)

        assert result is not None
        assert 'production_schedule' in result
        assert 'cost_breakdown' in result


class TestCostBreakdownHelpers:
    """Test TotalCostBreakdown helper methods."""

    def test_get_cost_proportions_exists(self, mock_optimization_solution):
        """Test that get_cost_proportions() method exists."""
        cost_breakdown = mock_optimization_solution.costs

        # Should not raise AttributeError
        proportions = cost_breakdown.get_cost_proportions()

        assert 'labor' in proportions
        assert 'production' in proportions
        assert 'transport' in proportions
        assert 'holding' in proportions
        assert 'waste' in proportions

    def test_get_cost_proportions_sums_to_one(self, mock_optimization_solution):
        """Test that proportions sum to 1.0."""
        cost_breakdown = mock_optimization_solution.costs
        proportions = cost_breakdown.get_cost_proportions()

        total = sum(proportions.values())
        assert abs(total - 1.0) < 0.001, f"Proportions should sum to 1.0, got {total}"

    def test_nested_costs_use_total_not_total_cost(self, mock_optimization_solution):
        """Test that nested breakdowns use .total, not .total_cost."""
        cost_breakdown = mock_optimization_solution.costs

        # These should work (nested use .total)
        assert cost_breakdown.labor.total == 200.0
        assert cost_breakdown.production.total == 300.0
        assert cost_breakdown.transport.total == 200.0
        assert cost_breakdown.holding.total == 200.0
        assert cost_breakdown.waste.total == 100.0

        # This should work (top-level uses .total_cost)
        assert cost_breakdown.total_cost == 1000.0

        # These should raise AttributeError (wrong attribute names)
        with pytest.raises(AttributeError):
            _ = cost_breakdown.labor.total_cost

        with pytest.raises(AttributeError):
            _ = cost_breakdown.production.total_cost


class TestPydanticInterfaceNotDict:
    """Test that OptimizationSolution doesn't have dict methods."""

    def test_no_get_method(self, mock_optimization_solution):
        """Test that .get() doesn't exist (not a dict)."""
        with pytest.raises(AttributeError, match="has no attribute 'get'"):
            _ = mock_optimization_solution.get('total_cost')

    def test_no_keys_method(self, mock_optimization_solution):
        """Test that .keys() doesn't exist (not a dict)."""
        with pytest.raises(AttributeError, match="has no attribute 'keys'"):
            _ = mock_optimization_solution.keys()

    def test_no_dict_bracket_access(self, mock_optimization_solution):
        """Test that bracket access doesn't work (not a dict)."""
        with pytest.raises(TypeError):
            _ = mock_optimization_solution['total_cost']

    def test_use_attributes_instead(self, mock_optimization_solution):
        """Test correct attribute access."""
        # Correct way to access fields
        assert mock_optimization_solution.total_cost == 1000.0
        assert mock_optimization_solution.model_type == "sliding_window"
        assert mock_optimization_solution.fill_rate == 0.95

    def test_use_getattr_for_optional_fields(self, mock_optimization_solution):
        """Test getattr() for optional extra fields."""
        # Extra fields (may not exist)
        batch_shipments = getattr(mock_optimization_solution, 'batch_shipments', [])
        assert batch_shipments == []  # Not set, returns default

        # Set an extra field
        mock_optimization_solution.custom_field = 42
        assert getattr(mock_optimization_solution, 'custom_field', None) == 42


class TestUIComponentsWithPydantic:
    """Test UI components handle Pydantic models correctly."""

    def test_cost_charts_accepts_total_cost_breakdown(self, mock_optimization_solution):
        """Test cost charts can handle TotalCostBreakdown."""
        from ui.components.cost_charts import render_cost_breakdown_chart

        cost_breakdown = mock_optimization_solution.costs

        # Should not raise AttributeError about .total vs .total_cost
        try:
            with patch('streamlit.plotly_chart'):
                fig = render_cost_breakdown_chart(cost_breakdown)
                assert fig is not None
        except AttributeError as e:
            pytest.fail(f"Cost chart raised AttributeError: {e}")

    def test_production_labeling_accepts_optimization_solution(self, mock_optimization_solution):
        """Test production labeling accepts OptimizationSolution."""
        from src.analysis.production_labeling_report import ProductionLabelingReportGenerator

        # Should not raise AttributeError about .get() or .keys()
        try:
            generator = ProductionLabelingReportGenerator(mock_optimization_solution)
            assert generator is not None
        except AttributeError as e:
            if '.get' in str(e) or '.keys' in str(e):
                pytest.fail(f"ProductionLabelingReportGenerator still uses dict methods: {e}")
            raise


class TestAnalysisModulesWithPydantic:
    """Test analysis modules handle Pydantic models correctly."""

    def test_daily_snapshot_accepts_optimization_solution(self, mock_optimization_solution):
        """Test DailySnapshotGenerator accepts OptimizationSolution."""
        from src.analysis.daily_snapshot import DailySnapshotGenerator
        from src.models.production_schedule import ProductionSchedule
        from src.models.location import Location
        from src.models.forecast import Forecast

        # Create minimal test data (use MagicMock to avoid Location validation issues)
        loc_6122 = MagicMock()
        loc_6122.id = "6122"
        loc_6122.name = "Manufacturing"

        loc_6104 = MagicMock()
        loc_6104.id = "6104"
        loc_6104.name = "Hub"

        locations = {
            "6122": loc_6122,
            "6104": loc_6104
        }
        production_schedule = MagicMock()
        production_schedule.production_batches = []
        shipments = []
        forecast = MagicMock()
        forecast.entries = []

        # Should not raise AttributeError about .get()
        try:
            generator = DailySnapshotGenerator(
                production_schedule=production_schedule,
                shipments=shipments,
                locations_dict=locations,
                forecast=forecast,
                model_solution=mock_optimization_solution
            )
            assert generator is not None
            assert generator.use_model_inventory is True
        except AttributeError as e:
            if '.get' in str(e):
                pytest.fail(f"DailySnapshotGenerator still uses .get(): {e}")
            raise


class TestCommonUIPatterns:
    """Test common UI access patterns work correctly."""

    def test_accessing_production_batches(self, mock_optimization_solution):
        """Test iterating over production_batches."""
        # Common pattern in UI
        total = sum(batch.quantity for batch in mock_optimization_solution.production_batches)
        assert total == 1500.0

        dates = [batch.date for batch in mock_optimization_solution.production_batches]
        assert len(dates) == 2

    def test_accessing_labor_hours(self, mock_optimization_solution):
        """Test accessing labor hours breakdown."""
        # Common pattern in UI
        total_hours = sum(
            breakdown.used
            for breakdown in mock_optimization_solution.labor_hours_by_date.values()
        )
        assert total_hours == 20.0

    def test_accessing_cost_components(self, mock_optimization_solution):
        """Test accessing nested cost components."""
        # Common patterns in UI (should NOT use .total_cost on nested)
        labor_cost = mock_optimization_solution.costs.labor.total
        production_cost = mock_optimization_solution.costs.production.total
        transport_cost = mock_optimization_solution.costs.transport.total

        assert labor_cost == 200.0
        assert production_cost == 300.0
        assert transport_cost == 200.0

    def test_cost_percentages_calculation(self, mock_optimization_solution):
        """Test calculating cost percentages (common in UI)."""
        cost_breakdown = mock_optimization_solution.costs

        # Common pattern in UI
        if cost_breakdown.total_cost > 0:
            labor_pct = (cost_breakdown.labor.total / cost_breakdown.total_cost) * 100
            prod_pct = (cost_breakdown.production.total / cost_breakdown.total_cost) * 100

            assert labor_pct == 20.0
            assert prod_pct == 30.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
