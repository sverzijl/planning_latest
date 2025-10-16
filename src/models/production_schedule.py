"""Production schedule data model for optimization results.

This module provides the ProductionSchedule class used by optimization models
(e.g., UnifiedNodeModel) to represent production plans with batches, labor hours,
and cost metrics.

Note: This is a clean data model for optimization results, separate from the
heuristic scheduler logic in src/production/scheduler.py.
"""

from datetime import date as Date
from typing import List, Dict
from dataclasses import dataclass, field

from src.models.production_batch import ProductionBatch


@dataclass
class ProductionSchedule:
    """Complete production schedule with batches and metadata.

    Used by optimization models to represent the production plan, including:
    - Production batches with quantities and dates
    - Daily production totals and labor hours
    - Feasibility status and aggregate metrics

    This is a pure data container - no scheduling logic included.

    Attributes:
        manufacturing_site_id: Manufacturing site identifier
        schedule_start_date: First production date in schedule
        schedule_end_date: Last production date in schedule
        production_batches: List of production batches
        daily_totals: Total units produced per date
        daily_labor_hours: Labor hours required per date
        infeasibilities: List of capacity violation messages (empty if feasible)
        total_units: Total units across all batches
        total_labor_hours: Total labor hours required across all dates
    """
    manufacturing_site_id: str
    schedule_start_date: Date
    schedule_end_date: Date
    production_batches: List[ProductionBatch]
    daily_totals: Dict[Date, float]
    daily_labor_hours: Dict[Date, float]
    infeasibilities: List[str]
    total_units: float
    total_labor_hours: float

    def is_feasible(self) -> bool:
        """Check if schedule is completely feasible (no capacity violations).

        Returns:
            True if no infeasibilities, False otherwise
        """
        return len(self.infeasibilities) == 0

    def get_batches_for_date(self, production_date: Date) -> List[ProductionBatch]:
        """Get all batches scheduled for a specific production date.

        Args:
            production_date: Date to filter batches

        Returns:
            List of batches produced on the given date
        """
        return [b for b in self.production_batches if b.production_date == production_date]

    def __str__(self) -> str:
        """String representation with schedule summary."""
        status = "FEASIBLE" if self.is_feasible() else f"INFEASIBLE ({len(self.infeasibilities)} issues)"
        return (
            f"ProductionSchedule ({self.schedule_start_date} to {self.schedule_end_date}): "
            f"{len(self.production_batches)} batches, {self.total_units:.0f} units total - {status}"
        )
