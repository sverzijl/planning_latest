"""Comprehensive integration test for Daily Inventory Snapshot.

This test validates the COMPLETE flow of inventory through the system over a 7-day period,
including production, shipments, demand satisfaction, and mass balance verification.

Test Scenario:
- Day 1 (Monday): Production at manufacturing site
- Day 2 (Tuesday): Shipment departs to hub
- Day 3 (Wednesday): Shipment arrives at hub, demand satisfied (inventory decreases)
- Day 4 (Thursday): New production, shipment departs from hub to spoke
- Day 5 (Friday): Shipment arrives at spoke, demand satisfied (inventory decreases)
- Days 6-7: No activity (inventory holding)

This test validates the bug fix where inventory tracking now correctly deducts demand
consumption using FIFO (first-in-first-out) strategy.
"""

import pytest
from datetime import date, timedelta
from typing import Dict, List

from src.analysis.daily_snapshot import (
    DailySnapshotGenerator,
    DailySnapshot,
)
from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.models.location import Location, LocationType, StorageMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.product import ProductState
from src.production.scheduler import ProductionSchedule


# ===========================
# Test Data Setup
# ===========================


class MockRouteLeg:
    """Mock route leg for testing."""
    def __init__(self, from_location_id: str, to_location_id: str, transit_days: int):
        self.from_location_id = from_location_id
        self.to_location_id = to_location_id
        self.transit_days = transit_days
        self.transport_mode = "ambient"


class MockRoute:
    """Mock route for testing."""
    def __init__(self, route_legs: List[MockRouteLeg]):
        self.route_legs = route_legs

    @property
    def total_transit_days(self) -> int:
        """Calculate total transit days."""
        return sum(leg.transit_days for leg in self.route_legs)


def _create_test_locations() -> Dict[str, Location]:
    """Create test network: 1 manufacturing + 2 hubs + 2 breadrooms."""
    return {
        "6122": Location(
            id="6122",
            name="Manufacturing Site",
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
        "6105": Location(
            id="6105",
            name="Breadroom NSW",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
            capacity=5000
        ),
    }


# ===========================
# Integration Test
# ===========================


def test_daily_snapshot_complete_flow_integration():
    """
    Integration test: Complete flow of production → shipment → demand.

    Validates that Daily Inventory Snapshot correctly tracks:
    - Production at manufacturing site
    - Inventory movement through shipments
    - Demand satisfaction from available inventory
    - Mass balance across the network (production - demand = inventory + in-transit)

    Day-by-Day Scenario:
    - Day 1 (2025-10-13 Monday): Produce 1,000 units of WW at 6122
    - Day 2 (2025-10-14 Tuesday): Ship 600 units (6122 → 6104, 1-day transit)
    - Day 3 (2025-10-15 Wednesday): Arrival at 6104, demand 300 units (consumed from inventory)
    - Day 4 (2025-10-16 Thursday): Produce 800 units, ship 200 units (6104 → 6103, 1-day transit)
    - Day 5 (2025-10-17 Friday): Arrival at 6103, demand 150 units (consumed from inventory)
    - Days 6-7: Inventory holding, no activity
    """
    # Setup dates
    day1 = date(2025, 10, 13)  # Monday - Production
    day2 = date(2025, 10, 14)  # Tuesday - Shipment departure
    day3 = date(2025, 10, 15)  # Wednesday - Arrival + Demand
    day4 = date(2025, 10, 16)  # Thursday - Production + Hub shipment
    day5 = date(2025, 10, 17)  # Friday - Arrival + Demand
    day6 = date(2025, 10, 18)  # Saturday - Holding
    day7 = date(2025, 10, 19)  # Sunday - Holding

    # Create locations
    locations_dict = _create_test_locations()

    # ==================
    # Production Batches
    # ==================
    batch1 = ProductionBatch(
        id="BATCH-001",
        product_id="WW",  # White Wonder product
        manufacturing_site_id="6122",
        production_date=day1,
        quantity=1000.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.72,
        production_cost=500.0
    )

    batch2 = ProductionBatch(
        id="BATCH-002",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=day4,
        quantity=800.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.57,
        production_cost=400.0
    )

    production_schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=day1,
        schedule_end_date=day4,
        production_batches=[batch1, batch2],
        daily_totals={
            day1: 1000.0,
            day4: 800.0
        },
        daily_labor_hours={
            day1: 0.72,
            day4: 0.57
        },
        infeasibilities=[],
        total_units=1800.0,
        total_labor_hours=1.29
    )

    # ==================
    # Shipments
    # ==================

    # Shipment 1: 6122 → 6104 (600 units, 1-day transit)
    # Departs Day 2, arrives Day 3
    route_6122_to_6104 = MockRoute(route_legs=[
        MockRouteLeg("6122", "6104", 1)
    ])

    shipment1 = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="WW",
        quantity=600.0,
        origin_id="6122",
        destination_id="6104",
        delivery_date=day3,  # Arrives Day 3
        route=route_6122_to_6104,
        production_date=day1
    )

    # Shipment 2: 6104 → 6103 (200 units, 1-day transit)
    # Departs Day 4, arrives Day 5
    route_6104_to_6103 = MockRoute(route_legs=[
        MockRouteLeg("6104", "6103", 1)
    ])

    shipment2 = Shipment(
        id="SHIP-002",
        batch_id="BATCH-001",  # From same batch as shipment1
        product_id="WW",
        quantity=200.0,
        origin_id="6104",
        destination_id="6103",
        delivery_date=day5,  # Arrives Day 5
        route=route_6104_to_6103,
        production_date=day1
    )

    shipments = [shipment1, shipment2]

    # ==================
    # Forecast (Demand)
    # ==================
    forecast = Forecast(
        name="Integration Test Forecast",
        entries=[
            # Day 3: 300 units demand at 6104
            ForecastEntry(
                location_id="6104",
                product_id="WW",
                forecast_date=day3,
                quantity=300.0
            ),
            # Day 5: 150 units demand at 6103
            ForecastEntry(
                location_id="6103",
                product_id="WW",
                forecast_date=day5,
                quantity=150.0
            ),
        ]
    )

    # ==================
    # Generate Snapshots
    # ==================
    generator = DailySnapshotGenerator(
        production_schedule=production_schedule,
        shipments=shipments,
        locations_dict=locations_dict,
        forecast=forecast
    )

    snapshots_list = generator.generate_snapshots(day1, day7)

    # Convert list to dict for easier access
    snapshots = {snapshot.date: snapshot for snapshot in snapshots_list}

    # ==================
    # Validation
    # ==================

    # ===== DAY 1 (Monday): Production =====
    print("\n===== DAY 1 (Monday): Production =====")
    snapshot_day1 = snapshots[day1]

    # Production appears at manufacturing site
    assert "6122" in snapshot_day1.location_inventory, "Manufacturing site should appear"
    assert snapshot_day1.location_inventory["6122"].total_quantity == 1000.0, \
        "Day 1: 6122 should have 1,000 units from production"

    # Check production activity
    assert len(snapshot_day1.production_activity) == 1, "Day 1: Should have 1 batch produced"
    assert snapshot_day1.production_activity[0].batch_id == "BATCH-001"
    assert snapshot_day1.production_activity[0].quantity == 1000.0

    # No shipments yet
    assert len(snapshot_day1.in_transit) == 0, "Day 1: No shipments should be in transit"

    # All locations should appear (even with zero inventory)
    assert len(snapshot_day1.location_inventory) == 5, \
        "Day 1: All 5 locations should appear in snapshot"
    assert snapshot_day1.location_inventory["6104"].total_quantity == 0.0
    assert snapshot_day1.location_inventory["6103"].total_quantity == 0.0

    print(f"✓ Day 1: 6122 has {snapshot_day1.location_inventory['6122'].total_quantity:.0f} units")
    print(f"✓ Day 1: Production of {snapshot_day1.production_activity[0].quantity:.0f} units")

    # ===== DAY 2 (Tuesday): Shipment Departure =====
    print("\n===== DAY 2 (Tuesday): Shipment Departure =====")
    snapshot_day2 = snapshots[day2]

    # Inventory at 6122 should decrease (600 units shipped)
    assert snapshot_day2.location_inventory["6122"].total_quantity == 400.0, \
        "Day 2: 6122 should have 400 units (1000 - 600 shipped)"

    # Shipment should be in transit
    assert len(snapshot_day2.in_transit) == 1, "Day 2: 1 shipment should be in transit"
    assert snapshot_day2.in_transit[0].shipment_id == "SHIP-001"
    assert snapshot_day2.in_transit[0].quantity == 600.0
    assert snapshot_day2.in_transit[0].origin_id == "6122"
    assert snapshot_day2.in_transit[0].destination_id == "6104"
    assert snapshot_day2.in_transit[0].days_in_transit == 0, "Day 2: Just departed"

    # 6104 should still have zero inventory (shipment not arrived yet)
    assert snapshot_day2.location_inventory["6104"].total_quantity == 0.0, \
        "Day 2: 6104 should have 0 units (shipment not arrived yet)"

    print(f"✓ Day 2: 6122 has {snapshot_day2.location_inventory['6122'].total_quantity:.0f} units")
    print(f"✓ Day 2: {len(snapshot_day2.in_transit)} shipment in transit (600 units)")

    # ===== DAY 3 (Wednesday): Arrival + Demand =====
    print("\n===== DAY 3 (Wednesday): Arrival + Demand =====")
    snapshot_day3 = snapshots[day3]

    # Shipment arrives at 6104, then 300 units consumed by demand
    # Expected: 600 (arrived) - 300 (demand) = 300 units remaining
    assert snapshot_day3.location_inventory["6104"].total_quantity == 300.0, \
        "Day 3: 6104 should have 300 units (600 arrived - 300 demand consumed)"

    # No shipments in transit (arrived)
    assert len(snapshot_day3.in_transit) == 0, "Day 3: No shipments in transit (delivered)"

    # Demand satisfaction (CRITICAL TEST - Bug Fix Validation)
    assert len(snapshot_day3.demand_satisfied) == 1, "Day 3: Should have 1 demand record"
    demand_record = snapshot_day3.demand_satisfied[0]

    assert demand_record.destination_id == "6104"
    assert demand_record.product_id == "WW"
    assert demand_record.demand_quantity == 300.0, "Day 3: Demand is 300 units"
    assert demand_record.supplied_quantity == 300.0, \
        "Day 3: CRITICAL - 300 units supplied (consumed from 600 available)"
    assert demand_record.shortage_quantity == 0.0, "Day 3: No shortage"
    assert demand_record.is_satisfied, "Day 3: Demand should be fully satisfied"
    assert demand_record.fill_rate == 1.0, "Day 3: 100% fill rate"

    # 6122 still has 400 units
    assert snapshot_day3.location_inventory["6122"].total_quantity == 400.0

    print(f"✓ Day 3: 6104 has {snapshot_day3.location_inventory['6104'].total_quantity:.0f} units (after demand)")
    print(f"✓ Day 3: Demand satisfied - {demand_record.supplied_quantity:.0f}/{demand_record.demand_quantity:.0f} units")

    # ===== DAY 4 (Thursday): New Production + Hub Shipment =====
    print("\n===== DAY 4 (Thursday): New Production + Hub Shipment =====")
    snapshot_day4 = snapshots[day4]

    # New production at 6122
    assert len(snapshot_day4.production_activity) == 1, "Day 4: Should have 1 batch produced"
    assert snapshot_day4.production_activity[0].batch_id == "BATCH-002"
    assert snapshot_day4.production_activity[0].quantity == 800.0

    # 6122 should have 400 (remaining) + 800 (new production) = 1,200 units
    assert snapshot_day4.location_inventory["6122"].total_quantity == 1200.0, \
        "Day 4: 6122 should have 1,200 units (400 + 800 new)"

    # 6104 ships 200 units to 6103
    # Departure date = day5 - 1 = day4
    # 6104 should have 300 - 200 = 100 units after shipment departs
    assert snapshot_day4.location_inventory["6104"].total_quantity == 100.0, \
        "Day 4: 6104 should have 100 units (300 - 200 shipped)"

    # Shipment should be in transit
    assert len(snapshot_day4.in_transit) == 1, "Day 4: 1 shipment should be in transit"
    assert snapshot_day4.in_transit[0].shipment_id == "SHIP-002"
    assert snapshot_day4.in_transit[0].quantity == 200.0
    assert snapshot_day4.in_transit[0].origin_id == "6104"
    assert snapshot_day4.in_transit[0].destination_id == "6103"

    print(f"✓ Day 4: 6122 has {snapshot_day4.location_inventory['6122'].total_quantity:.0f} units")
    print(f"✓ Day 4: 6104 has {snapshot_day4.location_inventory['6104'].total_quantity:.0f} units")
    print(f"✓ Day 4: Production of {snapshot_day4.production_activity[0].quantity:.0f} units")

    # ===== DAY 5 (Friday): Arrival + Demand =====
    print("\n===== DAY 5 (Friday): Arrival + Demand =====")
    snapshot_day5 = snapshots[day5]

    # Shipment arrives at 6103, then 150 units consumed by demand
    # Expected: 200 (arrived) - 150 (demand) = 50 units remaining
    assert snapshot_day5.location_inventory["6103"].total_quantity == 50.0, \
        "Day 5: 6103 should have 50 units (200 arrived - 150 demand consumed)"

    # No shipments in transit
    assert len(snapshot_day5.in_transit) == 0, "Day 5: No shipments in transit"

    # Demand satisfaction
    assert len(snapshot_day5.demand_satisfied) == 1, "Day 5: Should have 1 demand record"
    demand_record_day5 = snapshot_day5.demand_satisfied[0]

    assert demand_record_day5.destination_id == "6103"
    assert demand_record_day5.product_id == "WW"
    assert demand_record_day5.demand_quantity == 150.0
    assert demand_record_day5.supplied_quantity == 150.0, \
        "Day 5: 150 units supplied (consumed from 200 available)"
    assert demand_record_day5.shortage_quantity == 0.0
    assert demand_record_day5.is_satisfied

    # Other locations unchanged
    assert snapshot_day5.location_inventory["6122"].total_quantity == 1200.0
    assert snapshot_day5.location_inventory["6104"].total_quantity == 100.0

    print(f"✓ Day 5: 6103 has {snapshot_day5.location_inventory['6103'].total_quantity:.0f} units (after demand)")
    print(f"✓ Day 5: Demand satisfied - {demand_record_day5.supplied_quantity:.0f}/{demand_record_day5.demand_quantity:.0f} units")

    # ===== DAY 6 (Saturday): Inventory Holding =====
    print("\n===== DAY 6 (Saturday): Inventory Holding =====")
    snapshot_day6 = snapshots[day6]

    # No activity, inventory remains
    assert snapshot_day6.location_inventory["6122"].total_quantity == 1200.0
    assert snapshot_day6.location_inventory["6104"].total_quantity == 100.0
    assert snapshot_day6.location_inventory["6103"].total_quantity == 50.0
    assert len(snapshot_day6.in_transit) == 0
    assert len(snapshot_day6.production_activity) == 0

    print(f"✓ Day 6: No activity, inventory held")

    # ===== DAY 7 (Sunday): Inventory Holding =====
    print("\n===== DAY 7 (Sunday): Inventory Holding =====")
    snapshot_day7 = snapshots[day7]

    # No activity, inventory remains
    assert snapshot_day7.location_inventory["6122"].total_quantity == 1200.0
    assert snapshot_day7.location_inventory["6104"].total_quantity == 100.0
    assert snapshot_day7.location_inventory["6103"].total_quantity == 50.0

    print(f"✓ Day 7: No activity, inventory held")

    # ==================
    # Mass Balance Validation
    # ==================
    print("\n===== Mass Balance Validation =====")

    # Helper function to validate mass balance
    def validate_mass_balance(snapshot: DailySnapshot, expected_production: float, expected_demand: float) -> None:
        """
        Validate mass balance: production - demand = inventory + in-transit.

        Args:
            snapshot: Daily snapshot to validate
            expected_production: Total production up to this date
            expected_demand: Total demand consumed up to this date
        """
        total_on_hand = snapshot.total_system_inventory
        total_in_transit = snapshot.total_in_transit
        total_inventory = total_on_hand + total_in_transit

        # Mass balance: production - demand = inventory
        expected_inventory = expected_production - expected_demand

        # Allow small rounding errors
        assert abs(total_inventory - expected_inventory) < 0.1, \
            f"Mass balance failed on {snapshot.date}: " \
            f"inventory={total_inventory:.1f}, expected={expected_inventory:.1f} " \
            f"(production={expected_production:.1f}, demand={expected_demand:.1f})"

        return total_on_hand, total_in_transit

    # Day 1: Production=1000, Demand=0
    on_hand, in_transit = validate_mass_balance(snapshot_day1, 1000.0, 0.0)
    print(f"✓ Day 1: Mass balance OK - {on_hand:.0f} on-hand + {in_transit:.0f} in-transit = 1000.0 production")

    # Day 2: Production=1000, Demand=0 (shipment in transit)
    on_hand, in_transit = validate_mass_balance(snapshot_day2, 1000.0, 0.0)
    print(f"✓ Day 2: Mass balance OK - {on_hand:.0f} on-hand + {in_transit:.0f} in-transit = 1000.0 production")

    # Day 3: Production=1000, Demand=300 (demand consumed from inventory)
    # NEW SEMANTICS: Inventory AFTER demand consumption
    # Expected: 1000 - 300 = 700 total inventory
    on_hand, in_transit = validate_mass_balance(snapshot_day3, 1000.0, 300.0)
    print(f"✓ Day 3: Mass balance OK - {on_hand:.0f} on-hand + {in_transit:.0f} in-transit = 700.0 (1000 prod - 300 demand)")
    print(f"  (Note: Snapshot shows inventory AFTER demand consumption)")

    # Day 4: Production=1800, Demand=300
    on_hand, in_transit = validate_mass_balance(snapshot_day4, 1800.0, 300.0)
    print(f"✓ Day 4: Mass balance OK - {on_hand:.0f} on-hand + {in_transit:.0f} in-transit = 1500.0 (1800 prod - 300 demand)")

    # Day 5: Production=1800, Demand=450 (300 + 150)
    on_hand, in_transit = validate_mass_balance(snapshot_day5, 1800.0, 450.0)
    print(f"✓ Day 5: Mass balance OK - {on_hand:.0f} on-hand + {in_transit:.0f} in-transit = 1350.0 (1800 prod - 450 demand)")

    # Days 6-7: Same as Day 5
    validate_mass_balance(snapshot_day6, 1800.0, 450.0)
    validate_mass_balance(snapshot_day7, 1800.0, 450.0)
    print(f"✓ Days 6-7: Mass balance OK")

    # ==================
    # Summary Statistics
    # ==================
    print("\n===== Summary Statistics =====")
    print(f"Total production: 1,800 units (Day 1: 1,000 + Day 4: 800)")
    print(f"Total demand: 450 units (Day 3: 300 + Day 5: 150)")
    print(f"Total shipments: 2 (SHIP-001: 600 units, SHIP-002: 200 units)")
    print(f"Final inventory: 1,350 units (after demand consumption)")
    print(f"  - 6122: 1,200 units")
    print(f"  - 6104: 100 units")
    print(f"  - 6103: 50 units")
    print(f"\n✓✓✓ ALL VALIDATIONS PASSED ✓✓✓")
    print(f"\nThis test confirms:")
    print(f"  ✓ Production appears at manufacturing site")
    print(f"  ✓ Inventory transfers from manufacturing → hub → spoke")
    print(f"  ✓ Inventory decreases with shipments and demand (FIFO consumption)")
    print(f"  ✓ Mass balance is maintained throughout (production - demand = inventory)")
    print(f"  ✓ Demand is consumed from available inventory using FIFO strategy")
    print(f"  ✓ All locations appear in snapshots (even with zero inventory)")


def test_daily_snapshot_mass_balance_with_demand():
    """
    Test mass balance when demand is consumed from inventory.

    This validates that:
    - Available inventory is correctly calculated before consumption
    - Demand records show what was satisfied
    - Ending inventory reflects consumed demand
    - No inventory "leaks" occur
    """
    day1 = date(2025, 10, 13)
    day2 = date(2025, 10, 14)
    day3 = date(2025, 10, 15)

    locations_dict = {
        "6122": Location(
            id="6122", name="Mfg", type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.AMBIENT
        ),
        "6103": Location(
            id="6103", name="Dest", type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT
        ),
    }

    # Production: 1000 units
    batch = ProductionBatch(
        id="BATCH-001",
        product_id="WW",
        manufacturing_site_id="6122",
        production_date=day1,
        quantity=1000.0,
        initial_state=ProductState.AMBIENT,
        labor_hours_used=0.72,
        production_cost=500.0
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=day1,
        schedule_end_date=day1,
        production_batches=[batch],
        daily_totals={day1: 1000.0},
        daily_labor_hours={day1: 0.72},
        infeasibilities=[],
        total_units=1000.0,
        total_labor_hours=0.72
    )

    # Shipment: 1000 units to 6103
    route = MockRoute(route_legs=[MockRouteLeg("6122", "6103", 1)])

    shipment = Shipment(
        id="SHIP-001",
        batch_id="BATCH-001",
        product_id="WW",
        quantity=1000.0,
        origin_id="6122",
        destination_id="6103",
        delivery_date=day3,  # Arrives Day 3
        route=route,
        production_date=day1
    )

    # Demand: 600 units on Day 3
    forecast = Forecast(
        name="Test",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="WW",
                forecast_date=day3,
                quantity=600.0
            )
        ]
    )

    generator = DailySnapshotGenerator(schedule, [shipment], locations_dict, forecast)

    # Day 1: Production
    snapshot_day1 = generator._generate_single_snapshot(day1)
    assert snapshot_day1.total_system_inventory == 1000.0

    # Day 2: In transit (departs day2, arrives day3)
    snapshot_day2 = generator._generate_single_snapshot(day2)
    assert snapshot_day2.total_system_inventory + snapshot_day2.total_in_transit == 1000.0

    # Day 3: At destination, demand consumed
    snapshot_day3 = generator._generate_single_snapshot(day3)
    # After 600 units consumed: 1000 - 600 = 400 remaining
    assert snapshot_day3.location_inventory["6103"].total_quantity == 400.0
    assert snapshot_day3.demand_satisfied[0].supplied_quantity == 600.0
    assert snapshot_day3.demand_satisfied[0].demand_quantity == 600.0
    assert snapshot_day3.demand_satisfied[0].is_satisfied

    # Total inventory should be 400 (after consumption)
    assert snapshot_day3.total_system_inventory == 400.0

    print("✓ Mass balance with demand: PASSED")


def test_daily_snapshot_multi_location_flows():
    """
    Test complex scenario with multiple locations receiving shipments.

    Validates that inventory tracking works correctly when:
    - Multiple destinations receive shipments
    - Different products flow through the network
    - Hub locations act as waypoints
    """
    day1 = date(2025, 10, 13)
    day2 = date(2025, 10, 14)
    day3 = date(2025, 10, 15)

    locations_dict = _create_test_locations()

    # Two batches, two products
    batch1 = ProductionBatch(
        id="BATCH-001", product_id="WW",
        manufacturing_site_id="6122", production_date=day1,
        quantity=1000.0, initial_state=ProductState.AMBIENT,
        labor_hours_used=0.72, production_cost=500.0
    )

    batch2 = ProductionBatch(
        id="BATCH-002", product_id="SD",  # Soy & Linseed
        manufacturing_site_id="6122", production_date=day1,
        quantity=800.0, initial_state=ProductState.AMBIENT,
        labor_hours_used=0.57, production_cost=400.0
    )

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=day1,
        schedule_end_date=day1,
        production_batches=[batch1, batch2],
        daily_totals={day1: 1800.0},
        daily_labor_hours={day1: 1.29},
        infeasibilities=[],
        total_units=1800.0,
        total_labor_hours=1.29
    )

    # Two shipments to different destinations
    # Note: departure_date = delivery_date - transit_days
    # For delivery on day2 with transit=1, departure is on day1
    route1 = MockRoute(route_legs=[MockRouteLeg("6122", "6104", 1)])
    route2 = MockRoute(route_legs=[MockRouteLeg("6122", "6125", 1)])

    shipment1 = Shipment(
        id="SHIP-001", batch_id="BATCH-001", product_id="WW",
        quantity=600.0, origin_id="6122", destination_id="6104",
        delivery_date=day2, route=route1, production_date=day1
    )

    shipment2 = Shipment(
        id="SHIP-002", batch_id="BATCH-002", product_id="SD",
        quantity=500.0, origin_id="6122", destination_id="6125",
        delivery_date=day2, route=route2, production_date=day1
    )

    forecast = Forecast(name="Test", entries=[])

    generator = DailySnapshotGenerator(schedule, [shipment1, shipment2], locations_dict, forecast)

    # Day 1: Production + shipments depart same day
    # Departure on day1 means inventory immediately reduced
    snapshot_day1 = generator._generate_single_snapshot(day1)
    # Manufacturing should have: 1800 produced - 600 - 500 shipped = 700
    assert snapshot_day1.location_inventory["6122"].total_quantity == 700.0
    assert snapshot_day1.location_inventory["6122"].by_product["WW"] == 400.0  # 1000 - 600
    assert snapshot_day1.location_inventory["6122"].by_product["SD"] == 300.0  # 800 - 500

    # Should have 2 shipments in transit on day1 (just departed)
    assert len(snapshot_day1.in_transit) == 2

    # Day 2: Shipments arrive (transit complete)
    snapshot_day2 = generator._generate_single_snapshot(day2)

    # Manufacturing should still have 700
    assert snapshot_day2.location_inventory["6122"].total_quantity == 700.0

    # No shipments in transit (all delivered on day2)
    assert len(snapshot_day2.in_transit) == 0

    # Day 3: Arrived at hubs (inventory from day2 persists)
    snapshot_day3 = generator._generate_single_snapshot(day3)
    assert snapshot_day3.location_inventory["6104"].total_quantity == 600.0
    assert snapshot_day3.location_inventory["6125"].total_quantity == 500.0
    assert len(snapshot_day3.in_transit) == 0

    # Mass balance: 700 + 600 + 500 = 1800
    total_inventory = sum(loc.total_quantity for loc in snapshot_day3.location_inventory.values())
    assert abs(total_inventory - 1800.0) < 0.1

    print("✓ Multi-location flows: PASSED")


if __name__ == "__main__":
    # Run tests
    print("=" * 80)
    print("DAILY INVENTORY SNAPSHOT - COMPREHENSIVE INTEGRATION TEST")
    print("=" * 80)

    test_daily_snapshot_complete_flow_integration()

    print("\n" + "=" * 80)
    print("ADDITIONAL VALIDATION TESTS")
    print("=" * 80)

    test_daily_snapshot_mass_balance_with_demand()
    test_daily_snapshot_multi_location_flows()

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED SUCCESSFULLY")
    print("=" * 80)
