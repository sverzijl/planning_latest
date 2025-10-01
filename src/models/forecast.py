"""Forecast data model for demand planning."""

from datetime import date as Date
from typing import Optional
from pydantic import BaseModel, Field


class ForecastEntry(BaseModel):
    """
    Represents a single forecast entry for demand at a location.

    Attributes:
        location_id: ID of the breadroom/destination
        product_id: ID of the product
        forecast_date: Date of the forecast
        quantity: Forecasted demand quantity
        confidence: Optional confidence level (0-1)
    """
    location_id: str = Field(..., description="Destination location ID")
    product_id: str = Field(..., description="Product ID")
    forecast_date: Date = Field(..., description="Date of forecast")
    quantity: float = Field(..., description="Forecasted quantity", ge=0)
    confidence: Optional[float] = Field(
        None,
        description="Forecast confidence level",
        ge=0,
        le=1
    )

    def __str__(self) -> str:
        """String representation."""
        conf_str = f" (conf: {self.confidence:.1%})" if self.confidence else ""
        return (
            f"{self.forecast_date}: {self.quantity:.0f} units "
            f"of {self.product_id} to {self.location_id}{conf_str}"
        )


class Forecast(BaseModel):
    """
    Container for multiple forecast entries.

    Attributes:
        name: Name of the forecast (e.g., "Q4 2025 Forecast")
        entries: List of forecast entries
        creation_date: Date when forecast was created
    """
    name: str = Field(..., description="Forecast name")
    entries: list[ForecastEntry] = Field(
        default_factory=list,
        description="List of forecast entries"
    )
    creation_date: Date = Field(
        default_factory=Date.today,
        description="Forecast creation date"
    )

    def get_demand(self, location_id: str, product_id: str, forecast_date: Date) -> float:
        """
        Get forecasted demand for a specific location, product, and date.

        Args:
            location_id: Location ID
            product_id: Product ID
            forecast_date: Date to query

        Returns:
            Forecasted quantity (0 if not found)
        """
        for entry in self.entries:
            if (entry.location_id == location_id and
                entry.product_id == product_id and
                entry.forecast_date == forecast_date):
                return entry.quantity
        return 0.0

    def __str__(self) -> str:
        """String representation."""
        return f"Forecast '{self.name}' with {len(self.entries)} entries"
