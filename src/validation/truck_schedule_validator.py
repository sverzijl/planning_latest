"""Truck schedule validation - fail-fast detection of routing issues.

This module provides validation for truck schedules and routing to prevent
silent failures where goods can't reach destinations.

Key validations:
1. Intermediate stops have incoming routes
2. Intermediate stops have outgoing routes (continuation or final destination)
3. No unreachable nodes due to missing truck schedules
4. No conflicting trucks on same day to same destination
"""

from typing import List, Dict, Set, Tuple
from dataclasses import dataclass

from src.models.unified_truck_schedule import UnifiedTruckSchedule
from src.models.unified_route import UnifiedRoute
from src.models.unified_node import UnifiedNode


@dataclass
class TruckValidationIssue:
    """Represents a truck schedule validation issue."""
    severity: str  # 'error', 'warning', 'info'
    category: str
    message: str
    truck_id: str = None
    route: Tuple[str, str] = None


class TruckScheduleValidator:
    """Validates truck schedules and routes for operational feasibility."""

    def __init__(
        self,
        truck_schedules: List[UnifiedTruckSchedule],
        routes: List[UnifiedRoute],
        nodes: Dict[str, UnifiedNode]
    ):
        """Initialize validator.

        Args:
            truck_schedules: List of truck schedules
            routes: List of routes
            nodes: Dict of nodes {id: UnifiedNode}
        """
        self.truck_schedules = truck_schedules
        self.routes = routes
        self.nodes = nodes

        # Build route index
        self.route_index = {}
        for route in routes:
            key = (route.origin_node_id, route.destination_node_id)
            self.route_index[key] = route

    def validate(self) -> Tuple[bool, List[TruckValidationIssue]]:
        """Run all validation checks.

        Returns:
            Tuple of (is_valid, list of issues)
            is_valid is False if any errors found
        """
        issues = []

        # Run all validation checks
        issues.extend(self._validate_intermediate_stop_routes())
        issues.extend(self._validate_intermediate_stop_capabilities())
        issues.extend(self._validate_reachability())
        issues.extend(self._validate_conflicting_schedules())

        # Check if any errors
        has_errors = any(issue.severity == 'error' for issue in issues)

        return (not has_errors, issues)

    def _validate_intermediate_stop_routes(self) -> List[TruckValidationIssue]:
        """Validate that intermediate stops have necessary routes.

        Intermediate stops are DROP-OFF points, not transfer points.

        Truck with intermediate stops can deliver to:
        - origin → intermediate_stop (drop-off at stop)
        - origin → final_destination (goods continue on truck)

        We do NOT need: intermediate_stop → final_destination
        (Goods that continue stay on the truck, don't transfer between nodes)

        Checks:
        1. Route exists: origin → intermediate_stop (for drop-offs)
        2. Route exists: origin → final_destination (for continuing goods)
        """
        issues = []

        for truck in self.truck_schedules:
            if not truck.intermediate_stops:
                continue

            origin = truck.origin_node_id

            # Check route to final destination
            final_route_key = (origin, truck.destination_node_id)
            if final_route_key not in self.route_index:
                issues.append(TruckValidationIssue(
                    severity='error',
                    category='Missing Route',
                    message=f"Truck '{truck.id}' requires route {origin} → {truck.destination_node_id} but route doesn't exist",
                    truck_id=truck.id,
                    route=final_route_key
                ))

            # Check routes to each intermediate stop (drop-off points)
            for stop in truck.intermediate_stops:
                stop_route_key = (origin, stop)
                if stop_route_key not in self.route_index:
                    issues.append(TruckValidationIssue(
                        severity='error',
                        category='Missing Route',
                        message=f"Truck '{truck.id}' requires route {origin} → {stop} (intermediate drop-off) but route doesn't exist",
                        truck_id=truck.id,
                        route=stop_route_key
                    ))

        return issues

    def _validate_intermediate_stop_capabilities(self) -> List[TruckValidationIssue]:
        """Validate that intermediate stops have necessary capabilities.

        For Lineage specifically:
        - Must have freeze capability (ambient → frozen)
        - Must have frozen storage
        """
        issues = []

        for truck in self.truck_schedules:
            if not truck.intermediate_stops:
                continue

            for stop_id in truck.intermediate_stops:
                node = self.nodes.get(stop_id)

                if not node:
                    issues.append(TruckValidationIssue(
                        severity='error',
                        category='Missing Node',
                        message=f"Truck '{truck.id}' has intermediate stop '{stop_id}' but node doesn't exist",
                        truck_id=truck.id
                    ))
                    continue

                # Check if node can handle goods (store or transform)
                if not node.capabilities.can_store:
                    issues.append(TruckValidationIssue(
                        severity='warning',
                        category='No Storage',
                        message=f"Intermediate stop '{stop_id}' on truck '{truck.id}' has no storage capability - goods will flow through immediately",
                        truck_id=truck.id
                    ))

                # Special check for Lineage - must have freeze capability
                if 'lineage' in stop_id.lower():
                    if not node.supports_frozen_storage():
                        issues.append(TruckValidationIssue(
                            severity='error',
                            category='Missing Freeze Capability',
                            message=f"Lineage must have frozen storage capability for WA route",
                            truck_id=truck.id
                        ))

        return issues

    def _validate_reachability(self) -> List[TruckValidationIssue]:
        """Validate that all demand nodes are reachable from manufacturing.

        Uses truck schedules to determine reachability (not just route existence).
        """
        issues = []

        # Build reachability graph from truck schedules
        reachable_from_mfg = set()
        manufacturing_nodes = [node_id for node_id, node in self.nodes.items()
                               if node.can_produce()]

        for truck in self.truck_schedules:
            if truck.origin_node_id in manufacturing_nodes:
                # Can reach all nodes in path
                if truck.intermediate_stops:
                    reachable_from_mfg.update(truck.intermediate_stops)
                reachable_from_mfg.add(truck.destination_node_id)

        # Check demand nodes
        demand_nodes = [node_id for node_id, node in self.nodes.items()
                       if node.has_demand_capability()]

        for demand_node in demand_nodes:
            if demand_node not in reachable_from_mfg:
                # Check if reachable via hub
                reachable_via_hub = False
                for hub in reachable_from_mfg:
                    route_key = (hub, demand_node)
                    if route_key in self.route_index:
                        reachable_via_hub = True
                        break

                if not reachable_via_hub:
                    issues.append(TruckValidationIssue(
                        severity='warning',
                        category='Unreachable Node',
                        message=f"Demand node '{demand_node}' not reachable via truck schedules (may cause shortages)",
                    ))

        return issues

    def _validate_conflicting_schedules(self) -> List[TruckValidationIssue]:
        """Check for conflicting truck schedules (same day, same route)."""
        issues = []

        # Group trucks by (origin, dest, day)
        truck_by_route_day = {}

        for truck in self.truck_schedules:
            if not truck.day_of_week:
                continue  # Daily trucks don't conflict

            route_key = (truck.origin_node_id, truck.destination_node_id)
            day = str(truck.day_of_week.value) if hasattr(truck.day_of_week, 'value') else str(truck.day_of_week)
            schedule_key = (route_key, day.lower())

            if schedule_key not in truck_by_route_day:
                truck_by_route_day[schedule_key] = []
            truck_by_route_day[schedule_key].append(truck.id)

        # Check for duplicates
        for (route_key, day), truck_ids in truck_by_route_day.items():
            if len(truck_ids) > 1:
                origin, dest = route_key
                issues.append(TruckValidationIssue(
                    severity='info',
                    category='Multiple Trucks',
                    message=f"Multiple trucks on {day} for route {origin} → {dest}: {truck_ids} (OK - adds capacity)",
                    route=route_key
                ))

        return issues


def validate_truck_schedules(
    truck_schedules: List[UnifiedTruckSchedule],
    routes: List[UnifiedRoute],
    nodes: Dict[str, UnifiedNode]
) -> Tuple[bool, List[TruckValidationIssue]]:
    """Convenience function to validate truck schedules.

    Args:
        truck_schedules: List of truck schedules
        routes: List of routes
        nodes: Dict of nodes

    Returns:
        Tuple of (is_valid, list of issues)

    Raises:
        ValidationError: If critical validation fails
    """
    validator = TruckScheduleValidator(truck_schedules, routes, nodes)
    return validator.validate()
