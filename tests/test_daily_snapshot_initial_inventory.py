"""Integration test for Daily Snapshot with initial inventory.

This test suite validates that the Daily Snapshot correctly handles initial inventory
loaded from a snapshot date, ensuring:
1. Starts at the inventory snapshot date (not model planning horizon start)
2. Shows inventory at all locations (not just 6122)
3. Tracks inventory movement as batches are shipped
4. Shows correct outflows when shipments depart
5. Shows non-zero supplied in demand satisfaction
"""

import pytest
from datetime import date, timedelta
from typing import Dict, List, Any
from unittest.mock import MagicMock

# Result adapter (the code we're testing)
from ui.utils.result_adapter import adapt_optimization_results, _create_production_schedule

# Models
from src.production.scheduler import ProductionSchedule, ProductionBatch
from src.models.shipment import Shipment
from src.models.location import Location, LocationType, StorageMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.inventory import InventorySnapshot, InventoryEntry
from src.network.route_finder import RoutePath
from src.shelf_life import RouteLeg
from src.analysis.daily_snapshot import DailySnapshotGenerator, DailySnapshot


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_locations():
    """Create mock locations for testing."""
    return {
        '6122': Location(
            id='6122',
            name='Manufacturing Site',
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH
        ),
        '6104': Location(
            id='6104',
            name='Hub NSW',
            type=LocationType.STORAGE,  # Hubs are storage locations
            storage_mode=StorageMode.BOTH
        ),
        '6125': Location(
            id='6125',
            name='Hub VIC',
            type=LocationType.STORAGE,  # Hubs are storage locations
            storage_mode=StorageMode.BOTH
        ),
        '6130': Location(
            id='6130',
            name='Breadroom WA',
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.BOTH
        ),
    }


@pytest.fixture
def mock_cost_structure():
    """Create mock cost structure."""
    cost_structure = MagicMock()
    cost_structure.production_cost_per_unit = 2.50
    return cost_structure


@pytest.fixture
def mock_manufacturing_site():
    """Create mock manufacturing site."""
    site = MagicMock()
    site.location_id = '6122'
    site.production_rate = 1400.0  # units per hour
    return site


@pytest.fixture
def basic_route():
    """Create a basic route for shipments."""
    leg = RouteLeg(
        from_location_id='6122',
        to_location_id='6125',
        transport_mode='ambient',
        transit_days=1,
        triggers_thaw=False
    )
    return RoutePath(
        path=['6122', '6125'],
        route_legs=[leg],
        total_cost=0.10,
        total_transit_days=1,
        transport_modes=['ambient'],
        intermediate_stops=[]
    )


# ============================================================================
# MOCK OPTIMIZATION MODEL
# ============================================================================

class MockOptimizationModel:
    """Mock optimization model with initial inventory support."""

    def __init__(
        self,
        start_date: date,
        end_date: date,
        initial_inventory: Dict[tuple, float],
        manufacturing_site,
        cost_structure
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_inventory = initial_inventory
        self.manufacturing_site = manufacturing_site
        self.cost_structure = cost_structure
        self._solution = None
        self._shipments = []

    def get_solution(self):
        """Return the mock solution."""
        return self._solution

    def set_solution(self, solution: dict):
        """Set the mock solution."""
        self._solution = solution

    def get_shipment_plan(self):
        """Return the mock shipment plan."""
        return self._shipments

    def set_shipments(self, shipments: List[Shipment]):
        """Set the mock shipments."""
        self._shipments = shipments


# ============================================================================
# TEST 1: Initial Inventory Creates Batches
# ============================================================================

def test_initial_inventory_creates_batches(
    mock_manufacturing_site,
    mock_cost_structure
):
    """Test that initial inventory creates batches with correct IDs and locations."""

    # Setup
    inventory_snapshot_date = date(2025, 10, 8)
    model = MockOptimizationModel(start_date=date(2025, 10, 3),
        end_date=date(2025, 11, 30),
        initial_inventory={
            ('6122', '176283'): 320.0,  # Manufacturing
            ('6122', '176284'): 640.0,
            ('6104', '176283'): 160.0,  # Hub NSW
            ('6125', '176283'): 200.0,  # Hub VIC
            ('6125', '176284'): 320.0,
            ('6130', '176284'): 480.0,  # Breadroom WA
        },
        manufacturing_site=mock_manufacturing_site,
        cost_structure=mock_cost_structure
    )

    # Set empty solution (no production batches)
    model.set_solution({
        'production_batches': [],
        'labor_hours_by_date': {},
    })

    # Act
    schedule = _create_production_schedule(
        model,
        model.get_solution(),
        inventory_snapshot_date
    )

    # Assert - should have 6 initial inventory batches
    assert len(schedule.production_batches) == 6

    # Check batch IDs follow pattern "INIT-{location}-{product}"
    batch_ids = [b.id for b in schedule.production_batches]
    assert 'INIT-6122-176283' in batch_ids
    assert 'INIT-6122-176284' in batch_ids
    assert 'INIT-6104-176283' in batch_ids
    assert 'INIT-6125-176283' in batch_ids
    assert 'INIT-6125-176284' in batch_ids
    assert 'INIT-6130-176284' in batch_ids

    # Check manufacturing_site_id field has correct location (not all 6122!)
    batch_6104 = next(b for b in schedule.production_batches if b.id == 'INIT-6104-176283')
    assert batch_6104.manufacturing_site_id == '6104', "Initial inventory batch should use actual location"

    batch_6125 = next(b for b in schedule.production_batches if b.id == 'INIT-6125-176283')
    assert batch_6125.manufacturing_site_id == '6125'

    batch_6130 = next(b for b in schedule.production_batches if b.id == 'INIT-6130-176284')
    assert batch_6130.manufacturing_site_id == '6130'

    # Check production dates are snapshot_date - 1 day
    expected_production_date = inventory_snapshot_date - timedelta(days=1)
    for batch in schedule.production_batches:
        assert batch.production_date == expected_production_date


# ============================================================================
# TEST 2: Schedule Start Date Uses Inventory Snapshot Date
# ============================================================================

def test_schedule_start_date_uses_inventory_snapshot_date(
    mock_manufacturing_site,
    mock_cost_structure
):
    """Test that schedule_start_date uses inventory snapshot date, not model start date."""

    # Setup - model planning horizon starts Oct 3, but inventory snapshot is Oct 8
    model_start = date(2025, 10, 3)
    inventory_snapshot_date = date(2025, 10, 8)

    model = MockOptimizationModel(
        start_date=model_start,
        end_date=date(2025, 11, 30),
        initial_inventory={
            ('6122', '176283'): 320.0,
        },
        manufacturing_site=mock_manufacturing_site,
        cost_structure=mock_cost_structure
    )

    model.set_solution({
        'production_batches': [],
        'labor_hours_by_date': {},
    })

    # Act
    schedule = _create_production_schedule(
        model,
        model.get_solution(),
        inventory_snapshot_date
    )

    # Assert - should use inventory snapshot date, NOT model start date
    assert schedule.schedule_start_date == inventory_snapshot_date
    assert schedule.schedule_start_date != model_start, "Should NOT use model.start_date"


# ============================================================================
# TEST 3: Initial Inventory at Multiple Locations
# ============================================================================

def test_initial_inventory_at_multiple_locations(
    mock_manufacturing_site,
    mock_cost_structure
):
    """Test that initial inventory at multiple locations creates correct batches."""

    # Setup - 4 locations × 2 products = 8 batches
    inventory_snapshot_date = date(2025, 10, 8)
    model = MockOptimizationModel(start_date=date(2025, 10, 3),
        end_date=date(2025, 11, 30),
        initial_inventory={
            ('6122', '176283'): 320.0,
            ('6122', '176284'): 640.0,
            ('6104', '176283'): 160.0,
            ('6104', '176284'): 240.0,
            ('6125', '176283'): 200.0,
            ('6125', '176284'): 320.0,
            ('6130', '176283'): 100.0,
            ('6130', '176284'): 480.0,
        },
        manufacturing_site=mock_manufacturing_site,
        cost_structure=mock_cost_structure
    )

    model.set_solution({
        'production_batches': [],
        'labor_hours_by_date': {},
    })

    # Act
    schedule = _create_production_schedule(
        model,
        model.get_solution(),
        inventory_snapshot_date
    )

    # Assert
    assert len(schedule.production_batches) == 8, "Should have 8 initial inventory batches"

    # Group batches by location
    batches_by_location = {}
    for batch in schedule.production_batches:
        loc = batch.manufacturing_site_id
        if loc not in batches_by_location:
            batches_by_location[loc] = []
        batches_by_location[loc].append(batch)

    # Verify each location has correct batches
    assert len(batches_by_location['6122']) == 2
    assert len(batches_by_location['6104']) == 2
    assert len(batches_by_location['6125']) == 2
    assert len(batches_by_location['6130']) == 2

    # Verify quantities
    batch_6104_176283 = next(b for b in batches_by_location['6104'] if b.product_id == '176283')
    assert batch_6104_176283.quantity == 160.0

    batch_6130_176284 = next(b for b in batches_by_location['6130'] if b.product_id == '176284')
    assert batch_6130_176284.quantity == 480.0


# ============================================================================
# TEST 4: Initial Inventory Zero Cost
# ============================================================================

def test_initial_inventory_zero_cost(
    mock_manufacturing_site,
    mock_cost_structure
):
    """Test that initial inventory batches have zero labor and production costs."""

    # Setup
    inventory_snapshot_date = date(2025, 10, 8)
    model = MockOptimizationModel(start_date=date(2025, 10, 3),
        end_date=date(2025, 11, 30),
        initial_inventory={
            ('6122', '176283'): 320.0,
            ('6104', '176283'): 160.0,
            ('6125', '176284'): 320.0,
        },
        manufacturing_site=mock_manufacturing_site,
        cost_structure=mock_cost_structure
    )

    model.set_solution({
        'production_batches': [],
        'labor_hours_by_date': {},
    })

    # Act
    schedule = _create_production_schedule(
        model,
        model.get_solution(),
        inventory_snapshot_date
    )

    # Assert - all initial inventory batches should have zero costs
    for batch in schedule.production_batches:
        assert batch.labor_hours_used == 0.0, "Initial inventory should have zero labor hours"
        assert batch.production_cost == 0.0, "Initial inventory should have zero production cost (sunk cost)"


# ============================================================================
# TEST 5: Backwards Compatibility Without Snapshot Date
# ============================================================================

def test_backwards_compatibility_without_snapshot_date(
    mock_manufacturing_site,
    mock_cost_structure
):
    """Test that code works without inventory_snapshot_date (backwards compatible)."""

    # Setup
    model = MockOptimizationModel(start_date=date(2025, 10, 3),
        end_date=date(2025, 11, 30),
        initial_inventory={
            ('6122', '176283'): 320.0,
        },
        manufacturing_site=mock_manufacturing_site,
        cost_structure=mock_cost_structure
    )

    # Add a production batch
    model.set_solution({
        'production_batches': [
            {
                'product': '176283',
                'date': date(2025, 10, 10),
                'quantity': 640.0
            }
        ],
        'labor_hours_by_date': {
            date(2025, 10, 10): 8.0
        },
    })

    # Act - call without inventory_snapshot_date parameter
    schedule = _create_production_schedule(
        model,
        model.get_solution(),
        inventory_snapshot_date=None  # Explicitly None
    )

    # Assert - should still work (backwards compatible)
    assert schedule is not None, "Should not crash without inventory_snapshot_date"

    # Should have only production batch, no initial inventory batches
    assert len(schedule.production_batches) == 1
    assert schedule.production_batches[0].id.startswith('OPT-BATCH-')

    # Should use earliest batch date as schedule start
    assert schedule.schedule_start_date == date(2025, 10, 10)


# ============================================================================
# TEST 6: Mixed Initial and Production Batches
# ============================================================================

def test_mixed_initial_and_production_batches(
    mock_manufacturing_site,
    mock_cost_structure
):
    """Test that initial inventory and production batches coexist correctly."""

    # Setup
    inventory_snapshot_date = date(2025, 10, 8)
    model = MockOptimizationModel(start_date=date(2025, 10, 3),
        end_date=date(2025, 11, 30),
        initial_inventory={
            ('6122', '176283'): 320.0,
            ('6104', '176283'): 160.0,
            ('6125', '176283'): 200.0,
        },
        manufacturing_site=mock_manufacturing_site,
        cost_structure=mock_cost_structure
    )

    # Add production batches
    model.set_solution({
        'production_batches': [
            {
                'product': '176283',
                'date': date(2025, 10, 10),
                'quantity': 640.0
            },
            {
                'product': '176284',
                'date': date(2025, 10, 11),
                'quantity': 960.0
            },
            {
                'product': '176283',
                'date': date(2025, 10, 12),
                'quantity': 800.0
            }
        ],
        'labor_hours_by_date': {
            date(2025, 10, 10): 8.0,
            date(2025, 10, 11): 10.0,
            date(2025, 10, 12): 9.0,
        },
    })

    # Act
    schedule = _create_production_schedule(
        model,
        model.get_solution(),
        inventory_snapshot_date
    )

    # Assert - should have 3 initial + 3 production = 6 batches
    assert len(schedule.production_batches) == 6

    # Count initial vs production batches
    initial_batches = [b for b in schedule.production_batches if b.id.startswith('INIT-')]
    production_batches = [b for b in schedule.production_batches if b.id.startswith('OPT-BATCH-')]

    assert len(initial_batches) == 3, "Should have 3 initial inventory batches"
    assert len(production_batches) == 3, "Should have 3 production batches"

    # Initial batches should have earlier dates
    initial_dates = [b.production_date for b in initial_batches]
    production_dates = [b.production_date for b in production_batches]

    assert all(d == date(2025, 10, 7) for d in initial_dates), "Initial batches dated snapshot_date - 1"
    assert min(production_dates) >= date(2025, 10, 10), "Production batches dated later"

    # Schedule start should be inventory snapshot date
    assert schedule.schedule_start_date == inventory_snapshot_date


# ============================================================================
# TEST 7: Daily Snapshot Generator Integration
# ============================================================================

def test_daily_snapshot_generator_integration(
    mock_locations,
    basic_route
):
    """Test that DailySnapshotGenerator correctly tracks initial inventory."""

    # Setup - Create complete scenario with initial inventory
    inventory_snapshot_date = date(2025, 10, 8)

    # Create batches manually (simulating what _create_production_schedule does)
    batches = [
        # Initial inventory batches
        ProductionBatch(
            id='INIT-6122-176283',
            product_id='176283',
            manufacturing_site_id='6122',  # CRITICAL: At manufacturing
            production_date=date(2025, 10, 7),
            quantity=320.0,
            labor_hours_used=0.0,
            production_cost=0.0
        ),
        ProductionBatch(
            id='INIT-6104-176283',
            product_id='176283',
            manufacturing_site_id='6104',  # CRITICAL: At hub NSW
            production_date=date(2025, 10, 7),
            quantity=160.0,
            labor_hours_used=0.0,
            production_cost=0.0
        ),
        ProductionBatch(
            id='INIT-6125-176283',
            product_id='176283',
            manufacturing_site_id='6125',  # CRITICAL: At hub VIC
            production_date=date(2025, 10, 7),
            quantity=200.0,
            labor_hours_used=0.0,
            production_cost=0.0
        ),
        # Production batch
        ProductionBatch(
            id='OPT-BATCH-0001',
            product_id='176283',
            manufacturing_site_id='6122',
            production_date=date(2025, 10, 10),
            quantity=640.0,
            labor_hours_used=8.0,
            production_cost=1600.0
        ),
    ]

    # Create production schedule
    production_schedule = ProductionSchedule(
        manufacturing_site_id='6122',
        schedule_start_date=inventory_snapshot_date,
        schedule_end_date=date(2025, 10, 15),
        production_batches=batches,
        daily_totals={
            date(2025, 10, 7): 680.0,  # Initial inventory total
            date(2025, 10, 10): 640.0,
        },
        daily_labor_hours={
            date(2025, 10, 10): 8.0,
        },
        infeasibilities=[],
        total_units=1320.0,
        total_labor_hours=8.0,
        requirements=[]
    )

    # Create shipments moving inventory from 6122 to 6125
    shipments = [
        Shipment(
            id='SHIP-001',
            batch_id='INIT-6122-176283',
            product_id='176283',
            quantity=320.0,
            origin_id='6122',
            destination_id='6125',
            delivery_date=date(2025, 10, 9),
            route=basic_route,
            production_date=date(2025, 10, 7)
        )
    ]

    # Create forecast with demand
    forecast = Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id='6125',
                product_id='176283',
                forecast_date=date(2025, 10, 9),
                quantity=100.0
            )
        ]
    )

    # Create DailySnapshotGenerator
    generator = DailySnapshotGenerator(
        production_schedule=production_schedule,
        shipments=shipments,
        locations_dict=mock_locations,
        forecast=forecast
    )

    # Act - Generate snapshot for inventory snapshot date (Oct 8)
    snapshot = generator._generate_single_snapshot(inventory_snapshot_date)

    # Assert - Verify inventory at all 3 locations
    assert '6122' in snapshot.location_inventory, "Should have inventory at manufacturing (6122)"
    assert '6104' in snapshot.location_inventory, "Should have inventory at hub NSW (6104)"
    assert '6125' in snapshot.location_inventory, "Should have inventory at hub VIC (6125)"

    # Verify quantities at each location
    assert snapshot.location_inventory['6122'].total_quantity == 320.0, "6122 should have 320 units"
    assert snapshot.location_inventory['6104'].total_quantity == 160.0, "6104 should have 160 units"
    assert snapshot.location_inventory['6125'].total_quantity == 200.0, "6125 should have 200 units"

    # Verify initial batches are tracked
    batches_at_6104 = snapshot.location_inventory['6104'].batches
    assert len(batches_at_6104) == 1
    assert batches_at_6104[0].batch_id == 'INIT-6104-176283'
    assert batches_at_6104[0].quantity == 160.0

    # Act - Generate snapshot for next day (Oct 9) when shipment arrives
    snapshot_oct9 = generator._generate_single_snapshot(date(2025, 10, 9))

    # Assert - Verify inventory moved from 6122 to in-transit
    # On Oct 9, shipment departed from 6122 and arrived at 6125 (1 day transit)
    assert snapshot_oct9.location_inventory['6122'].total_quantity == 0.0, "6122 should be empty after shipment"

    # 6125 should now have initial 200 + shipped 320 = 520, but then -100 for demand = 420
    # Actually, we need to check more carefully - shipment arrives same day as demand
    assert snapshot_oct9.location_inventory['6125'].total_quantity >= 420.0, "6125 should have received shipment"

    # Verify demand satisfaction
    demand_records = snapshot_oct9.demand_satisfied
    if demand_records:
        demand_6125 = next((d for d in demand_records if d.destination_id == '6125'), None)
        if demand_6125:
            assert demand_6125.supplied_quantity > 0, "Should have non-zero supplied quantity"


# ============================================================================
# TEST 8: Outflows Shown When Shipments Depart
# ============================================================================

def test_outflows_shown_when_shipments_depart(
    mock_locations,
    basic_route
):
    """Test that outflows are correctly shown when shipments depart from locations."""

    # Setup
    inventory_snapshot_date = date(2025, 10, 8)

    # Create initial inventory batches at multiple locations
    batches = [
        ProductionBatch(
            id='INIT-6122-176283',
            product_id='176283',
            manufacturing_site_id='6122',
            production_date=date(2025, 10, 7),
            quantity=320.0,
            labor_hours_used=0.0,
            production_cost=0.0
        ),
        ProductionBatch(
            id='INIT-6104-176283',
            product_id='176283',
            manufacturing_site_id='6104',
            production_date=date(2025, 10, 7),
            quantity=160.0,
            labor_hours_used=0.0,
            production_cost=0.0
        ),
    ]

    production_schedule = ProductionSchedule(
        manufacturing_site_id='6122',
        schedule_start_date=inventory_snapshot_date,
        schedule_end_date=date(2025, 10, 15),
        production_batches=batches,
        daily_totals={date(2025, 10, 7): 480.0},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=480.0,
        total_labor_hours=0.0,
        requirements=[]
    )

    # Create shipment departing on Oct 9
    shipments = [
        Shipment(
            id='SHIP-001',
            batch_id='INIT-6122-176283',
            product_id='176283',
            quantity=320.0,
            origin_id='6122',
            destination_id='6125',
            delivery_date=date(2025, 10, 10),  # Arrives Oct 10
            route=basic_route,
            production_date=date(2025, 10, 7)
        )
    ]

    forecast = Forecast(
        name="Test Forecast",
        entries=[]
    )

    generator = DailySnapshotGenerator(
        production_schedule=production_schedule,
        shipments=shipments,
        locations_dict=mock_locations,
        forecast=forecast
    )

    # Act - Generate snapshot for departure date (Oct 9)
    departure_date = date(2025, 10, 9)
    snapshot = generator._generate_single_snapshot(departure_date)

    # Assert - Should have outflow on departure date
    outflows = snapshot.outflows
    assert len(outflows) > 0, "Should have outflows when shipment departs"

    # Find departure outflow
    departure_outflows = [f for f in outflows if f.flow_type == 'departure']
    assert len(departure_outflows) > 0, "Should have departure outflow"

    departure_outflow = departure_outflows[0]
    assert departure_outflow.location_id == '6122', "Outflow should be from 6122"
    assert departure_outflow.product_id == '176283'
    assert departure_outflow.quantity == 320.0
    assert departure_outflow.batch_id == 'INIT-6122-176283'


# ============================================================================
# TEST 9: Non-Zero Supplied in Demand Satisfaction
# ============================================================================

def test_nonzero_supplied_in_demand_satisfaction(
    mock_locations,
    basic_route
):
    """Test that demand satisfaction shows non-zero supplied when initial inventory is used."""

    # Setup
    inventory_snapshot_date = date(2025, 10, 8)

    # Create initial inventory at destination (6125)
    batches = [
        ProductionBatch(
            id='INIT-6125-176283',
            product_id='176283',
            manufacturing_site_id='6125',  # Already at destination
            production_date=date(2025, 10, 7),
            quantity=500.0,
            labor_hours_used=0.0,
            production_cost=0.0
        ),
    ]

    production_schedule = ProductionSchedule(
        manufacturing_site_id='6122',
        schedule_start_date=inventory_snapshot_date,
        schedule_end_date=date(2025, 10, 15),
        production_batches=batches,
        daily_totals={date(2025, 10, 7): 500.0},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=500.0,
        total_labor_hours=0.0,
        requirements=[]
    )

    # Create route from 6125 to 6125 (local delivery, 0 days transit)
    local_route = RoutePath(
        path=['6125', '6125'],
        route_legs=[
            RouteLeg(
                from_location_id='6125',
                to_location_id='6125',
                transport_mode='ambient',
                transit_days=0,
                triggers_thaw=False
            )
        ],
        total_cost=0.0,
        total_transit_days=0,
        transport_modes=['ambient'],
        intermediate_stops=[]
    )

    # Create shipment from initial inventory to satisfy demand
    shipments = [
        Shipment(
            id='SHIP-001',
            batch_id='INIT-6125-176283',
            product_id='176283',
            quantity=300.0,
            origin_id='6125',
            destination_id='6125',
            delivery_date=date(2025, 10, 9),
            route=local_route,
            production_date=date(2025, 10, 7)
        )
    ]

    # Create forecast with demand on Oct 9
    forecast = Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id='6125',
                product_id='176283',
                forecast_date=date(2025, 10, 9),
                quantity=300.0
            )
        ]
    )

    generator = DailySnapshotGenerator(
        production_schedule=production_schedule,
        shipments=shipments,
        locations_dict=mock_locations,
        forecast=forecast
    )

    # Act - Generate snapshot for demand date
    snapshot = generator._generate_single_snapshot(date(2025, 10, 9))

    # Assert - Demand should be satisfied with non-zero supplied
    demand_records = snapshot.demand_satisfied
    assert len(demand_records) > 0, "Should have demand records"

    demand_6125 = next((d for d in demand_records if d.destination_id == '6125'), None)
    assert demand_6125 is not None, "Should have demand record for 6125"
    assert demand_6125.demand_quantity == 300.0
    assert demand_6125.supplied_quantity == 300.0, "Should have non-zero supplied from initial inventory"
    assert demand_6125.shortage_quantity == 0.0
    assert demand_6125.is_satisfied, "Demand should be fully satisfied"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
