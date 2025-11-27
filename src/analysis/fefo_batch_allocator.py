"""FEFO (First-Expired-First-Out) Batch Allocator.

Converts aggregate flows from sliding window model into batch-level detail
with full traceability and state_entry_date tracking.

Following TDD: Minimal implementation to pass tests.
"""

from dataclasses import dataclass, field
from datetime import date as Date
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import uuid


@dataclass
class Batch:
    """Represents a production batch with full traceability.

    Attributes:
        id: Unique batch identifier
        product_id: Product manufactured
        manufacturing_site_id: Manufacturing node ID
        production_date: Date of production
        state_entry_date: Date when entered current state
        current_state: Current state (ambient/frozen/thawed)
        quantity: Current quantity (may decrease as allocated)
        initial_quantity: Original production quantity
        location_id: Current location in network
    """
    id: str
    product_id: str
    manufacturing_site_id: str
    production_date: Date
    state_entry_date: Date
    current_state: str
    quantity: float
    initial_quantity: float
    location_id: str
    initial_state: str = field(default='ambient')
    location_history: Dict[Date, str] = field(default_factory=dict)
    quantity_history: Dict[Date, float] = field(default_factory=dict)

    def age_in_state(self, current_date: Date) -> int:
        """Calculate age in current state."""
        return (current_date - self.state_entry_date).days

    def total_age(self, current_date: Date) -> int:
        """Calculate total age since production."""
        return (current_date - self.production_date).days

    def get_location_on_date(self, check_date: Date) -> Optional[str]:
        """Get batch location on a specific date."""
        if check_date in self.location_history:
            return self.location_history[check_date]

        # Find most recent date before or on check_date
        valid_dates = [d for d in self.location_history.keys() if d <= check_date]
        if valid_dates:
            return self.location_history[max(valid_dates)]

        return self.location_id  # Fallback to current

    def get_quantity_on_date(self, check_date: Date) -> float:
        """Get batch quantity on a specific date."""
        if check_date in self.quantity_history:
            return self.quantity_history[check_date]

        # Find most recent date before or on check_date
        valid_dates = [d for d in self.quantity_history.keys() if d <= check_date]
        if valid_dates:
            return self.quantity_history[max(valid_dates)]

        return self.quantity  # Fallback to current

    def record_snapshot(self, snapshot_date: Date):
        """Record current location and quantity for a date."""
        self.location_history[snapshot_date] = self.location_id
        self.quantity_history[snapshot_date] = self.quantity


class FEFOBatchAllocator:
    """Allocates aggregate flows to specific batches using FEFO policy.

    Takes solution from SlidingWindowModel (aggregate flows) and produces
    batch-level detail with full traceability.
    """

    def __init__(
        self,
        nodes: Dict[str, any],
        products: Dict[str, any],
        start_date: Date,
        end_date: Date
    ):
        """Initialize FEFO allocator.

        Args:
            nodes: Dictionary of node objects {id: node}
            products: Dictionary of product objects {id: product}
            start_date: Planning horizon start
            end_date: Planning horizon end
        """
        self.nodes = nodes
        self.products = products
        self.start_date = start_date
        self.end_date = end_date

        # Batch tracking
        self.batches: List[Batch] = []
        self.batch_inventory: Dict[Tuple[str, str, str], List[Batch]] = defaultdict(list)

        # Shipment allocations (for genealogy)
        self.shipment_allocations: List[Dict] = []

        # Deferred batch movements (two-phase allocation)
        # Allows multiple shipments from same origin before moving batches
        self.pending_moves: List[Dict] = []

    def create_batches_from_production(self, solution) -> List[Batch]:
        """Create batches from production events in solution.

        Args:
            solution: Dict or Pydantic OptimizationSolution with production data

        Returns:
            List of created batches
        """
        batches = []
        # Handle both dict and Pydantic OptimizationSolution
        if hasattr(solution, 'production_by_date_product'):
            # Pydantic object
            production_events = solution.production_by_date_product or {}
        elif isinstance(solution, dict):
            # Dict format
            production_events = solution.get('production_by_date_product', {})
        else:
            production_events = {}

        for (node_id, product_id, prod_date), quantity in production_events.items():
            if quantity <= 0:
                continue

            # Get production state from node
            node = self.nodes.get(node_id)
            if node and hasattr(node, 'get_production_state'):
                initial_state = node.get_production_state()
            else:
                initial_state = 'ambient'  # Default

            # Create batch
            batch = Batch(
                id=f"batch_{node_id}_{product_id}_{prod_date}_{uuid.uuid4().hex[:8]}",
                product_id=product_id,
                manufacturing_site_id=node_id,
                production_date=prod_date,
                state_entry_date=prod_date,  # Enters state on production date
                current_state=initial_state,
                quantity=quantity,
                initial_quantity=quantity,
                location_id=node_id,
                initial_state=initial_state
            )

            # Record initial location and quantity on production date
            batch.record_snapshot(prod_date)

            batches.append(batch)
            self.batches.append(batch)

            # Add to inventory tracking
            inv_key = (node_id, product_id, initial_state)
            self.batch_inventory[inv_key].append(batch)

        return batches

    def allocate_shipment(
        self,
        origin_node: str,
        destination_node: str,
        product_id: str,
        state: str,
        quantity: float,
        delivery_date: Date,
        use_weighted_age: bool = False
    ) -> List[Dict]:
        """Allocate shipment quantity from available batches using FEFO policy.

        Args:
            origin_node: Origin node ID
            destination_node: Destination node ID
            product_id: Product ID
            state: Product state (ambient/frozen/thawed)
            quantity: Quantity to ship
            delivery_date: Delivery date

        Returns:
            List of allocations [{'batch_id': str, 'quantity': float}, ...]
        """
        # Get available batches at origin, sorted by age (oldest first = FEFO)
        inv_key = (origin_node, product_id, state)
        available_batches = self.batch_inventory.get(inv_key, [])

        # Sort by age - weighted if requested, calendar age otherwise
        if use_weighted_age:
            # Import weighted age calculation
            from src.analysis.lp_fefo_allocator import calculate_weighted_age_from_batch

            # Sort by weighted age at delivery (oldest weighted age first)
            sorted_batches = sorted(
                available_batches,
                key=lambda b: calculate_weighted_age_from_batch(b, delivery_date),
                reverse=True  # Highest weighted age first (oldest)
            )
        else:
            # Sort by state_entry_date (oldest first for traditional FEFO)
            sorted_batches = sorted(available_batches, key=lambda b: b.state_entry_date)

        # Allocate from oldest batches
        allocations = []
        remaining_to_allocate = quantity

        for batch in sorted_batches:
            if remaining_to_allocate <= 0:
                break

            if batch.quantity <= 0:
                continue

            # Allocate from this batch
            allocated_qty = min(batch.quantity, remaining_to_allocate)

            allocations.append({
                'batch_id': batch.id,
                'product_id': product_id,  # Add product_id for Daily Snapshot flows
                'quantity': allocated_qty,
                'origin': origin_node,
                'destination': destination_node,
                'delivery_date': delivery_date,
                'state': state
            })

            # Update batch quantity (reduce available stock at origin)
            batch.quantity -= allocated_qty
            remaining_to_allocate -= allocated_qty

            # Queue the move for later - DON'T move batch yet!
            # This allows multiple shipments from same origin to allocate
            # from the same batch before it gets moved.
            self.pending_moves.append({
                'batch': batch,
                'origin': origin_node,
                'destination': destination_node,
                'product_id': product_id,
                'delivery_date': delivery_date,
                'state': state,
                'allocated_qty': allocated_qty
            })

        # Store allocation for genealogy
        if allocations:
            self.shipment_allocations.extend(allocations)

        return allocations

    def apply_pending_moves(self):
        """Apply all pending batch moves after allocations complete.

        This two-phase approach allows multiple shipments from same origin
        to allocate from the same batch before it's moved.

        Call this AFTER all allocate_shipment() calls are complete.
        """
        # Track which batches have been processed to handle duplicates
        # (same batch may appear multiple times if partially allocated)
        processed_batches = set()

        for move in self.pending_moves:
            batch = move['batch']
            origin = move['origin']
            dest = move['destination']
            state = move['state']
            delivery_date = move['delivery_date']

            # Skip if already processed (batch may have multiple partial allocations)
            batch_key = (id(batch), origin, state)
            if batch_key in processed_batches:
                continue
            processed_batches.add(batch_key)

            # Remove from origin inventory (if still there)
            inv_key = (origin, batch.product_id, state)
            if batch in self.batch_inventory[inv_key]:
                self.batch_inventory[inv_key].remove(batch)

            # Update batch location to final destination
            batch.location_id = dest

            # Record snapshot at delivery date
            batch.record_snapshot(delivery_date)

            # Add to destination inventory (only if quantity remains)
            if batch.quantity > 0:
                dest_inv_key = (dest, batch.product_id, state)
                if batch not in self.batch_inventory[dest_inv_key]:
                    self.batch_inventory[dest_inv_key].append(batch)

        # Clear pending moves
        self.pending_moves = []

    def apply_freeze_transition(
        self,
        node_id: str,
        product_id: str,
        quantity: float,
        freeze_date: Date
    ) -> List[Batch]:
        """Apply freeze transition (ambient → frozen) to batches using FEFO.

        Args:
            node_id: Node where freezing occurs
            product_id: Product ID
            quantity: Quantity to freeze
            freeze_date: Date of freeze transition

        Returns:
            List of batches that were frozen (or created from splits)
        """
        # Get available ambient batches at node (oldest first)
        inv_key = (node_id, product_id, 'ambient')
        available_batches = self.batch_inventory.get(inv_key, [])
        sorted_batches = sorted(available_batches, key=lambda b: b.state_entry_date)

        frozen_batches = []
        remaining_to_freeze = quantity

        for batch in sorted_batches:
            if remaining_to_freeze <= 0:
                break

            if batch.quantity <= 0:
                continue

            # Determine how much to freeze from this batch
            freeze_qty = min(batch.quantity, remaining_to_freeze)

            if freeze_qty >= batch.quantity:
                # Freeze entire batch
                batch.current_state = 'frozen'
                batch.state_entry_date = freeze_date  # Age resets!
                # Keep quantity unchanged (don't subtract - just transition state)

                # Remove from ambient inventory
                if batch in self.batch_inventory[inv_key]:
                    self.batch_inventory[inv_key].remove(batch)

                # Add to frozen inventory
                frozen_key = (node_id, product_id, 'frozen')
                self.batch_inventory[frozen_key].append(batch)

                frozen_batches.append(batch)
            else:
                # Partial freeze - split batch
                batch.quantity -= freeze_qty

                # Create new frozen batch (copy of original)
                frozen_batch = Batch(
                    id=f"{batch.id}_frozen_{uuid.uuid4().hex[:8]}",
                    product_id=batch.product_id,
                    manufacturing_site_id=batch.manufacturing_site_id,
                    production_date=batch.production_date,  # Preserve original prod date
                    state_entry_date=freeze_date,  # New state entry date!
                    current_state='frozen',
                    quantity=freeze_qty,
                    initial_quantity=batch.initial_quantity,
                    location_id=node_id,
                    initial_state=batch.initial_state
                )

                self.batches.append(frozen_batch)

                # Add to frozen inventory
                frozen_key = (node_id, product_id, 'frozen')
                self.batch_inventory[frozen_key].append(frozen_batch)

                frozen_batches.append(frozen_batch)

            remaining_to_freeze -= freeze_qty

        return frozen_batches

    def apply_thaw_transition(
        self,
        node_id: str,
        product_id: str,
        quantity: float,
        thaw_date: Date
    ) -> List[Batch]:
        """Apply thaw transition (frozen → thawed) to batches using FEFO.

        Args:
            node_id: Node where thawing occurs
            product_id: Product ID
            quantity: Quantity to thaw
            thaw_date: Date of thaw transition

        Returns:
            List of batches that were thawed (or created from splits)
        """
        # Get available frozen batches at node (oldest first)
        inv_key = (node_id, product_id, 'frozen')
        available_batches = self.batch_inventory.get(inv_key, [])
        sorted_batches = sorted(available_batches, key=lambda b: b.state_entry_date)

        thawed_batches = []
        remaining_to_thaw = quantity

        for batch in sorted_batches:
            if remaining_to_thaw <= 0:
                break

            if batch.quantity <= 0:
                continue

            # Determine how much to thaw from this batch
            thaw_qty = min(batch.quantity, remaining_to_thaw)

            if thaw_qty >= batch.quantity:
                # Thaw entire batch
                batch.current_state = 'thawed'
                batch.state_entry_date = thaw_date  # Age RESETS!
                # Keep quantity unchanged (don't subtract - just transition state)

                # Remove from frozen inventory
                if batch in self.batch_inventory[inv_key]:
                    self.batch_inventory[inv_key].remove(batch)

                # Add to thawed inventory
                thawed_key = (node_id, product_id, 'thawed')
                self.batch_inventory[thawed_key].append(batch)

                thawed_batches.append(batch)
            else:
                # Partial thaw - split batch
                batch.quantity -= thaw_qty

                # Create new thawed batch
                thawed_batch = Batch(
                    id=f"{batch.id}_thawed_{uuid.uuid4().hex[:8]}",
                    product_id=batch.product_id,
                    manufacturing_site_id=batch.manufacturing_site_id,
                    production_date=batch.production_date,
                    state_entry_date=thaw_date,  # New state entry date!
                    current_state='thawed',
                    quantity=thaw_qty,
                    initial_quantity=batch.initial_quantity,
                    location_id=node_id,
                    initial_state=batch.initial_state
                )

                self.batches.append(thawed_batch)

                # Add to thawed inventory
                thawed_key = (node_id, product_id, 'thawed')
                self.batch_inventory[thawed_key].append(thawed_batch)

                thawed_batches.append(thawed_batch)

            remaining_to_thaw -= thaw_qty

        return thawed_batches

    def apply_disposal(
        self,
        node_id: str,
        product_id: str,
        state: str,
        quantity: float,
        disposal_date: Date
    ) -> List[Batch]:
        """Remove disposed inventory from batch tracking.

        When the optimization model disposes of expired inventory, this method
        removes those batches from the FEFO allocator's tracking to prevent
        them from appearing in the Daily Inventory Snapshot.

        Args:
            node_id: Node where disposal occurs
            product_id: Product ID
            state: Product state being disposed (ambient/frozen/thawed)
            quantity: Quantity to dispose
            disposal_date: Date of disposal

        Returns:
            List of batches that were disposed (fully or partially)
        """
        inv_key = (node_id, product_id, state)
        available_batches = self.batch_inventory.get(inv_key, [])

        # Sort by age (oldest first - dispose oldest first, matching FEFO)
        sorted_batches = sorted(available_batches, key=lambda b: b.state_entry_date)

        disposed_batches = []
        remaining_to_dispose = quantity

        for batch in sorted_batches:
            if remaining_to_dispose <= 0:
                break

            if batch.quantity <= 0:
                continue

            dispose_qty = min(batch.quantity, remaining_to_dispose)
            batch.quantity -= dispose_qty
            remaining_to_dispose -= dispose_qty

            # Track disposed batch
            disposed_batches.append({
                'batch_id': batch.id,
                'disposed_quantity': dispose_qty,
                'disposal_date': disposal_date,
                'node_id': node_id,
                'product_id': product_id,
                'state': state
            })

            # Remove batch from inventory if fully disposed
            if batch.quantity <= 0:
                if batch in self.batch_inventory[inv_key]:
                    self.batch_inventory[inv_key].remove(batch)

        return disposed_batches
