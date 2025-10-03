"""Tests for solver configuration module.

Tests cross-platform solver detection, configuration, and selection.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.optimization.solver_config import (
    SolverConfig,
    SolverType,
    SolverInfo,
    get_global_config,
    get_solver,
)


class TestSolverInfo:
    """Tests for SolverInfo dataclass."""

    def test_create_unavailable_solver_info(self):
        """Test creating solver info for unavailable solver."""
        info = SolverInfo(name="cbc", available=False)

        assert info.name == "cbc"
        assert info.available is False
        assert info.version is None
        assert info.path is None
        assert info.tested is False
        assert info.works is False

    def test_create_available_solver_info(self):
        """Test creating solver info for available solver."""
        info = SolverInfo(
            name="cbc",
            available=True,
            version="2.10.5",
            path="/usr/bin/cbc"
        )

        assert info.name == "cbc"
        assert info.available is True
        assert info.version == "2.10.5"
        assert info.path == "/usr/bin/cbc"
        assert info.tested is False
        assert info.works is False

    def test_solver_info_str_unavailable(self):
        """Test string representation of unavailable solver."""
        info = SolverInfo(name="cbc", available=False)
        assert "CBC: ✗ unavailable" in str(info)

    def test_solver_info_str_available(self):
        """Test string representation of available solver."""
        info = SolverInfo(name="cbc", available=True)
        assert "CBC: ✓ available" in str(info)

    def test_solver_info_str_tested(self):
        """Test string representation of tested solver."""
        info = SolverInfo(name="cbc", available=True, tested=True, works=True)
        assert "CBC: ✓ available (tested)" in str(info)


class TestSolverConfig:
    """Tests for SolverConfig class."""

    def test_init_detects_solvers(self):
        """Test that SolverConfig detects solvers on initialization."""
        config = SolverConfig()

        # Should have info for all solver types
        assert SolverType.CBC.value in config._solver_info
        assert SolverType.GLPK.value in config._solver_info
        assert SolverType.GUROBI.value in config._solver_info
        assert SolverType.CPLEX.value in config._solver_info

    def test_get_available_solvers_none_available(self):
        """Test getting available solvers when none are available."""
        with patch('src.optimization.solver_config.SolverFactory') as mock_factory:
            # Mock all solvers as unavailable
            mock_solver = Mock()
            mock_solver.available.return_value = False
            mock_factory.return_value = mock_solver

            config = SolverConfig()
            available = config.get_available_solvers()

            assert available == []

    def test_get_available_solvers_some_available(self):
        """Test getting available solvers when some are available."""
        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            if solver_name == 'cbc':
                mock_solver.available.return_value = True
            else:
                mock_solver.available.return_value = False
            return mock_solver

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect):
            config = SolverConfig()
            available = config.get_available_solvers()

            assert 'cbc' in available
            assert 'glpk' not in available

    def test_get_solver_info_existing(self):
        """Test getting solver info for existing solver."""
        config = SolverConfig()
        info = config.get_solver_info('cbc')

        assert info is not None
        assert info.name == 'cbc'

    def test_get_solver_info_non_existing(self):
        """Test getting solver info for non-existing solver."""
        config = SolverConfig()
        info = config.get_solver_info('nonexistent')

        assert info is None

    def test_get_best_available_solver_none_available(self):
        """Test getting best solver when none are available."""
        with patch('src.optimization.solver_config.SolverFactory') as mock_factory:
            # Mock all solvers as unavailable
            mock_solver = Mock()
            mock_solver.available.return_value = False
            mock_factory.return_value = mock_solver

            config = SolverConfig()

            with pytest.raises(RuntimeError, match="No optimization solver available"):
                config.get_best_available_solver(test_if_needed=False)

    def test_get_best_available_solver_prefers_gurobi(self):
        """Test that best solver prefers Gurobi when available."""
        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            # All solvers available
            mock_solver.available.return_value = True
            return mock_solver

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect):
            config = SolverConfig()
            best = config.get_best_available_solver(test_if_needed=False)

            # Should prefer Gurobi
            assert best == 'gurobi'

    def test_get_best_available_solver_falls_back_to_cbc(self):
        """Test that best solver falls back to CBC when Gurobi/CPLEX not available."""
        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            # Only CBC and GLPK available
            if solver_name in ['cbc', 'glpk']:
                mock_solver.available.return_value = True
            else:
                mock_solver.available.return_value = False
            return mock_solver

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect):
            config = SolverConfig()
            best = config.get_best_available_solver(test_if_needed=False)

            # Should fall back to CBC
            assert best == 'cbc'

    def test_create_solver_with_specific_name(self):
        """Test creating solver with specific name."""
        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            mock_solver.available.return_value = True
            mock_solver.options = {}
            return mock_solver

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect) as mock_factory:
            config = SolverConfig()
            solver = config.create_solver('cbc')

            # Should have called SolverFactory with 'cbc'
            mock_factory.assert_called_with('cbc')

    def test_create_solver_with_options(self):
        """Test creating solver with options."""
        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            mock_solver.available.return_value = True
            mock_solver.options = {}
            return mock_solver

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect):
            config = SolverConfig()
            solver = config.create_solver('cbc', options={'sec': 300, 'ratio': 0.01})

            # Should have set options
            assert solver.options['sec'] == 300
            assert solver.options['ratio'] == 0.01

    def test_create_solver_unavailable_raises_error(self):
        """Test creating unavailable solver raises error."""
        with patch('src.optimization.solver_config.SolverFactory') as mock_factory:
            mock_solver = Mock()
            mock_solver.available.return_value = False
            mock_factory.return_value = mock_solver

            config = SolverConfig()

            with pytest.raises(RuntimeError, match="is not available"):
                config.create_solver('cbc')

    def test_create_solver_unknown_raises_error(self):
        """Test creating unknown solver raises error."""
        config = SolverConfig()

        with pytest.raises(RuntimeError, match="Unknown solver"):
            config.create_solver('nonexistent_solver')

    def test_get_platform_info(self):
        """Test getting platform information."""
        config = SolverConfig()
        info = config.get_platform_info()

        assert 'system' in info
        assert 'machine' in info
        assert 'python_version' in info
        assert isinstance(info['system'], str)

    def test_print_solver_status_no_errors(self):
        """Test that print_solver_status doesn't raise errors."""
        config = SolverConfig()
        # Should not raise any errors
        config.print_solver_status()

    def test_print_platform_info_no_errors(self):
        """Test that print_platform_info doesn't raise errors."""
        config = SolverConfig()
        # Should not raise any errors
        config.print_platform_info()


class TestGlobalConfig:
    """Tests for global configuration functions."""

    def test_get_global_config_creates_singleton(self):
        """Test that get_global_config returns singleton."""
        config1 = get_global_config()
        config2 = get_global_config()

        # Should be same instance
        assert config1 is config2

    def test_get_solver_uses_global_config(self):
        """Test that get_solver uses global config."""
        import src.optimization.solver_config as solver_config_module

        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            mock_solver.available.return_value = True
            mock_solver.options = {}

            # Mock solve method for testing
            mock_results = Mock()
            from pyomo.opt import SolverStatus
            mock_results.solver.status = SolverStatus.ok
            mock_solver.solve.return_value = mock_results

            return mock_solver

        # Reset global config for this test
        solver_config_module._global_config = None

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect):
            with patch('src.optimization.solver_config.value', return_value=1.0):
                # Should not raise error even if no solver specified
                solver = get_solver()
                assert solver is not None

        # Reset again after test
        solver_config_module._global_config = None


class TestSolverTesting:
    """Tests for solver testing functionality.

    Note: These tests mock Pyomo to avoid requiring actual solver installation.
    """

    def test_test_solver_marks_as_tested(self):
        """Test that test_solver marks solver as tested."""
        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            mock_solver.available.return_value = True
            mock_solver.options = {}

            # Mock solve method
            mock_results = Mock()
            mock_results.solver.status = Mock()
            # Import the actual enum value
            from pyomo.opt import SolverStatus
            mock_results.solver.status = SolverStatus.ok
            mock_solver.solve.return_value = mock_results

            return mock_solver

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect):
            with patch('src.optimization.solver_config.value', return_value=1.0):
                config = SolverConfig()
                result = config.test_solver('cbc')

                info = config.get_solver_info('cbc')
                assert info.tested is True

    def test_test_all_solvers_returns_results(self):
        """Test that test_all_solvers returns results dictionary."""
        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            if solver_name == 'cbc':
                mock_solver.available.return_value = True
                mock_solver.options = {}

                # Mock solve method
                mock_results = Mock()
                from pyomo.opt import SolverStatus
                mock_results.solver.status = SolverStatus.ok
                mock_solver.solve.return_value = mock_results
            else:
                mock_solver.available.return_value = False

            return mock_solver

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect):
            with patch('src.optimization.solver_config.value', return_value=1.0):
                config = SolverConfig()
                results = config.test_all_solvers()

                assert isinstance(results, dict)
                assert 'cbc' in results
                assert 'glpk' in results

    def test_get_working_solvers_after_testing(self):
        """Test getting working solvers after testing."""
        def solver_factory_side_effect(solver_name):
            mock_solver = Mock()
            if solver_name == 'cbc':
                mock_solver.available.return_value = True
                mock_solver.options = {}

                # Mock solve method
                mock_results = Mock()
                from pyomo.opt import SolverStatus
                mock_results.solver.status = SolverStatus.ok
                mock_solver.solve.return_value = mock_results
            else:
                mock_solver.available.return_value = False

            return mock_solver

        with patch('src.optimization.solver_config.SolverFactory',
                   side_effect=solver_factory_side_effect):
            with patch('src.optimization.solver_config.value', return_value=1.0):
                config = SolverConfig()
                config.test_all_solvers()
                working = config.get_working_solvers()

                # Only CBC should be working
                assert 'cbc' in working
                assert 'glpk' not in working


class TestSolverPreference:
    """Tests for solver preference ordering."""

    def test_solver_preference_order(self):
        """Test that solver preference is in expected order."""
        # Preference should be: Gurobi > CPLEX > ASL_CBC > CBC > GLPK
        assert SolverConfig.SOLVER_PREFERENCE[0] == SolverType.GUROBI
        assert SolverConfig.SOLVER_PREFERENCE[1] == SolverType.CPLEX
        assert SolverConfig.SOLVER_PREFERENCE[2] == SolverType.ASL_CBC
        assert SolverConfig.SOLVER_PREFERENCE[3] == SolverType.CBC
        assert SolverConfig.SOLVER_PREFERENCE[4] == SolverType.GLPK


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
