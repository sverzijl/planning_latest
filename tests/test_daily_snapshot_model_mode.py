"""Test Daily Snapshot with Model Mode (cohort inventory extraction)."""

import pytest
from datetime import date, timedelta

from src.analysis.daily_snapshot import DailySnapshotGenerator
from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.models.location import Location, LocationType, StorageMode
from src.models.forecast import Forecast, ForecastEntry
from src.production.scheduler import ProductionSchedule


class MockRouteLeg:
    """Mock route leg for testing."""
    def __init__(self, from_location_id: str, to_location_id: str, transit_days: int):
        self.from_location_id = from_location_id
        self.to_location_id = to_location_id
        self.transit_days = transit_days


class MockRoute:
    """Mock route for testing."""
    def __init__(self, route_legs):
        self.route_legs = route_legs

    @property
    def total_transit_days(self) -> int:
        return sum(leg.transit_days for leg in self.route_legs)


def test_daily_snapshot_model_mode():
    """Test that model mode extracts inventory correctly from cohort data."""
    
    # Create test data
    start_date = date(2025, 10, 13)  # Monday
    
    # Locations
    locations = {
        "6122_Storage": Location(
            id="6122_Storage",
            name="Manufacturing Storage",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH,
            capacity=100000
        ),
        "6104": Location(
            id="6104",
            name="Hub NSW",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
            capacity=50000
        ),
    }
    
    # Production batches
    batches = [
        ProductionBatch(
            id="BATCH-001",
            product_id="PROD-A",
            quantity=1000.0,
            production_date=start_date,
            manufacturing_site_id="6122_Storage"
        )
    ]
    
    prod_schedule = ProductionSchedule(
        schedule_start_date=start_date,
        schedule_end_date=start_date + timedelta(days=7),
        manufacturing_site_id="6122_Storage",
        production_batches=batches,
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=1000.0,
        total_labor_hours=0.0
    )
    
    # Create shipments
    route = MockRoute([MockRouteLeg("6122_Storage", "6104", 1)])
    shipments = [
        Shipment(
            id="SHIP-001",
            batch_id="BATCH-001",
            product_id="PROD-A",
            quantity=600.0,
            origin_id="6122_Storage",
            destination_id="6104",
            delivery_date=start_date + timedelta(days=2),  # Day 3
            route=route,
            production_date=start_date
        )
    ]
    
    # Forecast with demand
    forecast = Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="6104",
                product_id="PROD-A",
                forecast_date=start_date + timedelta(days=3),  # Day 4
                quantity=200.0
            )
        ]
    )
    
    # Create MOCK model solution with cohort inventory
    # Simulate what the optimization model would return
    model_solution = {
        'use_batch_tracking': True,
        'production_batches': [
            {'date': start_date, 'product': 'PROD-A', 'quantity': 1000.0}
        ],
        # cohort_inventory format: (location, product, prod_date, curr_date, state) -> qty
        'cohort_inventory': {
            # Day 1: All at manufacturing (1000 units)
            ('6122_Storage', 'PROD-A', start_date, start_date, 'ambient'): 1000.0,
            
            # Day 2: Shipment in transit, 400 at manufacturing
            ('6122_Storage', 'PROD-A', start_date, start_date + timedelta(days=1), 'ambient'): 400.0,
            
            # Day 3: Shipment arrived at hub (600), still 400 at manufacturing
            ('6122_Storage', 'PROD-A', start_date, start_date + timedelta(days=2), 'ambient'): 400.0,
            ('6104', 'PROD-A', start_date, start_date + timedelta(days=2), 'ambient'): 600.0,
            
            # Day 4: Demand consumed 200 from hub (model already did this!)
            ('6122_Storage', 'PROD-A', start_date, start_date + timedelta(days=3), 'ambient'): 400.0,
            ('6104', 'PROD-A', start_date, start_date + timedelta(days=3), 'ambient'): 400.0,  # 600 - 200
        }
    }
    
    # Create generator WITH model solution (MODEL MODE)
    generator_model = DailySnapshotGenerator(
        production_schedule=prod_schedule,
        shipments=shipments,
        locations_dict=locations,
        forecast=forecast,
        model_solution=model_solution,  # MODEL MODE enabled
        verbose=False
    )
    
    # Create generator WITHOUT model solution (LEGACY MODE)
    generator_legacy = DailySnapshotGenerator(
        production_schedule=prod_schedule,
        shipments=shipments,
        locations_dict=locations,
        forecast=forecast,
        model_solution=None,  # LEGACY MODE
        verbose=False
    )
    
    print(f"\n=== Mode Detection ===")
    print(f"MODEL generator use_model_inventory: {generator_model.use_model_inventory}")
    print(f"LEGACY generator use_model_inventory: {generator_legacy.use_model_inventory}")
    
    # Test Day 1: Production
    snapshot_model = generator_model.generate_snapshots(start_date, start_date)[0]
    snapshot_legacy = generator_legacy.generate_snapshots(start_date, start_date)[0]
    
    print("\n===== DAY 1: Production (Both Modes) =====")
    print(f"MODEL MODE:  {snapshot_model.location_inventory['6122_Storage'].total_quantity:.0f} units at 6122_Storage")
    print(f"LEGACY MODE: {snapshot_legacy.location_inventory['6122_Storage'].total_quantity:.0f} units at 6122_Storage")
    
    assert snapshot_model.location_inventory['6122_Storage'].total_quantity == 1000.0, "Model mode Day 1 failed"
    assert snapshot_legacy.location_inventory['6122_Storage'].total_quantity == 1000.0, "Legacy mode Day 1 failed"
    
    # Test Day 3: After shipment arrival
    day3 = start_date + timedelta(days=2)
    snapshot_model = generator_model.generate_snapshots(day3, day3)[0]
    snapshot_legacy = generator_legacy.generate_snapshots(day3, day3)[0]
    
    print("\n===== DAY 3: After Shipment Arrival =====")
    print(f"MODEL MODE:  6122_Storage={snapshot_model.location_inventory['6122_Storage'].total_quantity:.0f}, "
          f"6104={snapshot_model.location_inventory['6104'].total_quantity:.0f}")
    print(f"LEGACY MODE: 6122_Storage={snapshot_legacy.location_inventory['6122_Storage'].total_quantity:.0f}, "
          f"6104={snapshot_legacy.location_inventory['6104'].total_quantity:.0f}")
    
    assert snapshot_model.location_inventory['6122_Storage'].total_quantity == 400.0, "Model mode Day 3 6122 failed"
    assert snapshot_model.location_inventory['6104'].total_quantity == 600.0, "Model mode Day 3 6104 failed"
    assert snapshot_legacy.location_inventory['6122_Storage'].total_quantity == 400.0, "Legacy mode Day 3 6122 failed"
    assert snapshot_legacy.location_inventory['6104'].total_quantity == 600.0, "Legacy mode Day 3 6104 failed"
    
    # Test Day 4: After demand consumption
    # NOTE: Model mode uses cohort inventory which is ALREADY AFTER demand consumption
    # Legacy mode manually consumes demand using FIFO
    day4 = start_date + timedelta(days=3)
    snapshot_model = generator_model.generate_snapshots(day4, day4)[0]
    snapshot_legacy = generator_legacy.generate_snapshots(day4, day4)[0]
    
    print("\n===== DAY 4: After Demand Consumption =====")
    print(f"MODEL MODE:  6122_Storage={snapshot_model.location_inventory['6122_Storage'].total_quantity:.0f}, "
          f"6104={snapshot_model.location_inventory['6104'].total_quantity:.0f}")
    print(f"LEGACY MODE: 6122_Storage={snapshot_legacy.location_inventory['6122_Storage'].total_quantity:.0f}, "
          f"6104={snapshot_legacy.location_inventory['6104'].total_quantity:.0f}")
    
    # Model mode: demand already consumed in cohort_inventory (400 units at hub after 200 consumed)
    assert snapshot_model.location_inventory['6122_Storage'].total_quantity == 400.0, "Model mode Day 4 6122 failed"
    assert snapshot_model.location_inventory['6104'].total_quantity == 400.0, "Model mode Day 4 6104 failed (demand)"
    
    # Legacy mode: manually consumes demand using FIFO (600 - 200 = 400)
    assert snapshot_legacy.location_inventory['6122_Storage'].total_quantity == 400.0, "Legacy mode Day 4 6122 failed"
    assert snapshot_legacy.location_inventory['6104'].total_quantity == 400.0, "Legacy mode Day 4 6104 failed (demand)"
    
    print("\n✓✓✓ MODEL MODE and LEGACY MODE produce identical results ✓✓✓")
    print("\nThis confirms:")
    print("  ✓ Model mode extracts inventory from cohort_inventory correctly")
    print("  ✓ Model mode uses inventory AFTER demand consumption (from model)")
    print("  ✓ Legacy mode reconstructs inventory from shipments correctly")
    print("  ✓ Legacy mode manually consumes demand using FIFO")
    print("  ✓ Both modes produce consistent results")


if __name__ == "__main__":
    test_daily_snapshot_model_mode()
    print("\n✅ All model mode tests PASSED")
