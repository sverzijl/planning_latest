"""Cost breakdown data models.

Data classes representing detailed cost components for analysis and reporting.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List


@dataclass
class LaborCostBreakdown:
    """
    Detailed labor cost breakdown by date.

    Tracks fixed hours, overtime, non-fixed labor days, and total costs.

    Attributes:
        total_cost: Total labor cost across all dates
        fixed_hours_cost: Cost of fixed hours (regular rate)
        overtime_cost: Cost of overtime hours (premium rate)
        non_fixed_labor_cost: Cost of non-fixed labor days (weekend/holiday, minimum 4h)
        total_hours: Total labor hours used
        fixed_hours: Total fixed hours used
        overtime_hours: Total overtime hours (beyond fixed)
        non_fixed_hours: Total hours on non-fixed labor days
        daily_breakdown: Cost breakdown by date
    """
    total_cost: float = 0.0
    fixed_hours_cost: float = 0.0
    overtime_cost: float = 0.0
    non_fixed_labor_cost: float = 0.0
    total_hours: float = 0.0
    fixed_hours: float = 0.0
    overtime_hours: float = 0.0
    non_fixed_hours: float = 0.0
    daily_breakdown: Dict[date, Dict[str, float]] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Labor Cost: ${self.total_cost:,.2f} "
            f"({self.total_hours:.1f}h: {self.fixed_hours:.1f}h fixed, "
            f"{self.overtime_hours:.1f}h OT, {self.non_fixed_hours:.1f}h non-fixed)"
        )


@dataclass
class TransportCostBreakdown:
    """
    Detailed transport cost breakdown by route.

    Tracks costs per route leg and cumulative costs.

    Attributes:
        total_cost: Total transport cost across all shipments
        total_units_shipped: Total units shipped
        average_cost_per_unit: Average transport cost per unit
        cost_by_route: Cost breakdown by route path
        cost_by_leg: Cost breakdown by individual route leg
        shipment_details: Per-shipment cost details
    """
    total_cost: float = 0.0
    total_units_shipped: float = 0.0
    average_cost_per_unit: float = 0.0
    cost_by_route: Dict[str, float] = field(default_factory=dict)
    cost_by_leg: Dict[str, float] = field(default_factory=dict)
    shipment_details: List[Dict] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Transport Cost: ${self.total_cost:,.2f} "
            f"({self.total_units_shipped:,.0f} units @ ${self.average_cost_per_unit:.4f}/unit)"
        )


@dataclass
class ProductionCostBreakdown:
    """
    Detailed production cost breakdown by product.

    Tracks per-unit production costs across batches.

    Attributes:
        total_cost: Total production cost across all batches
        total_units_produced: Total units produced
        average_cost_per_unit: Average production cost per unit
        cost_by_product: Cost breakdown by product
        cost_by_date: Cost breakdown by production date
        batch_details: Per-batch cost details
    """
    total_cost: float = 0.0
    total_units_produced: float = 0.0
    average_cost_per_unit: float = 0.0
    cost_by_product: Dict[str, float] = field(default_factory=dict)
    cost_by_date: Dict[date, float] = field(default_factory=dict)
    batch_details: List[Dict] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Production Cost: ${self.total_cost:,.2f} "
            f"({self.total_units_produced:,.0f} units @ ${self.average_cost_per_unit:.4f}/unit)"
        )


@dataclass
class WasteCostBreakdown:
    """
    Detailed waste cost breakdown.

    Tracks costs of expired, discarded, or unmet demand.

    Attributes:
        total_cost: Total waste cost
        expired_units: Units that expired (shelf life)
        expired_cost: Cost of expired inventory
        unmet_demand_units: Units of unmet demand
        unmet_demand_cost: Opportunity cost of unmet demand
        waste_by_location: Waste breakdown by location
        waste_by_product: Waste breakdown by product
        waste_details: Per-incident waste details
    """
    total_cost: float = 0.0
    expired_units: float = 0.0
    expired_cost: float = 0.0
    unmet_demand_units: float = 0.0
    unmet_demand_cost: float = 0.0
    waste_by_location: Dict[str, float] = field(default_factory=dict)
    waste_by_product: Dict[str, float] = field(default_factory=dict)
    waste_details: List[Dict] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Waste Cost: ${self.total_cost:,.2f} "
            f"({self.expired_units:,.0f} expired, {self.unmet_demand_units:,.0f} unmet)"
        )


@dataclass
class TotalCostBreakdown:
    """
    Aggregated cost breakdown across all components.

    Combines labor, production, transport, and waste costs into total cost to serve.

    Attributes:
        total_cost: Total cost to serve (sum of all components)
        labor: Labor cost breakdown
        production: Production cost breakdown
        transport: Transport cost breakdown
        waste: Waste cost breakdown
        cost_per_unit_delivered: Average cost per unit delivered to customer
    """
    total_cost: float = 0.0
    labor: LaborCostBreakdown = field(default_factory=LaborCostBreakdown)
    production: ProductionCostBreakdown = field(default_factory=ProductionCostBreakdown)
    transport: TransportCostBreakdown = field(default_factory=TransportCostBreakdown)
    waste: WasteCostBreakdown = field(default_factory=WasteCostBreakdown)
    cost_per_unit_delivered: float = 0.0

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Total Cost to Serve: ${self.total_cost:,.2f}\n"
            f"  {self.labor}\n"
            f"  {self.production}\n"
            f"  {self.transport}\n"
            f"  {self.waste}\n"
            f"  Cost per unit delivered: ${self.cost_per_unit_delivered:.4f}"
        )

    def get_cost_proportions(self) -> Dict[str, float]:
        """
        Get proportion of each cost component.

        Returns:
            Dictionary mapping component name to proportion (0.0 to 1.0)
        """
        if self.total_cost == 0:
            return {"labor": 0.0, "production": 0.0, "transport": 0.0, "waste": 0.0}

        return {
            "labor": self.labor.total_cost / self.total_cost,
            "production": self.production.total_cost / self.total_cost,
            "transport": self.transport.total_cost / self.total_cost,
            "waste": self.waste.total_cost / self.total_cost,
        }
