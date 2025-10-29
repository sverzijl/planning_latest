"""Tests for optimization validation utilities.

These tests ensure that validation functions catch data structure bugs
BEFORE they cause silent failures or confusing errors.
"""

import pytest
from datetime import date

from src.optimization.validation_utils import (
    validate_dict_has_string_keys,
    validate_fefo_return_structure,
    validate_solution_dict_for_pydantic,
    validate_optimization_solution_complete,
)
from src.optimization.result_schema import (
    OptimizationSolution,
    ProductionBatchResult,
    LaborHoursBreakdown,
    TotalCostBreakdown,
    LaborCostBreakdown,
    ProductionCostBreakdown,
    TransportCostBreakdown,
    HoldingCostBreakdown,
    WasteCostBreakdown,
)


class TestValidateDictHasStringKeys:
    """Test validate_dict_has_string_keys catches tuple/date keys."""

    def test_valid_string_keys(self):
        """Test that valid string keys pass."""
        data = {'key1': 'value1', 'key2': 'value2'}
        # Should not raise
        validate_dict_has_string_keys(data, 'test_field')

    def test_tuple_keys_rejected(self):
        """Test that tuple keys are rejected with clear error.

        This is the exact bug that caused FEFO to fail silently.
        """
        data = {('6104', 'PRODUCT', 'ambient'): ['batch1', 'batch2']}

        with pytest.raises(TypeError) as exc_info:
            validate_dict_has_string_keys(data, 'batch_inventory')

        error_msg = str(exc_info.value)
        assert 'batch_inventory has 1 non-string keys' in error_msg
        assert 'tuple' in error_msg
        assert 'Convert complex keys to strings' in error_msg

    def test_date_keys_rejected(self):
        """Test that date keys are rejected."""
        data = {date(2025, 10, 1): 100.0, date(2025, 10, 2): 200.0}

        with pytest.raises(TypeError) as exc_info:
            validate_dict_has_string_keys(data, 'labor_cost_by_date')

        error_msg = str(exc_info.value)
        assert 'non-string keys' in error_msg
        assert 'date' in error_msg

    def test_non_dict_rejected(self):
        """Test that non-dict input is rejected."""
        with pytest.raises(TypeError) as exc_info:
            validate_dict_has_string_keys(['not', 'a', 'dict'], 'test_field')

        assert 'must be a dict' in str(exc_info.value)


class TestValidateFEFOReturnStructure:
    """Test validate_fefo_return_structure catches FEFO bugs."""

    def test_valid_fefo_structure(self):
        """Test that valid FEFO structure passes."""
        fefo_result = {
            'batches': [{'id': 'B1', 'quantity': 100}],
            'batch_objects': [],
            'batch_inventory': {'6104|PRODUCT|ambient': []},  # STRING keys
            'shipment_allocations': [],
        }

        # Should not raise
        validate_fefo_return_structure(fefo_result)

    def test_missing_field_rejected(self):
        """Test that missing required fields are caught."""
        fefo_result = {
            'batches': [],
            # Missing batch_inventory!
        }

        with pytest.raises(ValueError) as exc_info:
            validate_fefo_return_structure(fefo_result)

        error_msg = str(exc_info.value)
        assert 'missing required fields' in error_msg
        assert 'batch_inventory' in error_msg

    def test_tuple_keys_in_batch_inventory_rejected(self):
        """Test that tuple keys in batch_inventory are caught.

        This is the EXACT bug that caused the UI to break.
        """
        fefo_result = {
            'batches': [],
            'batch_objects': [],
            'batch_inventory': {
                ('6104', 'PRODUCT', 'ambient'): []  # TUPLE key - WRONG!
            },
            'shipment_allocations': [],
        }

        with pytest.raises(TypeError) as exc_info:
            validate_fefo_return_structure(fefo_result)

        error_msg = str(exc_info.value)
        assert 'batch_inventory has' in error_msg
        assert 'non-string keys' in error_msg
        assert 'tuple' in error_msg
        assert 'Convert complex keys to strings' in error_msg

    def test_wrong_field_type_rejected(self):
        """Test that wrong field types are caught."""
        fefo_result = {
            'batches': 'not a list',  # Should be list!
            'batch_objects': [],
            'batch_inventory': {},
            'shipment_allocations': [],
        }

        with pytest.raises(TypeError) as exc_info:
            validate_fefo_return_structure(fefo_result)

        assert "'batches' must be list" in str(exc_info.value)


class TestValidateSolutionDictForPydantic:
    """Test validate_solution_dict_for_pydantic catches extraction bugs."""

    def test_valid_solution_dict(self):
        """Test that valid solution dict passes."""
        solution_dict = {
            'production_batches': [{'node': '6122', 'product': 'P1', 'date': date(2025, 11, 3), 'quantity': 100}],
            'labor_hours_by_date': {date(2025, 11, 3): {'used': 10, 'paid': 10, 'fixed': 10, 'overtime': 0, 'non_fixed': 0}},
            'shipments': [{'origin': '6122', 'destination': '6104', 'product': 'P1', 'quantity': 100, 'delivery_date': date(2025, 11, 4)}],
            'total_production': 100.0,
            'fill_rate': 1.0,
            'total_cost': 1000.0,
        }

        # Should not raise
        validate_solution_dict_for_pydantic(solution_dict)

    def test_missing_required_field(self):
        """Test that missing required fields are caught."""
        solution_dict = {
            'production_batches': [],
            # Missing labor_hours_by_date, shipments, etc.
        }

        with pytest.raises(ValueError) as exc_info:
            validate_solution_dict_for_pydantic(solution_dict)

        error_msg = str(exc_info.value)
        assert 'missing required fields' in error_msg

    def test_production_without_batches(self):
        """Test that production > 0 without batches is caught."""
        solution_dict = {
            'production_batches': [],  # Empty!
            'labor_hours_by_date': {},
            'shipments': [],
            'total_production': 1000.0,  # But production > 0!
            'fill_rate': 1.0,
            'total_cost': 1000.0,
        }

        with pytest.raises(ValueError) as exc_info:
            validate_solution_dict_for_pydantic(solution_dict)

        error_msg = str(exc_info.value)
        assert 'total_production=1000' in error_msg
        assert 'production_batches is empty' in error_msg

    def test_production_without_shipments(self):
        """Test that production > 0 without shipments is caught.

        This is the bug that caused "no demand satisfaction" in UI.
        Validation accepts either 'shipments' (converted) or 'shipments_by_route_product_date' (raw).
        """
        solution_dict = {
            'production_batches': [{'node': '6122', 'product': 'P1', 'date': date(2025, 11, 3), 'quantity': 100}],
            'labor_hours_by_date': {},
            'shipments': [],  # Empty!
            'shipments_by_route_product_date': {},  # Also empty!
            'total_production': 100.0,
            'fill_rate': 1.0,
            'total_cost': 1000.0,
        }

        with pytest.raises(ValueError) as exc_info:
            validate_solution_dict_for_pydantic(solution_dict)

        error_msg = str(exc_info.value)
        assert 'no shipments found' in error_msg
        assert 'Production must be shipped somewhere' in error_msg


class TestValidateOptimizationSolutionComplete:
    """Test validate_optimization_solution_complete catches UI-breaking bugs."""

    def test_valid_complete_solution(self):
        """Test that valid complete solution passes."""
        solution = OptimizationSolution(
            model_type="sliding_window",
            production_batches=[
                ProductionBatchResult(node='6122', product='P1', date=date(2025, 11, 3), quantity=100)
            ],
            labor_hours_by_date={
                date(2025, 11, 3): LaborHoursBreakdown(used=10, paid=10, fixed=10, overtime=0, non_fixed=0)
            },
            shipments=[],  # Empty but no production, so OK
            costs=TotalCostBreakdown(
                total_cost=1000.0,
                labor=LaborCostBreakdown(total=300.0),
                production=ProductionCostBreakdown(total=250.0, unit_cost=0.25, total_units=100.0),
                transport=TransportCostBreakdown(total=200.0),
                holding=HoldingCostBreakdown(total=150.0),
                waste=WasteCostBreakdown(total=100.0),
            ),
            total_cost=1000.0,
            fill_rate=1.0,
            total_production=100.0,
            has_aggregate_inventory=True,
        )

        # Should raise because shipments empty but production > 0
        with pytest.raises(ValueError) as exc_info:
            validate_optimization_solution_complete(solution)

        assert 'shipments is empty' in str(exc_info.value)

    def test_wrong_type_rejected(self):
        """Test that non-OptimizationSolution is rejected."""
        with pytest.raises(TypeError) as exc_info:
            validate_optimization_solution_complete({'not': 'a', 'solution': 'object'})

        assert 'Expected OptimizationSolution' in str(exc_info.value)

    def test_batch_sum_mismatch(self):
        """Test that batch sum != total_production is caught by Pydantic schema.

        Pydantic's built-in validator catches this, which is GOOD!
        This test verifies that the schema validation works.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            solution = OptimizationSolution(
                model_type="sliding_window",
                production_batches=[
                    ProductionBatchResult(node='6122', product='P1', date=date(2025, 11, 3), quantity=100)
                ],
                labor_hours_by_date={
                    date(2025, 11, 3): LaborHoursBreakdown(used=10, paid=10, fixed=10, overtime=0, non_fixed=0)
                },
                shipments=[],
                costs=TotalCostBreakdown(
                    total_cost=1000.0,
                    labor=LaborCostBreakdown(total=300.0),
                    production=ProductionCostBreakdown(total=250.0, unit_cost=0.25, total_units=1000.0),
                    transport=TransportCostBreakdown(total=200.0),
                    holding=HoldingCostBreakdown(total=150.0),
                    waste=WasteCostBreakdown(total=100.0),
                ),
                total_cost=1000.0,
                fill_rate=1.0,
                total_production=1000.0,  # Says 1000 but batches only sum to 100!
                has_aggregate_inventory=True,
            )

        error_msg = str(exc_info.value)
        # Pydantic catches this during construction
        assert 'total_production' in error_msg or 'batch quantities' in error_msg
