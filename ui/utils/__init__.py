"""UI utility functions."""

from .result_adapter import adapt_optimization_results


def extract_labor_hours(hours_value, default=0.0):
    """Extract numeric labor hours from dict or numeric format.

    Handles both piecewise labor cost format (dict) and legacy numeric format.

    Formats supported:
    - NEW FORMAT (piecewise): {'used': X, 'paid': Y, 'fixed': Z, 'overtime': W}
    - OLD FORMAT (numeric): X (float or int)
    - None values (returns default)

    Args:
        hours_value: Either dict with 'used' key, numeric value, or None
        default: Default value if hours_value is None or invalid

    Returns:
        Float representing labor hours used

    Examples:
        >>> extract_labor_hours({'used': 12.5, 'paid': 12.5, 'fixed': 12.0, 'overtime': 0.5})
        12.5
        >>> extract_labor_hours(12.5)
        12.5
        >>> extract_labor_hours(None)
        0.0
        >>> extract_labor_hours(None, default=10.0)
        10.0
    """
    if hours_value is None:
        return default

    # Check if Pydantic LaborHoursBreakdown object
    if hasattr(hours_value, 'used'):
        # Pydantic LaborHoursBreakdown object
        return hours_value.used

    if isinstance(hours_value, dict):
        # NEW FORMAT: extract 'used' hours
        return hours_value.get('used', default)

    # OLD FORMAT: numeric value
    try:
        return float(hours_value)
    except (ValueError, TypeError):
        return default


__all__ = ['adapt_optimization_results', 'extract_labor_hours']
