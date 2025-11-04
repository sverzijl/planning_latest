"""
Network Topology Validation.

Validates the network structure to ensure:
- All routes reference valid nodes
- No disconnected components
- Manufacturing nodes can reach demand nodes
- Transit times are reasonable
- No circular routes
"""

from typing import List, Set, Dict, Tuple, Optional
from collections import defaultdict, deque
import logging

from src.validation.planning_data_schema import ValidationError

logger = logging.getLogger(__name__)


class NetworkTopologyValidator:
    """Validates network topology and connectivity."""

    def __init__(self, nodes: List, routes: List):
        """Initialize validator.

        Args:
            nodes: List of UnifiedNode or NodeID objects
            routes: List of UnifiedRoute objects
        """
        self.nodes = {n.id: n for n in nodes}
        self.routes = routes

        # Build adjacency lists
        self.outgoing = defaultdict(list)  # node_id -> [(dest_id, route)]
        self.incoming = defaultdict(list)   # node_id -> [(origin_id, route)]

        for route in routes:
            self.outgoing[route.origin_node_id].append((route.destination_node_id, route))
            self.incoming[route.destination_node_id].append((route.origin_node_id, route))

    def validate_all(self) -> Dict[str, any]:
        """Run all network validation checks.

        Returns:
            Dictionary with validation results and warnings
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Check 1: Route references valid nodes
        try:
            self._validate_route_references()
        except ValidationError as e:
            results["valid"] = False
            results["errors"].append(str(e))

        # Check 2: No disconnected components (warnings only)
        disconnected = self._find_disconnected_nodes()
        if disconnected:
            results["warnings"].append(
                f"Found {len(disconnected)} disconnected nodes (no incoming/outgoing routes): {list(disconnected)[:5]}"
            )

        # Check 3: Manufacturing can reach demand
        try:
            unreachable = self._validate_manufacturing_to_demand()
            if unreachable:
                results["warnings"].append(
                    f"Found {len(unreachable)} demand nodes unreachable from manufacturing: {list(unreachable)[:5]}"
                )
        except Exception as e:
            results["warnings"].append(f"Could not validate manufacturing connectivity: {e}")

        # Check 4: Transit times reasonable
        suspicious_routes = self._check_transit_times()
        if suspicious_routes:
            results["warnings"].append(
                f"Found {len(suspicious_routes)} routes with suspicious transit times (>30 days)"
            )

        # Check 5: Circular routes
        circular = self._find_circular_routes()
        if circular:
            results["warnings"].append(
                f"Found {len(circular)} potential circular routes (same origin and destination)"
            )

        return results

    def _validate_route_references(self):
        """Validate all routes reference valid nodes."""
        invalid_routes = []

        for route in self.routes:
            errors = []

            if route.origin_node_id not in self.nodes:
                errors.append(f"unknown origin node '{route.origin_node_id}'")

            if route.destination_node_id not in self.nodes:
                errors.append(f"unknown destination node '{route.destination_node_id}'")

            if errors:
                invalid_routes.append(f"Route {route.id}: {', '.join(errors)}")

        if invalid_routes:
            raise ValidationError(
                f"Found {len(invalid_routes)} routes with invalid node references:\n" +
                "\n".join(invalid_routes[:10]),
                {
                    "total_routes": len(self.routes),
                    "invalid_count": len(invalid_routes),
                    "registered_nodes": list(self.nodes.keys())
                }
            )

    def _find_disconnected_nodes(self) -> Set[str]:
        """Find nodes with no incoming or outgoing routes."""
        connected_nodes = set()

        for route in self.routes:
            connected_nodes.add(route.origin_node_id)
            connected_nodes.add(route.destination_node_id)

        all_nodes = set(self.nodes.keys())
        disconnected = all_nodes - connected_nodes

        return disconnected

    def _validate_manufacturing_to_demand(self) -> Set[str]:
        """Check if all demand nodes are reachable from manufacturing nodes.

        Returns:
            Set of unreachable demand node IDs
        """
        # Find manufacturing and demand nodes
        manufacturing_nodes = set()
        demand_nodes = set()

        for node_id, node in self.nodes.items():
            # Check if node has manufacturing capability
            if hasattr(node, 'capabilities'):
                if node.capabilities.can_manufacture:
                    manufacturing_nodes.add(node_id)
                if node.capabilities.has_demand:
                    demand_nodes.add(node_id)
            elif hasattr(node, 'type'):
                # Legacy Location format
                from src.models.location import LocationType
                if node.type == LocationType.MANUFACTURING:
                    manufacturing_nodes.add(node_id)
                if node.type == LocationType.BREADROOM:
                    demand_nodes.add(node_id)

        if not manufacturing_nodes:
            logger.warning("No manufacturing nodes found in network")
            return set()

        if not demand_nodes:
            logger.warning("No demand nodes found in network")
            return set()

        # BFS from all manufacturing nodes
        reachable = set()
        queue = deque(manufacturing_nodes)
        visited = set(manufacturing_nodes)

        while queue:
            current = queue.popleft()
            reachable.add(current)

            # Explore neighbors
            for dest_id, route in self.outgoing[current]:
                if dest_id not in visited:
                    visited.add(dest_id)
                    queue.append(dest_id)

        # Find unreachable demand nodes
        unreachable_demand = demand_nodes - reachable

        return unreachable_demand

    def _check_transit_times(self) -> List[Tuple[str, str, float]]:
        """Check for suspiciously long transit times.

        Returns:
            List of (origin, dest, transit_days) for suspicious routes
        """
        suspicious = []

        for route in self.routes:
            if route.transit_days > 30:
                suspicious.append((
                    route.origin_node_id,
                    route.destination_node_id,
                    route.transit_days
                ))

        return suspicious

    def _find_circular_routes(self) -> List[str]:
        """Find routes where origin == destination.

        Returns:
            List of route IDs with circular routing
        """
        circular = []

        for route in self.routes:
            if route.origin_node_id == route.destination_node_id:
                circular.append(route.id)

        return circular

    def get_network_summary(self) -> str:
        """Generate human-readable network summary."""
        manufacturing_count = sum(
            1 for n in self.nodes.values()
            if (hasattr(n, 'capabilities') and n.capabilities.can_manufacture) or
               (hasattr(n, 'type') and str(n.type) == 'manufacturing')
        )

        demand_count = sum(
            1 for n in self.nodes.values()
            if (hasattr(n, 'capabilities') and n.capabilities.has_demand) or
               (hasattr(n, 'type') and str(n.type) == 'breadroom')
        )

        return f"""
Network Topology Summary:
  Total nodes: {len(self.nodes)}
  Manufacturing nodes: {manufacturing_count}
  Demand nodes: {demand_count}
  Total routes: {len(self.routes)}
  Avg routes per node: {len(self.routes) / len(self.nodes):.1f}
"""


def validate_network_topology(nodes: List, routes: List) -> Dict[str, any]:
    """Convenience function to validate network topology.

    Args:
        nodes: List of node objects
        routes: List of route objects

    Returns:
        Validation results dictionary

    Raises:
        ValidationError: If critical validation fails

    Example:
        >>> results = validate_network_topology(nodes, routes)
        >>> if not results["valid"]:
        ...     print("Errors:", results["errors"])
        >>> if results["warnings"]:
        ...     print("Warnings:", results["warnings"])
    """
    validator = NetworkTopologyValidator(nodes, routes)
    return validator.validate_all()
