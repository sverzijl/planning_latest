"""Test unified data models (UnifiedNode, UnifiedRoute, UnifiedTruckSchedule)."""

import pytest
from datetime import time, date
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.unified_truck_schedule import UnifiedTruckSchedule, DayOfWeek, DepartureType


def test_unified_node_creation():
    """Test creating various types of unified nodes."""

    # Manufacturing node
    manufacturing = UnifiedNode(
        id="6122",
        name="Manufacturing Site",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            production_rate_per_hour=1400.0,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            requires_truck_schedules=True,
        )
    )

    assert manufacturing.can_produce()
    assert not manufacturing.has_demand_capability()
    assert manufacturing.supports_ambient_storage()
    assert not manufacturing.supports_frozen_storage()
    assert manufacturing.requires_trucks()
    assert manufacturing.get_production_state() == 'ambient'

    # Hub with demand
    hub = UnifiedNode(
        id="6125",
        name="VIC Hub",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            has_demand=True,
            requires_truck_schedules=False,  # Hub trucks not constrained (yet)
        )
    )

    assert not hub.can_produce()
    assert hub.has_demand_capability()
    assert hub.supports_ambient_storage()
    assert not hub.requires_trucks()

    # Frozen storage (Lineage)
    frozen_storage = UnifiedNode(
        id="Lineage",
        name="Lineage Frozen Storage",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.FROZEN,
            has_demand=False,
        )
    )

    assert not frozen_storage.can_produce()
    assert frozen_storage.supports_frozen_storage()
    assert not frozen_storage.supports_ambient_storage()
    assert not frozen_storage.can_freeze_thaw()

    # Freeze/thaw capable node (6130 - WA)
    thaw_node = UnifiedNode(
        id="6130",
        name="WA Breadroom",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.BOTH,  # Can handle both frozen and ambient
            has_demand=True,
        )
    )

    assert thaw_node.has_demand_capability()
    assert thaw_node.can_freeze_thaw()
    assert thaw_node.supports_frozen_storage()
    assert thaw_node.supports_ambient_storage()


def test_unified_route_creation():
    """Test creating unified routes."""

    # Ambient route
    ambient_route = UnifiedRoute(
        id="R1",
        origin_node_id="6122",
        destination_node_id="6125",
        transit_days=1.0,
        transport_mode=TransportMode.AMBIENT,
        cost_per_unit=0.30,
    )

    assert ambient_route.is_ambient_transport()
    assert not ambient_route.is_frozen_transport()
    assert not ambient_route.is_instant_transfer()

    # Frozen route
    frozen_route = UnifiedRoute(
        id="R10",
        origin_node_id="Lineage",
        destination_node_id="6130",
        transit_days=3.0,
        transport_mode=TransportMode.FROZEN,
        cost_per_unit=0.50,
    )

    assert frozen_route.is_frozen_transport()
    assert not frozen_route.is_ambient_transport()

    # Instant transfer route (0 days)
    instant_route = UnifiedRoute(
        id="R4",
        origin_node_id="6122",
        destination_node_id="Lineage",
        transit_days=0.5,  # Half day
        transport_mode=TransportMode.AMBIENT,
        cost_per_unit=0.20,
    )

    assert not instant_route.is_instant_transfer()  # 0.5 is not instant


def test_unified_truck_schedule_creation():
    """Test creating generalized truck schedules."""

    # Manufacturing truck (Monday only)
    mfg_truck = UnifiedTruckSchedule(
        id="T1",
        origin_node_id="6122",  # Explicit origin
        destination_node_id="6125",
        departure_type=DepartureType.MORNING,
        departure_time=time(8, 0),
        day_of_week=DayOfWeek.MONDAY,
        capacity=14080.0,
        cost_fixed=100.0,
        cost_per_unit=0.30,
    )

    assert mfg_truck.is_day_specific()
    assert mfg_truck.is_morning()
    assert not mfg_truck.is_afternoon()

    # Test day applicability
    monday = date(2025, 10, 13)  # Monday
    tuesday = date(2025, 10, 14)  # Tuesday

    assert mfg_truck.applies_on_date(monday)
    assert not mfg_truck.applies_on_date(tuesday)

    # Hub truck (NEW - not possible in legacy model)
    hub_truck = UnifiedTruckSchedule(
        id="T_HUB1",
        origin_node_id="6125",  # Hub origin!
        destination_node_id="6123",  # Spoke destination
        departure_type=DepartureType.MORNING,
        departure_time=time(8, 0),
        day_of_week=DayOfWeek.WEDNESDAY,  # Wednesday only
        capacity=14080.0,
    )

    assert hub_truck.origin_node_id == "6125"
    assert hub_truck.destination_node_id == "6123"

    wednesday = date(2025, 10, 15)
    assert hub_truck.applies_on_date(wednesday)
    assert not hub_truck.applies_on_date(monday)

    # Daily truck (no day_of_week constraint)
    daily_truck = UnifiedTruckSchedule(
        id="T_DAILY",
        origin_node_id="6104",
        destination_node_id="6105",
        departure_type=DepartureType.AFTERNOON,
        departure_time=time(14, 0),
        day_of_week=None,  # Runs every day
        capacity=14080.0,
    )

    assert not daily_truck.is_day_specific()
    assert daily_truck.applies_on_date(monday)
    assert daily_truck.applies_on_date(tuesday)
    assert daily_truck.applies_on_date(wednesday)


def test_pallet_calculations():
    """Test pallet calculation logic."""

    truck = UnifiedTruckSchedule(
        id="T1",
        origin_node_id="6122",
        destination_node_id="6125",
        departure_type=DepartureType.MORNING,
        departure_time=time(8, 0),
        capacity=14080.0,
        pallet_capacity=44,
        units_per_pallet=320,
    )

    # Full truck load
    assert truck.calculate_required_pallets(14080) == 44

    # Partial pallet (rounds up)
    assert truck.calculate_required_pallets(321) == 2  # Needs 2 pallets for 321 units
    assert truck.calculate_required_pallets(320) == 1
    assert truck.calculate_required_pallets(10) == 1  # Even 10 units needs 1 pallet

    # Zero
    assert truck.calculate_required_pallets(0) == 0


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
