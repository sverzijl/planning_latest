"""Solver configuration and detection for cross-platform optimization.

This module provides automatic solver detection and configuration
for Windows, Linux, and macOS platforms.
"""

import os
import platform
import shutil
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass

from pyomo.opt import SolverFactory, SolverStatus
from pyomo.environ import ConcreteModel, Var, Objective, Constraint, NonNegativeReals, value, minimize


class SolverType(str, Enum):
    """Supported solver types."""
    ASL_CBC = "asl:cbc"  # AMPL interface (preferred for CBC 2.10.12+)
    CBC = "cbc"          # Direct interface (may have issues with CBC 2.10.12+)
    GLPK = "glpk"
    HIGHS = "highs"      # HiGHS open-source solver (fast, comparable to Gurobi)
    GUROBI = "gurobi"
    CPLEX = "cplex"


@dataclass
class SolverInfo:
    """
    Information about an available solver.

    Attributes:
        name: Solver name (e.g., 'cbc', 'glpk')
        available: Whether solver is available
        version: Solver version string (if detectable)
        path: Full path to solver executable
        tested: Whether solver has been tested with a simple problem
        works: Whether solver successfully solved test problem
    """
    name: str
    available: bool
    version: Optional[str] = None
    path: Optional[str] = None
    tested: bool = False
    works: bool = False

    def __str__(self) -> str:
        """String representation."""
        status = "✓ available" if self.available else "✗ unavailable"
        if self.works:
            status += " (tested)"
        return f"{self.name.upper()}: {status}"


class SolverConfig:
    """
    Cross-platform solver configuration and detection.

    This class automatically detects available solvers, tests them,
    and provides utilities for solver selection and configuration.

    Example:
        # Get best available solver
        config = SolverConfig()
        solver_name = config.get_best_available_solver()
        solver = config.create_solver(solver_name)

        # Check what's available
        available = config.get_available_solvers()
        print(f"Available solvers: {available}")

        # Test all solvers
        config.test_all_solvers()
        config.print_solver_status()
    """

    # Solver preference order (best to worst for this application)
    SOLVER_PREFERENCE = [
        SolverType.GUROBI,   # Commercial, fastest
        SolverType.CPLEX,    # Commercial, very fast
        SolverType.HIGHS,    # Open source, performance comparable to Gurobi (2024 benchmarks)
        SolverType.ASL_CBC,  # Open source via AMPL interface (best for CBC 2.10.12+)
        SolverType.CBC,      # Open source direct (may fail with CBC 2.10.12+)
        SolverType.GLPK,     # Open source, slower but widely available
    ]

    def __init__(self):
        """Initialize solver configuration."""
        self._solver_info: Dict[str, SolverInfo] = {}
        self._detect_solvers()

    def _detect_solvers(self) -> None:
        """Detect available solvers on the system."""
        for solver_type in SolverType:
            self._solver_info[solver_type.value] = self._check_solver(solver_type.value)

    def _check_solver(self, solver_name: str) -> SolverInfo:
        """
        Check if a specific solver is available.

        Args:
            solver_name: Name of solver (e.g., 'cbc', 'glpk')

        Returns:
            SolverInfo with availability details
        """
        try:
            solver = SolverFactory(solver_name)
            available = solver.available()

            # Try to find executable path
            path = None
            if available:
                # Try to get path from various sources
                if hasattr(solver, 'executable'):
                    path = solver.executable()
                elif hasattr(solver, '_executable'):
                    path = solver._executable
                else:
                    # Try to find in PATH
                    path = shutil.which(solver_name)

            return SolverInfo(
                name=solver_name,
                available=available,
                path=path
            )
        except Exception as e:
            return SolverInfo(
                name=solver_name,
                available=False
            )

    def test_solver(self, solver_name: str, verbose: bool = False) -> bool:
        """
        Test if solver can solve a simple optimization problem.

        Args:
            solver_name: Name of solver to test
            verbose: If True, print detailed output

        Returns:
            True if solver successfully solved test problem

        Example:
            config = SolverConfig()
            if config.test_solver('cbc', verbose=True):
                print("CBC works!")
        """
        if solver_name not in self._solver_info:
            if verbose:
                print(f"Solver {solver_name} not found")
            return False

        info = self._solver_info[solver_name]
        if not info.available:
            if verbose:
                print(f"Solver {solver_name} is not available")
            return False

        try:
            # Create simple test problem: minimize x subject to x >= 1
            model = ConcreteModel()
            model.x = Var(within=NonNegativeReals)
            model.obj = Objective(expr=model.x, sense=minimize)
            model.con = Constraint(expr=model.x >= 1)

            # Create solver and solve
            solver = SolverFactory(solver_name)
            # Use symbolic_solver_labels=False for CBC 2.10.12+ compatibility
            results = solver.solve(model, tee=verbose, symbolic_solver_labels=False)

            # Check if solved successfully
            success = (
                results.solver.status == SolverStatus.ok
                and abs(value(model.x) - 1.0) < 1e-5
            )

            # Update solver info
            info.tested = True
            info.works = success

            if verbose:
                if success:
                    print(f"✓ {solver_name.upper()} successfully solved test problem")
                    print(f"  Solution: x = {value(model.x):.6f} (expected: 1.0)")
                else:
                    print(f"✗ {solver_name.upper()} failed to solve test problem")
                    print(f"  Status: {results.solver.status}")
                    print(f"  Termination: {results.solver.termination_condition}")

            return success

        except Exception as e:
            if verbose:
                print(f"✗ {solver_name.upper()} error: {e}")

            info.tested = True
            info.works = False
            return False

    def test_all_solvers(self, verbose: bool = False) -> Dict[str, bool]:
        """
        Test all available solvers.

        Args:
            verbose: If True, print detailed output for each solver

        Returns:
            Dictionary mapping solver names to test results (True if works)

        Example:
            config = SolverConfig()
            results = config.test_all_solvers(verbose=True)
            working_solvers = [name for name, works in results.items() if works]
        """
        results = {}
        for solver_name in self._solver_info.keys():
            if self._solver_info[solver_name].available:
                results[solver_name] = self.test_solver(solver_name, verbose=verbose)
            else:
                results[solver_name] = False
        return results

    def get_available_solvers(self) -> List[str]:
        """
        Get list of available solver names.

        Returns:
            List of solver names that are available

        Example:
            config = SolverConfig()
            available = config.get_available_solvers()
            print(f"Available: {available}")  # e.g., ['cbc', 'glpk']
        """
        return [
            name for name, info in self._solver_info.items()
            if info.available
        ]

    def get_working_solvers(self) -> List[str]:
        """
        Get list of solver names that have been tested and work.

        Returns:
            List of solver names that successfully solved test problem

        Note:
            Solvers must be tested first using test_solver() or test_all_solvers()

        Example:
            config = SolverConfig()
            config.test_all_solvers()
            working = config.get_working_solvers()
        """
        return [
            name for name, info in self._solver_info.items()
            if info.tested and info.works
        ]

    def get_best_available_solver(
        self,
        test_if_needed: bool = True,
        verbose: bool = False
    ) -> str:
        """
        Get the best available solver based on preference order.

        Args:
            test_if_needed: If True, test solvers that haven't been tested yet
            verbose: If True, print information about solver selection

        Returns:
            Name of best available solver

        Raises:
            RuntimeError: If no solver is available

        Example:
            config = SolverConfig()
            solver_name = config.get_best_available_solver()
            # Returns 'gurobi' if available, else 'cplex', else 'cbc', else 'glpk'
        """
        for solver_type in self.SOLVER_PREFERENCE:
            solver_name = solver_type.value
            if solver_name in self._solver_info:
                info = self._solver_info[solver_name]
                if info.available:
                    # Test if needed
                    if test_if_needed and not info.tested:
                        self.test_solver(solver_name, verbose=verbose)

                    # Use it if it works (or if testing is disabled)
                    if not test_if_needed or info.works:
                        if verbose:
                            print(f"Selected solver: {solver_name.upper()}")
                        return solver_name

        # No solver available
        raise RuntimeError(
            "No optimization solver available. "
            "Please install CBC or GLPK. "
            "See docs/SOLVER_INSTALLATION.md for instructions."
        )

    def create_solver(
        self,
        solver_name: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ):
        """
        Create a solver instance.

        Args:
            solver_name: Name of solver to create. If None, uses best available.
            options: Dictionary of solver options to set

        Returns:
            Pyomo SolverFactory instance

        Raises:
            RuntimeError: If solver is not available

        Example:
            config = SolverConfig()

            # Use best available solver
            solver = config.create_solver()

            # Use specific solver with options
            solver = config.create_solver(
                'cbc',
                options={'sec': 300, 'ratio': 0.01}
            )
        """
        if solver_name is None:
            solver_name = self.get_best_available_solver()

        if solver_name not in self._solver_info:
            raise RuntimeError(f"Unknown solver: {solver_name}")

        info = self._solver_info[solver_name]
        if not info.available:
            raise RuntimeError(
                f"Solver {solver_name} is not available. "
                f"See docs/SOLVER_INSTALLATION.md for installation instructions."
            )

        solver = SolverFactory(solver_name)

        # Set options if provided
        if options:
            for key, value in options.items():
                solver.options[key] = value

        return solver

    def get_solver_info(self, solver_name: str) -> Optional[SolverInfo]:
        """
        Get information about a specific solver.

        Args:
            solver_name: Name of solver

        Returns:
            SolverInfo object, or None if solver not found

        Example:
            config = SolverConfig()
            info = config.get_solver_info('cbc')
            print(f"CBC path: {info.path}")
        """
        return self._solver_info.get(solver_name)

    def print_solver_status(self) -> None:
        """
        Print status of all solvers.

        Example:
            config = SolverConfig()
            config.test_all_solvers()
            config.print_solver_status()

            # Output:
            # Solver Status:
            # CBC: ✓ available (tested)
            # GLPK: ✓ available (tested)
            # GUROBI: ✗ unavailable
            # CPLEX: ✗ unavailable
        """
        print("Solver Status:")
        print("-" * 50)
        for solver_name in [s.value for s in SolverType]:
            if solver_name in self._solver_info:
                info = self._solver_info[solver_name]
                print(f"  {info}")
        print("-" * 50)

        available = self.get_available_solvers()
        if available:
            print(f"Available solvers: {', '.join(available)}")
        else:
            print("⚠️  No solvers available! Please install CBC or GLPK.")
            print("   See docs/SOLVER_INSTALLATION.md")

    def get_platform_info(self) -> Dict[str, str]:
        """
        Get information about the current platform.

        Returns:
            Dictionary with platform information

        Example:
            config = SolverConfig()
            info = config.get_platform_info()
            print(f"Running on {info['system']} {info['machine']}")
        """
        return {
            'system': platform.system(),       # 'Linux', 'Darwin', 'Windows'
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),     # 'x86_64', 'AMD64', etc.
            'python_version': platform.python_version(),
        }

    def print_platform_info(self) -> None:
        """
        Print platform information.

        Example:
            config = SolverConfig()
            config.print_platform_info()
        """
        info = self.get_platform_info()
        print("Platform Information:")
        print("-" * 50)
        print(f"  OS: {info['system']} {info['release']}")
        print(f"  Machine: {info['machine']}")
        print(f"  Python: {info['python_version']}")
        print("-" * 50)


# Global instance for convenience
_global_config: Optional[SolverConfig] = None


def get_global_config() -> SolverConfig:
    """
    Get global solver configuration instance (singleton).

    Returns:
        Global SolverConfig instance

    Example:
        from src.optimization.solver_config import get_global_config

        config = get_global_config()
        solver = config.create_solver()
    """
    global _global_config
    if _global_config is None:
        _global_config = SolverConfig()
    return _global_config


def get_solver(
    solver_name: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None
):
    """
    Convenience function to get a solver using global config.

    Args:
        solver_name: Name of solver, or None for best available
        options: Dictionary of solver options

    Returns:
        Pyomo solver instance

    Example:
        from src.optimization.solver_config import get_solver

        # Get best available solver
        solver = get_solver()

        # Get specific solver with options
        solver = get_solver('cbc', options={'sec': 300})
    """
    config = get_global_config()
    return config.create_solver(solver_name, options)


if __name__ == "__main__":
    """
    Test script for solver configuration.

    Run this to check which solvers are available on your system:
        python -m src.optimization.solver_config
    """
    print("=" * 60)
    print("Optimization Solver Configuration Test")
    print("=" * 60)
    print()

    # Create config and show platform info
    config = SolverConfig()
    config.print_platform_info()
    print()

    # Test all solvers
    print("Testing all solvers...")
    print()
    config.test_all_solvers(verbose=True)
    print()

    # Show summary
    config.print_solver_status()
    print()

    # Try to get best solver
    try:
        best = config.get_best_available_solver(verbose=True)
        print()
        print(f"✓ Best available solver: {best.upper()}")
        print()
        print("Your system is ready for optimization!")
    except RuntimeError as e:
        print()
        print(f"✗ Error: {e}")
        print()
        print("Please install a solver. See docs/SOLVER_INSTALLATION.md")

    print()
    print("=" * 60)
