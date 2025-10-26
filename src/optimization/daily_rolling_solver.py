"""Daily rolling horizon solver with warmstart for production planning.

This module implements a daily rolling horizon approach where the production
planner solves once (expensive) and then each subsequent day shifts the
forecast forward and re-solves with warmstart (fast).

Key Class:
- DailyRollingSolver: Manages sequential daily solves with warmstart

Example Workflow:
    # Initialize solver with base configuration
    solver = DailyRollingSolver(
        nodes=nodes,
        routes=routes,
        base_forecast=forecast,
        horizon_days=28,  # 4-week planning horizon
        solver_name='appsi_highs'  # Required for warmstart
    )

    # Day 1: Full solve (expensive, ~30-96s)
    result_day1 = solver.solve_day_n(
        day_number=1,
        current_date=date(2025, 1, 6),
        use_warmstart=False  # Cold start
    )

    # Day 2: Re-solve with warmstart (fast, ~15-50s)
    result_day2 = solver.solve_day_n(
        day_number=2,
        current_date=date(2025, 1, 7),
        use_warmstart=True,  # Use Day 1 solution
        forecast_updates=small_demand_changes  # Optional
    )

    # Or solve entire week automatically
    results = solver.solve_sequence(
        start_date=date(2025, 1, 6),
        num_days=7,
        verbose=True
    )
"""

from datetime import date as Date, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import time
import warnings

from src.models.forecast import Forecast, ForecastEntry
from src.optimization.unified_node_model import UnifiedNodeModel, UnifiedNode, UnifiedRoute
from src.optimization.warmstart_utils import (
    extract_solution_for_warmstart,
    shift_warmstart_hints,
    validate_warmstart_quality,
    estimate_warmstart_speedup,
)


@dataclass
class DailyResult:
    """Result from solving a single day in rolling horizon.

    Attributes:
        day_number: Sequence number (1 = first day, 2 = second day, etc.)
        current_date: Calendar date for this solve
        start_date: Planning horizon start date
        end_date: Planning horizon end date
        solve_time: Solve time in seconds
        objective_value: Total cost for this horizon
        used_warmstart: Whether warmstart was used
        warmstart_speedup: Actual speedup factor vs baseline (if warmstart used)
        success: Whether solve succeeded
        termination_condition: Solver termination condition
        gap: MIP gap at termination
        num_variables: Number of decision variables
        num_constraints: Number of constraints
    """
    day_number: int
    current_date: Date
    start_date: Date
    end_date: Date
    solve_time: float
    objective_value: Optional[float]
    used_warmstart: bool
    warmstart_speedup: Optional[float] = None
    success: bool = False
    termination_condition: Optional[str] = None
    gap: Optional[float] = None
    num_variables: Optional[int] = None
    num_constraints: Optional[int] = None


@dataclass
class SequenceResult:
    """Result from solving a sequence of days.

    Attributes:
        daily_results: List of results for each day
        total_days: Number of days solved
        total_solve_time: Cumulative solve time (seconds)
        average_solve_time: Average solve time per day (seconds)
        average_speedup: Average warmstart speedup factor (days 2+)
        all_successful: Whether all solves succeeded
    """
    daily_results: List[DailyResult] = field(default_factory=list)
    total_days: int = 0
    total_solve_time: float = 0.0
    average_solve_time: float = 0.0
    average_speedup: Optional[float] = None
    all_successful: bool = True


class DailyRollingSolver:
    """Daily rolling horizon solver with warmstart capability.

    Manages sequential daily solves where each day:
    1. Shifts planning horizon forward by 1 day
    2. Updates forecast with latest data (small perturbations)
    3. Uses previous day's solution as warmstart
    4. Solves quickly (50-70% faster than cold start)

    The solver maintains state between days, tracking the previous solution
    and automatically shifting it forward for warmstart.

    Attributes:
        nodes: Network nodes (manufacturing, hubs, destinations)
        routes: Network routes between nodes
        base_forecast: Base forecast to shift each day
        horizon_days: Planning horizon length (default: 28 = 4 weeks)
        solver_name: Solver to use (default: 'appsi_highs')
        time_limit_seconds: Time limit per solve
        mip_gap: MIP gap tolerance
        use_batch_tracking: Enable age-cohort batch tracking
        allow_shortages: Allow demand shortages with penalty
        enforce_shelf_life: Enforce shelf life constraints

    Example:
        # Setup
        solver = DailyRollingSolver(
            nodes=nodes,
            routes=routes,
            base_forecast=forecast,
            horizon_days=28,
            solver_name='appsi_highs'
        )

        # Solve 7 days with warmstart
        results = solver.solve_sequence(
            start_date=date(2025, 1, 6),
            num_days=7,
            verbose=True
        )

        # Check performance
        print(f"Day 1: {results.daily_results[0].solve_time:.1f}s (cold start)")
        for i, res in enumerate(results.daily_results[1:], start=2):
            print(f"Day {i}: {res.solve_time:.1f}s "
                  f"({res.warmstart_speedup:.1%} speedup)")
    """

    def __init__(
        self,
        nodes: List[UnifiedNode],
        routes: List[UnifiedRoute],
        base_forecast: Forecast,
        labor_calendar: Any,  # LaborCalendar
        cost_structure: Any,  # CostStructure
        products: Dict[str, Any],  # Dict[str, Product]
        truck_schedules: Optional[List[Any]] = None,  # List[UnifiedTruckSchedule]
        horizon_days: int = 28,
        solver_name: str = 'appsi_highs',
        time_limit_seconds: Optional[float] = None,
        mip_gap: float = 0.01,
        use_batch_tracking: bool = True,
        allow_shortages: bool = False,
        enforce_shelf_life: bool = True,
    ):
        """Initialize daily rolling solver.

        Args:
            nodes: Network nodes
            routes: Network routes
            base_forecast: Base forecast to shift daily
            labor_calendar: Labor calendar with daily availability
            cost_structure: Cost parameters (production, storage, transport)
            products: Dictionary mapping product_id to Product objects
            truck_schedules: Optional list of truck schedules
            horizon_days: Planning horizon length in days (default: 28 = 4 weeks)
            solver_name: Solver to use (default: 'appsi_highs' for warmstart support)
            time_limit_seconds: Time limit per solve (None = no limit)
            mip_gap: MIP gap tolerance (default: 0.01 = 1%)
            use_batch_tracking: Enable batch tracking (default: True)
            allow_shortages: Allow demand shortages (default: False)
            enforce_shelf_life: Enforce shelf life (default: True)
        """
        self.nodes = nodes
        self.routes = routes
        self.base_forecast = base_forecast
        self.labor_calendar = labor_calendar
        self.cost_structure = cost_structure
        self.products = products
        self.truck_schedules = truck_schedules
        self.horizon_days = horizon_days
        self.solver_name = solver_name
        self.time_limit_seconds = time_limit_seconds
        self.mip_gap = mip_gap
        self.use_batch_tracking = use_batch_tracking
        self.allow_shortages = allow_shortages
        self.enforce_shelf_life = enforce_shelf_life

        # State tracking
        self._previous_warmstart: Optional[Dict] = None
        self._previous_solve_time: Optional[float] = None
        self._baseline_solve_time: Optional[float] = None

        # Validate solver supports warmstart
        if solver_name != 'appsi_highs':
            warnings.warn(
                f"Solver '{solver_name}' may not fully support warmstart. "
                f"Recommend using 'appsi_highs' for best performance."
            )

    def _create_forecast_for_window(
        self,
        start_date: Date,
        end_date: Date,
        forecast_updates: Optional[Dict[Tuple[str, str, Date], float]] = None
    ) -> Forecast:
        """Create forecast for specific planning window.

        Args:
            start_date: Window start date
            end_date: Window end date (inclusive)
            forecast_updates: Optional demand updates {(loc, prod, date): qty}

        Returns:
            Forecast covering the window
        """
        # Filter base forecast to window
        window_entries = [
            entry for entry in self.base_forecast.entries
            if start_date <= entry.forecast_date <= end_date
        ]

        # Apply updates if provided
        if forecast_updates:
            # Create lookup for existing entries
            entry_lookup = {
                (e.location_id, e.product_id, e.forecast_date): e
                for e in window_entries
            }

            # Apply updates
            for (loc, prod, date_val), new_qty in forecast_updates.items():
                if start_date <= date_val <= end_date:
                    if (loc, prod, date_val) in entry_lookup:
                        # Update existing entry
                        entry_lookup[(loc, prod, date_val)].quantity = new_qty
                    else:
                        # Add new entry
                        window_entries.append(
                            ForecastEntry(
                                location_id=loc,
                                product_id=prod,
                                forecast_date=date_val,
                                quantity=new_qty
                            )
                        )

        return Forecast(name=f"window_{start_date}_to_{end_date}", entries=window_entries)

    def solve_day_n(
        self,
        day_number: int,
        current_date: Date,
        use_warmstart: bool = True,
        forecast_updates: Optional[Dict[Tuple[str, str, Date], float]] = None,
        verbose: bool = True,
    ) -> DailyResult:
        """Solve for a specific day in the sequence.

        Args:
            day_number: Sequence number (1 = first day, 2 = second day, etc.)
            current_date: Calendar date for this solve (planning starts here)
            use_warmstart: Use previous day's solution as warmstart (if available)
            forecast_updates: Optional demand updates {(location, product, date): qty}
            verbose: Print progress messages

        Returns:
            DailyResult with solve metrics

        Example:
            # Day 1 (cold start)
            result1 = solver.solve_day_n(1, date(2025, 1, 6), use_warmstart=False)

            # Day 2 (with warmstart)
            result2 = solver.solve_day_n(2, date(2025, 1, 7), use_warmstart=True)
        """
        # Calculate planning window
        start_date = current_date
        end_date = current_date + timedelta(days=self.horizon_days - 1)

        if verbose:
            print(f"\n{'='*70}")
            print(f"DAY {day_number}: {current_date.strftime('%Y-%m-%d')}")
            print(f"Planning horizon: {start_date} to {end_date} ({self.horizon_days} days)")
            print(f"{'='*70}")

        # Create forecast for this window
        forecast = self._create_forecast_for_window(
            start_date=start_date,
            end_date=end_date,
            forecast_updates=forecast_updates
        )

        # Prepare warmstart hints
        warmstart_hints = None
        if use_warmstart and self._previous_warmstart is not None:
            if verbose:
                print(f"\n🔄 Shifting previous solution for warmstart...")

            # Shift previous solution forward by 1 day
            warmstart_hints = shift_warmstart_hints(
                warmstart_hints=self._previous_warmstart,
                shift_days=1,
                new_start_date=start_date,
                new_end_date=end_date,
                fill_new_dates=True,
                verbose=verbose
            )

            # Validate warmstart quality
            is_valid, msg = validate_warmstart_quality(
                original_hints=self._previous_warmstart,
                shifted_hints=warmstart_hints,
                min_overlap_ratio=0.7,
                verbose=verbose
            )

            if not is_valid:
                warnings.warn(f"Warmstart quality check failed: {msg}")
                if verbose:
                    print(f"  ⚠️  Proceeding anyway, but speedup may be limited")

            # Estimate expected speedup
            if self._baseline_solve_time:
                speedup_factor, desc = estimate_warmstart_speedup(
                    shift_days=1,
                    horizon_days=self.horizon_days,
                    base_solve_time=self._baseline_solve_time
                )
                if verbose:
                    print(f"  {desc}")

        elif use_warmstart and self._previous_warmstart is None:
            if verbose:
                print(f"\n⚠️  Warmstart requested but no previous solution available")
                print(f"    This is Day {day_number}, performing cold start")

        # Build and solve model
        if verbose:
            print(f"\n🔨 Building optimization model...")

        model = UnifiedNodeModel(
            nodes=self.nodes,
            routes=self.routes,
            forecast=forecast,
            labor_calendar=self.labor_calendar,
            cost_structure=self.cost_structure,
            products=self.products,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=self.truck_schedules,
            use_batch_tracking=self.use_batch_tracking,
            allow_shortages=self.allow_shortages,
            enforce_shelf_life=self.enforce_shelf_life,
        )

        if verbose:
            print(f"🚀 Solving with {self.solver_name}...")
            print(f"   Warmstart: {'Yes' if warmstart_hints else 'No (cold start)'}")

        solve_start = time.time()

        result = model.solve(
            solver_name=self.solver_name,
            time_limit_seconds=self.time_limit_seconds,
            mip_gap=self.mip_gap,
            tee=False,  # Don't show solver output (keep logs clean)
            use_warmstart=bool(warmstart_hints),
            warmstart_hints=warmstart_hints,
        )

        solve_time = time.time() - solve_start

        # Extract solution for next day's warmstart
        if result.success:
            if verbose:
                print(f"\n✅ Solve successful in {solve_time:.1f}s")
                print(f"   Objective: ${result.objective_value:,.2f}")
                print(f"   Gap: {result.gap:.2%}" if result.gap else "")

            # Extract warmstart for next day
            try:
                self._previous_warmstart = extract_solution_for_warmstart(
                    model=model,
                    verbose=verbose
                )
            except Exception as e:
                warnings.warn(f"Failed to extract warmstart: {e}")
                self._previous_warmstart = None

        else:
            if verbose:
                print(f"\n❌ Solve failed: {result.termination_condition}")
            self._previous_warmstart = None

        # Track baseline solve time (Day 1 cold start)
        if day_number == 1 or self._baseline_solve_time is None:
            self._baseline_solve_time = solve_time

        # Calculate actual speedup
        warmstart_speedup = None
        if warmstart_hints and self._previous_solve_time:
            warmstart_speedup = solve_time / self._previous_solve_time
            if verbose:
                speedup_pct = (1 - warmstart_speedup) * 100
                print(f"   Speedup: {speedup_pct:.1f}% faster than Day {day_number-1}")

        self._previous_solve_time = solve_time

        # Create result
        return DailyResult(
            day_number=day_number,
            current_date=current_date,
            start_date=start_date,
            end_date=end_date,
            solve_time=solve_time,
            objective_value=result.objective_value,
            used_warmstart=bool(warmstart_hints),
            warmstart_speedup=warmstart_speedup,
            success=result.success,
            termination_condition=str(result.termination_condition),
            gap=result.gap,
            num_variables=result.num_variables,
            num_constraints=result.num_constraints,
        )

    def solve_sequence(
        self,
        start_date: Date,
        num_days: int,
        forecast_updates_by_day: Optional[Dict[int, Dict[Tuple[str, str, Date], float]]] = None,
        verbose: bool = True,
    ) -> SequenceResult:
        """Solve a sequence of days with warmstart.

        Automatically chains daily solves:
        - Day 1: Cold start (expensive)
        - Days 2-N: Warmstart from previous day (fast)

        Args:
            start_date: Start date for Day 1
            num_days: Number of days to solve
            forecast_updates_by_day: Optional updates per day
                {day_number: {(location, product, date): quantity}}
            verbose: Print progress messages

        Returns:
            SequenceResult with all daily results and aggregate metrics

        Example:
            # Solve 7 days (1 week)
            results = solver.solve_sequence(
                start_date=date(2025, 1, 6),
                num_days=7,
                verbose=True
            )

            # Check cumulative performance
            print(f"Total time: {results.total_solve_time:.1f}s")
            print(f"Average time: {results.average_solve_time:.1f}s/day")
            print(f"Average speedup (Days 2+): {results.average_speedup:.1%}")
        """
        if verbose:
            print(f"\n{'#'*70}")
            print(f"DAILY ROLLING HORIZON SEQUENCE")
            print(f"{'#'*70}")
            print(f"Start date: {start_date}")
            print(f"Days to solve: {num_days}")
            print(f"Horizon length: {self.horizon_days} days")
            print(f"Solver: {self.solver_name}")

        # Reset state
        self._previous_warmstart = None
        self._previous_solve_time = None
        self._baseline_solve_time = None

        daily_results = []
        total_solve_time = 0.0

        for day_num in range(1, num_days + 1):
            current_date = start_date + timedelta(days=day_num - 1)

            # Get forecast updates for this day
            forecast_updates = None
            if forecast_updates_by_day and day_num in forecast_updates_by_day:
                forecast_updates = forecast_updates_by_day[day_num]

            # Solve this day (Day 1 = cold start, Days 2+ = warmstart)
            result = self.solve_day_n(
                day_number=day_num,
                current_date=current_date,
                use_warmstart=(day_num > 1),  # Only warmstart after Day 1
                forecast_updates=forecast_updates,
                verbose=verbose,
            )

            daily_results.append(result)
            total_solve_time += result.solve_time

        # Calculate aggregate metrics
        average_solve_time = total_solve_time / num_days if num_days > 0 else 0.0

        # Calculate average speedup (Days 2+)
        warmstart_results = [r for r in daily_results if r.used_warmstart and r.warmstart_speedup]
        if warmstart_results:
            average_speedup = sum(r.warmstart_speedup for r in warmstart_results) / len(warmstart_results)
        else:
            average_speedup = None

        all_successful = all(r.success for r in daily_results)

        # Print summary
        if verbose:
            print(f"\n{'='*70}")
            print(f"SEQUENCE SUMMARY")
            print(f"{'='*70}")
            print(f"Total days solved: {num_days}")
            print(f"Successful solves: {sum(1 for r in daily_results if r.success)}/{num_days}")
            print(f"Total solve time: {total_solve_time:.1f}s")
            print(f"Average solve time: {average_solve_time:.1f}s/day")

            if average_speedup:
                speedup_pct = (1 - average_speedup) * 100
                print(f"Average warmstart speedup: {speedup_pct:.1f}% faster (Days 2+)")

            if daily_results:
                day1_time = daily_results[0].solve_time
                if len(daily_results) > 1:
                    avg_days_2plus = sum(r.solve_time for r in daily_results[1:]) / (len(daily_results) - 1)
                    improvement = (1 - avg_days_2plus / day1_time) * 100 if day1_time > 0 else 0
                    print(f"\nPerformance comparison:")
                    print(f"  Day 1 (cold start): {day1_time:.1f}s")
                    print(f"  Days 2+ (warmstart): {avg_days_2plus:.1f}s average ({improvement:.1f}% faster)")

        return SequenceResult(
            daily_results=daily_results,
            total_days=num_days,
            total_solve_time=total_solve_time,
            average_solve_time=average_solve_time,
            average_speedup=average_speedup,
            all_successful=all_successful,
        )

    def reset(self):
        """Reset solver state (clears previous warmstart)."""
        self._previous_warmstart = None
        self._previous_solve_time = None
        self._baseline_solve_time = None
