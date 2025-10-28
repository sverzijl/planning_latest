"""Check which constraints are actually active."""

from datetime import date
from pyomo.environ import Constraint

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel


def create_test_setup(is_fixed_day: bool):
    """Create test setup."""
    production_date = date(2025, 10, 25)

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

    demand_node = UnifiedNode(
        id="6110",
        name="Breadroom",
        capabilities=NodeCapabilities(
            has_demand=True,
            can_store=True,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    route = UnifiedRoute(
        id="ROUTE-6122-6110",
        origin_node_id="6122",
        destination_node_id="6110",
        transport_mode=TransportMode.AMBIENT,
        transit_days=0.0,
        cost_per_unit=0.1,
    )

    forecast = Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="6110",
                product_id="PROD1",
                forecast_date=production_date,
                quantity=2800.0,
            )
        ]
    )

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


def check_constraints():
    """Check which constraints are active."""

    print("\n" + "="*80)
    print("NON-FIXED DAY - CONSTRAINT CHECK")
    print("="*80)

    setup = create_test_setup(is_fixed_day=False)

    # Create UnifiedNodeModel - this builds the model during __init__
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

    # Access the built model through the internal _model attribute or via solve
    # The model is built during initialization - let me check what's exposed
    # Actually, we need to trigger model building by attempting solve

    # Let's just write out the LP file and examine it
    import tempfile
    import os

    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lp', delete=False) as f:
        lp_file = f.name

    # Write LP
    from pyomo.environ import SolverFactory
    from pyomo.opt import ProblemFormat

    # Access the model - it should be stored internally
    # Let me check the base class to see how to access it
    print("Model object attributes:", dir(model_obj))


if __name__ == "__main__":
    check_constraints()
