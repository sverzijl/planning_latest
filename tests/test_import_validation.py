"""
Import Validation Tests - Fail Fast on Broken Imports

These tests run BEFORE any other tests to catch import errors immediately.
Prevents breaking changes from reaching the UI.

Based on lesson learned: Overwrote solver_config.py and broke imports.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def test_core_optimization_imports():
    """Validate all core optimization module imports work."""
    try:
        from src.optimization import (
            SolverConfig,
            SolverType,
            SolverInfo,
            get_global_config,
            get_solver,
            BaseOptimizationModel,
            OptimizationResult,
            UnifiedNodeModel,
            LegacyToUnifiedConverter,
        )
        assert True, "Core optimization imports successful"
    except ImportError as e:
        pytest.fail(f"CRITICAL: Core optimization imports broken! {e}")


def test_validation_imports():
    """Validate validation module imports."""
    try:
        from src.validation.planning_data_schema import (
            ValidatedPlanningData,
            ProductID,
            NodeID,
            DemandEntry,
            InventoryEntry,
        )
        from src.validation.data_coordinator import load_validated_data
        from src.validation.network_topology_validator import validate_network_topology
        assert True
    except ImportError as e:
        pytest.fail(f"CRITICAL: Validation imports broken! {e}")


def test_model_imports():
    """Validate model classes import."""
    try:
        from src.models import Product, CostStructure
        from src.models.unified_node import UnifiedNode
        from src.models.unified_route import UnifiedRoute
        from src.models.forecast import Forecast
        assert True
    except ImportError as e:
        pytest.fail(f"CRITICAL: Model imports broken! {e}")


def test_solver_config_completeness():
    """Validate solver_config.py has all required exports."""
    from src.optimization import solver_config

    required = ['SolverConfig', 'SolverType', 'SolverInfo', 'get_global_config', 'get_solver']

    missing = []
    for name in required:
        if not hasattr(solver_config, name):
            missing.append(name)

    if missing:
        pytest.fail(f"solver_config.py missing required exports: {missing}")


def test_verified_model_importable():
    """Validate VerifiedSlidingWindowModel can be imported (if it exists)."""
    try:
        from src.optimization.verified_sliding_window_model import VerifiedSlidingWindowModel
        assert True
    except ImportError:
        # OK if doesn't exist yet
        pytest.skip("VerifiedSlidingWindowModel not yet implemented")


if __name__ == "__main__":
    # Run these tests standalone for quick validation
    print("Running import validation tests...")

    try:
        test_core_optimization_imports()
        print("✓ Core optimization imports")

        test_validation_imports()
        print("✓ Validation imports")

        test_model_imports()
        print("✓ Model imports")

        test_solver_config_completeness()
        print("✓ Solver config complete")

        test_verified_model_importable()
        print("✓ Verified model importable")

        print("\n✅ ALL IMPORTS VALID!")

    except Exception as e:
        print(f"\n❌ IMPORT VALIDATION FAILED: {e}")
        import sys
        sys.exit(1)
