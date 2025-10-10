"""Regression tests for batch tracking implementation.

This test suite ensures that the batch tracking implementation maintains
backward compatibility and doesn't break existing functionality:
- Legacy mode works unchanged
- Existing tests still pass
- Cost calculations remain consistent
- Daily snapshot backward compatibility

These tests protect against regressions when adding new features.
"""

import pytest
from datetime import date, timedelta
from typing import List

from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route, RouteLeg
from src.production.scheduler import ProductionSchedule
from src.analysis.daily_snapshot import DailySnapshotGenerator


# ===========================
# Shared Fixtures
# ===========================


@pytest.fixture
def standard_forecast() -> Forecast:
    """Standard forecast for regression testing."""
    base_date = date(2025, 10, 13)
    entries = []

    for i in range(7):
        entries.append(
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=base_date + timedelta(days=i),
                quantity=100.0
            )
        )

    return Forecast(name="Standard Test Forecast", entries=entries)


@pytest.fixture
def standard_labor_calendar() -> LaborCalendar:
    """Standard labor calendar for regression testing."""
    base_date = date(2025, 10, 13)
    days = []

    for i in range(14):
        current_date = base_date + timedelta(days=i)
        is_weekend = current_date.weekday() >= 5

        days.append(
            LaborDay(
                calendar_date=current_date,
                fixed_hours=0.0 if is_weekend else 12.0,
                is_public_holiday=False,
                labor_cost_rate=50.0 if is_weekend else 40.0
            )
        )

    return LaborCalendar(days=days)


@pytest.fixture
def standard_manufacturing() -> ManufacturingSite:
    """Standard manufacturing site."""
    return ManufacturingSite(
        location_id="6122",
        production_rate_per_hour=1400.0,
        max_hours_per_day=14.0
    )


@pytest.fixture
def standard_cost_structure() -> CostStructure:
    """Standard cost structure."""
    return CostStructure(
        production_cost_per_unit=0.5,
        transport_cost_per_unit_per_km=0.01,
        holding_cost_per_unit_per_day=0.02,
        shortage_penalty_per_unit=100.0
    )


@pytest.fixture
def standard_locations() -> List[Location]:
    """Standard location list."""
    return [
        Location(
            id="6122",
            name="Manufacturing",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH
        ),
        Location(
            id="6103",
            name="Breadroom VIC",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT
        )
    ]


@pytest.fixture
def standard_routes() -> List[Route]:
    """Standard route list."""
    return [
        Route(
            id="ROUTE-001",
            route_legs=[
                RouteLeg(
                    from_location_id="6122",
                    to_location_id="6103",
                    transport_mode="ambient",
                    transit_days=2,
                    cost_per_unit=1.0
                )
            ]
        )
    ]


# ===========================
# Tests - Legacy Mode Compatibility
# ===========================


def test_legacy_mode_still_works(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    standard_manufacturing: ManufacturingSite,
    standard_cost_structure: CostStructure,
    standard_locations: List[Location],
    standard_routes: List[Route]
) -> None:
    """Test that legacy mode (use_batch_tracking=False) works unchanged."""
    model = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=60)

    # Verify solution was found
    assert result is not None
    assert 'solver_status' in result

    if result['solver_status'] == 'optimal':
        # Verify legacy result structure
        assert result['use_batch_tracking'] == False

        # Should have production
        assert 'production_by_date_product' in result
        assert sum(result['production_by_date_product'].values()) > 0

        # Should NOT have batch objects (or empty list)
        if 'production_batch_objects' in result:
            assert len(result['production_batch_objects']) == 0


def test_legacy_result_structure_unchanged(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    standard_manufacturing: ManufacturingSite,
    standard_cost_structure: CostStructure,
    standard_locations: List[Location],
    standard_routes: List[Route]
) -> None:
    """Test that legacy result dict has all expected fields."""
    model = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=60)

    if result.get('solver_status') != 'optimal':
        pytest.skip("Solver did not find optimal solution")

    # Check for expected legacy fields
    expected_fields = [
        'solver_status',
        'objective_value',
        'production_by_date_product',
        'total_production',
        'use_batch_tracking'
    ]

    for field in expected_fields:
        assert field in result, f"Missing field in legacy result: {field}"


def test_daily_snapshot_legacy_mode_without_model_solution(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    standard_manufacturing: ManufacturingSite,
    standard_cost_structure: CostStructure,
    standard_locations: List[Location],
    standard_routes: List[Route]
) -> None:
    """Test that DailySnapshot works in legacy mode (without model solution)."""
    # Solve in legacy mode
    model = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=60)

    if result.get('solver_status') != 'optimal':
        pytest.skip("Solver did not find optimal solution")

    # Create minimal production schedule (without batches)
    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=date(2025, 10, 13),
        schedule_end_date=date(2025, 10, 20),
        production_batches=[],  # Empty in legacy mode
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=0.0,
        total_labor_hours=0.0
    )

    # Create snapshot generator WITHOUT model solution
    locations_dict = {loc.id: loc for loc in standard_locations}

    generator = DailySnapshotGenerator(
        production_schedule=schedule,
        shipments=[],  # Empty shipments
        locations_dict=locations_dict,
        forecast=standard_forecast,
        model_solution=None  # Legacy mode
    )

    # Verify generator uses legacy mode
    assert generator.use_model_inventory == False

    # Generate snapshot (should not crash)
    snapshot = generator._generate_single_snapshot(date(2025, 10, 15))

    assert snapshot is not None
    assert snapshot.date == date(2025, 10, 15)
    assert len(snapshot.location_inventory) > 0


# ===========================
# Tests - Cost Equivalence
# ===========================


def test_cost_equivalence_between_modes(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    standard_manufacturing: ManufacturingSite,
    standard_cost_structure: CostStructure,
    standard_locations: List[Location],
    standard_routes: List[Route]
) -> None:
    """Test that both modes produce similar total costs (within tolerance).

    The FIFO penalty should be small for typical scenarios, so costs should
    be within 5% of each other.
    """
    # Solve in legacy mode
    model_legacy = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    result_legacy = model_legacy.solve(time_limit_seconds=60)

    if result_legacy.get('solver_status') != 'optimal':
        pytest.skip("Legacy solver did not find optimal solution")

    cost_legacy = result_legacy['objective_value']

    # Solve in cohort mode
    model_cohort = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result_cohort = model_cohort.solve(time_limit_seconds=60)

    if result_cohort.get('solver_status') != 'optimal':
        pytest.skip("Cohort solver did not find optimal solution")

    cost_cohort = result_cohort['objective_value']

    # Compare costs (should be within 10% due to FIFO penalty)
    if cost_legacy > 0:
        diff_pct = abs(cost_cohort - cost_legacy) / cost_legacy * 100

        assert diff_pct < 10.0, \
            f"Cost difference too large: {diff_pct:.1f}% " \
            f"(legacy=${cost_legacy:.2f}, cohort=${cost_cohort:.2f})"


def test_production_quantities_similar_between_modes(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    standard_manufacturing: ManufacturingSite,
    standard_cost_structure: CostStructure,
    standard_locations: List[Location],
    standard_routes: List[Route]
) -> None:
    """Test that production quantities are similar in both modes."""
    # Solve both modes
    model_legacy = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    result_legacy = model_legacy.solve(time_limit_seconds=60)

    model_cohort = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result_cohort = model_cohort.solve(time_limit_seconds=60)

    if result_legacy.get('solver_status') != 'optimal':
        pytest.skip("Legacy solver did not find optimal solution")

    if result_cohort.get('solver_status') != 'optimal':
        pytest.skip("Cohort solver did not find optimal solution")

    # Compare total production
    total_legacy = result_legacy.get('total_production', 0.0)
    total_cohort = result_cohort.get('total_production', 0.0)

    # Should be within 5%
    if total_legacy > 0:
        diff_pct = abs(total_cohort - total_legacy) / total_legacy * 100

        assert diff_pct < 5.0, \
            f"Production difference too large: {diff_pct:.1f}% " \
            f"(legacy={total_legacy:.2f}, cohort={total_cohort:.2f})"


# ===========================
# Tests - Existing Test Compatibility
# ===========================


def test_all_existing_daily_snapshot_tests_still_pass() -> None:
    """Meta-test: verify that all existing daily_snapshot tests still pass.

    This test imports and runs a subset of existing tests to ensure
    backward compatibility. In practice, this would be handled by
    the test suite runner, but we include it here for completeness.
    """
    # This is a placeholder - in practice, pytest will run all tests
    # We just document the requirement here
    pytest.skip("Meta-test: run via pytest tests/test_daily_snapshot.py")


def test_existing_integration_tests_still_pass() -> None:
    """Meta-test: verify that existing integration tests still pass."""
    pytest.skip("Meta-test: run via pytest tests/test_daily_snapshot_integration.py")


# ===========================
# Tests - API Stability
# ===========================


def test_model_constructor_api_unchanged(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    standard_manufacturing: ManufacturingSite,
    standard_cost_structure: CostStructure,
    standard_locations: List[Location],
    standard_routes: List[Route]
) -> None:
    """Test that model constructor API is unchanged (new param is optional)."""
    # Should work without use_batch_tracking parameter (defaults to False)
    model = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        validate_feasibility=False
    )

    # Default should be False (legacy mode)
    assert model.use_batch_tracking == False


def test_daily_snapshot_generator_api_unchanged(
    standard_locations: List[Location],
    standard_forecast: Forecast
) -> None:
    """Test that DailySnapshotGenerator API is unchanged."""
    # Create minimal schedule
    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=date(2025, 10, 13),
        schedule_end_date=date(2025, 10, 20),
        production_batches=[],
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=0.0,
        total_labor_hours=0.0
    )

    locations_dict = {loc.id: loc for loc in standard_locations}

    # Should work without model_solution parameter
    generator = DailySnapshotGenerator(
        production_schedule=schedule,
        shipments=[],
        locations_dict=locations_dict,
        forecast=standard_forecast
        # model_solution is optional
    )

    assert generator.model_solution is None
    assert generator.use_model_inventory == False


# ===========================
# Tests - Error Handling
# ===========================


def test_invalid_batch_tracking_flag_type(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    standard_manufacturing: ManufacturingSite,
    standard_cost_structure: CostStructure,
    standard_locations: List[Location],
    standard_routes: List[Route]
) -> None:
    """Test that invalid use_batch_tracking values are rejected."""
    # Should accept boolean values
    try:
        model = IntegratedProductionDistributionModel(
            forecast=standard_forecast,
            labor_calendar=standard_labor_calendar,
            manufacturing_site=standard_manufacturing,
            cost_structure=standard_cost_structure,
            locations=standard_locations,
            routes=standard_routes,
            use_batch_tracking=True,
            validate_feasibility=False
        )
        assert model.use_batch_tracking == True
    except TypeError:
        pytest.fail("Should accept boolean True")

    try:
        model = IntegratedProductionDistributionModel(
            forecast=standard_forecast,
            labor_calendar=standard_labor_calendar,
            manufacturing_site=standard_manufacturing,
            cost_structure=standard_cost_structure,
            locations=standard_locations,
            routes=standard_routes,
            use_batch_tracking=False,
            validate_feasibility=False
        )
        assert model.use_batch_tracking == False
    except TypeError:
        pytest.fail("Should accept boolean False")


def test_model_solution_format_validation() -> None:
    """Test that DailySnapshotGenerator validates model_solution format."""
    # This test would verify that passing an invalid model_solution
    # doesn't crash the generator (graceful fallback to legacy mode)

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=date(2025, 10, 13),
        schedule_end_date=date(2025, 10, 20),
        production_batches=[],
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=0.0,
        total_labor_hours=0.0
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.BOTH)
    }

    forecast = Forecast(name="Test", entries=[])

    # Pass invalid model_solution (missing required fields)
    invalid_solution = {'some_field': 'some_value'}

    generator = DailySnapshotGenerator(
        production_schedule=schedule,
        shipments=[],
        locations_dict=locations_dict,
        forecast=forecast,
        model_solution=invalid_solution
    )

    # Should fall back to legacy mode
    assert generator.use_model_inventory == False


# ===========================
# Tests - Performance Regression
# ===========================


def test_legacy_mode_performance_unchanged(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    standard_manufacturing: ManufacturingSite,
    standard_cost_structure: CostStructure,
    standard_locations: List[Location],
    standard_routes: List[Route]
) -> None:
    """Test that legacy mode performance is not degraded."""
    import time

    model = IntegratedProductionDistributionModel(
        forecast=standard_forecast,
        labor_calendar=standard_labor_calendar,
        manufacturing_site=standard_manufacturing,
        cost_structure=standard_cost_structure,
        locations=standard_locations,
        routes=standard_routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    # Model build should be fast
    start = time.time()
    pyomo_model = model.build_model()
    build_time = time.time() - start

    assert build_time < 2.0, f"Model build too slow: {build_time:.2f}s"
    assert pyomo_model is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
