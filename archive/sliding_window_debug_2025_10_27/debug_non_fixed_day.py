"""Debug script to diagnose non-fixed day infeasibility."""

from datetime import date
from pyomo.environ import value, Constraint

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


def print_constraint_details(model, node_id, date_val):
    """Print all constraint details for a specific node and date."""
    print(f"\n{'='*80}")
    print(f"CONSTRAINT ANALYSIS: Node {node_id}, Date {date_val}")
    print(f"{'='*80}")

    # Get constraint list
    constraints = [
        ('labor_hours_linking_con', model.labor_hours_linking_con),
        ('fixed_hours_limit_con', model.fixed_hours_limit_con),
        ('overtime_calculation_con', model.overtime_calculation_con),
        ('labor_hours_paid_lower_con', model.labor_hours_paid_lower_con),
        ('minimum_hours_enforcement_con', model.minimum_hours_enforcement_con),
        ('overtime_indicator_upper_con', model.overtime_indicator_upper_con),
        ('overtime_indicator_lower_con', model.overtime_indicator_lower_con),
        ('production_day_lower_con', model.production_day_lower_con),
        ('production_day_upper_con', model.production_day_upper_con),
    ]

    for name, con in constraints:
        if (node_id, date_val) in con:
            expr = con[node_id, date_val].expr
            print(f"\n{name}:")
            print(f"  Expression: {expr}")

    # Print variable bounds
    print(f"\n{'='*80}")
    print(f"VARIABLE BOUNDS:")
    print(f"{'='*80}")

    vars_to_check = [
        'labor_hours_used',
        'labor_hours_paid',
        'fixed_hours_used',
        'overtime_hours_used',
        'uses_overtime',
        'production_day',
    ]

    for var_name in vars_to_check:
        if hasattr(model, var_name):
            var = getattr(model, var_name)
            if (node_id, date_val) in var:
                var_obj = var[node_id, date_val]
                print(f"\n{var_name}[{node_id}, {date_val}]:")
                print(f"  Domain: {var_obj.domain}")
                print(f"  Bounds: [{var_obj.lb}, {var_obj.ub}]")


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

    # Print constraint details BEFORE solving
    print_constraint_details(model_obj.model, "6122", setup['production_date'])

    # Try to solve
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        tee=True,  # Show solver output
    )

    print(f"\n{'='*80}")
    print(f"SOLVE RESULT:")
    print(f"{'='*80}")
    print(f"Success: {result.success}")
    print(f"Status: {result.solver_status}")
    print(f"Termination: {result.termination_condition}")
    print(f"Message: {result.infeasibility_message}")

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

    # Print constraint details
    print_constraint_details(model_obj_fixed.model, "6122", setup_fixed['production_date'])

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

    if result_fixed.is_optimal() or result_fixed.is_feasible():
        print("\n✓ Fixed day SOLVES - extracting variable values:")
        for var_name in ['labor_hours_used', 'labor_hours_paid', 'fixed_hours_used',
                        'overtime_hours_used', 'uses_overtime', 'production_day']:
            if hasattr(model_obj_fixed.model, var_name):
                var = getattr(model_obj_fixed.model, var_name)
                if ("6122", setup_fixed['production_date']) in var:
                    val = value(var["6122", setup_fixed['production_date']])
                    print(f"  {var_name}: {val}")


if __name__ == "__main__":
    analyze_infeasibility()
