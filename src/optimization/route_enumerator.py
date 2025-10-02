"""Route enumeration utility for optimization models.

This module provides utilities to enumerate and manage feasible routes
from manufacturing to destinations for use in optimization models.
"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from src.network import NetworkGraphBuilder, RouteFinder, RoutePath


@dataclass
class EnumeratedRoute:
    """
    Represents an enumerated route with optimization-relevant metadata.

    Attributes:
        index: Unique index for this route (0, 1, 2, ...)
        route_path: Original RoutePath object
        origin_id: Origin location ID
        destination_id: Destination location ID
        total_cost: Total cost per unit for this route
        total_transit_days: Total transit time in days
        path: List of location IDs in path
        num_hops: Number of hops (edges) in path
    """
    index: int
    route_path: RoutePath
    origin_id: str
    destination_id: str
    total_cost: float
    total_transit_days: int
    path: List[str]
    num_hops: int

    def __str__(self) -> str:
        path_str = " → ".join(self.path)
        return f"Route {self.index}: {path_str} ({self.total_transit_days}d, ${self.total_cost:.2f}/unit)"


class RouteEnumerator:
    """
    Enumerates and manages routes for optimization models.

    This class handles route enumeration from a single source (manufacturing)
    to multiple destinations, with options to limit the number of routes
    per destination and filter by criteria.

    Example:
        enumerator = RouteEnumerator(
            graph_builder=graph_builder,
            manufacturing_site_id="6122",
            max_routes_per_destination=3
        )

        routes = enumerator.enumerate_routes_for_destinations(
            destinations=["6103", "6105", "6110"]
        )

        # Get route info
        route = enumerator.get_route(5)
        cost = enumerator.get_route_cost(5)
    """

    def __init__(
        self,
        graph_builder: NetworkGraphBuilder,
        manufacturing_site_id: str,
        max_routes_per_destination: int = 5,
        max_hops: int = 5,
    ):
        """
        Initialize route enumerator.

        Args:
            graph_builder: Network graph builder
            manufacturing_site_id: ID of manufacturing/source location
            max_routes_per_destination: Maximum routes to enumerate per destination
            max_hops: Maximum number of hops to consider in path finding
        """
        self.graph_builder = graph_builder
        self.manufacturing_site_id = manufacturing_site_id
        self.max_routes_per_destination = max_routes_per_destination
        self.max_hops = max_hops

        # Route finder for path enumeration
        self.route_finder = RouteFinder(graph_builder)

        # Storage for enumerated routes
        self._routes: List[EnumeratedRoute] = []
        self._routes_by_destination: Dict[str, List[int]] = defaultdict(list)
        self._route_index_map: Dict[int, EnumeratedRoute] = {}

    def enumerate_routes_for_destinations(
        self,
        destinations: List[str],
        rank_by: str = 'cost'
    ) -> Dict[str, List[EnumeratedRoute]]:
        """
        Enumerate routes from manufacturing to each destination.

        Args:
            destinations: List of destination location IDs
            rank_by: Ranking criterion ('cost', 'time', or 'hops')

        Returns:
            Dictionary mapping destination_id to list of EnumeratedRoute objects

        Example:
            routes = enumerator.enumerate_routes_for_destinations(
                destinations=["6103", "6105"],
                rank_by='cost'
            )
            # routes["6103"] = [Route(0), Route(1), Route(2)]
        """
        result: Dict[str, List[EnumeratedRoute]] = {}

        for destination_id in destinations:
            # Find all paths from manufacturing to this destination
            all_paths = self.route_finder.find_all_paths(
                source=self.manufacturing_site_id,
                target=destination_id,
                max_hops=self.max_hops
            )

            if not all_paths:
                # No route found - skip this destination
                result[destination_id] = []
                continue

            # Rank paths
            ranked_paths = self._rank_paths(all_paths, rank_by)

            # Take top K routes
            top_routes = ranked_paths[:self.max_routes_per_destination]

            # Create EnumeratedRoute objects
            enumerated = []
            for route_path in top_routes:
                route_index = len(self._routes)  # Next available index

                enum_route = EnumeratedRoute(
                    index=route_index,
                    route_path=route_path,
                    origin_id=route_path.origin,
                    destination_id=route_path.destination,
                    total_cost=route_path.total_cost,
                    total_transit_days=route_path.total_transit_days,
                    path=route_path.path,
                    num_hops=route_path.num_hops,
                )

                # Store
                self._routes.append(enum_route)
                self._routes_by_destination[destination_id].append(route_index)
                self._route_index_map[route_index] = enum_route
                enumerated.append(enum_route)

            result[destination_id] = enumerated

        return result

    def _rank_paths(
        self,
        paths: List[RoutePath],
        rank_by: str
    ) -> List[RoutePath]:
        """
        Rank paths by specified criterion.

        Args:
            paths: List of RoutePath objects
            rank_by: Ranking criterion ('cost', 'time', or 'hops')

        Returns:
            Sorted list of paths (best first)
        """
        if rank_by == 'cost':
            return sorted(paths, key=lambda p: (p.total_cost, p.total_transit_days))
        elif rank_by == 'time':
            return sorted(paths, key=lambda p: (p.total_transit_days, p.total_cost))
        elif rank_by == 'hops':
            return sorted(paths, key=lambda p: (p.num_hops, p.total_cost))
        else:
            # Default: cost
            return sorted(paths, key=lambda p: (p.total_cost, p.total_transit_days))

    def get_route(self, route_index: int) -> Optional[EnumeratedRoute]:
        """
        Get route by index.

        Args:
            route_index: Route index

        Returns:
            EnumeratedRoute or None if not found
        """
        return self._route_index_map.get(route_index)

    def get_route_cost(self, route_index: int) -> float:
        """
        Get total cost for route.

        Args:
            route_index: Route index

        Returns:
            Total cost per unit

        Raises:
            KeyError: If route index not found
        """
        route = self._route_index_map[route_index]
        return route.total_cost

    def get_route_transit_time(self, route_index: int) -> int:
        """
        Get transit time for route.

        Args:
            route_index: Route index

        Returns:
            Transit time in days

        Raises:
            KeyError: If route index not found
        """
        route = self._route_index_map[route_index]
        return route.total_transit_days

    def get_routes_to_destination(self, destination_id: str) -> List[int]:
        """
        Get all route indices that go to specified destination.

        Args:
            destination_id: Destination location ID

        Returns:
            List of route indices

        Example:
            route_indices = enumerator.get_routes_to_destination("6103")
            # Returns: [0, 1, 2] (up to max_routes_per_destination)
        """
        return self._routes_by_destination.get(destination_id, [])

    def get_all_routes(self) -> List[EnumeratedRoute]:
        """
        Get all enumerated routes.

        Returns:
            List of all EnumeratedRoute objects
        """
        return self._routes.copy()

    def get_all_destinations(self) -> Set[str]:
        """
        Get all destinations that have routes enumerated.

        Returns:
            Set of destination IDs
        """
        return set(self._routes_by_destination.keys())

    def get_total_route_count(self) -> int:
        """
        Get total number of enumerated routes.

        Returns:
            Total route count
        """
        return len(self._routes)

    def get_route_summary(self) -> Dict[str, any]:
        """
        Get summary statistics about enumerated routes.

        Returns:
            Dictionary with summary info

        Example:
            summary = enumerator.get_route_summary()
            print(f"Total routes: {summary['total_routes']}")
            print(f"Destinations: {summary['num_destinations']}")
        """
        costs = [r.total_cost for r in self._routes]
        transit_times = [r.total_transit_days for r in self._routes]
        hops = [r.num_hops for r in self._routes]

        return {
            'total_routes': len(self._routes),
            'num_destinations': len(self._routes_by_destination),
            'avg_routes_per_destination': (
                len(self._routes) / len(self._routes_by_destination)
                if self._routes_by_destination else 0
            ),
            'avg_cost': sum(costs) / len(costs) if costs else 0,
            'min_cost': min(costs) if costs else 0,
            'max_cost': max(costs) if costs else 0,
            'avg_transit_days': sum(transit_times) / len(transit_times) if transit_times else 0,
            'min_transit_days': min(transit_times) if transit_times else 0,
            'max_transit_days': max(transit_times) if transit_times else 0,
            'avg_hops': sum(hops) / len(hops) if hops else 0,
        }

    def print_route_summary(self) -> None:
        """
        Print human-readable route summary.

        Example:
            enumerator.print_route_summary()
        """
        summary = self.get_route_summary()

        print("=" * 70)
        print("Route Enumeration Summary")
        print("=" * 70)
        print(f"Total routes:              {summary['total_routes']}")
        print(f"Destinations:              {summary['num_destinations']}")
        print(f"Avg routes/destination:    {summary['avg_routes_per_destination']:.1f}")
        print()
        print(f"Cost range:                ${summary['min_cost']:.2f} - ${summary['max_cost']:.2f}")
        print(f"Average cost:              ${summary['avg_cost']:.2f}")
        print()
        print(f"Transit time range:        {summary['min_transit_days']:.0f} - {summary['max_transit_days']:.0f} days")
        print(f"Average transit time:      {summary['avg_transit_days']:.1f} days")
        print()
        print(f"Average hops:              {summary['avg_hops']:.1f}")
        print("=" * 70)

    def print_routes_by_destination(self, limit_per_dest: Optional[int] = None) -> None:
        """
        Print routes grouped by destination.

        Args:
            limit_per_dest: Optional limit on routes to print per destination

        Example:
            enumerator.print_routes_by_destination(limit_per_dest=3)
        """
        print("=" * 70)
        print("Routes by Destination")
        print("=" * 70)

        for destination_id in sorted(self._routes_by_destination.keys()):
            route_indices = self._routes_by_destination[destination_id]
            print(f"\nDestination: {destination_id} ({len(route_indices)} routes)")
            print("-" * 70)

            for i, route_idx in enumerate(route_indices):
                if limit_per_dest and i >= limit_per_dest:
                    remaining = len(route_indices) - limit_per_dest
                    print(f"  ... and {remaining} more routes")
                    break

                route = self._route_index_map[route_idx]
                print(f"  {route}")

        print("=" * 70)

    def clear(self) -> None:
        """
        Clear all enumerated routes.

        Useful for resetting before re-enumeration with different parameters.
        """
        self._routes.clear()
        self._routes_by_destination.clear()
        self._route_index_map.clear()


if __name__ == "__main__":
    """
    Example usage and testing.
    """
    # This would require actual network setup
    print("RouteEnumerator utility module loaded.")
    print("See tests/test_route_enumerator.py for usage examples.")
