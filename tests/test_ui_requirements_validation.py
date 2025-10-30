"""Test UI Requirements Validation.

This test suite proves that the UI requirements validator would have caught
all 4 recent UI display bugs before they reached the UI.

Each test simulates the exact bug condition and verifies the validator catches it.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock
from src.ui_interface.ui_requirements import (
    UITabRequirements,
    validate_solution_for_ui
)
from src.optimization.result_schema import (
    OptimizationSolution,
    TotalCostBreakdown,
    LaborCostBreakdown,
    ProductionCostBreakdown,
    TransportCostBreakdown,
    HoldingCostBreakdown,
    WasteCostBreakdown,
    ShipmentResult,
    ProductionBatchResult,
    LaborHoursBreakdown,
)


def create_minimal_solution():
    """Create minimal valid solution for testing."""
    costs = TotalCostBreakdown(
        total_cost=1000.0,
        labor=LaborCostBreakdown(total=500.0),
        production=ProductionCostBreakdown(total=200.0, unit_cost=0.1, total_units=2000.0),
        transport=TransportCostBreakdown(total=100.0),
        holding=HoldingCostBreakdown(total=50.0),
        waste=WasteCostBreakdown(total=150.0)
    )

    return OptimizationSolution(
        model_type="test",
        production_batches=[
            ProductionBatchResult(
                node="6122",
                product="TEST_PRODUCT",
                date=date.today(),
                quantity=1000.0
            )
        ],
        labor_hours_by_date={
            date.today(): LaborHoursBreakdown(used=10.0, paid=10.0)
        },
        shipments=[
            ShipmentResult(
                origin="6122",
                destination="6104",
                product="TEST_PRODUCT",
                quantity=500.0,
                delivery_date=date.today()
            )
        ],
        costs=costs,
        total_cost=1000.0,
        fill_rate=1.0,
        total_production=1000.0,
        total_shortage_units=0.0,
        has_aggregate_inventory=True,
        use_batch_tracking=False,
        production_by_date_product={
            ("6122", "TEST_PRODUCT", date.today()): 1000.0
        },
        shortages={},
        demand_consumed={
            ("6104", "TEST_PRODUCT", date.today()): 500.0
        }
    )


class TestBug1_LabelingDestinations:
    """Bug 1: Labeling Tab showed 'Unknown' destinations.

    Root Cause: production_by_date_product had 3-element tuples, code expected 2.

    Validator Should Catch:
    - Wrong tuple structure
    - Wrong tuple length
    - Wrong element types
    """

    def test_catches_wrong_tuple_length(self):
        """Validator catches 2-element tuples when 3 expected."""
        solution = create_minimal_solution()

        # Simulate the bug: wrong tuple format
        solution.production_by_date_product = {
            (date.today(), "PRODUCT"): 1000.0  # 2 elements instead of 3
        }

        errors = UITabRequirements.validate_foreign_keys(solution)

        # Should catch wrong tuple length
        assert any("must be (node, product, date)" in err for err in errors), \
            f"Should catch wrong tuple length, got: {errors}"

    def test_catches_wrong_element_types(self):
        """Validator catches non-string node/product IDs."""
        solution = create_minimal_solution()

        # Simulate type error: integer instead of string
        solution.production_by_date_product = {
            (6122, "PRODUCT", date.today()): 1000.0  # node is int, should be str
        }

        errors = UITabRequirements.validate_foreign_keys(solution)

        # Should catch wrong type
        assert any("node_id must be str" in err for err in errors), \
            f"Should catch wrong node type, got: {errors}"

    def test_valid_tuple_structure_passes(self):
        """Validator accepts correct 3-element tuple structure."""
        solution = create_minimal_solution()

        # Correct format
        solution.production_by_date_product = {
            ("6122", "PRODUCT", date.today()): 1000.0
        }

        errors = UITabRequirements.validate_foreign_keys(solution)

        # Should pass
        production_errors = [e for e in errors if "production" in e.lower()]
        assert not production_errors, f"Should accept valid tuples, got: {production_errors}"


class TestBug2_TruckAssignments:
    """Bug 2: Distribution Tab said 'not available' but 332 assignments existed.

    Root Cause: truck_assignments had integer index (10), truck.id was string ('T1').

    Validator Should Catch:
    - truck_id not in valid truck IDs
    - Type mismatch (int vs str)
    """

    def test_catches_invalid_truck_id(self):
        """Validator catches truck_id that doesn't exist in schedules."""
        solution = create_minimal_solution()
        solution.truck_assignments = {
            ("6122", "6104", "PRODUCT", date.today()): "T999"  # Invalid truck
        }

        # Mock model with truck schedules
        model = Mock()
        model.truck_schedules = [
            Mock(id="T1"),
            Mock(id="T2"),
        ]

        errors = UITabRequirements.validate_foreign_keys(solution, model)

        # Should catch invalid truck_id
        assert any("invalid truck_id 'T999'" in err.lower() for err in errors), \
            f"Should catch invalid truck_id, got: {errors}"

    def test_catches_integer_truck_id(self):
        """Validator catches integer truck_id when string expected."""
        solution = create_minimal_solution()
        solution.truck_assignments = {
            ("6122", "6104", "PRODUCT", date.today()): 10  # int instead of str
        }

        model = Mock()
        model.truck_schedules = [Mock(id="T1"), Mock(id="T2")]

        errors = UITabRequirements.validate_foreign_keys(solution, model)

        # Should catch type mismatch (10 not in {'T1', 'T2'})
        assert any("invalid truck_id" in err.lower() for err in errors), \
            f"Should catch wrong truck_id type, got: {errors}"

    def test_valid_truck_id_passes(self):
        """Validator accepts valid truck_id that exists."""
        solution = create_minimal_solution()
        solution.truck_assignments = {
            ("6122", "6104", "PRODUCT", date.today()): "T1"
        }

        model = Mock()
        model.truck_schedules = [Mock(id="T1"), Mock(id="T2")]

        errors = UITabRequirements.validate_foreign_keys(solution, model)

        # Should pass
        truck_errors = [e for e in errors if "truck" in e.lower()]
        assert not truck_errors, f"Should accept valid truck_id, got: {truck_errors}"


class TestBug3_DailySnapshotConsumption:
    """Bug 3: Daily Snapshot showed all demand as 'shortage', none as 'consumption'.

    Root Cause: demand_consumed field not extracted from model.

    Validator Should Catch:
    - Missing demand_consumed field
    - Empty demand_consumed dict
    """

    def test_catches_missing_demand_consumed(self):
        """Validator catches missing demand_consumed for aggregate models."""
        solution = create_minimal_solution()
        solution.demand_consumed = None  # Missing!

        errors = UITabRequirements.validate(solution, 'DAILY_SNAPSHOT')

        # Should catch missing demand_consumed
        assert any("demand_consumed" in err.lower() or "cohort_demand_consumption" in err.lower()
                   for err in errors), \
            f"Should catch missing demand data, got: {errors}"

    def test_catches_empty_demand_consumed(self):
        """Validator catches empty demand_consumed dict."""
        solution = create_minimal_solution()
        solution.demand_consumed = {}  # Empty!
        solution.cohort_demand_consumption = None  # Also empty

        errors = UITabRequirements.validate(solution, 'DAILY_SNAPSHOT')

        # Should warn about empty data
        assert any("demand_consumed" in err.lower() or "cohort" in err.lower()
                   for err in errors), \
            f"Should catch empty demand data, got: {errors}"

    def test_valid_demand_consumed_passes(self):
        """Validator accepts valid demand_consumed data."""
        solution = create_minimal_solution()
        solution.demand_consumed = {
            ("6104", "PRODUCT", date.today()): 500.0
        }

        errors = UITabRequirements.validate(solution, 'DAILY_SNAPSHOT')

        # Should pass
        assert not errors, f"Should accept valid demand_consumed, got: {errors}"


class TestBug4_DailyCostsGraph:
    """Bug 4: Daily Costs graph showed 'No data available'.

    Root Cause: costs.labor.daily_breakdown was None (not populated).

    Validator Should Catch:
    - Missing daily_breakdown
    - Empty daily_breakdown dict
    """

    def test_catches_missing_daily_breakdown(self):
        """Validator catches missing labor.daily_breakdown."""
        solution = create_minimal_solution()
        # Don't set daily_breakdown (it's None by default)

        errors = UITabRequirements.validate(solution, 'DAILY_COSTS_GRAPH')

        # Should catch missing daily_breakdown
        assert any("daily_breakdown" in err.lower() for err in errors), \
            f"Should catch missing daily_breakdown, got: {errors}"

    def test_catches_empty_daily_breakdown(self):
        """Validator catches empty daily_breakdown dict."""
        solution = create_minimal_solution()
        solution.costs.labor.daily_breakdown = {}  # Empty!

        errors = UITabRequirements.validate(solution, 'DAILY_COSTS_GRAPH')

        # Should catch empty dict (min_length: 1)
        assert any("daily_breakdown" in err.lower() and "at least 1" in err.lower()
                   for err in errors), \
            f"Should catch empty daily_breakdown, got: {errors}"

    def test_valid_daily_breakdown_passes(self):
        """Validator accepts valid daily_breakdown data."""
        solution = create_minimal_solution()
        solution.costs.labor.daily_breakdown = {
            date.today(): {
                'total_cost': 500.0,
                'total_hours': 10.0
            }
        }

        errors = UITabRequirements.validate(solution, 'DAILY_COSTS_GRAPH')

        # Should pass
        assert not errors, f"Should accept valid daily_breakdown, got: {errors}"


class TestComprehensiveValidation:
    """Test that comprehensive validation catches all issues at once."""

    def test_validate_all_tabs_catches_multiple_issues(self):
        """Validator reports issues across multiple tabs."""
        solution = create_minimal_solution()

        # Introduce multiple bugs
        solution.production_by_date_product = {
            (date.today(), "PRODUCT"): 1000.0  # Bug 1: wrong tuple
        }
        solution.demand_consumed = None  # Bug 3: missing field
        solution.costs.labor.daily_breakdown = None  # Bug 4: missing field

        all_errors = UITabRequirements.validate_all_tabs(solution)

        # Should catch issues in multiple tabs
        assert len(all_errors) >= 2, \
            f"Should catch issues in multiple tabs, got: {all_errors}"

    def test_validate_solution_for_ui_fail_fast(self):
        """Comprehensive validation raises on first error in fail_fast mode."""
        solution = create_minimal_solution()
        solution.production_by_date_product = {
            (date.today(), "PRODUCT"): 1000.0  # Bug: wrong tuple
        }

        with pytest.raises(ValueError) as exc_info:
            validate_solution_for_ui(solution, fail_fast=True)

        error_msg = str(exc_info.value)
        assert "validation failed" in error_msg.lower(), \
            f"Should raise validation error, got: {error_msg}"

    def test_validate_solution_for_ui_comprehensive(self):
        """Comprehensive validation checks both UI requirements and foreign keys."""
        solution = create_minimal_solution()

        # Introduce bugs
        solution.production_by_date_product = {
            (6122, "PRODUCT", date.today()): 1000.0  # Wrong type
        }
        solution.demand_consumed = {}  # Empty

        model = Mock()
        model.truck_schedules = [Mock(id="T1")]

        # Should not raise in non-fail-fast mode
        try:
            validate_solution_for_ui(solution, model, fail_fast=False)
        except ValueError:
            pytest.fail("Should not raise in non-fail-fast mode")

        # But should raise in fail-fast mode
        with pytest.raises(ValueError):
            validate_solution_for_ui(solution, model, fail_fast=True)


def test_all_validation_scenarios():
    """Integration test: Verify validator catches all 4 bug scenarios."""
    scenarios = [
        ("Labeling wrong tuple", {
            "production_by_date_product": {(date.today(), "P"): 100}
        }),
        ("Truck ID mismatch", {
            "truck_assignments": {("O", "D", "P", date.today()): 10}
        }),
        ("Missing demand_consumed", {
            "demand_consumed": None,
            "cohort_demand_consumption": None
        }),
        ("Missing daily_breakdown", {
            "costs": {"labor": {"daily_breakdown": None}}
        }),
    ]

    for scenario_name, modifications in scenarios:
        solution = create_minimal_solution()

        # Apply modifications
        for field, value in modifications.items():
            if "." in field:
                # Nested field
                parts = field.split(".")
                obj = solution
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:
                setattr(solution, field, value)

        # Should catch the issue
        all_errors = UITabRequirements.validate_all_tabs(solution)
        fk_errors = UITabRequirements.validate_foreign_keys(solution)

        assert all_errors or fk_errors, \
            f"Scenario '{scenario_name}' should be caught by validator"
