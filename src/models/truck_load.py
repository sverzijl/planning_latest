"""Truck loading data models for optimization results.

This module provides TruckLoad and TruckLoadPlan classes used by optimization models
to represent truck assignments and loading plans.

Note: These are clean data models for optimization results, separate from the
heuristic truck loading logic in src/distribution/truck_loader.py.
"""

from datetime import date as Date, time
from typing import List, Optional
from dataclasses import dataclass, field

from src.models.shipment import Shipment


@dataclass
class TruckLoad:
    """Represents a loaded truck with assigned shipments.

    Used by optimization models to represent a single truck departure with
    its shipment assignments, capacity utilization, and departure details.

    This is a pure data container - no loading logic included.

    Attributes:
        truck_schedule_id: ID of the truck schedule
        truck_name: Display name of truck
        departure_date: Date of truck departure
        departure_type: Departure type ("morning" or "afternoon")
        departure_time: Time of departure (from TruckSchedule)
        destination_id: Truck's destination location ID
        shipments: List of assigned shipments
        total_units: Total units loaded on truck
        total_pallets: Pallets required (accounting for partial pallets)
        capacity_units: Maximum units capacity
        capacity_pallets: Maximum pallet capacity (default: 44)
        capacity_utilization: Percentage of pallet capacity used (0.0 to 1.0)
        utilization_pct: Alias for capacity_utilization (for visualization compatibility)
        is_full: Whether truck is at capacity
    """
    truck_schedule_id: str
    truck_name: str
    departure_date: Date
    departure_type: str
    departure_time: time
    destination_id: Optional[str]
    shipments: List[Shipment] = field(default_factory=list)
    total_units: float = 0.0
    total_pallets: int = 0
    capacity_units: float = 0.0
    capacity_pallets: int = 44
    capacity_utilization: float = 0.0
    utilization_pct: float = 0.0
    is_full: bool = False

    def __str__(self) -> str:
        """String representation with truck summary."""
        dest_info = f"to {self.destination_id}" if self.destination_id else "flexible route"
        return (
            f"{self.truck_name} on {self.departure_date} ({self.departure_type}) {dest_info}: "
            f"{len(self.shipments)} shipments, {self.total_units:.0f} units, "
            f"{self.total_pallets}/{self.capacity_pallets} pallets ({self.capacity_utilization:.1%})"
        )


@dataclass
class TruckLoadPlan:
    """Complete truck loading plan with all assignments.

    Used by optimization models to represent the complete truck loading solution,
    including all truck loads, unassigned shipments, and utilization metrics.

    This is a pure data container - no assignment logic included.

    Attributes:
        loads: List of truck loads (one per truck departure)
        unassigned_shipments: Shipments that couldn't be assigned to trucks
        infeasibilities: List of constraint violation messages (empty if feasible)
        total_trucks_used: Number of trucks used in the plan
        total_shipments: Total shipments (assigned + unassigned)
        average_utilization: Average capacity utilization across all trucks
    """
    loads: List[TruckLoad]
    unassigned_shipments: List[Shipment] = field(default_factory=list)
    infeasibilities: List[str] = field(default_factory=list)
    total_trucks_used: int = 0
    total_shipments: int = 0
    average_utilization: float = 0.0

    def is_feasible(self) -> bool:
        """Check if all shipments were successfully assigned.

        Returns:
            True if no unassigned shipments and no infeasibilities, False otherwise
        """
        return len(self.unassigned_shipments) == 0 and len(self.infeasibilities) == 0

    def __str__(self) -> str:
        """String representation with plan summary."""
        status = "FEASIBLE" if self.is_feasible() else f"INFEASIBLE ({len(self.unassigned_shipments)} unassigned)"
        return (
            f"TruckLoadPlan: {self.total_trucks_used} trucks, "
            f"{self.total_shipments} shipments, "
            f"avg utilization {self.average_utilization:.1%} - {status}"
        )
