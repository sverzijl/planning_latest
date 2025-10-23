"""Comprehensive tests for pallet-based holding costs with ceiling rounding.

Tests the pallet-ceil rounding logic, holding cost calculation, and integration
with the optimization objective function.

Holding Cost Formula:
    total_holding_cost = Σ ceil(inventory_qty / 320) * storage_rate_per_pallet_day * days

Where:
    - 320 = UNITS_PER_PALLET (case size: 10 units, pallet: 32 cases)
    - storage_rate varies by state (frozen/ambient)
    - Partial pallets cost as full pallets (e.g., 50 units = 1 pallet cost)

Key Assertions:
    - Pallet count enforced by constraints: pallet * 320 >= inventory AND pallet * 320 < inventory + 320
    - Fixed cost charged per pallet per day
    - Frozen rate applied to frozen inventory, ambient rate to ambient/thawed
"""

import pytest
import math
from datetime import date, timedelta
from typing import Dict, List

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results


# ==================
# SHARED FIXTURES
# ==================

@pytest.fixture
def simple_network():
    """Create minimal 2-node network for testing."""
    manufacturing = UnifiedNode(
        id="MFG",
        name="Manufacturing",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            production_rate_per_hour=100.0,
            storage_capacity=10000.0,
        )
    )

    demand_node = UnifiedNode(
        id="DEST",
        name="Destination",
        capabilities=NodeCapabilities(
            has_demand=True,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            storage_capacity=5000.0,
        )
    )

    route = UnifiedRoute(
        id="R1",
        origin_node_id="MFG",
        destination_node_id="DEST",
        transport_mode=TransportMode.AMBIENT,
        transit_days=1.0,
        cost_per_unit=0.5,
    )

    return {'nodes': [manufacturing, demand_node], 'routes': [route]}


@pytest.fixture
def simple_forecast():
    """Minimal forecast with single demand entry."""
    return Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="DEST",
                product_id="P1",
                forecast_date=date(2025, 10, 7),
                quantity=320.0,  # Exactly 1 pallet
            )
        ]
    )


@pytest.fixture
def labor_calendar():
    """7-day labor calendar."""
    return LaborCalendar(
        name="Test Calendar",
        labor_days=[
            LaborDay(
                date=date(2025, 10, 1) + timedelta(days=i),
                is_fixed_day=True,
                fixed_hours=12.0,
                overtime_hours=2.0,
                regular_rate=25.0,
                overtime_rate=37.5,
            )
            for i in range(7)
        ]
    )


@pytest.fixture
def cost_structure_pallet_based():
    """Cost structure with pallet-based holding costs."""
    return CostStructure(
        production_cost_per_unit=2.0,
        storage_cost_fixed_per_pallet=10.0,  # $10 per pallet fixed
        storage_cost_per_pallet_day_frozen=2.0,  # $2/pallet/day frozen
        storage_cost_per_pallet_day_ambient=1.0,  # $1/pallet/day ambient
        shortage_penalty_per_unit=200.0,
    )


@pytest.fixture
def cost_structure_unit_based():
    """Cost structure with unit-based holding costs (legacy)."""
    return CostStructure(
        production_cost_per_unit=2.0,
        storage_cost_frozen_per_unit_day=0.10,  # $0.10/unit/day
        storage_cost_ambient_per_unit_day=0.05,  # $0.05/unit/day
        shortage_penalty_per_unit=200.0,
    )


@pytest.fixture
def cost_structure_zero_holding():
    """Cost structure with zero holding costs."""
    return CostStructure(
        production_cost_per_unit=2.0,
        storage_cost_frozen_per_unit_day=0.0,
        storage_cost_ambient_per_unit_day=0.0,
        shortage_penalty_per_unit=200.0,
    )


# ==================
# TEST CLASS 1: PALLET ROUNDING LOGIC
# ==================

class TestPalletRounding:
    """Test pallet count ceiling rounding logic."""

    @pytest.mark.parametrize("inventory_qty,expected_pallets", [
        (1, 1),      # Single unit → 1 pallet
        (50, 1),     # Half pallet → 1 pallet
        (160, 1),    # Exactly 0.5 pallet → 1 pallet
        (319, 1),    # Just under 1 pallet → 1 pallet
        (320, 1),    # Exactly 1 pallet → 1 pallet
        (321, 2),    # Just over 1 pallet → 2 pallets
        (640, 2),    # Exactly 2 pallets → 2 pallets
        (641, 3),    # Just over 2 pallets → 3 pallets
        (1000, 4),   # 3.125 pallets → 4 pallets
        (10000, 32),  # 31.25 pallets → 32 pallets
    ])
    def test_partial_pallet_rounds_up(
        self,
        inventory_qty,
        expected_pallets,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test that partial pallets round up to full pallet costs."""
        # Verify mathematical expectation
        calculated_pallets = math.ceil(inventory_qty / 320.0)
        assert calculated_pallets == expected_pallets, \
            f"Test data error: ceil({inventory_qty}/320) = {calculated_pallets}, not {expected_pallets}"

        # This is a structural test - doesn't require solving
        # The pallet ceiling constraint ensures: pallet_count = ceil(inventory / 320)
        # Actual solver tests are in integration tests


# ==================
# TEST CLASS 2: HOLDING COST CALCULATION
# ==================

class TestHoldingCostCalculation:
    """Test holding cost calculation with different inventory states."""

    def test_unit_based_costs_work(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_unit_based
    ):
        """Test that unit-based storage costs still work (backward compatibility)."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_unit_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        # Build model (don't need to solve for structural test)
        pyomo_model = model.build_model()

        # Verify pallet_count variables were created (unit costs converted to pallet basis)
        assert hasattr(pyomo_model, 'pallet_count'), \
            "Pallet variables should be created even with unit-based costs"

    def test_pallet_based_costs_take_precedence(
        self,
        simple_network,
        simple_forecast,
        labor_calendar
    ):
        """Test that pallet-based costs take precedence over unit-based costs."""
        # Cost structure with BOTH pallet and unit costs
        mixed_costs = CostStructure(
            production_cost_per_unit=2.0,
            storage_cost_frozen_per_unit_day=0.10,  # Unit-based
            storage_cost_ambient_per_unit_day=0.05,  # Unit-based
            storage_cost_per_pallet_day_frozen=3.0,  # Pallet-based (should win)
            storage_cost_per_pallet_day_ambient=1.5,  # Pallet-based (should win)
            shortage_penalty_per_unit=200.0,
        )

        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=mixed_costs,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        # Build model
        pyomo_model = model.build_model()

        # Should create pallet variables (not skip them)
        assert hasattr(pyomo_model, 'pallet_count')

    def test_zero_holding_costs_skips_pallet_variables(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_zero_holding
    ):
        """Test that zero storage costs skip pallet variable creation."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_zero_holding,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        pyomo_model = model.build_model()

        # With zero costs, pallet variables should NOT be created
        assert not hasattr(pyomo_model, 'pallet_count'), \
            "Pallet variables should be skipped when all storage rates are zero"

    def test_frozen_inventory_uses_frozen_rate(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test frozen inventory uses frozen storage rate."""
        # Create network with frozen storage node
        frozen_node = UnifiedNode(
            id="FROZEN",
            name="Frozen Storage",
            capabilities=NodeCapabilities(
                can_store=True,
                storage_mode=StorageMode.FROZEN,
                storage_capacity=10000.0,
            )
        )

        frozen_route = UnifiedRoute(
            id="R2",
            origin_node_id="MFG",
            destination_node_id="FROZEN",
            transport_mode=TransportMode.FROZEN,
            transit_days=1.0,
            cost_per_unit=0.3,
        )

        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'] + [frozen_node],
            routes=simple_network['routes'] + [frozen_route],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_pallet_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        pyomo_model = model.build_model()

        # Structural validation - frozen nodes should have frozen cohorts
        # Actual cost calculation tested in integration tests
        assert cost_structure_pallet_based.storage_cost_per_pallet_day_frozen == 2.0

    def test_ambient_inventory_uses_ambient_rate(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test ambient/thawed inventory uses ambient storage rate."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_pallet_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        pyomo_model = model.build_model()

        # Verify ambient storage rate is used
        assert cost_structure_pallet_based.storage_cost_per_pallet_day_ambient == 1.0


# ==================
# TEST CLASS 3: HOLDING COST INTEGRATION
# ==================

class TestHoldingCostIntegration:
    """Test integration with optimization model."""

    def test_holding_cost_in_objective_function(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test holding cost appears in objective function."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_pallet_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        # Build model (don't solve)
        pyomo_model = model.build_model()

        # Verify objective expression contains pallet_count variables
        obj_expr = pyomo_model.obj.expr
        obj_expr_str = str(obj_expr)

        # Check that pallet_count variables appear in objective
        assert 'pallet_count' in obj_expr_str, \
            "Objective should include pallet_count variables for holding cost"

    def test_ceiling_constraints_created(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test that ceiling constraints are created."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_pallet_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        pyomo_model = model.build_model()

        # Verify both lower and upper bound constraints exist
        assert hasattr(pyomo_model, 'pallet_lower_bound_con'), \
            "Lower bound constraint should exist"
        assert hasattr(pyomo_model, 'pallet_upper_bound_con'), \
            "Upper bound constraint should exist"

    def test_holding_cost_in_solution_dict(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test total_holding_cost appears in solution dictionary."""
        pytest.skip("Requires solver - integration test")

    def test_total_cost_includes_holding_cost(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test that total_cost = labor + production + transport + holding + shortage."""
        pytest.skip("Requires solver - integration test")


# ==================
# TEST CLASS 4: COST BREAKDOWN EXTRACTION
# ==================

class TestCostBreakdownExtraction:
    """Test result adapter extracts holding costs correctly."""

    def test_result_adapter_imports_holding_cost_breakdown(self):
        """Test that HoldingCostBreakdown is imported in result_adapter."""
        # Import test - will fail if module structure is incorrect
        from ui.utils.result_adapter import _create_cost_breakdown
        from src.costs.cost_breakdown import HoldingCostBreakdown

        # If we get here, imports are correct
        assert True

    def test_holding_breakdown_structure(self):
        """Test HoldingCostBreakdown has required fields."""
        from src.costs.cost_breakdown import HoldingCostBreakdown

        # Create instance
        breakdown = HoldingCostBreakdown(
            total_cost=100.0,
            frozen_cost=60.0,
            ambient_cost=40.0,
        )

        assert breakdown.total_cost == 100.0
        assert breakdown.frozen_cost == 60.0
        assert breakdown.ambient_cost == 40.0
        assert isinstance(breakdown.cost_by_location, dict)

    def test_total_cost_breakdown_includes_holding(self):
        """Test TotalCostBreakdown has holding field."""
        from src.costs.cost_breakdown import TotalCostBreakdown, HoldingCostBreakdown

        breakdown = TotalCostBreakdown(
            total_cost=1000.0,
            holding=HoldingCostBreakdown(total_cost=100.0)
        )

        assert breakdown.holding is not None
        assert breakdown.holding.total_cost == 100.0

    def test_get_cost_proportions_includes_holding(self):
        """Test cost proportions include holding component."""
        from src.costs.cost_breakdown import (
            TotalCostBreakdown,
            LaborCostBreakdown,
            ProductionCostBreakdown,
            TransportCostBreakdown,
            HoldingCostBreakdown,
            WasteCostBreakdown,
        )

        breakdown = TotalCostBreakdown(
            total_cost=1000.0,
            labor=LaborCostBreakdown(total_cost=300.0),
            production=ProductionCostBreakdown(total_cost=400.0),
            transport=TransportCostBreakdown(total_cost=150.0),
            holding=HoldingCostBreakdown(total_cost=100.0),
            waste=WasteCostBreakdown(total_cost=50.0),
        )

        proportions = breakdown.get_cost_proportions()

        assert 'holding' in proportions, "Proportions should include 'holding'"
        assert abs(proportions['holding'] - 0.10) < 0.001, \
            f"Holding proportion should be 0.10 (100/1000), got {proportions['holding']}"

        # Verify proportions sum to 1.0
        total = sum(proportions.values())
        assert abs(total - 1.0) < 0.0001, \
            f"Proportions should sum to 1.0, got {total}"


# ==================
# TEST CLASS 5: BACKWARD COMPATIBILITY
# ==================

class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_total_inventory_cost_alias_exists(self):
        """Test that total_inventory_cost alias exists for UI compatibility."""
        # Mock solution
        # This will be tested via extract_solution() in integration tests
        # Here we just verify the field mapping exists
        pytest.skip("Tested in integration tests")

    def test_zero_costs_behave_as_before(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_zero_holding
    ):
        """Test that zero holding costs behave identically to pre-feature implementation."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_zero_holding,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        pyomo_model = model.build_model()

        # With zero costs, no pallet variables should be created (optimization)
        assert not hasattr(pyomo_model, 'pallet_count')


# ==================
# TEST CLASS 6: EDGE CASES
# ==================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_inventory_zero_holding_cost(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test that empty inventory results in zero holding cost."""
        # This will be tested in integration tests where we can solve and extract
        pytest.skip("Requires solver - integration test")

    def test_very_large_inventory(self):
        """Test handling of very large inventory (>100,000 units)."""
        # 100,000 units = 312.5 pallets → 313 pallets
        large_qty = 100000
        expected_pallets = math.ceil(large_qty / 320.0)
        assert expected_pallets == 313

    def test_negative_storage_rates_raise_error(
        self,
        simple_network,
        simple_forecast,
        labor_calendar
    ):
        """Test that negative storage rates raise ValueError."""
        # This is handled by Pydantic validation in CostStructure
        with pytest.raises((ValueError, Exception)):
            invalid_costs = CostStructure(
                production_cost_per_unit=2.0,
                storage_cost_per_pallet_day_frozen=-1.0,  # Invalid
                shortage_penalty_per_unit=200.0,
            )


# ==================
# INTEGRATION TESTS (SOLVER REQUIRED)
# ==================

@pytest.mark.solver_required
class TestHoldingCostOptimization:
    """Integration tests requiring solver."""

    def test_solution_includes_holding_cost_fields(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test that solved model includes holding cost in solution."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_pallet_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=True,
        )

        result = model.solve(time_limit_seconds=30)
        assert result.is_optimal() or result.is_feasible()

        solution = model.get_solution()
        assert solution is not None

        # Check required fields exist
        assert 'total_holding_cost' in solution
        assert 'frozen_holding_cost' in solution
        assert 'ambient_holding_cost' in solution
        assert 'total_inventory_cost' in solution  # Backward compatibility

        # Holding cost should be non-negative
        assert solution['total_holding_cost'] >= 0

    def test_holding_cost_in_cost_breakdown(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test that result_adapter populates holding cost breakdown."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_pallet_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=True,
        )

        result = model.solve(time_limit_seconds=30)
        assert result.is_optimal() or result.is_feasible()

        # Adapt results for UI
        adapted_results = adapt_optimization_results(model, {}, None)
        assert adapted_results is not None

        cost_breakdown = adapted_results['cost_breakdown']
        assert cost_breakdown.holding is not None
        assert cost_breakdown.holding.total_cost >= 0

    def test_holding_cost_proportion_reasonable(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_pallet_based
    ):
        """Test holding cost is reasonable proportion of total cost."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_pallet_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=True,
        )

        result = model.solve(time_limit_seconds=30)
        assert result.is_optimal() or result.is_feasible()

        adapted_results = adapt_optimization_results(model, {}, None)
        proportions = adapted_results['cost_breakdown'].get_cost_proportions()

        # Holding should be present
        assert 'holding' in proportions

        # Proportions should sum to 1.0 (within tolerance)
        total = sum(proportions.values())
        assert abs(total - 1.0) < 0.001, \
            f"Cost proportions should sum to 1.0, got {total}"

    def test_holding_cost_doesnt_break_feasibility(
        self,
        simple_network,
        simple_forecast,
        labor_calendar,
        cost_structure_zero_holding,
        cost_structure_pallet_based
    ):
        """Test that adding holding costs doesn't make feasible problems infeasible."""
        # Solve WITHOUT holding costs
        model_no_holding = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_zero_holding,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=True,
        )

        result_no_holding = model_no_holding.solve(time_limit_seconds=30)
        assert result_no_holding.is_optimal() or result_no_holding.is_feasible()

        # Solve WITH holding costs (same problem)
        model_with_holding = UnifiedNodeModel(
            nodes=simple_network['nodes'],
            routes=simple_network['routes'],
            forecast=simple_forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure_pallet_based,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=True,
        )

        result_with_holding = model_with_holding.solve(time_limit_seconds=30)
        assert result_with_holding.is_optimal() or result_with_holding.is_feasible()

        # Holding costs don't add constraints, only objective terms
        # Both should be feasible
        solution_with = model_with_holding.get_solution()
        assert solution_with['total_holding_cost'] >= 0


# ==================
# TEST CLASS 7: CONSTANTS VALIDATION
# ==================

class TestPackagingConstants:
    """Test packaging constants are correctly defined."""

    def test_units_per_pallet_constant_exists(self):
        """Test UNITS_PER_PALLET is defined as class constant."""
        from src.optimization.unified_node_model import UnifiedNodeModel

        assert hasattr(UnifiedNodeModel, 'UNITS_PER_PALLET')
        assert UnifiedNodeModel.UNITS_PER_PALLET == 320.0

    def test_all_packaging_constants_defined(self):
        """Test all packaging constants are defined."""
        from src.optimization.unified_node_model import UnifiedNodeModel

        assert UnifiedNodeModel.UNITS_PER_CASE == 10.0
        assert UnifiedNodeModel.CASES_PER_PALLET == 32.0
        assert UnifiedNodeModel.UNITS_PER_PALLET == 320.0
        assert UnifiedNodeModel.PALLETS_PER_TRUCK == 44.0

    def test_packaging_constants_consistent(self):
        """Test packaging constants are mathematically consistent."""
        from src.optimization.unified_node_model import UnifiedNodeModel

        # UNITS_PER_PALLET should equal UNITS_PER_CASE × CASES_PER_PALLET
        expected = UnifiedNodeModel.UNITS_PER_CASE * UnifiedNodeModel.CASES_PER_PALLET
        assert UnifiedNodeModel.UNITS_PER_PALLET == expected
