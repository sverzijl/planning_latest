"""
Shelf life calculation engine for perishable products.

This module handles product state tracking (frozen/ambient/thawed),
aging through network routes, and shelf life business rules.
"""

from .state import ProductState, ShelfLifeInfo
from .rules import ShelfLifeRules, ShelfLifeValidationResult
from .tracker import ShelfLifeTracker, RouteLeg, RouteSegmentState

__all__ = [
    'ProductState',
    'ShelfLifeInfo',
    'ShelfLifeRules',
    'ShelfLifeValidationResult',
    'ShelfLifeTracker',
    'RouteLeg',
    'RouteSegmentState',
]
