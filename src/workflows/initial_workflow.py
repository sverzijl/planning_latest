"""Initial workflow for first-time or major replanning.

The Initial workflow is used for:
- First-time planning when starting to use the system
- Major replanning events (e.g., network changes, major forecast revisions)
- Establishing a baseline plan for subsequent Weekly/Daily solves

Characteristics:
- Full planning horizon (typically 12 weeks) completely free to optimize
- No warmstart (cold start from solver)
- No fixed periods
- Result saved as warmstart basis for future Weekly solves
"""

from datetime import date as Date, timedelta
from typing import Dict, Any, Optional
import logging

from .base_workflow import BaseWorkflow, WorkflowType, WorkflowConfig

logger = logging.getLogger(__name__)


class InitialWorkflow(BaseWorkflow):
    """Initial solve workflow for establishing baseline production plan.

    This workflow creates the first optimized plan, typically covering 12 weeks.
    It does not use any warmstart data and all time periods are free to optimize.

    Example Usage:
        ```python
        config = WorkflowConfig(
            workflow_type=WorkflowType.INITIAL,
            planning_horizon_weeks=12,
            solve_time_limit=1800,  # 30 minutes
            solver_name="appsi_highs",
        )

        workflow = InitialWorkflow(
            config=config,
            locations=locations,
            routes=routes,
            products=products,
            forecast=forecast,
            labor_calendar=labor_calendar,
            truck_schedules=truck_schedules,
            cost_structure=cost_structure,
            initial_inventory=inventory_snapshot,
        )

        result = workflow.execute()
        ```
    """

    def prepare_input_data(self) -> Dict[str, Any]:
        """Prepare and validate input data for Initial solve.

        For Initial workflow:
        - Planning horizon starts from tomorrow (or user-specified date)
        - All weeks are free to optimize
        - Initial inventory must be provided (from SAP MB52 dump or manual entry)

        Returns:
            Dictionary containing:
                - planning_start_date: First date of planning horizon
                - planning_end_date: Last date of planning horizon
                - horizon_days: Number of days in planning horizon

        Raises:
            ValueError: If initial inventory is missing or invalid
        """
        logger.info("Preparing input data for Initial workflow")

        # Validate required inputs
        if not self.initial_inventory:
            raise ValueError(
                "Initial workflow requires initial_inventory. "
                "Provide SAP MB52 inventory snapshot or manual inventory data."
            )

        # Calculate planning horizon dates
        # Start from tomorrow (production planners typically plan ahead)
        planning_start_date = Date.today() + timedelta(days=1)

        # End date = start + (weeks * 7 days) - 1 day (inclusive)
        horizon_days = self.config.planning_horizon_weeks * 7
        planning_end_date = planning_start_date + timedelta(days=horizon_days - 1)

        logger.info(
            f"Planning horizon: {planning_start_date} to {planning_end_date} "
            f"({horizon_days} days, {self.config.planning_horizon_weeks} weeks)"
        )

        # Validate forecast coverage
        forecast_entries = self.forecast.entries if hasattr(self.forecast, 'entries') else self.forecast
        forecast_dates = {f.forecast_date for f in forecast_entries}
        required_dates = {
            planning_start_date + timedelta(days=i)
            for i in range(horizon_days)
        }

        missing_dates = required_dates - forecast_dates
        if missing_dates:
            logger.warning(
                f"Forecast missing for {len(missing_dates)} dates. "
                f"First missing: {sorted(missing_dates)[0]}"
            )

        return {
            "planning_start_date": planning_start_date,
            "planning_end_date": planning_end_date,
            "horizon_days": horizon_days,
            "all_periods_free": True,
        }

    def prepare_warmstart(self) -> Optional[Dict[str, Any]]:
        """Prepare warmstart data.

        Initial workflow never uses warmstart (cold start).

        Returns:
            None (no warmstart for Initial workflow)
        """
        logger.info("Initial workflow uses cold start (no warmstart)")
        return None

    def apply_fixed_periods(self) -> None:
        """Apply fixed period constraints.

        Initial workflow has no fixed periods - all time periods are free.

        This is a no-op for Initial workflow.
        """
        logger.info("Initial workflow has no fixed periods (all periods free)")
        pass
