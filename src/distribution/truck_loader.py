"""Truck loading logic for assigning shipments to truck departures.

This module assigns shipments to specific truck departures based on:
- Destination matching (truck serves shipment's first leg)
- Timing rules (D-1 vs D0 production)
- Capacity constraints (units and pallets)
- Day-specific routing (Monday-Friday schedules)
"""

from datetime import date, time, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import math

from src.models.shipment import Shipment
from src.models.truck_schedule import TruckSchedule, DayOfWeek


@dataclass
class TruckLoad:
    """
    Represents a loaded truck with assigned shipments.

    Attributes:
        truck_schedule_id: ID of the truck schedule
        truck_name: Name of truck for display
        departure_date: Date of truck departure
        departure_type: morning or afternoon
        departure_time: Time of departure (from TruckSchedule)
        destination_id: Truck's destination location
        shipments: List of assigned shipments
        total_units: Total units loaded
        total_pallets: Pallets required (accounting for partial pallets)
        capacity_units: Maximum units capacity
        capacity_pallets: Maximum pallet capacity
        capacity_utilization: Percentage of pallet capacity used (0.0 to 1.0)
        utilization_pct: Alias for capacity_utilization (for visualization compatibility)
        is_full: Whether truck is at capacity
    """
    truck_schedule_id: str
    truck_name: str
    departure_date: date
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
        """String representation."""
        dest_info = f"to {self.destination_id}" if self.destination_id else "flexible route"
        return (
            f"{self.truck_name} on {self.departure_date} ({self.departure_type}) {dest_info}: "
            f"{len(self.shipments)} shipments, {self.total_units:.0f} units, "
            f"{self.total_pallets}/{self.capacity_pallets} pallets ({self.capacity_utilization:.1%})"
        )


@dataclass
class TruckLoadPlan:
    """
    Complete truck loading plan with all assignments.

    Attributes:
        loads: List of truck loads (one per truck departure)
        unassigned_shipments: Shipments that couldn't be assigned
        infeasibilities: List of constraint violation messages
        total_trucks_used: Number of trucks used
        total_shipments: Total shipments (assigned + unassigned)
        average_utilization: Average capacity utilization across trucks
    """
    loads: List[TruckLoad]
    unassigned_shipments: List[Shipment] = field(default_factory=list)
    infeasibilities: List[str] = field(default_factory=list)
    total_trucks_used: int = 0
    total_shipments: int = 0
    average_utilization: float = 0.0

    def is_feasible(self) -> bool:
        """Check if all shipments were successfully assigned."""
        return len(self.unassigned_shipments) == 0 and len(self.infeasibilities) == 0

    def __str__(self) -> str:
        """String representation."""
        status = "FEASIBLE" if self.is_feasible() else f"INFEASIBLE ({len(self.unassigned_shipments)} unassigned)"
        return (
            f"TruckLoadPlan: {self.total_trucks_used} trucks, "
            f"{self.total_shipments} shipments, "
            f"avg utilization {self.average_utilization:.1%} - {status}"
        )


class TruckLoader:
    """
    Assigns shipments to truck departures.

    Handles the complex logic of matching shipments to appropriate trucks based on:
    - Destination compatibility (truck serves shipment's first leg)
    - Production timing (D-1 vs D0 relative to truck departure)
    - Capacity constraints (both units and pallets)
    - Day-specific routing (Monday-Friday afternoon truck destinations)

    Example:
        loader = TruckLoader(truck_schedules)
        plan = loader.assign_shipments_to_trucks(shipments, start_date, end_date)

        if plan.is_feasible():
            print(f"All {plan.total_shipments} shipments assigned!")
        else:
            print(f"{len(plan.unassigned_shipments)} shipments couldn't be assigned")
    """

    # Packaging constants
    UNITS_PER_CASE = 10
    CASES_PER_PALLET = 32
    UNITS_PER_PALLET = 320
    PALLETS_PER_TRUCK = 44

    def __init__(self, truck_schedules: List[TruckSchedule]):
        """
        Initialize truck loader.

        Args:
            truck_schedules: List of truck schedule definitions
        """
        self.truck_schedules = truck_schedules

    def assign_shipments_to_trucks(
        self,
        shipments: List[Shipment],
        start_date: date,
        end_date: date
    ) -> TruckLoadPlan:
        """
        Assign shipments to trucks across a date range.

        Args:
            shipments: List of shipments to assign
            start_date: First date to consider for truck departures
            end_date: Last date to consider for truck departures

        Returns:
            TruckLoadPlan with assignments and unassigned shipments
        """
        loads: List[TruckLoad] = []
        unassigned: List[Shipment] = []
        infeasibilities: List[str] = []

        # Create a copy of shipments list for tracking assignments
        remaining_shipments = list(shipments)

        # Process each date in range
        current_date = start_date
        while current_date <= end_date:
            # Get trucks departing on this date
            trucks = self.get_trucks_for_date(current_date)

            for truck in trucks:
                # Create truck load
                truck_load = self._create_empty_load(truck, current_date)

                # Try to assign shipments to this truck
                self._load_truck(truck_load, remaining_shipments, current_date)

                # Only add to loads if truck has shipments
                if len(truck_load.shipments) > 0:
                    loads.append(truck_load)

            current_date += timedelta(days=1)

        # Any remaining shipments are unassigned
        unassigned = remaining_shipments

        # Check for infeasibilities
        if unassigned:
            for shipment in unassigned:
                infeasibilities.append(
                    f"Shipment {shipment.id} ({shipment.quantity:.0f} units to {shipment.destination_id}) "
                    f"could not be assigned to any truck"
                )

        # Calculate statistics
        total_trucks = len(loads)
        total_shipments = len(shipments)
        avg_util = sum(load.capacity_utilization for load in loads) / total_trucks if total_trucks > 0 else 0.0

        return TruckLoadPlan(
            loads=loads,
            unassigned_shipments=unassigned,
            infeasibilities=infeasibilities,
            total_trucks_used=total_trucks,
            total_shipments=total_shipments,
            average_utilization=avg_util
        )

    def get_trucks_for_date(self, departure_date: date) -> List[TruckSchedule]:
        """
        Get all trucks that depart on a specific date.

        Args:
            departure_date: Date to check

        Returns:
            List of truck schedules that depart on this date
        """
        day_of_week = self._get_day_of_week(departure_date)
        matching_trucks = []

        for truck in self.truck_schedules:
            if truck.is_day_specific():
                # Day-specific truck: only runs on specific day
                if truck.day_of_week == day_of_week:
                    matching_trucks.append(truck)
            else:
                # Daily truck: runs every day (typically weekdays)
                # For now, assume daily trucks run Mon-Fri
                if day_of_week not in [DayOfWeek.SATURDAY, DayOfWeek.SUNDAY]:
                    matching_trucks.append(truck)

        return matching_trucks

    def _create_empty_load(self, truck: TruckSchedule, departure_date: date) -> TruckLoad:
        """Create an empty truck load."""
        return TruckLoad(
            truck_schedule_id=truck.id,
            truck_name=truck.truck_name,
            departure_date=departure_date,
            departure_type=truck.departure_type,  # Already a string due to use_enum_values=True
            departure_time=truck.departure_time,
            destination_id=truck.destination_id,
            shipments=[],
            total_units=0.0,
            total_pallets=0,
            capacity_units=truck.capacity,
            capacity_pallets=truck.pallet_capacity,
            capacity_utilization=0.0,
            utilization_pct=0.0,
            is_full=False
        )

    def _load_truck(
        self,
        truck_load: TruckLoad,
        remaining_shipments: List[Shipment],
        departure_date: date
    ) -> None:
        """
        Load shipments onto a truck.

        Modifies truck_load and remaining_shipments in place.

        Args:
            truck_load: Truck load to populate
            remaining_shipments: List of shipments not yet assigned (will be modified)
            departure_date: Date of truck departure
        """
        # Filter shipments that could go on this truck
        # Criteria: destination match + timing (D-1 or D0 if allowed)
        candidates = [
            s for s in remaining_shipments
            if self._can_assign_to_truck(s, truck_load, departure_date)
        ]

        # Sort candidates: D-1 first (priority), then by quantity (largest first)
        candidates.sort(
            key=lambda s: (
                not s.is_d1_production(departure_date),  # False (D-1) sorts before True (D0)
                -s.quantity  # Descending order by quantity
            )
        )

        # Try to load each candidate
        for shipment in candidates:
            if self._try_add_shipment(truck_load, shipment):
                # Successfully added - remove from remaining
                remaining_shipments.remove(shipment)
                shipment.assigned_truck_id = truck_load.truck_schedule_id

                # Check if truck is now full
                if truck_load.total_pallets >= truck_load.capacity_pallets:
                    truck_load.is_full = True
                    break

    def _can_assign_to_truck(
        self,
        shipment: Shipment,
        truck_load: TruckLoad,
        departure_date: date
    ) -> bool:
        """
        Check if shipment can be assigned to this truck.

        Args:
            shipment: Shipment to check
            truck_load: Truck load to check against
            departure_date: Date of truck departure

        Returns:
            True if shipment is compatible with this truck
        """
        # Check 1: Destination match
        # Truck must serve the shipment's first leg destination
        if truck_load.destination_id is None:
            # Flexible routing - need more logic here (Phase 3)
            return False

        if shipment.first_leg_destination != truck_load.destination_id:
            return False

        # Check 2: Timing (D-1 vs D0)
        is_d1 = shipment.is_d1_production(departure_date)
        is_d0 = shipment.is_d0_production(departure_date)

        if not (is_d1 or is_d0):
            # Shipment not ready for this truck departure
            return False

        # Morning trucks: D-1 only
        if truck_load.departure_type == "morning" and not is_d1:
            return False

        # Afternoon trucks: D-1 or D0
        # (D0 feasibility would need production time check - assume feasible for now)

        return True

    def _try_add_shipment(
        self,
        truck_load: TruckLoad,
        shipment: Shipment
    ) -> bool:
        """
        Try to add shipment to truck load.

        Args:
            truck_load: Truck load to add to (modified in place)
            shipment: Shipment to add

        Returns:
            True if shipment was added, False if capacity exceeded
        """
        # Calculate pallets needed for this shipment
        pallets_needed = math.ceil(shipment.quantity / self.UNITS_PER_PALLET)

        # Check capacity
        if truck_load.total_pallets + pallets_needed > truck_load.capacity_pallets:
            return False

        if truck_load.total_units + shipment.quantity > truck_load.capacity_units:
            return False

        # Add shipment
        truck_load.shipments.append(shipment)
        truck_load.total_units += shipment.quantity
        truck_load.total_pallets += pallets_needed
        truck_load.capacity_utilization = truck_load.total_pallets / truck_load.capacity_pallets
        truck_load.utilization_pct = truck_load.capacity_utilization  # Keep in sync

        return True

    def _get_day_of_week(self, date: date) -> DayOfWeek:
        """
        Convert date to DayOfWeek enum.

        Args:
            date: Date to convert

        Returns:
            DayOfWeek enum value
        """
        day_name = date.strftime("%A").lower()
        return DayOfWeek(day_name)
