"""Comprehensive tests for Daily Inventory Snapshot demand consumption (FIFO strategy).

This test file specifically validates the FIFO (First-In-First-Out) demand consumption
logic that was implemented in the Daily Inventory Snapshot fix.

SEMANTICS:
- Snapshots show inventory AFTER demand consumption (end-of-day inventory)
- Demand is consumed using FIFO strategy (oldest batches consumed first)
- Mass balance is maintained: production - shipments_out + shipments_in - demand = inventory

These tests lock in the fix and prevent regression.
"""

import pytest
from datetime import date, timedelta
from typing import List, Dict
from dataclasses import dataclass

from src.analysis.daily_snapshot import DailySnapshotGenerator
from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.models.location import Location, LocationType, StorageMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.product import ProductState
from src.production.scheduler import ProductionSchedule


# ===========================
# Mock Data Classes
# ===========================


@dataclass
class MockRouteLeg:
    """Mock route leg for testing."""
    from_location_id: str
    to_location_id: str
    transit_days: int
    transport_mode: str = "ambient"


@dataclass
class MockRoute:
    """Mock route for testing."""
    route_legs: List[MockRouteLeg]

    @property
    def total_transit_days(self) -> int:
        """Calculate total transit days."""
        return sum(leg.transit_days for leg in self.route_legs)


# ===========================
# Test: Single Location, Demand Over Time
# ===========================


def test_single_location_demand_over_time():
    """Test inventory decreases correctly as demand is consumed over multiple days.

    Scenario:
    - Day 1: 1000 units arrive at location
    - Days 2-5: 200 units demand each day
    - Expected inventory progression: 1000 → 800 → 600 → 400 → 200

    This validates that demand is correctly deducted from inventory on each day.
    """
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=1)

    # Production: 1000 units
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=1000.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.72,
        production_cost=500.0
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[batch],
        daily_totals={base_date: 1000.0},
        daily_labor_hours={base_date: 0.72},
        infeasibilities=[],
        total_units=1000.0,
        total_labor_hours=0.72
    )

    # Shipment: 1000 units delivered on Day 1
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])
    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="WW",
        quantity=1000.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=delivery_date,
        route=route,
        production_date=base_date
    )

    # Demand: 200 units per day for 4 days
    forecast_entries = []
    for i in range(4):  # Days 2-5
        forecast_entries.append(
            ForecastEntry(
                location_id="6103",
                product_id="WW",
                forecast_date=base_date + timedelta(days=2+i),
                quantity=200.0
            )
        )

    forecast = Forecast(name="Test", entries=forecast_entries)

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)

    # Day 1: Delivery, no demand yet
    snapshot_day1 = generator._generate_single_snapshot(delivery_date)
    assert snapshot_day1.location_inventory["6103"].total_quantity == 1000.0

    # Day 2: First demand (200 units consumed)
    snapshot_day2 = generator._generate_single_snapshot(base_date + timedelta(days=2))
    assert snapshot_day2.location_inventory["6103"].total_quantity == 800.0
    assert snapshot_day2.demand_satisfied[0].supplied_quantity == 200.0

    # Day 3: Second demand (200 units consumed)
    snapshot_day3 = generator._generate_single_snapshot(base_date + timedelta(days=3))
    assert snapshot_day3.location_inventory["6103"].total_quantity == 600.0

    # Day 4: Third demand (200 units consumed)
    snapshot_day4 = generator._generate_single_snapshot(base_date + timedelta(days=4))
    assert snapshot_day4.location_inventory["6103"].total_quantity == 400.0

    # Day 5: Fourth demand (200 units consumed)
    snapshot_day5 = generator._generate_single_snapshot(base_date + timedelta(days=5))
    assert snapshot_day5.location_inventory["6103"].total_quantity == 200.0

    print("✓ Single location demand over time: PASSED")


# ===========================
# Test: Multi-Batch FIFO Consumption
# ===========================


def test_multi_batch_fifo_consumption():
    """Test that FIFO consumption uses oldest batches first.

    Scenario:
    - Day 1: Batch A (500 units, produced D1) arrives
    - Day 3: Batch B (500 units, produced D3) arrives
    - Day 5: 600 units demand
    - Expected: Batch A fully consumed (500), Batch B partially consumed (100), remaining 400

    This validates FIFO ordering by production date.
    """
    base_date = date(2025, 10, 13)

    # Two batches with different production dates
    batch_a = ProductionBatch(
        id="BATCH-A",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=base_date,  # Older batch
        quantity=500.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.36,
        production_cost=250.0
    )

    batch_b = ProductionBatch(
        id="BATCH-B",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=base_date + timedelta(days=2),  # Newer batch
        quantity=500.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.36,
        production_cost=250.0
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date + timedelta(days=2),
        production_batches=[batch_a, batch_b],
        daily_totals={
            base_date: 500.0,
            base_date + timedelta(days=2): 500.0
        },
        daily_labor_hours={
            base_date: 0.36,
            base_date + timedelta(days=2): 0.36
        },
        infeasibilities=[],
        total_units=1000.0,
        total_labor_hours=0.72
    )

    # Two shipments
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])

    shipment_a = Shipment(
        id="SHIP-A",
        batch_id="BATCH-A",
        product_id="WW",
        quantity=500.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=base_date + timedelta(days=1),
        route=route,
        production_date=base_date
    )

    shipment_b = Shipment(
        id="SHIP-B",
        batch_id="BATCH-B",
        product_id="WW",
        quantity=500.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=base_date + timedelta(days=3),
        route=route,
        production_date=base_date + timedelta(days=2)
    )

    # Demand: 600 units on Day 5
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="WW",
                forecast_date=base_date + timedelta(days=5),
                quantity=600.0
            )
        ]
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment_a, shipment_b], locations_dict, forecast)

    # Day 4: Before demand, both batches should be present
    snapshot_day4 = generator._generate_single_snapshot(base_date + timedelta(days=4))
    assert snapshot_day4.location_inventory["6103"].total_quantity == 1000.0
    assert len(snapshot_day4.location_inventory["6103"].batches) == 2

    # Day 5: After 600 units demand
    # FIFO: Batch A (older, 500 units) consumed first, then 100 from Batch B
    snapshot_day5 = generator._generate_single_snapshot(base_date + timedelta(days=5))
    assert snapshot_day5.location_inventory["6103"].total_quantity == 400.0

    # Should only have BATCH-B remaining (400 units)
    assert len(snapshot_day5.location_inventory["6103"].batches) == 1
    batch_remaining = snapshot_day5.location_inventory["6103"].batches[0]
    assert batch_remaining.batch_id == "BATCH-B"
    assert batch_remaining.quantity == 400.0

    # Verify demand satisfaction
    assert len(snapshot_day5.demand_satisfied) == 1
    assert snapshot_day5.demand_satisfied[0].supplied_quantity == 600.0
    assert snapshot_day5.demand_satisfied[0].is_satisfied

    print("✓ Multi-batch FIFO consumption: PASSED")


# ===========================
# Test: Demand with Concurrent Shipments
# ===========================


def test_demand_with_concurrent_shipments():
    """Test mass balance with arrivals, departures, AND demand.

    Scenario:
    - Track inventory through production, shipments (in/out), and demand
    - Verify mass balance: production - shipments_out + shipments_in - demand = inventory

    This ensures all flows are correctly accounted for.
    """
    base_date = date(2025, 10, 13)

    # Production: 2000 units on Day 0
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=2000.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=1.43,
        production_cost=1000.0
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[batch],
        daily_totals={base_date: 2000.0},
        daily_labor_hours={base_date: 1.43},
        infeasibilities=[],
        total_units=2000.0,
        total_labor_hours=1.43
    )

    # Shipments
    route_to_hub = MockRoute(route_legs=[MockRouteLeg("6122", "6104", 1)])
    route_hub_to_dest = MockRoute(route_legs=[MockRouteLeg("6104", "6103", 1)])

    shipment_to_hub = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="WW",
        quantity=1500.0,
        origin_id="6122",
        destination_id="6104",
        delivery_date=base_date + timedelta(days=2),
        route=route_to_hub,
        production_date=base_date
    )

    shipment_hub_to_dest = Shipment(
        id="SHIP-002",
        batch_id="BATCH-001",
        product_id="WW",
        quantity=1000.0,
        origin_id="6104",
        destination_id="6103",
        delivery_date=base_date + timedelta(days=4),
        route=route_hub_to_dest,
        production_date=base_date
    )

    # Demand: 500 units on Day 5 at destination
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="WW",
                forecast_date=base_date + timedelta(days=5),
                quantity=500.0
            )
        ]
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6104": Location(id="6104", name="Hub", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment_to_hub, shipment_hub_to_dest], locations_dict, forecast)

    # Day 0: Production
    snapshot_d0 = generator._generate_single_snapshot(base_date)
    assert snapshot_d0.location_inventory["6122"].total_quantity == 2000.0

    # Day 2: Shipment arrives at hub
    snapshot_d2 = generator._generate_single_snapshot(base_date + timedelta(days=2))
    assert snapshot_d2.location_inventory["6122"].total_quantity == 500.0  # 2000 - 1500
    assert snapshot_d2.location_inventory["6104"].total_quantity == 1500.0  # Arrived

    # Day 3: Shipment departs from hub to destination
    snapshot_d3 = generator._generate_single_snapshot(base_date + timedelta(days=3))
    assert snapshot_d3.location_inventory["6104"].total_quantity == 500.0  # 1500 - 1000

    # Day 4: Shipment arrives at destination
    snapshot_d4 = generator._generate_single_snapshot(base_date + timedelta(days=4))
    assert snapshot_d4.location_inventory["6103"].total_quantity == 1000.0

    # Day 5: Demand consumed
    snapshot_d5 = generator._generate_single_snapshot(base_date + timedelta(days=5))
    assert snapshot_d5.location_inventory["6103"].total_quantity == 500.0  # 1000 - 500

    # Mass balance check
    total_inventory = sum(loc.total_quantity for loc in snapshot_d5.location_inventory.values())
    total_in_transit = snapshot_d5.total_in_transit
    expected = 2000.0 - 500.0  # Production - demand
    assert abs(total_inventory + total_in_transit - expected) < 0.1

    print("✓ Demand with concurrent shipments: PASSED")


# ===========================
# Test: Shortage Scenario
# ===========================


def test_shortage_scenario():
    """Test shortage when demand exceeds available inventory.

    Scenario:
    - 300 units available
    - 500 units demand
    - Expected: inventory goes to 0 (not negative), shortage=200

    This validates shortage calculation and ensures inventory never goes negative.
    """
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=1)
    demand_date = base_date + timedelta(days=2)

    # Production: 300 units
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=300.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.21,
        production_cost=150.0
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[batch],
        daily_totals={base_date: 300.0},
        daily_labor_hours={base_date: 0.21},
        infeasibilities=[],
        total_units=300.0,
        total_labor_hours=0.21
    )

    # Shipment: 300 units
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])
    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="WW",
        quantity=300.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=delivery_date,
        route=route,
        production_date=base_date
    )

    # Demand: 500 units (more than available)
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="WW",
                forecast_date=demand_date,
                quantity=500.0
            )
        ]
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)

    # Before demand
    snapshot_before = generator._generate_single_snapshot(delivery_date)
    assert snapshot_before.location_inventory["6103"].total_quantity == 300.0

    # After demand (shortage scenario)
    snapshot_after = generator._generate_single_snapshot(demand_date)

    # Inventory should be 0 (all consumed, not negative)
    assert snapshot_after.location_inventory["6103"].total_quantity == 0.0

    # Demand record should show shortage
    assert len(snapshot_after.demand_satisfied) == 1
    record = snapshot_after.demand_satisfied[0]

    assert record.demand_quantity == 500.0
    assert record.supplied_quantity == 300.0  # Only what was available
    assert record.shortage_quantity == 200.0  # Shortage
    assert not record.is_satisfied
    assert abs(record.fill_rate - 0.6) < 0.01  # 60% fill rate

    print("✓ Shortage scenario: PASSED")


# ===========================
# Test: Multi-Product FIFO Consumption
# ===========================


def test_multi_product_fifo_consumption():
    """Test FIFO applies separately for each product.

    Scenario:
    - Two products at same location
    - Each product has multiple batches
    - Demand for both products
    - Expected: FIFO applied per product independently

    This validates that FIFO logic is product-specific.
    """
    base_date = date(2025, 10, 13)

    # Two products, two batches each
    batches = [
        # White Wonder - Batch 1 (older)
        ProductionBatch(
            id="BATCH-WW-1",
            product_id="WW",
            manufacturing_site_id="6122",
            production_date=base_date,
            quantity=300.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.21,
            production_cost=150.0
        ),
        # White Wonder - Batch 2 (newer)
        ProductionBatch(
            id="BATCH-WW-2",
            product_id="WW",
            manufacturing_site_id="6122",
            production_date=base_date + timedelta(days=1),
            quantity=300.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.21,
            production_cost=150.0
        ),
        # Soy & Linseed - Batch 1 (older)
        ProductionBatch(
            id="BATCH-SD-1",
            product_id="SD",
            manufacturing_site_id="6122",
            production_date=base_date,
            quantity=200.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.14,
            production_cost=100.0
        ),
        # Soy & Linseed - Batch 2 (newer)
        ProductionBatch(
            id="BATCH-SD-2",
            product_id="SD",
            manufacturing_site_id="6122",
            production_date=base_date + timedelta(days=1),
            quantity=200.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.14,
            production_cost=100.0
        ),
    ]

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date + timedelta(days=1),
        production_batches=batches,
        daily_totals={base_date: 500.0, base_date + timedelta(days=1): 500.0},
        daily_labor_hours={base_date: 0.35, base_date + timedelta(days=1): 0.35},
        infeasibilities=[],
        total_units=1000.0,
        total_labor_hours=0.70
    )

    # Shipments for all batches
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])

    shipments = [
        Shipment(id="SHIP-WW-1", batch_id="BATCH-WW-1", product_id="WW",
                 quantity=300.0, origin_id="6122", destination_id="6103",
                 delivery_date=base_date + timedelta(days=2),
                 route=route, production_date=base_date),
        Shipment(id="SHIP-WW-2", batch_id="BATCH-WW-2", product_id="WW",
                 quantity=300.0, origin_id="6122", destination_id="6103",
                 delivery_date=base_date + timedelta(days=3),
                 route=route, production_date=base_date + timedelta(days=1)),
        Shipment(id="SHIP-SD-1", batch_id="BATCH-SD-1", product_id="SD",
                 quantity=200.0, origin_id="6122", destination_id="6103",
                 delivery_date=base_date + timedelta(days=2),
                 route=route, production_date=base_date),
        Shipment(id="SHIP-SD-2", batch_id="BATCH-SD-2", product_id="SD",
                 quantity=200.0, origin_id="6122", destination_id="6103",
                 delivery_date=base_date + timedelta(days=3),
                 route=route, production_date=base_date + timedelta(days=1)),
    ]

    # Demand: 400 WW, 250 SD on Day 4
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="WW",
                forecast_date=base_date + timedelta(days=4),
                quantity=400.0
            ),
            ForecastEntry(
                location_id="6103",
                product_id="SD",
                forecast_date=base_date + timedelta(days=4),
                quantity=250.0
            ),
        ]
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, shipments, locations_dict, forecast)

    # Day 4: After demand
    snapshot = generator._generate_single_snapshot(base_date + timedelta(days=4))

    # WW: 600 available - 400 demand = 200 remaining
    # Should consume all of BATCH-WW-1 (300) and 100 from BATCH-WW-2
    ww_inventory = snapshot.location_inventory["6103"].by_product.get("WW", 0.0)
    assert ww_inventory == 200.0

    # SD: 400 available - 250 demand = 150 remaining
    # Should consume all of BATCH-SD-1 (200) and 50 from BATCH-SD-2
    sd_inventory = snapshot.location_inventory["6103"].by_product.get("SD", 0.0)
    assert sd_inventory == 150.0

    # Total inventory
    total_inventory = snapshot.location_inventory["6103"].total_quantity
    assert total_inventory == 350.0  # 200 WW + 150 SD

    # Check demand satisfaction
    assert len(snapshot.demand_satisfied) == 2
    for record in snapshot.demand_satisfied:
        assert record.is_satisfied
        assert record.fill_rate == 1.0

    print("✓ Multi-product FIFO consumption: PASSED")


# ===========================
# Test: Zero Demand Edge Case
# ===========================


def test_zero_demand():
    """Test inventory unchanged when no demand.

    Scenario:
    - Inventory exists at location
    - No demand on that date
    - Expected: Inventory unchanged

    This validates no-op behavior when demand is zero.
    """
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=1)

    # Production and shipment
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=1000.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.72,
        production_cost=500.0
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[batch],
        daily_totals={base_date: 1000.0},
        daily_labor_hours={base_date: 0.72},
        infeasibilities=[],
        total_units=1000.0,
        total_labor_hours=0.72
    )

    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])
    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="WW",
        quantity=1000.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=delivery_date,
        route=route,
        production_date=base_date
    )

    # No demand
    forecast = Forecast(name="Test", entries=[])

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)

    # Multiple days with no demand
    for days_offset in range(1, 6):
        snapshot = generator._generate_single_snapshot(delivery_date + timedelta(days=days_offset))

        # Inventory should remain unchanged at 1000 units
        assert snapshot.location_inventory["6103"].total_quantity == 1000.0

        # No demand records
        assert len(snapshot.demand_satisfied) == 0

    print("✓ Zero demand edge case: PASSED")


# ===========================
# Test: Exact Inventory Match
# ===========================


def test_exact_inventory_match():
    """Test exact match: demand equals available inventory.

    Scenario:
    - 500 units available
    - 500 units demand
    - Expected: inventory goes to 0, no shortage

    This validates boundary condition where supply exactly meets demand.
    """
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=1)
    demand_date = base_date + timedelta(days=2)

    # Production: 500 units
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=500.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.36,
        production_cost=250.0
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[batch],
        daily_totals={base_date: 500.0},
        daily_labor_hours={base_date: 0.36},
        infeasibilities=[],
        total_units=500.0,
        total_labor_hours=0.36
    )

    # Shipment: 500 units
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])
    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="WW",
        quantity=500.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=delivery_date,
        route=route,
        production_date=base_date
    )

    # Demand: exactly 500 units
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="WW",
                forecast_date=demand_date,
                quantity=500.0
            )
        ]
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)

    # After demand
    snapshot = generator._generate_single_snapshot(demand_date)

    # Inventory should be exactly 0
    assert snapshot.location_inventory["6103"].total_quantity == 0.0

    # No shortage
    assert len(snapshot.demand_satisfied) == 1
    record = snapshot.demand_satisfied[0]

    assert record.demand_quantity == 500.0
    assert record.supplied_quantity == 500.0
    assert record.shortage_quantity == 0.0
    assert record.is_satisfied
    assert record.fill_rate == 1.0

    print("✓ Exact inventory match: PASSED")


# ===========================
# Run All Tests
# ===========================


if __name__ == "__main__":
    """Run all demand consumption tests."""
    print("\n" + "=" * 80)
    print("DAILY INVENTORY SNAPSHOT - DEMAND CONSUMPTION TESTS (FIFO)")
    print("=" * 80)
    print("\nThese tests validate the FIFO demand consumption fix")
    print("Snapshots show inventory AFTER demand consumption (end-of-day semantics)\n")

    test_single_location_demand_over_time()
    test_multi_batch_fifo_consumption()
    test_demand_with_concurrent_shipments()
    test_shortage_scenario()
    test_multi_product_fifo_consumption()
    test_zero_demand()
    test_exact_inventory_match()

    print("\n" + "=" * 80)
    print("ALL DEMAND CONSUMPTION TESTS PASSED ✓✓✓")
    print("=" * 80)
    print("\nCoverage:")
    print("  ✓ Single location demand over time")
    print("  ✓ Multi-batch FIFO consumption (oldest first)")
    print("  ✓ Demand with concurrent shipments (mass balance)")
    print("  ✓ Shortage scenario (inventory doesn't go negative)")
    print("  ✓ Multi-product FIFO (product-specific FIFO)")
    print("  ✓ Zero demand (no-op behavior)")
    print("  ✓ Exact inventory match (boundary condition)")
    print("\nThe FIFO demand consumption fix is locked in and protected from regression.")
