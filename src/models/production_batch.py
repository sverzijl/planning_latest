"""Production batch data model for tracking manufactured goods."""

from datetime import date as Date, datetime
from typing import Optional
from pydantic import BaseModel, Field

from .product import ProductState


class ProductionBatch(BaseModel):
    """
    Represents a production batch manufactured on a specific date.

    Tracks when and how much was produced, the product state,
    and assignment to trucks.

    Attributes:
        id: Unique batch identifier
        product_id: Product manufactured
        manufacturing_site_id: Where it was produced
        production_date: Date of production
        production_time: Optional specific time of production completion
        quantity: Units produced
        initial_state: Initial product state (typically AMBIENT or FROZEN)
        assigned_truck_id: Truck this batch is assigned to (if any)
        sequence_number: Position in daily production sequence (1=first, 2=second, etc.)
        changeover_from_product: Product that was produced immediately before this one
        changeover_time_hours: Time spent on changeover to this product
        labor_hours_used: Labor hours consumed to produce this batch
        production_cost: Total production cost for this batch
    """
    id: str = Field(..., description="Unique batch identifier")
    product_id: str = Field(..., description="Product ID")
    manufacturing_site_id: str = Field(..., description="Manufacturing site ID")
    production_date: Date = Field(..., description="Date of production")
    production_time: Optional[datetime] = Field(
        None,
        description="Specific time of production completion"
    )
    quantity: float = Field(..., description="Quantity produced", gt=0)
    initial_state: ProductState = Field(
        default=ProductState.AMBIENT,
        description="Initial product state after production"
    )
    assigned_truck_id: Optional[str] = Field(
        None,
        description="Assigned truck schedule ID"
    )
    sequence_number: Optional[int] = Field(
        None,
        description="Position in daily production sequence (1=first, 2=second, etc.)",
        ge=1
    )
    changeover_from_product: Optional[str] = Field(
        None,
        description="Product ID that was produced immediately before this batch"
    )
    changeover_time_hours: float = Field(
        default=0.0,
        description="Time spent on changeover to this product (0 for first batch of day)",
        ge=0
    )
    labor_hours_used: float = Field(
        default=0.0,
        description="Labor hours used",
        ge=0
    )
    production_cost: float = Field(
        default=0.0,
        description="Total production cost",
        ge=0
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True

    def is_assigned(self) -> bool:
        """
        Check if batch is assigned to a truck.

        Returns:
            True if assigned_truck_id is set
        """
        return self.assigned_truck_id is not None

    def is_same_day_production(self, truck_departure_date: Date) -> bool:
        """
        Check if this is same-day (D0) production relative to truck departure.

        Args:
            truck_departure_date: Date of truck departure

        Returns:
            True if production date equals departure date
        """
        return self.production_date == truck_departure_date

    def is_previous_day_production(self, truck_departure_date: Date) -> bool:
        """
        Check if this is previous-day (D-1) production relative to truck departure.

        Args:
            truck_departure_date: Date of truck departure

        Returns:
            True if production date is one day before departure date
        """
        from datetime import timedelta
        return self.production_date == truck_departure_date - timedelta(days=1)

    def calculate_total_cost(self, additional_costs: float = 0.0) -> float:
        """
        Calculate total cost including production and any additional costs.

        Args:
            additional_costs: Additional costs to include (e.g., transport, storage)

        Returns:
            Total cost
        """
        return self.production_cost + additional_costs

    def __str__(self) -> str:
        """String representation."""
        truck_info = f" → Truck {self.assigned_truck_id}" if self.assigned_truck_id else ""
        return (
            f"Batch {self.id}: {self.quantity} units of {self.product_id} "
            f"on {self.production_date}{truck_info}"
        )
