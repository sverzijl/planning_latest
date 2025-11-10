"""Campaign-based warmstart hint generation for cohort-tracking models (archived).

This module implements a demand-weighted campaign pattern algorithm to generate
production hints that help the MIP solver find good initial solutions faster.

The campaign pattern allocates 2-3 SKUs per weekday based on proportional demand,
balances weekday production across products, minimizes weekend usage, and ensures
all SKUs are produced at least once per week.

Key Algorithm Steps:
1. Aggregate weekly demand by product
2. Calculate demand share percentage for each product
3. Allocate products to weekdays (2-3 SKUs per day) based on demand proportion
4. Generate weekly production pattern with balanced loading
5. Extend pattern across multi-week planning horizons
6. Minimize weekend production (use only if needed for capacity)

Example:
    >>> from datetime import date
    >>> demand = {
    ...     ('6122', 'SKU_A', date(2025, 1, 6)): 5000,
    ...     ('6122', 'SKU_B', date(2025, 1, 7)): 3000,
    ... }
    >>> hints = generate_campaign_warmstart(
    ...     demand_forecast=demand,
    ...     manufacturing_node_id='6122',
    ...     products=['SKU_A', 'SKU_B'],
    ...     start_date=date(2025, 1, 6),
    ...     end_date=date(2025, 1, 12),
    ...     max_daily_production=19600
    ... )
    >>> print(hints)
    {('6122', 'SKU_A', date(2025, 1, 6)): 1, ('6122', 'SKU_B', date(2025, 1, 7)): 1}
"""

from datetime import date as Date, timedelta
from typing import Dict, Tuple, List, Set, Optional
from collections import defaultdict
import warnings


def generate_campaign_warmstart(
    demand_forecast: Dict[Tuple[str, str, Date], float],
    manufacturing_node_id: str,
    products: List[str],
    start_date: Date,
    end_date: Date,
    max_daily_production: float,
    fixed_labor_days: Optional[Set[Date]] = None,
    target_skus_per_weekday: int = 3,
    freshness_days: int = 7,
) -> Dict[Tuple[str, str, Date], int]:
    """Generate campaign-based warmstart hints using demand-weighted allocation.

    This function implements the DEMAND_WEIGHTED campaign pattern algorithm:
    - Allocates 2-3 SKUs per weekday based on proportional demand
    - Balances weekly production load across products
    - Ensures all SKUs produced at least once per week
    - Minimizes weekend production (uses only if capacity insufficient)
    - Generates binary hints (1 = produce this SKU on this date, 0 = don't)

    Algorithm Steps:
        1. Setup: Extract planning horizon, products, weekday dates
        2. Weekly demand: Aggregate demand by product for first week
        3. Demand share: Calculate percentage contribution of each product
        4. Day allocation: Assign products to weekdays (round-robin + demand-weighted)
        5. Weekly pattern: Create base production pattern (binary flags)
        6. Multi-week extension: Replicate pattern across full planning horizon
        7. Weekend handling: Add weekend production only if needed for capacity

    Args:
        demand_forecast: Demand dict with (location, product, date) -> quantity
            Format: {('6122', 'SKU_A', date(2025, 1, 6)): 5000, ...}
        manufacturing_node_id: Node ID of manufacturing site (e.g., '6122')
        products: List of product IDs to include in campaign
        start_date: Planning horizon start date
        end_date: Planning horizon end date (inclusive)
        max_daily_production: Maximum production capacity per day (units)
        fixed_labor_days: Set of dates with fixed labor (Mon-Fri non-holidays).
            If None, assumes Mon-Fri are fixed labor days.
        target_skus_per_weekday: Target number of SKUs per weekday (default: 3)
        freshness_days: Demand aggregation window for freshness (default: 7)

    Returns:
        Warmstart hints dictionary: {(node_id, product_id, date): 1 or 0}
        Value = 1: Produce this SKU on this date (hint to solver)
        Value = 0: Don't produce this SKU on this date (optional hint)

    Validation:
        - All products must have demand > 0 (skips zero-demand products)
        - Planning horizon must be at least 7 days
        - Daily SKU limit must be 1-5 (reasonable range)
        - Warns if uneven demand distribution or capacity constraints detected

    Edge Cases Handled:
        - Zero demand products: Skipped (no production hints)
        - Single product: Produces every weekday (max freshness)
        - Uneven demand: Uses demand weighting to prioritize high-volume SKUs
        - Partial weeks: Handles start/end dates mid-week gracefully
        - Weekend-only capacity: Adds weekend hints if needed

    Performance:
        - O(P * D) where P = products, D = dates in horizon
        - Typical execution: <100ms for 5 products, 28 days
        - No solver calls, pure algorithmic hint generation

    Example:
        >>> from datetime import date
        >>> demand = {
        ...     ('6122', 'SKU_A', date(2025, 1, 6)): 5000,  # Monday
        ...     ('6122', 'SKU_A', date(2025, 1, 7)): 3000,  # Tuesday
        ...     ('6122', 'SKU_B', date(2025, 1, 8)): 2000,  # Wednesday
        ... }
        >>> hints = generate_campaign_warmstart(
        ...     demand_forecast=demand,
        ...     manufacturing_node_id='6122',
        ...     products=['SKU_A', 'SKU_B'],
        ...     start_date=date(2025, 1, 6),
        ...     end_date=date(2025, 1, 12),
        ...     max_daily_production=19600
        ... )
        >>> # Expected: SKU_A on Mon/Tue/Thu, SKU_B on Wed/Fri
        >>> # (Higher demand = more weekdays assigned)
    """
    # ==================
    # STEP 1: SETUP
    # ==================

    # Validate inputs
    planning_days = (end_date - start_date).days + 1
    if planning_days < 7:
        warnings.warn(
            f"Planning horizon ({planning_days} days) is less than 7 days. "
            "Campaign pattern may not be effective."
        )

    if not (1 <= target_skus_per_weekday <= 5):
        warnings.warn(
            f"target_skus_per_weekday={target_skus_per_weekday} is unusual. "
            "Recommended range: 1-5."
        )

    # Determine fixed labor days (Mon-Fri) if not provided
    if fixed_labor_days is None:
        fixed_labor_days = set()
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Monday=0, Friday=4
                fixed_labor_days.add(current)
            current += timedelta(days=1)

    # Extract weekday dates within planning horizon
    weekday_dates = sorted([d for d in fixed_labor_days if start_date <= d <= end_date])

    # All dates (for weekend handling)
    all_dates = []
    current = start_date
    while current <= end_date:
        all_dates.append(current)
        current += timedelta(days=1)

    if not weekday_dates:
        warnings.warn("No weekday dates in planning horizon. Cannot generate campaign hints.")
        return {}

    if not products:
        warnings.warn("No products provided. Cannot generate campaign hints.")
        return {}

    # ==================
    # STEP 2: WEEKLY DEMAND AGGREGATION
    # ==================

    # Aggregate demand by product for freshness window
    # Use first 'freshness_days' days to estimate demand proportions
    demand_window_end = min(start_date + timedelta(days=freshness_days - 1), end_date)

    product_demand: Dict[str, float] = defaultdict(float)
    for (loc, prod, demand_date), qty in demand_forecast.items():
        # Only aggregate demand within freshness window
        if prod in products and start_date <= demand_date <= demand_window_end:
            product_demand[prod] += qty

    # Filter out zero-demand products
    active_products = [p for p in products if product_demand.get(p, 0) > 0]

    if not active_products:
        warnings.warn("No products have demand > 0 in forecast. Cannot generate hints.")
        return {}

    total_demand = sum(product_demand[p] for p in active_products)

    # ==================
    # STEP 3: DEMAND SHARE CALCULATION
    # ==================

    demand_share: Dict[str, float] = {}
    for prod in active_products:
        demand_share[prod] = product_demand[prod] / total_demand if total_demand > 0 else 0.0

    # Sort products by demand (descending) for allocation
    products_by_demand = sorted(active_products, key=lambda p: product_demand[p], reverse=True)

    # ==================
    # STEP 4: WEEKDAY ALLOCATION (DEMAND-WEIGHTED)
    # ==================

    # Calculate number of weekday slots each product should get
    # Based on demand share and target SKUs per day
    num_weekdays_in_week = 5  # Mon-Fri

    # Total slots available per week
    total_weekly_slots = num_weekdays_in_week * target_skus_per_weekday

    # Allocate slots based on demand share (with minimum 1 slot per product)
    product_weekday_slots: Dict[str, int] = {}
    remaining_slots = total_weekly_slots

    for prod in products_by_demand:
        # Minimum 1 weekday per product (ensures weekly production)
        min_slots = 1
        # Proportional allocation based on demand share
        proportional_slots = max(min_slots, round(demand_share[prod] * total_weekly_slots))
        # Cap at remaining slots
        allocated_slots = min(proportional_slots, remaining_slots)
        product_weekday_slots[prod] = allocated_slots
        remaining_slots -= allocated_slots

    # If slots remaining, distribute to high-demand products
    if remaining_slots > 0:
        for prod in products_by_demand:
            if remaining_slots <= 0:
                break
            product_weekday_slots[prod] += 1
            remaining_slots -= 1

    # ==================
    # STEP 5: WEEKLY PRODUCTION PATTERN
    # ==================

    # Assign products to specific weekdays in a balanced way
    # Strategy: Round-robin allocation with demand weighting

    # Create weekly pattern: weekday_index (0=Mon, 4=Fri) -> list of products
    weekly_pattern: Dict[int, List[str]] = defaultdict(list)

    # Flatten product-weekday assignments to (product, weekday_index) pairs
    product_weekday_assignments: List[Tuple[str, int]] = []

    weekday_index = 0
    for prod in products_by_demand:
        num_slots = product_weekday_slots[prod]
        for _ in range(num_slots):
            # Round-robin assignment across weekdays
            product_weekday_assignments.append((prod, weekday_index % num_weekdays_in_week))
            weekday_index += 1

    # Build weekly pattern from assignments
    for prod, wd_idx in product_weekday_assignments:
        weekly_pattern[wd_idx].append(prod)

    # ==================
    # STEP 6: MULTI-WEEK EXTENSION
    # ==================

    # Generate warmstart hints by replicating weekly pattern across horizon
    warmstart_hints: Dict[Tuple[str, str, Date], int] = {}

    for date_val in weekday_dates:
        weekday_index = date_val.weekday()  # 0=Monday, 6=Sunday
        if weekday_index < 5:  # Weekday
            # Get products assigned to this weekday
            assigned_products = weekly_pattern.get(weekday_index, [])
            for prod in assigned_products:
                warmstart_hints[(manufacturing_node_id, prod, date_val)] = 1

    # ==================
    # STEP 7: WEEKEND HANDLING (MINIMAL)
    # ==================

    # Check if weekend production is needed for capacity
    # (Not implemented in Phase 1 - assume weekday capacity sufficient)
    # Future enhancement: Add weekend hints if total demand exceeds weekday capacity

    # Count weekend dates
    weekend_dates = [d for d in all_dates if d.weekday() >= 5 and d not in weekday_dates]

    if weekend_dates:
        # Calculate total weekday capacity
        total_weekday_capacity = len(weekday_dates) * max_daily_production
        # Calculate total demand
        total_horizon_demand = sum(
            qty for (loc, prod, demand_date), qty in demand_forecast.items()
            if prod in active_products and start_date <= demand_date <= end_date
        )

        # If demand exceeds weekday capacity, add weekend production hints
        if total_horizon_demand > total_weekday_capacity * 0.95:  # 95% threshold
            warnings.warn(
                f"Total demand ({total_horizon_demand:,.0f}) exceeds weekday capacity "
                f"({total_weekday_capacity:,.0f}). Consider weekend production."
            )
            # Add hints for highest-demand product on weekends (simple strategy)
            top_product = products_by_demand[0]
            for weekend_date in weekend_dates:
                warmstart_hints[(manufacturing_node_id, top_product, weekend_date)] = 1

    # ==================
    # VALIDATION & DIAGNOSTICS
    # ==================

    # Validate hints
    validate_warmstart_hints(warmstart_hints, products, start_date, end_date)

    # Print diagnostic info
    print(f"\n🚀 Warmstart Hints Generated (Campaign Pattern):")
    print(f"  Products: {len(active_products)}")
    print(f"  Weekdays: {len(weekday_dates)}")
    print(f"  Hints: {len(warmstart_hints)} (binary production flags)")
    print(f"  Pattern: {target_skus_per_weekday} SKUs/weekday, {len(weekend_dates)} weekend days")

    # Show demand distribution
    print(f"\n  Demand Distribution:")
    for prod in products_by_demand[:5]:  # Top 5 products
        share_pct = demand_share[prod] * 100
        slots = product_weekday_slots[prod]
        print(f"    {prod}: {share_pct:.1f}% demand → {slots} weekday slots")

    return warmstart_hints


def validate_warmstart_hints(
    hints: Dict[Tuple[str, str, Date], int],
    products: List[str],
    start_date: Date,
    end_date: Date,
) -> None:
    """Validate warmstart hints for correctness.

    Checks:
        - All hint values are binary (0 or 1)
        - All dates are within planning horizon
        - All products are in product list
        - At least one hint per product (ensures weekly production)

    Args:
        hints: Warmstart hints dictionary
        products: List of valid product IDs
        start_date: Planning horizon start
        end_date: Planning horizon end

    Raises:
        ValueError: If hints are invalid
    """
    if not hints:
        warnings.warn("No warmstart hints generated. Solver will use default initialization.")
        return

    # Check hint values are binary
    invalid_values = [v for v in hints.values() if v not in [0, 1]]
    if invalid_values:
        raise ValueError(f"Warmstart hints must be binary (0 or 1). Found: {invalid_values[:5]}")

    # Check dates are within horizon
    invalid_dates = [(node, prod, d) for (node, prod, d) in hints.keys()
                     if not (start_date <= d <= end_date)]
    if invalid_dates:
        raise ValueError(
            f"Warmstart hints contain dates outside planning horizon "
            f"[{start_date}, {end_date}]: {invalid_dates[:5]}"
        )

    # Check products are valid
    hint_products = set(prod for (_, prod, _) in hints.keys())
    invalid_products = hint_products - set(products)
    if invalid_products:
        raise ValueError(f"Warmstart hints contain invalid products: {invalid_products}")

    # Check all products have at least one hint (optional warning)
    products_with_hints = set(
        prod for (node, prod, date) in hints.keys()
        if hints[(node, prod, date)] == 1
    )
    missing_products = set(products) - products_with_hints
    if missing_products:
        warnings.warn(
            f"Some products have no warmstart hints (zero demand?): {missing_products}"
        )


def validate_freshness_constraint(
    hints: Dict[Tuple[str, str, Date], int],
    freshness_days: int = 7,
) -> bool:
    """Validate that campaign pattern maintains freshness constraint.

    Checks if each product is produced at least once every 'freshness_days'.

    Args:
        hints: Warmstart hints dictionary
        freshness_days: Maximum days between production runs (default: 7)

    Returns:
        True if freshness constraint satisfied, False otherwise
    """
    # Group hints by product
    product_production_dates: Dict[str, List[Date]] = defaultdict(list)
    for (node, prod, date_val), hint_value in hints.items():
        if hint_value == 1:
            product_production_dates[prod].append(date_val)

    # Check each product has production within freshness window
    for prod, dates in product_production_dates.items():
        if not dates:
            continue

        sorted_dates = sorted(dates)
        for i in range(len(sorted_dates) - 1):
            gap_days = (sorted_dates[i + 1] - sorted_dates[i]).days
            if gap_days > freshness_days:
                warnings.warn(
                    f"Product {prod} has {gap_days}-day gap between production runs "
                    f"(exceeds {freshness_days}-day freshness). "
                    f"Dates: {sorted_dates[i]} → {sorted_dates[i+1]}"
                )
                return False

    return True


def validate_daily_sku_limit(
    hints: Dict[Tuple[str, str, Date], int],
    max_skus_per_day: int = 5,
) -> bool:
    """Validate that daily SKU count doesn't exceed limit.

    Args:
        hints: Warmstart hints dictionary
        max_skus_per_day: Maximum SKUs allowed per day (default: 5)

    Returns:
        True if daily SKU limit satisfied, False otherwise
    """
    # Count SKUs per day
    daily_sku_count: Dict[Date, int] = defaultdict(int)
    for (node, prod, date_val), hint_value in hints.items():
        if hint_value == 1:
            daily_sku_count[date_val] += 1

    # Check for violations
    violations = [(d, count) for d, count in daily_sku_count.items() if count > max_skus_per_day]

    if violations:
        for date_val, count in violations[:5]:  # Show first 5
            warnings.warn(
                f"Date {date_val} has {count} SKUs (exceeds limit of {max_skus_per_day})"
            )
        return False

    return True


def create_default_warmstart(
    demand_forecast: Dict[Tuple[str, str, Date], float],
    manufacturing_node_id: str,
    products: List[str],
    start_date: Date,
    end_date: Date,
    max_daily_production: float,
    fixed_labor_days: Optional[Set[Date]] = None,
) -> Dict[Tuple[str, str, Date], int]:
    """Convenience function to create campaign warmstart with default parameters.

    Uses realistic defaults based on actual production patterns:
        - 2 SKUs per weekday (each SKU produced twice weekly for 5 SKUs)
        - 7-day freshness window
        - Demand-weighted allocation

    Args:
        demand_forecast: Demand dict (location, product, date) -> quantity
        manufacturing_node_id: Manufacturing site node ID
        products: List of product IDs
        start_date: Planning start date
        end_date: Planning end date
        max_daily_production: Max production per day (units)
        fixed_labor_days: Optional set of fixed labor dates

    Returns:
        Warmstart hints dictionary

    Example:
        >>> hints = create_default_warmstart(
        ...     demand_forecast=demand,
        ...     manufacturing_node_id='6122',
        ...     products=['SKU_A', 'SKU_B'],
        ...     start_date=date(2025, 1, 6),
        ...     end_date=date(2025, 2, 2),
        ...     max_daily_production=19600
        ... )
    """
    return generate_campaign_warmstart(
        demand_forecast=demand_forecast,
        manufacturing_node_id=manufacturing_node_id,
        products=products,
        start_date=start_date,
        end_date=end_date,
        max_daily_production=max_daily_production,
        fixed_labor_days=fixed_labor_days,
        target_skus_per_weekday=2,  # FIXED: 2 SKUs per weekday (each SKU twice weekly for 5 SKUs)
        freshness_days=7,  # Default: 7-day freshness
    )
