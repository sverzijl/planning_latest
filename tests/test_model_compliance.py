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
from src.optimization.unified_node_model import UnifiedNodeModel
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
            ambient_storage_capacity=None
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
            ambient_storage_capacity=None
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
    forecast = Forecast(entries=forecast_entries)

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
    labor_calendar = LaborCalendar(days=labor_days)

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

    def test_extract_solution_returns_optimization_solution(self, simple_test_data):
        """Test that extract_solution() returns OptimizationSolution."""
        model = SlidingWindowModel(
            nodes=simple_test_data['nodes'],
            routes=simple_test_data['routes'],
            forecast=simple_test_data['forecast'],
            products=simple_test_data['products'],
            labor_calendar=simple_test_data['labor_calendar'],
            cost_structure=simple_test_data['cost_structure'],
            start_date=simple_test_data['start_date'],
            end_date=simple_test_data['end_date'],
            allow_shortages=True
        )

        # Solve model
        result = model.solve(solver_name='appsi_highs', mip_gap=0.05, time_limit_seconds=30)

        if result.is_feasible():
            solution = model.get_solution()

            # CRITICAL: Must return OptimizationSolution
            assert isinstance(solution, OptimizationSolution), \
                f"extract_solution() must return OptimizationSolution, got {type(solution)}"

            # Must have correct model_type
            assert solution.model_type == "sliding_window", \
                f"SlidingWindowModel must set model_type='sliding_window', got '{solution.model_type}'"

            # Must set has_aggregate_inventory flag
            assert solution.has_aggregate_inventory is True, \
                "SlidingWindowModel must set has_aggregate_inventory=True"

            # Must NOT set use_batch_tracking
            assert solution.use_batch_tracking is False, \
                "SlidingWindowModel must set use_batch_tracking=False"

            # get_inventory_format() should return "state"
            assert solution.get_inventory_format() == "state", \
                "SlidingWindowModel inventory format should be 'state'"

            print(f"\n✓ SlidingWindowModel compliance validated")
            print(f"  - Inherits from BaseOptimizationModel")
            print(f"  - Returns OptimizationSolution")
            print(f"  - model_type: {solution.model_type}")
            print(f"  - inventory_format: {solution.get_inventory_format()}")
        else:
            pytest.skip(f"Solver not available or solution infeasible: {result.termination_condition}")


class TestUnifiedNodeModelCompliance:
    """Test UnifiedNodeModel interface compliance."""

    def test_inherits_from_base_model(self):
        """Test that UnifiedNodeModel inherits from BaseOptimizationModel."""
        assert issubclass(UnifiedNodeModel, BaseOptimizationModel), \
            "UnifiedNodeModel must inherit from BaseOptimizationModel"

    def test_extract_solution_returns_optimization_solution(self, simple_test_data):
        """Test that extract_solution() returns OptimizationSolution."""
        model = UnifiedNodeModel(
            nodes=simple_test_data['nodes'],
            routes=simple_test_data['routes'],
            forecast=simple_test_data['forecast'],
            products=simple_test_data['products'],
            labor_calendar=simple_test_data['labor_calendar'],
            cost_structure=simple_test_data['cost_structure'],
            start_date=simple_test_data['start_date'],
            end_date=simple_test_data['end_date'],
            use_batch_tracking=True,
            allow_shortages=True
        )

        # Solve model
        result = model.solve(solver_name='appsi_highs', mip_gap=0.05, time_limit_seconds=30)

        if result.is_feasible():
            solution = model.get_solution()

            # CRITICAL: Must return OptimizationSolution
            assert isinstance(solution, OptimizationSolution), \
                f"extract_solution() must return OptimizationSolution, got {type(solution)}"

            # Must have correct model_type
            assert solution.model_type == "unified_node", \
                f"UnifiedNodeModel must set model_type='unified_node', got '{solution.model_type}'"

            # Must set use_batch_tracking flag
            assert solution.use_batch_tracking is True, \
                "UnifiedNodeModel must set use_batch_tracking=True"

            # Must NOT set has_aggregate_inventory
            assert solution.has_aggregate_inventory is False, \
                "UnifiedNodeModel must set has_aggregate_inventory=False"

            # get_inventory_format() should return "cohort"
            assert solution.get_inventory_format() == "cohort", \
                "UnifiedNodeModel inventory format should be 'cohort'"

            print(f"\n✓ UnifiedNodeModel compliance validated")
            print(f"  - Inherits from BaseOptimizationModel")
            print(f"  - Returns OptimizationSolution")
            print(f"  - model_type: {solution.model_type}")
            print(f"  - inventory_format: {solution.get_inventory_format()}")
        else:
            pytest.skip(f"Solver not available or solution infeasible: {result.termination_condition}")


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
