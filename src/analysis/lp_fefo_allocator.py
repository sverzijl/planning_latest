"""LP-based FEFO Batch Allocator with State-Aware Weighted Aging.

Optimizes batch allocation to minimize weighted age at destination, accounting
for different aging rates in different states (frozen ages slower than ambient).

Key Innovation: Weighted age = (days_in_ambient/17) + (days_in_frozen/120) + (days_in_thawed/14)

This properly values frozen storage - a 60-day-old frozen batch has same
effective age as a 8.5-day-old ambient batch!
"""

from typing import Dict, List, Tuple, Optional
from datetime import date as Date, timedelta
import logging

from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective,
    NonNegativeReals, minimize, quicksum, value
)

logger = logging.getLogger(__name__)


# Shelf life constants (days)
AMBIENT_SHELF_LIFE = 17
FROZEN_SHELF_LIFE = 120
THAWED_SHELF_LIFE = 14


def calculate_weighted_age_from_batch(
    batch,
    delivery_date: Date
) -> float:
    """Calculate weighted age at delivery accounting for state transitions.

    Uses batch.initial_state, batch.state_entry_date, and batch.current_state
    to infer time spent in each state.

    Args:
        batch: Batch object with production_date, state_entry_date, initial_state, current_state
        delivery_date: When shipment delivers

    Returns:
        Weighted age as fraction of shelf life consumed (0 to 1+)

    Example:
        Batch produced Oct 15 in 'ambient':
          production_date: Oct 15
          initial_state: 'ambient'
          state_entry_date: Oct 20 (frozen on Oct 20)
          current_state: 'frozen'

        Delivery on Oct 30:
          Days in ambient: Oct 15-20 = 5 days → 5/17 = 0.294
          Days in frozen: Oct 20-30 = 10 days → 10/120 = 0.083
          Weighted age: 0.294 + 0.083 = 0.377 (37.7% of shelf life)

    Key insight: Frozen batch with 10 days age has effective_age = 10/120 = 0.083
                Ambient batch with 10 days age has effective_age = 10/17 = 0.588
                → Frozen is 7× "younger" despite same calendar age!
    """
    weighted_age = 0.0

    # Time in initial state (production_date to state_entry_date)
    days_in_initial = (batch.state_entry_date - batch.production_date).days

    if days_in_initial > 0:
        if batch.initial_state == 'ambient':
            weighted_age += days_in_initial / AMBIENT_SHELF_LIFE
        elif batch.initial_state == 'frozen':
            weighted_age += days_in_initial / FROZEN_SHELF_LIFE
        elif batch.initial_state == 'thawed':
            weighted_age += days_in_initial / THAWED_SHELF_LIFE

    # Time in current state (state_entry_date to delivery_date)
    days_in_current = (delivery_date - batch.state_entry_date).days

    if days_in_current > 0:
        if batch.current_state == 'ambient':
            weighted_age += days_in_current / AMBIENT_SHELF_LIFE
        elif batch.current_state == 'frozen':
            weighted_age += days_in_current / FROZEN_SHELF_LIFE
        elif batch.current_state == 'thawed':
            weighted_age += days_in_current / THAWED_SHELF_LIFE

    return weighted_age


class LPFEFOAllocator:
    """LP-based FEFO allocator with weighted state-aware aging.

    Formulates batch allocation as LP to minimize weighted age at destination,
    accounting for different aging rates in frozen vs ambient vs thawed states.
    """

    def __init__(
        self,
        batches: List,
        shipments: List[Tuple],
        ambient_shelf_life: int = 17,
        frozen_shelf_life: int = 120,
        thawed_shelf_life: int = 14
    ):
        """Initialize LP FEFO allocator.

        Args:
            batches: List of Batch objects available for allocation
            shipments: List of (origin, dest, product, state, quantity, delivery_date) tuples
            ambient_shelf_life: Days in ambient shelf life
            frozen_shelf_life: Days in frozen shelf life
            thawed_shelf_life: Days in thawed shelf life
        """
        self.batches = batches
        self.shipments = shipments
        self.ambient_shelf_life = ambient_shelf_life
        self.frozen_shelf_life = frozen_shelf_life
        self.thawed_shelf_life = thawed_shelf_life

        self.model = None
        self.allocation_result = None

    def optimize_allocation(self) -> Dict:
        """Solve LP to find optimal batch-to-shipment allocation.

        Minimizes weighted age at destination, accounting for state transitions
        and different aging rates.

        Returns:
            Dict with allocation results:
            {
                'allocations': [(batch_id, shipment_idx, quantity), ...],
                'objective_value': weighted_age_total,
                'solve_time': seconds
            }
        """
        import time

        model = ConcreteModel()

        # Sets
        model.batches = range(len(self.batches))
        model.shipments = range(len(self.shipments))

        # Decision variables: x[b,s] = quantity of batch b allocated to shipment s
        model.x = Var(
            model.batches,
            model.shipments,
            within=NonNegativeReals,
            doc="Batch to shipment allocation"
        )

        # Objective: Minimize weighted age at destination
        def objective_rule(model):
            total_weighted_age = 0

            for b_idx in model.batches:
                batch = self.batches[b_idx]

                for s_idx in model.shipments:
                    shipment = self.shipments[s_idx]
                    (origin, dest, product, state, qty, delivery_date) = shipment

                    # Check if batch can serve this shipment
                    if (batch.location_id != origin or
                        batch.product_id != product or
                        batch.current_state != state):
                        continue  # Incompatible

                    # Calculate weighted age at delivery using state-aware calculation
                    # This properly values frozen storage (120 day shelf life vs 17 ambient)
                    weighted_age = calculate_weighted_age_from_batch(batch, delivery_date)

                    # Add to objective: weighted_age × quantity allocated
                    total_weighted_age += weighted_age * model.x[b_idx, s_idx]

            return total_weighted_age

        model.obj = Objective(rule=objective_rule, sense=minimize)

        # Pre-compute compatible batches for each shipment
        compatible_batches = {}
        for s_idx in model.shipments:
            shipment = self.shipments[s_idx]
            (origin, dest, product, state, qty, delivery_date) = shipment

            compatible = []
            for b_idx in model.batches:
                batch = self.batches[b_idx]
                if (batch.location_id == origin and
                    batch.product_id == product and
                    batch.current_state == state and
                    batch.quantity > 0.01):
                    compatible.append(b_idx)

            compatible_batches[s_idx] = compatible

            # Check if shipment can be satisfied
            total_available = sum(self.batches[b_idx].quantity for b_idx in compatible)
            if total_available < qty - 0.01:
                logger.warning(f"Shipment {s_idx} ({origin}→{dest}, {product[:20]}, {qty:.0f}) has insufficient batches: {total_available:.0f} available")

        # Constraint 1: Each shipment must be satisfied
        def shipment_satisfaction_rule(model, s_idx):
            compatible = compatible_batches[s_idx]

            if not compatible:
                # No compatible batches - constraint infeasible
                return Constraint.Skip

            return sum(model.x[b_idx, s_idx] for b_idx in compatible) == self.shipments[s_idx][4]  # qty

        model.shipment_satisfaction = Constraint(
            model.shipments,
            rule=shipment_satisfaction_rule,
            doc="Each shipment must be fully satisfied"
        )

        # Constraint 2: Batch capacity (can't allocate more than available)
        def batch_capacity_rule(model, b_idx):
            batch = self.batches[b_idx]

            return sum(
                model.x[b_idx, s_idx]
                for s_idx in model.shipments
            ) <= batch.quantity

        model.batch_capacity = Constraint(
            model.batches,
            rule=batch_capacity_rule,
            doc="Cannot allocate more than batch has"
        )

        # Solve
        from pyomo.opt import SolverFactory

        logger.info(f"Building LP FEFO model: {len(self.batches)} batches × {len(self.shipments)} shipments")

        start_time = time.time()

        try:
            # Use HiGHS (fast LP solver)
            solver = SolverFactory('appsi_highs')
            results = solver.solve(model)
            solve_time = time.time() - start_time

            logger.info(f"LP FEFO solved in {solve_time:.2f}s")

            # Extract allocations
            allocations = []
            for b_idx in model.batches:
                for s_idx in model.shipments:
                    qty = value(model.x[b_idx, s_idx])
                    if qty > 0.01:
                        allocations.append({
                            'batch_id': self.batches[b_idx].id,
                            'shipment_idx': s_idx,
                            'quantity': qty,
                            'batch_idx': b_idx
                        })

            result = {
                'allocations': allocations,
                'objective_value': value(model.obj),
                'solve_time': solve_time,
                'method': 'LP',
                'num_variables': len(model.batches) * len(model.shipments),
                'num_nonzero': len(allocations)
            }

            logger.info(f"LP FEFO: {len(allocations)} non-zero allocations, objective={value(model.obj):.4f}")

            return result

        except Exception as e:
            logger.error(f"LP FEFO failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def apply_lp_allocation(self, lp_result: Dict, fefo_allocator) -> None:
        """Apply LP allocation results to FEFO batch allocator.

        Takes LP solution and updates batch locations/quantities accordingly.

        Args:
            lp_result: Result dict from optimize_allocation()
            fefo_allocator: FEFOBatchAllocator instance to update
        """
        if not lp_result:
            return

        allocations = lp_result['allocations']

        # Group allocations by shipment
        by_shipment = {}
        for alloc in allocations:
            s_idx = alloc['shipment_idx']
            if s_idx not in by_shipment:
                by_shipment[s_idx] = []
            by_shipment[s_idx].append(alloc)

        # Apply allocations shipment by shipment
        for s_idx in sorted(by_shipment.keys()):
            shipment = self.shipments[s_idx]
            (origin, dest, product, state, qty, delivery_date) = shipment

            # Apply all batch allocations for this shipment
            for alloc in by_shipment[s_idx]:
                b_idx = alloc['batch_idx']
                alloc_qty = alloc['quantity']

                batch = self.batches[b_idx]

                # Update batch similar to greedy allocate_shipment
                inv_key = (batch.location_id, batch.product_id, batch.current_state)

                # Remove from current location inventory
                if batch in fefo_allocator.batch_inventory[inv_key]:
                    fefo_allocator.batch_inventory[inv_key].remove(batch)

                # Update quantity
                batch.quantity -= alloc_qty

                # Move to destination
                batch.location_id = dest

                # Record snapshot at delivery
                batch.record_snapshot(delivery_date)

                # Add to destination inventory (if quantity remains)
                dest_inv_key = (dest, product, state)
                if batch.quantity > 0:
                    fefo_allocator.batch_inventory[dest_inv_key].append(batch)

                # Record allocation
                fefo_allocator.shipment_allocations.append({
                    'batch_id': batch.id,
                    'quantity': alloc_qty,
                    'origin': origin,
                    'destination': dest,
                    'delivery_date': delivery_date,
                    'state': state,
                    'method': 'LP'
                })


def allocate_batches_lp(
    batches: List,
    shipments: List[Tuple],
    allocation_method: str = 'greedy'
) -> Optional[Dict]:
    """Allocate batches to shipments using specified method.

    Args:
        batches: List of Batch objects
        shipments: List of shipment tuples
        allocation_method: 'greedy' (fast, FEFO-at-departure) or
                          'lp' (optimal, weighted-age-at-destination)

    Returns:
        Allocation result dict or None if failed
    """
    if allocation_method == 'lp':
        allocator = LPFEFOAllocator(batches, shipments)
        return allocator.optimize_allocation()
    else:
        # Greedy method handled by FEFOBatchAllocator
        return None  # Caller uses greedy
