"""Optimization module for production-distribution planning.

This module provides Pyomo-based mathematical optimization models for
integrated production scheduling and distribution planning.

The primary model is UnifiedNodeModel, which uses a clean node-based architecture
with no virtual locations and generalized truck constraints. It solves
the full planning horizon with proper weekend enforcement and state transitions.
Validated to solve 4-week horizons in < 30 seconds with modern MIP solvers like CBC.
"""

from .solver_config import (
    SolverConfig,
    SolverType,
    SolverInfo,
    get_global_config,
    get_solver,
)
from .base_model import (
    BaseOptimizationModel,
    OptimizationResult,
)
from .unified_node_model import (
    UnifiedNodeModel,
)
from .legacy_to_unified_converter import (
    LegacyToUnifiedConverter,
)

__all__ = [
    # Solver configuration
    "SolverConfig",
    "SolverType",
    "SolverInfo",
    "get_global_config",
    "get_solver",
    # Base model
    "BaseOptimizationModel",
    "OptimizationResult",
    # Unified node model (primary model)
    "UnifiedNodeModel",
    # Data conversion utility
    "LegacyToUnifiedConverter",
]
