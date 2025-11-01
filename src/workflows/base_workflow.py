"""Base workflow class for production planning solve phases.

This module defines the abstract base class for all workflow types (Initial, Weekly, Daily).
Each workflow orchestrates the solve process with appropriate data preparation, warmstart
handling, and result persistence.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date as Date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

from ..models.location import Location
from ..models.route import Route
from ..models.product import Product
from ..models.forecast import Forecast
from ..models.inventory import InventorySnapshot
from ..models.labor_calendar import LaborCalendar
from ..models.truck_schedule import TruckSchedule
from ..models.cost_structure import CostStructure
from ..optimization.base_model import OptimizationResult

logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """Type of workflow solve."""
    INITIAL = "initial"
    WEEKLY = "weekly"
    DAILY = "daily"


@dataclass
class WorkflowConfig:
    """Configuration for a workflow solve.

    Attributes:
        workflow_type: Type of workflow (Initial/Weekly/Daily)
        planning_horizon_weeks: Total planning horizon in weeks
        free_period_weeks: Number of weeks that can be re-optimized (Daily only)
        fixed_period_weeks: Number of weeks that are frozen (Daily only)
        solve_time_limit: Maximum solve time in seconds (None = no limit)
        mip_gap_tolerance: MIP gap tolerance (e.g., 0.01 for 1%)
        solver_name: Solver to use (e.g., 'appsi_highs', 'cbc')
        use_warmstart: Whether to use warmstart from previous solve
        allow_shortages: Whether to allow demand shortages
        track_batches: Whether to track production batches
        use_pallet_costs: Whether to use pallet-based storage costs
    """
    workflow_type: WorkflowType
    planning_horizon_weeks: int = 12
    free_period_weeks: Optional[int] = None  # For Daily workflow
    fixed_period_weeks: Optional[int] = None  # For Daily workflow
    solve_time_limit: Optional[float] = None
    mip_gap_tolerance: float = 0.01
    solver_name: str = "appsi_highs"
    use_warmstart: bool = False
    allow_shortages: bool = True  # Changed from False - required for waste penalty to work properly
    track_batches: bool = True
    use_pallet_costs: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if self.workflow_type == WorkflowType.DAILY:
            if self.free_period_weeks is None or self.fixed_period_weeks is None:
                raise ValueError(
                    "Daily workflow requires free_period_weeks and fixed_period_weeks"
                )
            if self.free_period_weeks + self.fixed_period_weeks != self.planning_horizon_weeks:
                raise ValueError(
                    f"free_period_weeks ({self.free_period_weeks}) + "
                    f"fixed_period_weeks ({self.fixed_period_weeks}) must equal "
                    f"planning_horizon_weeks ({self.planning_horizon_weeks})"
                )


@dataclass
class WorkflowResult:
    """Result from a workflow solve.

    Attributes:
        workflow_type: Type of workflow that was run
        solve_timestamp: When the solve was executed
        solution: Optimization solution metadata (persisted to file)
        model: Reference to optimization model (session state only, not persisted)
        success: Whether the solve was successful
        solve_time_seconds: Time taken to solve
        objective_value: Objective function value (None if failed)
        mip_gap: Final MIP gap (None if not applicable)
        solver_status: Solver termination status
        solver_message: Solver termination message
        metadata: Additional metadata (input hashes, config, etc.)
        error_message: Error message if solve failed
    """
    workflow_type: WorkflowType
    solve_timestamp: datetime
    solution: Optional[OptimizationResult] = None
    model: Optional[Any] = None  # UnifiedNodeModel reference (not persisted)
    success: bool = False
    solve_time_seconds: Optional[float] = None
    objective_value: Optional[float] = None
    mip_gap: Optional[float] = None
    solver_status: Optional[str] = None
    solver_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class BaseWorkflow(ABC):
    """Abstract base class for production planning workflows.

    This class defines the common interface and orchestration logic for all
    workflow types (Initial, Weekly, Daily). Each workflow type implements
    specific behavior for data preparation, warmstart handling, and constraint
    fixing.

    Workflow Execution Steps:
        1. prepare_input_data() - Load and validate input data
        2. prepare_warmstart() - Extract warmstart from previous solve (if applicable)
        3. build_model() - Construct optimization model
        4. apply_warmstart() - Initialize variables (if using warmstart)
        5. apply_fixed_periods() - Fix variables for locked periods (Daily only)
        6. solve() - Execute optimization
        7. validate_solution() - Check solution feasibility and quality
        8. persist_result() - Save result to file system
    """

    def __init__(
        self,
        config: WorkflowConfig,
        locations: List[Location],
        routes: List[Route],
        products: List[Product],
        forecast: Forecast,
        labor_calendar: LaborCalendar,
        truck_schedules: List[TruckSchedule],
        cost_structure: CostStructure,
        initial_inventory: Optional[InventorySnapshot] = None,
        in_transit_inventory: Optional[Dict] = None,
    ):
        """Initialize workflow.

        Args:
            config: Workflow configuration
            locations: List of network locations
            routes: List of network routes
            products: List of products
            forecast: Demand forecast (Forecast object)
            labor_calendar: Labor availability and costs
            truck_schedules: Truck departure schedules
            cost_structure: Cost parameters
            initial_inventory: Starting inventory (optional)
            in_transit_inventory: Inventory in transit (optional)
        """
        self.config = config
        self.locations = locations
        self.routes = routes
        self.products = products
        self.forecast = forecast
        self.labor_calendar = labor_calendar
        self.truck_schedules = truck_schedules
        self.cost_structure = cost_structure
        self.initial_inventory = initial_inventory
        self.in_transit_inventory = in_transit_inventory or {}

        # Will be populated during execution
        self.model = None
        self.warmstart_data = None
        self.result: Optional[WorkflowResult] = None

        logger.info(
            f"Initialized {self.config.workflow_type.value} workflow "
            f"with {config.planning_horizon_weeks}-week horizon"
        )

    @abstractmethod
    def prepare_input_data(self) -> Dict[str, Any]:
        """Prepare and validate input data for solve.

        Returns:
            Dictionary of prepared input data

        Raises:
            ValueError: If input data is invalid or incomplete
        """
        pass

    @abstractmethod
    def prepare_warmstart(self) -> Optional[Dict[str, Any]]:
        """Prepare warmstart data from previous solve.

        Returns:
            Warmstart data dictionary (None if not using warmstart)

        Raises:
            FileNotFoundError: If warmstart file not found
            ValueError: If warmstart data is incompatible
        """
        pass

    @abstractmethod
    def apply_fixed_periods(self) -> None:
        """Fix variables for locked time periods.

        Only applicable for Daily workflow (fixes weeks 5-12).
        Other workflows implement this as a no-op.

        Raises:
            ValueError: If fixed periods create infeasibility
        """
        pass

    def execute(self) -> WorkflowResult:
        """Execute the complete workflow.

        This orchestrates all workflow steps in order:
        1. Prepare input data
        2. Prepare warmstart (if applicable)
        3. Build optimization model
        4. Apply warmstart (if available)
        5. Apply fixed periods (if applicable)
        6. Solve optimization
        7. Validate solution
        8. Persist result

        Returns:
            WorkflowResult with solve outcome
        """
        try:
            start_time = datetime.now()
            logger.info(f"Starting {self.config.workflow_type.value} workflow execution")

            # Step 1: Prepare input data
            logger.info("Step 1: Preparing input data")
            input_data = self.prepare_input_data()

            # Step 2: Prepare warmstart
            if self.config.use_warmstart:
                logger.info("Step 2: Preparing warmstart")
                self.warmstart_data = self.prepare_warmstart()
            else:
                logger.info("Step 2: Skipping warmstart (cold start)")
                self.warmstart_data = None

            # Step 3: Build model
            logger.info("Step 3: Building optimization model")
            self._build_model(input_data)

            # Step 4: Apply warmstart
            if self.warmstart_data:
                logger.info("Step 4: Applying warmstart")
                self._apply_warmstart()
            else:
                logger.info("Step 4: Skipping warmstart application")

            # Step 5: Apply fixed periods
            logger.info("Step 5: Applying fixed periods")
            self.apply_fixed_periods()

            # Step 6: Solve
            logger.info("Step 6: Solving optimization model")
            solution = self._solve_model()

            # Step 7: Validate
            logger.info("Step 7: Validating solution")
            validation_result = self._validate_solution(solution)

            if not validation_result["valid"]:
                logger.warning(f"Solution validation failed: {validation_result['message']}")

            # Step 8: Create result
            end_time = datetime.now()
            solve_time = (end_time - start_time).total_seconds()

            self.result = WorkflowResult(
                workflow_type=self.config.workflow_type,
                solve_timestamp=start_time,
                solution=solution,
                model=self.model,  # Store model reference for result extraction
                success=solution is not None and solution.success,
                solve_time_seconds=solve_time,
                objective_value=solution.objective_value if solution else None,
                mip_gap=solution.gap if solution else None,
                solver_status=str(solution.solver_status) if solution and solution.solver_status else None,
                solver_message=str(solution.termination_condition) if solution and solution.termination_condition else None,
                metadata=self._build_metadata(input_data),
            )

            logger.info(
                f"Workflow execution complete. Success: {self.result.success}, "
                f"Time: {solve_time:.2f}s"
            )

            return self.result

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)

            self.result = WorkflowResult(
                workflow_type=self.config.workflow_type,
                solve_timestamp=datetime.now(),
                success=False,
                error_message=str(e),
            )

            return self.result

    def _build_model(self, input_data: Dict[str, Any]) -> None:
        """Build the optimization model.

        Args:
            input_data: Prepared input data from prepare_input_data()
        """
        from ..optimization.sliding_window_model import SlidingWindowModel
        from ..optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

        # Convert legacy data structures to unified format
        converter = LegacyToUnifiedConverter()

        # Get manufacturing site (should be first location with is_manufacturing=True)
        manufacturing_site = None
        for loc in self.locations:
            if hasattr(loc, 'is_manufacturing') and loc.is_manufacturing:
                manufacturing_site = loc
                break

        if manufacturing_site is None:
            # Fallback: find location with ID 6122
            manufacturing_site = next((loc for loc in self.locations if loc.location_id == "6122"), None)

        if manufacturing_site is None:
            raise ValueError("No manufacturing site found in locations")

        # Get truck schedules list
        truck_schedules_list = self.truck_schedules.schedules if hasattr(self.truck_schedules, 'schedules') else self.truck_schedules

        # Convert to unified format
        nodes, unified_routes, unified_trucks = converter.convert_all(
            manufacturing_site=manufacturing_site,
            locations=self.locations,
            routes=self.routes,
            truck_schedules=truck_schedules_list,
            forecast=self.forecast
        )

        # Convert products list to dict
        products_dict = {p.id: p for p in self.products} if isinstance(self.products, list) else self.products

        # Get initial inventory dict
        initial_inventory_dict = {}
        if self.initial_inventory:
            if hasattr(self.initial_inventory, 'to_optimization_dict'):
                # to_optimization_dict() returns 2-tuple: (location, product)
                # But SlidingWindowModel needs 3-tuple: (location, product, state)
                inv_2tuple = self.initial_inventory.to_optimization_dict()

                # Convert to 3-tuple format (assume ambient state)
                for (location, product), quantity in inv_2tuple.items():
                    initial_inventory_dict[(location, product, 'ambient')] = quantity
            elif isinstance(self.initial_inventory, dict):
                initial_inventory_dict = self.initial_inventory

        # Get inventory snapshot date if available
        inventory_snapshot_date = None
        if self.initial_inventory:
            if hasattr(self.initial_inventory, 'snapshot_date'):
                inventory_snapshot_date = self.initial_inventory.snapshot_date
            elif 'inventory_snapshot_date' in input_data:
                inventory_snapshot_date = input_data['inventory_snapshot_date']

        # DIAGNOSTIC LOGGING for debugging infeasibility (using print to show in Streamlit)
        print("\n" + "=" * 80)
        print(f"WORKFLOW MODEL PARAMETERS [allow_shortages={self.config.allow_shortages}]")
        print(f"  start_date: {input_data['planning_start_date']}")
        print(f"  end_date: {input_data['planning_end_date']}")
        print(f"  inventory_snapshot_date: {inventory_snapshot_date}")
        print(f"  initial_inventory entries: {len(initial_inventory_dict)}")
        print(f"  initial_inventory total: {sum(initial_inventory_dict.values()):,.0f} units")
        print(f"  use_pallet_tracking: {self.config.use_pallet_costs}")
        print(f"  allow_shortages: {self.config.allow_shortages}")
        print("=" * 80)

        # Build model (using SlidingWindowModel for 60-220× speedup!)
        self.model = SlidingWindowModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=self.forecast,
            labor_calendar=self.labor_calendar,
            cost_structure=self.cost_structure,
            products=products_dict,
            start_date=input_data["planning_start_date"],
            end_date=input_data["planning_end_date"],
            truck_schedules=unified_trucks,
            initial_inventory=initial_inventory_dict,
            inventory_snapshot_date=inventory_snapshot_date,
            allow_shortages=self.config.allow_shortages,
            use_pallet_tracking=self.config.use_pallet_costs,  # Enabled
            use_truck_pallet_tracking=True,  # RE-ENABLED with fixed constraint
        )

        logger.info("Model built successfully")

    def _apply_warmstart(self) -> None:
        """Apply warmstart data to model variables.

        This is called after model is built and before solving.
        """
        if not self.warmstart_data or not self.model:
            return

        # Implementation will be added when warmstart module is ready
        logger.info("Warmstart application not yet implemented")
        pass

    def _solve_model(self) -> Optional[OptimizationResult]:
        """Solve the optimization model.

        Returns:
            OptimizationResult if solve successful, None otherwise
        """
        if not self.model:
            raise RuntimeError("Model not built. Call _build_model() first.")

        solution = self.model.solve(
            solver_name=self.config.solver_name,
            time_limit_seconds=self.config.solve_time_limit,
            mip_gap=self.config.mip_gap_tolerance,
        )

        return solution

    def _validate_solution(self, solution: Optional[OptimizationResult]) -> Dict[str, Any]:
        """Validate solution quality and feasibility.

        Args:
            solution: Solution to validate

        Returns:
            Dictionary with validation results
        """
        if solution is None:
            return {"valid": False, "message": "No solution returned from solver"}

        # Use OptimizationResult's built-in validation methods
        if not solution.is_feasible():
            from ..utils.version import GIT_COMMIT
            return {
                "valid": False,
                "message": f"Solution not feasible. Termination: {solution.termination_condition} [git:{GIT_COMMIT}]"
            }

        # Additional validation can be added here
        # - Check constraint violations
        # - Verify demand satisfaction
        # - Validate fixed periods (for Daily workflow)

        return {"valid": True, "message": "Solution validated successfully"}

    def _build_metadata(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build metadata dictionary for result.

        Args:
            input_data: Input data dictionary

        Returns:
            Metadata dictionary
        """
        # Get forecast entries count
        num_forecast_entries = 0
        if hasattr(self.forecast, 'entries'):
            num_forecast_entries = len(self.forecast.entries)
        elif isinstance(self.forecast, (list, tuple)):
            num_forecast_entries = len(self.forecast)

        return {
            "workflow_type": self.config.workflow_type.value,
            "planning_horizon_weeks": self.config.planning_horizon_weeks,
            "planning_start_date": input_data.get("planning_start_date").isoformat() if input_data.get("planning_start_date") else None,
            "planning_end_date": input_data.get("planning_end_date").isoformat() if input_data.get("planning_end_date") else None,
            "solver_name": self.config.solver_name,
            "used_warmstart": self.warmstart_data is not None,
            "num_locations": len(self.locations),
            "num_routes": len(self.routes),
            "num_products": len(self.products),
            "num_forecast_entries": num_forecast_entries,
        }
