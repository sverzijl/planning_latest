"""Integration tests for Daily Snapshot UI component with backend.

This test suite validates the integration between the UI component and backend
DailySnapshotGenerator, ensuring correct data flow and transformation from
backend dataclasses to UI dict format.
"""

import pytest
import sys
from datetime import date, timedelta
from typing import Dict, List
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

# Mock streamlit before importing UI components
sys.modules['streamlit'] = MagicMock()

# Import UI component functions
from ui.components.daily_snapshot import _generate_snapshot, _get_date_range

# Import backend for verification
from src.analysis.daily_snapshot import DailySnapshotGenerator

# Import models
from src.models.location import Location, LocationType, StorageMode
from src.production.scheduler import ProductionSchedule
from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.models.forecast import Forecast, ForecastEntry
from src.models.product import ProductState


# ===========================
# Mock Route Classes
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
def sample_locations() -> Dict[str, Location]:
    """Returns dict of Location objects for 6122, 6125, 6103."""
    return {
        "6122": Location(
            id="6122",
            name="Manufacturing Site",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH,
            capacity=100000
        ),
        "6125": Location(
            id="6125",
            name="Hub VIC",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
            capacity=50000
        ),
        "6103": Location(
            id="6103",
            name="Breadroom VIC",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
            capacity=5000
        ),
    }


@pytest.fixture
def sample_production_schedule() -> ProductionSchedule:
    """Returns ProductionSchedule with batches and schedule_start_date."""
    base_date = date(2025, 10, 15)

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
    ]

    return ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=base_date,
        schedule_end_date=base_date + timedelta(days=5),
        production_batches=batches,
        daily_totals={base_date: 960.0},
        daily_labor_hours={base_date: 0.69},
        infeasibilities=[],
        total_units=960.0,
        total_labor_hours=0.69
    )


@pytest.fixture
def sample_shipments() -> List[Shipment]:
    """Returns list of Shipment objects with multi-leg routes."""
    base_date = date(2025, 10, 15)

    # Multi-leg route: 6122 -> 6125 (1 day) -> 6103 (1 day)
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
            delivery_date=base_date + timedelta(days=3),  # Arrives Oct 18
            route=route,
            production_date=base_date
        ),
        Shipment(
            id="SHIP-002",
            batch_id="BATCH-002",
            product_id="176284",
            quantity=200.0,  # Partial fulfillment
            origin_id="6122",
            destination_id="6103",
            delivery_date=base_date + timedelta(days=3),  # Arrives Oct 18
            route=route,
            production_date=base_date
        ),
    ]


@pytest.fixture
def sample_forecast() -> Forecast:
    """Returns Forecast object with demand entries."""
    base_date = date(2025, 10, 15)
    demand_date = base_date + timedelta(days=3)  # Oct 18

    return Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                forecast_date=demand_date,
                quantity=320.0
            ),
            ForecastEntry(
                location_id="6103",
                product_id="176284",
                forecast_date=demand_date,
                quantity=640.0  # More than shipped (200)
            ),
        ]
    )


# ===========================
# Helper function to generate snapshot with forecast
# ===========================


def generate_snapshot_with_forecast(
    selected_date: date,
    production_schedule: ProductionSchedule,
    shipments: List[Shipment],
    locations: Dict[str, Location],
    forecast: Forecast
) -> Dict:
    """Generate snapshot by mocking Streamlit session state with forecast."""

    # Mock streamlit session state with forecast
    mock_session_state = {'forecast': forecast}

    with patch('streamlit.session_state', mock_session_state):
        return _generate_snapshot(
            selected_date=selected_date,
            production_schedule=production_schedule,
            shipments=shipments,
            locations=locations
        )


# ===========================
# Test 1: Multi-Location Inventory Display
# ===========================


def test_multi_location_inventory_display(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test inventory appears at all locations with correct quantities."""

    # Generate snapshot for date after arrivals (Oct 18)
    snapshot_date = date(2025, 10, 18)

    snapshot = generate_snapshot_with_forecast(
        selected_date=snapshot_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Verify snapshot structure
    assert 'location_inventory' in snapshot
    assert isinstance(snapshot['location_inventory'], dict)

    # Verify inventory at destination location 6103 (arrivals completed)
    assert '6103' in snapshot['location_inventory']
    dest_inv = snapshot['location_inventory']['6103']

    # Should have both products delivered
    assert dest_inv['total'] == 520.0  # 320 + 200
    assert '176283' in dest_inv['by_product']
    assert dest_inv['by_product']['176283'] == 320.0
    assert '176284' in dest_inv['by_product']
    assert dest_inv['by_product']['176284'] == 200.0


def test_manufacturing_inventory_decreases_after_shipment(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test manufacturing location inventory decreases after shipments depart."""

    # Snapshot on production day (Oct 15) - inventory should exist
    production_date = date(2025, 10, 15)
    snapshot_production = generate_snapshot_with_forecast(
        selected_date=production_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Manufacturing should have full inventory
    assert '6122' in snapshot_production['location_inventory']
    mfg_inv_before = snapshot_production['location_inventory']['6122']
    assert mfg_inv_before['total'] == 960.0

    # Snapshot on departure day (Oct 16) - shipments depart
    departure_date = date(2025, 10, 16)
    snapshot_departure = generate_snapshot_with_forecast(
        selected_date=departure_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Manufacturing inventory should decrease by shipped amount
    mfg_inv_after = snapshot_departure['location_inventory']['6122']
    # 960 - 320 - 200 = 440 remaining
    assert mfg_inv_after['total'] == 440.0


def test_hub_inventory_increases_after_arrival(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test hub location increases after shipments arrive."""

    # Snapshot on hub arrival date (Oct 17) - first leg arrival
    hub_arrival_date = date(2025, 10, 17)
    snapshot = generate_snapshot_with_forecast(
        selected_date=hub_arrival_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Hub 6125 should have inventory from arrivals
    assert '6125' in snapshot['location_inventory']
    hub_inv = snapshot['location_inventory']['6125']

    # Should have arrived shipments
    assert hub_inv['total'] == 520.0  # 320 + 200


# ===========================
# Test 2: In-Transit Detection
# ===========================


def test_in_transit_detection(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test in-transit shipments are correctly identified."""

    # Snapshot during first leg transit (Oct 16)
    transit_date = date(2025, 10, 16)
    snapshot = generate_snapshot_with_forecast(
        selected_date=transit_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have in-transit shipments
    assert 'in_transit_shipments' in snapshot
    assert isinstance(snapshot['in_transit_shipments'], list)
    assert len(snapshot['in_transit_shipments']) == 2

    # Verify details
    for transit in snapshot['in_transit_shipments']:
        assert transit['origin_id'] == '6122'
        assert transit['destination_id'] == '6125'  # First leg
        assert transit['days_in_transit'] == 0  # Just departed
        assert transit['product_id'] in ['176283', '176284']
        assert transit['quantity'] in [320.0, 200.0]


def test_no_in_transit_before_departure(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test shipments not yet departed don't appear in transit."""

    # Snapshot before departure (Oct 15)
    before_departure = date(2025, 10, 15)
    snapshot = generate_snapshot_with_forecast(
        selected_date=before_departure,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have no in-transit shipments
    assert len(snapshot['in_transit_shipments']) == 0


def test_no_in_transit_after_arrival(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test shipments already arrived don't appear in transit."""

    # Snapshot after final delivery (Oct 19)
    after_arrival = date(2025, 10, 19)
    snapshot = generate_snapshot_with_forecast(
        selected_date=after_arrival,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have no in-transit shipments
    assert len(snapshot['in_transit_shipments']) == 0


def test_multi_leg_in_transit(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test in-transit detection on second leg of multi-leg route."""

    # Snapshot during second leg transit (Oct 17)
    second_leg_date = date(2025, 10, 17)
    snapshot = generate_snapshot_with_forecast(
        selected_date=second_leg_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have in-transit shipments on second leg
    assert len(snapshot['in_transit_shipments']) == 2

    for transit in snapshot['in_transit_shipments']:
        assert transit['origin_id'] == '6125'  # Second leg origin
        assert transit['destination_id'] == '6103'  # Second leg destination


# ===========================
# Test 3: Outflow Tracking
# ===========================


def test_outflow_tracking_departures(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test outflows include departure events."""

    # Snapshot on departure date (Oct 16)
    departure_date = date(2025, 10, 16)
    snapshot = generate_snapshot_with_forecast(
        selected_date=departure_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have outflows
    assert 'outflows' in snapshot
    assert isinstance(snapshot['outflows'], list)

    # Filter for departure outflows
    departures = [f for f in snapshot['outflows'] if f['type'] == 'Departure']
    assert len(departures) == 2

    # Verify details
    for outflow in departures:
        assert outflow['location'] == '6122'
        assert outflow['product'] in ['176283', '176284']
        assert outflow['quantity'] in [320.0, 200.0]
        assert 'To 6125' in outflow.get('details', '')


def test_outflow_tracking_demand(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test outflows include demand when deliveries occur."""

    # Snapshot on delivery date (Oct 18)
    delivery_date = date(2025, 10, 18)
    snapshot = generate_snapshot_with_forecast(
        selected_date=delivery_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have demand outflows
    demand_outflows = [f for f in snapshot['outflows'] if f['type'] == 'Demand']
    assert len(demand_outflows) == 2  # Two products delivered

    # Verify details
    total_demand_outflow = sum(f['quantity'] for f in demand_outflows)
    assert total_demand_outflow == 520.0  # 320 + 200


# ===========================
# Test 4: Demand Satisfaction Accuracy
# ===========================


def test_demand_satisfaction_partial(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test demand satisfaction with partial fulfillment."""

    # Snapshot on demand date (Oct 18)
    demand_date = date(2025, 10, 18)
    snapshot = generate_snapshot_with_forecast(
        selected_date=demand_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have demand satisfaction records
    assert 'demand_satisfaction' in snapshot
    assert len(snapshot['demand_satisfaction']) == 2

    # Check product 176283 - fully satisfied
    prod_283 = next(d for d in snapshot['demand_satisfaction'] if d['product'] == '176283')
    assert prod_283['demand'] == 320.0
    assert prod_283['supplied'] == 320.0
    assert '✅ Met' in prod_283['status']

    # Check product 176284 - partially satisfied (demand 640, supplied 200)
    prod_284 = next(d for d in snapshot['demand_satisfaction'] if d['product'] == '176284')
    assert prod_284['demand'] == 640.0
    assert prod_284['supplied'] == 200.0
    assert '⚠️ Short' in prod_284['status']


def test_demand_satisfaction_status(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test status calculation for met vs short demand."""

    demand_date = date(2025, 10, 18)
    snapshot = generate_snapshot_with_forecast(
        selected_date=demand_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Count met vs short
    met_count = sum(1 for d in snapshot['demand_satisfaction'] if '✅' in d['status'])
    short_count = sum(1 for d in snapshot['demand_satisfaction'] if '⚠️' in d['status'])

    assert met_count == 1  # 176283 met
    assert short_count == 1  # 176284 short


# ===========================
# Test 5: Planning Horizon Respect
# ===========================


def test_planning_horizon_respect() -> None:
    """Test date range respects planning horizon start date."""

    # Create production schedule with schedule_start_date
    schedule_start = date(2025, 10, 15)
    historical_date = date(2025, 10, 10)  # Before planning start

    # Production batches with historical dates
    batches = [
        ProductionBatch(
            id="BATCH-OLD",
            product_id="176283",
            manufacturing_site_id="6122",
            production_date=historical_date,  # Before planning start
            quantity=100.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.07,
            production_cost=50.0
        ),
        ProductionBatch(
            id="BATCH-NEW",
            product_id="176283",
            manufacturing_site_id="6122",
            production_date=schedule_start,  # On planning start
            quantity=320.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.23,
            production_cost=160.0
        ),
    ]

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=schedule_start,
        schedule_end_date=schedule_start + timedelta(days=5),
        production_batches=batches,
        daily_totals={historical_date: 100.0, schedule_start: 320.0},
        daily_labor_hours={historical_date: 0.07, schedule_start: 0.23},
        infeasibilities=[],
        total_units=420.0,
        total_labor_hours=0.30
    )

    # Get date range
    date_range = _get_date_range(schedule, [])

    # Should start at planning start, not historical date
    assert date_range is not None
    min_date, max_date = date_range
    assert min_date == schedule_start
    assert min_date > historical_date


def test_date_range_filters_historical_production() -> None:
    """Test historical production dates are filtered from date range."""

    schedule_start = date(2025, 10, 15)

    batches = [
        ProductionBatch(
            id="BATCH-001",
            product_id="176283",
            manufacturing_site_id="6122",
            production_date=date(2025, 10, 12),  # 3 days before start
            quantity=320.0,
            initial_state=ProductState.AMBIENT,
            labor_hours_used=0.23,
            production_cost=160.0
        ),
    ]

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=schedule_start,
        schedule_end_date=schedule_start,
        production_batches=batches,
        daily_totals={date(2025, 10, 12): 320.0},
        daily_labor_hours={date(2025, 10, 12): 0.23},
        infeasibilities=[],
        total_units=320.0,
        total_labor_hours=0.23
    )

    # Date range should be None (no dates on or after planning start)
    date_range = _get_date_range(schedule, [])

    # Since there's no production on or after start date, should return None or start date
    # The implementation may vary - let's verify it doesn't include historical dates
    if date_range is not None:
        min_date, _ = date_range
        assert min_date >= schedule_start


# ===========================
# Test 6: Edge Cases
# ===========================


def test_empty_forecast(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location]
) -> None:
    """Test with empty forecast (no demand data)."""

    empty_forecast = Forecast(name="Empty", entries=[])

    snapshot = generate_snapshot_with_forecast(
        selected_date=date(2025, 10, 18),
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=empty_forecast
    )

    # Should still generate snapshot
    assert 'location_inventory' in snapshot
    assert 'in_transit_shipments' in snapshot

    # Demand satisfaction should be empty or only show deliveries
    # (depending on implementation, may show supplied without demand)
    assert 'demand_satisfaction' in snapshot


def test_no_shipments(
    sample_production_schedule: ProductionSchedule,
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test with no shipments (only production)."""

    snapshot = generate_snapshot_with_forecast(
        selected_date=date(2025, 10, 15),
        production_schedule=sample_production_schedule,
        shipments=[],
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have production but no transit
    assert snapshot['production_total'] == 960.0
    assert snapshot['in_transit_total'] == 0.0
    assert len(snapshot['in_transit_shipments']) == 0

    # All inventory should be at manufacturing
    assert '6122' in snapshot['location_inventory']
    assert snapshot['location_inventory']['6122']['total'] == 960.0


def test_missing_location_in_dict(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_forecast: Forecast
) -> None:
    """Test with missing locations in locations_dict."""

    # Only provide manufacturing location
    partial_locations = {
        "6122": Location(
            id="6122",
            name="Manufacturing",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH
        )
    }

    # Should still work, using location IDs where location objects missing
    snapshot = generate_snapshot_with_forecast(
        selected_date=date(2025, 10, 18),
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=partial_locations,
        forecast=sample_forecast
    )

    # Should still have location inventory (may use ID as name)
    assert 'location_inventory' in snapshot
    assert isinstance(snapshot['location_inventory'], dict)


def test_snapshot_before_production(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test snapshot date before any production."""

    # Date before production starts
    before_date = date(2025, 10, 14)

    snapshot = generate_snapshot_with_forecast(
        selected_date=before_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have zero inventory and production
    assert snapshot['total_inventory'] == 0.0
    assert snapshot['production_total'] == 0.0
    assert len(snapshot['production_batches']) == 0


def test_snapshot_after_all_deliveries(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test snapshot date after all deliveries complete."""

    # Date well after deliveries (Oct 25)
    after_date = date(2025, 10, 25)

    snapshot = generate_snapshot_with_forecast(
        selected_date=after_date,
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Should have inventory at destinations, no in-transit
    assert snapshot['in_transit_total'] == 0.0
    assert len(snapshot['in_transit_shipments']) == 0

    # Inventory should be at final destinations
    if '6103' in snapshot['location_inventory']:
        assert snapshot['location_inventory']['6103']['total'] > 0


# ===========================
# Test 7: Data Type Validation
# ===========================


def test_snapshot_data_types(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test all snapshot fields have correct data types."""

    snapshot = generate_snapshot_with_forecast(
        selected_date=date(2025, 10, 18),
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Verify top-level structure
    assert isinstance(snapshot, dict)
    assert isinstance(snapshot['date'], date)
    assert isinstance(snapshot['total_inventory'], (int, float))
    assert isinstance(snapshot['in_transit_total'], (int, float))
    assert isinstance(snapshot['production_total'], (int, float))
    assert isinstance(snapshot['demand_total'], (int, float))

    # Verify nested structures
    assert isinstance(snapshot['location_inventory'], dict)
    assert isinstance(snapshot['in_transit_shipments'], list)
    assert isinstance(snapshot['production_batches'], list)
    assert isinstance(snapshot['inflows'], list)
    assert isinstance(snapshot['outflows'], list)
    assert isinstance(snapshot['demand_satisfaction'], list)

    # Verify location inventory structure
    if snapshot['location_inventory']:
        for loc_id, inv_data in snapshot['location_inventory'].items():
            assert isinstance(loc_id, str)
            assert isinstance(inv_data, dict)
            assert isinstance(inv_data['total'], (int, float))
            assert isinstance(inv_data['by_product'], dict)
            assert isinstance(inv_data.get('batches', {}), dict)


def test_exact_quantities(
    sample_production_schedule: ProductionSchedule,
    sample_shipments: List[Shipment],
    sample_locations: Dict[str, Location],
    sample_forecast: Forecast
) -> None:
    """Test exact quantity calculations (not just presence)."""

    snapshot = generate_snapshot_with_forecast(
        selected_date=date(2025, 10, 15),  # Production day
        production_schedule=sample_production_schedule,
        shipments=sample_shipments,
        locations=sample_locations,
        forecast=sample_forecast
    )

    # Exact production total
    assert snapshot['production_total'] == 960.0  # 320 + 640

    # Exact inventory at manufacturing
    mfg_inv = snapshot['location_inventory']['6122']
    assert mfg_inv['total'] == 960.0
    assert mfg_inv['by_product']['176283'] == 320.0
    assert mfg_inv['by_product']['176284'] == 640.0
