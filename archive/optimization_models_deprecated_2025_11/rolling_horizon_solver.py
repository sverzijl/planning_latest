"""Rolling horizon solver for long-term production planning.

This module implements a rolling horizon approach that solves large planning
problems by breaking them into smaller overlapping windows, solving each
independently, and stitching the solutions together.
"""

from datetime import date as Date, timedelta
from typing import Dict, List, Tuple, Optional, Any
import time
import warnings

from src.models.forecast import Forecast
from src.models.labor_calendar import LaborCalendar
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location
from src.models.route import Route
from src.models.truck_schedule import TruckScheduleCollection
from src.models.time_period import (
    VariableGranularityConfig,
    create_uniform_buckets,
    create_variable_granularity_buckets,
)
from src.models.forecast_aggregator import aggregate_forecast_to_buckets
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.optimization.window_config import (
    WindowConfig,
    WindowSolution,
    RollingHorizonResult,
    create_windows,
)
from src.optimization.solver_config import SolverConfig


class RollingHorizonSolver:
    """
    Rolling horizon solver for long-term production-distribution planning.

    Breaks large planning horizons into smaller overlapping windows, solves
    each window independently, and combines solutions.

    Attributes:
        labor_calendar: Labor availability and costs
        manufacturing_site: Manufacturing site configuration
        cost_structure: Cost parameters
        locations: Network locations
        routes: Network routes
        truck_schedules: Optional truck schedules
        solver_config: Solver configuration
        window_size_days: Size of each window in days (default: 28 = 4 weeks)
        overlap_days: Overlap between windows in days (default: 7 = 1 week)
        max_routes_per_destination: Max routes to enumerate per destination
        allow_shortages: Whether to allow demand shortages
        enforce_shelf_life: Whether to enforce shelf life constraints
        time_limit_per_window: Time limit for each window solve (seconds)
        mip_gap: MIP gap tolerance

    Example:
        solver = RollingHorizonSolver(
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            truck_schedules=truck_schedules,
            window_size_days=28,  # 4 weeks
            overlap_days=7,  # 1 week overlap
        )

        result = solver.solve(
            forecast=full_29week_forecast,
            granularity_config=None,  # Optional temporal aggregation
            verbose=True
        )

        if result.all_feasible:
            print(f"Total cost: ${result.total_cost:,.2f}")
            print(f"Solve time: {result.total_solve_time:.2f}s")
    """

    def __init__(
        self,
        labor_calendar: LaborCalendar,
        manufacturing_site: ManufacturingSite,
        cost_structure: CostStructure,
        locations: List[Location],
        routes: List[Route],
        truck_schedules: Optional[TruckScheduleCollection] = None,
        solver_config: Optional[SolverConfig] = None,
        window_size_days: int = 28,
        overlap_days: int = 7,
        max_routes_per_destination: int = 5,
        allow_shortages: bool = True,
        enforce_shelf_life: bool = True,
        time_limit_per_window: int = 300,
        mip_gap: float = 0.01,
    ):
        """
        Initialize rolling horizon solver.

        Args:
            labor_calendar: Labor availability and costs
            manufacturing_site: Manufacturing site configuration
            cost_structure: Cost parameters
            locations: All network locations
            routes: All network routes
            truck_schedules: Optional truck schedules
            solver_config: Solver configuration
            window_size_days: Window size in days (default: 28 = 4 weeks)
            overlap_days: Overlap in days (default: 7 = 1 week)
            max_routes_per_destination: Max routes per destination
            allow_shortages: Allow demand shortages (default: True for robustness)
            enforce_shelf_life: Enforce shelf life constraints
            time_limit_per_window: Time limit per window in seconds
            mip_gap: MIP gap tolerance
        """
        self.labor_calendar = labor_calendar
        self.manufacturing_site = manufacturing_site
        self.cost_structure = cost_structure
        self.locations = locations
        self.routes = routes
        self.truck_schedules = truck_schedules
        self.solver_config = solver_config or SolverConfig()

        self.window_size_days = window_size_days
        self.overlap_days = overlap_days
        self.max_routes_per_destination = max_routes_per_destination
        self.allow_shortages = allow_shortages
        self.enforce_shelf_life = enforce_shelf_life
        self.time_limit_per_window = time_limit_per_window
        self.mip_gap = mip_gap

        if window_size_days <= overlap_days:
            raise ValueError(
                f"window_size_days ({window_size_days}) must be > overlap_days ({overlap_days})"
            )

    def solve(
        self,
        forecast: Forecast,
        initial_inventory: Optional[Dict[Tuple[str, str], float]] = None,
        granularity_config: Optional[VariableGranularityConfig] = None,
        solver_name: str = 'cbc',
        use_aggressive_heuristics: bool = False,
        verbose: bool = True,
    ) -> RollingHorizonResult:
        """
        Solve forecast using rolling horizon approach.

        Args:
            forecast: Full forecast to solve
            initial_inventory: Initial inventory (default: empty)
            granularity_config: Optional temporal aggregation config
            solver_name: Solver to use ('cbc', 'gurobi', 'cplex')
            use_aggressive_heuristics: Enable aggressive heuristics for CBC
                (recommended for 21+ day windows)
            verbose: Print progress messages

        Returns:
            RollingHorizonResult with complete solution

        Example:
            result = solver.solve(
                forecast=full_forecast,
                granularity_config=VariableGranularityConfig(
                    near_term_days=7,
                    near_term_granularity=BucketGranularity.DAILY,
                    far_term_granularity=BucketGranularity.TWO_DAY
                ),
                use_aggressive_heuristics=True,  # For 21+ day windows
                verbose=True
            )
        """
        if verbose:
            print("=" * 70)
            print("ROLLING HORIZON SOLVER")
            print("=" * 70)

        # Get planning horizon from forecast
        if not forecast.entries:
            raise ValueError("Forecast has no entries")

        start_date = min(e.forecast_date for e in forecast.entries)
        end_date = max(e.forecast_date for e in forecast.entries)
        total_days = (end_date - start_date).days + 1

        if verbose:
            print(f"\nPlanning horizon: {start_date} to {end_date} ({total_days} days)")
            print(f"Window size: {self.window_size_days} days")
            print(f"Overlap: {self.overlap_days} days")
            print(f"Temporal aggregation: {'Yes' if granularity_config else 'No'}")

        # Create windows
        if verbose:
            print(f"\nCreating windows...")

        windows = create_windows(
            start_date=start_date,
            end_date=end_date,
            window_size_days=self.window_size_days,
            overlap_days=self.overlap_days,
            forecast=forecast,
            initial_inventory=initial_inventory or {}
        )

        if verbose:
            print(f"  Created {len(windows)} windows")
            for i, window in enumerate(windows, 1):
                print(f"    {i}. {window}")

        # Solve each window
        window_solutions = []
        total_solve_time = 0.0
        all_feasible = True

        for i, window in enumerate(windows, 1):
            if verbose:
                print(f"\n{'=' * 70}")
                print(f"SOLVING WINDOW {i}/{len(windows)}: {window.window_id}")
                print(f"{'=' * 70}")
                print(f"  Dates: {window.start_date} to {window.end_date} ({window.num_days} days)")
                print(f"  Demand entries: {len(window.forecast_subset.entries)}")
                if window.initial_inventory:
                    total_units = sum(window.initial_inventory.values())
                    print(f"  Initial inventory: {len(window.initial_inventory)} SKUs, {total_units:,.0f} total units")
                    # Show breakdown by product if verbose
                    if verbose and len(window.initial_inventory) <= 10:
                        for (dest, prod), qty in window.initial_inventory.items():
                            print(f"    - {dest}/{prod}: {qty:,.0f} units")

            # Solve this window
            try:
                window_solution = self._solve_window(
                    window=window,
                    granularity_config=granularity_config,
                    solver_name=solver_name,
                    use_aggressive_heuristics=use_aggressive_heuristics,
                    verbose=verbose
                )

                window_solutions.append(window_solution)
                total_solve_time += window_solution.solve_time_seconds

                if not window_solution.is_feasible():
                    all_feasible = False
                    if verbose:
                        print(f"\n  ❌ Window {window.window_id} is INFEASIBLE")
                        if window_solution.optimization_result.infeasibility_message:
                            print(f"     {window_solution.optimization_result.infeasibility_message}")
                else:
                    if verbose:
                        status = "OPTIMAL" if window_solution.is_optimal() else "FEASIBLE"
                        print(f"\n  ✅ Window {window.window_id} solved: {status}")
                        print(f"     Cost: ${window_solution.total_cost:,.2f}")
                        print(f"     Time: {window_solution.solve_time_seconds:.2f}s")

                        # Show ending inventory
                        if window_solution.ending_inventory:
                            total_ending = sum(window_solution.ending_inventory.values())
                            print(f"     Ending inventory: {len(window_solution.ending_inventory)} SKUs, {total_ending:,.0f} total units")
                            if len(window_solution.ending_inventory) <= 10:
                                for (dest, prod), qty in window_solution.ending_inventory.items():
                                    print(f"       - {dest}/{prod}: {qty:,.0f} units")

                # Update initial inventory for next window (if not last)
                if i < len(windows):
                    # Only update if window was feasible
                    if window_solution.is_feasible():
                        windows[i].initial_inventory = window_solution.ending_inventory.copy()
                        if verbose:
                            print(f"     → Inventory passed to Window {windows[i].window_id}")
                    else:
                        # Keep previous initial_inventory (don't break the chain)
                        if verbose:
                            print(f"     ⚠ Preserving inventory for Window {windows[i].window_id} (window was infeasible)")

            except Exception as e:
                if verbose:
                    print(f"\n  ❌ Error solving window {window.window_id}: {e}")

                # Create failed result
                from src.optimization.base_model import OptimizationResult
                from pyomo.opt import TerminationCondition

                failed_result = OptimizationResult(
                    success=False,
                    termination_condition=TerminationCondition.error,
                    infeasibility_message=str(e)
                )

                window_solution = WindowSolution(
                    window_id=window.window_id,
                    optimization_result=failed_result
                )

                window_solutions.append(window_solution)
                all_feasible = False

        # Stitch solutions together
        if verbose:
            print(f"\n{'=' * 70}")
            print("STITCHING SOLUTIONS")
            print(f"{'=' * 70}")

        stitched_result = self._stitch_solutions(
            windows=windows,
            window_solutions=window_solutions,
            verbose=verbose
        )

        # Create final result
        result = RollingHorizonResult(
            window_results=window_solutions,
            complete_production_plan=stitched_result['production_plan'],
            complete_shipment_plan=stitched_result['shipments'],
            total_cost=stitched_result['total_cost'],
            total_solve_time=total_solve_time,
            num_windows=len(windows),
            all_feasible=all_feasible,
            metadata={
                'window_size_days': self.window_size_days,
                'overlap_days': self.overlap_days,
                'total_horizon_days': total_days,
                'granularity_config': granularity_config,
            }
        )

        if verbose:
            print(f"\n{'=' * 70}")
            print("ROLLING HORIZON COMPLETE")
            print(f"{'=' * 70}")
            print(f"\n{result}")
            if not all_feasible:
                print(f"\n  Infeasible windows: {result.infeasible_windows}")

        return result

    def _solve_window(
        self,
        window: WindowConfig,
        granularity_config: Optional[VariableGranularityConfig],
        solver_name: str,
        use_aggressive_heuristics: bool,
        verbose: bool
    ) -> WindowSolution:
        """
        Solve a single window.

        Args:
            window: Window configuration
            granularity_config: Optional temporal aggregation
            solver_name: Solver to use
            verbose: Print progress

        Returns:
            WindowSolution with results
        """
        # Apply temporal aggregation if configured
        forecast_to_solve = window.forecast_subset

        if granularity_config is not None:
            if verbose:
                print(f"  Applying temporal aggregation: {granularity_config}")

            # Create buckets
            buckets = create_variable_granularity_buckets(
                start_date=window.start_date,
                end_date=window.end_date,
                config=granularity_config
            )

            if verbose:
                print(f"    Created {len(buckets)} time buckets (from {window.num_days} days)")

            # Aggregate forecast
            forecast_to_solve = aggregate_forecast_to_buckets(
                forecast=window.forecast_subset,
                buckets=buckets
            )

            if verbose:
                print(f"    Aggregated forecast: {len(forecast_to_solve.entries)} entries")

        # Build and solve model
        if verbose:
            print(f"  Building optimization model...")

        model = IntegratedProductionDistributionModel(
            forecast=forecast_to_solve,
            labor_calendar=self.labor_calendar,
            manufacturing_site=self.manufacturing_site,
            cost_structure=self.cost_structure,
            locations=self.locations,
            routes=self.routes,
            truck_schedules=self.truck_schedules,
            solver_config=self.solver_config,
            max_routes_per_destination=self.max_routes_per_destination,
            allow_shortages=self.allow_shortages,
            enforce_shelf_life=self.enforce_shelf_life,
            initial_inventory=window.initial_inventory,
        )

        if verbose:
            print(f"  Solving with {solver_name}...")

        start_time = time.time()
        result = model.solve(
            solver_name=solver_name,
            time_limit_seconds=self.time_limit_per_window,
            mip_gap=self.mip_gap,
            use_aggressive_heuristics=use_aggressive_heuristics,
            tee=False  # Don't print solver output
        )
        solve_time = time.time() - start_time

        # Extract solution
        solution_data = model.get_solution()

        if solution_data is None:
            # No solution extracted
            return WindowSolution(
                window_id=window.window_id,
                optimization_result=result,
                solve_time_seconds=solve_time
            )

        # Extract ending inventory at committed region end (handoff point)
        ending_inventory = self._extract_ending_inventory(
            solution_data=solution_data,
            window=window
        )

        # Create window solution with cost breakdown
        window_solution = WindowSolution(
            window_id=window.window_id,
            optimization_result=result,
            production_by_date_product=solution_data.get('production_by_date_product', {}),
            shipments_by_route_product_date=solution_data.get('shipments_by_route_product_date', {}),
            ending_inventory=ending_inventory,
            total_cost=result.objective_value or 0.0,
            labor_cost=solution_data.get('total_labor_cost', 0.0),
            production_cost=solution_data.get('total_production_cost', 0.0),
            transport_cost=solution_data.get('total_transport_cost', 0.0),
            inventory_cost=solution_data.get('total_inventory_cost', 0.0),
            truck_cost=solution_data.get('total_truck_cost', 0.0),
            shortage_cost=solution_data.get('total_shortage_cost', 0.0),
            labor_cost_by_date=solution_data.get('labor_cost_by_date', {}),
            solve_time_seconds=solve_time,
            production_batches=solution_data.get('production_batches', []),
            shipments=solution_data.get('shipments', []),
        )

        return window_solution

    def _extract_ending_inventory(
        self,
        solution_data: Dict,
        window: WindowConfig
    ) -> Dict[Tuple[str, str], float]:
        """
        Extract ending inventory from window solution at window end.

        This extracts inventory at the end of the full window (including overlap region)
        to ensure the next window has sufficient starting inventory.

        Args:
            solution_data: Solution dictionary from model
            window: Window configuration (to get window_end_date)

        Returns:
            Dict mapping (dest_id, product_id) -> quantity
        """
        ending_inventory = {}

        inventory_by_dest_prod_date = solution_data.get('inventory_by_dest_prod_date', {})

        # Use committed_end_date as handoff point (not window_end_date)
        # This ensures next window gets inventory from correct transition point
        handoff_date = window.committed_end_date

        for (dest, prod, date), quantity in inventory_by_dest_prod_date.items():
            if date == handoff_date and quantity > 1e-6:
                ending_inventory[(dest, prod)] = quantity

        return ending_inventory

    def _stitch_solutions(
        self,
        windows: List[WindowConfig],
        window_solutions: List[WindowSolution],
        verbose: bool
    ) -> Dict[str, Any]:
        """
        Stitch window solutions into complete plan.

        Uses only the committed (non-overlap) portion of each window.

        Args:
            windows: Window configurations
            window_solutions: Solutions for each window
            verbose: Print progress

        Returns:
            Dict with 'production_plan', 'shipments', 'total_cost'
        """
        complete_production = {}
        complete_shipments = []
        total_cost = 0.0

        for window, solution in zip(windows, window_solutions):
            if not solution.is_feasible():
                continue

            # Determine committed date range (exclude overlap)
            committed_end = window.committed_end_date

            if verbose:
                committed_days = (committed_end - window.start_date).days + 1
                print(f"  {window.window_id}: Using {committed_days} committed days "
                      f"({window.start_date} to {committed_end})")

            # Add production from committed region
            # Handle both formats: Dict[Tuple[Date, str], float] and Dict[Date, Dict[str, float]]
            for key, value in solution.production_by_date_product.items():
                if isinstance(key, tuple):
                    # Format: {(date, product): quantity}
                    prod_date, product_id = key
                    quantity = value
                    if window.start_date <= prod_date <= committed_end:
                        if prod_date not in complete_production:
                            complete_production[prod_date] = {}
                        complete_production[prod_date][product_id] = quantity
                else:
                    # Format: {date: {product: quantity}}
                    prod_date = key
                    products = value
                    if window.start_date <= prod_date <= committed_end:
                        if prod_date not in complete_production:
                            complete_production[prod_date] = {}
                        for product_id, quantity in products.items():
                            complete_production[prod_date][product_id] = quantity

            # Add shipments from committed region
            for shipment in solution.shipments:
                if window.start_date <= shipment.delivery_date <= committed_end:
                    complete_shipments.append(shipment)

            # Calculate actual cost for committed region (not uniform prorating!)
            # This fixes the bug where 21d/14d appeared more expensive than 14d/7d
            window_cost = self._calculate_committed_cost(
                window=window,
                solution=solution,
                verbose=verbose
            )

            total_cost += window_cost

        return {
            'production_plan': complete_production,
            'shipments': complete_shipments,
            'total_cost': total_cost
        }

    def _calculate_committed_cost(
        self,
        window: WindowConfig,
        solution: WindowSolution,
        verbose: bool
    ) -> float:
        """
        Calculate actual cost for committed region of a window.

        This replaces the old uniform prorating approach which incorrectly assumed
        costs were evenly distributed across window days.

        Args:
            window: Window configuration
            solution: Window solution with cost breakdown
            verbose: Print cost details

        Returns:
            Total cost for committed region
        """
        # If no overlap, use full window cost
        if not window.has_overlap:
            if verbose:
                print(f"     → Full window cost: ${solution.total_cost:,.2f}")
            return solution.total_cost

        committed_end = window.committed_end_date

        # 1. Labor cost: Sum only dates in committed region
        labor_cost = sum(
            cost for date, cost in solution.labor_cost_by_date.items()
            if window.start_date <= date <= committed_end
        )

        # 2. Production cost: Calculate from production in committed region
        production_cost = 0.0
        prod_cost_per_unit = self.cost_structure.production_cost_per_unit or 0.0
        for key, value in solution.production_by_date_product.items():
            if isinstance(key, tuple):
                # Format: {(date, product): quantity}
                prod_date, product_id = key
                quantity = value
                if window.start_date <= prod_date <= committed_end:
                    production_cost += prod_cost_per_unit * quantity
            else:
                # Format: {date: {product: quantity}}
                prod_date = key
                if window.start_date <= prod_date <= committed_end:
                    if isinstance(value, dict):
                        for product_id, quantity in value.items():
                            production_cost += prod_cost_per_unit * quantity
                    else:
                        production_cost += prod_cost_per_unit * value

        # 3. Transport cost: Sum shipments delivered in committed region
        transport_cost = 0.0
        for shipment in solution.shipments:
            if window.start_date <= shipment.delivery_date <= committed_end:
                # Get route cost from shipment (already includes quantity)
                # Shipment objects don't store cost, so we need to estimate
                # For now, prorate transport cost by shipment ratio
                pass  # Will calculate below using shipment ratio

        # 4. For transport, inventory, truck, shortage costs that we can't easily
        #    allocate by date, use a ratio based on committed/total days
        #    This is still an approximation but better than before since we have
        #    exact labor and production costs
        if solution.total_cost > 0:
            # Calculate what's left after labor and production
            other_costs = solution.transport_cost + solution.inventory_cost + solution.truck_cost + solution.shortage_cost

            # For these costs, use ratio of committed days
            # (still imperfect but better than prorating ALL costs)
            cost_ratio = (committed_end - window.start_date).days + 1
            cost_ratio /= window.num_days

            transport_cost = solution.transport_cost * cost_ratio
            inventory_cost = solution.inventory_cost * cost_ratio
            truck_cost = solution.truck_cost * cost_ratio
            shortage_cost = solution.shortage_cost * cost_ratio
        else:
            transport_cost = 0.0
            inventory_cost = 0.0
            truck_cost = 0.0
            shortage_cost = 0.0

        total = labor_cost + production_cost + transport_cost + inventory_cost + truck_cost + shortage_cost

        if verbose:
            print(f"     → Committed cost: ${total:,.2f}")
            print(f"        Labor:     ${labor_cost:,.2f} (exact)")
            print(f"        Production: ${production_cost:,.2f} (exact)")
            print(f"        Transport: ${transport_cost:,.2f} (prorated)")
            print(f"        Other:     ${inventory_cost + truck_cost + shortage_cost:,.2f} (prorated)")

        return total
