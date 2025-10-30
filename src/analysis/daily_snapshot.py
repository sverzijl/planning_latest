"""Daily inventory snapshot generator for production planning results.

This module generates daily snapshots of inventory across the supply chain network,
tracking batches, quantities, in-transit shipments, flows, and demand satisfaction.

REFACTORED: Now expects Pydantic-validated OptimizationSolution.
Mode detection uses solution.get_inventory_format() instead of dict checks.

TWO MODES:
1. MODEL MODE (Preferred): Extract inventory directly from optimization model solution
   - Requires: model_solution parameter (OptimizationSolution with inventory data)
   - Benefits: Single source of truth, no duplicate logic, guaranteed consistency
   - Performance: Fast (just data extraction)

2. LEGACY MODE (Deprecated): Reconstruct inventory from shipments
   - Used when: model_solution not provided
   - Status: Deprecated - will be removed in future version
   - Drawbacks: Duplicate logic, potential divergence

SNAPSHOT SEMANTICS:
- Inventory shown is the "ending inventory" AFTER all activities on that date
- Activities include: production, shipment departures, shipment arrivals, and demand consumption
- Demand is consumed from inventory using FIFO (first-in-first-out) strategy
- This represents the actual inventory available at the end of the day

USAGE:
    # Preferred (with Pydantic solution):
    generator = DailySnapshotGenerator(
        production_schedule, shipments, locations, forecast,
        model_solution=solution  # OptimizationSolution (Pydantic validated)
    )

    # Deprecated (without model solution):
    generator = DailySnapshotGenerator(
        production_schedule, shipments, locations, forecast
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date, timedelta
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from collections import defaultdict

from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.models.location import Location
from src.models.forecast import Forecast
from src.models.production_schedule import ProductionSchedule

if TYPE_CHECKING:
    from src.optimization.result_schema import OptimizationSolution


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
        state: Storage state ('frozen', 'ambient', or 'thawed')
    """
    batch_id: str
    product_id: str
    quantity: float
    production_date: Date
    age_days: int
    state: str = 'ambient'  # Default to ambient for backward compatibility

    def __str__(self) -> str:
        """String representation."""
        state_emoji = '❄️' if self.state == 'frozen' else '🌡️' if self.state == 'thawed' else '🌤️'
        return f"Batch {self.batch_id}: {self.quantity:.0f} units ({self.age_days}d old, {state_emoji} {self.state})"


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

    Attributes:
        destination_id: Destination location ID
        product_id: Product identifier
        demand_quantity: Forecasted demand quantity
        supplied_quantity: Actual quantity supplied (consumed from inventory)
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

    This snapshot represents the state AFTER all activities on the date,
    including production, arrivals, departures, and demand consumption.

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

    This class supports TWO MODES:
    
    1. MODEL MODE (Preferred): Extract inventory directly from model solution
       - Uses cohort_inventory from IntegratedProductionDistributionModel
       - Single source of truth - no duplicate logic
       - Guaranteed consistency with optimization results
    
    2. LEGACY MODE: Reconstruct inventory from shipments
       - Used when model_solution not provided
       - Backward compatible with existing code

    Snapshots show inventory state AFTER all activities on each date, including:
    - Production at manufacturing sites
    - Shipment departures and arrivals
    - Demand consumption (using FIFO strategy)
    """

    def __init__(
        self,
        production_schedule: ProductionSchedule,
        shipments: List[Shipment],
        locations_dict: Dict[str, Location],
        forecast: Forecast,
        model_solution: Optional['OptimizationSolution'] = None,
        verbose: bool = False
    ):
        """
        Initialize snapshot generator.

        REFACTORED: Now expects Pydantic-validated OptimizationSolution.

        Args:
            production_schedule: Production schedule with batches
            shipments: List of shipments
            locations_dict: Dictionary mapping location_id to Location object
            forecast: Forecast with demand data
            model_solution: Optional OptimizationSolution (Pydantic validated).
                           If provided, uses inventory data directly (preferred).
                           If None, falls back to legacy reconstruction (deprecated).
            verbose: Enable debug logging (default: False)
        """
        self.production_schedule = production_schedule
        self.shipments = shipments
        self.locations_dict = locations_dict
        self.forecast = forecast
        self.model_solution = model_solution

        # Detect inventory format using Pydantic helper method
        # SIMPLIFIED: No more .get() checks, use solution.get_inventory_format()
        self.use_model_inventory = False
        self.is_aggregate_model = False
        if model_solution is not None:
            inventory_format = model_solution.get_inventory_format()
            if inventory_format == "state":
                # SlidingWindowModel: has aggregate inventory
                self.use_model_inventory = True
                self.is_aggregate_model = True
            elif inventory_format == "cohort":
                # UnifiedNodeModel: has cohort_inventory
                self.use_model_inventory = True
                self.is_aggregate_model = False
            # else: inventory_format == "none" → use_model_inventory = False

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
        - Demand by date, location, and product
        - Current location of each batch over time
        """
        # Index batches by production date
        # FILTER OUT initial inventory (INIT-*) - they're not production activity!
        self._batches_by_date: Dict[Date, List[ProductionBatch]] = defaultdict(list)
        for batch in self.production_schedule.production_batches:
            # Only index actual production batches, not initial inventory
            if not batch.id.startswith('INIT-'):
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

        # Index demand by date, location, and product
        self.demand_by_date_location_product: Dict[Date, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        for entry in self.forecast.entries:
            self.demand_by_date_location_product[entry.forecast_date][entry.location_id][entry.product_id] = entry.quantity

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

        # Calculate inventory at ALL locations (even with zero inventory)
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

    def _extract_inventory_from_model(
        self,
        location_id: str,
        snapshot_date: Date
    ) -> LocationInventory:
        """
        Extract inventory directly from model solution (MODEL MODE).
        
        This is the preferred path when model_solution is provided.
        It extracts cohort inventory directly from the optimization model,
        ensuring consistency with the model's decisions.
        
        Args:
            location_id: Location to extract inventory for
            snapshot_date: Date to extract inventory on
            
        Returns:
            LocationInventory for the location
        """
        location = self.locations_dict.get(location_id)
        location_name = location.name if location else location_id
        
        loc_inv = LocationInventory(
            location_id=location_id,
            location_name=location_name
        )

        if self.is_aggregate_model:
            # AGGREGATE MODEL (SlidingWindowModel): Use FEFO batches if available
            # Try batch objects first (in-memory), then batch dicts (from JSON)
            # SIMPLIFIED: Pydantic attributes instead of .get()
            fefo_batches = self.model_solution.fefo_batch_objects
            if not fefo_batches:
                fefo_batches = self.model_solution.fefo_batches or []

            if fefo_batches:
                # Use FEFO batches with location history for accurate tracking
                # Find batches that were AT THIS LOCATION ON THIS DATE
                for batch in fefo_batches:
                    # Handle both Batch objects and dicts
                    if isinstance(batch, dict):
                        batch_id = batch['id']
                        product_id = batch['product_id']
                        current_state = batch['current_state']
                        from datetime import datetime
                        production_date = datetime.fromisoformat(batch['production_date']).date()

                        # Get location and quantity on snapshot_date from history
                        location_history = batch.get('location_history', {})
                        quantity_history = batch.get('quantity_history', {})

                        # Find location on snapshot_date
                        snapshot_date_iso = snapshot_date.isoformat()
                        if snapshot_date_iso in location_history:
                            location_id_batch = location_history[snapshot_date_iso]
                            quantity = quantity_history.get(snapshot_date_iso, batch['quantity'])
                        else:
                            # Find most recent date before snapshot_date
                            valid_dates = [d for d in location_history.keys() if d <= snapshot_date_iso]
                            if valid_dates:
                                most_recent = max(valid_dates)
                                location_id_batch = location_history[most_recent]
                                quantity = quantity_history.get(most_recent, batch['quantity'])
                            else:
                                continue  # Batch doesn't exist yet on this date
                    else:
                        # Batch object
                        batch_id = batch.id
                        product_id = batch.product_id
                        current_state = batch.current_state
                        production_date = batch.production_date

                        # Use methods to get location/quantity on date
                        location_id_batch = batch.get_location_on_date(snapshot_date)
                        quantity = batch.get_quantity_on_date(snapshot_date)

                        if location_id_batch is None:
                            continue  # Batch doesn't exist on this date

                    # Filter: location matches AND batch exists on this date
                    if (location_id_batch == location_id and
                        quantity > 0.01 and
                        production_date <= snapshot_date):  # Don't show future production!

                        # Calculate age
                        age_days = (snapshot_date - production_date).days

                        batch_inv = BatchInventory(
                            batch_id=batch_id,
                            product_id=product_id,
                            quantity=quantity,  # Quantity on THIS date
                            production_date=production_date,
                            age_days=age_days,
                            state=current_state
                        )
                        loc_inv.add_batch(batch_inv)
            else:
                # Fallback: Use aggregate inventory (approximate ages)
                # SIMPLIFIED: Pydantic attribute
                aggregate_inventory = self.model_solution.inventory_state or {}

                # Filter for this location and date
                location_inventory = [
                    (node_id, product_id, state, qty)
                    for (node_id, product_id, state, inv_date), qty in aggregate_inventory.items()
                    if node_id == location_id and inv_date == snapshot_date and qty > 0.01
                ]

                # Create simplified BatchInventory objects
                for (node_id, product_id, state, qty) in location_inventory:
                    batch_inv = BatchInventory(
                        batch_id=f"AGG-{product_id}-{state}",
                        product_id=product_id,
                        quantity=qty,
                        production_date=snapshot_date,  # Unknown without FEFO
                        age_days=0,  # Unknown without FEFO
                        state=state
                    )
                    loc_inv.add_batch(batch_inv)

        else:
            # COHORT MODEL (UnifiedNodeModel): cohort_inventory with batch detail
            # SIMPLIFIED: Pydantic attributes
            cohort_inventory = self.model_solution.cohort_inventory or {}
            production_batches_data = [
                {'date': b.date, 'product': b.product, 'quantity': b.quantity, 'node': b.node}
                for b in self.model_solution.production_batches
            ]

            # Build batch lookup
            batch_lookup = {}
            for batch_data in production_batches_data:
                batch_date = batch_data['date']
                batch_product = batch_data['product']
                batch_qty = batch_data['quantity']
                batch_id = f"BATCH-{batch_date}-{batch_product}"
                batch_lookup[(batch_date, batch_product)] = {
                    'id': batch_id,
                    'quantity': batch_qty,
                    'date': batch_date,
                    'product': batch_product
                }

            # Filter cohorts for this location and date
            # cohort_inventory format: {(loc, prod, prod_date, curr_date, state): qty}
            location_cohorts = [
                (loc, prod, prod_date, curr_date, state, qty)
                for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                if loc == location_id and curr_date == snapshot_date and qty > 0.01
            ]

            # Group by batch (production_date + product + state = unique cohort)
            batches_at_location = {}
            for (loc, product_id, prod_date, curr_date, state, qty) in location_cohorts:
                batch_key = (prod_date, product_id, state)
                if batch_key not in batches_at_location:
                    batches_at_location[batch_key] = 0.0
                batches_at_location[batch_key] += qty

            # Create BatchInventory objects
            for (prod_date, product_id, state), total_qty in batches_at_location.items():
                age_days = (snapshot_date - prod_date).days
                batch_info = batch_lookup.get((prod_date, product_id))
                batch_id = batch_info['id'] if batch_info else f"BATCH-{prod_date}-{product_id}"

                # Append state indicator to batch_id for clarity
                batch_id_with_state = f"{batch_id}-{state}"

                batch_inv = BatchInventory(
                    batch_id=batch_id_with_state,
                    product_id=product_id,
                    quantity=total_qty,
                    production_date=prod_date,
                    age_days=age_days,
                    state=state
                )

                loc_inv.add_batch(batch_inv)
        
        return loc_inv

    def _reconstruct_inventory_legacy(
        self,
        location_id: str,
        snapshot_date: Date,
        verbose: bool = False
    ) -> LocationInventory:
        """
        Reconstruct inventory from shipments (LEGACY MODE).
        
        This is the existing ~240 line implementation that manually tracks
        inventory through the network. Used for backward compatibility when
        model_solution is not provided.
        
        Args:
            location_id: Location to calculate inventory for
            snapshot_date: Date to calculate inventory on
            verbose: Enable debug logging
            
        Returns:
            LocationInventory for the location
        """
        # Use instance verbose flag if not explicitly overridden
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
            print(f"  [DEBUG] Before demand consumption: {len(batch_quantities)} batches, total: {sum(batch_quantities.values()):.0f}")

        # Deduct demand consumed using FIFO strategy
        # Process all demand from schedule start through snapshot_date
        schedule_start = self.production_schedule.schedule_start_date
        demand_consumed = self._consume_demand_fifo(
            location_id=location_id,
            batch_quantities=batch_quantities,
            start_date=schedule_start,
            end_date=snapshot_date,
            debug=debug
        )

        if debug and demand_consumed > 0:
            print(f"  [DEBUG] After demand consumption: {len(batch_quantities)} batches, total: {sum(batch_quantities.values()):.0f}")
            print(f"  [DEBUG] Total demand consumed: {demand_consumed:.0f}")

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

    def _calculate_location_inventory(
        self,
        location_id: str,
        snapshot_date: Date,
        verbose: bool = False
    ) -> LocationInventory:
        """
        Calculate inventory at a location on a specific date.

        This method dispatches to MODEL MODE or LEGACY MODE based on
        whether model_solution is provided.

        MODEL MODE: Extract directly from cohort_inventory (preferred)
        LEGACY MODE: Reconstruct from shipments (backward compatible)

        Args:
            location_id: Location to calculate inventory for
            snapshot_date: Date to calculate inventory on
            verbose: Enable debug logging for this calculation (default: False)

        Returns:
            LocationInventory for the location
        """
        if self.use_model_inventory:
            return self._extract_inventory_from_model(location_id, snapshot_date)
        else:
            return self._reconstruct_inventory_legacy(location_id, snapshot_date, verbose)

    def _consume_demand_fifo(
        self,
        location_id: str,
        batch_quantities: Dict[str, float],
        start_date: Date,
        end_date: Date,
        debug: bool = False
    ) -> float:
        """
        Consume demand from inventory using FIFO (first-in-first-out) strategy.

        This modifies batch_quantities in-place, deducting demand consumed from
        the oldest batches first.

        Args:
            location_id: Location where demand is consumed
            batch_quantities: Dict mapping batch_id to current quantity (modified in-place)
            start_date: First date to process demand from
            end_date: Last date to process demand through (inclusive)
            debug: Enable debug logging

        Returns:
            Total quantity of demand consumed
        """
        total_consumed = 0.0
        current_date = start_date

        # Iterate through each date in the range
        while current_date <= end_date:
            # Get demand for this location on this date
            demand_by_product = self.demand_by_date_location_product.get(current_date, {}).get(location_id, {})

            for product_id, demand_qty in demand_by_product.items():
                if demand_qty <= 0:
                    continue

                if debug:
                    print(f"  [DEBUG] Consuming demand: {demand_qty:.0f} units of {product_id} on {current_date}")

                # Find all batches of this product at this location
                # Sort by production_date (oldest first) for FIFO
                product_batches = []
                for batch_id, quantity in batch_quantities.items():
                    if quantity > 0.01:  # Only consider non-empty batches
                        batch = self._get_batch_by_id(batch_id)
                        if batch and batch.product_id == product_id:
                            product_batches.append((batch_id, quantity, batch.production_date))

                # Sort by production date (oldest first)
                product_batches.sort(key=lambda x: x[2])

                # Consume demand from batches in FIFO order
                remaining_demand = demand_qty
                for batch_id, available_qty, production_date in product_batches:
                    if remaining_demand <= 0.01:
                        break

                    # Consume from this batch
                    consumed_from_batch = min(remaining_demand, available_qty)
                    batch_quantities[batch_id] -= consumed_from_batch
                    remaining_demand -= consumed_from_batch
                    total_consumed += consumed_from_batch

                    if debug:
                        print(f"    [DEBUG] Consumed {consumed_from_batch:.0f} from batch {batch_id} (produced {production_date})")

                    # Remove batch if fully consumed
                    if batch_quantities[batch_id] <= 0.01:
                        del batch_quantities[batch_id]
                        if debug:
                            print(f"    [DEBUG] Batch {batch_id} fully consumed, removed from inventory")

                # Check for shortage (demand exceeds available inventory)
                if remaining_demand > 0.01:
                    if debug:
                        print(f"    [DEBUG] WARNING: Shortage of {remaining_demand:.0f} units of {product_id}")

            current_date += timedelta(days=1)

        return total_consumed

    def _get_batch_by_id(self, batch_id: str) -> Optional[ProductionBatch]:
        """
        Retrieve a batch object by its ID.

        Args:
            batch_id: Batch identifier

        Returns:
            ProductionBatch object if found, None otherwise
        """
        for batch in self.production_schedule.production_batches:
            if batch.id == batch_id:
                return batch
        return None

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

        # For aggregate models with FEFO batches, use those
        if self.is_aggregate_model and self.model_solution:
            fefo_batches = self.model_solution.fefo_batch_objects
            if not fefo_batches:
                fefo_batches = self.model_solution.fefo_batches or []

            for batch in fefo_batches:
                # Handle both Batch objects and dicts
                if isinstance(batch, dict):
                    prod_date = batch.get('production_date')
                    if isinstance(prod_date, str):
                        from datetime import datetime
                        prod_date = datetime.fromisoformat(prod_date).date()

                    if prod_date == snapshot_date:
                        batch_inv = BatchInventory(
                            batch_id=batch['id'],
                            product_id=batch['product_id'],
                            quantity=batch['quantity'],
                            production_date=prod_date,
                            age_days=0,  # Just produced
                            state=batch.get('current_state', 'ambient')
                        )
                        production_activity.append(batch_inv)
                else:
                    # Batch object
                    if batch.production_date == snapshot_date:
                        batch_inv = BatchInventory(
                            batch_id=batch.id,
                            product_id=batch.product_id,
                            quantity=batch.initial_quantity,  # Original production quantity
                            production_date=batch.production_date,
                            age_days=0,
                            state=batch.current_state
                        )
                        production_activity.append(batch_inv)
        else:
            # Use production_schedule batches
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

        # Production inflows - use FEFO batches for aggregate models
        if self.is_aggregate_model and self.model_solution:
            fefo_batches = self.model_solution.fefo_batch_objects or []
            if not fefo_batches:
                fefo_batches = self.model_solution.fefo_batches or []

            for batch in fefo_batches:
                # Handle both objects and dicts
                if isinstance(batch, dict):
                    prod_date = batch.get('production_date')
                    if isinstance(prod_date, str):
                        from datetime import datetime
                        prod_date = datetime.fromisoformat(prod_date).date()
                    batch_id = batch['id']
                    product_id = batch['product_id']
                    quantity = batch.get('initial_quantity', batch.get('quantity', 0))
                    mfg_site = batch.get('manufacturing_site_id', 'UNKNOWN')
                else:
                    prod_date = batch.production_date
                    batch_id = batch.id
                    product_id = batch.product_id
                    quantity = batch.initial_quantity
                    mfg_site = batch.manufacturing_site_id

                if prod_date == snapshot_date and not batch_id.startswith('INIT'):
                    flow = InventoryFlow(
                        flow_type="production",
                        location_id=mfg_site,
                        product_id=product_id,
                        quantity=quantity,
                        counterparty=None,
                        batch_id=batch_id
                    )
                    inflows.append(flow)
        else:
            # Production inflows from production_schedule
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

        # Arrival inflows from FEFO shipment allocations for aggregate models
        if self.is_aggregate_model and self.model_solution:
            fefo_allocations = self.model_solution.fefo_shipment_allocations or []

            for alloc in fefo_allocations:
                delivery_date = alloc.get('delivery_date')
                if isinstance(delivery_date, str):
                    from datetime import datetime
                    delivery_date = datetime.fromisoformat(delivery_date).date()

                if delivery_date == snapshot_date:
                    flow = InventoryFlow(
                        flow_type="arrival",
                        location_id=alloc['destination'],
                        product_id=alloc.get('product_id', 'UNKNOWN'),
                        quantity=alloc['quantity'],
                        counterparty=alloc['origin'],
                        batch_id=alloc['batch_id']
                    )
                    inflows.append(flow)
        else:
            # Arrival inflows from shipments list
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

        # Departures from FEFO shipment allocations for aggregate models
        if self.is_aggregate_model and self.model_solution:
            fefo_allocations = self.model_solution.fefo_shipment_allocations or []

            # Need to calculate departure date for each allocation
            # shipment_allocation has delivery_date, need to subtract transit_time
            for alloc in fefo_allocations:
                delivery_date = alloc.get('delivery_date')
                if isinstance(delivery_date, str):
                    from datetime import datetime
                    delivery_date = datetime.fromisoformat(delivery_date).date()

                origin = alloc['origin']
                dest = alloc['destination']

                # Find route to get transit time (simplified - assume 1 day if not found)
                # In real implementation, would look up actual route
                transit_days = 1  # Default

                departure_date = delivery_date - timedelta(days=transit_days)

                if departure_date == snapshot_date:
                    flow = InventoryFlow(
                        flow_type="departure",
                        location_id=origin,
                        product_id=alloc.get('product_id', 'UNKNOWN'),
                        quantity=alloc['quantity'],
                        counterparty=dest,
                        batch_id=alloc['batch_id']
                    )
                    outflows.append(flow)
        else:
            # Departure outflows from shipments list
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

        # Demand consumption - use model solution for aggregate models
        if self.is_aggregate_model and self.model_solution:
            demand_consumed = getattr(self.model_solution, 'demand_consumed', {})

            # demand_consumed format from solution: {(node, product, date): qty}
            # But it's in metadata, need to check actual format
            # For now, use arrivals at demand nodes as proxy for demand
            fefo_allocations = self.model_solution.fefo_shipment_allocations or []

            for alloc in fefo_allocations:
                delivery_date = alloc.get('delivery_date')
                if isinstance(delivery_date, str):
                    from datetime import datetime
                    delivery_date = datetime.fromisoformat(delivery_date).date()

                dest = alloc['destination']

                # Check if destination is a demand node (not a hub)
                # Simplified: if not 6104, 6125, Lineage, assume it's demand
                if dest not in ['6104', '6125', 'Lineage'] and delivery_date == snapshot_date:
                    flow = InventoryFlow(
                        flow_type="demand",
                        location_id=dest,
                        product_id=alloc.get('product_id', 'UNKNOWN'),
                        quantity=alloc['quantity'],
                        counterparty=None,
                        batch_id=alloc['batch_id']
                    )
                    outflows.append(flow)
        else:
            # Demand outflows from shipments list
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

        MODEL MODE (preferred): Extract directly from model's cohort_demand_consumption
        and shortages_by_dest_product_date dictionaries.

        LEGACY MODE (fallback): Recalculate by tracking inventory before demand consumption.

        Args:
            snapshot_date: Date to check demand satisfaction
            location_inventory: Inventory at each location on this date (after demand consumption)

        Returns:
            List of DemandRecord objects
        """
        # Use MODEL MODE if available (batch tracking enabled)
        if self.use_model_inventory and self.model_solution:
            return self._get_demand_satisfied_from_model(snapshot_date)
        else:
            # Fallback to LEGACY MODE
            return self._get_demand_satisfied_legacy(snapshot_date, location_inventory)

    def _get_demand_satisfied_from_model(
        self,
        snapshot_date: Date
    ) -> List[DemandRecord]:
        """
        Extract demand satisfaction directly from model solution (MODEL MODE).

        This extracts the exact demand satisfaction tracked by the optimization model,
        including which batches satisfied demand and any shortages.

        Args:
            snapshot_date: Date to check demand satisfaction

        Returns:
            List of DemandRecord objects
        """
        demand_records = []

        # Get demand from forecast for this date
        forecast_demand: Dict[Tuple[str, str], float] = {}  # (loc, prod) → qty
        for entry in self.forecast.entries:
            if entry.forecast_date == snapshot_date:
                key = (entry.location_id, entry.product_id)
                forecast_demand[key] = entry.quantity

        # Get demand consumption from model
        # For batch tracking models: cohort_demand_consumption {(loc, prod, prod_date, demand_date): qty}
        # For aggregate models: demand_consumed {(loc, prod, date): qty}
        cohort_consumption = getattr(self.model_solution, 'cohort_demand_consumption', {})
        aggregate_consumption = getattr(self.model_solution, 'demand_consumed', {})

        # Aggregate consumption by location and product for this date
        supplied_qty: Dict[Tuple[str, str], float] = {}  # (loc, prod) → total supplied

        # Extract from cohort tracking (if available)
        for (loc, prod, prod_date, demand_date), qty in cohort_consumption.items():
            if demand_date == snapshot_date:
                key = (loc, prod)
                supplied_qty[key] = supplied_qty.get(key, 0.0) + qty

        # Extract from aggregate tracking (if available)
        for (loc, prod, date), qty in aggregate_consumption.items():
            if date == snapshot_date:
                key = (loc, prod)
                supplied_qty[key] = supplied_qty.get(key, 0.0) + qty

        # Get shortages from model
        # Format: {(dest, prod, date): qty}
        shortages_dict = self.model_solution.shortages or {}

        # Create demand records for all locations with demand
        for (loc, prod), demand in forecast_demand.items():
            supplied = supplied_qty.get((loc, prod), 0.0)
            shortage = shortages_dict.get((loc, prod, snapshot_date), 0.0)

            # Validation: supplied + shortage should approximately equal demand
            # Allow small tolerance for numerical precision
            total_accounted = supplied + shortage
            if abs(total_accounted - demand) > 0.01:
                # If there's a mismatch, use supplied + shortage as ground truth
                # This could happen if there's rounding or if shortage variable wasn't needed
                if shortage == 0.0:
                    # No explicit shortage variable - calculate from supplied
                    shortage = max(0.0, demand - supplied)

            # Round shortage to exactly 0.0 if within epsilon tolerance to prevent false shortage display
            if shortage < 0.01:
                shortage = 0.0

            record = DemandRecord(
                destination_id=loc,
                product_id=prod,
                demand_quantity=demand,
                supplied_quantity=supplied,
                shortage_quantity=shortage
            )
            demand_records.append(record)

        return demand_records

    def _get_demand_satisfied_legacy(
        self,
        snapshot_date: Date,
        location_inventory: Dict[str, LocationInventory]
    ) -> List[DemandRecord]:
        """
        Calculate demand satisfaction by reconstructing inventory (LEGACY MODE).

        This method calculates how much demand was satisfied from available inventory.
        Since inventory is calculated AFTER demand consumption, the supplied_quantity
        represents what was actually consumed (limited by available inventory).

        Args:
            snapshot_date: Date to check demand satisfaction
            location_inventory: Inventory at each location on this date (after demand consumption)

        Returns:
            List of DemandRecord objects
        """
        demand_records = []

        # Get all demand for this date from forecast
        demand_by_location_product: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for entry in self.forecast.entries:
            if entry.forecast_date == snapshot_date:
                demand_by_location_product[entry.location_id][entry.product_id] = entry.quantity

        # Get ending inventory at each location (after demand consumption)
        ending_inventory_by_location_product: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for location_id, loc_inv in location_inventory.items():
            for product_id, quantity in loc_inv.by_product.items():
                ending_inventory_by_location_product[location_id][product_id] = quantity

        # Create demand records
        # ONLY create records for locations that actually have demand
        all_locations_with_demand = set(demand_by_location_product.keys())

        for location_id in all_locations_with_demand:
            # For this location with demand, check all products that have demand
            all_products_with_demand = set(demand_by_location_product[location_id].keys())

            for product_id in all_products_with_demand:
                demand_qty = demand_by_location_product[location_id][product_id]

                # Calculate what was supplied by comparing with a hypothetical "before consumption" inventory
                # We need to recalculate inventory before consumption for this specific date
                # For now, we use a simplified approach: supplied = min(demand, available inventory before consumption)

                # Get the available inventory before demand consumption
                # This requires a separate calculation or tracking
                # For simplicity, we'll calculate supplied_qty based on whether there's a shortage

                # Since we consumed demand in FIFO order, the supplied quantity is:
                # supplied = demand - shortage
                # We can infer shortage from the ending inventory

                # Actually, we need to track what was available before consumption
                # Let's use a different approach: calculate inventory before demand for this location
                available_before = self._calculate_inventory_before_demand_on_date(
                    location_id, product_id, snapshot_date
                )

                supplied_qty = min(demand_qty, available_before)
                shortage_qty = max(0.0, demand_qty - supplied_qty)

                # Round shortage to exactly 0.0 if within epsilon tolerance
                if shortage_qty < 0.01:
                    shortage_qty = 0.0

                record = DemandRecord(
                    destination_id=location_id,
                    product_id=product_id,
                    demand_quantity=demand_qty,
                    supplied_quantity=supplied_qty,
                    shortage_quantity=shortage_qty
                )
                demand_records.append(record)

        return demand_records

    def _calculate_inventory_before_demand_on_date(
        self,
        location_id: str,
        product_id: str,
        target_date: Date
    ) -> float:
        """
        Calculate inventory available before demand consumption on a specific date.

        This is a helper method to determine how much inventory was available to
        satisfy demand, before the demand was actually consumed.

        Args:
            location_id: Location to check
            product_id: Product to check
            target_date: Date to check inventory on (before demand)

        Returns:
            Quantity available before demand consumption
        """
        # Calculate inventory state just before demand consumption on target_date
        # This means: all activities up to and including target_date, EXCEPT demand on target_date

        batch_quantities: Dict[str, float] = {}

        # Add all production up to target_date
        for batch in self.production_schedule.production_batches:
            if batch.manufacturing_site_id == location_id and batch.production_date <= target_date:
                batch_quantities[batch.id] = batch.quantity

        # Process all shipments up to target_date
        for shipment in self.shipments:
            departure_date = shipment.delivery_date - timedelta(days=shipment.total_transit_days)
            current_date = departure_date
            current_location = shipment.origin_id

            for leg in shipment.route.route_legs:
                next_location = leg.to_location_id
                arrival_date = current_date + timedelta(days=leg.transit_days)

                # Departure
                if current_location == location_id and current_date <= target_date:
                    if shipment.batch_id in batch_quantities:
                        batch_quantities[shipment.batch_id] -= shipment.quantity
                        if batch_quantities[shipment.batch_id] <= 0.01:
                            del batch_quantities[shipment.batch_id]

                # Arrival
                if next_location == location_id and arrival_date <= target_date:
                    if shipment.batch_id not in batch_quantities:
                        batch_quantities[shipment.batch_id] = 0.0
                    batch_quantities[shipment.batch_id] += shipment.quantity

                current_date = arrival_date
                current_location = next_location

        # Consume demand from schedule_start to (target_date - 1)
        # This gives us inventory right before target_date's demand
        if target_date > self.production_schedule.schedule_start_date:
            self._consume_demand_fifo(
                location_id=location_id,
                batch_quantities=batch_quantities,
                start_date=self.production_schedule.schedule_start_date,
                end_date=target_date - timedelta(days=1),
                debug=False
            )

        # Sum up inventory for this product
        total_qty = 0.0
        for batch_id, quantity in batch_quantities.items():
            if quantity > 0.01:
                batch = self._get_batch_by_id(batch_id)
                if batch and batch.product_id == product_id:
                    total_qty += quantity

        return total_qty
