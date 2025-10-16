"""Production cost calculator.

Calculates production costs from production batches, accounting for:
- Per-unit production costs
- Cost breakdown by product and date
"""

from typing import List, Dict
from datetime import date

from src.models.production_schedule import ProductionSchedule
from src.models.production_batch import ProductionBatch
from src.models.cost_structure import CostStructure
from .cost_breakdown import ProductionCostBreakdown


class ProductionCostCalculator:
    """
    Calculates production costs from production schedule.

    Uses per-unit production costs from cost structure to compute:
    - Total production cost across all batches
    - Average cost per unit
    - Cost breakdown by product and date

    Example:
        calculator = ProductionCostCalculator(cost_structure)
        breakdown = calculator.calculate_production_cost(production_schedule)
        print(f"Total production cost: ${breakdown.total_cost:,.2f}")
    """

    def __init__(self, cost_structure: CostStructure):
        """
        Initialize production cost calculator.

        Args:
            cost_structure: Cost structure with per-unit production cost
        """
        self.cost_structure = cost_structure

    def calculate_production_cost(
        self,
        schedule: ProductionSchedule
    ) -> ProductionCostBreakdown:
        """
        Calculate total production cost from production schedule.

        For each batch:
        1. Get per-unit production cost from cost structure
        2. Calculate total cost = quantity × cost_per_unit
        3. Aggregate by product and date
        4. Sum across all batches

        Args:
            schedule: Production schedule with batches

        Returns:
            Detailed production cost breakdown
        """
        breakdown = ProductionCostBreakdown()

        for batch in schedule.production_batches:
            # Calculate batch cost
            batch_cost = batch.quantity * self.cost_structure.production_cost_per_unit

            # Update totals
            breakdown.total_cost += batch_cost
            breakdown.total_units_produced += batch.quantity

            # Update cost by product
            if batch.product_id not in breakdown.cost_by_product:
                breakdown.cost_by_product[batch.product_id] = 0.0
            breakdown.cost_by_product[batch.product_id] += batch_cost

            # Update cost by date
            if batch.production_date not in breakdown.cost_by_date:
                breakdown.cost_by_date[batch.production_date] = 0.0
            breakdown.cost_by_date[batch.production_date] += batch_cost

            # Batch detail
            breakdown.batch_details.append({
                "batch_id": batch.id,
                "product_id": batch.product_id,
                "production_date": batch.production_date,
                "quantity": batch.quantity,
                "cost_per_unit": self.cost_structure.production_cost_per_unit,
                "total_cost": batch_cost,
            })

        # Calculate average cost per unit
        if breakdown.total_units_produced > 0:
            breakdown.average_cost_per_unit = breakdown.total_cost / breakdown.total_units_produced

        return breakdown

    def calculate_batch_cost(self, batch: ProductionBatch) -> float:
        """
        Calculate production cost for a single batch.

        Args:
            batch: Production batch

        Returns:
            Total production cost for this batch
        """
        return batch.quantity * self.cost_structure.production_cost_per_unit

    def calculate_quantity_cost(self, quantity: float) -> float:
        """
        Calculate production cost for a given quantity.

        Args:
            quantity: Units to produce

        Returns:
            Total production cost
        """
        return quantity * self.cost_structure.production_cost_per_unit
