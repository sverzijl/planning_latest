"""Validation utilities for optimization solutions.

Provides strict validation functions to catch data structure issues BEFORE
they cause silent failures or confusing errors downstream.

Design Philosophy: FAIL FAST with DESCRIPTIVE ERRORS
- Detect problems at the source, not at the UI
- Provide actionable error messages
- Prevent silent data corruption
"""

from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)


def validate_dict_has_string_keys(data: Dict[Any, Any], field_name: str) -> None:
    """Validate that all dictionary keys are strings (Pydantic-serializable).

    Pydantic schemas require string keys for JSON serialization. Tuple keys,
    date objects, or other complex types will cause validation errors.

    Args:
        data: Dictionary to validate
        field_name: Name of field for error message

    Raises:
        TypeError: If any keys are not strings, with details on which keys are invalid
    """
    if not isinstance(data, dict):
        raise TypeError(f"{field_name} must be a dict, got {type(data).__name__}")

    non_string_keys = []
    for key in data.keys():
        if not isinstance(key, str):
            non_string_keys.append((key, type(key).__name__))

    if non_string_keys:
        examples = ", ".join(f"{key!r} ({type_name})" for key, type_name in non_string_keys[:3])
        raise TypeError(
            f"{field_name} has {len(non_string_keys)} non-string keys (Pydantic requires strings).\n"
            f"Examples: {examples}\n"
            f"FIX: Convert complex keys to strings before returning.\n"
            f"Example: key = f\"{{node}}|{{product}}|{{state}}\" for tuple (node, product, state)"
        )


def validate_fefo_return_structure(fefo_result: Dict[str, Any]) -> None:
    """Validate FEFO allocation return structure for Pydantic compatibility.

    Catches common issues that cause silent validation failures:
    - Tuple keys in batch_inventory (must be strings)
    - Missing required fields
    - Invalid field types

    Args:
        fefo_result: Return value from apply_fefo_allocation()

    Raises:
        ValueError: If structure is invalid
        TypeError: If field types are incompatible with Pydantic
    """
    required_fields = ['batches', 'batch_objects', 'batch_inventory', 'shipment_allocations']

    # Check required fields exist
    missing = [f for f in required_fields if f not in fefo_result]
    if missing:
        raise ValueError(
            f"FEFO result missing required fields: {missing}\n"
            f"apply_fefo_allocation() must return dict with: {required_fields}"
        )

    # Validate batches is a list
    if not isinstance(fefo_result['batches'], list):
        raise TypeError(
            f"FEFO 'batches' must be list, got {type(fefo_result['batches']).__name__}"
        )

    # Validate batch_inventory has string keys (CRITICAL)
    validate_dict_has_string_keys(fefo_result['batch_inventory'], 'batch_inventory')

    # Validate shipment_allocations is a list
    if not isinstance(fefo_result['shipment_allocations'], list):
        raise TypeError(
            f"FEFO 'shipment_allocations' must be list, got {type(fefo_result['shipment_allocations']).__name__}"
        )

    logger.info(f"FEFO structure validation passed: {len(fefo_result['batches'])} batches, {len(fefo_result['batch_inventory'])} inventory groups")


def validate_solution_dict_for_pydantic(solution_dict: Dict[str, Any]) -> None:
    """Validate solution dictionary structure before Pydantic conversion.

    Catches issues that would cause ValidationError during OptimizationSolution creation:
    - Missing required fields
    - Tuple keys in dict fields
    - Invalid types
    - Inconsistent data

    Args:
        solution_dict: Solution dictionary to validate

    Raises:
        ValueError: If required fields missing or data inconsistent
        TypeError: If field types incompatible with Pydantic
    """
    # Required top-level fields (raw solution_dict format BEFORE Pydantic conversion)
    # Note: 'shipments' is NOT in raw dict - it gets created during conversion
    #       from 'shipments_by_route_product_date'
    required = ['production_batches', 'labor_hours_by_date',
                'total_production', 'fill_rate', 'total_cost']

    missing = [f for f in required if f not in solution_dict]
    if missing:
        raise ValueError(
            f"Solution dict missing required fields: {missing}\n"
            f"extract_solution() must populate: {required}"
        )

    # Validate production_batches is non-empty if total_production > 0
    total_prod = solution_dict.get('total_production', 0)
    batch_count = len(solution_dict.get('production_batches', []))

    if total_prod > 0.01 and batch_count == 0:
        raise ValueError(
            f"Inconsistent data: total_production={total_prod:.0f} but production_batches is empty.\n"
            f"Check that production_batches list is populated in extract_solution()."
        )

    # Validate shipments exist (check both raw format and converted format)
    # Raw format: 'shipments_by_route_product_date' (dict)
    # Converted format: 'shipments' (list)
    shipments_raw = solution_dict.get('shipments_by_route_product_date', {})
    shipments_list = solution_dict.get('shipments', [])

    has_shipments = len(shipments_raw) > 0 or len(shipments_list) > 0

    if total_prod > 0.01 and not has_shipments:
        raise ValueError(
            f"Inconsistent data: total_production={total_prod:.0f} but no shipments found.\n"
            f"Production must be shipped somewhere. Check shipment extraction in extract_solution().\n"
            f"Expected either 'shipments_by_route_product_date' (raw) or 'shipments' (converted)."
        )

    # Validate optional dict fields have Pydantic-compatible keys
    # NOTE: Most dict fields use tuple/date keys and rely on arbitrary_types_allowed
    # Only validate fields that MUST have string keys (like fefo_batch_inventory)
    # This is handled by specific validators, not here

    shipment_count = len(shipments_raw) + len(shipments_list)
    logger.info(
        f"Solution dict validation passed: {batch_count} batches, "
        f"{shipment_count} shipments (raw+converted), fill_rate={solution_dict['fill_rate']:.1%}"
    )


def validate_optimization_solution_complete(solution: 'OptimizationSolution') -> None:
    """Validate OptimizationSolution has complete data for UI display.

    This is a stricter validation than Pydantic schema validation - it checks
    that data is actually usable by UI components, not just schema-compliant.

    Args:
        solution: OptimizationSolution (Pydantic validated)

    Raises:
        ValueError: If solution data is incomplete or inconsistent
    """
    from src.optimization.result_schema import OptimizationSolution

    if not isinstance(solution, OptimizationSolution):
        raise TypeError(
            f"Expected OptimizationSolution, got {type(solution).__name__}\n"
            f"Model must return Pydantic-validated solution."
        )

    errors = []

    # Check production data completeness
    if solution.total_production > 0.01:
        if len(solution.production_batches) == 0:
            errors.append(
                f"total_production={solution.total_production:.0f} but production_batches is empty"
            )

        if len(solution.shipments) == 0:
            errors.append(
                f"total_production={solution.total_production:.0f} but shipments is empty"
            )

        if len(solution.labor_hours_by_date) == 0:
            errors.append(
                f"total_production={solution.total_production:.0f} but labor_hours_by_date is empty"
            )

    # Check batch-production consistency
    batch_sum = sum(b.quantity for b in solution.production_batches)
    if abs(batch_sum - solution.total_production) > 1.0:
        errors.append(
            f"Batch quantity sum ({batch_sum:.0f}) != total_production ({solution.total_production:.0f})"
        )

    # Check model-specific flags
    if solution.model_type == "sliding_window" and not solution.has_aggregate_inventory:
        errors.append(
            "SlidingWindowModel must set has_aggregate_inventory=True"
        )

    if solution.model_type == "unified_node" and not solution.use_batch_tracking:
        errors.append(
            "Models using batch tracking must set use_batch_tracking=True"
        )

    if errors:
        error_msg = "OptimizationSolution has incomplete/inconsistent data:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    logger.info(
        f"OptimizationSolution completeness validated: "
        f"{len(solution.production_batches)} batches, "
        f"{len(solution.shipments)} shipments, "
        f"{len(solution.labor_hours_by_date)} dates, "
        f"fill_rate={solution.fill_rate:.1%}"
    )
