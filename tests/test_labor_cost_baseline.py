"""Baseline tests for labor cost calculation.

These tests capture the CURRENT behavior (blended rate approximation) before
implementing piecewise labor cost modeling. These baselines help detect
regressions and quantify the impact of the fix.

IMPORTANT: Run these tests BEFORE implementing piecewise labor costs!
"""

import json
import pytest
from datetime import date, timedelta
from pathlib import Path

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel


def create_minimal_labor_test_setup(
    production_date: date,
    demand_qty: float,
    is_fixed_day: bool,
    fixed_hours: float = 12.0,
    regular_rate: float = 20.0,
    overtime_rate: float = 30.0,
    non_fixed_rate: float = 40.0,
    minimum_hours: float = 4.0,
):
    """Create minimal test setup for labor cost testing.

    Network: Manufacturing (6122) → Breadroom (6110)
    Single product, single day forecast

    Args:
        production_date: Date of production
        demand_qty: Demand quantity (units)
        is_fixed_day: True for weekday, False for weekend
        fixed_hours: Fixed labor hours (default 12)
        regular_rate: Regular hourly rate (default $20)
        overtime_rate: Overtime hourly rate (default $30)
        non_fixed_rate: Non-fixed day rate (default $40)
        minimum_hours: Minimum hours payment on non-fixed days (default 4)

    Returns:
        Dict with nodes, routes, forecast, labor_calendar, cost_structure, production_date
    """
    # Manufacturing node
    manufacturing_node = UnifiedNode(
        id="6122",
        name="Manufacturing",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            production_rate_per_hour=1400.0,  # QBA actual rate
        ),
        storage_mode=StorageMode.AMBIENT,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
    )

    # Demand node
    demand_node = UnifiedNode(
        id="6110",
        name="Breadroom",
        capabilities=NodeCapabilities(
            has_demand=True,
            can_store=True,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    # Route (instant transit for simplicity)
    route = UnifiedRoute(
        id="ROUTE-6122-6110",
        origin_node_id="6122",
        destination_node_id="6110",
        transport_mode=TransportMode.AMBIENT,
        transit_days=0.0,  # Same-day delivery
        cost_per_unit=0.1,
    )

    # Forecast (single day demand)
    forecast = Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="6110",
                product_id="PROD1",
                forecast_date=production_date,
                quantity=demand_qty,
            )
        ]
    )

    # Labor calendar (single day)
    labor_day = LaborDay(
        date=production_date,
        fixed_hours=fixed_hours if is_fixed_day else 0.0,
        overtime_hours=2.0 if is_fixed_day else 0.0,  # Weekday: 12 + 2 OT = 14h max
        regular_rate=regular_rate,
        overtime_rate=overtime_rate,
        non_fixed_rate=non_fixed_rate if not is_fixed_day else None,
        minimum_hours=minimum_hours if not is_fixed_day else 0.0,
        is_fixed_day=is_fixed_day,
    )

    labor_calendar = LaborCalendar(
        name="Test Calendar",
        days=[labor_day]
    )

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=1.0,
        default_regular_rate=regular_rate,
        default_overtime_rate=overtime_rate,
        default_non_fixed_rate=non_fixed_rate,
        shortage_penalty_per_unit=100.0,  # High penalty to force satisfaction
        # Zero storage costs to simplify labor cost isolation
        storage_cost_frozen_per_unit_day=0.0,
        storage_cost_ambient_per_unit_day=0.0,
    )

    return {
        'nodes': [manufacturing_node, demand_node],
        'routes': [route],
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'cost_structure': cost_structure,
        'production_date': production_date,
    }


@pytest.mark.baseline
def test_labor_cost_baseline_fixed_day_no_overtime():
    """Baseline: Fixed day with 6h production (no overtime).

    Setup:
        - Monday (fixed day): 12h @ $20/h regular, OT @ $30/h
        - Production: 8,400 units = 6h at 1,400 units/hr
        - Overhead: 0.5h startup + 0.25h shutdown = 0.75h
        - Total labor hours: 6h + 0.75h = 6.75h

    Current Behavior (blended rate):
        - Blended rate = ($20 + $30) / 2 = $25/h
        - Labor cost = 6.75h × $25 = $168.75

    Expected Behavior (piecewise - NOT YET IMPLEMENTED):
        - All hours at regular rate: 6.75h × $20 = $135.00
        - Error: $33.75 (25% overcharge)
    """
    setup = create_minimal_labor_test_setup(
        production_date=date(2025, 10, 20),  # Monday
        demand_qty=8400.0,  # 6h production
        is_fixed_day=True,
    )

    # Create model
    model_obj = UnifiedNodeModel(
        nodes=setup['nodes'],
        routes=setup['routes'],
        forecast=setup['forecast'],
        labor_calendar=setup['labor_calendar'],
        cost_structure=setup['cost_structure'],
        start_date=setup['production_date'],
        end_date=setup['production_date'],
        use_batch_tracking=True,
        allow_shortages=False,
    )

    # Solve
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        tee=False,
    )

    # Assert solution found
    assert result.is_optimal() or result.is_feasible(), \
        f"Expected feasible solution, got {result.termination_condition}"

    # Extract solution
    solution = model_obj.get_solution()

    # Extract total cost (includes labor cost)
    total_cost = solution.get('total_cost', 0)
    production_cost = solution.get('total_production_cost', 0)
    transport_cost = solution.get('total_transport_cost', 0)

    # Calculate labor cost (by subtraction - no direct extraction in current model)
    labor_cost_extracted = total_cost - production_cost - transport_cost

    # Expected values with current blended rate (NO OVERHEAD - BUG!)
    PRODUCTION_TIME = 8400.0 / 1400.0  # 6.0h
    OVERHEAD_TIME = 0.5 + 0.25  # 0.75h
    BLENDED_RATE = (20.0 + 30.0) / 2  # $25/h

    # CURRENT BEHAVIOR: Only charges for production time, NOT overhead!
    EXPECTED_LABOR_COST_CURRENT = PRODUCTION_TIME * BLENDED_RATE  # $150.00 (BUG: no overhead!)

    # CORRECT with blended rate (including overhead)
    TOTAL_HOURS = PRODUCTION_TIME + OVERHEAD_TIME  # 6.75h
    EXPECTED_LABOR_COST_BLENDED_WITH_OVERHEAD = TOTAL_HOURS * BLENDED_RATE  # $168.75

    # CORRECT with piecewise (including overhead)
    EXPECTED_LABOR_COST_PIECEWISE = TOTAL_HOURS * 20.0  # $135.00 (all regular rate)

    # Error vs correct piecewise
    ERROR_AMOUNT = EXPECTED_LABOR_COST_BLENDED_WITH_OVERHEAD - EXPECTED_LABOR_COST_PIECEWISE  # $33.75
    ERROR_PCT = (ERROR_AMOUNT / EXPECTED_LABOR_COST_PIECEWISE) * 100  # 25%

    # Save baseline
    baseline = {
        'test_name': 'test_labor_cost_baseline_fixed_day_no_overtime',
        'scenario': 'Fixed day, 6h production (no overtime)',
        'production_qty': 8400.0,
        'labor_hours_production': PRODUCTION_TIME,
        'labor_hours_overhead': OVERHEAD_TIME,
        'labor_hours_total': TOTAL_HOURS,
        'regular_rate': 20.0,
        'overtime_rate': 30.0,
        'blended_rate': BLENDED_RATE,
        'labor_cost_actual': labor_cost_extracted,
        'labor_cost_current_expected': EXPECTED_LABOR_COST_CURRENT,
        'labor_cost_blended_with_overhead': EXPECTED_LABOR_COST_BLENDED_WITH_OVERHEAD,
        'labor_cost_piecewise_correct': EXPECTED_LABOR_COST_PIECEWISE,
        'bug': 'Current model does NOT include overhead time in labor cost',
        'error_amount': ERROR_AMOUNT,
        'error_pct': ERROR_PCT,
    }

    baseline_file = Path(__file__).parent / "test_baseline_labor_fixed_no_ot.json"
    with open(baseline_file, 'w') as f:
        json.dump(baseline, f, indent=2)

    print(f"\n✓ Baseline saved: {baseline_file}")
    print(f"  Labor cost (current): ${labor_cost_extracted:.2f}")
    print(f"  Expected (piecewise + overhead): ${EXPECTED_LABOR_COST_PIECEWISE:.2f}")
    print(f"  Error: ${ERROR_AMOUNT:.2f} ({ERROR_PCT:.1f}%)")
    print(f"  ⚠️ BUG: Current model does NOT include overhead time in labor cost!")

    # Assert baseline captured (with tolerance) - check against CURRENT behavior
    assert abs(labor_cost_extracted - EXPECTED_LABOR_COST_CURRENT) < 1.0, \
        f"Baseline labor cost {labor_cost_extracted:.2f} differs from current expected {EXPECTED_LABOR_COST_CURRENT:.2f}"


@pytest.mark.baseline
def test_labor_cost_baseline_fixed_day_with_overtime():
    """Baseline: Fixed day with 14h production (includes overtime).

    Setup:
        - Monday (fixed day): 12h @ $20/h regular, 2h OT @ $30/h
        - Production: 19,600 units = 14h at 1,400 units/hr
        - Overhead: 0.5h startup + 0.25h shutdown = 0.75h
        - Total labor hours: 14h + 0.75h = 14.75h

    Current Behavior (blended rate):
        - Blended rate = ($20 + $30) / 2 = $25/h
        - Labor cost = 14.75h × $25 = $368.75

    Expected Behavior (piecewise - NOT YET IMPLEMENTED):
        - Fixed: 12h × $20 = $240
        - Overtime: 2.75h × $30 = $82.50
        - Total: $322.50
        - Error: $46.25 (14.3% overcharge)
    """
    setup = create_minimal_labor_test_setup(
        production_date=date(2025, 10, 20),  # Monday
        demand_qty=19600.0,  # 14h production (maxes out capacity)
        is_fixed_day=True,
    )

    # Create model
    model_obj = UnifiedNodeModel(
        nodes=setup['nodes'],
        routes=setup['routes'],
        forecast=setup['forecast'],
        labor_calendar=setup['labor_calendar'],
        cost_structure=setup['cost_structure'],
        start_date=setup['production_date'],
        end_date=setup['production_date'],
        use_batch_tracking=True,
        allow_shortages=False,
    )

    # Solve
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        tee=False,
    )

    # Assert solution found
    assert result.is_optimal() or result.is_feasible(), \
        f"Expected feasible solution, got {result.termination_condition}"

    # Extract solution
    solution = model_obj.get_solution()

    # Extract total cost
    total_cost = solution.get('total_cost', 0)
    production_cost = solution.get('total_production_cost', 0)
    transport_cost = solution.get('total_transport_cost', 0)

    # Calculate labor cost
    labor_cost_extracted = total_cost - production_cost - transport_cost

    # Expected values
    PRODUCTION_TIME = 19600.0 / 1400.0  # 14.0h
    OVERHEAD_TIME = 0.5 + 0.25  # 0.75h
    TOTAL_HOURS = PRODUCTION_TIME + OVERHEAD_TIME  # 14.75h
    BLENDED_RATE = (20.0 + 30.0) / 2  # $25/h
    EXPECTED_LABOR_COST_BLENDED = TOTAL_HOURS * BLENDED_RATE  # $368.75

    # Piecewise calculation
    FIXED_HOURS = 12.0
    OVERTIME_HOURS = TOTAL_HOURS - FIXED_HOURS  # 2.75h
    EXPECTED_LABOR_COST_PIECEWISE = FIXED_HOURS * 20.0 + OVERTIME_HOURS * 30.0  # $322.50
    ERROR_AMOUNT = EXPECTED_LABOR_COST_BLENDED - EXPECTED_LABOR_COST_PIECEWISE
    ERROR_PCT = (ERROR_AMOUNT / EXPECTED_LABOR_COST_PIECEWISE) * 100

    # Save baseline
    baseline = {
        'test_name': 'test_labor_cost_baseline_fixed_day_with_overtime',
        'scenario': 'Fixed day, 14h production (with overtime)',
        'production_qty': 19600.0,
        'labor_hours_production': PRODUCTION_TIME,
        'labor_hours_overhead': OVERHEAD_TIME,
        'labor_hours_total': TOTAL_HOURS,
        'fixed_hours': FIXED_HOURS,
        'overtime_hours': OVERTIME_HOURS,
        'regular_rate': 20.0,
        'overtime_rate': 30.0,
        'blended_rate': BLENDED_RATE,
        'labor_cost_actual': labor_cost_extracted,
        'labor_cost_expected_blended': EXPECTED_LABOR_COST_BLENDED,
        'labor_cost_expected_piecewise': EXPECTED_LABOR_COST_PIECEWISE,
        'error_amount': ERROR_AMOUNT,
        'error_pct': ERROR_PCT,
    }

    baseline_file = Path(__file__).parent / "test_baseline_labor_fixed_with_ot.json"
    with open(baseline_file, 'w') as f:
        json.dump(baseline, f, indent=2)

    print(f"\n✓ Baseline saved: {baseline_file}")
    print(f"  Labor cost (blended): ${labor_cost_extracted:.2f}")
    print(f"  Expected (piecewise): ${EXPECTED_LABOR_COST_PIECEWISE:.2f}")
    print(f"  Error: ${ERROR_AMOUNT:.2f} ({ERROR_PCT:.1f}%)")

    # Assert baseline captured
    assert abs(labor_cost_extracted - EXPECTED_LABOR_COST_BLENDED) < 1.0


@pytest.mark.baseline
def test_labor_cost_baseline_non_fixed_day():
    """Baseline: Non-fixed day (weekend) production.

    Setup:
        - Saturday (non-fixed day): $40/h rate, 4h minimum payment
        - Production: 2,800 units = 2h at 1,400 units/hr
        - Overhead: 0.5h startup + 0.25h shutdown = 0.75h
        - Total labor hours: 2h + 0.75h = 2.75h

    Current Behavior:
        - Uses non_fixed_rate: $40/h
        - Labor cost = 2.75h × $40 = $110
        - WARNING: Does NOT enforce 4-hour minimum! (Bug)

    Expected Behavior (piecewise with 4h minimum):
        - Paid hours = max(2.75, 4.0) = 4.0h
        - Labor cost = 4.0h × $40 = $160
        - Current error: $50 undercharge (31% error)
    """
    setup = create_minimal_labor_test_setup(
        production_date=date(2025, 10, 25),  # Saturday
        demand_qty=2800.0,  # 2h production
        is_fixed_day=False,
        non_fixed_rate=40.0,
        minimum_hours=4.0,
    )

    # Create model
    model_obj = UnifiedNodeModel(
        nodes=setup['nodes'],
        routes=setup['routes'],
        forecast=setup['forecast'],
        labor_calendar=setup['labor_calendar'],
        cost_structure=setup['cost_structure'],
        start_date=setup['production_date'],
        end_date=setup['production_date'],
        use_batch_tracking=True,
        allow_shortages=False,
    )

    # Solve
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        tee=False,
    )

    # Assert solution found
    assert result.is_optimal() or result.is_feasible(), \
        f"Expected feasible solution, got {result.termination_condition}"

    # Extract solution
    solution = model_obj.get_solution()

    # Extract total cost
    total_cost = solution.get('total_cost', 0)
    production_cost = solution.get('total_production_cost', 0)
    transport_cost = solution.get('total_transport_cost', 0)

    # Calculate labor cost
    labor_cost_extracted = total_cost - production_cost - transport_cost

    # Expected values
    PRODUCTION_TIME = 2800.0 / 1400.0  # 2.0h
    OVERHEAD_TIME = 0.5 + 0.25  # 0.75h
    TOTAL_HOURS = PRODUCTION_TIME + OVERHEAD_TIME  # 2.75h
    NON_FIXED_RATE = 40.0
    MINIMUM_HOURS = 4.0

    EXPECTED_LABOR_COST_CURRENT = TOTAL_HOURS * NON_FIXED_RATE  # $110 (no minimum!)
    EXPECTED_LABOR_COST_WITH_MINIMUM = MINIMUM_HOURS * NON_FIXED_RATE  # $160 (with 4h minimum)
    ERROR_AMOUNT = EXPECTED_LABOR_COST_WITH_MINIMUM - EXPECTED_LABOR_COST_CURRENT
    ERROR_PCT = (ERROR_AMOUNT / EXPECTED_LABOR_COST_WITH_MINIMUM) * 100

    # Save baseline
    baseline = {
        'test_name': 'test_labor_cost_baseline_non_fixed_day',
        'scenario': 'Non-fixed day (weekend), 2h production',
        'production_qty': 2800.0,
        'labor_hours_production': PRODUCTION_TIME,
        'labor_hours_overhead': OVERHEAD_TIME,
        'labor_hours_total': TOTAL_HOURS,
        'minimum_hours': MINIMUM_HOURS,
        'non_fixed_rate': NON_FIXED_RATE,
        'labor_cost_actual': labor_cost_extracted,
        'labor_cost_expected_no_minimum': EXPECTED_LABOR_COST_CURRENT,
        'labor_cost_expected_with_minimum': EXPECTED_LABOR_COST_WITH_MINIMUM,
        'error_amount': ERROR_AMOUNT,
        'error_pct': ERROR_PCT,
        'bug': 'Current model does NOT enforce 4-hour minimum payment',
    }

    baseline_file = Path(__file__).parent / "test_baseline_labor_non_fixed.json"
    with open(baseline_file, 'w') as f:
        json.dump(baseline, f, indent=2)

    print(f"\n✓ Baseline saved: {baseline_file}")
    print(f"  Labor cost (no minimum): ${labor_cost_extracted:.2f}")
    print(f"  Expected (with 4h min): ${EXPECTED_LABOR_COST_WITH_MINIMUM:.2f}")
    print(f"  Error: ${ERROR_AMOUNT:.2f} ({ERROR_PCT:.1f}%)")
    print(f"  ⚠️ BUG: Current model does NOT enforce 4-hour minimum!")

    # Assert baseline captured (current behavior without minimum)
    assert abs(labor_cost_extracted - EXPECTED_LABOR_COST_CURRENT) < 1.0
