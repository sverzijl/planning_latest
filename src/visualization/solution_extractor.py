"""Extract visualization-friendly data from optimization solution.

This module transforms the raw optimization solution into a format that's easier
to visualize, including truck movements, inventory snapshots, and location states.
"""

from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import date as Date, timedelta
from collections import defaultdict


@dataclass
class TruckMovement:
    """Represents a truck traveling between locations."""
    truck_id: int
    origin: str
    destination: str
    departure_date: Date
    arrival_date: Date
    products: Dict[str, float]  # product_id -> quantity
    is_frozen: bool
    total_units: float

    @property
    def transit_days(self) -> int:
        """Calculate transit time in days."""
        return (self.arrival_date - self.departure_date).days


@dataclass
class LocationState:
    """Represents the state of a location on a specific date."""
    location_id: str
    date: Date
    production: Dict[str, float]  # product_id -> quantity (only for manufacturing)
    inventory_frozen: Dict[str, float]  # product_id -> quantity
    inventory_ambient: Dict[str, float]  # product_id -> quantity
    inbound_shipments: List[TruckMovement]
    outbound_shipments: List[TruckMovement]
    demand_satisfied: Dict[str, float]  # product_id -> quantity delivered


class SolutionDataExtractor:
    """
    Extract and transform optimization solution data for visualization.

    This class processes the raw solution dictionary from the integrated model
    and creates visualization-friendly data structures including truck movements,
    location states, and animation frames.
    """

    def __init__(
        self,
        solution: Dict[str, Any],
        network_config: Any,  # Network configuration with routes
        truck_schedules: Optional[List[Any]] = None,
    ):
        """
        Initialize the extractor with solution data.

        Args:
            solution: Solution dictionary from integrated model
            network_config: Network configuration with location and route information
            truck_schedules: Optional truck schedule data
        """
        self.solution = solution
        self.network_config = network_config
        self.truck_schedules = truck_schedules or []

        # Extract core data from solution
        self.production_data = solution.get("production_by_date_product", {})
        self.shipments_data = solution.get("shipments_by_leg_product_date", {})
        self.inventory_frozen = solution.get("inventory_frozen_by_loc_product_date", {})
        self.inventory_ambient = solution.get("inventory_ambient_by_loc_product_date", {})
        self.truck_loads = solution.get("truck_loads_by_truck_dest_product_date", {})

        # Get demand satisfaction from shortages
        self.shortages = solution.get("shortages_by_dest_product_date", {})

    def get_all_dates(self) -> List[Date]:
        """Get all unique dates in the solution, sorted."""
        dates = set()

        # Collect dates from all data sources
        for (d, _) in self.production_data.keys():
            dates.add(d)
        for ((_, _), _, d) in self.shipments_data.keys():
            dates.add(d)
        for (_, _, d) in self.inventory_frozen.keys():
            dates.add(d)
        for (_, _, d) in self.inventory_ambient.keys():
            dates.add(d)

        return sorted(list(dates))

    def get_all_locations(self) -> List[str]:
        """Get all unique location IDs in the solution."""
        locations = set()

        # Manufacturing location (from production data)
        # Assume production happens at a single manufacturing location
        # This should be configurable or extracted from network config

        # Collect from shipments
        for ((origin, dest), _, _) in self.shipments_data.keys():
            locations.add(origin)
            locations.add(dest)

        # Collect from inventory
        for (loc, _, _) in self.inventory_frozen.keys():
            locations.add(loc)
        for (loc, _, _) in self.inventory_ambient.keys():
            locations.add(loc)

        return sorted(list(locations))

    def get_truck_movements(self) -> List[TruckMovement]:
        """
        Extract all truck movements from the solution.

        Returns:
            List of TruckMovement objects representing truck trips
        """
        movements = []

        # If we have truck load data, use that
        if self.truck_loads:
            truck_movements_by_key: Dict[Tuple[int, str, Date], TruckMovement] = {}

            for (truck_idx, dest, product, date), quantity in self.truck_loads.items():
                key = (truck_idx, dest, date)

                if key not in truck_movements_by_key:
                    # Create new truck movement
                    # We need to determine origin and arrival date
                    # For now, assume manufacturing origin (6122) and 1-day transit
                    origin = "6122"  # Manufacturing site
                    arrival_date = date + timedelta(days=1)

                    movement = TruckMovement(
                        truck_id=truck_idx,
                        origin=origin,
                        destination=dest,
                        departure_date=date,
                        arrival_date=arrival_date,
                        products={},
                        is_frozen=False,  # Will be determined from route
                        total_units=0.0,
                    )
                    truck_movements_by_key[key] = movement

                # Add product to movement
                truck_movements_by_key[key].products[product] = quantity
                truck_movements_by_key[key].total_units += quantity

            movements.extend(truck_movements_by_key.values())

        # Otherwise, extract from leg-based shipments
        else:
            # Group shipments by origin-dest-date
            shipments_by_leg_date: Dict[Tuple[Tuple[str, str], Date], Dict[str, float]] = defaultdict(dict)

            for ((origin, dest), product, date), quantity in self.shipments_data.items():
                key = ((origin, dest), date)
                shipments_by_leg_date[key][product] = quantity

            # Create truck movements
            for ((origin, dest), date), products in shipments_by_leg_date.items():
                # Determine transit time from route (simplified: assume 1 day)
                transit_days = 1
                arrival_date = date + timedelta(days=transit_days)

                total_units = sum(products.values())

                movement = TruckMovement(
                    truck_id=0,  # Generic truck
                    origin=origin,
                    destination=dest,
                    departure_date=date,
                    arrival_date=arrival_date,
                    products=products,
                    is_frozen=self._is_frozen_route(origin, dest),
                    total_units=total_units,
                )
                movements.append(movement)

        return movements

    def _is_frozen_route(self, origin: str, dest: str) -> bool:
        """Determine if a route uses frozen transport."""
        # Simplified: frozen if destination is Lineage or 6130 (WA)
        frozen_locations = ["Lineage", "6130"]
        return dest in frozen_locations

    def get_location_state(self, location_id: str, date: Date) -> LocationState:
        """
        Get the state of a location on a specific date.

        Args:
            location_id: Location ID
            date: Date to query

        Returns:
            LocationState with all relevant information
        """
        # Get production (only for manufacturing location)
        production = {}
        for (prod_date, product), quantity in self.production_data.items():
            if prod_date == date:
                production[product] = quantity

        # Get inventory
        inventory_frozen = {}
        inventory_ambient = {}

        for (loc, product, inv_date), quantity in self.inventory_frozen.items():
            if loc == location_id and inv_date == date:
                inventory_frozen[product] = quantity

        for (loc, product, inv_date), quantity in self.inventory_ambient.items():
            if loc == location_id and inv_date == date:
                inventory_ambient[product] = quantity

        # Get inbound and outbound shipments
        all_movements = self.get_truck_movements()
        inbound = [m for m in all_movements if m.destination == location_id and m.departure_date == date]
        outbound = [m for m in all_movements if m.origin == location_id and m.departure_date == date]

        # Get demand satisfied (for breadroom locations)
        demand_satisfied = {}
        for (dest, product, delivery_date), quantity in self.shortages.items():
            if dest == location_id and delivery_date == date:
                # Shortage means demand NOT satisfied, so we need to get actual demand
                # This is a simplified approach - actual demand would come from input data
                pass

        return LocationState(
            location_id=location_id,
            date=date,
            production=production,
            inventory_frozen=inventory_frozen,
            inventory_ambient=inventory_ambient,
            inbound_shipments=inbound,
            outbound_shipments=outbound,
            demand_satisfied=demand_satisfied,
        )

    def get_date_range(self) -> Tuple[Date, Date]:
        """Get the date range of the solution."""
        dates = self.get_all_dates()
        if not dates:
            return (Date.today(), Date.today())
        return (dates[0], dates[-1])
