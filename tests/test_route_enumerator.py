"""Tests for route enumerator utility.

Tests route enumeration functionality for optimization models.
"""

import pytest

from src.optimization.route_enumerator import RouteEnumerator, EnumeratedRoute
from src.network import NetworkGraphBuilder
from src.models import Location, LocationType, StorageMode, Route


@pytest.fixture
def simple_network():
    """
    Create a simple test network:
        MFG (6122)
        ├── HUB1 (6104) → DEST1 (6105)
        │               → DEST2 (6103)
        └── DEST3 (6110) [direct]

    Routes:
    - 6122 → 6104 (cost: 0.2, 2 days)
    - 6104 → 6105 (cost: 0.1, 1 day)
    - 6104 → 6103 (cost: 0.15, 1 day)
    - 6122 → 6110 (cost: 0.4, 3 days) [direct]

    Possible paths:
    - To 6105: 6122 → 6104 → 6105 (cost: 0.3, 3 days)
    - To 6103: 6122 → 6104 → 6103 (cost: 0.35, 3 days)
    - To 6110: 6122 → 6110 (cost: 0.4, 3 days)
    - To 6104: 6122 → 6104 (cost: 0.2, 2 days)
    """
    # Create locations
    manufacturing = Location(
        id="6122",
        name="Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT,
    )

    hub1 = Location(
        id="6104",
        name="Hub 1",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.AMBIENT,
    )

    dest1 = Location(
        id="6105",
        name="Destination 1",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )

    dest2 = Location(
        id="6103",
        name="Destination 2",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )

    dest3 = Location(
        id="6110",
        name="Destination 3 (Direct)",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )

    # Create routes
    routes = [
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6104",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=2.0,
            cost=0.2,
        ),
        Route(
            id="R2",
            origin_id="6104",
            destination_id="6105",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.1,
        ),
        Route(
            id="R3",
            origin_id="6104",
            destination_id="6103",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.15,
        ),
        Route(
            id="R4",
            origin_id="6122",
            destination_id="6110",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=3.0,
            cost=0.4,
        ),
    ]

    # Build graph
    locations = [manufacturing, hub1, dest1, dest2, dest3]
    graph_builder = NetworkGraphBuilder(locations, routes)
    graph_builder.build_graph()  # Build the graph

    return graph_builder


class TestRouteEnumerator:
    """Tests for RouteEnumerator class."""

    def test_init(self, simple_network):
        """Test RouteEnumerator initialization."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=3
        )

        assert enumerator.manufacturing_site_id == "6122"
        assert enumerator.max_routes_per_destination == 3
        assert enumerator.get_total_route_count() == 0  # No routes enumerated yet

    def test_enumerate_single_hop_routes(self, simple_network):
        """Test enumerating direct (single-hop) routes."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        # Enumerate route to direct destination (6110)
        routes = enumerator.enumerate_routes_for_destinations(
            destinations=["6110"],
            rank_by='cost'
        )

        assert "6110" in routes
        assert len(routes["6110"]) == 1  # Only one path to 6110

        route = routes["6110"][0]
        assert route.origin_id == "6122"
        assert route.destination_id == "6110"
        assert route.total_cost == pytest.approx(0.4)
        assert route.total_transit_days == 3
        assert route.path == ["6122", "6110"]
        assert route.num_hops == 1

    def test_enumerate_multi_hop_routes(self, simple_network):
        """Test enumerating multi-hop routes (via hub)."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        # Enumerate route to destination via hub (6105)
        routes = enumerator.enumerate_routes_for_destinations(
            destinations=["6105"],
            rank_by='cost'
        )

        assert "6105" in routes
        assert len(routes["6105"]) == 1  # Only one path to 6105

        route = routes["6105"][0]
        assert route.origin_id == "6122"
        assert route.destination_id == "6105"
        assert route.total_cost == pytest.approx(0.3)  # 0.2 + 0.1
        assert route.total_transit_days == 3  # 2 + 1
        assert route.path == ["6122", "6104", "6105"]
        assert route.num_hops == 2

    def test_enumerate_multiple_destinations(self, simple_network):
        """Test enumerating routes to multiple destinations."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        routes = enumerator.enumerate_routes_for_destinations(
            destinations=["6105", "6103", "6110"],
            rank_by='cost'
        )

        assert len(routes) == 3
        assert "6105" in routes
        assert "6103" in routes
        assert "6110" in routes

        # Verify total route count
        total = enumerator.get_total_route_count()
        assert total == 3  # One route to each destination

    def test_get_route_by_index(self, simple_network):
        """Test retrieving route by index."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        enumerator.enumerate_routes_for_destinations(
            destinations=["6105", "6103"],
            rank_by='cost'
        )

        # Get route by index
        route_0 = enumerator.get_route(0)
        assert route_0 is not None
        assert route_0.index == 0

        route_1 = enumerator.get_route(1)
        assert route_1 is not None
        assert route_1.index == 1

        # Non-existent route
        route_99 = enumerator.get_route(99)
        assert route_99 is None

    def test_get_route_cost(self, simple_network):
        """Test getting route cost by index."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        enumerator.enumerate_routes_for_destinations(
            destinations=["6105"],
            rank_by='cost'
        )

        cost = enumerator.get_route_cost(0)
        assert cost == pytest.approx(0.3)  # 6122 → 6104 → 6105

    def test_get_route_transit_time(self, simple_network):
        """Test getting route transit time by index."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        enumerator.enumerate_routes_for_destinations(
            destinations=["6105"],
            rank_by='cost'
        )

        transit_time = enumerator.get_route_transit_time(0)
        assert transit_time == 3  # 2 + 1 days

    def test_get_routes_to_destination(self, simple_network):
        """Test getting all routes to a specific destination."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        enumerator.enumerate_routes_for_destinations(
            destinations=["6105", "6103"],
            rank_by='cost'
        )

        # Get routes to 6105
        routes_to_6105 = enumerator.get_routes_to_destination("6105")
        assert len(routes_to_6105) == 1
        assert 0 in routes_to_6105 or 1 in routes_to_6105  # Index depends on order

        # Get routes to non-enumerated destination
        routes_to_6999 = enumerator.get_routes_to_destination("6999")
        assert len(routes_to_6999) == 0

    def test_get_all_destinations(self, simple_network):
        """Test getting all enumerated destinations."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        enumerator.enumerate_routes_for_destinations(
            destinations=["6105", "6103", "6110"],
            rank_by='cost'
        )

        destinations = enumerator.get_all_destinations()
        assert len(destinations) == 3
        assert "6105" in destinations
        assert "6103" in destinations
        assert "6110" in destinations

    def test_rank_by_cost(self):
        """Test ranking routes by cost."""
        # Create network with multiple routes to same destination
        manufacturing = Location(
            id="6122", name="Manufacturing",
            type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT
        )
        hub1 = Location(
            id="6104", name="Hub 1",
            type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT
        )
        dest1 = Location(
            id="6105", name="Destination 1",
            type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT
        )

        # Two routes to 6105: cheap via hub, expensive direct
        routes = [
            Route(id="R1", origin_id="6122", destination_id="6104",
                  transport_mode=StorageMode.AMBIENT, transit_time_days=2.0, cost=0.2),
            Route(id="R2", origin_id="6104", destination_id="6105",
                  transport_mode=StorageMode.AMBIENT, transit_time_days=1.0, cost=0.1),
            Route(id="R5", origin_id="6122", destination_id="6105",
                  transport_mode=StorageMode.AMBIENT, transit_time_days=1.0, cost=0.5),
        ]

        locations = [manufacturing, hub1, dest1]
        graph_builder = NetworkGraphBuilder(locations, routes)
        graph_builder.build_graph()

        enumerator = RouteEnumerator(
            graph_builder=graph_builder,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        routes = enumerator.enumerate_routes_for_destinations(
            destinations=["6105"],
            rank_by='cost'
        )

        # Should have 2 routes to 6105
        assert len(routes["6105"]) == 2

        # First route should be cheaper (via hub)
        route1 = routes["6105"][0]
        route2 = routes["6105"][1]
        assert route1.total_cost < route2.total_cost

    def test_max_routes_per_destination_limit(self):
        """Test that max_routes_per_destination limit is respected."""
        # Create network with multiple routes to same destination
        manufacturing = Location(
            id="6122", name="Manufacturing",
            type=LocationType.MANUFACTURING, storage_mode=StorageMode.AMBIENT
        )
        hub1 = Location(
            id="6104", name="Hub 1",
            type=LocationType.STORAGE, storage_mode=StorageMode.AMBIENT
        )
        dest1 = Location(
            id="6105", name="Destination 1",
            type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT
        )

        # Multiple routes to 6105
        routes = [
            Route(id="R1", origin_id="6122", destination_id="6104",
                  transport_mode=StorageMode.AMBIENT, transit_time_days=2.0, cost=0.2),
            Route(id="R2", origin_id="6104", destination_id="6105",
                  transport_mode=StorageMode.AMBIENT, transit_time_days=1.0, cost=0.1),
            Route(id="R5", origin_id="6122", destination_id="6105",
                  transport_mode=StorageMode.AMBIENT, transit_time_days=1.0, cost=0.5),
        ]

        locations = [manufacturing, hub1, dest1]
        graph_builder = NetworkGraphBuilder(locations, routes)
        graph_builder.build_graph()

        enumerator = RouteEnumerator(
            graph_builder=graph_builder,
            manufacturing_site_id="6122",
            max_routes_per_destination=1  # Limit to 1 route
        )

        routes = enumerator.enumerate_routes_for_destinations(
            destinations=["6105"],
            rank_by='cost'
        )

        # Should only have 1 route (the cheapest)
        assert len(routes["6105"]) == 1

    def test_get_route_summary(self, simple_network):
        """Test getting route summary statistics."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        enumerator.enumerate_routes_for_destinations(
            destinations=["6105", "6103", "6110"],
            rank_by='cost'
        )

        summary = enumerator.get_route_summary()

        assert summary['total_routes'] == 3
        assert summary['num_destinations'] == 3
        assert summary['avg_routes_per_destination'] == pytest.approx(1.0)
        assert summary['avg_cost'] > 0
        assert summary['avg_transit_days'] > 0

    def test_clear_routes(self, simple_network):
        """Test clearing enumerated routes."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        # Enumerate some routes
        enumerator.enumerate_routes_for_destinations(
            destinations=["6105"],
            rank_by='cost'
        )

        assert enumerator.get_total_route_count() > 0

        # Clear
        enumerator.clear()

        assert enumerator.get_total_route_count() == 0
        assert len(enumerator.get_all_destinations()) == 0

    def test_no_route_to_destination(self, simple_network):
        """Test handling when no route exists to destination."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        # Try to enumerate route to non-existent destination
        routes = enumerator.enumerate_routes_for_destinations(
            destinations=["9999"],  # Doesn't exist
            rank_by='cost'
        )

        assert "9999" in routes
        assert len(routes["9999"]) == 0  # No routes found

    def test_enumerated_route_str(self, simple_network):
        """Test string representation of EnumeratedRoute."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        routes = enumerator.enumerate_routes_for_destinations(
            destinations=["6105"],
            rank_by='cost'
        )

        route = routes["6105"][0]
        route_str = str(route)

        assert "6122" in route_str
        assert "6105" in route_str
        assert "0.3" in route_str or "0.30" in route_str  # Cost
        assert "3" in route_str  # Transit days

    def test_print_methods_no_errors(self, simple_network, capsys):
        """Test that print methods execute without errors."""
        enumerator = RouteEnumerator(
            graph_builder=simple_network,
            manufacturing_site_id="6122",
            max_routes_per_destination=5
        )

        enumerator.enumerate_routes_for_destinations(
            destinations=["6105", "6103"],
            rank_by='cost'
        )

        # Should not raise errors
        enumerator.print_route_summary()
        enumerator.print_routes_by_destination(limit_per_dest=1)

        # Verify some output was produced
        captured = capsys.readouterr()
        assert len(captured.out) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
