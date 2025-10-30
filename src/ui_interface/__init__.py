"""UI interface validation and adaptation layer.

This module provides validation and adaptation between optimization models
and UI components, ensuring robust data flow with clear error messages.
"""

from .solution_validator import SolutionValidator, UIDataValidationError

__all__ = ['SolutionValidator', 'UIDataValidationError']
