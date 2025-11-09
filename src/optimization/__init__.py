"""Optimization module for production-distribution planning.

This module provides Pyomo-based mathematical optimization models for
integrated production scheduling and distribution planning.

The primary model is SlidingWindowModel, which uses state-based aggregate flows
with sliding window shelf life constraints. It provides 60-80× speedup over
cohort-tracking approaches while maintaining exact shelf life enforcement.
Validated to solve 4-week horizons in 5-7 seconds with APPSI HiGHS solver.
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
from .sliding_window_model import (
    SlidingWindowModel,
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
    # Sliding window model (production model)
    "SlidingWindowModel",
]
