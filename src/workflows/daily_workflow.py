"""Daily workflow for operational replanning with actuals.

The Daily workflow is used for:
- Daily replanning with actual production and shipments locked in
- Near-term planning (weeks 1-4) free, long-term (weeks 5-12) fixed
- Generating forward production plans for next 1-7 days
- Review and lock workflow for today's plan

Characteristics:
- Partial horizon optimization (typically 4 weeks free, 8 weeks fixed)
- Uses warmstart from previous Daily or Weekly solve
- Today's production is locked after review and approval
- Yesterday's actuals override planned values
- Fixed periods (weeks 5-12) are hard-constrained to previous solve
- Generates exportable production plans for shop floor
"""

from datetime import date as Date, timedelta
from typing import Dict, Any, Optional, List
import logging

from .base_workflow import BaseWorkflow, WorkflowType, WorkflowConfig

logger = logging.getLogger(__name__)


class DailyWorkflow(BaseWorkflow):
    """Daily operational workflow with actuals locking and fixed periods.

    This workflow re-optimizes weeks 1-4 while keeping weeks 5-12 frozen from
    the previous solve. It incorporates actual production and shipments from
    yesterday and locks in today's plan after planner review.

    Typical Timeline:
    - Early morning (5-7am): Planner runs Daily workflow
    - Yesterday: Actual production/shipments entered
    - Today: Plan reviewed and locked
    - Tomorrow: Primary focus of new planning
    - Days 2-28: Free to optimize (weeks 1-4)
    - Days 29-84: Fixed from previous solve (weeks 5-12)

    Example Usage:
        ```python
        config = WorkflowConfig(
            workflow_type=WorkflowType.DAILY,
            planning_horizon_weeks=12,
            free_period_weeks=4,
            fixed_period_weeks=8,
            solve_time_limit=120,  # 2 minutes
            solver_name="appsi_highs",
            use_warmstart=True,
        )

        workflow = DailyWorkflow(
            config=config,
            locations=locations,
            routes=routes,
            products=products,
            forecast=forecast,
            labor_calendar=labor_calendar,
            truck_schedules=truck_schedules,
            cost_structure=cost_structure,
            yesterday_actuals=actuals_data,  # From actuals entry form
            today_plan_approved=True,  # From review and lock workflow
        )

        result = workflow.execute()
        ```
    """

    def __init__(
        self,
        *args,
        previous_solve_path: Optional[str] = None,
        yesterday_actuals: Optional[Dict] = None,
        today_plan_approved: bool = False,
        **kwargs
    ):
        """Initialize Daily workflow.

        Args:
            previous_solve_path: Path to previous solve file for warmstart and fixed periods
            yesterday_actuals: Actual production and shipments from yesterday
            today_plan_approved: Whether today's plan has been reviewed and locked
            *args, **kwargs: Passed to BaseWorkflow
        """
        super().__init__(*args, **kwargs)
        self.previous_solve_path = previous_solve_path
        self.yesterday_actuals = yesterday_actuals or {}
        self.today_plan_approved = today_plan_approved

    def prepare_input_data(self) -> Dict[str, Any]:
        """Prepare and validate input data for Daily solve.

        For Daily workflow:
        - Planning horizon starts tomorrow
        - Weeks 1-4 are free to optimize
        - Weeks 5-12 are fixed from previous solve
        - Yesterday's actuals override planned values
        - Today's plan must be approved before solve

        Returns:
            Dictionary containing:
                - planning_start_date: First date of planning horizon (tomorrow)
                - planning_end_date: Last date of planning horizon
                - horizon_days: Number of days in planning horizon
                - free_period_end_date: Last date of free period
                - fixed_period_start_date: First date of fixed period
                - yesterday_date: Date of actuals
                - today_date: Date being locked

        Raises:
            ValueError: If today's plan not approved or actuals invalid
        """
        logger.info("Preparing input data for Daily workflow")

        # Validate today's plan has been approved
        if not self.today_plan_approved:
            raise ValueError(
                "Today's plan must be reviewed and approved before running Daily solve. "
                "Complete the 'Review Today' step first."
            )

        # Validate yesterday's actuals
        if not self.yesterday_actuals:
            logger.warning(
                "No yesterday_actuals provided. "
                "System should auto-populate from previous day's plan."
            )

        # Calculate dates
        today = Date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        # Planning starts tomorrow
        planning_start_date = tomorrow

        # End date based on total horizon
        horizon_days = self.config.planning_horizon_weeks * 7
        planning_end_date = planning_start_date + timedelta(days=horizon_days - 1)

        # Free period (weeks 1-4)
        free_period_days = self.config.free_period_weeks * 7
        free_period_end_date = planning_start_date + timedelta(days=free_period_days - 1)

        # Fixed period (weeks 5-12)
        fixed_period_start_date = free_period_end_date + timedelta(days=1)

        logger.info(
            f"Planning horizon: {planning_start_date} to {planning_end_date} "
            f"({horizon_days} days, {self.config.planning_horizon_weeks} weeks)"
        )
        logger.info(
            f"Free period: {planning_start_date} to {free_period_end_date} "
            f"({free_period_days} days, {self.config.free_period_weeks} weeks)"
        )
        logger.info(
            f"Fixed period: {fixed_period_start_date} to {planning_end_date} "
            f"({self.config.fixed_period_weeks} weeks)"
        )

        return {
            "planning_start_date": planning_start_date,
            "planning_end_date": planning_end_date,
            "horizon_days": horizon_days,
            "free_period_end_date": free_period_end_date,
            "fixed_period_start_date": fixed_period_start_date,
            "yesterday_date": yesterday,
            "today_date": today,
            "all_periods_free": False,
        }

    def prepare_warmstart(self) -> Optional[Dict[str, Any]]:
        """Prepare warmstart data from previous solve.

        For Daily workflow:
        1. Load previous solve (Daily or Weekly)
        2. Validate compatibility with new problem
        3. Extract variable values for initialization

        Note: Unlike Weekly workflow, Daily does NOT shift time forward.
        The warmstart is used as-is since we're replanning the same horizon.

        Returns:
            Warmstart data dictionary if using warmstart, None otherwise

        Raises:
            FileNotFoundError: If previous solve file not found
            ValueError: If warmstart data incompatible
        """
        if not self.config.use_warmstart:
            logger.info("Warmstart disabled in config")
            return None

        logger.info("Preparing warmstart for Daily workflow")

        # TODO: Implement warmstart extraction
        # This will be completed when warmstart module is ready
        logger.warning(
            "Warmstart extraction not yet implemented. "
            "Using cold start for now."
        )

        return None

    def apply_fixed_periods(self) -> None:
        """Fix variables for weeks 5-12 (locked time periods).

        For Daily workflow:
        - Weeks 1-4 (free period): Variables remain free
        - Weeks 5-12 (fixed period): Variables fixed to previous solve values
        - Today (day 0): Already locked via today_plan_approved

        This ensures long-term plan stability while allowing near-term replanning.

        Raises:
            ValueError: If fixed periods create infeasibility with actuals
        """
        if not self.model:
            raise RuntimeError("Model must be built before applying fixed periods")

        logger.info(
            f"Applying fixed periods for weeks {self.config.free_period_weeks + 1}-"
            f"{self.config.planning_horizon_weeks} (weeks 5-12)"
        )

        # TODO: Implement fixed period application
        # This will be completed when fixed_periods module is ready
        logger.warning(
            "Fixed period application not yet implemented. "
            "All periods will remain free for now."
        )

        # Future implementation will:
        # 1. Load previous solve values for weeks 5-12
        # 2. Fix production variables to those values
        # 3. Fix shipment variables to those values
        # 4. Allow inventory to adjust based on actuals
        # 5. Validate that fixed values are feasible
        # 6. Raise error if infeasibility detected

    def get_variance_report(self) -> Dict[str, Any]:
        """Generate variance report comparing plan vs actuals.

        Compares yesterday's planned values (from previous solve) with
        yesterday's actual values (entered by planner). Flags deviations
        exceeding threshold (e.g., >10%).

        Returns:
            Dictionary with variance analysis:
                - production_variances: List of production deviations
                - shipment_variances: List of shipment deviations
                - large_deviations: Items exceeding threshold
                - total_deviation_percent: Overall deviation

        Note:
            This should be called during actuals entry to alert planner
            to significant deviations requiring explanation.
        """
        logger.info("Generating variance report")

        # TODO: Implement variance detection
        # This will be completed in Phase B (actuals module)

        return {
            "report_available": False,
            "message": "Variance reporting not yet implemented"
        }

    def get_forward_plan(self, days_ahead: int = 7) -> Dict[str, Any]:
        """Generate forward production plan for next N days.

        Extracts production schedule from solve results for the next 1-7 days,
        formatted for shop floor export (Excel, PDF, interactive dashboard).

        Args:
            days_ahead: Number of days to include in forward plan (default: 7)

        Returns:
            Dictionary with forward plan data:
                - daily_production: Production by date, SKU, quantity
                - labor_allocation: Labor hours by date
                - truck_loading: Truck assignments by date
                - dough_plan: Dough prep schedule
                - packing_plan: Packing schedule

        Note:
            Planner can manually edit these plans, and system tracks deviations.
        """
        logger.info(f"Generating {days_ahead}-day forward production plan")

        # TODO: Implement forward plan generation
        # This will be completed in Phase C (exporters module enhancement)

        return {
            "plan_available": False,
            "message": "Forward plan generation not yet implemented",
            "days_ahead": days_ahead
        }
