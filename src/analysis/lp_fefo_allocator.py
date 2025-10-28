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

        # Constraint 1: Each shipment must be satisfied
        def shipment_satisfaction_rule(model, s_idx):
            shipment = self.shipments[s_idx]
            (origin, dest, product, state, qty, delivery_date) = shipment

            return sum(
                model.x[b_idx, s_idx]
                for b_idx in model.batches
                if (self.batches[b_idx].location_id == origin and
                    self.batches[b_idx].product_id == product and
                    self.batches[b_idx].current_state == state)
            ) == qty

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

            return {
                'allocations': allocations,
                'objective_value': value(model.obj),
                'solve_time': solve_time,
                'method': 'LP'
            }

        except Exception as e:
            logger.error(f"LP FEFO failed: {e}")
            return None


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
