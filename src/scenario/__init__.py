"""Scenario management module for planning application.

This module provides functionality for saving, loading, comparing, and managing
multiple planning scenarios. It enables "what-if" analysis and scenario comparison.
"""

from .manager import (
    Scenario,
    ScenarioManager,
)

__all__ = [
    "Scenario",
    "ScenarioManager",
]
