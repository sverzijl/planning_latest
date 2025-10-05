"""Reusable solver mocks for optimization model tests.

This module provides mock solver configurations that properly handle
both the simple test models used by SolverConfig.test_solver() and
the complex optimization model structures.
"""

from unittest.mock import Mock
from pyomo.opt import SolverStatus, TerminationCondition


def create_mock_solver_config():
    """
    Create a mock SolverConfig that bypasses actual solver detection and testing.

    Returns a mock that provides a working solver without requiring
    actual solver binaries to be installed.

    Returns:
        Mock SolverConfig object with create_solver() method
    """
    mock_config = Mock()

    def mock_create_solver(solver_name=None, options=None):
        """Create a mock solver that handles both test and optimization models."""
        mock_solver = Mock()
        mock_solver.options = options or {}

        def mock_solve(pyomo_model, **kwargs):
            """
            Adaptive solve method that handles multiple model types.

            Detects model type and sets appropriate variable values:
            - Simple test model (has 'x' variable): Sets x = 1.0
            - Optimization model (has 'dates', 'products', 'routes'): Sets all variables
            """
            # Check if this is the simple test model from SolverConfig.test_solver()
            if hasattr(pyomo_model, 'x') and not hasattr(pyomo_model, 'dates'):
                # Simple test model: single variable x with constraint x >= 1
                pyomo_model.x.set_value(1.0)

            # Check if this is an optimization model
            elif hasattr(pyomo_model, 'dates') and hasattr(pyomo_model, 'products'):
                # Optimization model - set all decision variables

                # Set production variables
                if hasattr(pyomo_model, 'production'):
                    for d in pyomo_model.dates:
                        for p in pyomo_model.products:
                            pyomo_model.production[d, p].set_value(500.0)

                # Set shipment variables
                if hasattr(pyomo_model, 'shipment'):
                    for r in pyomo_model.routes:
                        for p in pyomo_model.products:
                            for d in pyomo_model.dates:
                                pyomo_model.shipment[r, p, d].set_value(100.0)

                # Set labor variables
                if hasattr(pyomo_model, 'labor_hours'):
                    for d in pyomo_model.dates:
                        pyomo_model.labor_hours[d].set_value(3.0)
                        if hasattr(pyomo_model, 'fixed_hours_used'):
                            pyomo_model.fixed_hours_used[d].set_value(3.0)
                        if hasattr(pyomo_model, 'overtime_hours_used'):
                            pyomo_model.overtime_hours_used[d].set_value(0.0)
                        if hasattr(pyomo_model, 'non_fixed_hours_paid'):
                            pyomo_model.non_fixed_hours_paid[d].set_value(0.0)

                # Set shortage variables if they exist
                if hasattr(pyomo_model, 'shortage'):
                    for key in pyomo_model.shortage:
                        pyomo_model.shortage[key].set_value(0.0)

                # Set inventory variables if they exist
                if hasattr(pyomo_model, 'inventory'):
                    for key in pyomo_model.inventory:
                        pyomo_model.inventory[key].set_value(50.0)

            # Create successful result
            mock_results = Mock()
            mock_results.solver.status = SolverStatus.ok
            mock_results.solver.termination_condition = TerminationCondition.optimal

            # Set problem bounds to avoid Mock type errors
            mock_problem = Mock()
            mock_problem.upper_bound = 1000.0
            mock_problem.lower_bound = 1000.0
            mock_results.problem = mock_problem

            # Set solution for objective value extraction
            mock_solution = Mock()
            mock_objective = Mock()
            mock_objective_value = Mock()
            mock_objective_value.value = 1000.0
            mock_objective.values = Mock(return_value=[mock_objective_value])
            mock_solution.objective = mock_objective
            mock_results.solution = Mock(return_value=mock_solution)

            # Mock the load_from method (no-op since values already set)
            def mock_load_from(results):
                pass

            pyomo_model.solutions.load_from = mock_load_from

            return mock_results

        mock_solver.solve = mock_solve
        return mock_solver

    mock_config.create_solver = mock_create_solver
    return mock_config


def create_mock_solver():
    """
    Create a standalone mock solver (without SolverConfig wrapper).

    Useful for direct solver mocking scenarios.

    Returns:
        Mock solver object with solve() method
    """
    config = create_mock_solver_config()
    return config.create_solver()
