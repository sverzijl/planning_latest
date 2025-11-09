"""Centralized constants for optimization models.

This module contains all hardcoded constants used across optimization models,
including shelf life durations, packaging constraints, and production parameters.
Centralizing these values ensures consistency and makes them easy to update.
"""

# ============================================================================
# SHELF LIFE CONSTANTS (days)
# ============================================================================

#: Shelf life for products stored in ambient (room temperature) conditions
AMBIENT_SHELF_LIFE_DAYS = 17

#: Shelf life for products stored in frozen conditions
FROZEN_SHELF_LIFE_DAYS = 120

#: Shelf life after thawing (frozen → ambient transition)
#: Critical for WA route (6130) which receives frozen and thaws on-site
THAWED_SHELF_LIFE_DAYS = 14

#: Minimum acceptable shelf life at breadroom (breadroom policy)
#: Breadrooms discard stock with less than this many days remaining
MINIMUM_ACCEPTABLE_SHELF_LIFE_DAYS = 7


# ============================================================================
# PACKAGING CONSTANTS
# ============================================================================

#: Number of individual units per case
#: All production and shipping must be in multiples of cases (no partial cases)
UNITS_PER_CASE = 10

#: Number of cases per pallet
CASES_PER_PALLET = 32

#: Number of units per pallet (derived: UNITS_PER_CASE × CASES_PER_PALLET)
#: Used for pallet-based cost calculations and storage constraints
UNITS_PER_PALLET = 320

#: Number of pallets per truck
#: Standard truck capacity constraint
PALLETS_PER_TRUCK = 44

#: Number of units per truck (derived: UNITS_PER_PALLET × PALLETS_PER_TRUCK)
#: Maximum units that can be loaded on a single truck
UNITS_PER_TRUCK = 14_080


# ============================================================================
# PRODUCTION CONSTANTS
# ============================================================================

#: Production rate at manufacturing site (units per hour)
#: Used to convert labor hours to production capacity
PRODUCTION_RATE_UNITS_PER_HOUR = 1_400

#: Maximum regular hours per weekday (Monday-Friday)
#: Fixed labor capacity before overtime kicks in
REGULAR_HOURS_PER_WEEKDAY = 12

#: Maximum overtime hours per weekday
#: Additional capacity beyond regular hours at premium rate
MAX_OVERTIME_HOURS_PER_WEEKDAY = 2

#: Total maximum hours per weekday (regular + overtime)
MAX_HOURS_PER_WEEKDAY = 14

#: Minimum payment hours for non-fixed days (weekends/holidays)
#: Even if production is less, labor must be paid for at least this many hours
MIN_HOURS_NON_FIXED_DAYS = 4

#: Startup time per production day (hours)
#: Fixed overhead for starting production
STARTUP_TIME_HOURS = 0.5

#: Shutdown time per production day (hours)
#: Fixed overhead for ending production
SHUTDOWN_TIME_HOURS = 0.5

#: Changeover time per product switch (hours)
#: Time required when switching from one SKU to another
CHANGEOVER_TIME_HOURS = 0.0  # Currently modeled as zero; future enhancement


# ============================================================================
# DERIVED CONSTANTS
# ============================================================================

#: Maximum production capacity per weekday (regular hours only)
#: REGULAR_HOURS_PER_WEEKDAY × PRODUCTION_RATE_UNITS_PER_HOUR
MAX_PRODUCTION_REGULAR_PER_DAY = 16_800

#: Maximum production capacity per weekday (with overtime)
#: MAX_HOURS_PER_WEEKDAY × PRODUCTION_RATE_UNITS_PER_HOUR
MAX_PRODUCTION_WITH_OT_PER_DAY = 19_600

#: Maximum weekly production capacity (5 weekdays, regular hours only)
#: Assumes Mon-Fri production, no weekends
MAX_PRODUCTION_REGULAR_PER_WEEK = 84_000

#: Maximum weekly production capacity (5 weekdays with daily overtime)
MAX_PRODUCTION_WITH_OT_PER_WEEK = 98_000


# ============================================================================
# STATE CONSTANTS
# ============================================================================

#: Product storage/transport states
STATE_AMBIENT = "ambient"
STATE_FROZEN = "frozen"
STATE_THAWED = "thawed"

#: All valid states
VALID_STATES = [STATE_AMBIENT, STATE_FROZEN, STATE_THAWED]


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_shelf_life(state: str, days: int) -> bool:
    """Validate that remaining shelf life is acceptable for given state.

    Args:
        state: Product state (ambient, frozen, or thawed)
        days: Remaining shelf life in days

    Returns:
        True if shelf life is within valid range for state

    Raises:
        ValueError: If state is not recognized
    """
    if state == STATE_AMBIENT:
        return 0 <= days <= AMBIENT_SHELF_LIFE_DAYS
    elif state == STATE_FROZEN:
        return 0 <= days <= FROZEN_SHELF_LIFE_DAYS
    elif state == STATE_THAWED:
        return 0 <= days <= THAWED_SHELF_LIFE_DAYS
    else:
        raise ValueError(f"Invalid state: {state}. Must be one of {VALID_STATES}")


def is_acceptable_for_breadroom(days_remaining: int) -> bool:
    """Check if product has acceptable shelf life for breadroom delivery.

    Args:
        days_remaining: Shelf life remaining in days

    Returns:
        True if acceptable (≥ minimum policy), False otherwise
    """
    return days_remaining >= MINIMUM_ACCEPTABLE_SHELF_LIFE_DAYS


def get_max_shelf_life(state: str) -> int:
    """Get maximum shelf life for given state.

    Args:
        state: Product state (ambient, frozen, or thawed)

    Returns:
        Maximum shelf life in days

    Raises:
        ValueError: If state is not recognized
    """
    if state == STATE_AMBIENT:
        return AMBIENT_SHELF_LIFE_DAYS
    elif state == STATE_FROZEN:
        return FROZEN_SHELF_LIFE_DAYS
    elif state == STATE_THAWED:
        return THAWED_SHELF_LIFE_DAYS
    else:
        raise ValueError(f"Invalid state: {state}. Must be one of {VALID_STATES}")


# ============================================================================
# USAGE NOTES
# ============================================================================

"""
IMPORTANT: When adding new constants:

1. Choose the appropriate section (Shelf Life, Packaging, Production, etc.)
2. Use ALL_CAPS naming convention
3. Add a docstring comment explaining the constant
4. Include units in the name or comment (e.g., _DAYS, _HOURS, _UNITS)
5. If derived from other constants, document the formula
6. Update tests if the constant affects optimization behavior

Example:
    # New constant for minimum batch size
    MIN_BATCH_SIZE_UNITS = 1_000  # Minimum production batch (units)
"""
