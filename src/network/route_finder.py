"""
Route finding and path enumeration for distribution network.

This module provides path finding capabilities including:
- All paths enumeration
- Shortest path by transit time
- Cheapest path by cost
- Shelf-life-aware routing
"""

import networkx as nx
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from datetime import date

from .graph_builder import NetworkGraphBuilder
from src.shelf_life import RouteLeg, ShelfLifeTracker, ProductState


@dataclass
class RoutePath:
    """
    Represents a complete path through the distribution network.

    Attributes:
        path: List of location IDs in order
        total_transit_days: Total transit time
        total_cost: Total cost per unit
        transport_modes: List of transport modes for each leg
        route_legs: List of RouteLeg objects for shelf life tracking
        intermediate_stops: All intermediate stops in the path
    """
    path: List[str]
    total_transit_days: int
    total_cost: float
    transport_modes: List[str]
    route_legs: List[RouteLeg]
    intermediate_stops: List[str]

    @property
    def origin(self) -> str:
        """Get the origin location."""
        return self.path[0]

    @property
    def destination(self) -> str:
        """Get the destination location."""
        return self.path[-1]

    @property
    def num_hops(self) -> int:
        """Get the number of hops (edges) in the path."""
        return len(self.path) - 1

    def __str__(self) -> str:
        path_str = " -> ".join(self.path)
        return f"{path_str} ({self.total_transit_days}d, ${self.total_cost:.2f})"


class RouteFinder:
    """
    Finds and analyzes routes through the distribution network.

    This class provides various path-finding algorithms and integrates
    with the shelf life tracker to validate route feasibility.
    """

    def __init__(
        self,
        graph_builder: NetworkGraphBuilder,
        shelf_life_tracker: Optional[ShelfLifeTracker] = None
    ):
        """
        Initialize route finder.

        Args:
            graph_builder: NetworkGraphBuilder instance
            shelf_life_tracker: Optional ShelfLifeTracker for shelf life validation
        """
        self.graph_builder = graph_builder
        self.graph = graph_builder.get_graph()
        self.shelf_life_tracker = shelf_life_tracker or ShelfLifeTracker()

    def find_all_paths(
        self,
        source: str,
        target: str,
        max_hops: Optional[int] = None
    ) -> List[RoutePath]:
        """
        Find all simple paths from source to target.

        Args:
            source: Source location ID
            target: Target location ID
            max_hops: Maximum number of hops (default: unlimited)

        Returns:
            List of RoutePath objects
        """
        try:
            if max_hops is None:
                # Use a reasonable default to avoid exponential explosion
                max_hops = 10

            all_paths = nx.all_simple_paths(
                self.graph,
                source,
                target,
                cutoff=max_hops
            )

            route_paths = []
            for path in all_paths:
                route_path = self._build_route_path(path)
                if route_path:
                    route_paths.append(route_path)

            # Sort by total transit days (then by cost)
            route_paths.sort(key=lambda r: (r.total_transit_days, r.total_cost))

            return route_paths

        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return []

    def find_shortest_path(self, source: str, target: str) -> Optional[RoutePath]:
        """
        Find shortest path by transit time.

        Args:
            source: Source location ID
            target: Target location ID

        Returns:
            RoutePath with minimum transit time, or None if no path exists
        """
        try:
            path = nx.shortest_path(
                self.graph,
                source,
                target,
                weight='transit_days'
            )
            return self._build_route_path(path)

        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None

    def find_cheapest_path(self, source: str, target: str) -> Optional[RoutePath]:
        """
        Find cheapest path by cost per unit.

        Args:
            source: Source location ID
            target: Target location ID

        Returns:
            RoutePath with minimum cost, or None if no path exists
        """
        try:
            path = nx.shortest_path(
                self.graph,
                source,
                target,
                weight='cost_per_unit'
            )
            return self._build_route_path(path)

        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None

    def find_feasible_paths(
        self,
        source: str,
        target: str,
        initial_state: ProductState = ProductState.AMBIENT,
        max_paths: int = 10
    ) -> List[Tuple[RoutePath, bool]]:
        """
        Find paths and check shelf life feasibility.

        Args:
            source: Source location ID
            target: Target location ID
            initial_state: Initial product state
            max_paths: Maximum number of paths to return

        Returns:
            List of tuples (RoutePath, is_feasible)
        """
        all_paths = self.find_all_paths(source, target)[:max_paths]

        feasible_paths = []
        for route_path in all_paths:
            is_feasible, reason = self.shelf_life_tracker.validate_route_feasibility(
                route_legs=route_path.route_legs,
                initial_state=initial_state
            )
            feasible_paths.append((route_path, is_feasible))

        return feasible_paths

    def recommend_route(
        self,
        source: str,
        target: str,
        initial_state: ProductState = ProductState.AMBIENT,
        prioritize: str = 'cost'  # 'cost' or 'time'
    ) -> Optional[RoutePath]:
        """
        Recommend best route based on criteria.

        Args:
            source: Source location ID
            target: Target location ID
            initial_state: Initial product state
            prioritize: 'cost' to minimize cost, 'time' to minimize transit

        Returns:
            Recommended RoutePath, or None if no feasible path exists
        """
        feasible_paths = self.find_feasible_paths(source, target, initial_state)

        # Filter to only feasible routes
        viable_routes = [route for route, is_feasible in feasible_paths if is_feasible]

        if not viable_routes:
            return None

        # Sort by priority
        if prioritize == 'cost':
            viable_routes.sort(key=lambda r: (r.total_cost, r.total_transit_days))
        else:  # prioritize == 'time'
            viable_routes.sort(key=lambda r: (r.total_transit_days, r.total_cost))

        return viable_routes[0]

    def get_routes_to_all_breadrooms(
        self,
        source: str,
        initial_state: ProductState = ProductState.AMBIENT
    ) -> Dict[str, Optional[RoutePath]]:
        """
        Find recommended routes from source to all breadrooms.

        Args:
            source: Source location ID (typically manufacturing site)
            initial_state: Initial product state

        Returns:
            Dictionary mapping breadroom IDs to recommended RoutePath
        """
        breadrooms = self.graph_builder.get_breadroom_nodes()

        routes = {}
        for breadroom in breadrooms:
            route = self.recommend_route(source, breadroom, initial_state)
            routes[breadroom] = route

        return routes

    def _build_route_path(self, path: List[str]) -> Optional[RoutePath]:
        """
        Build a RoutePath object from a list of location IDs.

        Args:
            path: List of location IDs

        Returns:
            RoutePath object, or None if path is invalid
        """
        if len(path) < 2:
            return None

        total_transit_days = 0
        total_cost = 0.0
        transport_modes = []
        route_legs = []
        all_intermediate_stops = []

        # Build route legs from consecutive pairs in path
        for i in range(len(path) - 1):
            from_loc = path[i]
            to_loc = path[i + 1]

            # Get edge attributes
            try:
                edge_attrs = self.graph.edges[from_loc, to_loc]
            except KeyError:
                # Edge doesn't exist
                return None

            transit_days = edge_attrs.get('transit_days', 0)
            cost_per_unit = edge_attrs.get('cost_per_unit', 0.0)
            transport_mode = edge_attrs.get('transport_mode', 'ambient')
            intermediate_stops = edge_attrs.get('intermediate_stops', [])

            total_transit_days += transit_days
            total_cost += cost_per_unit
            transport_modes.append(transport_mode)
            all_intermediate_stops.extend(intermediate_stops)

            # Check if this location triggers thawing (e.g., location 6130 in WA)
            # This would need to be configured per location in Phase 1 models
            # For now, detect based on location ID
            triggers_thaw = (to_loc == "6130")  # WA breadroom thaws frozen product

            route_leg = RouteLeg(
                from_location_id=from_loc,
                to_location_id=to_loc,
                transit_days=transit_days,
                transport_mode=transport_mode,
                triggers_thaw=triggers_thaw
            )
            route_legs.append(route_leg)

        return RoutePath(
            path=path,
            total_transit_days=total_transit_days,
            total_cost=total_cost,
            transport_modes=transport_modes,
            route_legs=route_legs,
            intermediate_stops=all_intermediate_stops
        )

    def analyze_network_connectivity(self) -> Dict[str, Any]:
        """
        Analyze overall network connectivity and structure.

        Returns:
            Dictionary with connectivity metrics
        """
        manufacturing = self.graph_builder.get_manufacturing_nodes()
        breadrooms = self.graph_builder.get_breadroom_nodes()
        hubs = self.graph_builder.get_hub_nodes()

        # Check connectivity from each manufacturing to each breadroom
        connectivity_matrix = {}
        for mfg in manufacturing:
            connectivity_matrix[mfg] = {}
            for br in breadrooms:
                connectivity_matrix[mfg][br] = self.graph_builder.is_reachable(mfg, br)

        # Calculate some basic metrics
        total_connections = sum(1 for routes in connectivity_matrix.values() for connected in routes.values() if connected)
        possible_connections = len(manufacturing) * len(breadrooms)

        return {
            'manufacturing_nodes': manufacturing,
            'breadroom_nodes': breadrooms,
            'hub_nodes': hubs,
            'connectivity_matrix': connectivity_matrix,
            'total_connections': total_connections,
            'possible_connections': possible_connections,
            'connectivity_ratio': total_connections / possible_connections if possible_connections > 0 else 0,
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
        }
