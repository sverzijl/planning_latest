"""UI Tab Requirements Contract.

This module documents and validates what data each UI tab requires to function.
Prevents "No data available" errors by catching missing fields at model boundary.

Design Philosophy:
- Fail-fast: Validate at model→UI boundary, not in UI
- Self-documenting: Requirements are code, not comments
- Comprehensive: Every tab, every chart, every table

Last Updated: 2025-10-30
"""

from typing import List, Dict, Any, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)


class UITabRequirements:
    """Contract: What data each UI tab requires to render successfully.

    This class documents the dependencies between UI components and data fields.
    Use validate() to check if a solution satisfies requirements before rendering.

    Example:
        >>> missing = UITabRequirements.validate(solution, 'LABELING')
        >>> if missing:
        >>>     raise ValueError(f"Cannot render Labeling tab: missing {missing}")
    """

    # Production Tab requirements
    PRODUCTION = {
        'production_batches': {'required': True, 'type': list, 'min_length': 1},
        'labor_hours_by_date': {'required': True, 'type': dict, 'min_length': 1},
        'costs.labor.total': {'required': True, 'type': float, 'min_value': 0},
    }

    # Labeling Tab requirements
    LABELING = {
        'production_by_date_product': {'required': True, 'type': dict, 'min_length': 1},
        'shipments': {'required': True, 'type': list, 'min_length': 1},
        # route_arrival_state comes from model, not solution
    }

    # Distribution Tab requirements
    DISTRIBUTION = {
        'truck_assignments': {'required': False, 'type': dict},  # Optional (may have unassigned)
        'shipments': {'required': True, 'type': list, 'min_length': 1},
        # truck_schedules validated separately (model attribute)
    }

    # Daily Snapshot requirements
    DAILY_SNAPSHOT = {
        'shipments': {'required': True, 'type': list},
        'production_batches': {'required': True, 'type': list},
        # demand_consumed OR cohort_demand_consumption required (validated separately)
        'shortages': {'required': False, 'type': dict},  # Optional
    }

    # Costs Tab requirements
    COSTS_TAB = {
        'costs': {'required': True, 'type': object},
        'costs.total_cost': {'required': True, 'type': float, 'min_value': 0},
        'costs.labor': {'required': True, 'type': object},
        'costs.production': {'required': True, 'type': object},
        'costs.transport': {'required': True, 'type': object},
        'costs.holding': {'required': True, 'type': object},
        'costs.waste': {'required': True, 'type': object},
    }

    # Daily Costs Graph (within Costs Tab)
    DAILY_COSTS_GRAPH = {
        'costs.labor.daily_breakdown': {'required': True, 'type': dict, 'min_length': 1},
        # production.cost_by_date is optional
    }

    # Network Tab requirements
    NETWORK_TAB = {
        'shipments': {'required': True, 'type': list, 'min_length': 1},
        # Locations come from model context, not solution
    }

    @staticmethod
    def validate(solution: Any, tab: str, model: Any = None) -> List[str]:
        """Validate that solution has all required data for UI tab.

        Args:
            solution: OptimizationSolution instance
            tab: Tab name (e.g., 'LABELING', 'DISTRIBUTION')
            model: Optional model instance (for model-level attributes)

        Returns:
            List of missing/invalid requirements (empty if valid)

        Example:
            >>> errors = UITabRequirements.validate(solution, 'LABELING')
            >>> if errors:
            >>>     raise ValueError(f"Labeling tab requirements not met: {errors}")
        """
        requirements = getattr(UITabRequirements, tab.upper(), {})
        if not requirements:
            logger.warning(f"No requirements defined for tab '{tab}'")
            return []

        errors = []

        for field_path, constraints in requirements.items():
            # Navigate nested paths (e.g., 'costs.labor.daily_breakdown')
            obj = solution
            parts = field_path.split('.')

            for i, part in enumerate(parts):
                obj = getattr(obj, part, None)
                if obj is None:
                    if constraints.get('required', False):
                        errors.append(f"Missing required field: {field_path}")
                    break

            # If we got the object, validate constraints
            if obj is not None:
                # Type check
                expected_type = constraints.get('type')
                if expected_type:
                    if expected_type == dict and not isinstance(obj, dict):
                        errors.append(f"{field_path} must be dict, got {type(obj).__name__}")
                    elif expected_type == list and not isinstance(obj, list):
                        errors.append(f"{field_path} must be list, got {type(obj).__name__}")
                    elif expected_type == float and not isinstance(obj, (int, float)):
                        errors.append(f"{field_path} must be numeric, got {type(obj).__name__}")

                # Minimum length check
                min_length = constraints.get('min_length')
                if min_length is not None and hasattr(obj, '__len__'):
                    if len(obj) < min_length:
                        errors.append(f"{field_path} must have at least {min_length} items, got {len(obj)}")

                # Minimum value check
                min_value = constraints.get('min_value')
                if min_value is not None and isinstance(obj, (int, float)):
                    if obj < min_value:
                        errors.append(f"{field_path} must be >= {min_value}, got {obj}")

        # Special case validations
        if tab.upper() == 'DAILY_SNAPSHOT':
            # Must have EITHER demand_consumed OR cohort_demand_consumption
            has_aggregate = hasattr(solution, 'demand_consumed') and solution.demand_consumed
            has_cohort = hasattr(solution, 'cohort_demand_consumption') and solution.cohort_demand_consumption
            if not (has_aggregate or has_cohort):
                errors.append("Daily Snapshot requires either demand_consumed or cohort_demand_consumption")

        return errors

    @staticmethod
    def validate_all_tabs(solution: Any, model: Any = None) -> Dict[str, List[str]]:
        """Validate requirements for ALL UI tabs.

        Args:
            solution: OptimizationSolution instance
            model: Optional model instance

        Returns:
            Dict mapping tab name to list of errors (empty dict if all valid)
        """
        all_tabs = [
            'PRODUCTION',
            'LABELING',
            'DISTRIBUTION',
            'DAILY_SNAPSHOT',
            'COSTS_TAB',
            'DAILY_COSTS_GRAPH',
            'NETWORK_TAB'
        ]

        results = {}
        for tab in all_tabs:
            errors = UITabRequirements.validate(solution, tab, model)
            if errors:
                results[tab] = errors

        return results

    @staticmethod
    def validate_foreign_keys(solution: Any, model: Any = None) -> List[str]:
        """Validate that all IDs reference valid entities (foreign key integrity).

        This catches bugs like truck_id=10 when truck.id='T1'.

        Args:
            solution: OptimizationSolution instance
            model: Optional model instance for reference data

        Returns:
            List of foreign key violations (empty if valid)
        """
        errors = []

        # Validate truck_assignments reference valid truck IDs
        if hasattr(solution, 'truck_assignments') and solution.truck_assignments:
            if model and hasattr(model, 'truck_schedules'):
                valid_truck_ids = {t.id for t in model.truck_schedules}
                for shipment_key, truck_id in solution.truck_assignments.items():
                    if truck_id not in valid_truck_ids:
                        errors.append(
                            f"truck_assignments contains invalid truck_id '{truck_id}'. "
                            f"Valid IDs: {valid_truck_ids}"
                        )

        # Validate shipments reference valid products (if products available)
        if hasattr(solution, 'shipments') and solution.shipments:
            if model and hasattr(model, 'products'):
                valid_products = {p.id for p in model.products}
                for shipment in solution.shipments:
                    if hasattr(shipment, 'product') and shipment.product not in valid_products:
                        errors.append(
                            f"Shipment references invalid product_id '{shipment.product}'"
                        )

        # Validate production_by_date_product keys
        if hasattr(solution, 'production_by_date_product') and solution.production_by_date_product:
            for key in solution.production_by_date_product.keys():
                # Check tuple structure
                if not isinstance(key, tuple):
                    errors.append(f"production_by_date_product key must be tuple, got {type(key)}")
                    continue

                if len(key) != 3:
                    errors.append(
                        f"production_by_date_product key must be (node, product, date), "
                        f"got {len(key)}-tuple: {key}"
                    )
                    continue

                node, product, date_val = key

                # Validate types
                if not isinstance(node, str):
                    errors.append(f"production key node_id must be str, got {type(node)}: {key}")
                if not isinstance(product, str):
                    errors.append(f"production key product_id must be str, got {type(product)}: {key}")
                if not isinstance(date_val, date):
                    errors.append(f"production key date must be date, got {type(date_val)}: {key}")

        return errors


def validate_solution_for_ui(solution: Any, model: Any = None, fail_fast: bool = True) -> None:
    """Comprehensive validation: Checks ALL UI requirements and foreign keys.

    This is the main validation function to call at model→UI boundary.

    Args:
        solution: OptimizationSolution instance
        model: Optional model instance for validation context
        fail_fast: If True, raises ValueError on first error

    Raises:
        ValueError: If validation fails and fail_fast=True

    Example:
        >>> validate_solution_for_ui(solution, model)  # Raises on any issue
    """
    all_errors = {}

    # 1. Validate UI tab requirements
    tab_errors = UITabRequirements.validate_all_tabs(solution, model)
    if tab_errors:
        all_errors['UI Requirements'] = tab_errors

    # 2. Validate foreign key integrity
    fk_errors = UITabRequirements.validate_foreign_keys(solution, model)
    if fk_errors:
        all_errors['Foreign Keys'] = fk_errors

    if all_errors and fail_fast:
        # Format error message
        error_lines = ["Solution validation failed:"]
        for category, errors in all_errors.items():
            error_lines.append(f"\n{category}:")
            if isinstance(errors, dict):
                for tab, tab_errors in errors.items():
                    error_lines.append(f"  {tab}:")
                    for err in tab_errors:
                        error_lines.append(f"    - {err}")
            else:
                for err in errors:
                    error_lines.append(f"  - {err}")

        raise ValueError("\n".join(error_lines))

    if all_errors:
        logger.warning(f"Solution validation found issues: {all_errors}")
