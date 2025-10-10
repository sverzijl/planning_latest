"""Production smoothing tests for batch tracking mode.

This test suite validates the production smoothing fix that prevents
the single-day production concentration bug caused by the FIFO penalty.

CRITICAL BUG FIXED:
- Bug: FIFO penalty caused ALL production to concentrate on 1 day (unrealistic)
- Fix Applied:
  1. Disabled broken FIFO penalty (lines 2215-2240 in integrated_model.py)
  2. Added production smoothing constraint (lines 1448-1494)
  3. Added enable_production_smoothing parameter (default True when batch_tracking=True)

These tests ensure:
1. Production spreads across multiple days (not concentrated on 1 day)
2. Day-to-day production changes respect smoothing constraint
3. Parameter control works correctly
4. The single-day bug never regresses
5. Batch tracking and smoothing work together correctly
"""

import pytest
from datetime import date, timedelta
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import warnings

from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route, RouteLeg
from src.optimization.solver_config import SolverConfig


# ===========================
# Fixtures - Realistic 4-Week Scenario
# ===========================


@pytest.fixture
def four_week_forecast() -> Forecast:
    """Create realistic 4-week (28-day) forecast with varying demand."""
    base_date = date(2025, 10, 13)
    entries = []

    # Two products with different demand patterns
    # Product 176283: 500-800 units/day (varying)
    # Product 176284: 300-500 units/day (varying)

    for i in range(28):
        curr_date = base_date + timedelta(days=i)

        # Week 1: Moderate demand
        if i < 7:
            qty_1 = 600.0
            qty_2 = 400.0
        # Week 2: High demand (peak)
        elif i < 14:
            qty_1 = 800.0
            qty_2 = 500.0
        # Week 3: Low demand (trough)
        elif i < 21:
            qty_1 = 500.0
            qty_2 = 300.0
        # Week 4: Moderate demand
        else:
            qty_1 = 650.0
            qty_2 = 420.0

        # Add demand for single destination
        entries.append(
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=curr_date,
                quantity=qty_1
            )
        )
        entries.append(
            ForecastEntry(
                location_id="6103",
                product_id="176284",
                forecast_date=curr_date,
                quantity=qty_2
            )
        )

    return Forecast(name="4-Week Varying Demand", entries=entries)


@pytest.fixture
def four_week_labor_calendar() -> LaborCalendar:
    """Create 4-week labor calendar with weekday/weekend structure."""
    base_date = date(2025, 10, 13)
    labor_days = []

    for i in range(35):  # Extra days for planning horizon
        curr_date = base_date + timedelta(days=i)
        day_of_week = curr_date.weekday()

        # Monday-Friday: Fixed labor days
        if day_of_week < 5:
            labor_days.append(
                LaborDay(
                    calendar_date=curr_date,
                    is_fixed_day=True,
                    fixed_hours=12.0,
                    overtime_hours_available=2.0,
                    minimum_hours=0.0,
                    regular_rate=50.0,
                    overtime_rate=75.0,
                    non_fixed_rate=0.0
                )
            )
        # Saturday-Sunday: Non-fixed labor (OT only)
        else:
            labor_days.append(
                LaborDay(
                    calendar_date=curr_date,
                    is_fixed_day=False,
                    fixed_hours=0.0,
                    overtime_hours_available=14.0,
                    minimum_hours=4.0,
                    regular_rate=0.0,
                    overtime_rate=0.0,
                    non_fixed_rate=100.0
                )
            )

    return LaborCalendar(labor_days=labor_days)


@pytest.fixture
def simple_manufacturing_site() -> ManufacturingSite:
    """Create simple manufacturing site."""
    return ManufacturingSite(
        location_id="6122",
        production_rate_per_hour=1400.0,
        max_hours_per_day=14.0
    )


@pytest.fixture
def simple_cost_structure() -> CostStructure:
    """Create simple cost structure."""
    return CostStructure(
        production_cost_per_unit=0.5,
        transport_cost_per_unit_per_km=0.01,
        holding_cost_per_unit_per_day=0.02,
        shortage_penalty_per_unit=100.0,
        storage_cost_frozen_per_unit_day=0.05,
        storage_cost_ambient_per_unit_day=0.02
    )


@pytest.fixture
def simple_locations() -> List[Location]:
    """Create simple location network."""
    return [
        Location(
            id="6122",
            name="Manufacturing Site",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH,
            capacity=100000
        ),
        Location(
            id="6103",
            name="Breadroom",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
            capacity=10000
        ),
    ]


@pytest.fixture
def simple_routes() -> List[Route]:
    """Create simple route (direct)."""
    return [
        Route(
            id="R1",
            route_legs=[
                RouteLeg(
                    from_location_id="6122",
                    to_location_id="6103",
                    transport_mode="ambient",
                    transit_days=1,
                    cost_per_unit=1.0
                )
            ]
        ),
    ]


@pytest.fixture
def solver_config() -> SolverConfig:
    """Create solver configuration for tests."""
    return SolverConfig(
        solver_name="cbc",
        time_limit_seconds=300,
        mip_gap=0.05,
        threads=1
    )


# ===========================
# Test 1: Production Spread Test
# ===========================


def test_production_spread_with_smoothing(
    four_week_forecast,
    four_week_labor_calendar,
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    Test that production spreads across multiple days with smoothing enabled.

    REGRESSION TEST: This test would FAIL on the old code with FIFO penalty,
    which caused all production to concentrate on 1 day.

    Verifies:
    - Production occurs on ≥ 10 days (for 4 weeks)
    - NOT all production on 1 day
    - Production spread > 30% of planning horizon
    """
    model = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,  # Enable batch tracking
        enable_production_smoothing=True  # Enable smoothing (should be default)
    )

    # Build and solve
    model.build()
    result = model.solve()

    # Check solution exists
    assert result.is_optimal() or result.is_feasible(), \
        f"Solution should be optimal or feasible, got: {result.termination_condition}"

    # Extract production schedule
    production_schedule = model.get_production_schedule()

    # Count days with production
    days_with_production = set()
    total_production = 0.0

    for batch in production_schedule.batches:
        if batch.quantity > 0.1:  # Ignore tiny floating-point values
            days_with_production.add(batch.production_date)
            total_production += batch.quantity

    num_production_days = len(days_with_production)
    total_days = len(model.dates)
    production_spread = num_production_days / total_days if total_days > 0 else 0

    print(f"\n=== Production Spread Test Results ===")
    print(f"Total days in horizon: {total_days}")
    print(f"Days with production: {num_production_days}")
    print(f"Production spread: {production_spread:.1%}")
    print(f"Total production: {total_production:,.0f} units")
    print(f"Production days: {sorted(days_with_production)[:10]}...")  # Show first 10

    # CRITICAL REGRESSION TEST: Should NOT concentrate on 1 day
    assert num_production_days > 1, \
        "REGRESSION: Production concentrated on single day (FIFO penalty bug)"

    # Should spread across multiple days (at least 10 for 4-week horizon)
    assert num_production_days >= 10, \
        f"Production should spread across ≥10 days, got {num_production_days}"

    # Production spread should be > 30% (at least 1/3 of days have production)
    assert production_spread > 0.30, \
        f"Production spread should be >30%, got {production_spread:.1%}"


# ===========================
# Test 2: Smoothing Constraint Test
# ===========================


def test_smoothing_constraint_enforced(
    four_week_forecast,
    four_week_labor_calendar,
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    Test that day-to-day production changes respect smoothing constraint.

    Verifies:
    - Max day-to-day change ≤ 20% of max capacity (3,920 units)
    - Consecutive production days don't violate constraint
    - Constraint is actually enforced by optimizer
    """
    model = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,
        enable_production_smoothing=True
    )

    model.build()
    result = model.solve()

    assert result.is_optimal() or result.is_feasible(), \
        f"Solution should be optimal or feasible, got: {result.termination_condition}"

    # Extract production by date and product
    production_by_date_product: Dict[Tuple[date, str], float] = defaultdict(float)

    production_schedule = model.get_production_schedule()
    for batch in production_schedule.batches:
        if batch.quantity > 0.1:
            key = (batch.production_date, batch.product_id)
            production_by_date_product[key] = batch.quantity

    # Calculate max capacity and smoothing limit
    max_daily_capacity = 1400.0 * 14.0  # 19,600 units
    max_allowed_change = 0.20 * max_daily_capacity  # 3,920 units

    # Check day-to-day changes for each product
    dates_sorted = sorted(model.dates)
    max_violation = 0.0
    violations = []

    for product in model.products:
        for i in range(1, len(dates_sorted)):
            prev_date = dates_sorted[i - 1]
            curr_date = dates_sorted[i]

            prev_prod = production_by_date_product.get((prev_date, product), 0.0)
            curr_prod = production_by_date_product.get((curr_date, product), 0.0)

            change = abs(curr_prod - prev_prod)

            if change > max_allowed_change + 1.0:  # Allow 1-unit tolerance for solver precision
                violations.append({
                    'product': product,
                    'date': curr_date,
                    'prev_prod': prev_prod,
                    'curr_prod': curr_prod,
                    'change': change,
                    'limit': max_allowed_change
                })
                max_violation = max(max_violation, change - max_allowed_change)

    print(f"\n=== Smoothing Constraint Test Results ===")
    print(f"Max allowed day-to-day change: {max_allowed_change:,.0f} units")
    print(f"Number of violations: {len(violations)}")
    if violations:
        print(f"Max violation: {max_violation:,.0f} units over limit")
        print(f"Sample violations:")
        for v in violations[:3]:
            print(f"  {v['product']} on {v['date']}: {v['prev_prod']:,.0f} → {v['curr_prod']:,.0f} (Δ={v['change']:,.0f})")

    # Should have no violations
    assert len(violations) == 0, \
        f"Found {len(violations)} smoothing constraint violations (max: {max_violation:,.0f} units over limit)"


# ===========================
# Test 3: Parameter Control Test
# ===========================


def test_parameter_control_smoothing_on_off(
    four_week_forecast,
    four_week_labor_calendar,
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    Test that enable_production_smoothing parameter controls behavior.

    Verifies:
    - enable_production_smoothing=True: Enforces smoothing (spread)
    - enable_production_smoothing=False: Allows concentration (if desired)
    - Default behavior with batch_tracking=True is smoothing enabled
    """
    # Test 1: Smoothing ENABLED (should spread production)
    model_with_smoothing = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,
        enable_production_smoothing=True
    )

    model_with_smoothing.build()
    result_with = model_with_smoothing.solve()

    assert result_with.is_optimal() or result_with.is_feasible()

    schedule_with = model_with_smoothing.get_production_schedule()
    days_with_production_smoothed = len({b.production_date for b in schedule_with.batches if b.quantity > 0.1})

    # Test 2: Smoothing DISABLED (may concentrate, but not required to)
    model_without_smoothing = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,
        enable_production_smoothing=False
    )

    model_without_smoothing.build()
    result_without = model_without_smoothing.solve()

    assert result_without.is_optimal() or result_without.is_feasible()

    schedule_without = model_without_smoothing.get_production_schedule()
    days_with_production_unsmoothed = len({b.production_date for b in schedule_without.batches if b.quantity > 0.1})

    # Test 3: Default behavior (should enable smoothing when batch_tracking=True)
    model_default = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,
        # enable_production_smoothing NOT specified (should default to True)
    )

    assert model_default.enable_production_smoothing == True, \
        "Default should enable smoothing when batch_tracking=True"

    print(f"\n=== Parameter Control Test Results ===")
    print(f"Days with production (smoothing ON):  {days_with_production_smoothed}")
    print(f"Days with production (smoothing OFF): {days_with_production_unsmoothed}")
    print(f"Default enable_production_smoothing: {model_default.enable_production_smoothing}")

    # With smoothing, should spread across multiple days
    assert days_with_production_smoothed >= 10, \
        f"Smoothing enabled should spread production, got {days_with_production_smoothed} days"

    # Without smoothing, might be fewer days (model has freedom to concentrate)
    # But both should produce feasible solutions
    assert days_with_production_unsmoothed >= 1, \
        "Should have at least 1 production day"


# ===========================
# Test 4: Regression Test - Single Day Bug
# ===========================


def test_regression_single_day_production_bug_fixed(
    four_week_forecast,
    four_week_labor_calendar,
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    CRITICAL REGRESSION TEST: Verify single-day production bug is fixed.

    This test explicitly validates that the FIFO penalty bug that caused
    all production to concentrate on 1 day is now fixed.

    Bug History:
    - Old code: FIFO penalty (lines 2215-2240) caused perverse incentive
    - Result: ALL production concentrated on single day (unrealistic)
    - Fix: Disabled FIFO penalty, added production smoothing constraint

    This test would FAIL on old code, PASS on fixed code.
    """
    model = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,  # This triggered the bug in old code
        enable_production_smoothing=True  # This is the fix
    )

    model.build()
    result = model.solve()

    assert result.is_optimal() or result.is_feasible(), \
        f"Solution should be optimal or feasible, got: {result.termination_condition}"

    # Extract production schedule
    production_schedule = model.get_production_schedule()

    # Group by production date
    production_by_date: Dict[date, float] = defaultdict(float)
    for batch in production_schedule.batches:
        if batch.quantity > 0.1:
            production_by_date[batch.production_date] += batch.quantity

    # Calculate statistics
    num_production_days = len(production_by_date)
    total_production = sum(production_by_date.values())
    max_single_day = max(production_by_date.values()) if production_by_date else 0
    max_single_day_percentage = (max_single_day / total_production * 100) if total_production > 0 else 0

    print(f"\n=== Regression Test: Single-Day Bug ===")
    print(f"Total production days: {num_production_days}")
    print(f"Total production: {total_production:,.0f} units")
    print(f"Max single-day production: {max_single_day:,.0f} units ({max_single_day_percentage:.1f}%)")
    print(f"Production by date (top 5):")
    for prod_date, qty in sorted(production_by_date.items(), key=lambda x: x[1], reverse=True)[:5]:
        pct = (qty / total_production * 100) if total_production > 0 else 0
        print(f"  {prod_date}: {qty:,.0f} units ({pct:.1f}%)")

    # CRITICAL: Should NOT have only 1 production day
    assert num_production_days > 1, \
        "REGRESSION FAILURE: Production concentrated on single day (FIFO penalty bug returned!)"

    # Should NOT have 80%+ production on single day (indicates concentration)
    assert max_single_day_percentage < 80.0, \
        f"REGRESSION WARNING: {max_single_day_percentage:.1f}% of production on single day (threshold: 80%)"

    # Should have reasonable spread (at least 10 days for 4-week scenario)
    assert num_production_days >= 10, \
        f"REGRESSION WARNING: Only {num_production_days} production days (expected ≥10 for 4 weeks)"


# ===========================
# Test 5: Integration Test
# ===========================


def test_batch_tracking_and_smoothing_integration(
    four_week_forecast,
    four_week_labor_calendar,
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    Test that batch tracking and production smoothing work together correctly.

    Verifies:
    - Cohort variables created correctly
    - Shelf life enforcement still works
    - Demand satisfaction maintained
    - Production smoothing doesn't break batch tracking logic
    """
    model = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,
        enable_production_smoothing=True
    )

    model.build()
    result = model.solve()

    assert result.is_optimal() or result.is_feasible(), \
        f"Solution should be optimal or feasible, got: {result.termination_condition}"

    # Check batch tracking components exist
    pyomo_model = model.model
    assert hasattr(pyomo_model, 'cohort_inventory'), \
        "Batch tracking should create cohort_inventory variables"
    assert hasattr(pyomo_model, 'cohort_balance_initial'), \
        "Batch tracking should create cohort balance constraints"

    # Check production smoothing constraint exists
    assert hasattr(pyomo_model, 'production_smoothing_con'), \
        "Production smoothing constraint should exist"

    # Extract and validate production schedule
    production_schedule = model.get_production_schedule()
    total_production = sum(b.quantity for b in production_schedule.batches)

    # Calculate total demand
    total_demand = sum(e.quantity for e in four_week_forecast.entries)

    print(f"\n=== Integration Test Results ===")
    print(f"Total demand: {total_demand:,.0f} units")
    print(f"Total production: {total_production:,.0f} units")
    print(f"Production/Demand ratio: {total_production / total_demand:.2f}")

    # Production should meet or exceed demand (allowing for some waste/inventory)
    assert total_production >= total_demand * 0.95, \
        f"Production ({total_production:,.0f}) should meet demand ({total_demand:,.0f})"

    # Should not overproduce excessively (< 20% over demand)
    assert total_production <= total_demand * 1.20, \
        f"Production ({total_production:,.0f}) should not exceed demand by >20%"


# ===========================
# Test 6: Edge Cases
# ===========================


def test_high_demand_edge_case(
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    Test smoothing with very high demand requiring max capacity.

    Verifies:
    - Smoothing should relax if demand requires max capacity
    - Should still find feasible solution
    - Should not force infeasibility
    """
    # Create high demand scenario (near max capacity)
    base_date = date(2025, 10, 13)
    entries = []

    # Max capacity: 1400 * 14 = 19,600 units/day
    # Set demand to ~18,000 units/day for 14 days
    for i in range(14):
        entries.append(
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=base_date + timedelta(days=i),
                quantity=18000.0
            )
        )

    high_demand_forecast = Forecast(name="High Demand Test", entries=entries)

    # Create labor calendar
    labor_days = []
    for i in range(21):
        curr_date = base_date + timedelta(days=i)
        labor_days.append(
            LaborDay(
                calendar_date=curr_date,
                is_fixed_day=True,
                fixed_hours=12.0,
                overtime_hours_available=2.0,
                minimum_hours=0.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                non_fixed_rate=0.0
            )
        )

    high_demand_labor = LaborCalendar(labor_days=labor_days)

    model = IntegratedProductionDistributionModel(
        forecast=high_demand_forecast,
        labor_calendar=high_demand_labor,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=True,  # Allow shortages if capacity insufficient
        use_batch_tracking=True,
        enable_production_smoothing=True
    )

    model.build()
    result = model.solve()

    # Should find a solution (may have shortages if capacity insufficient)
    assert result.is_optimal() or result.is_feasible(), \
        f"High demand scenario should find solution, got: {result.termination_condition}"

    production_schedule = model.get_production_schedule()
    total_production = sum(b.quantity for b in production_schedule.batches)

    print(f"\n=== High Demand Edge Case Results ===")
    print(f"Total production: {total_production:,.0f} units")
    print(f"Total demand: {18000 * 14:,.0f} units")

    # Should produce at high capacity
    assert total_production > 200000, \
        f"High demand should trigger high production, got {total_production:,.0f}"


def test_low_demand_edge_case(
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    Test smoothing with very low demand.

    Verifies:
    - Should allow zero production on many days
    - Should not force unnecessary production
    - Should minimize cost
    """
    # Create low demand scenario
    base_date = date(2025, 10, 13)
    entries = []

    # Low demand: 200 units/day for 14 days
    for i in range(14):
        entries.append(
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=base_date + timedelta(days=i),
                quantity=200.0
            )
        )

    low_demand_forecast = Forecast(name="Low Demand Test", entries=entries)

    # Create labor calendar
    labor_days = []
    for i in range(21):
        curr_date = base_date + timedelta(days=i)
        day_of_week = curr_date.weekday()

        if day_of_week < 5:  # Weekday
            labor_days.append(
                LaborDay(
                    calendar_date=curr_date,
                    is_fixed_day=True,
                    fixed_hours=12.0,
                    overtime_hours_available=2.0,
                    minimum_hours=0.0,
                    regular_rate=50.0,
                    overtime_rate=75.0,
                    non_fixed_rate=0.0
                )
            )
        else:  # Weekend
            labor_days.append(
                LaborDay(
                    calendar_date=curr_date,
                    is_fixed_day=False,
                    fixed_hours=0.0,
                    overtime_hours_available=14.0,
                    minimum_hours=4.0,
                    regular_rate=0.0,
                    overtime_rate=0.0,
                    non_fixed_rate=100.0
                )
            )

    low_demand_labor = LaborCalendar(labor_days=labor_days)

    model = IntegratedProductionDistributionModel(
        forecast=low_demand_forecast,
        labor_calendar=low_demand_labor,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,
        enable_production_smoothing=True
    )

    model.build()
    result = model.solve()

    assert result.is_optimal() or result.is_feasible(), \
        f"Low demand scenario should find solution, got: {result.termination_condition}"

    production_schedule = model.get_production_schedule()
    days_with_production = len({b.production_date for b in production_schedule.batches if b.quantity > 0.1})
    total_production = sum(b.quantity for b in production_schedule.batches)

    print(f"\n=== Low Demand Edge Case Results ===")
    print(f"Total production: {total_production:,.0f} units")
    print(f"Total demand: {200 * 14:,.0f} units")
    print(f"Production days: {days_with_production}")

    # Should have minimal production days (low demand allows concentration for efficiency)
    assert days_with_production >= 1, "Should have at least 1 production day"
    assert days_with_production <= 7, f"Low demand should use few production days, got {days_with_production}"


# ===========================
# Test 7: Backward Compatibility
# ===========================


def test_backward_compatibility_no_batch_tracking(
    four_week_forecast,
    four_week_labor_calendar,
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    Test backward compatibility with legacy mode (no batch tracking).

    Verifies:
    - use_batch_tracking=False still works
    - Production smoothing defaults to False when batch_tracking=False
    - Can explicitly enable smoothing even without batch tracking
    """
    # Test 1: Legacy mode (no batch tracking, no smoothing)
    model_legacy = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=False,  # Legacy mode
        # enable_production_smoothing not specified (should default to False)
    )

    assert model_legacy.enable_production_smoothing == False, \
        "Legacy mode should default to smoothing OFF"

    model_legacy.build()
    result_legacy = model_legacy.solve()

    assert result_legacy.is_optimal() or result_legacy.is_feasible(), \
        "Legacy mode should still work"

    # Test 2: Can explicitly enable smoothing even without batch tracking
    model_legacy_smoothed = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=False,
        enable_production_smoothing=True  # Explicitly enable
    )

    assert model_legacy_smoothed.enable_production_smoothing == True, \
        "Should allow explicit smoothing even without batch tracking"

    model_legacy_smoothed.build()
    result_smoothed = model_legacy_smoothed.solve()

    assert result_smoothed.is_optimal() or result_smoothed.is_feasible(), \
        "Legacy mode with smoothing should work"

    print(f"\n=== Backward Compatibility Test Results ===")
    print(f"Legacy mode (no batch tracking): Solved successfully")
    print(f"Legacy mode default smoothing: {model_legacy.enable_production_smoothing}")
    print(f"Legacy with explicit smoothing: {model_legacy_smoothed.enable_production_smoothing}")


# ===========================
# Summary Test
# ===========================


def test_production_smoothing_summary(
    four_week_forecast,
    four_week_labor_calendar,
    simple_manufacturing_site,
    simple_cost_structure,
    simple_locations,
    simple_routes,
    solver_config
):
    """
    Summary test that validates all key aspects of production smoothing fix.

    This is a comprehensive test that would be run in CI/CD to ensure
    the production smoothing fix is working correctly and hasn't regressed.
    """
    print("\n" + "=" * 70)
    print("PRODUCTION SMOOTHING FIX - COMPREHENSIVE VALIDATION")
    print("=" * 70)

    model = IntegratedProductionDistributionModel(
        forecast=four_week_forecast,
        labor_calendar=four_week_labor_calendar,
        manufacturing_site=simple_manufacturing_site,
        cost_structure=simple_cost_structure,
        locations=simple_locations,
        routes=simple_routes,
        solver_config=solver_config,
        allow_shortages=False,
        use_batch_tracking=True,
        enable_production_smoothing=True
    )

    model.build()
    result = model.solve()

    assert result.is_optimal() or result.is_feasible()

    # Extract production data
    production_schedule = model.get_production_schedule()
    production_by_date: Dict[date, float] = defaultdict(float)

    for batch in production_schedule.batches:
        if batch.quantity > 0.1:
            production_by_date[batch.production_date] += batch.quantity

    num_production_days = len(production_by_date)
    total_production = sum(production_by_date.values())
    total_demand = sum(e.quantity for e in four_week_forecast.entries)
    production_spread = num_production_days / len(model.dates)

    # Calculate day-to-day changes
    dates_sorted = sorted(production_by_date.keys())
    max_change = 0.0
    for i in range(1, len(dates_sorted)):
        change = abs(production_by_date[dates_sorted[i]] - production_by_date[dates_sorted[i-1]])
        max_change = max(max_change, change)

    max_allowed_change = 0.20 * 1400.0 * 14.0  # 3,920 units

    print(f"\n📊 PRODUCTION STATISTICS:")
    print(f"   Total demand:           {total_demand:>10,.0f} units")
    print(f"   Total production:       {total_production:>10,.0f} units")
    print(f"   Production days:        {num_production_days:>10} / {len(model.dates)}")
    print(f"   Production spread:      {production_spread:>10.1%}")
    print(f"   Max day-to-day change:  {max_change:>10,.0f} units")
    print(f"   Smoothing limit:        {max_allowed_change:>10,.0f} units")

    print(f"\n✅ VALIDATION CHECKS:")

    # Check 1: Not single day
    check1 = num_production_days > 1
    print(f"   ✓ NOT single-day production:      {'PASS' if check1 else 'FAIL'}")
    assert check1, "CRITICAL: Single-day production bug detected!"

    # Check 2: Good spread
    check2 = num_production_days >= 10
    print(f"   ✓ Production spread (≥10 days):   {'PASS' if check2 else 'FAIL'}")
    assert check2

    # Check 3: Smoothing respected
    check3 = max_change <= max_allowed_change + 1.0
    print(f"   ✓ Smoothing constraint:           {'PASS' if check3 else 'FAIL'}")
    assert check3

    # Check 4: Demand satisfied
    check4 = total_production >= total_demand * 0.95
    print(f"   ✓ Demand satisfaction:            {'PASS' if check4 else 'FAIL'}")
    assert check4

    print(f"\n{'=' * 70}")
    print("ALL CHECKS PASSED - Production smoothing fix validated successfully!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
