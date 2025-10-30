"""Type aliases for optimization models.

This module defines semantic types and structured aliases to replace
permissive Dict[Any, Any] types throughout the codebase.

Goals:
1. Self-documenting tuple structures
2. Type safety (catch errors at compile time)
3. IDE support (autocomplete, navigation)
4. Foreign key semantics (TruckID vs ProductID)

Design Philosophy:
- NewType for semantic IDs (prevents mixing TruckID with ProductID)
- Tuple type aliases for documented structures
- Dict type aliases for common patterns
- Backward compatible (doesn't break existing code)

Usage Example:
    from src.optimization.types import ProductionKey, TruckID

    production: Dict[ProductionKey, float] = {
        ('6122', 'PRODUCT_A', date(2025, 10, 30)): 1000.0
    }

    truck_id: TruckID = TruckID('T1')  # Type checked!

Last Updated: 2025-10-30
"""

from typing import NewType, Tuple, Dict, Any
from datetime import date as Date

# ============================================================================
# Semantic ID Types
# ============================================================================
# These create distinct types to prevent mixing different kinds of IDs

NodeID = NewType('NodeID', str)
"""Node identifier (e.g., '6122', '6104').

Distinct from ProductID to prevent passing product ID where node ID expected.
"""

ProductID = NewType('ProductID', str)
"""Product identifier (e.g., 'HELGAS GFREE MIXED GRAIN 500G').

Distinct from NodeID to prevent ID confusion.
"""

TruckID = NewType('TruckID', str)
"""Truck schedule identifier (e.g., 'T1', 'T2').

CRITICAL: Must be string, not integer.
Common bug: Using truck index (0, 1, 2) instead of truck.id ('T1', 'T2').
"""

RouteID = NewType('RouteID', str)
"""Route identifier (typically '{origin}→{destination}').

Used for route naming and display.
"""

# ============================================================================
# Tuple Key Type Aliases
# ============================================================================
# Document the structure of tuple keys used throughout the codebase

ProductionKey = Tuple[str, str, Date]
"""Production batch identifier: (node_id, product_id, date).

Example:
    ('6122', 'HELGAS GFREE MIXED GRAIN 500G', date(2025, 10, 30))

Used in:
- production_by_date_product: Dict[ProductionKey, float]
- Production variable indexing

CRITICAL: Must be 3-tuple (node, product, date), NOT 2-tuple (date, product).
Common bug: Code expecting (date, product) when data is (node, product, date).
"""

ShipmentKey = Tuple[str, str, str, Date]
"""Shipment identifier: (origin, destination, product_id, delivery_date).

Example:
    ('6122', '6104', 'HELGAS GFREE MIXED GRAIN 500G', date(2025, 10, 31))

Used in:
- shipments_by_route_product_date: Dict[ShipmentKey, float]
- truck_assignments: Dict[ShipmentKey, TruckID]
"""

DemandKey = Tuple[str, str, Date]
"""Demand identifier: (node_id, product_id, date).

Example:
    ('6104', 'HELGAS GFREE MIXED GRAIN 500G', date(2025, 10, 30))

Used in:
- demand_consumed: Dict[DemandKey, float]
- shortages: Dict[DemandKey, float]
"""

InventoryKey = Tuple[str, str, Date, str]
"""Inventory cohort identifier: (node_id, product_id, date, state).

Example:
    ('6104', 'HELGAS GFREE MIXED GRAIN 500G', date(2025, 10, 30), 'ambient')

Used in:
- inventory_state: Dict[InventoryKey, float]
- Cohort tracking models

State is one of: 'ambient', 'frozen', 'thawed'
"""

CohortDemandKey = Tuple[str, str, Date, Date]
"""Cohort demand consumption identifier: (node_id, product_id, prod_date, demand_date).

Example:
    ('6104', 'HELGAS GFREE MIXED GRAIN 500G', date(2025, 10, 28), date(2025, 10, 30))

Used in:
- cohort_demand_consumption: Dict[CohortDemandKey, float]
- Batch tracking models only

prod_date: When product was produced
demand_date: When demand was satisfied
"""

LegKey = Tuple[str, str]
"""Route leg identifier: (origin, destination).

Example:
    ('6122', '6104')

Used in:
- route_arrival_state: Dict[LegKey, str]  # 'frozen' or 'ambient'
- leg_states mapping
"""

# ============================================================================
# Typed Dict Aliases
# ============================================================================
# Replace Dict[Any, Any] with self-documenting typed dicts

ProductionDict = Dict[ProductionKey, float]
"""Production quantities by (node, product, date).

Maps production batch identifier to quantity produced.
"""

ShipmentDict = Dict[ShipmentKey, float]
"""Shipment quantities by (origin, dest, product, delivery_date).

Maps shipment identifier to quantity shipped.
"""

DemandConsumedDict = Dict[DemandKey, float]
"""Demand consumed from inventory by (node, product, date).

Maps demand identifier to quantity consumed (satisfied).
Used by aggregate models (SlidingWindowModel).
"""

ShortagesDict = Dict[DemandKey, float]
"""Unmet demand by (node, product, date).

Maps demand identifier to shortage quantity.
"""

TruckAssignmentsDict = Dict[ShipmentKey, str]
"""Truck assignments by shipment.

Maps shipment identifier to truck_id string.

CRITICAL: Values must be truck.id strings ('T1', 'T2'), NOT indices (0, 1).
Common bug: Assigning truck index instead of truck.id.
"""

RouteStateDict = Dict[LegKey, str]
"""Route arrival state by leg.

Maps (origin, destination) to arrival state: 'frozen', 'ambient', or 'thawed'.

Example:
    {
        ('6122', 'Lineage'): 'frozen',
        ('6122', '6104'): 'ambient',
    }
"""

CohortConsumptionDict = Dict[CohortDemandKey, float]
"""Cohort demand consumption by (node, product, prod_date, demand_date).

Maps cohort consumption identifier to quantity consumed.
Used by batch tracking models (UnifiedNodeModel).
"""

LaborHoursDict = Dict[Date, Dict[str, float]]
"""Labor hours breakdown by date.

Maps date to nested dict with:
- 'used': float - Hours actually used
- 'paid': float - Hours paid (including minimums)
- 'fixed': float - Fixed hours (weekday regular)
- 'overtime': float - Overtime hours
- 'non_fixed': float - Non-fixed hours (weekends/holidays)
- 'total_cost': float - Total labor cost for that day
"""

# ============================================================================
# Type Guards
# ============================================================================

def is_valid_production_key(key: Any) -> bool:
    """Check if key is valid ProductionKey.

    Args:
        key: Value to check

    Returns:
        True if key is (str, str, date) tuple

    Example:
        >>> is_valid_production_key(('6122', 'PRODUCT', date(2025, 10, 30)))
        True
        >>> is_valid_production_key((date(2025, 10, 30), 'PRODUCT'))
        False
    """
    if not isinstance(key, tuple):
        return False
    if len(key) != 3:
        return False
    node, product, date_val = key
    return (isinstance(node, str) and
            isinstance(product, str) and
            isinstance(date_val, Date))


def is_valid_shipment_key(key: Any) -> bool:
    """Check if key is valid ShipmentKey.

    Args:
        key: Value to check

    Returns:
        True if key is (str, str, str, date) tuple
    """
    if not isinstance(key, tuple):
        return False
    if len(key) != 4:
        return False
    origin, dest, product, date_val = key
    return (isinstance(origin, str) and
            isinstance(dest, str) and
            isinstance(product, str) and
            isinstance(date_val, Date))


def is_valid_demand_key(key: Any) -> bool:
    """Check if key is valid DemandKey.

    Args:
        key: Value to check

    Returns:
        True if key is (str, str, date) tuple
    """
    if not isinstance(key, tuple):
        return False
    if len(key) != 3:
        return False
    node, product, date_val = key
    return (isinstance(node, str) and
            isinstance(product, str) and
            isinstance(date_val, Date))


# ============================================================================
# Conversion Utilities
# ============================================================================

def normalize_production_key(key: Any) -> ProductionKey:
    """Normalize production key to standard 3-tuple format.

    Handles legacy formats:
    - 2-tuple (date, product) → raises ValueError
    - 3-tuple (node, product, date) → validated and returned

    Args:
        key: Production key to normalize

    Returns:
        Validated ProductionKey

    Raises:
        ValueError: If key format is invalid

    Example:
        >>> normalize_production_key(('6122', 'PRODUCT', date(2025, 10, 30)))
        ('6122', 'PRODUCT', datetime.date(2025, 10, 30))
    """
    if not isinstance(key, tuple):
        raise ValueError(f"Production key must be tuple, got {type(key)}")

    if len(key) == 2:
        raise ValueError(
            f"Production key must be 3-tuple (node, product, date), got 2-tuple: {key}. "
            "Legacy format no longer supported."
        )

    if len(key) != 3:
        raise ValueError(
            f"Production key must be 3-tuple (node, product, date), got {len(key)}-tuple: {key}"
        )

    if not is_valid_production_key(key):
        raise ValueError(f"Invalid production key types: {key}")

    return key  # type: ignore


def validate_truck_assignment(truck_id: Any, valid_truck_ids: set) -> str:
    """Validate truck_id is a string and references a valid truck.

    Args:
        truck_id: Truck identifier to validate
        valid_truck_ids: Set of valid truck.id values

    Returns:
        Validated truck_id as string

    Raises:
        ValueError: If truck_id is invalid

    Example:
        >>> validate_truck_assignment('T1', {'T1', 'T2'})
        'T1'
        >>> validate_truck_assignment(10, {'T1', 'T2'})
        ValueError: truck_id must be string, got int: 10
    """
    if not isinstance(truck_id, str):
        raise ValueError(f"truck_id must be string, got {type(truck_id).__name__}: {truck_id}")

    if truck_id not in valid_truck_ids:
        raise ValueError(
            f"truck_id '{truck_id}' not found in valid trucks. "
            f"Valid IDs: {sorted(valid_truck_ids)}"
        )

    return truck_id


# ============================================================================
# Documentation
# ============================================================================

__all__ = [
    # Semantic ID types
    'NodeID',
    'ProductID',
    'TruckID',
    'RouteID',

    # Tuple key types
    'ProductionKey',
    'ShipmentKey',
    'DemandKey',
    'InventoryKey',
    'CohortDemandKey',
    'LegKey',

    # Dict type aliases
    'ProductionDict',
    'ShipmentDict',
    'DemandConsumedDict',
    'ShortagesDict',
    'TruckAssignmentsDict',
    'RouteStateDict',
    'CohortConsumptionDict',
    'LaborHoursDict',

    # Type guards
    'is_valid_production_key',
    'is_valid_shipment_key',
    'is_valid_demand_key',

    # Utilities
    'normalize_production_key',
    'validate_truck_assignment',
]
