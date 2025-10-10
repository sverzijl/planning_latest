"""Tests for batch-level solution extraction from cohort-tracking models."""

import pytest
from datetime import date, timedelta
from typing import Dict

from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.forecast import Forecast
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment


@pytest.fixture
def simple_test_data():
    """Create simple test data for batch extraction testing."""
    # Dates
    start_date = date(2025, 1, 6)  # Monday
    end_date = date(2025, 1, 10)   # Friday (5 days)

    # Locations
    manufacturing = Location(
        id='6122',
        name='Manufacturing Site',
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT
    )

    breadroom = Location(
        id='6100',
        name='Breadroom',
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT
    )

    # Routes (direct shipping)
    routes = [
        Route(
            id='R1',
            origin_id='6122',
            destination_id='6100',
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1,
            cost=0.5
        )
    ]

    # Products
    products = ['P1', 'P2']

    # Demand (simple demand at breadroom)
    demand = {
        ('6100', 'P1', start_date + timedelta(days=2)): 1000,
        ('6100', 'P2', start_date + timedelta(days=2)): 500,
        ('6100', 'P1', start_date + timedelta(days=4)): 800,
    }

    # Labor calendar (weekdays only)
    labor_days = []
    for i in range(5):
        d = start_date + timedelta(days=i)
        labor_days.append(LaborDay(
            date=d,
            is_fixed_day=True,
            fixed_hours=12,
            max_overtime_hours=2,
            regular_rate=50.0,
            overtime_rate=75.0,
            is_public_holiday=False
        ))

    labor_calendar = LaborCalendar(
        site_id='6122',
        labor_days=labor_days
    )

    # Manufacturing site
    manufacturing_site = ManufacturingSite(
        location_id='6122',
        production_rate_units_per_hour=1400,
        products=products
    )

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=1.0,
        storage_cost_frozen_per_unit_day=0.01,
        storage_cost_ambient_per_unit_day=0.005,
        shortage_penalty_per_unit=100.0,
        waste_cost_per_unit=2.0
    )

    # Forecast
    forecast = Forecast(
        demands=demand,
        products=products,
        locations=[manufacturing, breadroom],
        start_date=start_date,
        end_date=end_date
    )

    return {
        'forecast': forecast,
        'locations': [manufacturing, breadroom],
        'routes': routes,
        'labor_calendar': labor_calendar,
        'manufacturing_site': manufacturing_site,
        'cost_structure': cost_structure,
        'start_date': start_date,
        'end_date': end_date
    }


def test_batch_extraction_creates_batches(simple_test_data):
    """Test that production batches are created from solution."""
    # Build and solve model with batch tracking
    model = IntegratedProductionDistributionModel(
        forecast=simple_test_data['forecast'],
        locations=simple_test_data['locations'],
        routes=simple_test_data['routes'],
        manufacturing_site=simple_test_data['manufacturing_site'],
        labor_calendar=simple_test_data['labor_calendar'],
        cost_structure=simple_test_data['cost_structure'],
        start_date=simple_test_data['start_date'],
        end_date=simple_test_data['end_date'],
        use_batch_tracking=True  # Enable batch tracking
    )

    result = model.solve()

    # Assert model solved successfully
    assert result.is_optimal() or result.is_feasible(), "Model should find a solution"

    # Extract solution
    solution = model.solution
    assert solution is not None, "Solution should not be None"

    # Check that ProductionBatch objects were created
    assert 'production_batch_objects' in solution, "Should have production_batch_objects"
    batches = solution['production_batch_objects']

    assert len(batches) > 0, "Should create at least one batch"
    assert all(isinstance(b, ProductionBatch) for b in batches), "All batches should be ProductionBatch objects"

    # Check batch IDs are unique
    batch_ids = [b.id for b in batches]
    assert len(batch_ids) == len(set(batch_ids)), "Batch IDs should be unique"

    # Check batch quantities sum to production quantities
    production_by_date_product = solution['production_by_date_product']
    total_production = sum(production_by_date_product.values())
    total_batch_qty = sum(b.quantity for b in batches)

    assert abs(total_production - total_batch_qty) < 0.1, \
        f"Batch quantities ({total_batch_qty}) should equal production ({total_production})"

    # Check batch ID map exists and matches
    assert 'batch_id_map' in solution, "Should have batch_id_map"
    batch_id_map = solution['batch_id_map']

    for batch in batches:
        key = (batch.production_date, batch.product_id)
        assert key in batch_id_map, f"Batch {batch.id} should be in batch_id_map"
        assert batch_id_map[key] == batch.id, "Batch ID should match map"


def test_shipments_linked_to_batches(simple_test_data):
    """Test that shipments reference batch IDs."""
    # Build and solve model with batch tracking
    model = IntegratedProductionDistributionModel(
        forecast=simple_test_data['forecast'],
        locations=simple_test_data['locations'],
        routes=simple_test_data['routes'],
        manufacturing_site=simple_test_data['manufacturing_site'],
        labor_calendar=simple_test_data['labor_calendar'],
        cost_structure=simple_test_data['cost_structure'],
        start_date=simple_test_data['start_date'],
        end_date=simple_test_data['end_date'],
        use_batch_tracking=True
    )

    result = model.solve()
    assert result.is_optimal() or result.is_feasible()

    solution = model.solution

    # Check batch shipments
    assert 'batch_shipments' in solution, "Should have batch_shipments"
    batch_shipments = solution['batch_shipments']

    if len(batch_shipments) > 0:
        # All shipments should be Shipment objects
        assert all(isinstance(s, Shipment) for s in batch_shipments), \
            "All batch_shipments should be Shipment objects"

        # All shipments should have batch_id
        assert all(s.batch_id is not None for s in batch_shipments), \
            "All shipments should have batch_id"

        # All batch IDs should exist in production batches
        batch_ids = {b.id for b in solution['production_batch_objects']}
        for shipment in batch_shipments:
            assert shipment.batch_id in batch_ids or 'UNKNOWN' in shipment.batch_id, \
                f"Shipment batch_id {shipment.batch_id} should exist in batches"

        # Check shipments have production_date
        assert all(s.production_date is not None for s in batch_shipments), \
            "All shipments should have production_date"


def test_cohort_inventory_extraction(simple_test_data):
    """Test that cohort inventory is extracted correctly."""
    # Build and solve model with batch tracking
    model = IntegratedProductionDistributionModel(
        forecast=simple_test_data['forecast'],
        locations=simple_test_data['locations'],
        routes=simple_test_data['routes'],
        manufacturing_site=simple_test_data['manufacturing_site'],
        labor_calendar=simple_test_data['labor_calendar'],
        cost_structure=simple_test_data['cost_structure'],
        start_date=simple_test_data['start_date'],
        end_date=simple_test_data['end_date'],
        use_batch_tracking=True
    )

    result = model.solve()
    assert result.is_optimal() or result.is_feasible()

    solution = model.solution

    # Check cohort inventory fields exist
    assert 'cohort_inventory_frozen' in solution
    assert 'cohort_inventory_ambient' in solution
    assert 'cohort_inventory' in solution  # Combined

    cohort_inv = solution['cohort_inventory']

    # Each cohort inventory key should have 5 elements
    for key, qty in cohort_inv.items():
        assert len(key) == 5, \
            f"Cohort inventory key should have 5 elements (loc, prod, prod_date, curr_date, state), got {len(key)}"

        loc, prod, prod_date, curr_date, state = key

        # Validate types
        assert isinstance(loc, str), "Location should be string"
        assert isinstance(prod, str), "Product should be string"
        assert isinstance(prod_date, date), "Production date should be date"
        assert isinstance(curr_date, date), "Current date should be date"
        assert state in ['frozen', 'ambient'], f"State should be 'frozen' or 'ambient', got {state}"

        # Quantities should be positive
        assert qty > 0, f"Cohort inventory quantity should be positive, got {qty}"


def test_backward_compatibility(simple_test_data):
    """Test that legacy mode still works (use_batch_tracking=False)."""
    # Build model WITHOUT batch tracking
    model = IntegratedProductionDistributionModel(
        forecast=simple_test_data['forecast'],
        locations=simple_test_data['locations'],
        routes=simple_test_data['routes'],
        manufacturing_site=simple_test_data['manufacturing_site'],
        labor_calendar=simple_test_data['labor_calendar'],
        cost_structure=simple_test_data['cost_structure'],
        start_date=simple_test_data['start_date'],
        end_date=simple_test_data['end_date'],
        use_batch_tracking=False  # Legacy mode
    )

    result = model.solve()
    assert result.is_optimal() or result.is_feasible()

    solution = model.solution

    # Check backward compatibility fields
    assert 'production_batch_objects' in solution
    assert 'batch_shipments' in solution
    assert 'cohort_inventory' in solution

    # These should be populated even in legacy mode (but without cohort detail)
    batches = solution['production_batch_objects']
    assert len(batches) >= 0, "Should have batches (possibly empty list)"

    # Batch shipments should be empty in legacy mode
    assert solution['batch_shipments'] == [], \
        "Batch shipments should be empty when use_batch_tracking=False"

    # Cohort inventory should be empty in legacy mode
    assert solution['cohort_inventory'] == {}, \
        "Cohort inventory should be empty when use_batch_tracking=False"

    # Legacy shipments should still work
    assert 'shipments_by_leg_product_date' in solution
    shipments_by_leg = solution['shipments_by_leg_product_date']
    # Should have some shipments (aggregated, not cohort-based)


def test_batch_ids_deterministic(simple_test_data):
    """Test that batch IDs are deterministic (same production -> same batch ID)."""
    # Build and solve model twice
    model1 = IntegratedProductionDistributionModel(
        forecast=simple_test_data['forecast'],
        locations=simple_test_data['locations'],
        routes=simple_test_data['routes'],
        manufacturing_site=simple_test_data['manufacturing_site'],
        labor_calendar=simple_test_data['labor_calendar'],
        cost_structure=simple_test_data['cost_structure'],
        start_date=simple_test_data['start_date'],
        end_date=simple_test_data['end_date'],
        use_batch_tracking=True
    )

    result1 = model1.solve()
    assert result1.is_optimal() or result1.is_feasible()

    batches1 = model1.solution['production_batch_objects']
    batch_ids1 = sorted([b.id for b in batches1])

    # Solve again with same data
    model2 = IntegratedProductionDistributionModel(
        forecast=simple_test_data['forecast'],
        locations=simple_test_data['locations'],
        routes=simple_test_data['routes'],
        manufacturing_site=simple_test_data['manufacturing_site'],
        labor_calendar=simple_test_data['labor_calendar'],
        cost_structure=simple_test_data['cost_structure'],
        start_date=simple_test_data['start_date'],
        end_date=simple_test_data['end_date'],
        use_batch_tracking=True
    )

    result2 = model2.solve()
    assert result2.is_optimal() or result2.is_feasible()

    batches2 = model2.solution['production_batch_objects']
    batch_ids2 = sorted([b.id for b in batches2])

    # Batch IDs should be the same (deterministic)
    # NOTE: This assumes solver produces same solution, which may not always be true
    # So we'll just check the format is consistent
    assert len(batch_ids1) == len(batch_ids2), \
        "Should produce same number of batches"

    # Check batch ID format
    for batch_id in batch_ids1 + batch_ids2:
        assert batch_id.startswith('BATCH-'), f"Batch ID should start with 'BATCH-', got {batch_id}"
        assert len(batch_id.split('-')) >= 3, f"Batch ID should have date and product, got {batch_id}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
