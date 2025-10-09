"""Daily inventory snapshot generator for production planning results.

This module generates daily snapshots of inventory across the supply chain network,
tracking batches, quantities, in-transit shipments, flows, and demand satisfaction.

SNAPSHOT SEMANTICS:
- Inventory shown is the "available inventory" BEFORE demand consumption on that date
- This represents what inventory is available to satisfy demand
- In real-world scenarios, pre-positioned inventory from earlier deliveries can
  satisfy demand without requiring same-day delivery
- Demand satisfaction shows what is available to meet forecasted demand
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date, timedelta
from typing import Dict, List, Optional, Set
from collections import defaultdict

from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.models.location import Location
from src.models.forecast import Forecast
from src.production.scheduler import ProductionSchedule


@dataclass
class BatchInventory:
    """
    Represents a production batch at a specific location.

    Attributes:
        batch_id: Unique batch identifier
        product_id: Product identifier
        quantity: Quantity in units
        production_date: Date when batch was produced
        age_days: Age of batch in days (calculated from snapshot date)
    """
    batch_id: str
    product_id: str
    quantity: float
    production_date: Date
    age_days: int

    def __str__(self) -> str:
        """String representation."""
        return f"Batch {self.batch_id}: {self.quantity:.0f} units ({self.age_days}d old)"


@dataclass
class LocationInventory:
    """
    Aggregated inventory at a specific location.

    Attributes:
        location_id: Location identifier
        location_name: Human-readable location name
        batches: List of batches at this location
        total_quantity: Total quantity across all batches
        by_product: Quantity breakdown by product ID
    """
    location_id: str
    location_name: str
    batches: List[BatchInventory] = field(default_factory=list)
    total_quantity: float = 0.0
    by_product: Dict[str, float] = field(default_factory=dict)

    def add_batch(self, batch: BatchInventory) -> None:
        """
        Add a batch to this location's inventory.

        Args:
            batch: BatchInventory to add
        """
        self.batches.append(batch)
        self.total_quantity += batch.quantity

        if batch.product_id not in self.by_product:
            self.by_product[batch.product_id] = 0.0
        self.by_product[batch.product_id] += batch.quantity

    def __str__(self) -> str:
        """String representation."""
        products = ", ".join(f"{pid}: {qty:.0f}" for pid, qty in self.by_product.items())
        return f"{self.location_name} ({self.location_id}): {self.total_quantity:.0f} units [{products}]"


@dataclass
class TransitInventory:
    """
    Represents inventory in transit between locations.

    Attributes:
        shipment_id: Unique shipment identifier
        origin_id: Origin location ID
        destination_id: Destination location ID
        product_id: Product identifier
        quantity: Quantity in units
        departure_date: Date when shipment departed origin
        expected_arrival_date: Date when shipment will arrive at destination
        days_in_transit: Number of days shipment has been in transit
    """
    shipment_id: str
    origin_id: str
    destination_id: str
    product_id: str
    quantity: float
    departure_date: Date
    expected_arrival_date: Date
    days_in_transit: int

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Shipment {self.shipment_id}: {self.quantity:.0f} units from "
            f"{self.origin_id} -> {self.destination_id} (day {self.days_in_transit})"
        )


@dataclass
class InventoryFlow:
    """
    Represents an inventory flow (in or out) at a location.

    Attributes:
        flow_type: Type of flow ('production', 'arrival', 'departure', 'demand')
        location_id: Location where flow occurs
        product_id: Product identifier
        quantity: Quantity in units (positive for inflows, negative for outflows)
        counterparty: Other location involved (for arrivals/departures)
        batch_id: Associated batch ID (if applicable)
    """
    flow_type: str  # "production", "arrival", "departure", "demand"
    location_id: str
    product_id: str
    quantity: float
    counterparty: Optional[str] = None
    batch_id: Optional[str] = None

    def __str__(self) -> str:
        """String representation."""
        counterparty_str = f" ({self.counterparty})" if self.counterparty else ""
        batch_str = f" [batch: {self.batch_id}]" if self.batch_id else ""
        return (
            f"{self.flow_type.upper()}: {self.quantity:.0f} units of {self.product_id} "
            f"at {self.location_id}{counterparty_str}{batch_str}"
        )


@dataclass
class DemandRecord:
    """
    Represents demand satisfaction at a destination.

    NOTE: supplied_quantity represents the inventory AVAILABLE to satisfy demand,
    not necessarily the inventory consumed. This is the "before demand" view.

    Attributes:
        destination_id: Destination location ID
        product_id: Product identifier
        demand_quantity: Forecasted demand quantity
        supplied_quantity: Actual quantity supplied (available inventory)
        shortage_quantity: Shortage (demand - supplied, if positive)
    """
    destination_id: str
    product_id: str
    demand_quantity: float
    supplied_quantity: float
    shortage_quantity: float

    @property
    def fill_rate(self) -> float:
        """
        Calculate fill rate (supplied / demand).

        Returns:
            Fill rate as fraction (0.0 to 1.0), or 1.0 if no demand
        """
        if self.demand_quantity == 0:
            return 1.0
        return min(1.0, self.supplied_quantity / self.demand_quantity)

    @property
    def is_satisfied(self) -> bool:
        """
        Check if demand is fully satisfied.

        Returns:
            True if shortage is zero or negligible
        """
        return self.shortage_quantity < 0.01  # Allow small rounding errors

    def __str__(self) -> str:
        """String representation."""
        fill_pct = self.fill_rate * 100
        status = "SATISFIED" if self.is_satisfied else f"SHORT by {self.shortage_quantity:.0f}"
        return (
            f"{self.destination_id} - {self.product_id}: "
            f"{self.supplied_quantity:.0f}/{self.demand_quantity:.0f} ({fill_pct:.1f}%) - {status}"
        )


@dataclass
class DailySnapshot:
    """
    Complete inventory snapshot for a single date.

    NOTE: This snapshot represents the state BEFORE demand consumption on the date.
    - location_inventory: Available inventory that can satisfy demand
    - demand_satisfied: Compares available inventory to forecasted demand

    Attributes:
        date: Snapshot date
        location_inventory: Inventory at each location (keyed by location_id)
        in_transit: List of shipments in transit
        production_activity: Batches produced on this date
        inflows: All inflows (production + arrivals)
        outflows: All outflows (departures + demand)
        demand_satisfied: Demand satisfaction records
        total_system_inventory: Total inventory across all locations
        total_in_transit: Total inventory in transit
    """
    date: Date
    location_inventory: Dict[str, LocationInventory] = field(default_factory=dict)
    in_transit: List[TransitInventory] = field(default_factory=list)
    production_activity: List[BatchInventory] = field(default_factory=list)
    inflows: List[InventoryFlow] = field(default_factory=list)
    outflows: List[InventoryFlow] = field(default_factory=list)
    demand_satisfied: List[DemandRecord] = field(default_factory=list)
    total_system_inventory: float = 0.0
    total_in_transit: float = 0.0

    def __str__(self) -> str:
        """String representation."""
        num_locations = len(self.location_inventory)
        num_transit = len(self.in_transit)
        num_produced = len(self.production_activity)
        return (
            f"Snapshot for {self.date}: {num_locations} locations, "
            f"{num_transit} in-transit, {num_produced} batches produced, "
            f"total inventory: {self.total_system_inventory:.0f} units"
        )


class DailySnapshotGenerator:
    """
    Generates daily inventory snapshots from production planning results.

    This class tracks inventory movement through the supply chain network,
    including production, shipments, arrivals, and demand satisfaction.

    IMPORTANT: Snapshots show inventory state BEFORE demand consumption.
    This means:
    - Inventory reflects what is available to satisfy demand on that date
    - Pre-positioned inventory from earlier deliveries is included
    - Demand satisfaction compares available inventory to forecasted demand
    """

    def __init__(
        self,
        production_schedule: ProductionSchedule,
        shipments: List[Shipment],
        locations_dict: Dict[str, Location],
        forecast: Forecast,
        verbose: bool = False
    ):
        """
        Initialize snapshot generator.

        Args:
            production_schedule: Production schedule with batches
            shipments: List of shipments
            locations_dict: Dictionary mapping location_id to Location object
            forecast: Forecast with demand data
            verbose: Enable debug logging (default: False)
        """
        self.production_schedule = production_schedule
        self.shipments = shipments
        self.locations_dict = locations_dict
        self.forecast = forecast
        self.verbose = verbose

        # Build efficient lookup structures
        self._build_lookup_structures()

    def _build_lookup_structures(self) -> None:
        """
        Build efficient lookup structures for fast querying.

        Creates indexes for:
        - Batches by production date
        - Shipments by departure date
        - Shipments by arrival date
        - Shipments by delivery date (for demand)
        - Current location of each batch over time
        """
        # Index batches by production date
        self._batches_by_date: Dict[Date, List[ProductionBatch]] = defaultdict(list)
        for batch in self.production_schedule.production_batches:
            self._batches_by_date[batch.production_date].append(batch)

        # Index shipments by departure date
        self._shipments_by_departure: Dict[Date, List[Shipment]] = defaultdict(list)
        for shipment in self.shipments:
            # Calculate departure date from delivery date and transit time
            departure_date = shipment.delivery_date - timedelta(days=shipment.total_transit_days)
            self._shipments_by_departure[departure_date].append(shipment)

        # Index shipments by arrival date (first leg)
        self._shipments_by_arrival: Dict[Date, Dict[str, List[Shipment]]] = defaultdict(lambda: defaultdict(list))
        for shipment in self.shipments:
            # For multi-leg routes, we need to track arrivals at each intermediate location
            current_date = shipment.delivery_date - timedelta(days=shipment.total_transit_days)

            for leg in shipment.route.route_legs:
                arrival_date = current_date + timedelta(days=leg.transit_days)
                self._shipments_by_arrival[arrival_date][leg.to_location_id].append(shipment)
                current_date = arrival_date

        # Index shipments by delivery date
        self._shipments_by_delivery: Dict[Date, Dict[str, Dict[str, List[Shipment]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for shipment in self.shipments:
            self._shipments_by_delivery[shipment.delivery_date][shipment.destination_id][shipment.product_id].append(
                shipment
            )

    def generate_snapshots(self, start_date: Date, end_date: Date) -> List[DailySnapshot]:
        """
        Generate daily snapshots for a date range.

        Args:
            start_date: First date to snapshot
            end_date: Last date to snapshot (inclusive)

        Returns:
            List of DailySnapshot objects, one per day
        """
        snapshots = []
        current_date = start_date

        while current_date <= end_date:
            snapshot = self._generate_single_snapshot(current_date)
            snapshots.append(snapshot)
            current_date += timedelta(days=1)

        return snapshots

    def _generate_single_snapshot(self, snapshot_date: Date) -> DailySnapshot:
        """
        Generate snapshot for a single date.

        Args:
            snapshot_date: Date to snapshot

        Returns:
            DailySnapshot for the specified date
        """
        snapshot = DailySnapshot(date=snapshot_date)

        # FIX #1: Calculate inventory at ALL locations (even with zero inventory)
        # This ensures complete visibility of the network state
        location_inventory = {}
        for location_id in self.locations_dict.keys():
            loc_inv = self._calculate_location_inventory(location_id, snapshot_date)
            # ALWAYS add the location (removed filter that excluded zero-inventory locations)
            location_inventory[location_id] = loc_inv
            snapshot.total_system_inventory += loc_inv.total_quantity

        snapshot.location_inventory = location_inventory

        # Find in-transit shipments
        snapshot.in_transit = self._find_in_transit_shipments(snapshot_date)
        snapshot.total_in_transit = sum(t.quantity for t in snapshot.in_transit)

        # Get production activity
        snapshot.production_activity = self._get_production_activity(snapshot_date)

        # Calculate flows
        snapshot.inflows = self._calculate_inflows(snapshot_date)
        snapshot.outflows = self._calculate_outflows(snapshot_date)

        # Get demand satisfaction (pass location inventory for accurate calculation)
        snapshot.demand_satisfied = self._get_demand_satisfied(snapshot_date, location_inventory)

        return snapshot

    def _calculate_location_inventory(
        self,
        location_id: str,
        snapshot_date: Date,
        verbose: bool = False
    ) -> LocationInventory:
        """
        Calculate inventory at a location on a specific date.

        This tracks batches through the network:
        - Batches are at their origin location (manufacturing_site_id) on production date
        - Batches move with shipments through the network
        - A batch leaves origin when shipment departs
        - A batch arrives at destination after transit time

        NOTE: This calculates inventory BEFORE demand consumption on the snapshot date.
        Available inventory includes pre-positioned stock from earlier deliveries.

        Args:
            location_id: Location to calculate inventory for
            snapshot_date: Date to calculate inventory on
            verbose: Enable debug logging for this calculation (default: False)

        Returns:
            LocationInventory for the location
        """
        # FIX #3: Use instance verbose flag if not explicitly overridden
        debug = verbose or self.verbose

        if debug:
            print(f"\n[DEBUG] Calculating inventory for {location_id} on {snapshot_date}")

        location = self.locations_dict.get(location_id)
        location_name = location.name if location else location_id

        loc_inv = LocationInventory(
            location_id=location_id,
            location_name=location_name
        )

        # Track which batches are at this location
        # We need to trace each batch through shipments
        batch_quantities: Dict[str, float] = {}  # batch_id -> remaining quantity at this location

        # Start with batches at their ACTUAL location (from manufacturing_site_id field)
        # This handles both regular production (always at manufacturing) and initial inventory (can be anywhere)
        for batch in self.production_schedule.production_batches:
            if batch.manufacturing_site_id == location_id and batch.production_date <= snapshot_date:
                batch_quantities[batch.id] = batch.quantity
                if debug:
                    print(f"  [DEBUG] Added batch {batch.id}: {batch.quantity} units (produced {batch.production_date})")

        if debug:
            print(f"  [DEBUG] Initial batches: {len(batch_quantities)}, total: {sum(batch_quantities.values()):.0f}")

        # Process shipments to track batch movements
        shipments_processed = 0
        for shipment in self.shipments:
            # Calculate key dates for this shipment
            departure_date = shipment.delivery_date - timedelta(days=shipment.total_transit_days)

            # Track shipment through each leg
            current_date = departure_date
            current_location = shipment.origin_id

            for leg in shipment.route.route_legs:
                next_location = leg.to_location_id
                arrival_date = current_date + timedelta(days=leg.transit_days)

                # If shipment departed from this location, remove from inventory
                if current_location == location_id and current_date <= snapshot_date:
                    if shipment.batch_id in batch_quantities:
                        batch_quantities[shipment.batch_id] -= shipment.quantity
                        if debug:
                            print(f"  [DEBUG] Departure: batch {shipment.batch_id} -= {shipment.quantity} (departed {current_date})")
                        if batch_quantities[shipment.batch_id] <= 0.01:  # Account for rounding
                            del batch_quantities[shipment.batch_id]
                        shipments_processed += 1

                # If shipment arrived at this location, add to inventory
                if next_location == location_id and arrival_date <= snapshot_date:
                    # Only add if not yet departed (check next leg)
                    if arrival_date <= snapshot_date:
                        if shipment.batch_id not in batch_quantities:
                            batch_quantities[shipment.batch_id] = 0.0
                        batch_quantities[shipment.batch_id] += shipment.quantity
                        if debug:
                            print(f"  [DEBUG] Arrival: batch {shipment.batch_id} += {shipment.quantity} (arrived {arrival_date})")
                        shipments_processed += 1

                # Move to next leg
                current_date = arrival_date
                current_location = next_location

        if debug:
            print(f"  [DEBUG] Processed {shipments_processed} shipment movements")
            print(f"  [DEBUG] Final batches: {len(batch_quantities)}, total: {sum(batch_quantities.values()):.0f}")

        # Build BatchInventory objects for remaining quantities
        for batch_id, quantity in batch_quantities.items():
            if quantity > 0.01:  # Only include non-zero quantities
                # Find the original batch
                batch = next((b for b in self.production_schedule.production_batches if b.id == batch_id), None)
                if batch:
                    age_days = (snapshot_date - batch.production_date).days
                    batch_inv = BatchInventory(
                        batch_id=batch_id,
                        product_id=batch.product_id,
                        quantity=quantity,
                        production_date=batch.production_date,
                        age_days=age_days
                    )
                    loc_inv.add_batch(batch_inv)

        if debug:
            print(f"  [DEBUG] RESULT: {loc_inv.total_quantity:.0f} units at {location_id}")

        return loc_inv

    def _find_in_transit_shipments(self, snapshot_date: Date) -> List[TransitInventory]:
        """
        Find all shipments in transit on the snapshot date.

        A shipment is in transit if:
        - departure_date <= snapshot_date < arrival_date

        Args:
            snapshot_date: Date to check

        Returns:
            List of TransitInventory objects
        """
        in_transit = []

        for shipment in self.shipments:
            # Calculate departure and arrival dates for each leg
            current_date = shipment.delivery_date - timedelta(days=shipment.total_transit_days)

            for leg in shipment.route.route_legs:
                departure_date = current_date
                arrival_date = current_date + timedelta(days=leg.transit_days)

                # Check if in transit on this leg
                if departure_date <= snapshot_date < arrival_date:
                    days_in_transit = (snapshot_date - departure_date).days
                    transit_inv = TransitInventory(
                        shipment_id=shipment.id,
                        origin_id=leg.from_location_id,
                        destination_id=leg.to_location_id,
                        product_id=shipment.product_id,
                        quantity=shipment.quantity,
                        departure_date=departure_date,
                        expected_arrival_date=arrival_date,
                        days_in_transit=days_in_transit
                    )
                    in_transit.append(transit_inv)
                    break  # Shipment can only be in transit on one leg at a time

                current_date = arrival_date

        return in_transit

    def _get_production_activity(self, snapshot_date: Date) -> List[BatchInventory]:
        """
        Get batches produced on the snapshot date.

        Args:
            snapshot_date: Date to check

        Returns:
            List of BatchInventory for batches produced on this date
        """
        production_activity = []

        batches = self._batches_by_date.get(snapshot_date, [])
        for batch in batches:
            batch_inv = BatchInventory(
                batch_id=batch.id,
                product_id=batch.product_id,
                quantity=batch.quantity,
                production_date=batch.production_date,
                age_days=0  # Just produced
            )
            production_activity.append(batch_inv)

        return production_activity

    def _calculate_inflows(self, snapshot_date: Date) -> List[InventoryFlow]:
        """
        Calculate all inflows on the snapshot date.

        Inflows include:
        - Production (batches produced at manufacturing site)
        - Arrivals (shipments arriving at locations)

        Args:
            snapshot_date: Date to calculate inflows for

        Returns:
            List of InventoryFlow objects for inflows
        """
        inflows = []

        # Production inflows
        batches = self._batches_by_date.get(snapshot_date, [])
        for batch in batches:
            flow = InventoryFlow(
                flow_type="production",
                location_id=batch.manufacturing_site_id,
                product_id=batch.product_id,
                quantity=batch.quantity,
                counterparty=None,
                batch_id=batch.id
            )
            inflows.append(flow)

        # Arrival inflows (shipments arriving at locations)
        arrivals_by_location = self._shipments_by_arrival.get(snapshot_date, {})
        for location_id, shipments in arrivals_by_location.items():
            for shipment in shipments:
                flow = InventoryFlow(
                    flow_type="arrival",
                    location_id=location_id,
                    product_id=shipment.product_id,
                    quantity=shipment.quantity,
                    counterparty=shipment.origin_id,
                    batch_id=shipment.batch_id
                )
                inflows.append(flow)

        return inflows

    def _calculate_outflows(self, snapshot_date: Date) -> List[InventoryFlow]:
        """
        Calculate all outflows on the snapshot date.

        Outflows include:
        - Departures (shipments leaving locations)
        - Demand (deliveries to destinations)

        Args:
            snapshot_date: Date to calculate outflows for

        Returns:
            List of InventoryFlow objects for outflows
        """
        outflows = []

        # Departure outflows
        shipments = self._shipments_by_departure.get(snapshot_date, [])
        for shipment in shipments:
            flow = InventoryFlow(
                flow_type="departure",
                location_id=shipment.origin_id,
                product_id=shipment.product_id,
                quantity=shipment.quantity,
                counterparty=shipment.first_leg_destination,
                batch_id=shipment.batch_id
            )
            outflows.append(flow)

        # Demand outflows (deliveries)
        deliveries_by_dest = self._shipments_by_delivery.get(snapshot_date, {})
        for dest_id, products in deliveries_by_dest.items():
            for product_id, shipments in products.items():
                total_delivered = sum(s.quantity for s in shipments)
                flow = InventoryFlow(
                    flow_type="demand",
                    location_id=dest_id,
                    product_id=product_id,
                    quantity=total_delivered,
                    counterparty=None,
                    batch_id=None
                )
                outflows.append(flow)

        return outflows

    def _get_demand_satisfied(
        self,
        snapshot_date: Date,
        location_inventory: Dict[str, LocationInventory]
    ) -> List[DemandRecord]:
        """
        Get demand satisfaction records for the snapshot date.

        FIX #2: CLARIFIED SEMANTICS
        This method calculates what inventory is AVAILABLE to satisfy demand on the
        snapshot date. This is the "before demand consumption" view.

        Available inventory includes:
        - On-hand inventory at the location (from earlier deliveries)
        - New deliveries arriving on the snapshot date

        In practice, the location_inventory already includes deliveries that have
        arrived by the snapshot date (including same-day arrivals), so we use
        that directly as the "available" quantity.

        This reflects the real-world scenario where pre-positioned inventory
        can satisfy demand without requiring same-day delivery.

        FUTURE ENHANCEMENT:
        Could add an "ending_inventory" field showing inventory AFTER demand
        consumption for clearer user understanding.

        Args:
            snapshot_date: Date to check demand satisfaction
            location_inventory: Inventory at each location on this date (before demand)

        Returns:
            List of DemandRecord objects
        """
        demand_records = []

        # Get all demand for this date from forecast
        demand_by_location_product: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for entry in self.forecast.entries:
            if entry.forecast_date == snapshot_date:
                demand_by_location_product[entry.location_id][entry.product_id] = entry.quantity

        # Get available inventory at each location (before demand consumption)
        # This includes both on-hand inventory from earlier deliveries AND
        # new arrivals on the snapshot date
        inventory_by_location_product: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for location_id, loc_inv in location_inventory.items():
            for product_id, quantity in loc_inv.by_product.items():
                inventory_by_location_product[location_id][product_id] = quantity

        # Combine to create demand records
        # ONLY create records for locations that actually have demand
        all_locations_with_demand = set(demand_by_location_product.keys())

        for location_id in all_locations_with_demand:
            # For this location with demand, check all products that have demand
            all_products_with_demand = set(demand_by_location_product[location_id].keys())

            for product_id in all_products_with_demand:
                demand_qty = demand_by_location_product[location_id][product_id]

                # Available inventory = what's on hand (including today's arrivals)
                # The location_inventory already accounts for arrivals up to snapshot_date
                available_qty = inventory_by_location_product[location_id].get(product_id, 0.0)

                # Calculate shortage
                shortage_qty = max(0.0, demand_qty - available_qty)

                record = DemandRecord(
                    destination_id=location_id,
                    product_id=product_id,
                    demand_quantity=demand_qty,
                    supplied_quantity=available_qty,  # Available inventory (before demand)
                    shortage_quantity=shortage_qty
                )
                demand_records.append(record)

        return demand_records
