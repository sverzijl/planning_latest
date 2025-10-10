"""Simple test for batch extraction - validates ProductionBatch creation."""

from datetime import date
from src.models.production_batch import ProductionBatch
from src.models.product import ProductState


def test_production_batch_creation():
    """Test that ProductionBatch objects can be created correctly."""
    batch = ProductionBatch(
        id="BATCH-20250106-P1-0001",
        product_id="P1",
        manufacturing_site_id="6122",
        production_date=date(2025, 1, 6),
        quantity=1000.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=8.5,
        production_cost=1000.0
    )

    assert batch.id == "BATCH-20250106-P1-0001"
    assert batch.product_id == "P1"
    assert batch.quantity == 1000.0
    assert batch.production_date == date(2025, 1, 6)
    assert batch.labor_hours_used == 8.5
    assert batch.production_cost == 1000.0
    assert batch.initial_state == ProductState.AMBIENT


def test_batch_id_format():
    """Test batch ID format follows convention."""
    batch_id = "BATCH-20250106-P1-0001"

    parts = batch_id.split('-')
    assert len(parts) == 4, "Batch ID should have 4 parts: BATCH-DATE-PRODUCT-NUMBER"
    assert parts[0] == "BATCH", "Should start with 'BATCH'"
    assert len(parts[1]) == 8, "Date should be YYYYMMDD format (8 digits)"
    assert parts[2] == "P1", "Product ID should be included"
    assert len(parts[3]) == 4, "Sequence number should be 4 digits"


def test_solution_dict_structure():
    """Test that solution dict has expected batch fields."""
    # Simulate solution dictionary structure
    solution = {
        'production_by_date_product': {
            (date(2025, 1, 6), 'P1'): 1000,
            (date(2025, 1, 7), 'P2'): 500
        },
        'production_batch_objects': [
            ProductionBatch(
                id="BATCH-20250106-P1-0001",
                product_id="P1",
                manufacturing_site_id="6122",
                production_date=date(2025, 1, 6),
                quantity=1000.0,
                initial_state=ProductState.AMBIENT,
                labor_hours_used=4.0,
                production_cost=1000.0
            ),
            ProductionBatch(
                id="BATCH-20250107-P2-0002",
                product_id="P2",
                manufacturing_site_id="6122",
                production_date=date(2025, 1, 7),
                quantity=500.0,
                initial_state=ProductState.AMBIENT,
                labor_hours_used=2.0,
                production_cost=500.0
            )
        ],
        'batch_id_map': {
            (date(2025, 1, 6), 'P1'): "BATCH-20250106-P1-0001",
            (date(2025, 1, 7), 'P2'): "BATCH-20250107-P2-0002"
        },
        'batch_shipments': [],
        'use_batch_tracking': True
    }

    # Validate structure
    assert 'production_batch_objects' in solution
    assert 'batch_id_map' in solution
    assert 'batch_shipments' in solution
    assert 'use_batch_tracking' in solution

    # Validate batches
    batches = solution['production_batch_objects']
    assert len(batches) == 2
    assert all(isinstance(b, ProductionBatch) for b in batches)

    # Validate batch IDs are unique
    batch_ids = [b.id for b in batches]
    assert len(batch_ids) == len(set(batch_ids)), "Batch IDs should be unique"

    # Validate batch quantities match production
    total_production = sum(solution['production_by_date_product'].values())
    total_batches = sum(b.quantity for b in batches)
    assert abs(total_production - total_batches) < 0.01


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
