"""Base class for optimization models.

This module provides an abstract base class that all optimization models inherit from,
providing common functionality for model building, solving, and result extraction.

IMPORTANT: All models must return OptimizationSolution (Pydantic validated) from extract_solution().
This ensures strict interface compliance and fail-fast validation at the model-UI boundary.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
import time
import math

from pyomo.environ import ConcreteModel, Objective, Constraint, Var, value
from pyomo.opt import SolverStatus, TerminationCondition

from .solver_config import SolverConfig

# Import OptimizationSolution for type hints
if TYPE_CHECKING:
    from .result_schema import OptimizationSolution

# Import ValidationError for fail-fast handling
from pydantic import ValidationError


@dataclass
class OptimizationResult:
    """
    Results from optimization model solve.

    Attributes:
        success: Whether optimization was successful
        objective_value: Optimal objective function value
        solver_status: Pyomo solver status
        termination_condition: Pyomo termination condition
        solve_time_seconds: Time taken to solve (seconds)
        solver_name: Name of solver used
        gap: MIP gap (if applicable)
        num_variables: Number of decision variables
        num_constraints: Number of constraints
        num_integer_vars: Number of integer/binary variables
        infeasibility_message: Message explaining why model is infeasible (if applicable)
        solver_output: Raw solver output (if captured)
        metadata: Additional result metadata
    """
    success: bool
    objective_value: Optional[float] = None
    solver_status: Optional[SolverStatus] = None
    termination_condition: Optional[TerminationCondition] = None
    solve_time_seconds: Optional[float] = None
    solver_name: Optional[str] = None
    gap: Optional[float] = None
    num_variables: int = 0
    num_constraints: int = 0
    num_integer_vars: int = 0
    infeasibility_message: Optional[str] = None
    solver_output: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_optimal(self) -> bool:
        """Check if solution is optimal."""
        return (
            self.success
            and self.termination_condition == TerminationCondition.optimal
        )

    def is_feasible(self) -> bool:
        """Check if solution is feasible (optimal or sub-optimal but valid).

        This includes:
        - optimal: Proven optimal solution
        - feasible: Valid but not proven optimal
        - maxTimeLimit: Hit time limit but has valid solution
        - intermediateNonInteger: MIP solver has valid solution but not integer-optimal
        - other: Check string representation for solver-specific feasible statuses
        """
        if not self.success:
            return False

        # Check for known feasible termination conditions
        if self.termination_condition in [
            TerminationCondition.optimal,
            TerminationCondition.feasible,
            TerminationCondition.maxTimeLimit,  # Hit time limit but has solution
        ]:
            return True

        # Check string representation for solver-specific statuses
        # Some solvers return custom termination conditions not in the enum
        if self.termination_condition is not None:
            tc_str = str(self.termination_condition).lower()
            # Accept any status containing these keywords
            feasible_keywords = ['optimal', 'feasible', 'intermediate']
            if any(keyword in tc_str for keyword in feasible_keywords):
                return True

        return False

    def is_infeasible(self) -> bool:
        """Check if model is infeasible."""
        return self.termination_condition == TerminationCondition.infeasible

    def __str__(self) -> str:
        """String representation."""
        if self.is_optimal():
            status = "OPTIMAL"
        elif self.is_feasible():
            status = "FEASIBLE"
        elif self.is_infeasible():
            status = "INFEASIBLE"
        else:
            status = f"{self.termination_condition}"

        result = f"OptimizationResult: {status}"
        if self.objective_value is not None:
            result += f", objective = {self.objective_value:,.2f}"
        if self.solve_time_seconds is not None:
            result += f", time = {self.solve_time_seconds:.2f}s"

        return result


class BaseOptimizationModel(ABC):
    """
    Abstract base class for optimization models.

    All optimization models should inherit from this class and implement:
    - build_model(): Construct the Pyomo model
    - extract_solution(): Extract solution from solved model

    This base class provides:
    - Solver configuration and management
    - Model building and solving workflow
    - Result extraction and validation
    - Error handling and diagnostics

    Example:
        class MyModel(BaseOptimizationModel):
            def __init__(self, data, solver_config=None):
                super().__init__(solver_config)
                self.data = data

            def build_model(self):
                model = ConcreteModel()
                # Add variables, constraints, objective
                return model

            def extract_solution(self, model):
                # Extract decision variable values
                return {"x": value(model.x)}

        # Use the model
        model = MyModel(data)
        result = model.solve()
        if result.is_optimal():
            solution = model.get_solution()
    """

    def __init__(self, solver_config: Optional[SolverConfig] = None):
        """
        Initialize optimization model.

        Args:
            solver_config: SolverConfig instance. If None, creates default config.
        """
        self.solver_config = solver_config or SolverConfig()
        self.model: Optional[ConcreteModel] = None
        self.result: Optional[OptimizationResult] = None
        self.solution: Optional['OptimizationSolution'] = None  # Now Pydantic validated
        self._build_time: Optional[float] = None

    @abstractmethod
    def build_model(self) -> ConcreteModel:
        """
        Build and return the Pyomo optimization model.

        This method must be implemented by subclasses.

        Returns:
            ConcreteModel: Pyomo model with variables, constraints, and objective

        Example:
            def build_model(self):
                model = ConcreteModel()
                model.x = Var(within=NonNegativeReals)
                model.y = Var(within=NonNegativeReals)
                model.obj = Objective(expr=model.x + model.y, sense=minimize)
                model.con = Constraint(expr=model.x + 2*model.y >= 10)
                return model
        """
        raise NotImplementedError("Subclass must implement build_model()")

    @abstractmethod
    def extract_solution(self, model: ConcreteModel) -> 'OptimizationSolution':
        """
        Extract solution values from the solved model.

        This method must be implemented by subclasses and MUST return
        a validated OptimizationSolution Pydantic model.

        Args:
            model: Solved Pyomo ConcreteModel

        Returns:
            OptimizationSolution: Validated solution data (Pydantic model)

        Raises:
            ValidationError: If solution data doesn't conform to schema

        Example:
            def extract_solution(self, model):
                from .result_schema import OptimizationSolution, ProductionBatchResult, ...

                # Extract data from model
                batches = [...]
                labor = {...}

                # Build and validate solution
                return OptimizationSolution(
                    model_type="sliding_window",
                    production_batches=batches,
                    labor_hours_by_date=labor,
                    shipments=shipments,
                    costs=costs,
                    total_cost=value(model.obj),
                    ...
                )
        """
        raise NotImplementedError("Subclass must implement extract_solution()")

    def _solve_with_appsi_highs(
        self,
        time_limit_seconds: Optional[float] = None,
        mip_gap: Optional[float] = None,
        use_warmstart: bool = False,
        use_aggressive_heuristics: bool = False,
        tee: bool = False,
    ) -> OptimizationResult:
        """
        Solve model using APPSI HiGHS solver (modern Pyomo interface).

        APPSI (Advanced Persistent Solver Interface) provides better performance
        for repeated solves and warmstarting.

        Args:
            time_limit_seconds: Maximum solve time
            mip_gap: MIP gap tolerance
            use_warmstart: Enable warmstart from variable initial values
            use_aggressive_heuristics: Enable aggressive MIP heuristics
            tee: Show solver output

        Returns:
            OptimizationResult
        """
        from pyomo.contrib.appsi.solvers import Highs
        import os

        # Create APPSI solver
        solver = Highs()

        # Configure solver
        if time_limit_seconds:
            solver.config.time_limit = time_limit_seconds
        if mip_gap:
            solver.config.mip_gap = mip_gap
        if use_warmstart:
            solver.config.warmstart = True
        if tee:
            solver.config.stream_solver = True

        # Configure HiGHS-specific options (same as legacy interface)
        solver.highs_options['presolve'] = 'on'
        solver.highs_options['parallel'] = 'on'
        solver.highs_options['threads'] = os.cpu_count() or 4
        solver.highs_options['mip_detect_symmetry'] = True

        if use_aggressive_heuristics:
            solver.highs_options['mip_heuristic_effort'] = 1.0
            solver.highs_options['mip_lp_age_limit'] = 10
            solver.highs_options['mip_heuristic_run_zi_round'] = True
            solver.highs_options['mip_heuristic_run_shifting'] = True
        else:
            solver.highs_options['mip_heuristic_effort'] = 0.5
            solver.highs_options['mip_lp_age_limit'] = 10

        # Solve
        solve_start = time.time()
        results = solver.solve(self.model)
        solve_time = time.time() - solve_start

        # Convert APPSI Results to our OptimizationResult
        # Check termination condition by name (APPSI has: optimal, infeasible, unbounded, etc.)
        from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC

        # Map APPSI termination conditions to legacy pyomo.opt.TerminationCondition
        # (OptimizationResult uses legacy enum for compatibility)
        appsi_tc = results.termination_condition
        if appsi_tc == AppsiTC.optimal:
            legacy_tc = TerminationCondition.optimal
            success = True
        elif appsi_tc == AppsiTC.infeasible:
            legacy_tc = TerminationCondition.infeasible
            success = False
        elif appsi_tc == AppsiTC.unbounded:
            legacy_tc = TerminationCondition.unbounded
            success = False
        elif appsi_tc == AppsiTC.maxTimeLimit:
            # Hit time limit - check if we have a feasible solution
            legacy_tc = TerminationCondition.maxTimeLimit
            success = (hasattr(results, 'best_feasible_objective') and
                      results.best_feasible_objective is not None)
        else:
            # Unknown or error condition
            legacy_tc = TerminationCondition.unknown
            success = False

        objective_value = getattr(results, 'best_feasible_objective', None)

        # Extract MIP gap from APPSI results
        gap = None
        if hasattr(results, 'best_objective_bound') and hasattr(results, 'best_feasible_objective'):
            bound = results.best_objective_bound
            obj = results.best_feasible_objective
            if bound is not None and obj is not None and abs(obj) > 1e-10:
                gap = abs((obj - bound) / obj)

        # Count variables and constraints
        num_vars = self.model.nvariables()
        num_cons = self.model.nconstraints()
        num_integer = sum(
            1 for var in self.model.component_data_objects(Var, active=True)
            if var.is_integer() or var.is_binary()
        )

        result = OptimizationResult(
            success=success,
            objective_value=objective_value,
            solver_status=None,  # APPSI doesn't have solver_status
            termination_condition=legacy_tc,  # Use converted legacy enum for compatibility
            solve_time_seconds=solve_time,
            solver_name='appsi_highs',
            gap=gap,
            num_variables=num_vars,
            num_constraints=num_cons,
            num_integer_vars=num_integer,
        )

        self.result = result

        # Extract solution if successful
        if success:
            try:
                # APPSI automatically loads solution into model
                self.solution = self.extract_solution(self.model)  # Returns OptimizationSolution (Pydantic)

                # Store solution data in result metadata (convert to dict)
                result.metadata.update(self.solution.model_dump(mode='json'))

                # Get objective from solution if not set
                if result.objective_value is None and hasattr(self.solution, 'total_cost'):
                    result.objective_value = self.solution.total_cost

                # Apply FEFO allocation if available (for batch-level detail)
                # Note: FEFO is now handled in extract_solution() which returns OptimizationSolution
                # with fefo fields populated. This code is kept for backward compatibility.
                if hasattr(self, 'apply_fefo_allocation'):
                    try:
                        fefo_detail = self.apply_fefo_allocation()
                        if fefo_detail:
                            # Update Pydantic model attributes (schema allows extra fields)
                            self.solution.fefo_batches = fefo_detail['batches']  # Dicts for JSON
                            self.solution.fefo_batch_objects = fefo_detail.get('batch_objects', [])  # Objects for UI
                            self.solution.fefo_batch_inventory = fefo_detail.get('batch_inventory', {})
                            self.solution.fefo_shipment_allocations = fefo_detail.get('shipment_allocations', [])

                            # Re-dump to metadata with FEFO data
                            result.metadata.update(self.solution.model_dump(mode='json'))
                    except Exception as e:
                        # FEFO is optional - don't fail if it errors
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"FEFO allocation failed: {e}")

            except ValidationError as ve:
                # Validation errors indicate a BUG in the model's extract_solution()
                # These should NOT be swallowed - they indicate programming errors
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"CRITICAL: Model violates OptimizationSolution schema: {ve}")
                raise  # Re-raise to fail fast
            except Exception as e:
                # Other exceptions (e.g., solver-specific issues) can be logged
                result.infeasibility_message = f"Warning: Solution extraction failed: {e}. Solve was successful but solution data unavailable."
                # Keep result.success = True (solver succeeded)
                result.metadata['solution_extraction_failed'] = True

        return result

    def solve(
        self,
        solver_name: Optional[str] = None,
        solver_options: Optional[Dict[str, Any]] = None,
        tee: bool = False,
        time_limit_seconds: Optional[float] = None,
        mip_gap: Optional[float] = None,
        use_aggressive_heuristics: bool = False,
        use_warmstart: bool = False,
    ) -> OptimizationResult:
        """
        Build and solve the optimization model.

        Args:
            solver_name: Name of solver to use (None = best available)
            solver_options: Additional solver options
            tee: If True, print solver output
            time_limit_seconds: Maximum solve time in seconds
            mip_gap: MIP gap tolerance (e.g., 0.01 for 1% gap)
            use_aggressive_heuristics: If True, enable aggressive heuristics for CBC
                (feasibility pump, RINS, proximity search, diving, etc.)
                Recommended for large problems (21+ day windows)
            use_warmstart: If True, pass warmstart flag to solver (requires variables
                to have initial values set via .set_value()). Used for MIP warmstarting.

        Returns:
            OptimizationResult with solve status and objective value

        Example:
            result = model.solve(
                solver_name='cbc',
                time_limit_seconds=300,
                mip_gap=0.01,
                use_aggressive_heuristics=True,  # For large problems
                use_warmstart=True,  # Use warmstart values if available
                tee=True
            )
        """
        # Build model
        build_start = time.time()
        self.model = self.build_model()
        self._build_time = time.time() - build_start

        # Prepare solver options
        options = solver_options or {}

        # Handle APPSI solvers (different interface than legacy SolverFactory)
        if solver_name == 'appsi_highs':
            return self._solve_with_appsi_highs(
                time_limit_seconds=time_limit_seconds,
                mip_gap=mip_gap,
                use_warmstart=use_warmstart,
                use_aggressive_heuristics=use_aggressive_heuristics,
                tee=tee
            )

        # Configure solver-specific options (legacy interface)
        if solver_name in ['cbc', 'asl:cbc'] or (solver_name is None and self.solver_config.get_best_available_solver() in ['cbc', 'asl:cbc']):
            # CBC-specific options
            if use_aggressive_heuristics:
                # Aggressive heuristics for large problems (e.g., 21+ day windows)
                # These settings enable TABU-like search, proximity search, and other heuristics
                aggressive_options = {
                    'seconds': time_limit_seconds if time_limit_seconds else 120,
                    'ratio': mip_gap if mip_gap else 0.01,
                    # Preprocessing
                    'preprocess': 'sos',
                    'passPresolve': 10,
                    # Heuristics (THE KEY!)
                    'heuristics': 'on',
                    'feaspump': 'on',     # Feasibility pump
                    'rins': 'on',         # RINS (TABU-like)
                    'diving': 'on',       # Diving
                    'proximity': 'on',    # Proximity search (TABU-like!)
                    'combine': 'on',      # Combine solutions
                    # Cuts
                    'cuts': 'on',
                    'gomory': 'on',
                    'knapsack': 'on',
                    'probing': 'on',
                    'clique': 'on',
                    # Strategy
                    'strategy': 1,        # Aggressive
                    'tune': 2,            # Maximum auto-tune
                }
                options.update(aggressive_options)
            else:
                # Standard CBC options (without aggressive heuristics)
                # CRITICAL: MUST set timeout and gap for normal mode too!
                standard_options = {}
                if time_limit_seconds is not None:
                    standard_options['seconds'] = time_limit_seconds
                if mip_gap is not None:
                    standard_options['ratio'] = mip_gap
                if standard_options:
                    options.update(standard_options)
        elif solver_name == 'gurobi':
            if time_limit_seconds is not None:
                options['TimeLimit'] = time_limit_seconds
            if mip_gap is not None:
                options['MIPGap'] = mip_gap
        elif solver_name == 'cplex':
            if time_limit_seconds is not None:
                options['timelimit'] = time_limit_seconds
            if mip_gap is not None:
                options['mip_tolerances_mipgap'] = mip_gap
        elif solver_name == 'highs':
            # HiGHS-specific options
            # HiGHS uses different parameter names than CBC/Gurobi/CPLEX
            import os

            # CRITICAL: ALWAYS enable presolve (HiGHS's main advantage - reduces problem by 60-70%)
            # Previously this was only enabled with aggressive_heuristics flag, causing poor performance
            options['presolve'] = 'on'

            # ALWAYS enable parallel mode and threads
            options['parallel'] = 'on'
            options['threads'] = os.cpu_count() or 4

            if time_limit_seconds is not None:
                options['time_limit'] = time_limit_seconds
            if mip_gap is not None:
                options['mip_rel_gap'] = mip_gap

            # Essential HiGHS MIP options (ALWAYS enabled for MIP problems)
            options['mip_detect_symmetry'] = True  # Symmetry detection (very powerful for MIP)
            # Let HiGHS choose best simplex strategy (auto-select between serial/parallel dual)
            # Testing showed: strategy=1 (serial dual) best for small problems,
            #                strategy=2 (parallel dual) better for large problems
            # Default (no setting) lets HiGHS decide based on problem structure

            # Additional aggressive options for large problems
            if use_aggressive_heuristics:
                options['mip_heuristic_effort'] = 1.0  # Maximum heuristic effort (0.0-1.0)
                options['mip_lp_age_limit'] = 10  # Standard cut aging
                options['mip_heuristic_run_zi_round'] = True  # Enable ZI Round heuristic
                options['mip_heuristic_run_shifting'] = True  # Enable Shifting heuristic
            else:
                # Standard MIP heuristics (10x better than HiGHS default of 0.05!)
                options['mip_heuristic_effort'] = 0.5  # Moderate heuristic effort
                options['mip_lp_age_limit'] = 10  # Standard LP age limit (HiGHS default)

        # Create solver
        try:
            solver = self.solver_config.create_solver(solver_name, options)
        except RuntimeError as e:
            # No solver available
            return OptimizationResult(
                success=False,
                infeasibility_message=str(e),
                num_variables=self.model.nvariables() if self.model else 0,
                num_constraints=self.model.nconstraints() if self.model else 0,
            )

        # Solve
        solve_start = time.time()

        # Pass options to avoid compatibility issues with CBC
        # symbolic_solver_labels=False prevents -printingOptions error
        # load_solutions=False to handle errors more gracefully
        # warmstart=True tells solver to use variable initial values (CBC only)

        # HiGHS doesn't support warmstart kwarg - only CBC/Gurobi/CPLEX do
        solve_kwargs = {
            'tee': tee,
            'symbolic_solver_labels': False,
            'load_solutions': False,  # Load manually to handle errors better
        }

        # Only pass warmstart for solvers that support it
        if use_warmstart and solver_name not in ['highs']:
            solve_kwargs['warmstart'] = True

        results = solver.solve(self.model, **solve_kwargs)
        solve_time = time.time() - solve_start

        # Extract result information
        result = self._process_results(results, solver_name, solve_time)
        self.result = result

        # Load solutions and extract if successful
        if result.is_feasible():
            try:
                # Load solution into model
                self.model.solutions.load_from(results)

                # Get objective value from model if not already set or if it's infinity
                # (results.problem.upper_bound is infinity for minimization problems)
                if (result.objective_value is None or math.isinf(result.objective_value)) and hasattr(self.model, 'obj'):
                    try:
                        result.objective_value = value(self.model.obj)
                    except (ValueError, AttributeError, KeyError, RuntimeError):
                        # Objective expression may reference uninitialized variables
                        # This can happen when costs are 0 and solver skips those variables
                        # Objective value should already be in results.solution
                        pass

                # Extract solution to our format
                self.solution = self.extract_solution(self.model)  # Returns OptimizationSolution (Pydantic)

                # Store solution data in result metadata for easy access (convert to dict)
                result.metadata.update(self.solution.model_dump(mode='json'))

                # If objective value is still missing, try to get it from extracted solution
                if result.objective_value is None and hasattr(self.solution, 'total_cost'):
                    result.objective_value = self.solution.total_cost
            except ValidationError as ve:
                # Validation errors indicate a BUG in the model's extract_solution()
                # These should NOT be swallowed - they indicate programming errors
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"CRITICAL: Model violates OptimizationSolution schema: {ve}")
                raise  # Re-raise to fail fast
            except Exception as e:
                # Other exceptions (e.g., solver-specific issues) can be logged
                result.infeasibility_message = f"Warning: Solution extraction failed: {e}. Solve was successful but solution data unavailable."
                # Keep result.success = True (solver succeeded)
                result.metadata['solution_extraction_failed'] = True

        return result

    def _process_results(
        self,
        results,
        solver_name: Optional[str],
        solve_time: float
    ) -> OptimizationResult:
        """
        Process solver results into OptimizationResult.

        Args:
            results: Pyomo solver results
            solver_name: Name of solver used
            solve_time: Time taken to solve

        Returns:
            OptimizationResult
        """
        # Extract solver status and termination condition
        solver_status = results.solver.status if hasattr(results, 'solver') else None
        termination_condition = results.solver.termination_condition if hasattr(results, 'solver') else None

        # Determine success (optimal or feasible solution found)
        success = (
            solver_status == SolverStatus.ok
            and termination_condition in [
                TerminationCondition.optimal,
                TerminationCondition.feasible,
                TerminationCondition.maxTimeLimit,  # Hit time limit but has solution
            ]
        )

        # Get objective value
        objective_value = None
        if hasattr(results.problem, 'upper_bound'):
            # For minimization, upper_bound is the objective value
            objective_value = results.problem.upper_bound
            # Check if it's infinity (no solution found)
            if objective_value is not None and math.isinf(objective_value):
                objective_value = None

        # Extract MIP gap if available
        gap = None
        if hasattr(results.problem, 'upper_bound') and hasattr(results.problem, 'lower_bound'):
            ub = results.problem.upper_bound
            lb = results.problem.lower_bound
            # Only calculate gap if both bounds are finite and non-zero
            if (ub is not None and lb is not None and
                math.isfinite(ub) and math.isfinite(lb) and
                abs(ub) > 1e-10):
                gap = abs((ub - lb) / ub)

        # Count variables and constraints
        num_vars = self.model.nvariables() if self.model else 0
        num_cons = self.model.nconstraints() if self.model else 0

        # Count integer variables
        num_integer = 0
        if self.model:
            for var in self.model.component_data_objects(Var, active=True):
                if var.is_integer() or var.is_binary():
                    num_integer += 1

        # Infeasibility message
        infeasibility_message = None
        if termination_condition == TerminationCondition.infeasible:
            infeasibility_message = (
                "Model is infeasible. Constraints cannot all be satisfied simultaneously."
            )
        elif not success:
            # Try to get more detailed error info
            error_details = f"Status: {solver_status}, Termination: {termination_condition}"

            # Check for solver message
            if hasattr(results.solver, 'message') and results.solver.message:
                error_details += f", Message: {results.solver.message}"

            # Check for error messages in results
            if hasattr(results.solver, 'error') and results.solver.error:
                error_details += f", Error: {results.solver.error}"

            infeasibility_message = f"Solver failed - {error_details}"

        return OptimizationResult(
            success=success,
            objective_value=objective_value,
            solver_status=solver_status,
            termination_condition=termination_condition,
            solve_time_seconds=solve_time,
            solver_name=solver_name,
            gap=gap,
            num_variables=num_vars,
            num_constraints=num_cons,
            num_integer_vars=num_integer,
            infeasibility_message=infeasibility_message,
        )

    def get_solution(self) -> Optional['OptimizationSolution']:
        """
        Get extracted solution from last solve.

        Returns:
            OptimizationSolution (Pydantic validated), or None if not solved or infeasible

        Example:
            result = model.solve()
            if result.is_optimal():
                solution = model.get_solution()
                print(f"Total cost: {solution.total_cost}")
                print(f"Production batches: {len(solution.production_batches)}")
        """
        return self.solution

    def get_model_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the model.

        Returns:
            Dictionary with model statistics

        Example:
            stats = model.get_model_statistics()
            print(f"Variables: {stats['num_variables']}")
            print(f"Constraints: {stats['num_constraints']}")
        """
        if self.model is None:
            return {
                'built': False,
                'num_variables': 0,
                'num_constraints': 0,
                'num_integer_vars': 0,
            }

        # Count integer variables
        num_integer = sum(
            1 for var in self.model.component_data_objects(Var, active=True)
            if var.is_integer() or var.is_binary()
        )

        return {
            'built': True,
            'build_time_seconds': self._build_time,
            'num_variables': self.model.nvariables(),
            'num_constraints': self.model.nconstraints(),
            'num_integer_vars': num_integer,
        }

    def get_build_time(self) -> Optional[float]:
        """
        Get model build time in seconds.

        Returns:
            Build time in seconds, or None if model not built
        """
        return self._build_time

    def reset(self):
        """
        Reset the model state.

        Clears the built model, results, and solution.
        Useful for rebuilding the model with different parameters.
        """
        self.model = None
        self.result = None
        self.solution = None
        self._build_time = None
