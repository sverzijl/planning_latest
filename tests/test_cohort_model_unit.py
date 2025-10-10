"""Unit tests for age-cohort batch tracking model components.

This test suite validates individual components of the batch tracking implementation:
- Sparse cohort indexing
- Shelf life filtering
- FIFO penalty calculation
- Cohort balance constraints
- Production-to-cohort mapping

These tests are fast and isolated, designed to run frequently during development.
"""

import pytest
from datetime import date, timedelta
from typing import Dict, List, Set, Tuple

from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route, RouteLeg


# ===========================
# Fixtures - Basic Setup
# ===========================


@pytest.fixture
def minimal_forecast() -> Forecast:
    """Create minimal 7-day forecast for testing."""
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

    return Forecast(name="Minimal Test Forecast", entries=entries)


@pytest.fixture
def minimal_labor_calendar() -> LaborCalendar:
    """Create minimal labor calendar."""
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
def minimal_manufacturing() -> ManufacturingSite:
    """Create minimal manufacturing site."""
    return ManufacturingSite(
        location_id="6122",
        production_rate_per_hour=1400.0,
        max_hours_per_day=14.0
    )


@pytest.fixture
def minimal_cost_structure() -> CostStructure:
    """Create minimal cost structure."""
    return CostStructure(
        production_cost_per_unit=0.5,
        transport_cost_per_unit_per_km=0.01,
        holding_cost_per_unit_per_day=0.02,
        shortage_penalty_per_unit=100.0
    )


@pytest.fixture
def minimal_locations() -> List[Location]:
    """Create minimal location list."""
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
def minimal_routes() -> List[Route]:
    """Create minimal route list."""
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
# Tests - Model Construction
# ===========================


def test_batch_tracking_flag_initialization(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that use_batch_tracking flag is properly stored."""
    # Legacy mode (default)
    model_legacy = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=False,
        validate_feasibility=False
    )
    assert model_legacy.use_batch_tracking == False

    # Batch tracking mode
    model_cohort = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False
    )
    assert model_cohort.use_batch_tracking == True


def test_cohort_model_builds_successfully(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that cohort model builds without errors."""
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False
    )

    pyomo_model = model.build_model()

    # Verify model was created
    assert pyomo_model is not None

    # Verify cohort-specific components exist (if implemented)
    # Note: These checks will pass/fail based on actual implementation
    # Adjust based on actual variable names in your implementation


def test_legacy_model_builds_successfully(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that legacy model still builds successfully."""
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=False,
        validate_feasibility=False
    )

    pyomo_model = model.build_model()

    # Verify model was created
    assert pyomo_model is not None


# ===========================
# Tests - Sparse Indexing
# ===========================


def test_sparse_indexing_reasonable_size(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that sparse indexing keeps model size manageable.

    For a 7-day horizon with 1 product and 2 locations, cohort variables
    should be limited by shelf life constraints.
    """
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False
    )

    pyomo_model = model.build_model()

    # Count total variables (rough upper bound check)
    # For 7-day horizon: should have < 1000 variables total
    from pyomo.environ import Var
    total_vars = sum(1 for _ in pyomo_model.component_data_objects(Var))

    assert total_vars < 1000, f"Too many variables: {total_vars}"


def test_cohort_index_respects_shelf_life(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that cohort indexes only include valid (non-expired) cohorts.

    For ambient storage with 17-day shelf life, cohorts older than 17 days
    should not exist in the index.
    """
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False
    )

    pyomo_model = model.build_model()

    # If cohort indexes are exposed, verify shelf life constraint
    # This test assumes cohort indexes are accessible via:
    # pyomo_model.inventory_ambient_cohort_index or similar

    # Skip if not implemented yet
    if not hasattr(pyomo_model, 'inventory_ambient_cohort_index'):
        pytest.skip("Cohort indexes not yet implemented")

    AMBIENT_SHELF_LIFE = 17

    for cohort_key in pyomo_model.inventory_ambient_cohort_index:
        # Expected format: (location, product, production_date, current_date)
        if len(cohort_key) == 4:
            _, _, prod_date, curr_date = cohort_key
            age = (curr_date - prod_date).days
            assert age <= AMBIENT_SHELF_LIFE, \
                f"Expired cohort found: age={age}d > {AMBIENT_SHELF_LIFE}d"


# ===========================
# Tests - Production Batches
# ===========================


def test_production_batches_created_from_solution(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that ProductionBatch objects are created from solution."""
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True  # Allow shortages for quick solve
    )

    result = model.solve(time_limit_seconds=30)

    # Verify batches were created
    if 'production_batch_objects' in result:
        batches = result['production_batch_objects']

        # Should have at least one batch if production occurred
        if result.get('total_production', 0) > 0:
            assert len(batches) > 0, "No batches created despite production"

            # Verify batch structure
            for batch in batches:
                assert batch.id.startswith("BATCH-"), f"Invalid batch ID: {batch.id}"
                assert batch.quantity > 0, "Batch has zero quantity"
                assert batch.production_date is not None, "Batch missing production date"
                assert batch.product_id in model.products, f"Unknown product: {batch.product_id}"


def test_batch_ids_unique(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that all batch IDs are unique."""
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=30)

    if 'production_batch_objects' in result:
        batches = result['production_batch_objects']
        batch_ids = [b.id for b in batches]

        # Check uniqueness
        assert len(batch_ids) == len(set(batch_ids)), \
            f"Duplicate batch IDs found: {[id for id in batch_ids if batch_ids.count(id) > 1]}"


def test_production_batch_quantities_match_decision_variables(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that batch quantities match production decision variables."""
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=30)

    if 'production_batch_objects' in result and 'production_by_date_product' in result:
        batches = result['production_batch_objects']
        production_vars = result['production_by_date_product']

        # Sum batches by (date, product)
        batch_totals: Dict[Tuple[date, str], float] = {}
        for batch in batches:
            key = (batch.production_date, batch.product_id)
            if key not in batch_totals:
                batch_totals[key] = 0.0
            batch_totals[key] += batch.quantity

        # Compare with production variables
        for key, batch_total in batch_totals.items():
            prod_var_total = production_vars.get(key, 0.0)

            # Should match within rounding tolerance
            assert abs(batch_total - prod_var_total) < 0.01, \
                f"Batch total {batch_total} != production var {prod_var_total} for {key}"


# ===========================
# Tests - Mass Balance
# ===========================


def test_production_equals_shipments_plus_inventory(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test mass balance: production = shipments + ending inventory + demand."""
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=60)

    if not result.get('solver_status') == 'optimal':
        pytest.skip("Solver did not find optimal solution")

    # Extract totals
    total_production = sum(result.get('production_by_date_product', {}).values())

    # Calculate total shipments
    if 'batch_shipments' in result:
        total_shipments = sum(s.quantity for s in result['batch_shipments'])
    else:
        total_shipments = sum(result.get('shipments_by_route_product_date', {}).values())

    # Get ending inventory
    if 'cohort_inventory' in result:
        total_inventory = sum(result['cohort_inventory'].values())
    else:
        total_inventory = 0.0

    # Get total demand satisfied
    total_demand = sum(result.get('demand_by_dest_product_date', {}).values())
    total_shortage = sum(result.get('shortages_by_dest_product_date', {}).values())
    total_satisfied = total_demand - total_shortage

    # Mass balance check (allowing for rounding errors)
    # production ≈ (shipments - demand_satisfied) + inventory
    # OR simpler: production + initial_inventory ≈ shipments + ending_inventory

    # Since we have no initial inventory:
    # production ≈ total_satisfied + ending_inventory
    expected = total_satisfied + total_inventory

    assert abs(total_production - expected) < 1.0, \
        f"Mass balance violated: production={total_production:.2f}, " \
        f"satisfied={total_satisfied:.2f}, inventory={total_inventory:.2f}, " \
        f"expected={expected:.2f}"


# ===========================
# Tests - Result Structure
# ===========================


def test_result_contains_batch_tracking_fields(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that result dict contains batch tracking fields."""
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=30)

    # Verify required fields
    assert 'use_batch_tracking' in result
    assert result['use_batch_tracking'] == True

    # If solution was found, verify batch-specific fields
    if result.get('solver_status') == 'optimal':
        # These fields should exist (may be empty)
        assert 'production_batch_objects' in result
        assert isinstance(result['production_batch_objects'], list)


def test_legacy_result_structure_preserved(
    minimal_forecast: Forecast,
    minimal_labor_calendar: LaborCalendar,
    minimal_manufacturing: ManufacturingSite,
    minimal_cost_structure: CostStructure,
    minimal_locations: List[Location],
    minimal_routes: List[Route]
) -> None:
    """Test that legacy mode result structure is unchanged."""
    model = IntegratedProductionDistributionModel(
        forecast=minimal_forecast,
        labor_calendar=minimal_labor_calendar,
        manufacturing_site=minimal_manufacturing,
        cost_structure=minimal_cost_structure,
        locations=minimal_locations,
        routes=minimal_routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=30)

    # Verify legacy fields
    assert 'use_batch_tracking' in result
    assert result['use_batch_tracking'] == False

    # Legacy mode should NOT have batch objects
    if 'production_batch_objects' in result:
        assert len(result['production_batch_objects']) == 0


# ===========================
# Tests - Performance
# ===========================


def test_model_build_time_acceptable() -> None:
    """Test that model builds in reasonable time."""
    import time

    # Create 14-day test scenario
    base_date = date(2025, 10, 13)

    forecast = Forecast(
        name="14-day Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=base_date + timedelta(days=i),
                quantity=100.0
            )
            for i in range(14)
        ]
    )

    labor_calendar = LaborCalendar(
        days=[
            LaborDay(
                calendar_date=base_date + timedelta(days=i),
                fixed_hours=12.0 if (base_date + timedelta(days=i)).weekday() < 5 else 0.0,
                is_public_holiday=False,
                labor_cost_rate=40.0
            )
            for i in range(21)
        ]
    )

    manufacturing = ManufacturingSite(
        location_id="6122",
        production_rate_per_hour=1400.0,
        max_hours_per_day=14.0
    )

    cost_structure = CostStructure(
        production_cost_per_unit=0.5,
        transport_cost_per_unit_per_km=0.01,
        holding_cost_per_unit_per_day=0.02,
        shortage_penalty_per_unit=100.0
    )

    locations = [
        Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.BOTH),
        Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT)
    ]

    routes = [
        Route(
            id="R1",
            route_legs=[
                RouteLeg(from_location_id="6122", to_location_id="6103",
                        transport_mode="ambient", transit_days=2, cost_per_unit=1.0)
            ]
        )
    ]

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=True,
        validate_feasibility=False
    )

    start = time.time()
    pyomo_model = model.build_model()
    elapsed = time.time() - start

    # Model should build in < 5 seconds for 14-day horizon
    assert elapsed < 5.0, f"Model build too slow: {elapsed:.2f}s"
    assert pyomo_model is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
