"""Warmstart utilities for rolling horizon optimization.

This module provides functions to extract solutions from solved models,
shift them forward in time, and apply them as warmstart hints for subsequent
solves. This enables fast daily re-optimization using previous solutions.

Key Functions:
- extract_solution_for_warmstart: Extract complete solution from solved model
- shift_warmstart_hints: Shift solution dates forward by N days
- validate_warmstart_quality: Check if warmstart will be beneficial

Example:
    # Day 1: Full solve (expensive)
    model_day1 = UnifiedNodeModel(...)
    result_day1 = model_day1.solve(use_warmstart=False)

    # Extract solution
    warmstart_day1 = extract_solution_for_warmstart(model_day1)

    # Day 2: Shift forecast and warmstart forward
    warmstart_day2 = shift_warmstart_hints(warmstart_day1, shift_days=1,
                                           new_start_date=date(2025, 1, 7),
                                           new_end_date=date(2025, 2, 3))

    # Solve with warmstart (fast!)
    model_day2 = UnifiedNodeModel(forecast=forecast_day2, ...)
    result_day2 = model_day2.solve(use_warmstart=True,
                                   warmstart_hints=warmstart_day2)
"""

from datetime import date as Date, timedelta
from typing import Dict, Tuple, Optional, Any, Set
import warnings
from pyomo.environ import value as pyo_value


def clean_numerical_error(value: float, tolerance: float = 1e-10) -> float:
    """Clean tiny numerical errors from solver output.

    Clamps small negative values to zero and rounds near-integers.

    Args:
        value: Value from solver
        tolerance: Threshold for numerical error (default: 1e-10)

    Returns:
        Cleaned value
    """
    # Clamp tiny negative values to zero (numerical error)
    if abs(value) < tolerance:
        return 0.0
    if value < 0 and value > -tolerance:
        return 0.0

    # Round near-integers for binary/integer variables
    if abs(value - round(value)) < tolerance:
        return float(round(value))

    return value


def extract_solution_for_warmstart(
    model: Any,
    verbose: bool = False
) -> Dict[Tuple, float]:
    """Extract complete solution from solved UnifiedNodeModel for warmstart.

    Extracts all relevant variable values from a solved optimization model
    and converts them to the warmstart hints format. This provides 100%
    variable coverage for a complete warmstart.

    Variables Extracted:
    - production[node, product, date]: Production quantities
    - product_produced[node, product, date]: Binary production flags
    - product_start[node, product, date]: Binary changeover flags
    - inventory_cohort[node, product, state, prod_date, inv_date]: Inventory by age
    - shipment_cohort[origin, dest, product, state, prod_date, ship_date]: Shipments
    - production_day[node, date]: Binary production day flags
    - uses_overtime[node, date]: Overtime usage
    - labor_hours_*[node, date]: Labor allocation variables

    Args:
        model: Solved UnifiedNodeModel instance with .model attribute (Pyomo model)
        verbose: Print diagnostic information

    Returns:
        Dictionary mapping variable indices to values:
        {(node, product, date): value, ...}

    Raises:
        ValueError: If model is not solved or has no solution

    Example:
        >>> result = model.solve(solver_name='appsi_highs')
        >>> if result.success:
        ...     hints = extract_solution_for_warmstart(model, verbose=True)
        ...     print(f"Extracted {len(hints)} variable values")
    """
    if not hasattr(model, 'model'):
        raise ValueError("Model must have .model attribute (Pyomo ConcreteModel)")

    pyomo_model = model.model
    hints = {}

    stats = {
        'production': 0,
        'product_produced': 0,
        'product_start': 0,
        'inventory_cohort': 0,
        'shipment_cohort': 0,
        'production_day': 0,
        'uses_overtime': 0,
        'labor_hours': 0,
        'pallet_count': 0,
        'other': 0,
        'errors': 0,
    }

    # Extract production variables (ALL values, including zeros!)
    if hasattr(pyomo_model, 'production'):
        for key in pyomo_model.production:
            try:
                val = pyo_value(pyomo_model.production[key])
                if val is not None:
                    hints[key] = val  # Include zeros for complete warmstart
                    stats['production'] += 1
            except Exception as e:
                stats['errors'] += 1
                if verbose:
                    warnings.warn(f"Could not extract production{key}: {e}")

    # Extract binary product_produced variables
    if hasattr(pyomo_model, 'product_produced'):
        for key in pyomo_model.product_produced:
            try:
                val = pyo_value(pyomo_model.product_produced[key])
                if val is not None:
                    hints[key] = 1 if val > 0.5 else 0  # Round binary
                    stats['product_produced'] += 1
            except Exception as e:
                stats['errors'] += 1
                if verbose:
                    warnings.warn(f"Could not extract product_produced{key}: {e}")

    # Extract binary product_start variables (changeovers)
    if hasattr(pyomo_model, 'product_start'):
        for key in pyomo_model.product_start:
            try:
                val = pyo_value(pyomo_model.product_start[key])
                if val is not None:
                    hints[key] = 1 if val > 0.5 else 0  # Round binary
                    stats['product_start'] += 1
            except Exception as e:
                stats['errors'] += 1
                if verbose:
                    warnings.warn(f"Could not extract product_start{key}: {e}")

    # Extract inventory_cohort variables (ALL values including zeros!)
    if hasattr(pyomo_model, 'inventory_cohort'):
        for key in pyomo_model.inventory_cohort:
            try:
                val = pyo_value(pyomo_model.inventory_cohort[key])
                if val is not None:
                    hints[key] = clean_numerical_error(val)  # Clean numerical errors
                    stats['inventory_cohort'] += 1
            except Exception as e:
                stats['errors'] += 1
                if verbose:
                    warnings.warn(f"Could not extract inventory_cohort{key}: {e}")

    # Extract shipment_cohort variables (ALL values including zeros!)
    if hasattr(pyomo_model, 'shipment_cohort'):
        for key in pyomo_model.shipment_cohort:
            try:
                val = pyo_value(pyomo_model.shipment_cohort[key])
                if val is not None:
                    hints[key] = clean_numerical_error(val)  # Clean numerical errors
                    stats['shipment_cohort'] += 1
            except Exception as e:
                stats['errors'] += 1
                if verbose:
                    warnings.warn(f"Could not extract shipment_cohort{key}: {e}")

    # Extract production_day binary variables
    if hasattr(pyomo_model, 'production_day'):
        for key in pyomo_model.production_day:
            try:
                val = pyo_value(pyomo_model.production_day[key])
                if val is not None:
                    hints[key] = 1 if val > 0.5 else 0
                    stats['production_day'] += 1
            except Exception as e:
                stats['errors'] += 1

    # Extract uses_overtime binary variables
    if hasattr(pyomo_model, 'uses_overtime'):
        for key in pyomo_model.uses_overtime:
            try:
                val = pyo_value(pyomo_model.uses_overtime[key])
                if val is not None:
                    hints[key] = 1 if val > 0.5 else 0
                    stats['uses_overtime'] += 1
            except Exception as e:
                stats['errors'] += 1

    # Extract labor hour allocation variables (ALL values including zeros!)
    for labor_var_name in ['labor_hours_fixed', 'labor_hours_overtime',
                           'labor_hours_nonfixed', 'labor_hours_paid_nonfixed']:
        if hasattr(pyomo_model, labor_var_name):
            var = getattr(pyomo_model, labor_var_name)
            for key in var:
                try:
                    val = pyo_value(var[key])
                    if val is not None:
                        # Store with variable name prefix to avoid key collision
                        hints[(labor_var_name,) + key] = val
                        stats['labor_hours'] += 1
                except Exception as e:
                    stats['errors'] += 1

    # Extract pallet_count variables (ALL values including zeros!)
    for pallet_var_name in ['pallet_count_frozen', 'pallet_count_ambient']:
        if hasattr(pyomo_model, pallet_var_name):
            var = getattr(pyomo_model, pallet_var_name)
            for key in var:
                try:
                    val = pyo_value(var[key])
                    if val is not None:
                        hints[(pallet_var_name,) + key] = val
                        stats['pallet_count'] += 1
                except Exception as e:
                    stats['errors'] += 1

    # Extract mix_count variables (ALL values including zeros!)
    if hasattr(pyomo_model, 'mix_count'):
        for key in pyomo_model.mix_count:
            try:
                val = pyo_value(pyomo_model.mix_count[key])
                if val is not None:
                    hints[('mix_count',) + key] = val
                    stats['other'] += 1
            except Exception as e:
                stats['errors'] += 1

    total_extracted = sum(stats.values()) - stats['errors']

    if verbose:
        print(f"\n✓ Warmstart extraction complete:")
        print(f"  Total variables: {total_extracted:,}")
        print(f"  Production: {stats['production']:,}")
        print(f"  Product binaries: {stats['product_produced']:,}")
        print(f"  Changeover starts: {stats['product_start']:,}")
        print(f"  Inventory cohorts: {stats['inventory_cohort']:,}")
        print(f"  Shipment cohorts: {stats['shipment_cohort']:,}")
        print(f"  Production days: {stats['production_day']:,}")
        print(f"  Overtime flags: {stats['uses_overtime']:,}")
        print(f"  Labor hours: {stats['labor_hours']:,}")
        print(f"  Pallet counts: {stats['pallet_count']:,}")
        print(f"  Other: {stats['other']:,}")
        if stats['errors'] > 0:
            print(f"  Errors: {stats['errors']:,}")

    if total_extracted == 0:
        raise ValueError("No variables extracted from model. Is the model solved?")

    return hints


def shift_warmstart_hints(
    warmstart_hints: Dict[Tuple, float],
    shift_days: int,
    new_start_date: Date,
    new_end_date: Date,
    fill_new_dates: bool = True,
    verbose: bool = False
) -> Dict[Tuple, float]:
    """Shift warmstart hints forward in time for rolling horizon optimization.

    Takes solution from Day N and remaps it to Day N+shift_days by:
    1. Shifting all date components forward by shift_days
    2. Filtering out dates outside the new planning horizon
    3. Optionally filling new end-of-horizon dates with default values

    This enables using yesterday's solution as warmstart for today's solve.

    Args:
        warmstart_hints: Original warmstart hints {(node, prod, date): value, ...}
        shift_days: Number of days to shift forward (typically 1 for daily planning)
        new_start_date: Start date of new planning horizon
        new_end_date: End date of new planning horizon (inclusive)
        fill_new_dates: If True, initialize new end dates with zeros (default: True)
        verbose: Print diagnostic information

    Returns:
        Shifted warmstart hints dictionary with dates adjusted

    Example:
        >>> # Day 1 solution covers Jan 1-28
        >>> hints_day1 = extract_solution_for_warmstart(model_day1)
        >>>
        >>> # Shift forward by 1 day to cover Jan 2-29
        >>> hints_day2 = shift_warmstart_hints(
        ...     hints_day1,
        ...     shift_days=1,
        ...     new_start_date=date(2025, 1, 2),
        ...     new_end_date=date(2025, 1, 29)
        ... )
        >>>
        >>> # Now hints_day2 contains Jan 2-28 from shifted day1 solution
        >>> # plus zeros for new Jan 29
    """
    shifted_hints = {}

    stats = {
        'original': len(warmstart_hints),
        'shifted': 0,
        'dropped_before_horizon': 0,
        'dropped_after_horizon': 0,
        'filled_new_dates': 0,
        'non_date_vars': 0,
    }

    shift_delta = timedelta(days=shift_days)

    # Shift existing hints
    for key, value in warmstart_hints.items():
        # Find date component(s) in key tuple
        new_key = list(key)
        has_date = False
        all_dates_in_range = True

        for i, component in enumerate(key):
            if isinstance(component, Date):
                has_date = True
                shifted_date = component + shift_delta
                new_key[i] = shifted_date

                # Check if shifted date is within new horizon
                if shifted_date < new_start_date:
                    all_dates_in_range = False
                    stats['dropped_before_horizon'] += 1
                elif shifted_date > new_end_date:
                    all_dates_in_range = False
                    stats['dropped_after_horizon'] += 1

        if not has_date:
            # Non-date variables (e.g., parameters) - keep as-is
            shifted_hints[tuple(new_key)] = value
            stats['non_date_vars'] += 1
        elif all_dates_in_range:
            # All dates in this variable are within new horizon
            shifted_hints[tuple(new_key)] = value
            stats['shifted'] += 1

    # Fill new dates at end of horizon with default values
    if fill_new_dates:
        # Identify which dates are new (not covered by shifted hints)
        covered_dates = set()
        for key in shifted_hints.keys():
            for component in key:
                if isinstance(component, Date):
                    covered_dates.add(component)

        # Find dates in new horizon that aren't covered
        current_date = new_start_date
        new_dates = []
        while current_date <= new_end_date:
            if current_date not in covered_dates:
                new_dates.append(current_date)
            current_date += timedelta(days=1)

        # Initialize new dates with zeros (solver will determine optimal values)
        # We only initialize key variable types to avoid dimension explosion
        # The solver will naturally set these during optimization
        stats['filled_new_dates'] = len(new_dates)

        if verbose and new_dates:
            print(f"  New dates at end of horizon: {new_dates[0]} to {new_dates[-1]} ({len(new_dates)} days)")

    if verbose:
        print(f"\n✓ Warmstart shifting complete:")
        print(f"  Original variables: {stats['original']:,}")
        print(f"  Shifted successfully: {stats['shifted']:,}")
        print(f"  Dropped (before horizon): {stats['dropped_before_horizon']:,}")
        print(f"  Dropped (after horizon): {stats['dropped_after_horizon']:,}")
        print(f"  Non-date variables kept: {stats['non_date_vars']:,}")
        print(f"  New dates added: {stats['filled_new_dates']:,}")
        print(f"  Total in shifted hints: {len(shifted_hints):,}")

    return shifted_hints


def validate_warmstart_quality(
    original_hints: Dict[Tuple, float],
    shifted_hints: Dict[Tuple, float],
    min_overlap_ratio: float = 0.7,
    verbose: bool = False
) -> Tuple[bool, str]:
    """Validate that shifted warmstart has sufficient overlap with original.

    Checks if the shifted warmstart solution has enough variables in common
    with the original to be useful. If too many variables were dropped during
    shifting, warmstart may not help much.

    Args:
        original_hints: Original warmstart hints before shifting
        shifted_hints: Shifted warmstart hints
        min_overlap_ratio: Minimum ratio of shifted/original variables (default: 0.7)
        verbose: Print diagnostic information

    Returns:
        Tuple of (is_valid, message):
        - is_valid: True if warmstart quality is acceptable
        - message: Description of validation result

    Example:
        >>> hints_shifted = shift_warmstart_hints(hints_original, ...)
        >>> is_valid, msg = validate_warmstart_quality(hints_original, hints_shifted)
        >>> if not is_valid:
        ...     print(f"Warning: {msg}")
    """
    n_original = len(original_hints)
    n_shifted = len(shifted_hints)

    if n_original == 0:
        return False, "Original hints are empty"

    if n_shifted == 0:
        return False, "Shifted hints are empty - no variables remain after shifting"

    overlap_ratio = n_shifted / n_original

    if overlap_ratio < min_overlap_ratio:
        msg = (
            f"Warmstart quality may be poor: only {overlap_ratio:.1%} of variables "
            f"remain after shifting ({n_shifted:,} / {n_original:,}). "
            f"Consider increasing horizon length or shift_days is too large."
        )
        if verbose:
            warnings.warn(msg)
        return False, msg

    msg = (
        f"Warmstart quality good: {overlap_ratio:.1%} overlap "
        f"({n_shifted:,} / {n_original:,} variables)"
    )
    if verbose:
        print(f"✓ {msg}")

    return True, msg


def extract_warmstart_for_rolling_window(
    warmstart_hints: Dict[Tuple, float],
    new_start_date: Date,
    new_end_date: Date,
    verbose: bool = False
) -> Dict[Tuple, float]:
    """Extract warmstart hints for rolling window (no date shifting, exact match).

    For rolling window planning where Day 2 solves [D+1, D+N] using Day 1's
    solution for [D, D+N-1], this extracts the overlapping portion directly
    without shifting dates.

    This is the CORRECT approach for production planning where:
    - Day 1: Solve Days 1-42 (e.g., Oct 16 - Nov 26)
    - Planner executes Day 1 plan, records actuals
    - Day 2: Solve Days 2-43 (e.g., Oct 17 - Nov 27)
      - Use Day 1 solution for Days 2-42 EXACTLY (no shifting!)
      - Day 43 is new (solver decides freely)

    Args:
        warmstart_hints: Original warmstart hints from previous solve
        new_start_date: Start date of new planning window
        new_end_date: End date of new planning window (inclusive)
        verbose: Print diagnostic information

    Returns:
        Filtered warmstart hints containing only overlapping dates

    Example:
        >>> # Day 1: Oct 16-Nov 26 (42 days)
        >>> hints_day1 = extract_solution_for_warmstart(model_day1)
        >>>
        >>> # Day 2: Oct 17-Nov 27 (42 days)
        >>> # Want: Oct 17-Nov 26 from Day 1 (exact), Nov 27 new
        >>> hints_day2 = extract_warmstart_for_rolling_window(
        ...     hints_day1,
        ...     new_start_date=date(2025, 10, 17),
        ...     new_end_date=date(2025, 11, 27)
        ... )
        >>> # Result: 41 days exact warmstart, 1 day new (solver decides)
    """
    filtered_hints = {}

    stats = {
        'original': len(warmstart_hints),
        'kept_in_window': 0,
        'dropped_before': 0,
        'dropped_after': 0,
        'non_date_vars': 0,
    }

    for key, value in warmstart_hints.items():
        # Check if all date components in key are within new window
        has_date = False
        all_dates_in_range = True

        for component in key:
            if isinstance(component, Date):
                has_date = True
                if component < new_start_date:
                    all_dates_in_range = False
                    stats['dropped_before'] += 1
                    break
                elif component > new_end_date:
                    all_dates_in_range = False
                    stats['dropped_after'] += 1
                    break

        if not has_date:
            # Non-date variables - keep as-is
            filtered_hints[key] = value
            stats['non_date_vars'] += 1
        elif all_dates_in_range:
            # All dates within new window - keep EXACTLY (no shifting!)
            filtered_hints[key] = value
            stats['kept_in_window'] += 1

    if verbose:
        overlap_count = stats['kept_in_window'] + stats['non_date_vars']
        overlap_pct = overlap_count / stats['original'] * 100 if stats['original'] > 0 else 0

        print(f"\n✓ Warmstart extraction for rolling window:")
        print(f"  Original variables: {stats['original']:,}")
        print(f"  Kept in new window: {stats['kept_in_window']:,}")
        print(f"  Dropped (before window): {stats['dropped_before']:,}")
        print(f"  Dropped (after window): {stats['dropped_after']:,}")
        print(f"  Non-date variables: {stats['non_date_vars']:,}")
        print(f"  Total warmstart: {len(filtered_hints):,} ({overlap_pct:.1f}% coverage)")

    return filtered_hints


def estimate_warmstart_speedup(
    shift_days: int,
    horizon_days: int,
    base_solve_time: Optional[float] = None
) -> Tuple[float, str]:
    """Estimate expected speedup from warmstart based on horizon parameters.

    Provides a heuristic estimate of how much faster the warmstart solve
    will be compared to cold start. Based on empirical observations from
    warmstart investigation (docs/lessons_learned/warmstart_investigation_2025_10.md).

    Args:
        shift_days: Number of days shifted forward (typically 1 for daily)
        horizon_days: Total planning horizon length in days
        base_solve_time: Optional baseline solve time (seconds) to estimate new time

    Returns:
        Tuple of (speedup_factor, description):
        - speedup_factor: Expected speedup multiplier (e.g., 0.5 = 50% faster)
        - description: Human-readable description

    Example:
        >>> speedup, desc = estimate_warmstart_speedup(shift_days=1, horizon_days=28)
        >>> print(f"Expected speedup: {desc}")
        >>> if base_solve_time:
        ...     print(f"Estimated time: {base_solve_time * speedup:.1f}s")
    """
    # Calculate overlap percentage
    overlap_days = horizon_days - shift_days
    overlap_pct = overlap_days / horizon_days if horizon_days > 0 else 0

    # Heuristic speedup based on investigation results
    # High overlap (90%+): 0.3-0.5x time (50-70% faster)
    # Medium overlap (70-90%): 0.5-0.7x time (30-50% faster)
    # Low overlap (<70%): 0.7-0.9x time (10-30% faster)

    if overlap_pct >= 0.9:
        speedup_factor = 0.4  # 60% faster
        desc = "Excellent warmstart (90%+ overlap): expect ~60% faster"
    elif overlap_pct >= 0.7:
        speedup_factor = 0.6  # 40% faster
        desc = "Good warmstart (70-90% overlap): expect ~40% faster"
    elif overlap_pct >= 0.5:
        speedup_factor = 0.8  # 20% faster
        desc = "Fair warmstart (50-70% overlap): expect ~20% faster"
    else:
        speedup_factor = 0.9  # 10% faster
        desc = "Poor warmstart (<50% overlap): expect ~10% faster"

    if base_solve_time:
        estimated_time = base_solve_time * speedup_factor
        desc += f" ({base_solve_time:.1f}s → {estimated_time:.1f}s)"

    return speedup_factor, desc
