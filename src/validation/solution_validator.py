"""Solution validation - mandatory checks that fail loudly on incorrect solutions.

This validator runs AFTER solution extraction and catches bugs that made it
through the optimization model. It enforces business rules that MUST hold.

If validation fails, the solution is INVALID and should not be used.
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import date as Date

from src.optimization.result_schema import OptimizationSolution


@dataclass
class SolutionValidationError:
    """Represents a solution validation error (CRITICAL - solution invalid)."""
    category: str
    message: str
    details: Dict = None


class SolutionValidator:
    """Validates optimization solutions for business rule compliance."""

    def __init__(self, solution: OptimizationSolution, demand_data: Dict = None):
        """Initialize validator.

        Args:
            solution: Extracted optimization solution
            demand_data: Optional demand data for context
        """
        self.solution = solution
        self.demand_data = demand_data or {}

    def validate(self) -> Tuple[bool, List[SolutionValidationError]]:
        """Run all mandatory validation checks.

        Returns:
            Tuple of (is_valid, list of errors)
            is_valid is False if ANY error found (solution is invalid)
        """
        errors = []

        # MANDATORY CHECKS (any failure = invalid solution)
        errors.extend(self._validate_no_labor_without_production())
        errors.extend(self._validate_lineage_receives_goods_if_wa_demand())
        errors.extend(self._validate_no_shipments_on_wrong_days())
        errors.extend(self._validate_weekend_labor_minimum())

        # Return validation result
        return (len(errors) == 0, errors)

    def _validate_no_labor_without_production(self) -> List[SolutionValidationError]:
        """CRITICAL: Labor hours should be 0 when production is 0.

        Catches phantom labor from broken binary linking constraints.
        """
        errors = []

        # Group production by date
        production_by_date = {}
        for batch in self.solution.production_batches:
            # ProductionBatchResult uses 'date', not 'production_date'
            date_key = batch.date
            production_by_date[date_key] = production_by_date.get(date_key, 0) + batch.quantity

        # Check labor hours
        if hasattr(self.solution, 'labor_hours_by_date'):
            for date_key, labor_info in self.solution.labor_hours_by_date.items():
                # Extract hours
                if hasattr(labor_info, 'used'):
                    hours = labor_info.used
                elif isinstance(labor_info, dict):
                    hours = labor_info.get('used', 0)
                else:
                    hours = float(labor_info) if labor_info else 0

                production = production_by_date.get(date_key, 0)

                # CRITICAL CHECK
                if hours > 0.1 and production < 0.01:
                    errors.append(SolutionValidationError(
                        category='Labor Without Production',
                        message=f"Date {date_key}: {hours:.2f}h labor but {production:.0f} units production (should be 0h or 4h+ if minimum payment)",
                        details={'date': date_key, 'labor_hours': hours, 'production': production}
                    ))

        return errors

    def _validate_lineage_receives_goods_if_wa_demand(self) -> List[SolutionValidationError]:
        """CRITICAL: If 6130 (WA) has demand, Lineage must receive goods.

        Lineage is the ONLY source of frozen goods for 6130.
        If 6130 has demand and Lineage receives no shipments, WA demand cannot be satisfied.
        """
        errors = []

        # Check if 6130 has demand
        wa_demand = sum(
            self.demand_data.get(('6130', prod, date), 0)
            for prod in ['HELGAS GFREE MIXED GRAIN 500G', 'HELGAS GFREE TRAD WHITE 470G',
                        'HELGAS GFREE WHOLEM 500G', 'WONDER GFREE WHITE 470G', 'WONDER GFREE WHOLEM 500G']
            for date in self.demand_data.keys()
            if isinstance(date, tuple) and len(date) == 3 and date[0] == '6130'
        ) if self.demand_data else 0

        if wa_demand < 100:
            # Minimal/no WA demand - Lineage usage optional
            return errors

        # Check shipments TO Lineage
        shipments_to_lineage = [
            s for s in self.solution.shipments
            if s.destination == 'Lineage'
        ]

        total_to_lineage = sum(s.quantity for s in shipments_to_lineage)

        if total_to_lineage < 10:  # Allow small tolerance
            errors.append(SolutionValidationError(
                category='Lineage Not Receiving Goods',
                message=f"6130 (WA) has {wa_demand:.0f} units demand but Lineage received only {total_to_lineage:.0f} units. "
                       f"Lineage is the only frozen source for WA - this indicates a routing bug.",
                details={'wa_demand': wa_demand, 'lineage_received': total_to_lineage}
            ))

        return errors

    def _validate_no_shipments_on_wrong_days(self) -> List[SolutionValidationError]:
        """CRITICAL: Shipments should only occur on days when trucks operate.

        This catches day-of-week enforcement failures.
        """
        errors = []

        # Define truck schedules (hardcoded for now - could be passed in)
        truck_schedule_days = {
            ('6122', '6125'): {'monday', 'tuesday', 'wednesday', 'thursday', 'friday'},
            ('6122', '6104'): {'monday', 'wednesday', 'friday'},
            ('6122', '6110'): {'tuesday', 'thursday'},
            ('6122', 'Lineage'): {'wednesday'},
        }

        for shipment in self.solution.shipments:
            route_key = (shipment.origin, shipment.destination)
            valid_days = truck_schedule_days.get(route_key)

            if not valid_days:
                continue  # No schedule defined

            # Check if shipment is on valid day
            ship_day = shipment.departure_date.strftime('%A').lower() if hasattr(shipment, 'departure_date') and shipment.departure_date else None

            if ship_day and ship_day not in valid_days:
                errors.append(SolutionValidationError(
                    category='Shipment On Wrong Day',
                    message=f"Shipment {shipment.origin} → {shipment.destination} on {ship_day} "
                           f"but truck only runs on {valid_days}",
                    details={'route': route_key, 'day': ship_day, 'valid_days': list(valid_days)}
                ))

        return errors

    def _validate_weekend_labor_minimum(self) -> List[SolutionValidationError]:
        """CRITICAL: Weekend/holiday labor must be 0h or ≥4h (minimum payment rule).

        If producing on weekend: must pay for at least 4 hours.
        If not producing: should be 0 hours.

        This catches 4-hour minimum payment enforcement failures.
        """
        errors = []

        # Need labor calendar to check which days are weekends
        # For now, check all labor hours in reasonable range
        if hasattr(self.solution, 'labor_hours_by_date'):
            for date_key, labor_info in self.solution.labor_hours_by_date.items():
                # Extract hours
                if hasattr(labor_info, 'used'):
                    hours_used = labor_info.used
                    hours_paid = labor_info.paid if hasattr(labor_info, 'paid') else hours_used
                elif isinstance(labor_info, dict):
                    hours_used = labor_info.get('used', 0)
                    hours_paid = labor_info.get('paid', hours_used)
                else:
                    hours_used = float(labor_info) if labor_info else 0
                    hours_paid = hours_used

                # Check if this looks like a weekend (would need labor calendar for definitive check)
                # For now: if hours_used is small but positive, flag it
                if 0.01 < hours_used < 3.5:
                    # This looks like fractional labor that should either be 0 or trigger 4h minimum
                    errors.append(SolutionValidationError(
                        category='Fractional Weekend Labor',
                        message=f"Date {date_key}: {hours_used:.2f}h used, {hours_paid:.2f}h paid. "
                               f"Weekend labor should be 0h or ≥4h (minimum payment). "
                               f"Fractional hours indicate constraint bug.",
                        details={'date': date_key, 'hours_used': hours_used, 'hours_paid': hours_paid}
                    ))

        return errors


def validate_solution(
    solution: OptimizationSolution,
    demand_data: Dict = None,
    fail_on_error: bool = True
) -> Tuple[bool, List[SolutionValidationError]]:
    """Validate optimization solution for business rule compliance.

    This is a MANDATORY validation that should run after every solve.
    If validation fails, the solution should NOT be used.

    Args:
        solution: Extracted optimization solution
        demand_data: Optional demand data for context
        fail_on_error: If True, raises exception on validation failure

    Returns:
        Tuple of (is_valid, list of errors)

    Raises:
        ValidationError: If fail_on_error=True and validation fails
    """
    validator = SolutionValidator(solution, demand_data)
    is_valid, errors = validator.validate()

    if not is_valid:
        error_messages = [f"{e.category}: {e.message}" for e in errors]

        if fail_on_error:
            from src.validation.planning_data_schema import ValidationError
            raise ValidationError(
                f"Solution validation failed - solution is INVALID:\n" +
                "\n".join(f"  ❌ {msg}" for msg in error_messages)
            )
        else:
            # Just log
            print(f"\n❌ SOLUTION VALIDATION FAILED:")
            for msg in error_messages:
                print(f"  {msg}")

    return is_valid, errors
