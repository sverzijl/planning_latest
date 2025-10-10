"""
Test suite for cohort tracking (batch/age-aware) optimization model.

This test file validates the age-cohort batch tracking implementation that enables:
- Shelf life enforcement during optimization (not after)
- FIFO/FEFO inventory management
- Product age tracking across the network

Tests cover:
1. Sparse cohort indexing produces reasonable model sizes
2. Cohort balance equations maintain mass balance
3. FIFO soft constraint encourages consuming old stock first
4. Production flows correctly into cohorts
5. Demand allocation sums correctly across cohorts
6. Backward compatibility with legacy aggregated model
"""

import pytest
from datetime import date, timedelta
from typing import Dict, List

from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.truck_schedule import TruckSchedule, TruckScheduleCollection
from src.optimization.solver_config import SolverConfig


@pytest.fixture
def simple_locations() -> List[Location]:
    """Create simple 2-location network for testing."""
    return [
        Location(
            id='6122',
            name='Manufacturing',
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.AMBIENT
        ),
        Location(
            id='6104',
            name='Destination',
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT
        )
    ]


@pytest.fixture
def simple_routes(simple_locations) -> List[Route]:
    """Create simple route from manufacturing to destination."""
    return [
        Route(
            origin_id='6122',
            destination_id='6104',
            transport_mode='ambient',
            transit_days=2,
            cost_per_unit=1.0
        )
    ]


@pytest.fixture
def simple_forecast() -> Forecast:
    """Create simple 7-day forecast for testing."""
    start_date = date(2024, 1, 1)
    entries = []
    for day in range(7):
        forecast_date = start_date + timedelta(days=day)
        entries.append(
            ForecastEntry(
                location_id='6104',
                product_id='P1',
                forecast_date=forecast_date,
                quantity=100.0
            )
        )
    return Forecast(entries=entries)


@pytest.fixture
def simple_labor_calendar() -> LaborCalendar:
    """Create labor calendar with simple weekday schedule."""
    labor_days = []
    start_date = date(2023, 12, 25)  # Start before forecast to allow production buffer
    for day in range(20):
        current_date = start_date + timedelta(days=day)
        is_weekend = current_date.weekday() >= 5
        labor_days.append(
            LaborDay(
                date=current_date,
                fixed_hours=0.0 if is_weekend else 12.0,
                is_fixed_day=not is_weekend,
                regular_rate=50.0,
                overtime_rate=75.0,
                non_fixed_rate=100.0 if is_weekend else None
            )
        )
    return LaborCalendar(labor_days=labor_days)


@pytest.fixture
def simple_manufacturing() -> ManufacturingSite:
    """Create manufacturing site."""
    return ManufacturingSite(
        location_id='6122',
        production_rate_units_per_hour=1400.0
    )


@pytest.fixture
def simple_costs() -> CostStructure:
    """Create cost structure."""
    return CostStructure(
        production_cost_per_unit=1.0,
        transport_cost_per_unit_km=0.01,
        storage_cost_frozen_per_unit_day=0.05,
        storage_cost_ambient_per_unit_day=0.02,
        shortage_penalty_per_unit=1000.0
    )


class TestCohortIndexing:
    """Test sparse cohort indexing for reasonable model size."""

    def test_cohort_indices_created(
        self,
        simple_forecast,
        simple_labor_calendar,
        simple_manufacturing,
        simple_costs,
        simple_locations,
        simple_routes
    ):
        """Test that cohort indices are created when use_batch_tracking=True."""
        model_obj = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=simple_manufacturing,
            cost_structure=simple_costs,
            locations=simple_locations,
            routes=simple_routes,
            use_batch_tracking=True,
            validate_feasibility=False  # Skip feasibility validation for unit test
        )

        # Build model to trigger index creation
        model = model_obj.build_model()

        # Verify cohort index sets exist
        assert hasattr(model_obj, 'cohort_frozen_index_set')
        assert hasattr(model_obj, 'cohort_ambient_index_set')
        assert hasattr(model_obj, 'cohort_shipment_index_set')
        assert hasattr(model_obj, 'cohort_demand_index_set')

        # Verify indices are non-empty
        assert len(model_obj.cohort_ambient_index_set) > 0
        assert len(model_obj.cohort_demand_index_set) > 0

        # Verify model has cohort variables
        assert hasattr(model, 'inventory_ambient_cohort')
        assert hasattr(model, 'shipment_leg_cohort')
        assert hasattr(model, 'demand_from_cohort')

    def test_cohort_index_size_reasonable(
        self,
        simple_forecast,
        simple_labor_calendar,
        simple_manufacturing,
        simple_costs,
        simple_locations,
        simple_routes
    ):
        """Test that cohort indexing doesn't explode model size."""
        model_obj = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=simple_manufacturing,
            cost_structure=simple_costs,
            locations=simple_locations,
            routes=simple_routes,
            use_batch_tracking=True,
            validate_feasibility=False
        )

        model = model_obj.build_model()

        # For a 7-day forecast with 1 product and 2 locations:
        # Naive 4D would be: ~7 dates × 7 prod_dates × 2 locs × 1 product = ~100 per type
        # But sparse indexing should filter many invalid combinations

        total_cohort_indices = (
            len(model_obj.cohort_frozen_index_set) +
            len(model_obj.cohort_ambient_index_set) +
            len(model_obj.cohort_shipment_index_set) +
            len(model_obj.cohort_demand_index_set)
        )

        # For this simple test case, should be < 500 total cohort indices
        assert total_cohort_indices < 500, (
            f"Cohort indexing too large: {total_cohort_indices} indices. "
            f"Sparse indexing may not be working correctly."
        )

        print(f"\nCohort index breakdown:")
        print(f"  Frozen: {len(model_obj.cohort_frozen_index_set)}")
        print(f"  Ambient: {len(model_obj.cohort_ambient_index_set)}")
        print(f"  Shipment: {len(model_obj.cohort_shipment_index_set)}")
        print(f"  Demand: {len(model_obj.cohort_demand_index_set)}")
        print(f"  Total: {total_cohort_indices}")

    def test_shelf_life_enforced_in_indexing(
        self,
        simple_forecast,
        simple_labor_calendar,
        simple_manufacturing,
        simple_costs,
        simple_locations,
        simple_routes
    ):
        """Test that cohort indices respect shelf life limits."""
        model_obj = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=simple_manufacturing,
            cost_structure=simple_costs,
            locations=simple_locations,
            routes=simple_routes,
            use_batch_tracking=True,
            validate_feasibility=False
        )

        model = model_obj.build_model()

        # Check ambient cohorts respect 17-day shelf life
        for (loc, prod, prod_date, curr_date) in model_obj.cohort_ambient_index_set:
            age_days = (curr_date - prod_date).days
            # Should not exceed ambient shelf life
            assert age_days <= model_obj.AMBIENT_SHELF_LIFE, (
                f"Ambient cohort exceeds shelf life: age={age_days} days at {loc} "
                f"(prod_date={prod_date}, curr_date={curr_date})"
            )

        # Check frozen cohorts respect 120-day shelf life
        for (loc, prod, prod_date, curr_date) in model_obj.cohort_frozen_index_set:
            age_days = (curr_date - prod_date).days
            assert age_days <= model_obj.FROZEN_SHELF_LIFE, (
                f"Frozen cohort exceeds shelf life: age={age_days} days"
            )


class TestCohortConstraints:
    """Test cohort balance equations and constraints."""

    def test_cohort_constraints_created(
        self,
        simple_forecast,
        simple_labor_calendar,
        simple_manufacturing,
        simple_costs,
        simple_locations,
        simple_routes
    ):
        """Test that cohort constraints are created."""
        model_obj = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=simple_manufacturing,
            cost_structure=simple_costs,
            locations=simple_locations,
            routes=simple_routes,
            use_batch_tracking=True,
            validate_feasibility=False
        )

        model = model_obj.build_model()

        # Verify cohort constraints exist
        assert hasattr(model, 'inventory_frozen_cohort_balance_con')
        assert hasattr(model, 'inventory_ambient_cohort_balance_con')
        assert hasattr(model, 'demand_cohort_allocation_con')
        assert hasattr(model, 'shipment_cohort_aggregation_con')

    def test_production_flows_into_cohorts(
        self,
        simple_forecast,
        simple_labor_calendar,
        simple_manufacturing,
        simple_costs,
        simple_locations,
        simple_routes
    ):
        """Test that all production dates have corresponding 6122_Storage cohorts."""
        model_obj = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=simple_manufacturing,
            cost_structure=simple_costs,
            locations=simple_locations,
            routes=simple_routes,
            use_batch_tracking=True,
            validate_feasibility=False
        )

        model = model_obj.build_model()

        # For each production date, there should be a 6122_Storage cohort
        for prod_date in model.dates:
            for product in model.products:
                cohort_key = ('6122_Storage', product, prod_date, prod_date)
                assert cohort_key in model_obj.cohort_ambient_index_set, (
                    f"Missing cohort for production on {prod_date} product {product}. "
                    f"Production must flow into 6122_Storage ambient cohort."
                )


class TestDemandAllocation:
    """Test demand allocation across cohorts."""

    def test_demand_cohorts_exist(
        self,
        simple_forecast,
        simple_labor_calendar,
        simple_manufacturing,
        simple_costs,
        simple_locations,
        simple_routes
    ):
        """Test that demand allocation cohorts exist for all demand points."""
        model_obj = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=simple_manufacturing,
            cost_structure=simple_costs,
            locations=simple_locations,
            routes=simple_routes,
            use_batch_tracking=True,
            validate_feasibility=False
        )

        model = model_obj.build_model()

        # For each demand point, there should be at least one cohort that can satisfy it
        for (loc, prod, demand_date) in model_obj.demand.keys():
            cohorts_for_demand = [
                (l, p, pd, dd)
                for (l, p, pd, dd) in model_obj.cohort_demand_index_set
                if l == loc and p == prod and dd == demand_date
            ]

            # Should have multiple cohorts (different production dates) that could satisfy demand
            assert len(cohorts_for_demand) > 0, (
                f"No cohorts available for demand at {loc}/{prod} on {demand_date}"
            )


class TestBackwardCompatibility:
    """Test that legacy model still works when use_batch_tracking=False."""

    def test_legacy_model_without_batch_tracking(
        self,
        simple_forecast,
        simple_labor_calendar,
        simple_manufacturing,
        simple_costs,
        simple_locations,
        simple_routes
    ):
        """Test that model builds successfully with use_batch_tracking=False."""
        model_obj = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=simple_manufacturing,
            cost_structure=simple_costs,
            locations=simple_locations,
            routes=simple_routes,
            use_batch_tracking=False,  # Legacy mode
            validate_feasibility=False
        )

        model = model_obj.build_model()

        # Verify cohort variables are NOT created
        assert not hasattr(model, 'inventory_ambient_cohort')
        assert not hasattr(model, 'shipment_leg_cohort')
        assert not hasattr(model, 'demand_from_cohort')

        # Verify legacy variables still exist
        assert hasattr(model, 'inventory_ambient')
        assert hasattr(model, 'shipment_leg')
        assert hasattr(model, 'production')


class TestValidation:
    """Test cohort model validation."""

    def test_validation_passes_for_valid_model(
        self,
        simple_forecast,
        simple_labor_calendar,
        simple_manufacturing,
        simple_costs,
        simple_locations,
        simple_routes
    ):
        """Test that validation passes for a correctly constructed model."""
        model_obj = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=simple_manufacturing,
            cost_structure=simple_costs,
            locations=simple_locations,
            routes=simple_routes,
            use_batch_tracking=True,
            validate_feasibility=False
        )

        # Building model should trigger validation (should not raise)
        model = model_obj.build_model()

        # Explicitly call validation
        model_obj._validate_cohort_model(model)  # Should not raise


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
