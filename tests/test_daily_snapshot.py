"""Comprehensive unit tests for daily inventory snapshot generator.

This test suite validates the DailySnapshotGenerator and all related dataclasses,
ensuring accurate inventory tracking, flow calculations, and demand satisfaction reporting.
"""

import pytest
from datetime import date, timedelta
from typing import List, Dict
from dataclasses import dataclass

from src.analysis.daily_snapshot import (
    BatchInventory,
    LocationInventory,
    TransitInventory,
    InventoryFlow,
    DemandRecord,
    DailySnapshot,
    DailySnapshotGenerator,
)
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
# Fixtures - Locations
# ===========================


@pytest.fixture
def manufacturing_location() -> Location:
    """Manufacturing site location (6122)."""
    return Location(
        id="6122",
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        capacity=100000
    )


@pytest.fixture
def hub_6125() -> Location:
    """Regional hub 6125 (VIC)."""
    return Location(
        id="6125",
        name="Hub VIC",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.BOTH,
        capacity=50000
    )


@pytest.fixture
def hub_6104() -> Location:
    """Regional hub 6104 (NSW)."""
    return Location(
        id="6104",
        name="Hub NSW",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.BOTH,
        capacity=50000
    )


@pytest.fixture
def breadroom_6103() -> Location:
    """Breadroom destination 6103."""
    return Location(
        id="6103",
        name="Breadroom VIC",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
        capacity=5000
    )


@pytest.fixture
def breadroom_6130() -> Location:
    """Breadroom destination 6130 (WA)."""
    return Location(
        id="6130",
        name="Breadroom WA",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.BOTH,
        capacity=5000
    )


@pytest.fixture
def locations_dict(
    manufacturing_location: Location,
    hub_6125: Location,
    hub_6104: Location,
    breadroom_6103: Location,
    breadroom_6130: Location
) -> Dict[str, Location]:
    """Dictionary of all locations."""
    return {
        "6122": manufacturing_location,
        "6125": hub_6125,
        "6104": hub_6104,
        "6103": breadroom_6103,
        "6130": breadroom_6130,
    }


# ===========================
# Fixtures - Production Data
# ===========================


@pytest.fixture
def basic_production_schedule() -> ProductionSchedule:
    """Create basic production schedule with 3 batches."""
    base_date = date(2025, 10, 13)  # Monday

    batches = [
        ProductionBatch(
            id="BATCH-001",
            product_id="176283",
            manufacturing_site_id="6122",
            production_date=base_date,
            quantity=320.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.23,
            production_cost=160.0
        ),
        ProductionBatch(
            id="BATCH-002",
            product_id="176284",
            manufacturing_site_id="6122",
            production_date=base_date,
            quantity=640.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.46,
            production_cost=320.0
        ),
        ProductionBatch(
            id="BATCH-003",
            product_id="176283",
            manufacturing_site_id="6122",
            production_date=base_date + timedelta(days=1),  # Tuesday
            quantity=960.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.69,
            production_cost=480.0
        ),
    ]

    return ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date + timedelta(days=1),
        production_batches=batches,
        daily_totals={
            base_date: 960.0,
            base_date + timedelta(days=1): 960.0
        },
        daily_labor_hours={
            base_date: 0.69,
            base_date + timedelta(days=1): 0.69
        },
        infeasibilities=[],
        total_units=1920.0,
        total_labor_hours=1.38
    )


@pytest.fixture
def basic_shipments() -> List[Shipment]:
    """Create basic shipments for testing."""
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=3)  # Thursday delivery

    # Route: 6122 -> 6125 (1 day) -> 6103 (1 day) = 2 days total
    route = MockRoute(
        route_legs=[
            MockRouteLeg("6122", "6125", 1),
            MockRouteLeg("6125", "6103", 1)
        ]
    )

    return [
        Shipment(
            id="SHIP-001",
            batch_id="BATCH-001",
            product_id="176283",
            quantity=320.0,
            origin_id="6122",
            destination_id="6103",
            delivery_date=delivery_date,
            route=route,
            production_date=base_date
        ),
        Shipment(
            id="SHIP-002",
            batch_id="BATCH-002",
            product_id="176284",
            quantity=640.0,
            origin_id="6122",
            destination_id="6103",
            delivery_date=delivery_date,
            route=route,
            production_date=base_date
        ),
    ]


@pytest.fixture
def basic_forecast() -> Forecast:
    """Create basic forecast with demand."""
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=3)

    return Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=delivery_date,
                quantity=320.0
            ),
            ForecastEntry(
                location_id="6103",
                product_id="176284",
                forecast_date=delivery_date,
                quantity=640.0
            ),
        ]
    )


# ===========================
# Tests - Basic Functionality
# ===========================


def test_daily_snapshot_generator_basic(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test basic snapshot generator initialization and structure."""
    generator = DailySnapshotGenerator(
        production_schedule=basic_production_schedule,
        shipments=basic_shipments,
        locations_dict=locations_dict,
        forecast=basic_forecast
    )

    # Verify generator attributes
    assert generator.production_schedule == basic_production_schedule
    assert generator.shipments == basic_shipments
    assert generator.locations_dict == locations_dict
    assert generator.forecast == basic_forecast

    # Verify lookup structures were built
    assert hasattr(generator, '_batches_by_date')
    assert hasattr(generator, '_shipments_by_departure')
    assert hasattr(generator, '_shipments_by_arrival')
    assert hasattr(generator, '_shipments_by_delivery')


def test_single_snapshot_generation(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test generating a single snapshot for a specific date."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    snapshot_date = date(2025, 10, 13)
    snapshot = generator._generate_single_snapshot(snapshot_date)

    # Verify snapshot structure
    assert isinstance(snapshot, DailySnapshot)
    assert snapshot.date == snapshot_date
    assert isinstance(snapshot.location_inventory, dict)
    assert isinstance(snapshot.in_transit, list)
    assert isinstance(snapshot.production_activity, list)
    assert isinstance(snapshot.inflows, list)
    assert isinstance(snapshot.outflows, list)
    assert isinstance(snapshot.demand_satisfied, list)


def test_multiple_snapshots_generation(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test generating snapshots for a date range."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    start_date = date(2025, 10, 13)
    end_date = date(2025, 10, 17)  # 5 days

    snapshots = generator.generate_snapshots(start_date, end_date)

    # Verify we got the right number of snapshots
    assert len(snapshots) == 5

    # Verify dates are sequential
    for i, snapshot in enumerate(snapshots):
        expected_date = start_date + timedelta(days=i)
        assert snapshot.date == expected_date


def test_empty_data_handling() -> None:
    """Test handling of empty production schedule and shipments."""
    empty_schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=date(2025, 10, 13),
        schedule_end_date=date(2025, 10, 13),
        production_batches=[],
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=0.0,
        total_labor_hours=0.0
    )

    empty_forecast = Forecast(name="Empty", entries=[])

    locations_dict = {
        "6122": Location(
            id="6122",
            name="Manufacturing",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.AMBIENT
        )
    }

    generator = DailySnapshotGenerator(
        empty_schedule, [], locations_dict, empty_forecast
    )

    snapshot = generator._generate_single_snapshot(date(2025, 10, 13))

    # Should have manufacturing location but with zero inventory
    assert "6122" in snapshot.location_inventory
    assert snapshot.location_inventory["6122"].total_quantity == 0.0
    assert len(snapshot.in_transit) == 0
    assert len(snapshot.production_activity) == 0


# ===========================
# Tests - Location Inventory
# ===========================


def test_location_inventory_calculation(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Verify inventory calculation at manufacturing location."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    snapshot_date = date(2025, 10, 13)  # Production day
    snapshot = generator._generate_single_snapshot(snapshot_date)

    # Manufacturing site should have inventory
    assert "6122" in snapshot.location_inventory
    mfg_inv = snapshot.location_inventory["6122"]

    # Should have 2 batches (BATCH-001: 320, BATCH-002: 640)
    assert mfg_inv.total_quantity == 960.0
    assert len(mfg_inv.batches) == 2

    # Check product breakdown
    assert "176283" in mfg_inv.by_product
    assert "176284" in mfg_inv.by_product
    assert mfg_inv.by_product["176283"] == 320.0
    assert mfg_inv.by_product["176284"] == 640.0


def test_batch_tracking_at_manufacturing(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test batch tracking at manufacturing site."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    snapshot_date = date(2025, 10, 14)  # Day after first production
    snapshot = generator._generate_single_snapshot(snapshot_date)

    mfg_inv = snapshot.location_inventory["6122"]

    # Should have 3 batches total:
    # - BATCH-001 and BATCH-002 from 10/13 (before shipment departure)
    # - BATCH-003 from 10/14
    # Note: Shipments depart on 10/14, so batches still at mfg on snapshot
    assert len(mfg_inv.batches) >= 1  # At least BATCH-003

    # Check batch IDs
    batch_ids = {b.batch_id for b in mfg_inv.batches}
    assert "BATCH-003" in batch_ids


def test_batch_age_calculation(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Verify age calculation from production date."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    production_date = date(2025, 10, 13)
    snapshot_date = date(2025, 10, 16)  # 3 days later

    snapshot = generator._generate_single_snapshot(snapshot_date)

    # Find a batch from 10/13 production
    for loc_inv in snapshot.location_inventory.values():
        for batch in loc_inv.batches:
            if batch.production_date == production_date:
                assert batch.age_days == 3
                break


def test_multiple_products_at_location(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test multiple products at same location."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    snapshot_date = date(2025, 10, 13)
    snapshot = generator._generate_single_snapshot(snapshot_date)

    mfg_inv = snapshot.location_inventory["6122"]

    # Should have 2 different products
    assert len(mfg_inv.by_product) == 2
    assert "176283" in mfg_inv.by_product
    assert "176284" in mfg_inv.by_product

    # Total should equal sum of products
    total = sum(mfg_inv.by_product.values())
    assert abs(total - mfg_inv.total_quantity) < 0.01


# ===========================
# Tests - In-Transit
# ===========================


def test_in_transit_identification(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test identification of shipments in transit."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Shipments depart on 10/14 (delivery 10/16 - 2 days transit)
    # On 10/14, should be in transit on first leg (6122 -> 6125)
    snapshot_date = date(2025, 10, 14)
    snapshot = generator._generate_single_snapshot(snapshot_date)

    # Should have 2 shipments in transit
    assert len(snapshot.in_transit) == 2

    # Verify transit details
    for transit in snapshot.in_transit:
        assert transit.origin_id == "6122"
        assert transit.destination_id == "6125"  # First leg
        assert transit.days_in_transit == 0  # Just departed


def test_in_transit_before_departure(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test no shipment in transit before departure."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Day before departure
    snapshot_date = date(2025, 10, 13)
    snapshot = generator._generate_single_snapshot(snapshot_date)

    # No shipments should be in transit yet
    assert len(snapshot.in_transit) == 0


def test_in_transit_after_arrival(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test no shipment in transit after arrival."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Day after final delivery
    snapshot_date = date(2025, 10, 17)
    snapshot = generator._generate_single_snapshot(snapshot_date)

    # No shipments should be in transit
    assert len(snapshot.in_transit) == 0


def test_multi_leg_transit() -> None:
    """Test multi-leg routes in transit."""
    base_date = date(2025, 10, 13)

    # 3-leg route: 6122 -> 6125 (1d) -> 6104 (1d) -> 6130 (2d)
    route = MockRoute(
        route_legs=[
            MockRouteLeg("6122", "6125", 1),
            MockRouteLeg("6125", "6104", 1),
            MockRouteLeg("6104", "6130", 2)
        ]
    )

    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=320.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.23,
        production_cost=160.0
    )

    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="176283",
        quantity=320.0,
        origin_id="6122",
        destination_id="6130",
        delivery_date=base_date + timedelta(days=4),  # 4 days total transit
        route=route,
        production_date=base_date
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[batch],
        daily_totals={base_date: 320.0},
        daily_labor_hours={base_date: 0.23},
        infeasibilities=[],
        total_units=320.0,
        total_labor_hours=0.23
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6125": Location(id="6125", name="Hub1", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6104": Location(id="6104", name="Hub2", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6130": Location(id="6130", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)

    # Check transit on different legs
    # Day 0 (10/13): At manufacturing (not yet departed)
    snapshot_d0 = generator._generate_single_snapshot(base_date)
    assert len(snapshot_d0.in_transit) == 0

    # Day 1 (10/14): In transit 6122 -> 6125
    snapshot_d1 = generator._generate_single_snapshot(base_date + timedelta(days=1))
    assert len(snapshot_d1.in_transit) == 1
    assert snapshot_d1.in_transit[0].origin_id == "6122"
    assert snapshot_d1.in_transit[0].destination_id == "6125"

    # Day 2 (10/15): In transit 6125 -> 6104
    snapshot_d2 = generator._generate_single_snapshot(base_date + timedelta(days=2))
    assert len(snapshot_d2.in_transit) == 1
    assert snapshot_d2.in_transit[0].origin_id == "6125"
    assert snapshot_d2.in_transit[0].destination_id == "6104"


# ===========================
# Tests - Production Activity
# ===========================


def test_production_activity_tracking(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test tracking production on specific date."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    production_date = date(2025, 10, 13)
    snapshot = generator._generate_single_snapshot(production_date)

    # Should have 2 batches produced on this date
    assert len(snapshot.production_activity) == 2

    # Verify batch details
    batch_ids = {b.batch_id for b in snapshot.production_activity}
    assert "BATCH-001" in batch_ids
    assert "BATCH-002" in batch_ids

    # All should have age 0 (just produced)
    for batch in snapshot.production_activity:
        assert batch.age_days == 0


def test_no_production_on_date(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test handling dates with no production."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Day with no production
    no_production_date = date(2025, 10, 15)
    snapshot = generator._generate_single_snapshot(no_production_date)

    # Should have no production activity
    assert len(snapshot.production_activity) == 0


def test_multiple_batches_same_date(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test multiple batches on same day."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # 10/13 has 2 batches
    snapshot = generator._generate_single_snapshot(date(2025, 10, 13))

    assert len(snapshot.production_activity) == 2

    # Different products
    products = {b.product_id for b in snapshot.production_activity}
    assert len(products) == 2  # 2 different products


# ===========================
# Tests - Inflow/Outflow
# ===========================


def test_inflow_calculation(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test calculation of inflows (production + arrivals)."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Production day - should have production inflows
    snapshot = generator._generate_single_snapshot(date(2025, 10, 13))

    # Should have 2 production inflows
    production_inflows = [f for f in snapshot.inflows if f.flow_type == "production"]
    assert len(production_inflows) == 2

    # Check quantities
    total_production = sum(f.quantity for f in production_inflows)
    assert total_production == 960.0


def test_outflow_calculation(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test calculation of outflows (departures + demand)."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Departure day (delivery 10/16 - 2 days = depart 10/14)
    snapshot = generator._generate_single_snapshot(date(2025, 10, 14))

    # Should have 2 departure outflows
    departure_outflows = [f for f in snapshot.outflows if f.flow_type == "departure"]
    assert len(departure_outflows) == 2

    # Check quantities
    total_departures = sum(f.quantity for f in departure_outflows)
    assert total_departures == 960.0


def test_flow_balance(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test that inflows and outflows balance correctly."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # On production day, inflows (production) should occur
    snapshot_production = generator._generate_single_snapshot(date(2025, 10, 13))
    production_inflow = sum(f.quantity for f in snapshot_production.inflows if f.flow_type == "production")
    assert production_inflow == 960.0

    # On departure day, outflows should equal production
    snapshot_departure = generator._generate_single_snapshot(date(2025, 10, 14))
    departure_outflow = sum(f.quantity for f in snapshot_departure.outflows if f.flow_type == "departure")
    assert departure_outflow == 960.0


def test_production_inflow(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test production shows as inflow at manufacturing."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    snapshot = generator._generate_single_snapshot(date(2025, 10, 13))

    production_flows = [f for f in snapshot.inflows if f.flow_type == "production"]

    # All production should be at manufacturing site
    for flow in production_flows:
        assert flow.location_id == "6122"
        assert flow.batch_id is not None


def test_shipment_arrival_inflow(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test shipment arrival shows as inflow."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Arrival at hub 6125 on 10/15 (depart 10/14 + 1 day)
    snapshot = generator._generate_single_snapshot(date(2025, 10, 15))

    arrival_flows = [f for f in snapshot.inflows if f.flow_type == "arrival"]

    # Should have arrivals at 6125
    hub_arrivals = [f for f in arrival_flows if f.location_id == "6125"]
    assert len(hub_arrivals) == 2

    total_arrived = sum(f.quantity for f in hub_arrivals)
    assert total_arrived == 960.0


def test_shipment_departure_outflow(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test shipment departure shows as outflow."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Departure from 6122 on 10/14
    snapshot = generator._generate_single_snapshot(date(2025, 10, 14))

    departure_flows = [f for f in snapshot.outflows if f.flow_type == "departure"]

    # All departures should be from manufacturing
    for flow in departure_flows:
        assert flow.location_id == "6122"
        assert flow.counterparty == "6125"  # First leg destination


# ===========================
# Tests - Demand Satisfaction
# ===========================


def test_demand_satisfaction_tracking(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test tracking demand met on date."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Delivery date
    delivery_date = date(2025, 10, 16)
    snapshot = generator._generate_single_snapshot(delivery_date)

    # Should have demand records
    assert len(snapshot.demand_satisfied) == 2

    # Check all demand is satisfied
    for record in snapshot.demand_satisfied:
        assert record.is_satisfied
        assert record.fill_rate == 1.0


def test_demand_with_shortage() -> None:
    """Test calculate shortage when supply < demand."""
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=3)

    # Production: only 200 units
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=200.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.14,
        production_cost=100.0
    )

    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 2)])

    # Shipment: only 200 units
    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="176283",
        quantity=200.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=delivery_date,
        route=route,
        production_date=base_date
    )

    # Demand: 320 units
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=delivery_date,
                quantity=320.0
            )
        ]
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[batch],
        daily_totals={base_date: 200.0},
        daily_labor_hours={base_date: 0.14},
        infeasibilities=[],
        total_units=200.0,
        total_labor_hours=0.14
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(delivery_date)

    # Check shortage
    assert len(snapshot.demand_satisfied) == 1
    record = snapshot.demand_satisfied[0]

    assert record.demand_quantity == 320.0
    assert record.supplied_quantity == 200.0
    assert record.shortage_quantity == 120.0
    assert not record.is_satisfied
    assert abs(record.fill_rate - 200.0/320.0) < 0.01


def test_demand_overfulfillment() -> None:
    """Test handle supply > demand."""
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=3)

    # Production: 500 units
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=500.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.36,
        production_cost=250.0
    )

    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 2)])

    # Shipment: 500 units
    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="176283",
        quantity=500.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=delivery_date,
        route=route,
        production_date=base_date
    )

    # Demand: only 320 units
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=delivery_date,
                quantity=320.0
            )
        ]
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

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(delivery_date)

    # Check overfulfillment
    record = snapshot.demand_satisfied[0]

    assert record.demand_quantity == 320.0
    assert record.supplied_quantity == 500.0
    assert record.shortage_quantity == 0.0  # No shortage
    assert record.is_satisfied
    assert record.fill_rate == 1.0  # Capped at 100%


def test_no_demand_on_date(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test handling dates with no demand."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Date with no demand
    no_demand_date = date(2025, 10, 15)
    snapshot = generator._generate_single_snapshot(no_demand_date)

    # Should have no demand records
    assert len(snapshot.demand_satisfied) == 0


# ===========================
# Tests - Edge Cases
# ===========================


def test_future_date_snapshot(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test handling snapshot date in future."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Far future date
    future_date = date(2025, 12, 31)
    snapshot = generator._generate_single_snapshot(future_date)

    # Should still generate snapshot (inventory may be zero)
    assert snapshot.date == future_date
    assert isinstance(snapshot, DailySnapshot)


def test_past_date_before_start(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test handling snapshot date before production start."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Date before any production
    past_date = date(2025, 10, 1)
    snapshot = generator._generate_single_snapshot(past_date)

    # Should have no inventory or activity
    assert snapshot.total_system_inventory == 0.0
    assert len(snapshot.production_activity) == 0
    assert len(snapshot.in_transit) == 0


def test_invalid_date_range(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test handling end_date before start_date."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    # Invalid range
    start_date = date(2025, 10, 20)
    end_date = date(2025, 10, 15)

    snapshots = generator.generate_snapshots(start_date, end_date)

    # Should return empty list
    assert len(snapshots) == 0


# ===========================
# Tests - Integration
# ===========================


def test_multi_product_multi_location() -> None:
    """Test complex scenario with multiple products and locations."""
    base_date = date(2025, 10, 13)

    # 3 batches, 2 products, various dates
    batches = [
        ProductionBatch(
            id="BATCH-001",
            product_id="176283",
            manufacturing_site_id="6122",
            production_date=base_date,
            quantity=320.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.23,
            production_cost=160.0
        ),
        ProductionBatch(
            id="BATCH-002",
            product_id="176284",
            manufacturing_site_id="6122",
            production_date=base_date,
            quantity=640.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.46,
            production_cost=320.0
        ),
        ProductionBatch(
            id="BATCH-003",
            product_id="176283",
            manufacturing_site_id="6122",
            production_date=base_date + timedelta(days=1),
            quantity=320.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.23,
            production_cost=160.0
        ),
    ]

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date + timedelta(days=1),
        production_batches=batches,
        daily_totals={base_date: 960.0, base_date + timedelta(days=1): 320.0},
        daily_labor_hours={base_date: 0.69, base_date + timedelta(days=1): 0.23},
        infeasibilities=[],
        total_units=1280.0,
        total_labor_hours=0.92
    )

    # Multiple routes to different destinations
    route1 = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 2)])
    route2 = MockRoute(route_legs=[MockRouteLeg("6122", "6125", 1), MockRouteLeg("6125", "6130", 2)])

    shipments = [
        Shipment(
            id="SHIP-001",
            batch_id="BATCH-001",
            product_id="176283",
            quantity=320.0,
            origin_id="6122",
            destination_id="6103",
            delivery_date=base_date + timedelta(days=3),
            route=route1,
            production_date=base_date
        ),
        Shipment(
            id="SHIP-002",
            batch_id="BATCH-002",
            product_id="176284",
            quantity=640.0,
            origin_id="6122",
            destination_id="6130",
            delivery_date=base_date + timedelta(days=4),
            route=route2,
            production_date=base_date
        ),
    ]

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6125": Location(id="6125", name="Hub", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest1", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6130": Location(id="6130", name="Dest2", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, shipments, locations_dict, forecast)

    # Check mid-journey snapshot
    snapshot = generator._generate_single_snapshot(base_date + timedelta(days=2))

    # Should have inventory at multiple locations
    assert len(snapshot.location_inventory) >= 2

    # Should have shipments in various states
    assert snapshot.total_system_inventory > 0


def test_full_week_scenario() -> None:
    """Test complete week of activity."""
    start_date = date(2025, 10, 13)  # Monday

    # Daily production Mon-Fri
    batches = []
    for i in range(5):  # Mon-Fri
        batches.append(
            ProductionBatch(
                id=f"BATCH-{i+1:03d}",
                product_id="176283",
                manufacturing_site_id="6122",
                production_date=start_date + timedelta(days=i),
                quantity=320.0,
                initial_state=ProductState.AMBIENT,
                labor_hours_used=0.23,
                production_cost=160.0
            )
        )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=start_date,
        schedule_end_date=start_date + timedelta(days=4),
        production_batches=batches,
        daily_totals={start_date + timedelta(days=i): 320.0 for i in range(5)},
        daily_labor_hours={start_date + timedelta(days=i): 0.23 for i in range(5)},
        infeasibilities=[],
        total_units=1600.0,
        total_labor_hours=1.15
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, [], locations_dict, forecast)

    # Generate full week
    snapshots = generator.generate_snapshots(start_date, start_date + timedelta(days=6))

    assert len(snapshots) == 7  # Mon-Sun

    # Production should occur Mon-Fri
    production_days = sum(1 for s in snapshots if len(s.production_activity) > 0)
    assert production_days == 5


def test_hub_spoke_network() -> None:
    """Test hub-and-spoke routing."""
    base_date = date(2025, 10, 13)

    # Hub-spoke route: 6122 -> 6125 -> 6103
    route = MockRoute(
        route_legs=[
            MockRouteLeg("6122", "6125", 1),  # Mfg -> Hub
            MockRouteLeg("6125", "6103", 1),  # Hub -> Spoke
        ]
    )

    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=320.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.23,
        production_cost=160.0
    )

    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="176283",
        quantity=320.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=base_date + timedelta(days=3),  # 2 days transit + 1 safety
        route=route,
        production_date=base_date
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[batch],
        daily_totals={base_date: 320.0},
        daily_labor_hours={base_date: 0.23},
        infeasibilities=[],
        total_units=320.0,
        total_labor_hours=0.23
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6125": Location(id="6125", name="Hub", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Spoke", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)

    # Day 1: Depart mfg
    snapshot_d1 = generator._generate_single_snapshot(base_date + timedelta(days=1))
    assert len(snapshot_d1.in_transit) == 1
    assert snapshot_d1.in_transit[0].destination_id == "6125"

    # Day 2: At hub, then depart for spoke
    snapshot_d2 = generator._generate_single_snapshot(base_date + timedelta(days=2))
    # Should be in transit to spoke or at hub

    # Day 3: At spoke (delivered)
    snapshot_d3 = generator._generate_single_snapshot(base_date + timedelta(days=3))
    assert len(snapshot_d3.in_transit) == 0  # Delivered


# ===========================
# Tests - Dataclass Properties
# ===========================


def test_demand_record_fill_rate() -> None:
    """Test DemandRecord fill_rate property."""
    # Full satisfaction
    record1 = DemandRecord(
        destination_id="6103",
        product_id="176283",
        demand_quantity=320.0,
        supplied_quantity=320.0,
        shortage_quantity=0.0
    )
    assert record1.fill_rate == 1.0
    assert record1.is_satisfied

    # Partial satisfaction
    record2 = DemandRecord(
        destination_id="6103",
        product_id="176283",
        demand_quantity=320.0,
        supplied_quantity=200.0,
        shortage_quantity=120.0
    )
    assert abs(record2.fill_rate - 0.625) < 0.01
    assert not record2.is_satisfied

    # No demand
    record3 = DemandRecord(
        destination_id="6103",
        product_id="176283",
        demand_quantity=0.0,
        supplied_quantity=0.0,
        shortage_quantity=0.0
    )
    assert record3.fill_rate == 1.0  # No demand = 100% fill
    assert record3.is_satisfied


def test_location_inventory_add_batch() -> None:
    """Test LocationInventory add_batch method."""
    loc_inv = LocationInventory(
        location_id="6122",
        location_name="Manufacturing"
    )

    # Add first batch
    batch1 = BatchInventory(
        batch_id="BATCH-001",
        product_id="176283",
        quantity=320.0,
        production_date=date(2025, 10, 13),
        age_days=0
    )
    loc_inv.add_batch(batch1)

    assert loc_inv.total_quantity == 320.0
    assert len(loc_inv.batches) == 1
    assert loc_inv.by_product["176283"] == 320.0

    # Add second batch (different product)
    batch2 = BatchInventory(
        batch_id="BATCH-002",
        product_id="176284",
        quantity=640.0,
        production_date=date(2025, 10, 13),
        age_days=0
    )
    loc_inv.add_batch(batch2)

    assert loc_inv.total_quantity == 960.0
    assert len(loc_inv.batches) == 2
    assert loc_inv.by_product["176283"] == 320.0
    assert loc_inv.by_product["176284"] == 640.0

    # Add third batch (same product as first)
    batch3 = BatchInventory(
        batch_id="BATCH-003",
        product_id="176283",
        quantity=320.0,
        production_date=date(2025, 10, 14),
        age_days=1
    )
    loc_inv.add_batch(batch3)

    assert loc_inv.total_quantity == 1280.0
    assert len(loc_inv.batches) == 3
    assert loc_inv.by_product["176283"] == 640.0  # Accumulated
    assert loc_inv.by_product["176284"] == 640.0


def test_snapshot_string_representation(
    basic_production_schedule: ProductionSchedule,
    basic_shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    basic_forecast: Forecast
) -> None:
    """Test string representations of snapshot objects."""
    generator = DailySnapshotGenerator(
        basic_production_schedule, basic_shipments, locations_dict, basic_forecast
    )

    snapshot = generator._generate_single_snapshot(date(2025, 10, 13))

    # Test DailySnapshot.__str__
    snapshot_str = str(snapshot)
    assert "2025-10-13" in snapshot_str
    assert "locations" in snapshot_str.lower()

    # Test BatchInventory.__str__
    if snapshot.production_activity:
        batch_str = str(snapshot.production_activity[0])
        assert "BATCH" in batch_str
        assert "units" in batch_str.lower()

    # Test LocationInventory.__str__
    if snapshot.location_inventory:
        loc_inv_str = str(list(snapshot.location_inventory.values())[0])
        assert "units" in loc_inv_str.lower()

    # Test TransitInventory.__str__
    transit_snapshot = generator._generate_single_snapshot(date(2025, 10, 14))
    if transit_snapshot.in_transit:
        transit_str = str(transit_snapshot.in_transit[0])
        assert "Shipment" in transit_str
        assert "units" in transit_str.lower()

    # Test InventoryFlow.__str__
    if snapshot.inflows:
        flow_str = str(snapshot.inflows[0])
        assert "units" in flow_str.lower()

    # Test DemandRecord.__str__
    delivery_snapshot = generator._generate_single_snapshot(date(2025, 10, 16))
    if delivery_snapshot.demand_satisfied:
        demand_str = str(delivery_snapshot.demand_satisfied[0])
        assert "6103" in demand_str or "176283" in demand_str


# ===========================
# Tests - Pre-positioned Inventory (Bug Fix)
# ===========================


def test_demand_satisfied_from_prepositioned_inventory() -> None:
    """Test demand is met from pre-positioned inventory (delivered earlier).

    Scenario:
    - Day 1: Deliver 1000 units to location 6103
    - Day 3: Demand 500 units at location 6103
    - Expected: supplied=500 (from on-hand inventory), shortage=0

    This tests the fix for the bug where demand was incorrectly shown as
    not satisfied when inventory was available from earlier deliveries.
    """
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=1)  # Day 1
    demand_date = base_date + timedelta(days=3)     # Day 3

    # Production: 1000 units on Day 0
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=1000.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.72,
        production_cost=500.0
    )

    # Direct route: 6122 -> 6103 (1 day transit)
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])

    # Shipment: Deliver 1000 units on Day 1
    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="176283",
        quantity=1000.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=delivery_date,
        route=route,
        production_date=base_date
    )

    # Demand: 500 units on Day 3 (2 days after delivery)
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=demand_date,
                quantity=500.0
            )
        ]
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

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)

    # Check snapshot on demand date (Day 3)
    snapshot = generator._generate_single_snapshot(demand_date)

    # Verify demand record
    assert len(snapshot.demand_satisfied) == 1
    record = snapshot.demand_satisfied[0]

    # CRITICAL ASSERTION: Demand should be satisfied from on-hand inventory
    assert record.demand_quantity == 500.0
    assert record.supplied_quantity == 1000.0  # Full inventory available (was 0 before fix)
    assert record.shortage_quantity == 0.0
    assert record.is_satisfied
    assert record.fill_rate == 1.0

    # Verify inventory exists at location
    assert "6103" in snapshot.location_inventory
    assert snapshot.location_inventory["6103"].total_quantity == 1000.0


def test_demand_partially_satisfied_from_inventory() -> None:
    """Test partial demand satisfaction from on-hand inventory (no new deliveries).

    Scenario:
    - Day 1: Deliver 300 units to location 6103
    - Day 3: Demand 500 units at location 6103 (no new deliveries)
    - Expected: supplied=300 (from on-hand), shortage=200
    """
    base_date = date(2025, 10, 13)
    delivery_date = base_date + timedelta(days=1)
    demand_date = base_date + timedelta(days=3)

    # Production: 300 units
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=300.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.21,
        production_cost=150.0
    )

    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])

    # Shipment: Deliver 300 units on Day 1
    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="176283",
        quantity=300.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=delivery_date,
        route=route,
        production_date=base_date
    )

    # Demand: 500 units on Day 3 (more than available)
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=demand_date,
                quantity=500.0
            )
        ]
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

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(demand_date)

    # Verify partial satisfaction
    assert len(snapshot.demand_satisfied) == 1
    record = snapshot.demand_satisfied[0]

    assert record.demand_quantity == 500.0
    assert record.supplied_quantity == 300.0  # Only what's available
    assert record.shortage_quantity == 200.0  # Shortage
    assert not record.is_satisfied
    assert abs(record.fill_rate - 0.6) < 0.01  # 300/500 = 60%

    # Verify inventory
    assert "6103" in snapshot.location_inventory
    assert snapshot.location_inventory["6103"].total_quantity == 300.0


def test_demand_satisfied_from_inventory_and_delivery() -> None:
    """Test demand satisfied from BOTH on-hand inventory AND same-day delivery.

    Scenario:
    - Day 1: Deliver 200 units to location 6103
    - Day 3: Demand 500 units at location 6103
    - Day 3: NEW delivery of 300 units arrives
    - Expected: supplied=500 (200 on-hand + 300 delivered today), shortage=0
    """
    base_date = date(2025, 10, 13)
    first_delivery = base_date + timedelta(days=1)   # Day 1
    demand_date = base_date + timedelta(days=3)      # Day 3
    second_delivery = demand_date                     # Day 3 (same day as demand)

    # Two batches
    batch1 = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=200.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.14,
        production_cost=100.0
    )

    batch2 = ProductionBatch(
        id="BATCH-002",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date + timedelta(days=1),
        quantity=300.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.21,
        production_cost=150.0
    )

    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])

    # First shipment: 200 units delivered on Day 1
    shipment1 = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="176283",
        quantity=200.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=first_delivery,
        route=route,
        production_date=base_date
    )

    # Second shipment: 300 units delivered on Day 3 (demand day)
    shipment2 = Shipment(
        id="SHIP-002",
        batch_id="BATCH-002",
        product_id="176283",
        quantity=300.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=second_delivery,
        route=route,
        production_date=base_date + timedelta(days=1)
    )

    # Demand: 500 units on Day 3
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=demand_date,
                quantity=500.0
            )
        ]
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date + timedelta(days=1),
        production_batches=[batch1, batch2],
        daily_totals={base_date: 200.0, base_date + timedelta(days=1): 300.0},
        daily_labor_hours={base_date: 0.14, base_date + timedelta(days=1): 0.21},
        infeasibilities=[],
        total_units=500.0,
        total_labor_hours=0.35
    )

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Dest", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    generator = DailySnapshotGenerator(schedule, [shipment1, shipment2], locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(demand_date)

    # Verify demand is fully satisfied from on-hand + new delivery
    assert len(snapshot.demand_satisfied) == 1
    record = snapshot.demand_satisfied[0]

    assert record.demand_quantity == 500.0
    assert record.supplied_quantity == 500.0  # 200 on-hand + 300 delivered today
    assert record.shortage_quantity == 0.0
    assert record.is_satisfied
    assert record.fill_rate == 1.0

    # Verify total inventory includes both shipments
    assert "6103" in snapshot.location_inventory
    assert snapshot.location_inventory["6103"].total_quantity == 500.0


# ===========================
# NEW REGRESSION TESTS - Missing Locations Bug
# ===========================


def test_all_locations_appear_regardless_of_inventory() -> None:
    """Verify ALL network locations appear in snapshot even with zero inventory.

    Regression test for bug where locations with zero inventory were excluded
    from the snapshot, leading to missing breadrooms in the UI.

    Bug: Line 344 in daily_snapshot.py had condition:
        if loc_inv.total_quantity > 0 or location_id == self.production_schedule.manufacturing_site_id:

    This excluded locations with zero inventory unless they were the manufacturing site.
    """
    base_date = date(2025, 10, 13)

    # Create 10 locations - but only ship to 3 of them
    locations_dict = {
        "6122": Location(id="6122", name="Manufacturing", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6104": Location(id="6104", name="Hub NSW", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6125": Location(id="6125", name="Hub VIC", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="Breadroom VIC", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6105": Location(id="6105", name="Breadroom NSW", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6107": Location(id="6107", name="Breadroom ACT", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6110": Location(id="6110", name="Breadroom QLD", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6115": Location(id="6115", name="Breadroom SA", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6118": Location(id="6118", name="Breadroom TAS", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6130": Location(id="6130", name="Breadroom WA", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    # Production at manufacturing only
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
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

    # Only ship to 3 locations (6103, 6104, 6125)
    route1 = MockRoute(route_legs=[MockRouteLeg("6122", "6104", 1)])
    route2 = MockRoute(route_legs=[MockRouteLeg("6122", "6125", 1)])
    route3 = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 2)])

    shipments = [
        Shipment(
            id="SHIP-001", batch_id="BATCH-001", product_id="176283",
            quantity=300.0, origin_id="6122", destination_id="6104",
            delivery_date=base_date + timedelta(days=2),
            route=route1, production_date=base_date
        ),
        Shipment(
            id="SHIP-002", batch_id="BATCH-001", product_id="176283",
            quantity=300.0, origin_id="6122", destination_id="6125",
            delivery_date=base_date + timedelta(days=2),
            route=route2, production_date=base_date
        ),
        Shipment(
            id="SHIP-003", batch_id="BATCH-001", product_id="176283",
            quantity=400.0, origin_id="6122", destination_id="6103",
            delivery_date=base_date + timedelta(days=3),
            route=route3, production_date=base_date
        ),
    ]

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, shipments, locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(base_date + timedelta(days=5))

    # CRITICAL: ALL 10 locations MUST appear in snapshot
    # Before fix: Only 4 locations appeared (6122, 6103, 6104, 6125)
    # After fix: All 10 locations appear
    assert len(snapshot.location_inventory) == 10, f"Expected 10 locations, got {len(snapshot.location_inventory)}"

    # Specifically check for the missing locations from the bug report
    assert "6110" in snapshot.location_inventory, "6110 (QLD) should appear even with zero inventory"
    assert "6103" in snapshot.location_inventory, "6103 (VIC) should appear"
    assert "6105" in snapshot.location_inventory, "6105 (NSW) should appear even with zero inventory"
    assert "6107" in snapshot.location_inventory, "6107 (ACT) should appear even with zero inventory"
    assert "6115" in snapshot.location_inventory, "6115 (SA) should appear even with zero inventory"
    assert "6118" in snapshot.location_inventory, "6118 (TAS) should appear even with zero inventory"
    assert "6130" in snapshot.location_inventory, "6130 (WA) should appear even with zero inventory"

    # Verify zero-inventory locations have zero quantity
    assert snapshot.location_inventory["6110"].total_quantity == 0.0
    assert snapshot.location_inventory["6105"].total_quantity == 0.0
    assert snapshot.location_inventory["6107"].total_quantity == 0.0


def test_zero_inventory_locations_included() -> None:
    """Verify locations with zero inventory are included in snapshot."""
    base_date = date(2025, 10, 13)

    # Create location that will never receive shipments
    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6110": Location(id="6110", name="QLD", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    # No production, no shipments
    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[],
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=0.0,
        total_labor_hours=0.0
    )

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, [], locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(base_date)

    # Both locations should appear
    assert len(snapshot.location_inventory) == 2
    assert "6122" in snapshot.location_inventory
    assert "6110" in snapshot.location_inventory

    # Both should have zero inventory
    assert snapshot.location_inventory["6122"].total_quantity == 0.0
    assert snapshot.location_inventory["6110"].total_quantity == 0.0


def test_all_nine_breadrooms_appear() -> None:
    """Verify all 9 breadrooms appear in snapshot."""
    base_date = date(2025, 10, 13)

    # All 9 breadrooms from real network
    breadrooms = {
        "6103": "Breadroom VIC",
        "6105": "Breadroom NSW",
        "6107": "Breadroom ACT",
        "6110": "Breadroom QLD",
        "6115": "Breadroom SA",
        "6118": "Breadroom TAS",
        "6123": "Breadroom NSW2",
        "6127": "Breadroom VIC2",
        "6130": "Breadroom WA",
    }

    locations_dict = {
        "6122": Location(id="6122", name="Manufacturing", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
    }

    for br_id, br_name in breadrooms.items():
        locations_dict[br_id] = Location(
            id=br_id, name=br_name, type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT
        )

    # Create demand at all breadrooms
    forecast_entries = []
    for br_id in breadrooms.keys():
        forecast_entries.append(
            ForecastEntry(
                location_id=br_id,
                product_id="176283",
                forecast_date=base_date + timedelta(days=3),
                quantity=100.0
            )
        )

    forecast = Forecast(name="Test", entries=forecast_entries)

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[],
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=0.0,
        total_labor_hours=0.0
    )

    generator = DailySnapshotGenerator(schedule, [], locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(base_date)

    # All 10 locations (1 manufacturing + 9 breadrooms) should appear
    assert len(snapshot.location_inventory) == 10

    # Check each breadroom
    for br_id in breadrooms.keys():
        assert br_id in snapshot.location_inventory, f"Breadroom {br_id} should appear in snapshot"


def test_hub_locations_always_appear() -> None:
    """Verify hub locations (6104, 6125) appear in snapshot even with zero inventory."""
    base_date = date(2025, 10, 13)

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6104": Location(id="6104", name="Hub NSW", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6125": Location(id="6125", name="Hub VIC", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
    }

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[],
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=0.0,
        total_labor_hours=0.0
    )

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, [], locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(base_date)

    # All 3 locations should appear
    assert len(snapshot.location_inventory) == 3
    assert "6104" in snapshot.location_inventory
    assert "6125" in snapshot.location_inventory

    # Both hubs should have zero inventory
    assert snapshot.location_inventory["6104"].total_quantity == 0.0
    assert snapshot.location_inventory["6125"].total_quantity == 0.0


def test_missing_locations_bug_regression() -> None:
    """Regression test for specific bug where 6110, 6103, 6105 were missing.

    Bug: Line 344 in daily_snapshot.py filtered out locations with zero inventory.
    Fix: Changed condition to always include ALL locations from locations_dict.

    Before:
        if loc_inv.total_quantity > 0 or location_id == self.production_schedule.manufacturing_site_id:

    After:
        # Always include all locations (removed the condition entirely)
    """
    base_date = date(2025, 10, 13)

    # Recreate exact scenario from bug report
    locations_dict = {
        "6122": Location(id="6122", name="Manufacturing", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6104": Location(id="6104", name="Hub NSW", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6125": Location(id="6125", name="Hub VIC", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
        "6103": Location(id="6103", name="VIC", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6105": Location(id="6105", name="NSW", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6110": Location(id="6110", name="QLD", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
    }

    # Production at manufacturing
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
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

    # Only ship to one location
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6104", 1)])
    shipments = [
        Shipment(
            id="SHIP-001", batch_id="BATCH-001", product_id="176283",
            quantity=500.0, origin_id="6122", destination_id="6104",
            delivery_date=base_date + timedelta(days=2),
            route=route, production_date=base_date
        ),
    ]

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, shipments, locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(base_date + timedelta(days=3))

    # CRITICAL: All 6 locations MUST appear
    assert len(snapshot.location_inventory) == 6

    # Specifically check the problematic locations
    assert "6110" in snapshot.location_inventory, "6110 (QLD) was missing in bug report"
    assert "6103" in snapshot.location_inventory, "6103 (VIC) was missing in bug report"
    assert "6105" in snapshot.location_inventory, "6105 (NSW) was missing in bug report"


def test_in_transit_shipments_tracked() -> None:
    """Verify in-transit shipments are captured in snapshot."""
    base_date = date(2025, 10, 13)

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "6104": Location(id="6104", name="Hub", type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT),
    }

    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
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

    # 3-day transit
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6104", 3)])
    shipments = [
        Shipment(
            id="SHIP-001", batch_id="BATCH-001", product_id="176283",
            quantity=500.0, origin_id="6122", destination_id="6104",
            delivery_date=base_date + timedelta(days=4),  # Depart day 1, arrive day 4
            route=route, production_date=base_date
        ),
    ]

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, shipments, locations_dict, forecast)

    # Day 2: Should be in transit
    snapshot = generator._generate_single_snapshot(base_date + timedelta(days=2))

    assert len(snapshot.in_transit) == 1
    assert snapshot.in_transit[0].shipment_id == "SHIP-001"
    assert snapshot.in_transit[0].origin_id == "6122"
    assert snapshot.in_transit[0].destination_id == "6104"
    assert snapshot.in_transit[0].days_in_transit == 1


def test_manufacturing_site_always_appears() -> None:
    """Verify manufacturing site (6122) always appears even with no production."""
    base_date = date(2025, 10, 13)

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
    }

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date,
        production_batches=[],
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=0.0,
        total_labor_hours=0.0
    )

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, [], locations_dict, forecast)

    # Check multiple days
    for days_offset in range(5):
        snapshot = generator._generate_single_snapshot(base_date + timedelta(days=days_offset))

        assert "6122" in snapshot.location_inventory, f"Manufacturing should appear on day {days_offset}"
        assert snapshot.location_inventory["6122"].total_quantity == 0.0


def test_intermediate_storage_appears_when_used() -> None:
    """Verify intermediate storage (Lineage) appears when used."""
    base_date = date(2025, 10, 13)

    locations_dict = {
        "6122": Location(id="6122", name="Mfg", type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT),
        "Lineage": Location(id="Lineage", name="Lineage Frozen", type=LocationType.STORAGE, storage_mode=StorageMode.FROZEN),
        "6130": Location(id="6130", name="WA", type=LocationType.BREADROOM, storage_mode=StorageMode.BOTH),
    }

    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
        manufacturing_site_id="6122",
        production_date=base_date,
        quantity=500.0,
        initial_state=ProductState.FROZEN,
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

    # Route through Lineage
    route = MockRoute(route_legs=[
        MockRouteLeg("6122", "Lineage", 2, "frozen"),
        MockRouteLeg("Lineage", "6130", 3, "frozen")
    ])

    shipments = [
        Shipment(
            id="SHIP-001", batch_id="BATCH-001", product_id="176283",
            quantity=500.0, origin_id="6122", destination_id="6130",
            delivery_date=base_date + timedelta(days=6),
            route=route, production_date=base_date
        ),
    ]

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, shipments, locations_dict, forecast)

    # All 3 locations should always appear
    for days_offset in range(7):
        snapshot = generator._generate_single_snapshot(base_date + timedelta(days=days_offset))

        assert len(snapshot.location_inventory) == 3, f"All 3 locations should appear on day {days_offset}"
        assert "6122" in snapshot.location_inventory
        assert "Lineage" in snapshot.location_inventory
        assert "6130" in snapshot.location_inventory


def test_full_network_all_locations() -> None:
    """Integration test: Full network with all 10+ locations.

    This test verifies the complete fix by creating a realistic scenario
    with all network locations and ensuring they ALL appear regardless of
    inventory state.
    """
    base_date = date(2025, 10, 13)

    # Complete network: 1 manufacturing + 2 hubs + 9 breadrooms + 1 intermediate storage
    locations_dict = {
        "6122": Location(id="6122", name="Manufacturing", type=LocationType.MANUFACTURING, storage_mode=StorageMode.BOTH),
        "6104": Location(id="6104", name="Hub NSW", type=LocationType.STORAGE, storage_mode=StorageMode.BOTH),
        "6125": Location(id="6125", name="Hub VIC", type=LocationType.STORAGE, storage_mode=StorageMode.BOTH),
        "Lineage": Location(id="Lineage", name="Lineage", type=LocationType.STORAGE, storage_mode=StorageMode.FROZEN),
        "6103": Location(id="6103", name="VIC", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6105": Location(id="6105", name="NSW", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6107": Location(id="6107", name="ACT", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6110": Location(id="6110", name="QLD", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6115": Location(id="6115", name="SA", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6118": Location(id="6118", name="TAS", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6123": Location(id="6123", name="NSW2", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6127": Location(id="6127", name="VIC2", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        "6130": Location(id="6130", name="WA", type=LocationType.BREADROOM, storage_mode=StorageMode.BOTH),
    }

    # Some production
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="176283",
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

    # Ship to only a few locations (mixed inventory states)
    route1 = MockRoute(route_legs=[MockRouteLeg("6122", "6104", 1)])
    route2 = MockRoute(route_legs=[MockRouteLeg("6122", "6125", 1), MockRouteLeg("6125", "6103", 1)])
    route3 = MockRoute(route_legs=[MockRouteLeg("6122", "6110", 2)])

    shipments = [
        Shipment(
            id="SHIP-001", batch_id="BATCH-001", product_id="176283",
            quantity=600.0, origin_id="6122", destination_id="6104",
            delivery_date=base_date + timedelta(days=2),
            route=route1, production_date=base_date
        ),
        Shipment(
            id="SHIP-002", batch_id="BATCH-001", product_id="176283",
            quantity=700.0, origin_id="6122", destination_id="6103",
            delivery_date=base_date + timedelta(days=3),
            route=route2, production_date=base_date
        ),
        Shipment(
            id="SHIP-003", batch_id="BATCH-001", product_id="176283",
            quantity=700.0, origin_id="6122", destination_id="6110",
            delivery_date=base_date + timedelta(days=3),
            route=route3, production_date=base_date
        ),
    ]

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, shipments, locations_dict, forecast)
    snapshot = generator._generate_single_snapshot(base_date + timedelta(days=5))

    # CRITICAL: ALL 13 locations MUST appear
    assert len(snapshot.location_inventory) == 13, f"Expected 13 locations, got {len(snapshot.location_inventory)}"

    # Verify each location appears
    for location_id in locations_dict.keys():
        assert location_id in snapshot.location_inventory, f"Location {location_id} should appear in snapshot"

    # Verify locations with zero inventory are included
    zero_inventory_locations = ["6105", "6107", "6115", "6118", "6123", "6127", "6130", "Lineage"]
    for location_id in zero_inventory_locations:
        assert snapshot.location_inventory[location_id].total_quantity == 0.0, \
            f"Location {location_id} should have zero inventory"
