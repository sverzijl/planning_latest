"""Optimization module for production-distribution planning.

This module provides Pyomo-based mathematical optimization models for
integrated production scheduling and distribution planning.

The primary model is IntegratedProductionDistributionModel, which solves
the full planning horizon (e.g., 29 weeks) as a monolithic optimization problem.
This approach has been validated to solve optimally in ~2 minutes for realistic
problem sizes with modern MIP solvers like CBC.
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
from .production_model import (
    ProductionOptimizationModel,
)
from .route_enumerator import (
    RouteEnumerator,
    EnumeratedRoute,
)
from .integrated_model import (
    IntegratedProductionDistributionModel,
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
    # Production optimization
    "ProductionOptimizationModel",
    # Integrated production-distribution
    "IntegratedProductionDistributionModel",
    # Route enumeration
    "RouteEnumerator",
    "EnumeratedRoute",
]
