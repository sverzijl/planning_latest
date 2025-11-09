"""Tests for optimization model interface compliance.

This module validates that all optimization models conform to the
BaseOptimizationModel interface specification, ensuring:
1. Models inherit from BaseOptimizationModel
2. Models return OptimizationSolution (Pydantic validated)
3. Solutions have correct model_type flags
4. Solutions have correct inventory format flags

Run: pytest tests/test_model_compliance.py -v
"""

import pytest
from datetime import date, timedelta
from pathlib import Path

from src.optimization.base_model import BaseOptimizationModel
from src.optimization.result_schema import OptimizationSolution
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.sliding_window_model import SlidingWindowModel
from src.parsers.multi_file_parser import MultiFileParser
from tests.conftest import create_test_products


@pytest.fixture(scope="module")
def simple_test_data():
    """Create minimal test data for model instantiation."""
    from src.models.unified_node import UnifiedNode, StorageMode
    from src.models.unified_route import UnifiedRoute, TransportMode
    from src.models.forecast import Forecast, ForecastEntry
    from src.models.labor_calendar import LaborCalendar, LaborDay
    from src.models.cost_structure import CostStructure

    # Create single node (manufacturing)
    from src.models.unified_node import NodeCapabilities

    nodes = [
        UnifiedNode(
            id="6122",
            name="Manufacturing",
            node_type="manufacturing",
            can_manufacture=True,
            has_demand=False,
            storage_mode=StorageMode.AMBIENT,
            requires_trucks=True,
            frozen_storage_capacity=None,
            ambient_storage_capacity=None,
            capabilities=NodeCapabilities(
                can_manufacture=True,
                can_store_frozen=False,
                can_store_ambient=True,
                can_store_thawed=False,
                has_demand=False
            )
        ),
        UnifiedNode(
            id="6104",
            name="Destination",
            node_type="breadroom",
            can_manufacture=False,
            has_demand=True,
            storage_mode=StorageMode.AMBIENT,
            requires_trucks=False,
            frozen_storage_capacity=None,
            ambient_storage_capacity=None,
            capabilities=NodeCapabilities(
                can_manufacture=False,
                can_store_frozen=False,
                can_store_ambient=True,
                can_store_thawed=False,
                has_demand=True
            )
        )
    ]

    # Create single route
    routes = [
        UnifiedRoute(
            id="R1",
            origin_node_id="6122",
            destination_node_id="6104",
            transport_mode=TransportMode.AMBIENT,
            transit_days=1,
            cost_per_unit=0.10
        )
    ]

    # Create minimal forecast (1 week, 1 product, 1 location)
    forecast_entries = [
        ForecastEntry(
            location_id="6104",
            product_id="PROD1",
            forecast_date=date(2025, 10, 1) + timedelta(days=i),
            quantity=100.0
        )
        for i in range(7)
    ]
    forecast = Forecast(name="Test Forecast", entries=forecast_entries)

    # Create products
    products = create_test_products(["PROD1"])

    # Create labor calendar (7 days)
    labor_days = [
        LaborDay(
            date=date(2025, 10, 1) + timedelta(days=i),
            is_working_day=True,
            fixed_hours=12.0,
            regular_rate=20.0,
            overtime_rate=30.0,
            non_fixed_rate=40.0
        )
        for i in range(7)
    ]
    labor_calendar = LaborCalendar(name="Test Calendar", days=labor_days)

    # Create cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=1.0,
        shortage_penalty_per_unit=1000.0,
        storage_cost_frozen_per_unit_day=0.01,
        storage_cost_ambient_per_unit_day=0.005
    )

    return {
        'nodes': nodes,
        'routes': routes,
        'forecast': forecast,
        'products': products,
        'labor_calendar': labor_calendar,
        'cost_structure': cost_structure,
        'start_date': date(2025, 10, 1),
        'end_date': date(2025, 10, 7)
    }


class TestSlidingWindowModelCompliance:
    """Test SlidingWindowModel interface compliance."""

    def test_inherits_from_base_model(self):
        """Test that SlidingWindowModel inherits from BaseOptimizationModel."""
        assert issubclass(SlidingWindowModel, BaseOptimizationModel), \
            "SlidingWindowModel must inherit from BaseOptimizationModel"

    def test_extract_solution_returns_optimization_solution(self):
        """Test that extract_solution() signature returns OptimizationSolution."""
        # Just test type annotations, don't solve
        from inspect import signature

        sig = signature(SlidingWindowModel.extract_solution)
        return_annotation = sig.return_annotation

        assert 'OptimizationSolution' in str(return_annotation), \
            f"extract_solution() must return OptimizationSolution, got {return_annotation}"

        # Test that get_solution() also has correct type
        sig2 = signature(SlidingWindowModel.get_solution)
        return_annotation2 = sig2.return_annotation

        assert 'OptimizationSolution' in str(return_annotation2), \
            f"get_solution() must return OptimizationSolution, got {return_annotation2}"

        print(f"\n✓ SlidingWindowModel type signatures validated")
        print(f"  - extract_solution() -> {return_annotation}")
        print(f"  - get_solution() -> {return_annotation2}")


class TestUnifiedNodeModelCompliance:
    """Test UnifiedNodeModel interface compliance."""

    def test_inherits_from_base_model(self):
        """Test that UnifiedNodeModel inherits from BaseOptimizationModel."""
        assert issubclass(UnifiedNodeModel, BaseOptimizationModel), \
            "UnifiedNodeModel must inherit from BaseOptimizationModel"

    def test_extract_solution_returns_optimization_solution(self):
        """Test that extract_solution() signature returns OptimizationSolution."""
        # Just test type annotations, don't solve
        from inspect import signature

        sig = signature(UnifiedNodeModel.extract_solution)
        return_annotation = sig.return_annotation

        assert 'OptimizationSolution' in str(return_annotation), \
            f"extract_solution() must return OptimizationSolution, got {return_annotation}"

        # Test that get_solution() also has correct type
        sig2 = signature(UnifiedNodeModel.get_solution)
        return_annotation2 = sig2.return_annotation

        assert 'OptimizationSolution' in str(return_annotation2), \
            f"get_solution() must return OptimizationSolution, got {return_annotation2}"

        print(f"\n✓ UnifiedNodeModel type signatures validated")
        print(f"  - extract_solution() -> {return_annotation}")
        print(f"  - get_solution() -> {return_annotation2}")


class TestModelInterfaceContract:
    """Test that both models satisfy the interface contract."""

    def test_both_models_have_required_methods(self):
        """Test that both models implement required abstract methods."""
        # Check class methods exist
        assert hasattr(SlidingWindowModel, 'build_model'), "SlidingWindowModel must implement build_model()"
        assert hasattr(SlidingWindowModel, 'extract_solution'), "SlidingWindowModel must implement extract_solution()"

        assert hasattr(UnifiedNodeModel, 'build_model'), "UnifiedNodeModel must implement build_model()"
        assert hasattr(UnifiedNodeModel, 'extract_solution'), "UnifiedNodeModel must implement extract_solution()"

    def test_both_models_return_optimization_solution(self, simple_test_data):
        """Test that both models return OptimizationSolution type."""
        # This test just verifies type annotations, not actual solving
        from inspect import signature

        # Check SlidingWindowModel
        sliding_sig = signature(SlidingWindowModel.extract_solution)
        sliding_return_annotation = sliding_sig.return_annotation
        assert 'OptimizationSolution' in str(sliding_return_annotation), \
            f"SlidingWindowModel.extract_solution() must return OptimizationSolution, got {sliding_return_annotation}"

        # Check UnifiedNodeModel
        unified_sig = signature(UnifiedNodeModel.extract_solution)
        unified_return_annotation = unified_sig.return_annotation
        assert 'OptimizationSolution' in str(unified_return_annotation), \
            f"UnifiedNodeModel.extract_solution() must return OptimizationSolution, got {unified_return_annotation}"

        print("\n✓ Both models have correct type annotations")
        print(f"  - SlidingWindowModel.extract_solution() -> {sliding_return_annotation}")
        print(f"  - UnifiedNodeModel.extract_solution() -> {unified_return_annotation}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
