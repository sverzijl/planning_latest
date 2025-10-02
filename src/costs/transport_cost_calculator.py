"""Transport cost calculator.

Calculates transport costs from shipments and routes, accounting for:
- Per-unit costs across route legs
- Cumulative costs from origin to destination
- Cost breakdown by route and leg
"""

from typing import List, Dict

from src.models.shipment import Shipment
from .cost_breakdown import TransportCostBreakdown


class TransportCostCalculator:
    """
    Calculates transport costs from shipments.

    Uses route costs from shipments (which are cumulative across legs) to compute:
    - Total transport cost across all shipments
    - Average cost per unit
    - Cost breakdown by route and individual legs

    Example:
        calculator = TransportCostCalculator()
        breakdown = calculator.calculate_transport_cost(shipments)
        print(f"Total transport cost: ${breakdown.total_cost:,.2f}")
    """

    def calculate_transport_cost(self, shipments: List[Shipment]) -> TransportCostBreakdown:
        """
        Calculate total transport cost from shipments.

        For each shipment:
        1. Get route from shipment
        2. Calculate total cost = quantity × route.total_cost
        3. Break down by individual legs
        4. Aggregate across all shipments

        Args:
            shipments: List of shipments with routes

        Returns:
            Detailed transport cost breakdown
        """
        breakdown = TransportCostBreakdown()

        for shipment in shipments:
            route = shipment.route
            quantity = shipment.quantity

            # Total cost for this shipment
            shipment_cost = quantity * route.total_cost

            # Route path string for grouping
            route_path = " → ".join(route.path)

            # Update totals
            breakdown.total_cost += shipment_cost
            breakdown.total_units_shipped += quantity

            # Update cost by route
            if route_path not in breakdown.cost_by_route:
                breakdown.cost_by_route[route_path] = 0.0
            breakdown.cost_by_route[route_path] += shipment_cost

            # Update cost by leg (note: individual leg costs not available in current model)
            # For now, we only track total route costs
            # In future, could decompose route.total_cost across route.route_legs

            # Shipment detail
            breakdown.shipment_details.append({
                "shipment_id": shipment.id,
                "product_id": shipment.product_id,
                "quantity": quantity,
                "route": route_path,
                "cost_per_unit": route.total_cost,
                "total_cost": shipment_cost,
            })

        # Calculate average cost per unit
        if breakdown.total_units_shipped > 0:
            breakdown.average_cost_per_unit = breakdown.total_cost / breakdown.total_units_shipped

        return breakdown

    def calculate_shipment_cost(self, shipment: Shipment) -> float:
        """
        Calculate transport cost for a single shipment.

        Args:
            shipment: Shipment with route

        Returns:
            Total transport cost for this shipment
        """
        return shipment.quantity * shipment.route.total_cost

    def calculate_route_cost(self, quantity: float, route) -> float:
        """
        Calculate transport cost for a given quantity on a route.

        Args:
            quantity: Units to transport
            route: RoutePath object

        Returns:
            Total transport cost
        """
        return quantity * route.total_cost
