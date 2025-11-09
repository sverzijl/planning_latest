"""Conversion layer: Legacy data structures → Unified node model.

This module provides conversion from existing Location/ManufacturingSite/TruckSchedule
data to the new unified model format. Enables backward compatibility with existing
Excel files and UI code.
"""

from typing import List, Dict, Set, Optional
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.unified_truck_schedule import UnifiedTruckSchedule, DayOfWeek, DepartureType
from src.models.location import Location
from src.models.manufacturing import ManufacturingSite
from src.models.route import Route
from src.models.truck_schedule import TruckSchedule
from src.models.forecast import Forecast


class LegacyToUnifiedConverter:
    """Convert legacy data structures to unified node model.

    Handles conversion of:
    - ManufacturingSite + Locations → UnifiedNodes
    - Routes → UnifiedRoutes
    - TruckSchedules → UnifiedTruckSchedules (with explicit origin)
    """

    def convert_nodes(
        self,
        manufacturing_site: ManufacturingSite,
        locations: List[Location],
        forecast: Forecast
    ) -> List[UnifiedNode]:
        """Convert manufacturing site + locations to unified nodes.

        Args:
            manufacturing_site: Legacy manufacturing site
            locations: List of legacy Location objects
            forecast: Forecast (used to identify demand locations)

        Returns:
            List of UnifiedNode objects
        """
        nodes = []

        # Identify demand locations from forecast
        demand_locations: Set[str] = {e.location_id for e in forecast.entries}

        # Convert manufacturing site to node
        # Manufacturing site has special capabilities
        mfg_node = UnifiedNode(
            id=manufacturing_site.id,
            name=manufacturing_site.name,
            capabilities=NodeCapabilities(
                can_manufacture=True,
                production_rate_per_hour=manufacturing_site.production_rate,
                daily_startup_hours=getattr(manufacturing_site, 'daily_startup_hours', 0.5),
                daily_shutdown_hours=getattr(manufacturing_site, 'daily_shutdown_hours', 0.5),
                default_changeover_hours=getattr(manufacturing_site, 'default_changeover_hours', 1.0),
                can_store=True,
                storage_mode=self._convert_storage_mode(manufacturing_site.storage_mode),
                has_demand=False,  # Manufacturing site doesn't have customer demand
                requires_truck_schedules=True,  # Manufacturing uses scheduled trucks
            ),
            latitude=manufacturing_site.latitude,
            longitude=manufacturing_site.longitude,
        )
        nodes.append(mfg_node)

        # Convert other locations to nodes
        for loc in locations:
            # Skip manufacturing site - already converted above to avoid duplicates
            if loc.id == manufacturing_site.id:
                continue

            # Determine if this location has demand
            has_demand = loc.id in demand_locations

            # Note: In unified model, we don't distinguish between
            # storage/breadroom/hub types - it's all about capabilities
            node = UnifiedNode(
                id=loc.id,
                name=loc.name,
                capabilities=NodeCapabilities(
                    can_manufacture=False,  # Only manufacturing site can produce
                    can_store=True,  # All locations can store
                    storage_mode=self._convert_storage_mode(loc.storage_mode),
                    storage_capacity=loc.capacity,
                    has_demand=has_demand,
                    requires_truck_schedules=False,  # Currently, only manufacturing has truck constraints
                                                    # Could be True for specific hubs in future
                ),
                latitude=loc.latitude,
                longitude=loc.longitude,
            )
            nodes.append(node)

        return nodes

    def convert_routes(self, routes: List[Route]) -> List[UnifiedRoute]:
        """Convert legacy routes to unified format.

        Args:
            routes: List of legacy Route objects

        Returns:
            List of UnifiedRoute objects
        """
        unified_routes = []

        for route in routes:
            # Convert transport mode
            transport_mode = (
                TransportMode.FROZEN if route.transport_mode == 'frozen'
                else TransportMode.AMBIENT
            )

            # Extract cost (may not exist in all legacy routes)
            cost = 0.0
            if hasattr(route, 'cost_per_unit') and route.cost_per_unit is not None:
                cost = route.cost_per_unit
            elif hasattr(route, 'cost') and route.cost is not None:
                cost = route.cost

            unified_route = UnifiedRoute(
                id=route.id,
                origin_node_id=route.origin_id,
                destination_node_id=route.destination_id,
                transit_days=route.transit_time_days,
                transport_mode=transport_mode,
                cost_per_unit=cost,
            )
            unified_routes.append(unified_route)

        return unified_routes

    def convert_truck_schedules(
        self,
        truck_schedules: List[TruckSchedule],
        manufacturing_site_id: str
    ) -> List[UnifiedTruckSchedule]:
        """Convert legacy truck schedules to unified format.

        Key change: Explicitly set origin_node_id (was implicit as manufacturing in legacy).

        Args:
            truck_schedules: List of legacy TruckSchedule objects
            manufacturing_site_id: ID of manufacturing site (used as origin for all legacy trucks)

        Returns:
            List of UnifiedTruckSchedule objects
        """
        unified_trucks = []

        for truck in truck_schedules:
            # Legacy truck schedules are all from manufacturing
            # In unified model, we make origin explicit
            unified_truck = UnifiedTruckSchedule(
                id=truck.id,
                origin_node_id=manufacturing_site_id,  # Explicit origin (was implicit)
                destination_node_id=truck.destination_id,
                departure_type=self._convert_departure_type(truck.departure_type),
                departure_time=truck.departure_time,
                day_of_week=self._convert_day_of_week(truck.day_of_week),
                capacity=truck.capacity,
                cost_fixed=truck.cost_fixed,
                cost_per_unit=truck.cost_per_unit,
                intermediate_stops=truck.intermediate_stops,
                pallet_capacity=truck.pallet_capacity,
                units_per_pallet=truck.units_per_pallet,
                units_per_case=truck.units_per_case,
            )
            unified_trucks.append(unified_truck)

        return unified_trucks

    def _convert_storage_mode(self, legacy_mode) -> StorageMode:
        """Convert legacy storage mode to unified enum."""
        mode_str = str(legacy_mode).lower()

        if mode_str == 'frozen':
            return StorageMode.FROZEN
        elif mode_str == 'ambient':
            return StorageMode.AMBIENT
        elif mode_str == 'both':
            # 'both' no longer supported - default to ambient
            # User should create separate nodes for frozen/ambient capabilities
            return StorageMode.AMBIENT
        else:
            return StorageMode.AMBIENT  # Default

    def _convert_departure_type(self, legacy_type) -> DepartureType:
        """Convert legacy departure type to unified enum."""
        type_str = str(legacy_type).lower()

        if type_str == 'morning':
            return DepartureType.MORNING
        elif type_str == 'afternoon':
            return DepartureType.AFTERNOON
        else:
            return DepartureType.MORNING  # Default

    def _convert_day_of_week(self, legacy_day) -> Optional[DayOfWeek]:
        """Convert legacy day of week to unified enum."""
        if legacy_day is None:
            return None  # Daily schedule

        day_str = str(legacy_day).lower()

        day_map = {
            'monday': DayOfWeek.MONDAY,
            'tuesday': DayOfWeek.TUESDAY,
            'wednesday': DayOfWeek.WEDNESDAY,
            'thursday': DayOfWeek.THURSDAY,
            'friday': DayOfWeek.FRIDAY,
            'saturday': DayOfWeek.SATURDAY,
            'sunday': DayOfWeek.SUNDAY,
        }

        return day_map.get(day_str)

    def convert_all(
        self,
        manufacturing_site: ManufacturingSite,
        locations: List[Location],
        routes: List[Route],
        truck_schedules: List[TruckSchedule],
        forecast: Forecast
    ) -> tuple[List[UnifiedNode], List[UnifiedRoute], List[UnifiedTruckSchedule]]:
        """Convert all legacy data to unified format in one call.

        Args:
            manufacturing_site: Legacy manufacturing site
            locations: Legacy locations
            routes: Legacy routes
            truck_schedules: Legacy truck schedules
            forecast: Forecast data

        Returns:
            Tuple of (nodes, routes, trucks) in unified format
        """
        nodes = self.convert_nodes(manufacturing_site, locations, forecast)
        unified_routes = self.convert_routes(routes)
        unified_trucks = self.convert_truck_schedules(truck_schedules, manufacturing_site.id)

        return nodes, unified_routes, unified_trucks
