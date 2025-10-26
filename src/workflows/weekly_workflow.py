"""Weekly workflow for rolling horizon replanning.

The Weekly workflow is used for:
- Weekly replanning with updated forecast
- Rolling the planning horizon forward one week
- Using warmstart from previous solve for faster optimization

Characteristics:
- Full planning horizon (typically 12 weeks) completely free to optimize
- Uses warmstart from previous solve (Initial or Weekly)
- Warmstart is time-shifted forward by 1 week (weeks 2-12 become weeks 1-11)
- New week 12 is added to horizon
- Includes warmstart preview/approval workflow
- Detects large forecast changes and alerts planner
"""

from datetime import date as Date, timedelta
from typing import Dict, Any, Optional
import logging

from .base_workflow import BaseWorkflow, WorkflowType, WorkflowConfig

logger = logging.getLogger(__name__)


class WeeklyWorkflow(BaseWorkflow):
    """Weekly rolling horizon workflow with warmstart.

    This workflow re-optimizes the full 12-week horizon with updated forecast,
    using the previous solve as a warmstart. The planning horizon rolls forward
    by one week.

    Example Usage:
        ```python
        config = WorkflowConfig(
            workflow_type=WorkflowType.WEEKLY,
            planning_horizon_weeks=12,
            solve_time_limit=600,  # 10 minutes
            solver_name="appsi_highs",
            use_warmstart=True,
        )

        workflow = WeeklyWorkflow(
            config=config,
            locations=locations,
            routes=routes,
            products=products,
            forecast=updated_forecast,  # New forecast
            labor_calendar=labor_calendar,
            truck_schedules=truck_schedules,
            cost_structure=cost_structure,
            initial_inventory=None,  # Will be auto-calculated from previous solve
        )

        result = workflow.execute()
        ```
    """

    def __init__(self, *args, previous_solve_path: Optional[str] = None, **kwargs):
        """Initialize Weekly workflow.

        Args:
            previous_solve_path: Path to previous solve file for warmstart.
                If None, will auto-discover most recent solve.
            *args, **kwargs: Passed to BaseWorkflow
        """
        super().__init__(*args, **kwargs)
        self.previous_solve_path = previous_solve_path

    def prepare_input_data(self) -> Dict[str, Any]:
        """Prepare and validate input data for Weekly solve.

        For Weekly workflow:
        - Planning horizon rolls forward by 1 week from previous solve
        - All weeks are free to optimize
        - Inventory is auto-calculated from previous solve + actuals (with review)

        Returns:
            Dictionary containing:
                - planning_start_date: First date of planning horizon
                - planning_end_date: Last date of planning horizon
                - horizon_days: Number of days in planning horizon
                - rolled_from_previous: Whether horizon was rolled from previous solve

        Raises:
            ValueError: If inputs are invalid
        """
        logger.info("Preparing input data for Weekly workflow")

        # TODO: Auto-calculate inventory from previous solve
        # For now, require explicit inventory or use provided inventory
        if not self.initial_inventory:
            logger.warning(
                "No initial_inventory provided. "
                "In production, this should be auto-calculated from previous solve."
            )

        # Calculate planning horizon dates
        # For Weekly workflow, start from next Monday (or tomorrow if already Monday)
        today = Date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7  # If today is Monday, start next Monday

        planning_start_date = today + timedelta(days=days_until_monday)

        # End date = start + (weeks * 7 days) - 1 day (inclusive)
        horizon_days = self.config.planning_horizon_weeks * 7
        planning_end_date = planning_start_date + timedelta(days=horizon_days - 1)

        logger.info(
            f"Planning horizon: {planning_start_date} to {planning_end_date} "
            f"({horizon_days} days, {self.config.planning_horizon_weeks} weeks)"
        )

        return {
            "planning_start_date": planning_start_date,
            "planning_end_date": planning_end_date,
            "horizon_days": horizon_days,
            "all_periods_free": True,
            "rolled_from_previous": True,
        }

    def prepare_warmstart(self) -> Optional[Dict[str, Any]]:
        """Prepare warmstart data from previous solve.

        For Weekly workflow:
        1. Load previous solve (Initial or Weekly)
        2. Shift time forward by 1 week (weeks 2-12 → weeks 1-11)
        3. Validate compatibility with new problem
        4. Generate preview data for planner approval

        Returns:
            Warmstart data dictionary if using warmstart, None otherwise

        Raises:
            FileNotFoundError: If previous solve file not found
            ValueError: If warmstart data incompatible
        """
        if not self.config.use_warmstart:
            logger.info("Warmstart disabled in config")
            return None

        logger.info("Preparing warmstart for Weekly workflow")

        # TODO: Implement warmstart extraction and shifting
        # This will be completed when warmstart module is ready
        logger.warning(
            "Warmstart extraction not yet implemented. "
            "Using cold start for now."
        )

        return None

    def apply_fixed_periods(self) -> None:
        """Apply fixed period constraints.

        Weekly workflow has no fixed periods - all time periods are free.

        This is a no-op for Weekly workflow.
        """
        logger.info("Weekly workflow has no fixed periods (all periods free)")
        pass

    def get_warmstart_preview(self) -> Dict[str, Any]:
        """Generate warmstart preview data for planner review.

        Preview includes:
        - Demand delta (forecast changes from previous solve)
        - Cost comparison (old objective vs estimated new objective)
        - Constraint violations (capacity changes, holidays, etc.)
        - Age of previous solve (hours/days since creation)

        Returns:
            Dictionary with preview data for UI display

        Note:
            This should be called before execute() to allow planner to review
            and approve/reject warmstart before running the solve.
        """
        logger.info("Generating warmstart preview")

        # TODO: Implement warmstart preview generation
        # This will be completed when warmstart module is ready

        return {
            "preview_available": False,
            "message": "Warmstart preview not yet implemented"
        }
