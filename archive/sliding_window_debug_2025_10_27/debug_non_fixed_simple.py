"""Simple debug script to diagnose non-fixed day infeasibility."""

from datetime import date
from pyomo.environ import value

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel


def create_test_setup(is_fixed_day: bool):
    """Create test setup."""
    production_date = date(2025, 10, 25)  # Saturday

    # Manufacturing node
    manufacturing_node = UnifiedNode(
        id="6122",
        name="Manufacturing",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            production_rate_per_hour=1400.0,
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

    # Route
    route = UnifiedRoute(
        id="ROUTE-6122-6110",
        origin_node_id="6122",
        destination_node_id="6110",
        transport_mode=TransportMode.AMBIENT,
        transit_days=0.0,
        cost_per_unit=0.1,
    )

    # Forecast
    forecast = Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="6110",
                product_id="PROD1",
                forecast_date=production_date,
                quantity=2800.0,  # 2h production
            )
        ]
    )

    # Labor calendar
    labor_day = LaborDay(
        date=production_date,
        fixed_hours=12.0 if is_fixed_day else 0.0,
        overtime_hours=2.0 if is_fixed_day else 0.0,
        regular_rate=20.0,
        overtime_rate=30.0,
        non_fixed_rate=40.0 if not is_fixed_day else None,
        minimum_hours=4.0 if not is_fixed_day else 0.0,
        is_fixed_day=is_fixed_day,
    )

    labor_calendar = LaborCalendar(
        name="Test Calendar",
        days=[labor_day]
    )

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=1.0,
        default_regular_rate=20.0,
        default_overtime_rate=30.0,
        default_non_fixed_rate=40.0,
        shortage_penalty_per_unit=100.0,
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


def analyze_infeasibility():
    """Analyze the infeasibility."""

    print("\n" + "="*80)
    print("TESTING NON-FIXED DAY (SATURDAY)")
    print("="*80)

    setup = create_test_setup(is_fixed_day=False)

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

    # Try to solve
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        tee=True,  # Show solver output
    )

    print(f"\n{'='*80}")
    print(f"SOLVE RESULT (NON-FIXED DAY):")
    print(f"{'='*80}")
    print(f"Success: {result.success}")
    print(f"Status: {result.solver_status}")
    print(f"Termination: {result.termination_condition}")
    print(f"Message: {result.infeasibility_message}")
    print(f"Num variables: {result.num_variables}")
    print(f"Num constraints: {result.num_constraints}")
    print(f"Num integer vars: {result.num_integer_vars}")

    # Compare with fixed day
    print("\n\n" + "="*80)
    print("TESTING FIXED DAY (WEEKDAY) - FOR COMPARISON")
    print("="*80)

    setup_fixed = create_test_setup(is_fixed_day=True)

    model_obj_fixed = UnifiedNodeModel(
        nodes=setup_fixed['nodes'],
        routes=setup_fixed['routes'],
        forecast=setup_fixed['forecast'],
        labor_calendar=setup_fixed['labor_calendar'],
        cost_structure=setup_fixed['cost_structure'],
        start_date=setup_fixed['production_date'],
        end_date=setup_fixed['production_date'],
        use_batch_tracking=True,
        allow_shortages=False,
    )

    result_fixed = model_obj_fixed.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        tee=False,
    )

    print(f"\n{'='*80}")
    print(f"SOLVE RESULT (FIXED DAY):")
    print(f"{'='*80}")
    print(f"Success: {result_fixed.success}")
    print(f"Status: {result_fixed.solver_status}")
    print(f"Termination: {result_fixed.termination_condition}")
    print(f"Num variables: {result_fixed.num_variables}")
    print(f"Num constraints: {result_fixed.num_constraints}")
    print(f"Num integer vars: {result_fixed.num_integer_vars}")

    if result_fixed.is_optimal() or result_fixed.is_feasible():
        print("\n✓ Fixed day SOLVES - this confirms the issue is NON-FIXED day specific")


if __name__ == "__main__":
    analyze_infeasibility()
