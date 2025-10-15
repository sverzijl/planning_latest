"""Test legacy to unified data conversion."""

import pytest
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.unified_truck_schedule import DayOfWeek


def test_convert_nodes():
    """Test converting legacy locations to unified nodes."""

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Find manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Convert
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)

    # Assertions
    assert len(nodes) > 0, "Should have converted nodes"

    # Find manufacturing node
    mfg_node = next((n for n in nodes if n.id == manufacturing_site.id), None)
    assert mfg_node is not None, "Manufacturing site should be converted"
    assert mfg_node.can_produce(), "Manufacturing node should have production capability"
    assert mfg_node.capabilities.production_rate_per_hour == 1400.0
    assert mfg_node.requires_trucks(), "Manufacturing should require truck schedules"

    # Find a hub node (6125)
    hub_node = next((n for n in nodes if n.id == '6125'), None)
    assert hub_node is not None, "Hub 6125 should exist"
    assert hub_node.has_demand_capability(), "Hub 6125 has demand in forecast"
    assert not hub_node.can_produce(), "Hub cannot manufacture"
    assert not hub_node.requires_trucks(), "Hubs don't require trucks (legacy behavior)"

    # Find frozen storage (Lineage)
    lineage_node = next((n for n in nodes if n.id == 'Lineage'), None)
    if lineage_node:
        assert lineage_node.supports_frozen_storage(), "Lineage should support frozen"
        assert not lineage_node.has_demand_capability(), "Lineage has no demand"

    print(f"✅ Converted {len(nodes)} locations to unified nodes")
    print(f"   Manufacturing nodes: {sum(1 for n in nodes if n.can_produce())}")
    print(f"   Demand nodes: {sum(1 for n in nodes if n.has_demand_capability())}")
    print(f"   Nodes requiring trucks: {sum(1 for n in nodes if n.requires_trucks())}")


def test_convert_routes():
    """Test converting legacy routes to unified routes."""

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    _, _, routes, _, _, _ = parser.parse_all()

    # Convert
    converter = LegacyToUnifiedConverter()
    unified_routes = converter.convert_routes(routes)

    # Assertions
    assert len(unified_routes) == len(routes), "Should convert all routes"

    # Check a frozen route (Lineage → 6130)
    frozen_route = next((r for r in unified_routes if r.origin_node_id == 'Lineage' and r.destination_node_id == '6130'), None)
    if frozen_route:
        assert frozen_route.is_frozen_transport(), "Lineage→6130 should be frozen"
        assert frozen_route.transit_days == 3.0, "Transit time should be preserved"

    # Check an ambient route (6122 → 6125)
    ambient_route = next((r for r in unified_routes if r.origin_node_id == '6122' and r.destination_node_id == '6125'), None)
    if ambient_route:
        assert ambient_route.is_ambient_transport(), "6122→6125 should be ambient"
        assert ambient_route.transit_days == 1.0, "Transit time should be preserved"

    print(f"✅ Converted {len(unified_routes)} routes")
    print(f"   Frozen routes: {sum(1 for r in unified_routes if r.is_frozen_transport())}")
    print(f"   Ambient routes: {sum(1 for r in unified_routes if r.is_ambient_transport())}")


def test_convert_truck_schedules():
    """Test converting legacy truck schedules to unified format."""

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, _, _, truck_schedules_list, _ = parser.parse_all()

    # Find manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Convert
    converter = LegacyToUnifiedConverter()
    unified_trucks = converter.convert_truck_schedules(
        truck_schedules_list,
        manufacturing_site.id
    )

    # Assertions
    assert len(unified_trucks) == len(truck_schedules_list), "Should convert all trucks"

    # All trucks should have origin_node_id = manufacturing site (in legacy data)
    for truck in unified_trucks:
        assert truck.origin_node_id == manufacturing_site.id, \
            f"Truck {truck.id} should originate from manufacturing"

    # Check day-specific truck (T1 = Monday)
    t1 = next((t for t in unified_trucks if t.id == 'T1'), None)
    if t1:
        assert t1.day_of_week == DayOfWeek.MONDAY, "T1 should run Monday only"
        assert t1.is_day_specific()

        # Test day applicability
        from datetime import date
        monday = date(2025, 10, 13)
        tuesday = date(2025, 10, 14)
        assert t1.applies_on_date(monday)
        assert not t1.applies_on_date(tuesday)

    # Check Wednesday Lineage truck
    t3 = next((t for t in unified_trucks if t.id == 'T3'), None)
    if t3:
        assert t3.day_of_week == DayOfWeek.WEDNESDAY
        assert t3.has_intermediate_stops()
        assert 'Lineage' in t3.intermediate_stops

    print(f"✅ Converted {len(unified_trucks)} truck schedules")
    print(f"   All originate from: {manufacturing_site.id}")
    print(f"   Day-specific trucks: {sum(1 for t in unified_trucks if t.is_day_specific())}")
    print(f"   Daily trucks: {sum(1 for t in unified_trucks if not t.is_day_specific())}")


def test_convert_all():
    """Test converting all data in one call."""

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, _, truck_schedules_list, _ = parser.parse_all()

    # Find manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Convert everything
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site,
        locations,
        routes,
        truck_schedules_list,
        forecast
    )

    # Assertions
    assert len(nodes) > 0
    assert len(unified_routes) > 0
    assert len(unified_trucks) > 0

    # Verify node IDs match original locations + manufacturing
    expected_node_ids = {manufacturing_site.id} | {loc.id for loc in locations}
    actual_node_ids = {n.id for n in nodes}
    assert actual_node_ids == expected_node_ids, "Node IDs should match original locations"

    print(f"✅ Full conversion successful")
    print(f"   Nodes: {len(nodes)}")
    print(f"   Routes: {len(unified_routes)}")
    print(f"   Trucks: {len(unified_trucks)}")


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
