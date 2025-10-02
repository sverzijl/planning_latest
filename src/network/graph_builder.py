"""
Network graph builder for distribution network modeling.

This module builds a NetworkX directed graph from Location and Route objects,
enabling path finding and network analysis.
"""

import networkx as nx
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from src.models.location import Location
from src.models.route import Route


@dataclass
class NetworkNode:
    """
    Represents a node in the distribution network graph.

    Attributes:
        location_id: Unique location identifier
        location_type: Type of location (manufacturing, hub, storage, breadroom)
        name: Human-readable name
        attributes: Additional location attributes
    """
    location_id: str
    location_type: str
    name: str
    attributes: Dict[str, Any]


@dataclass
class NetworkEdge:
    """
    Represents an edge (route) in the distribution network graph.

    Attributes:
        from_location: Source location ID
        to_location: Destination location ID
        transit_days: Transit time in days
        transport_mode: Transport mode (frozen/ambient)
        cost_per_unit: Cost per unit for this route
        intermediate_stops: List of intermediate location IDs
        attributes: Additional route attributes
    """
    from_location: str
    to_location: str
    transit_days: int
    transport_mode: str
    cost_per_unit: float
    intermediate_stops: List[str]
    attributes: Dict[str, Any]


class NetworkGraphBuilder:
    """
    Builds a NetworkX directed graph from Location and Route data.

    This class creates a graph representation of the distribution network
    that can be used for path finding, shortest path analysis, and
    route enumeration.
    """

    def __init__(self, locations: List[Location], routes: List[Route]):
        """
        Initialize graph builder with locations and routes.

        Args:
            locations: List of Location objects
            routes: List of Route objects
        """
        self.locations = {loc.location_id: loc for loc in locations}
        self.routes = routes
        self.graph: Optional[nx.DiGraph] = None

    def build_graph(self) -> nx.DiGraph:
        """
        Build the NetworkX directed graph from locations and routes.

        Returns:
            NetworkX DiGraph with locations as nodes and routes as edges

        Raises:
            ValueError: If routes reference non-existent locations
        """
        graph = nx.DiGraph()

        # Add all locations as nodes
        for location_id, location in self.locations.items():
            node_attrs = {
                'location_type': location.location_type,
                'name': location.name,
                'location_obj': location,
            }

            # Add capacity attributes if available
            if hasattr(location, 'storage_capacity'):
                node_attrs['storage_capacity'] = location.storage_capacity
            if hasattr(location, 'frozen_capacity'):
                node_attrs['frozen_capacity'] = location.frozen_capacity

            graph.add_node(location_id, **node_attrs)

        # Add all routes as edges
        for route in self.routes:
            # Validate locations exist
            if route.from_location not in self.locations:
                raise ValueError(f"Route references non-existent location: {route.from_location}")
            if route.to_location not in self.locations:
                raise ValueError(f"Route references non-existent location: {route.to_location}")

            # Handle intermediate stops
            intermediate_stops = []
            if route.intermediate_stops:
                intermediate_stops = route.intermediate_stops
                # Validate intermediate stops exist
                for stop in intermediate_stops:
                    if stop not in self.locations:
                        raise ValueError(f"Route references non-existent intermediate stop: {stop}")

            edge_attrs = {
                'transit_days': route.transit_days,
                'transport_mode': route.transport_mode,
                'cost_per_unit': route.cost_per_unit,
                'intermediate_stops': intermediate_stops,
                'route_obj': route,
            }

            # Add day-specific schedule if available
            if hasattr(route, 'days_available'):
                edge_attrs['days_available'] = route.days_available

            graph.add_edge(
                route.from_location,
                route.to_location,
                **edge_attrs
            )

        self.graph = graph
        return graph

    def get_graph(self) -> nx.DiGraph:
        """
        Get the built graph, building it first if necessary.

        Returns:
            NetworkX DiGraph
        """
        if self.graph is None:
            return self.build_graph()
        return self.graph

    def get_node_attributes(self, location_id: str) -> Dict[str, Any]:
        """
        Get all attributes for a node.

        Args:
            location_id: Location ID

        Returns:
            Dictionary of node attributes

        Raises:
            ValueError: If location doesn't exist in graph
        """
        graph = self.get_graph()
        if location_id not in graph:
            raise ValueError(f"Location {location_id} not in graph")

        return dict(graph.nodes[location_id])

    def get_edge_attributes(self, from_location: str, to_location: str) -> Dict[str, Any]:
        """
        Get all attributes for an edge.

        Args:
            from_location: Source location ID
            to_location: Destination location ID

        Returns:
            Dictionary of edge attributes

        Raises:
            ValueError: If edge doesn't exist in graph
        """
        graph = self.get_graph()
        if not graph.has_edge(from_location, to_location):
            raise ValueError(f"Edge {from_location}->{to_location} not in graph")

        return dict(graph.edges[from_location, to_location])

    def get_successors(self, location_id: str) -> List[str]:
        """
        Get all direct successors (destinations) from a location.

        Args:
            location_id: Source location ID

        Returns:
            List of destination location IDs
        """
        graph = self.get_graph()
        if location_id not in graph:
            return []

        return list(graph.successors(location_id))

    def get_predecessors(self, location_id: str) -> List[str]:
        """
        Get all direct predecessors (sources) to a location.

        Args:
            location_id: Destination location ID

        Returns:
            List of source location IDs
        """
        graph = self.get_graph()
        if location_id not in graph:
            return []

        return list(graph.predecessors(location_id))

    def get_manufacturing_nodes(self) -> List[str]:
        """
        Get all manufacturing location IDs.

        Returns:
            List of manufacturing location IDs
        """
        graph = self.get_graph()
        return [
            node for node, attrs in graph.nodes(data=True)
            if attrs.get('location_type') == 'manufacturing'
        ]

    def get_breadroom_nodes(self) -> List[str]:
        """
        Get all breadroom location IDs.

        Returns:
            List of breadroom location IDs
        """
        graph = self.get_graph()
        return [
            node for node, attrs in graph.nodes(data=True)
            if attrs.get('location_type') == 'breadroom'
        ]

    def get_hub_nodes(self) -> List[str]:
        """
        Get all hub location IDs.

        Returns:
            List of hub location IDs
        """
        graph = self.get_graph()
        return [
            node for node, attrs in graph.nodes(data=True)
            if attrs.get('location_type') == 'hub'
        ]

    def is_reachable(self, from_location: str, to_location: str) -> bool:
        """
        Check if there's any path from source to destination.

        Args:
            from_location: Source location ID
            to_location: Destination location ID

        Returns:
            True if path exists, False otherwise
        """
        graph = self.get_graph()
        try:
            return nx.has_path(graph, from_location, to_location)
        except nx.NodeNotFound:
            return False

    def get_shortest_path_length(self, from_location: str, to_location: str) -> Optional[int]:
        """
        Get shortest path length (number of hops) between locations.

        Args:
            from_location: Source location ID
            to_location: Destination location ID

        Returns:
            Number of hops in shortest path, or None if no path exists
        """
        graph = self.get_graph()
        try:
            return nx.shortest_path_length(graph, from_location, to_location)
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None

    def visualize_graph(self) -> Dict[str, Any]:
        """
        Generate graph visualization data for plotting.

        Returns:
            Dictionary with 'nodes' and 'edges' for visualization
        """
        graph = self.get_graph()

        nodes_data = []
        for node, attrs in graph.nodes(data=True):
            nodes_data.append({
                'id': node,
                'label': attrs.get('name', node),
                'type': attrs.get('location_type', 'unknown'),
            })

        edges_data = []
        for from_loc, to_loc, attrs in graph.edges(data=True):
            edges_data.append({
                'from': from_loc,
                'to': to_loc,
                'transit_days': attrs.get('transit_days', 0),
                'mode': attrs.get('transport_mode', 'unknown'),
                'cost': attrs.get('cost_per_unit', 0),
            })

        return {
            'nodes': nodes_data,
            'edges': edges_data,
        }
