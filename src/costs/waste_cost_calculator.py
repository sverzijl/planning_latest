"""Waste cost calculator.

Calculates waste costs from expired inventory and unmet demand, accounting for:
- Expired units (shelf life violations)
- Unmet demand (opportunity cost)
- Production and transport costs sunk into wasted product

NOTE: Full waste calculation requires shelf life tracking (Phase 3).
For Phase 2, provides basic framework and unmet demand tracking.
"""

from typing import List, Dict

from src.models.cost_structure import CostStructure
from src.models.forecast import Forecast
from src.models.shipment import Shipment
from .cost_breakdown import WasteCostBreakdown


class WasteCostCalculator:
    """
    Calculates waste costs from various sources.

    Computes costs for:
    - Expired inventory (units that exceeded shelf life)
    - Unmet demand (forecast not satisfied)
    - Includes sunk costs (production + transport to point of waste)

    Example:
        calculator = WasteCostCalculator(cost_structure)
        breakdown = calculator.calculate_waste_cost(
            forecast=forecast,
            shipments=shipments,
            expired_units={}
        )
        print(f"Total waste cost: ${breakdown.total_cost:,.2f}")
    """

    def __init__(self, cost_structure: CostStructure):
        """
        Initialize waste cost calculator.

        Args:
            cost_structure: Cost structure with waste penalty and production cost
        """
        self.cost_structure = cost_structure

    def calculate_waste_cost(
        self,
        forecast: Forecast,
        shipments: List[Shipment],
        expired_units: Dict[str, float] = None
    ) -> WasteCostBreakdown:
        """
        Calculate total waste cost.

        Args:
            forecast: Demand forecast
            shipments: List of shipments (for unmet demand calculation)
            expired_units: Optional dict of location_id -> units expired
                          (requires shelf life tracking - Phase 3)

        Returns:
            Detailed waste cost breakdown
        """
        breakdown = WasteCostBreakdown()

        # Calculate unmet demand
        unmet = self._calculate_unmet_demand(forecast, shipments)
        breakdown.unmet_demand_units = unmet["total_units"]
        breakdown.unmet_demand_cost = unmet["total_cost"]
        breakdown.waste_by_location.update(unmet["by_location"])
        breakdown.waste_by_product.update(unmet["by_product"])

        # Calculate expired units cost (if provided)
        if expired_units:
            expired = self._calculate_expired_cost(expired_units)
            breakdown.expired_units = expired["total_units"]
            breakdown.expired_cost = expired["total_cost"]

            # Merge into waste_by_location
            for loc, cost in expired["by_location"].items():
                if loc not in breakdown.waste_by_location:
                    breakdown.waste_by_location[loc] = 0.0
                breakdown.waste_by_location[loc] += cost

            breakdown.waste_details.extend(expired["details"])

        # Total waste cost
        breakdown.total_cost = breakdown.unmet_demand_cost + breakdown.expired_cost

        return breakdown

    def _calculate_unmet_demand(
        self,
        forecast: Forecast,
        shipments: List[Shipment]
    ) -> Dict:
        """
        Calculate cost of unmet demand.

        Compares forecast to shipments delivered on the same date.

        KNOWN LIMITATION: This method only considers shipments delivered ON the demand date,
        ignoring pre-positioned inventory from earlier deliveries. This can overestimate
        unmet demand costs when inventory is held at locations.

        For accurate demand satisfaction tracking that includes pre-positioned inventory,
        use DailySnapshotGenerator which tracks cumulative inventory over time.

        Phase 3 enhancement: Implement chronological inventory tracking to account for
        inventory carried forward from earlier deliveries.

        Args:
            forecast: Demand forecast
            shipments: List of shipments

        Returns:
            Dictionary with unmet demand details
        """
        # Build demand by (location, date, product)
        demand: Dict[tuple, float] = {}
        for entry in forecast.entries:
            key = (entry.location_id, entry.forecast_date, entry.product_id)
            demand[key] = entry.quantity

        # Build shipments by (location, delivery_date, product)
        shipped: Dict[tuple, float] = {}
        for shipment in shipments:
            key = (shipment.destination_id, shipment.delivery_date, shipment.product_id)
            if key not in shipped:
                shipped[key] = 0.0
            shipped[key] += shipment.quantity

        # Calculate unmet demand
        total_units = 0.0
        total_cost = 0.0
        by_location: Dict[str, float] = {}
        by_product: Dict[str, float] = {}

        for key, demand_qty in demand.items():
            location_id, delivery_date, product_id = key
            shipped_qty = shipped.get(key, 0.0)
            unmet = max(0.0, demand_qty - shipped_qty)

            if unmet > 0:
                # Cost = lost revenue (use shortage penalty as proxy for opportunity cost)
                cost = unmet * self.cost_structure.shortage_penalty_per_unit

                total_units += unmet
                total_cost += cost

                if location_id not in by_location:
                    by_location[location_id] = 0.0
                by_location[location_id] += cost

                if product_id not in by_product:
                    by_product[product_id] = 0.0
                by_product[product_id] += cost

        return {
            "total_units": total_units,
            "total_cost": total_cost,
            "by_location": by_location,
            "by_product": by_product,
        }

    def _calculate_expired_cost(self, expired_units: Dict[str, float]) -> Dict:
        """
        Calculate cost of expired inventory.

        Args:
            expired_units: Dictionary mapping location_id to units expired

        Returns:
            Dictionary with expired inventory details
        """
        total_units = 0.0
        total_cost = 0.0
        by_location: Dict[str, float] = {}
        details = []

        for location_id, units in expired_units.items():
            # Cost = production cost × waste multiplier
            # (transport cost would need route tracking - simplified for Phase 2)
            cost_per_unit = (
                self.cost_structure.production_cost_per_unit *
                self.cost_structure.waste_cost_multiplier
            )
            cost = units * cost_per_unit

            total_units += units
            total_cost += cost
            by_location[location_id] = cost

            details.append({
                "location_id": location_id,
                "units_expired": units,
                "cost_per_unit": cost_per_unit,
                "total_cost": cost,
            })

        return {
            "total_units": total_units,
            "total_cost": total_cost,
            "by_location": by_location,
            "details": details,
        }

    def calculate_unmet_demand_penalty(self, units: float) -> float:
        """
        Calculate penalty for unmet demand.

        Args:
            units: Units of unmet demand

        Returns:
            Penalty cost
        """
        return units * self.cost_structure.shortage_penalty_per_unit
