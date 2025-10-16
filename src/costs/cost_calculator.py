"""Cost calculator aggregator.

Combines all cost components into total cost to serve:
- Labor costs
- Production costs
- Transport costs
- Waste costs
"""

from typing import List, Optional, Dict

from src.models.cost_structure import CostStructure
from src.models.labor_calendar import LaborCalendar
from src.models.forecast import Forecast
from src.models.shipment import Shipment
from src.models.production_schedule import ProductionSchedule
from .cost_breakdown import TotalCostBreakdown
from .labor_cost_calculator import LaborCostCalculator
from .production_cost_calculator import ProductionCostCalculator
from .transport_cost_calculator import TransportCostCalculator
from .waste_cost_calculator import WasteCostCalculator


class CostCalculator:
    """
    Aggregates all cost components into total cost to serve.

    Coordinates individual cost calculators:
    - LaborCostCalculator: Labor costs from production schedule and calendar
    - ProductionCostCalculator: Per-unit production costs
    - TransportCostCalculator: Transport costs from shipments and routes
    - WasteCostCalculator: Waste and unmet demand costs

    Example:
        calculator = CostCalculator(cost_structure, labor_calendar)
        total_cost = calculator.calculate_total_cost(
            production_schedule=schedule,
            shipments=shipments,
            forecast=forecast
        )
        print(total_cost)  # Shows full breakdown
    """

    def __init__(
        self,
        cost_structure: CostStructure,
        labor_calendar: LaborCalendar
    ):
        """
        Initialize cost calculator.

        Args:
            cost_structure: Cost structure with rates and penalties
            labor_calendar: Labor calendar with daily rates and fixed hours
        """
        self.cost_structure = cost_structure
        self.labor_calendar = labor_calendar

        # Initialize component calculators
        self.labor_calculator = LaborCostCalculator(labor_calendar)
        self.production_calculator = ProductionCostCalculator(cost_structure)
        self.transport_calculator = TransportCostCalculator()
        self.waste_calculator = WasteCostCalculator(cost_structure)

    def calculate_total_cost(
        self,
        production_schedule: ProductionSchedule,
        shipments: List[Shipment],
        forecast: Forecast,
        expired_units: Optional[Dict[str, float]] = None
    ) -> TotalCostBreakdown:
        """
        Calculate total cost to serve.

        Aggregates all cost components:
        1. Labor costs from production schedule and calendar
        2. Production costs from batches
        3. Transport costs from shipments
        4. Waste costs from expired inventory and unmet demand

        Args:
            production_schedule: Production schedule with batches
            shipments: List of shipments with routes
            forecast: Demand forecast (for unmet demand calculation)
            expired_units: Optional dict of location_id -> units expired

        Returns:
            Complete cost breakdown with all components
        """
        breakdown = TotalCostBreakdown()

        # Calculate labor costs
        breakdown.labor = self.labor_calculator.calculate_labor_cost(production_schedule)

        # Calculate production costs
        breakdown.production = self.production_calculator.calculate_production_cost(production_schedule)

        # Calculate transport costs
        breakdown.transport = self.transport_calculator.calculate_transport_cost(shipments)

        # Calculate waste costs
        breakdown.waste = self.waste_calculator.calculate_waste_cost(
            forecast=forecast,
            shipments=shipments,
            expired_units=expired_units
        )

        # Calculate total cost
        breakdown.total_cost = (
            breakdown.labor.total_cost +
            breakdown.production.total_cost +
            breakdown.transport.total_cost +
            breakdown.waste.total_cost
        )

        # Calculate cost per unit delivered
        units_delivered = breakdown.transport.total_units_shipped
        if units_delivered > 0:
            breakdown.cost_per_unit_delivered = breakdown.total_cost / units_delivered

        return breakdown

    def calculate_labor_cost(self, production_schedule: ProductionSchedule):
        """Calculate labor cost only."""
        return self.labor_calculator.calculate_labor_cost(production_schedule)

    def calculate_production_cost(self, production_schedule: ProductionSchedule):
        """Calculate production cost only."""
        return self.production_calculator.calculate_production_cost(production_schedule)

    def calculate_transport_cost(self, shipments: List[Shipment]):
        """Calculate transport cost only."""
        return self.transport_calculator.calculate_transport_cost(shipments)

    def calculate_waste_cost(
        self,
        forecast: Forecast,
        shipments: List[Shipment],
        expired_units: Optional[Dict[str, float]] = None
    ):
        """Calculate waste cost only."""
        return self.waste_calculator.calculate_waste_cost(
            forecast=forecast,
            shipments=shipments,
            expired_units=expired_units
        )
