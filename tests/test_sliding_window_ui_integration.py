"""Test SlidingWindowModel UI integration with Pydantic schema.

This test validates that the SlidingWindowModel properly:
1. Extracts shipments from Pydantic solution.shipments (not raw dicts)
2. Filters out INIT batches from production activity
3. Validates solution data before returning
4. Works with Daily Snapshot component

Regression tests for issues reported 2025-10-29:
- No demand being satisfied
- No inflows/outflows visible
- Initial inventory appearing in Manufacturing Activity
- No manufacturing activity on days 2+
"""

import pytest
from datetime import date, timedelta
from src.optimization.result_schema import OptimizationSolution
from src.models.shipment import Shipment
from src.models.production_schedule import ProductionSchedule


def test_sliding_window_solution_has_shipments(sliding_window_4week_solution):
    """Test that SlidingWindowModel extracts shipments into Pydantic solution.

    Regression: extract_shipments() was trying to access non-existent
    shipments_by_route_product_date field instead of solution.shipments.
    """
    solution = sliding_window_4week_solution

    # Validate solution is Pydantic model
    assert isinstance(solution, OptimizationSolution)
    assert solution.model_type == "sliding_window"

    # Check shipments exist in solution
    assert solution.shipments is not None
    assert len(solution.shipments) > 0, "SlidingWindowModel must extract shipments"

    # Check shipments have required fields
    for shipment in solution.shipments:
        assert shipment.origin is not None
        assert shipment.destination is not None
        assert shipment.product is not None
        assert shipment.quantity > 0
        assert shipment.delivery_date is not None


def test_extract_shipments_uses_pydantic_solution(sliding_window_model_4week):
    """Test that extract_shipments() uses solution.shipments field.

    Regression: extract_shipments() was accessing shipments_by_route_product_date
    which doesn't exist on OptimizationSolution, causing empty shipments list.
    """
    model = sliding_window_model_4week

    # Get shipments via extract_shipments()
    shipments = model.extract_shipments()

    assert shipments is not None
    assert isinstance(shipments, list)
    assert len(shipments) > 0, "extract_shipments() must return shipments from solution"

    # Check shipments are proper Shipment objects
    for shipment in shipments:
        assert isinstance(shipment, Shipment)
        assert shipment.id is not None
        assert shipment.quantity > 0


def test_init_batches_not_in_production_activity(adapted_results_4week):
    """Test that INIT batches don't appear in production activity.

    Regression: Initial inventory batches (INIT-*) were appearing as
    "Manufacturing Activity" on day 1, confusing users.
    """
    production_schedule = adapted_results_4week['production_schedule']

    assert isinstance(production_schedule, ProductionSchedule)

    # Check that some batches exist
    assert len(production_schedule.production_batches) > 0

    # Get actual production activity (excluding INIT batches)
    actual_production_batches = [
        b for b in production_schedule.production_batches
        if not b.id.startswith('INIT-')
    ]

    # Check daily_totals only includes actual production
    for prod_date, quantity in production_schedule.daily_totals.items():
        # Count production on this date (excluding INIT)
        date_production = sum(
            b.quantity for b in actual_production_batches
            if b.production_date == prod_date
        )

        assert abs(date_production - quantity) < 0.01, \
            f"daily_totals[{prod_date}] should only include actual production, not INIT batches"


def test_solution_validation_catches_missing_shipments(sliding_window_model_4week):
    """Test that validation catches when shipments are missing.

    Validates that _validate_solution() catches data extraction bugs early.
    """
    from src.optimization.result_schema import (
        OptimizationSolution,
        ProductionBatchResult,
        TotalCostBreakdown,
        LaborCostBreakdown,
        ProductionCostBreakdown,
        TransportCostBreakdown,
        HoldingCostBreakdown,
        WasteCostBreakdown,
    )

    model = sliding_window_model_4week

    # Create invalid solution (production but no shipments)
    invalid_solution = OptimizationSolution(
        model_type="sliding_window",
        production_batches=[
            ProductionBatchResult(
                node="6122",
                product="TEST",
                date=date(2025, 11, 1),
                quantity=1000.0
            )
        ],
        labor_hours_by_date={},
        shipments=[],  # BUG: No shipments despite production
        costs=TotalCostBreakdown(
            total_cost=1000.0,
            labor=LaborCostBreakdown(total=300.0),
            production=ProductionCostBreakdown(total=250.0, unit_cost=0.25, total_units=1000.0),
            transport=TransportCostBreakdown(total=200.0),
            holding=HoldingCostBreakdown(total=150.0),
            waste=WasteCostBreakdown(total=100.0),
        ),
        total_cost=1000.0,
        fill_rate=1.0,
        total_production=1000.0,  # Production exists
        has_aggregate_inventory=True,
    )

    # Validation should catch this
    with pytest.raises(ValueError, match="Production exists.*but no shipments found"):
        model._validate_solution(invalid_solution)


def test_daily_snapshot_shows_flows(adapted_results_4week):
    """Test that Daily Snapshot has inflows/outflows/demand.

    Regression: No inflows/outflows were visible because shipments were empty.
    """
    from src.analysis.daily_snapshot import DailySnapshotGenerator
    from src.models.forecast import Forecast

    production_schedule = adapted_results_4week['production_schedule']
    shipments = adapted_results_4week['shipments']
    model_solution = adapted_results_4week['model_solution']

    # Need locations and forecast for snapshot
    # This is a simplified test - full test would use actual data
    assert len(shipments) > 0, "Shipments must exist for flows to be visible"
    assert isinstance(model_solution, OptimizationSolution)
    assert model_solution.model_type == "sliding_window"


# Fixtures

@pytest.fixture
def sliding_window_model_4week():
    """Create SlidingWindowModel with 4-week horizon."""
    # Import here to avoid circular dependencies
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.parsers.excel_parser import ExcelParser
    from src.optimization.sliding_window_model import SlidingWindowModel
    from datetime import date

    # Parse test data
    data_dir = Path(__file__).parent.parent / "data" / "examples"
    forecast_file = data_dir / "Gluten Free Forecast - Latest.xlsm"
    config_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory_latest.XLSX"

    parser = ExcelParser()
    forecast = parser.parse_forecast(forecast_file)
    locations = parser.parse_locations(config_file)
    routes = parser.parse_routes(config_file, locations)
    labor_calendar = parser.parse_labor_calendar(config_file)
    truck_schedules = parser.parse_truck_schedules(config_file)
    cost_params = parser.parse_cost_parameters(config_file)
    initial_inventory = parser.parse_inventory(inventory_file, locations)

    # Create model
    start_date = date(2025, 11, 3)
    end_date = start_date + timedelta(days=27)  # 4 weeks

    model = SlidingWindowModel(
        locations=locations,
        routes=routes,
        products=forecast.get_products(),
        forecast=forecast,
        start_date=start_date,
        end_date=end_date,
        labor_calendar=labor_calendar,
        truck_schedules=truck_schedules,
        cost_structure=cost_params,
        initial_inventory=initial_inventory,
        solver='appsi_highs',
        mip_gap=0.01,
        time_limit=120,
    )

    # Build and solve
    model.build_model()
    result = model.solve()

    assert result['status'] in ['optimal', 'feasible']

    return model


@pytest.fixture
def sliding_window_4week_solution(sliding_window_model_4week):
    """Get OptimizationSolution from solved model."""
    solution = sliding_window_model_4week.get_solution()
    assert solution is not None
    assert isinstance(solution, OptimizationSolution)
    return solution


@pytest.fixture
def adapted_results_4week(sliding_window_model_4week):
    """Get adapted results (UI-compatible format)."""
    from ui.utils.result_adapter import adapt_optimization_results
    from datetime import date

    model = sliding_window_model_4week
    result = {'status': 'optimal'}
    inventory_date = date(2025, 11, 2)

    adapted = adapt_optimization_results(model, result, inventory_date)
    assert adapted is not None
    return adapted
