"""Base class for optimization models.

This module provides an abstract base class that all optimization models inherit from,
providing common functionality for model building, solving, and result extraction.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import time

from pyomo.environ import ConcreteModel, Objective, Constraint, Var, value
from pyomo.opt import SolverStatus, TerminationCondition

from .solver_config import SolverConfig


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
        """Check if solution is feasible (optimal or sub-optimal but valid)."""
        return (
            self.success
            and self.termination_condition in [
                TerminationCondition.optimal,
                TerminationCondition.feasible,
                TerminationCondition.maxTimeLimit,  # Hit time limit but has solution
            ]
        )

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
        self.solution: Optional[Dict[str, Any]] = None
        self._build_time: Optional[float] = None

    @abstractmethod
    def build_model(self) -> ConcreteModel:
        """
        Build and return the Pyomo optimization model.

        This method must be implemented by subclasses.

        Returns:
            ConcreteModel with variables, constraints, and objective

        Example:
            def build_model(self):
                model = ConcreteModel()
                model.x = Var(within=NonNegativeReals)
                model.obj = Objective(expr=model.x)
                model.con = Constraint(expr=model.x >= 1)
                return model
        """
        pass

    @abstractmethod
    def extract_solution(self, model: ConcreteModel) -> Dict[str, Any]:
        """
        Extract solution from solved model.

        This method must be implemented by subclasses.

        Args:
            model: Solved Pyomo model

        Returns:
            Dictionary containing extracted solution values

        Example:
            def extract_solution(self, model):
                return {
                    "x_value": value(model.x),
                    "objective": value(model.obj)
                }
        """
        pass

    def solve(
        self,
        solver_name: Optional[str] = None,
        solver_options: Optional[Dict[str, Any]] = None,
        tee: bool = False,
        time_limit_seconds: Optional[float] = None,
        mip_gap: Optional[float] = None,
    ) -> OptimizationResult:
        """
        Build and solve the optimization model.

        Args:
            solver_name: Name of solver to use (None = best available)
            solver_options: Additional solver options
            tee: If True, print solver output
            time_limit_seconds: Maximum solve time in seconds
            mip_gap: MIP gap tolerance (e.g., 0.01 for 1% gap)

        Returns:
            OptimizationResult with solve status and objective value

        Example:
            result = model.solve(
                solver_name='cbc',
                time_limit_seconds=300,
                mip_gap=0.01,
                tee=True
            )
        """
        # Build model
        build_start = time.time()
        self.model = self.build_model()
        self._build_time = time.time() - build_start

        # Prepare solver options
        options = solver_options or {}

        # For CBC 2.10.12+, avoid passing options that may not be recognized
        # Only set options if explicitly provided or for commercial solvers
        if solver_name not in ['cbc', 'asl:cbc', None]:
            if time_limit_seconds is not None:
                # Set time limit (solver-specific parameter names)
                if solver_name == 'gurobi':
                    options['TimeLimit'] = time_limit_seconds
                elif solver_name == 'cplex':
                    options['timelimit'] = time_limit_seconds

            if mip_gap is not None:
                # Set MIP gap (solver-specific parameter names)
                if solver_name == 'gurobi':
                    options['MIPGap'] = mip_gap
                elif solver_name == 'cplex':
                    options['mip_tolerances_mipgap'] = mip_gap
        # For CBC, let it run with defaults to avoid option compatibility issues
        # Time limit and gap can still be passed via solver_options if needed

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
        results = solver.solve(
            self.model,
            tee=tee,
            symbolic_solver_labels=False,
            load_solutions=False,  # Load manually to handle errors better
        )
        solve_time = time.time() - solve_start

        # Extract result information
        result = self._process_results(results, solver_name, solve_time)
        self.result = result

        # Load solutions and extract if successful
        if result.is_feasible():
            try:
                # Load solution into model
                self.model.solutions.load_from(results)
                # Extract solution to our format
                self.solution = self.extract_solution(self.model)
            except Exception as e:
                result.infeasibility_message = f"Error extracting solution: {e}"
                result.success = False

        return result

    def _process_results(
        self,
        results,
        solver_name: str,
        solve_time: float
    ) -> OptimizationResult:
        """
        Process Pyomo solver results into OptimizationResult.

        Args:
            results: Pyomo solver results
            solver_name: Name of solver used
            solve_time: Time taken to solve

        Returns:
            OptimizationResult
        """
        solver_status = results.solver.status
        termination_condition = results.solver.termination_condition

        # Check if successful
        success = (
            solver_status == SolverStatus.ok
            and termination_condition in [
                TerminationCondition.optimal,
                TerminationCondition.feasible,
                TerminationCondition.maxTimeLimit,
            ]
        )

        # Get objective value
        objective_value = None
        if success and hasattr(self.model, 'obj'):
            try:
                objective_value = value(self.model.obj)
            except:
                objective_value = None

        # Get gap if available
        gap = None
        if hasattr(results.problem, 'upper_bound') and hasattr(results.problem, 'lower_bound'):
            ub = results.problem.upper_bound
            lb = results.problem.lower_bound
            if ub is not None and lb is not None and abs(ub) > 1e-10:
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

    def get_solution(self) -> Optional[Dict[str, Any]]:
        """
        Get extracted solution from last solve.

        Returns:
            Solution dictionary, or None if not solved or infeasible

        Example:
            result = model.solve()
            if result.is_optimal():
                solution = model.get_solution()
                print(f"x = {solution['x_value']}")
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
            'num_continuous_vars': self.model.nvariables() - num_integer,
        }

    def print_model_summary(self) -> None:
        """
        Print summary of model structure.

        Example:
            model = MyModel(data)
            model.solve()
            model.print_model_summary()
        """
        print("=" * 60)
        print("Optimization Model Summary")
        print("=" * 60)

        stats = self.get_model_statistics()
        if not stats['built']:
            print("Model not yet built")
            return

        print(f"Variables:       {stats['num_variables']:,}")
        print(f"  Continuous:    {stats['num_continuous_vars']:,}")
        print(f"  Integer/Binary: {stats['num_integer_vars']:,}")
        print(f"Constraints:     {stats['num_constraints']:,}")
        if stats['build_time_seconds']:
            print(f"Build time:      {stats['build_time_seconds']:.2f} seconds")

        if self.result:
            print()
            print(f"Solve status:    {self.result.termination_condition}")
            if self.result.objective_value is not None:
                print(f"Objective value: {self.result.objective_value:,.2f}")
            if self.result.solve_time_seconds is not None:
                print(f"Solve time:      {self.result.solve_time_seconds:.2f} seconds")
            if self.result.gap is not None:
                print(f"MIP gap:         {self.result.gap*100:.2f}%")

        print("=" * 60)

    def write_model(self, filename: str) -> None:
        """
        Write model to file in LP or MPS format.

        Args:
            filename: Output filename (.lp or .mps extension)

        Example:
            model = MyModel(data)
            model.solve()
            model.write_model("model.lp")  # For debugging
        """
        if self.model is None:
            raise RuntimeError("Model not yet built. Call solve() first.")

        self.model.write(filename)

    def __str__(self) -> str:
        """String representation."""
        stats = self.get_model_statistics()
        if not stats['built']:
            return f"{self.__class__.__name__} (not built)"

        status = "built"
        if self.result:
            if self.result.is_optimal():
                status = "optimal"
            elif self.result.is_feasible():
                status = "feasible"
            elif self.result.is_infeasible():
                status = "infeasible"
            else:
                status = str(self.result.termination_condition)

        return (
            f"{self.__class__.__name__} "
            f"({stats['num_variables']} vars, {stats['num_constraints']} cons, {status})"
        )
