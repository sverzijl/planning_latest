"""Window configuration and results for rolling horizon optimization.

This module provides configuration classes for rolling horizon windows and
data structures to hold window-specific solutions.
"""

from datetime import date as Date
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from src.models.forecast import Forecast
from src.models.time_period import VariableGranularityConfig
from src.models.shipment import Shipment
from src.models.production_batch import ProductionBatch
from src.optimization.base_model import OptimizationResult


class WindowConfig(BaseModel):
    """
    Configuration for a single window in rolling horizon optimization.

    Attributes:
        window_id: Unique identifier for this window (e.g., "window_1")
        start_date: First date in the window (inclusive)
        end_date: Last date in the window (inclusive)
        overlap_start: Start of overlap region with next window (None for last window)
        overlap_end: End of overlap region (None for last window)
        forecast_subset: Forecast filtered to this window's date range
        initial_inventory: Starting inventory from previous window
                          Dict mapping (destination_id, product_id) -> quantity
        granularity_config: Optional variable granularity configuration
        is_first_window: True if this is the first window in the sequence
        is_last_window: True if this is the last window in the sequence

    Example:
        # First window in 29-week horizon (4 weeks + 1 week overlap)
        config = WindowConfig(
            window_id="window_1",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 28),  # 4 weeks
            overlap_start=date(2025, 6, 22),  # Last week is overlap
            overlap_end=date(2025, 6, 28),
            forecast_subset=forecast_window1,
            initial_inventory={},  # Empty for first window
            is_first_window=True,
            is_last_window=False
        )
    """

    window_id: str = Field(..., description="Unique window identifier")
    start_date: Date = Field(..., description="Window start date (inclusive)")
    end_date: Date = Field(..., description="Window end date (inclusive)")
    overlap_start: Optional[Date] = Field(
        None,
        description="Start of overlap region with next window"
    )
    overlap_end: Optional[Date] = Field(
        None,
        description="End of overlap region with next window"
    )
    forecast_subset: Forecast = Field(..., description="Forecast for this window")
    initial_inventory: Dict[Tuple[str, str], float] = Field(
        default_factory=dict,
        description="Initial inventory: (dest_id, product_id) -> quantity"
    )
    granularity_config: Optional[VariableGranularityConfig] = Field(
        None,
        description="Optional variable granularity configuration"
    )
    is_first_window: bool = Field(False, description="True if first window")
    is_last_window: bool = Field(False, description="True if last window")

    class Config:
        arbitrary_types_allowed = True

    @property
    def num_days(self) -> int:
        """Get number of days in this window."""
        return (self.end_date - self.start_date).days + 1

    @property
    def has_overlap(self) -> bool:
        """Check if this window has overlap with next window."""
        return self.overlap_start is not None and self.overlap_end is not None

    @property
    def overlap_days(self) -> int:
        """Get number of days in overlap region."""
        if not self.has_overlap:
            return 0
        return (self.overlap_end - self.overlap_start).days + 1

    @property
    def committed_end_date(self) -> Date:
        """Get end date of committed (non-overlap) region."""
        if self.has_overlap:
            return self.overlap_start - __import__('datetime').timedelta(days=1)
        return self.end_date

    def __str__(self) -> str:
        """String representation."""
        overlap_str = f" (overlap: {self.overlap_days}d)" if self.has_overlap else ""
        return f"Window[{self.window_id}]: {self.start_date} to {self.end_date} ({self.num_days}d{overlap_str})"


@dataclass
class WindowSolution:
    """
    Solution for a single window in rolling horizon optimization.

    Contains all decision variable values and metadata for one window solve.

    Attributes:
        window_id: Identifier matching the WindowConfig
        optimization_result: Raw optimization result (status, objective, etc.)
        production_by_date_product: Production quantities
                                   Dict: {date: {product_id: quantity}}
        shipments_by_route_product_date: Shipment quantities
                                        Dict: {(route_idx, product_id, delivery_date): quantity}
        ending_inventory: Inventory at end of window (handoff to next window)
                         Dict: {(dest_id, product_id): quantity}
        total_cost: Total cost for this window
        labor_cost: Labor cost component
        production_cost: Production cost component
        transport_cost: Transport cost component
        inventory_cost: Inventory holding cost component
        truck_cost: Truck fixed cost component
        shortage_cost: Shortage penalty cost component
        labor_cost_by_date: Labor cost for each date (for accurate stitching)
        solve_time_seconds: Time taken to solve this window
        production_batches: List of ProductionBatch objects (if extracted)
        shipments: List of Shipment objects (if extracted)

    Note:
        Only the committed (non-overlap) portion of the solution should be
        used when stitching windows together.
    """

    window_id: str
    optimization_result: OptimizationResult
    production_by_date_product: Dict[Date, Dict[str, float]] = field(default_factory=dict)
    shipments_by_route_product_date: Dict[Tuple, float] = field(default_factory=dict)
    ending_inventory: Dict[Tuple[str, str], float] = field(default_factory=dict)
    total_cost: float = 0.0
    labor_cost: float = 0.0
    production_cost: float = 0.0
    transport_cost: float = 0.0
    inventory_cost: float = 0.0
    truck_cost: float = 0.0
    shortage_cost: float = 0.0
    labor_cost_by_date: Dict[Date, float] = field(default_factory=dict)
    solve_time_seconds: float = 0.0
    production_batches: List[ProductionBatch] = field(default_factory=list)
    shipments: List[Shipment] = field(default_factory=list)

    def is_feasible(self) -> bool:
        """Check if window solution is feasible."""
        return self.optimization_result.is_feasible()

    def is_optimal(self) -> bool:
        """Check if window solution is optimal."""
        return self.optimization_result.is_optimal()

    def __str__(self) -> str:
        """String representation."""
        status = "OPTIMAL" if self.is_optimal() else "FEASIBLE" if self.is_feasible() else "INFEASIBLE"
        return (
            f"WindowSolution[{self.window_id}]: {status}, "
            f"cost=${self.total_cost:,.2f}, time={self.solve_time_seconds:.2f}s"
        )


@dataclass
class RollingHorizonResult:
    """
    Complete results from rolling horizon optimization.

    Aggregates results across all windows in the rolling horizon solve.

    Attributes:
        window_results: List of WindowSolution objects (one per window)
        complete_production_plan: Stitched production plan across all windows
                                 Dict: {date: {product_id: quantity}}
        complete_shipment_plan: Stitched shipment plan across all windows
        total_cost: Total cost across all windows (from committed regions only)
        total_solve_time: Total time taken to solve all windows
        num_windows: Number of windows solved
        all_feasible: True if all windows found feasible solutions
        metadata: Additional result metadata

    Example:
        result = rolling_horizon_solver.solve(forecast, ...)
        if result.all_feasible:
            print(f"Total cost: ${result.total_cost:,.2f}")
            print(f"Solve time: {result.total_solve_time:.2f}s")
            print(f"Num windows: {result.num_windows}")
    """

    window_results: List[WindowSolution] = field(default_factory=list)
    complete_production_plan: Dict[Date, Dict[str, float]] = field(default_factory=dict)
    complete_shipment_plan: List[Shipment] = field(default_factory=list)
    total_cost: float = 0.0
    total_solve_time: float = 0.0
    num_windows: int = 0
    all_feasible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def average_solve_time_per_window(self) -> float:
        """Get average solve time per window."""
        if self.num_windows == 0:
            return 0.0
        return self.total_solve_time / self.num_windows

    @property
    def infeasible_windows(self) -> List[str]:
        """Get list of window IDs that were infeasible."""
        return [
            ws.window_id for ws in self.window_results
            if not ws.is_feasible()
        ]

    def __str__(self) -> str:
        """String representation."""
        status = "ALL FEASIBLE" if self.all_feasible else f"INFEASIBLE: {len(self.infeasible_windows)} windows"
        return (
            f"RollingHorizonResult: {status}, "
            f"{self.num_windows} windows, "
            f"cost=${self.total_cost:,.2f}, "
            f"time={self.total_solve_time:.2f}s "
            f"({self.average_solve_time_per_window:.2f}s/window)"
        )


def create_windows(
    start_date: Date,
    end_date: Date,
    window_size_days: int,
    overlap_days: int,
    forecast: Forecast,
    initial_inventory: Optional[Dict[Tuple[str, str], float]] = None
) -> List[WindowConfig]:
    """
    Create rolling horizon windows with overlap.

    Args:
        start_date: First date in full planning horizon
        end_date: Last date in full planning horizon
        window_size_days: Size of each window in days
        overlap_days: Number of days to overlap between windows
        forecast: Full forecast (will be filtered per window)
        initial_inventory: Initial inventory for first window

    Returns:
        List of WindowConfig objects

    Example:
        # 29 weeks (203 days) with 4-week windows and 1-week overlap
        windows = create_windows(
            start_date=date(2025, 6, 1),
            end_date=date(2025, 12, 20),  # 203 days
            window_size_days=28,  # 4 weeks
            overlap_days=7,  # 1 week
            forecast=full_forecast
        )
        # Result: ~8 windows covering the full horizon
    """
    if initial_inventory is None:
        initial_inventory = {}

    if window_size_days <= overlap_days:
        raise ValueError(f"window_size_days ({window_size_days}) must be > overlap_days ({overlap_days})")

    windows = []
    current_start = start_date
    window_count = 0

    while current_start <= end_date:
        window_count += 1
        window_id = f"window_{window_count}"

        # Calculate window end date
        window_end = min(
            current_start + __import__('datetime').timedelta(days=window_size_days - 1),
            end_date
        )

        # Calculate overlap region (except for last window)
        is_last = window_end >= end_date
        if not is_last and overlap_days > 0:
            # Overlap starts overlap_days before window end
            overlap_start = window_end - __import__('datetime').timedelta(days=overlap_days - 1)
            overlap_end = window_end
        else:
            overlap_start = None
            overlap_end = None

        # Filter forecast to this window
        forecast_entries = [
            e for e in forecast.entries
            if current_start <= e.forecast_date <= window_end
        ]
        forecast_subset = Forecast(
            name=f"{forecast.name}_{window_id}",
            entries=forecast_entries,
            creation_date=forecast.creation_date
        )

        # Create window config
        window = WindowConfig(
            window_id=window_id,
            start_date=current_start,
            end_date=window_end,
            overlap_start=overlap_start,
            overlap_end=overlap_end,
            forecast_subset=forecast_subset,
            initial_inventory=initial_inventory.copy(),
            is_first_window=(window_count == 1),
            is_last_window=is_last
        )

        windows.append(window)

        # Stop if this window reaches the end of the planning horizon
        if is_last:
            break

        # Update initial inventory for next window (will be set after solving)
        initial_inventory = {}

        # Move to next window start (advance by committed days, not full window)
        committed_days = window_size_days - overlap_days
        current_start = current_start + __import__('datetime').timedelta(days=committed_days)

    return windows
