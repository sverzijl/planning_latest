"""Shipment data model for distribution planning.

A shipment represents a portion of a production batch that needs to be
delivered to a specific destination via a specific route.
"""

from datetime import date
from typing import Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.network import RoutePath


class Shipment(BaseModel):
    """
    Represents a shipment from production to destination.

    A shipment links a production batch to a specific delivery destination,
    capturing the route, timing, and truck assignment for distribution planning.

    Attributes:
        id: Unique shipment identifier
        batch_id: ID of the production batch this shipment comes from
        product_id: Product being shipped
        quantity: Units in this shipment
        origin_id: Origin location (typically manufacturing site)
        destination_id: Final destination location ID
        delivery_date: Required delivery date at destination
        route: Complete route path from origin to destination
        assigned_truck_id: Truck schedule ID if assigned
        production_date: Date when batch was/will be produced
    """
    id: str = Field(..., description="Unique shipment identifier")
    batch_id: str = Field(..., description="Production batch ID")
    product_id: str = Field(..., description="Product ID")
    quantity: float = Field(..., description="Quantity in units", gt=0)
    origin_id: str = Field(..., description="Origin location ID")
    destination_id: str = Field(..., description="Final destination location ID")
    delivery_date: date = Field(..., description="Required delivery date")
    route: "RoutePath" = Field(..., description="Route from origin to destination")
    assigned_truck_id: Optional[str] = Field(
        None,
        description="Assigned truck schedule ID"
    )
    production_date: date = Field(..., description="Production date of batch")

    @property
    def first_leg_destination(self) -> str:
        """
        Get the destination of the first route leg.

        This is critical for truck loading - shipments are assigned to trucks
        based on matching the truck's destination to the first leg destination.

        Returns:
            Destination ID of first leg in route

        Example:
            Route: 6122 → 6125 → 6103
            First leg: 6122 → 6125
            first_leg_destination = "6125"
            This shipment goes on trucks to 6125 (morning truck Mon-Fri)
        """
        if not self.route.route_legs or len(self.route.route_legs) == 0:
            return self.destination_id

        return self.route.route_legs[0].to_location_id

    @property
    def total_transit_days(self) -> int:
        """
        Get total transit time for the route.

        Returns:
            Total days from origin to destination
        """
        return self.route.total_transit_days

    def is_assigned(self) -> bool:
        """
        Check if shipment is assigned to a truck.

        Returns:
            True if assigned_truck_id is set
        """
        return self.assigned_truck_id is not None

    def is_d1_production(self, truck_departure_date: date) -> bool:
        """
        Check if this is D-1 production relative to truck departure.

        D-1 means the batch was produced the day before the truck departs.
        Morning and afternoon trucks both prefer D-1 production.

        Args:
            truck_departure_date: Date when truck departs

        Returns:
            True if production_date is one day before truck departure
        """
        from datetime import timedelta
        return self.production_date == truck_departure_date - timedelta(days=1)

    def is_d0_production(self, truck_departure_date: date) -> bool:
        """
        Check if this is D0 (same-day) production relative to truck departure.

        D0 means the batch was produced on the same day as truck departure.
        Only afternoon trucks can load D0 production, and only if ready before cutoff.

        Args:
            truck_departure_date: Date when truck departs

        Returns:
            True if production_date equals truck departure date
        """
        return self.production_date == truck_departure_date

    def __str__(self) -> str:
        """String representation."""
        truck_info = f" → Truck {self.assigned_truck_id}" if self.assigned_truck_id else " [unassigned]"
        return (
            f"Shipment {self.id}: {self.quantity:.0f} units of {self.product_id} "
            f"from {self.origin_id} to {self.destination_id} on {self.delivery_date}{truck_info}"
        )
