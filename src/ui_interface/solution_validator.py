"""Validation layer for OptimizationSolution → UI data flow.

Ensures OptimizationSolution has ALL required data for UI tabs.
Fails fast with clear error messages if data is missing or incorrect.
"""

from typing import List
from src.optimization.result_schema import OptimizationSolution


class UIDataValidationError(Exception):
    """Raised when OptimizationSolution is missing required data for UI."""
    pass


class SolutionValidator:
    """Validates OptimizationSolution has complete data for all UI tabs."""

    @staticmethod
    def validate_for_production_tab(solution: OptimizationSolution) -> List[str]:
        """Validate solution has data for Production tab.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Production batches
        if not solution.production_batches:
            errors.append("production_batches is empty - Production tab needs batches")

        # Labor hours
        if not solution.labor_hours_by_date:
            errors.append("labor_hours_by_date is empty - Labor hours chart needs data")

        # Check labor hours are LaborHoursBreakdown objects
        if solution.labor_hours_by_date:
            sample = list(solution.labor_hours_by_date.values())[0]
            if not hasattr(sample, 'used'):
                errors.append("labor_hours_by_date values missing 'used' attribute")

        return errors

    @staticmethod
    def validate_for_labeling_tab(solution: OptimizationSolution, model) -> List[str]:
        """Validate solution has data for Labeling tab."""
        errors = []

        # Production data
        if not solution.production_batches:
            errors.append("production_batches empty - Labeling needs production data")

        # Route states
        if not hasattr(model, 'route_arrival_state'):
            errors.append("model missing route_arrival_state - Labeling needs frozen/ambient routing info")
        elif not model.route_arrival_state:
            errors.append("route_arrival_state is empty")

        return errors

    @staticmethod
    def validate_for_distribution_tab(solution: OptimizationSolution) -> List[str]:
        """Validate solution has data for Distribution tab."""
        errors = []

        # Shipments
        if not solution.shipments:
            errors.append("shipments list empty - Distribution tab needs shipment data")

        # Check truck assignments (at least some should be assigned)
        if solution.shipments:
            assigned = [s for s in solution.shipments if s.assigned_truck_id]
            if len(assigned) == 0:
                errors.append("No shipments have truck assignments - check truck_pallet_load extraction")

        return errors

    @staticmethod
    def validate_for_daily_snapshot(solution: OptimizationSolution) -> List[str]:
        """Validate solution has data for Daily Snapshot."""
        errors = []

        # FEFO batches
        if not hasattr(solution, 'fefo_batch_objects'):
            errors.append("fefo_batch_objects missing - Daily Snapshot needs FEFO batches")
        elif not solution.fefo_batch_objects:
            errors.append("fefo_batch_objects is empty")

        # FEFO allocations (for flows)
        if not hasattr(solution, 'fefo_shipment_allocations'):
            errors.append("fefo_shipment_allocations missing - Daily Snapshot needs flow data")
        elif not solution.fefo_shipment_allocations:
            errors.append("fefo_shipment_allocations is empty")

        # Check allocations have product_id
        if hasattr(solution, 'fefo_shipment_allocations') and solution.fefo_shipment_allocations:
            sample = solution.fefo_shipment_allocations[0]
            if 'product_id' not in sample:
                errors.append("fefo_shipment_allocations missing product_id field")

        # Inventory
        if solution.model_type == 'sliding_window':
            if not solution.has_aggregate_inventory:
                errors.append("has_aggregate_inventory is False - should be True for SlidingWindow")
            if not solution.inventory_state:
                errors.append("inventory_state is empty")

        return errors

    @staticmethod
    def validate_for_costs_tab(solution: OptimizationSolution) -> List[str]:
        """Validate solution has data for Costs tab."""
        errors = []

        # Cost breakdown
        if not solution.costs:
            errors.append("costs is None - Costs tab needs cost breakdown")

        # Total cost validation
        if solution.costs:
            component_sum = (
                solution.costs.labor.total +
                solution.costs.production.total +
                solution.costs.transport.total +
                solution.costs.holding.total +
                solution.costs.waste.total
            )

            # Allow 1% tolerance
            if abs(solution.total_cost - component_sum) > 0.01 * max(solution.total_cost, component_sum):
                errors.append(
                    f"total_cost ({solution.total_cost:.2f}) doesn't match components ({component_sum:.2f})"
                )

        return errors

    @staticmethod
    def validate_complete(solution: OptimizationSolution, model) -> None:
        """Validate solution has ALL required data for ALL UI tabs.

        Raises:
            UIDataValidationError: If any validation fails
        """
        all_errors = []

        all_errors.extend(SolutionValidator.validate_for_production_tab(solution))
        all_errors.extend(SolutionValidator.validate_for_labeling_tab(solution, model))
        all_errors.extend(SolutionValidator.validate_for_distribution_tab(solution))
        all_errors.extend(SolutionValidator.validate_for_daily_snapshot(solution))
        all_errors.extend(SolutionValidator.validate_for_costs_tab(solution))

        if all_errors:
            error_msg = "OptimizationSolution validation failed:\n"
            for i, err in enumerate(all_errors, 1):
                error_msg += f"  {i}. {err}\n"

            raise UIDataValidationError(error_msg)
