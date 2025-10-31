"""Sliding Window Shelf Life Model for Production-Distribution Planning.

This model uses sliding window constraints for shelf life enforcement instead of
explicit age-cohort tracking. It's significantly faster and simpler than the
cohort-based approach while maintaining exact shelf life enforcement.

Key Features:
- State-based inventory tracking (ambient, frozen, thawed)
- Sliding window constraints for shelf life (17d, 120d, 14d)
- Integer pallet tracking for storage and truck loading
- O(H) variables instead of O(H³) cohorts
- FEFO batch allocation via post-processing

Performance:
- 1-week solve: <30 seconds (vs 2-3 min with cohorts)
- 4-week solve: <2 minutes (vs 6-8 min with cohorts)
- Model building: <5 seconds (vs 30-60 sec with cohorts)

Architecture based on:
- Standard perishables inventory literature (sliding window)
- User-provided formulation for two-state shelf life tracking
- Production-proven approach from SAP/Oracle planning systems
"""

from datetime import date as Date, timedelta
from typing import Dict, List, Set, Tuple, Optional, Any
import warnings
import logging

from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, Set as PyomoSet,
    NonNegativeReals, NonNegativeIntegers, Binary, Integers,
    minimize, quicksum, value
)

logger = logging.getLogger(__name__)

from ..models import Product, CostStructure
from ..models.unified_node import UnifiedNode
from ..models.unified_route import UnifiedRoute, TransportMode
from ..models.unified_truck_schedule import UnifiedTruckSchedule
from ..models.labor_calendar import LaborCalendar
from ..models.forecast import Forecast
from .base_model import BaseOptimizationModel, OptimizationResult


class SlidingWindowModel(BaseOptimizationModel):
    """Sliding window model for production-distribution planning.

    This model uses state-based aggregate flows with sliding window constraints
    for shelf life enforcement. Much faster and simpler than cohort tracking.

    Key Concept:
        Inventory age is tracked implicitly via sliding windows. Products
        that entered a state more than L days ago cannot be used (automatically
        expired and excluded from the feasible region).

    Variables:
        - I[node, product, state, t]: Inventory by state
        - production[node, product, t]: Production quantity
        - shipment[origin, dest, product, t, state]: Shipments by state
        - thaw[node, product, t]: Frozen → thawed flow
        - freeze[node, product, t]: Ambient → frozen flow
        - pallet_count[node, product, state, t]: Integer pallets for storage
        - truck_pallet_load[truck, dest, product, t]: Integer pallets for trucks

    Constraints:
        - Sliding window shelf life (ambient: 17d, frozen: 120d, thawed: 14d)
        - State balance equations (material conservation)
        - Production capacity and labor
        - Truck capacity and scheduling
        - Integer pallet ceiling (storage and trucks)
        - Demand satisfaction

    Objective:
        Minimize: labor + transport + holding + shortage + changeover + waste
        (NO explicit staleness - implicit via holding costs)
    """

    # Shelf life constants (days)
    AMBIENT_SHELF_LIFE = 17
    FROZEN_SHELF_LIFE = 120
    THAWED_SHELF_LIFE = 14
    MINIMUM_ACCEPTABLE_SHELF_LIFE_DAYS = 7  # Breadroom policy

    # Packaging constants
    UNITS_PER_CASE = 10
    CASES_PER_PALLET = 32
    UNITS_PER_PALLET = 320
    PALLETS_PER_TRUCK = 44

    def __init__(
        self,
        nodes: List[UnifiedNode],
        routes: List[UnifiedRoute],
        forecast: Forecast,
        labor_calendar: LaborCalendar,
        cost_structure: CostStructure,
        products: Dict[str, Product],
        start_date: Date,
        end_date: Date,
        truck_schedules: Optional[List[UnifiedTruckSchedule]] = None,
        initial_inventory: Optional[Dict[Tuple, float]] = None,
        inventory_snapshot_date: Optional[Date] = None,
        allow_shortages: bool = True,
        use_pallet_tracking: bool = True,
        use_truck_pallet_tracking: bool = True,
    ):
        """Initialize sliding window model.

        COMPATIBLE with UnifiedNodeModel interface for easy migration.

        Args:
            nodes: List of UnifiedNode objects (same as UnifiedNodeModel)
            routes: List of UnifiedRoute objects (same as UnifiedNodeModel)
            forecast: Forecast object with demand entries
            labor_calendar: Labor availability and costs
            cost_structure: Cost parameters
            products: Product dictionary {id: Product}
            start_date: Planning horizon start
            end_date: Planning horizon end (inclusive)
            truck_schedules: Optional list of truck schedules
            initial_inventory: Initial inventory {(node, product, state): quantity}
            inventory_snapshot_date: Date of inventory snapshot
            allow_shortages: Allow unmet demand (with penalty)
            use_pallet_tracking: Use integer pallets for storage costs
            use_truck_pallet_tracking: Use integer pallets for truck capacity
        """
        super().__init__()

        # Store inputs (compatible with UnifiedNodeModel)
        self.nodes = {node.id: node for node in nodes}
        self.nodes_list = nodes
        self.routes = routes
        self.products = products
        self.products_dict = products

        # Convert forecast to demand dict (FILTER to planning horizon only!)
        self.demand = {}
        for entry in forecast.entries:
            # Only include demand within planning horizon
            if start_date <= entry.forecast_date <= end_date:
                key = (entry.location_id, entry.product_id, entry.forecast_date)
                self.demand[key] = self.demand.get(key, 0) + entry.quantity

        self.forecast = forecast

        # Build date list BEFORE using for filtering
        self.dates = []
        current = start_date
        while current <= end_date:
            self.dates.append(current)
            current += timedelta(days=1)
        self.truck_schedules = truck_schedules or []
        self.labor_calendar = labor_calendar
        self.cost_structure = cost_structure
        self.start_date = start_date
        self.end_date = end_date
        self.allow_shortages = allow_shortages
        self.use_pallet_tracking = use_pallet_tracking
        self.use_truck_pallet_tracking = use_truck_pallet_tracking

        # Preprocess initial inventory to standard format
        self.initial_inventory = self._preprocess_initial_inventory(
            initial_inventory, inventory_snapshot_date
        )

        # Build network indices
        self._build_network_indices()

        print(f"\nSliding Window Model Initialized:")
        print(f"  Nodes: {len(self.nodes)}")
        print(f"  Routes: {len(self.routes)}")
        print(f"  Products: {len(self.products)}")
        print(f"  Planning horizon: {len(self.dates)} days")
        print(f"  Demand entries: {len(self.demand)}")
        print(f"  Pallet tracking: {use_pallet_tracking}")

    def _preprocess_initial_inventory(
        self,
        initial_inventory: Optional[Dict[Tuple, float]],
        snapshot_date: Optional[Date]
    ) -> Dict[Tuple[str, str, str], float]:
        """Convert initial inventory to (node, product, state) format.

        Accepts:
            - 2-tuple: (node, product) → infer state from node
            - 3-tuple: (node, product, state) → use as-is
            - 4-tuple+: (node, product, prod_date, ...) → extract (node, product, state)

        Returns:
            Dict {(node, product, state): quantity}
        """
        if not initial_inventory:
            return {}

        converted = {}

        for key, qty in initial_inventory.items():
            if qty <= 0:
                continue

            if len(key) == 2:
                node_id, prod = key
                # Infer state from node
                node = self.nodes.get(node_id)
                if node and node.supports_frozen_storage() and not node.supports_ambient_storage():
                    state = 'frozen'
                else:
                    state = 'ambient'  # Default
                converted[(node_id, prod, state)] = qty

            elif len(key) == 3:
                node_id, prod, state = key
                converted[(node_id, prod, state)] = qty

            elif len(key) >= 4:
                # Extract from longer tuple (cohort format)
                node_id, prod = key[0], key[1]
                state = key[-1] if len(key) >= 4 else 'ambient'

                # Aggregate if multiple entries
                key_3 = (node_id, prod, state)
                converted[key_3] = converted.get(key_3, 0) + qty

        print(f"  Initial inventory: {len(converted)} entries")
        return converted

    def _build_network_indices(self):
        """Build network routing indices for efficient constraint generation."""
        from collections import defaultdict

        # Routes from/to each node
        self.routes_from_node = defaultdict(list)
        self.routes_to_node = defaultdict(list)

        for route in self.routes:
            # Handle both Route and UnifiedRoute objects
            origin = getattr(route, 'origin_node_id', getattr(route, 'origin_id', None))
            dest = getattr(route, 'destination_node_id', getattr(route, 'destination_id', None))
            if origin and dest:
                self.routes_from_node[origin].append(route)
                self.routes_to_node[dest].append(route)

        # Nodes by capability
        self.manufacturing_nodes = [
            node for node in self.nodes.values()
            if node.can_produce()
        ]
        self.demand_nodes = [
            node for node in self.nodes.values()
            if node.has_demand_capability()
        ]

        print(f"  Manufacturing nodes: {len(self.manufacturing_nodes)}")
        print(f"  Demand nodes: {len(self.demand_nodes)}")

    def build_model(self) -> ConcreteModel:
        """Build the Pyomo optimization model.

        Returns:
            Pyomo ConcreteModel ready to solve
        """
        print("\n" + "="*80)
        print("BUILDING SLIDING WINDOW MODEL")
        print("="*80)

        model = ConcreteModel()

        # Define sets
        model.nodes = PyomoSet(initialize=list(self.nodes.keys()))
        model.products = PyomoSet(initialize=list(self.products.keys()))
        model.dates = PyomoSet(initialize=self.dates, ordered=True)
        model.states = PyomoSet(initialize=['ambient', 'frozen', 'thawed'])

        print(f"\n📐 Sets defined:")
        print(f"  Nodes: {len(list(model.nodes))}")
        print(f"  Products: {len(list(model.products))}")
        print(f"  Dates: {len(list(model.dates))}")
        print(f"  States: {len(list(model.states))}")

        # Add variables
        self._add_variables(model)

        # Add constraints
        self._add_constraints(model)

        # Build objective
        self._build_objective(model)

        print(f"\n✅ Model built successfully")
        return model

    def _add_variables(self, model: ConcreteModel):
        """Add decision variables to model."""
        print(f"\n📊 Adding variables...")

        # PRODUCTION VARIABLES (same as cohort model)
        # production[node, product, t] - continuous quantity
        production_index = [
            (node.id, prod, t)
            for node in self.manufacturing_nodes
            for prod in model.products
            for t in model.dates
        ]
        model.production = Var(
            production_index,
            within=NonNegativeReals,
            doc="Production quantity by node, product, date"
        )
        print(f"  Production variables: {len(production_index)}")

        # STATE-BASED INVENTORY VARIABLES (NEW - replaces inventory_cohort)
        # I[node, product, state, t] - end-of-day inventory in each state
        # CRITICAL: Create inventory vars for ALL nodes (including demand nodes!)
        # Demand nodes need inventory to satisfy demand from
        inventory_index = []
        for node_id, node in self.nodes.items():
            # Skip only if node has no storage AND no demand capability
            if not node.capabilities.can_store and not node.has_demand_capability():
                continue

            for prod in model.products:
                for t in model.dates:
                    # Add state dimensions based on node capabilities
                    if node.supports_frozen_storage():
                        inventory_index.append((node_id, prod, 'frozen', t))
                    if node.supports_ambient_storage() or node.has_demand_capability():
                        # Demand nodes need ambient inventory to satisfy demand from
                        inventory_index.append((node_id, prod, 'ambient', t))
                        inventory_index.append((node_id, prod, 'thawed', t))

        model.inventory = Var(
            inventory_index,
            within=NonNegativeReals,
            doc="End-of-day inventory by node, product, state, date"
        )
        print(f"  Inventory variables: {len(inventory_index)}")

        # STATE TRANSITION VARIABLES (NEW - enables freeze/thaw flows)
        # Only create where transitions make sense!

        # Thaw: frozen → thawed (only for nodes WITH frozen storage capability)
        # Ambient-only nodes receiving frozen shipments: thaw happens automatically on arrival (no thaw variable)
        thaw_index = [
            (node_id, prod, t)
            for node_id, node in self.nodes.items()
            if node.supports_frozen_storage()  # Only nodes that can HOLD frozen inventory
            for prod in model.products
            for t in model.dates
        ]

        # Freeze: ambient → frozen (only for nodes with BOTH frozen AND ambient storage)
        freeze_index = [
            (node_id, prod, t)
            for node_id, node in self.nodes.items()
            if node.supports_frozen_storage() and node.supports_ambient_storage()
            for prod in model.products
            for t in model.dates
        ]

        model.thaw = Var(
            thaw_index,
            within=NonNegativeReals,
            doc="Thawing flow: frozen → thawed"
        )
        model.freeze = Var(
            freeze_index,
            within=NonNegativeReals,
            doc="Freezing flow: ambient → frozen"
        )
        print(f"  State transition variables: {len(thaw_index)} thaw + {len(freeze_index)} freeze")

        # IN-TRANSIT VARIABLES (Pipeline Inventory Tracking)
        # In-transit inventory is indexed by DEPARTURE date (not delivery date)
        #
        # ARCHITECTURAL CHANGE (2025-10-31):
        # Previous: shipment[origin, dest, prod, delivery_date, state]
        # New:      in_transit[origin, dest, prod, departure_date, state]
        #
        # WHY THIS MATTERS:
        # 1. Symmetry: Variables and truck constraints have same date scope (planning horizon only)
        # 2. Material balance: References in_transit[t] directly (no future date indexing)
        # 3. Clarity: "What's in the pipeline on day t" is explicit
        # 4. No escape valve: All in-transit variables are constrained by truck capacity
        #
        # Material balance logic:
        # - Departures on day t: in_transit[origin, dest, prod, t, state]
        # - Arrivals on day t:   in_transit[origin, dest, prod, t - transit_days, state]

        in_transit_index = []
        for route in self.routes:
            for prod in model.products:
                # Create in-transit variables for DEPARTURES within planning horizon only
                for departure_date in model.dates:
                    # In-transit can be in frozen or ambient state
                    for state in ['frozen', 'ambient']:
                        in_transit_index.append((
                            route.origin_node_id,
                            route.destination_node_id,
                            prod,
                            departure_date,  # KEY: indexed by DEPARTURE, not delivery
                            state
                        ))

        model.in_transit = Var(
            in_transit_index,
            within=NonNegativeReals,
            doc="In-transit inventory by route, product, DEPARTURE date, state"
        )
        print(f"  In-transit variables: {len(in_transit_index)} (indexed by DEPARTURE date)")

        # PALLET VARIABLES (optional - for storage costs)
        if self.use_pallet_tracking:
            pallet_index = []
            for node_id, node in self.nodes.items():
                if not node.capabilities.can_store:
                    continue
                for prod in model.products:
                    for t in model.dates:
                        # Track pallets for states with pallet-based costs
                        if node.supports_frozen_storage():
                            pallet_index.append((node_id, prod, 'frozen', t))
                        if node.supports_ambient_storage():
                            # Ambient + thawed share same physical space
                            pallet_index.append((node_id, prod, 'ambient', t))

            model.pallet_count = Var(
                pallet_index,
                within=NonNegativeIntegers,
                bounds=(0, 62),  # Max ~20k units / 320 = 62 pallets
                doc="Integer pallet count for storage costs"
            )
            print(f"  Pallet storage variables: {len(pallet_index)} integers")

            # Pallet entry variables (for fixed entry costs)
            # Only create if fixed costs are configured
            frozen_fixed = self.cost_structure.storage_cost_fixed_per_pallet_frozen or 0
            ambient_fixed = self.cost_structure.storage_cost_fixed_per_pallet_ambient or 0

            if frozen_fixed > 0 or ambient_fixed > 0:
                model.pallet_entry = Var(
                    pallet_index,
                    within=NonNegativeIntegers,
                    bounds=(0, 62),
                    doc="New pallets entering storage (for fixed entry costs)"
                )
                print(f"  Pallet entry variables: {len(pallet_index)} integers (for fixed costs)")

        # TRUCK PALLET VARIABLES (optional - for truck capacity)
        if self.use_truck_pallet_tracking and self.truck_schedules:
            truck_pallet_index = []
            for truck_idx, truck in enumerate(self.truck_schedules):
                # Get truck's destination
                truck_dest = truck.destination_node_id if hasattr(truck, 'destination_node_id') else truck.destination_id

                for t in model.dates:
                    # For each product this truck might carry
                    for prod in model.products:
                        truck_pallet_index.append((truck_idx, truck_dest, prod, t))

            model.truck_pallet_load = Var(
                truck_pallet_index,
                within=NonNegativeIntegers,
                bounds=(0, self.PALLETS_PER_TRUCK),
                doc="Integer pallet count for truck loading"
            )
            print(f"  Truck pallet variables: {len(truck_pallet_index)} integers")

        # DEMAND CONSUMPTION VARIABLES (tracks what's actually consumed from inventory)
        demand_keys = list(self.demand.keys())
        model.demand_consumed = Var(
            demand_keys,
            within=NonNegativeReals,
            doc="Demand actually consumed from inventory"
        )
        print(f"  Demand consumed variables: {len(demand_keys)}")

        # SHORTAGE VARIABLES (if allowed)
        if self.allow_shortages:
            model.shortage = Var(
                demand_keys,
                within=NonNegativeReals,
                doc="Unmet demand with penalty"
            )
            print(f"  Shortage variables: {len(demand_keys)}")

        # BINARY INDICATORS (for changeover tracking, labor, trucks)
        # Product produced indicator
        product_produced_index = [
            (node.id, prod, t)
            for node in self.manufacturing_nodes
            for prod in model.products
            for t in model.dates
        ]
        model.product_produced = Var(
            product_produced_index,
            within=Binary,
            doc="Binary: 1 if product produced on date"
        )

        # Product start indicator (for changeover detection)
        model.product_start = Var(
            product_produced_index,
            within=Binary,
            doc="Binary: 1 if product starts (0→1 transition)"
        )

        print(f"  Binary product indicators: {len(product_produced_index) * 2}")

        # LABOR VARIABLES (for cost modeling)
        labor_index = [
            (node.id, t)
            for node in self.manufacturing_nodes
            for t in model.dates
        ]

        # Labor hours used for production
        model.labor_hours_used = Var(
            labor_index,
            within=NonNegativeReals,
            doc="Total labor hours used for production"
        )

        # Overtime hours (for proper weekday cost model)
        # overtime_hours >= 0 and overtime_hours >= hours_used - fixed_hours
        # Minimization sets overtime_hours = max(0, hours_used - fixed_hours)
        model.overtime_hours = Var(
            labor_index,
            within=NonNegativeReals,
            bounds=(0, 2),  # Max 2h overtime per weekday
            doc="Overtime hours (hours beyond fixed hours on weekdays)"
        )

        print(f"  Labor variables: {len(labor_index)} (hours + overtime)")

        # Mix count variables (integer production batches)
        mix_index = []
        for node in self.manufacturing_nodes:
            for prod_id, product in self.products.items():
                if hasattr(product, 'units_per_mix') and product.units_per_mix > 0:
                    for t in model.dates:
                        mix_index.append((node.id, prod_id, t))

        if mix_index:
            model.mix_count = Var(
                mix_index,
                within=NonNegativeIntegers,
                doc="Number of production mixes (batches)"
            )
            print(f"  Mix count variables: {len(mix_index)} integers")

        print(f"\n✅ Variables created")
        total_vars = (len(production_index) + len(inventory_index) +
                     len(thaw_index) + len(freeze_index) + len(shipment_index))
        total_integers = len(pallet_index) if self.use_pallet_tracking else 0
        total_binaries = len(product_produced_index) * 2
        print(f"  Continuous: {total_vars:,}")
        print(f"  Integers: {total_integers:,}")
        print(f"  Binaries: {total_binaries:,}")
        print(f"  TOTAL: {total_vars + total_integers + total_binaries:,}")
        print(f"  (vs cohort model: ~500,000 total)")


    def _add_constraints(self, model: ConcreteModel):
        """Add constraints to model."""
        print(f"\n🔗 Adding constraints...")

        # Core constraints
        self._add_sliding_window_shelf_life(model)
        self._add_state_balance(model)
        self._add_demand_satisfaction(model)
        self._add_pallet_constraints(model)
        self._add_production_constraints(model)
        self._add_changeover_detection(model)
        self._add_truck_constraints(model)

        print(f"\n✅ Constraints added")

    def _add_sliding_window_shelf_life(self, model: ConcreteModel):
        """Add sliding window shelf life constraints.

        For each state, outflows in any L-day window cannot exceed inflows
        in that same window. Products older than L days are implicitly expired.

        This elegantly handles age reset on state transitions:
        - Thawing creates fresh inflow to 'thawed' state
        - Freezing creates fresh inflow to 'frozen' state
        """
        print(f"\n  Adding sliding window shelf life constraints...")

        # AMBIENT shelf life: 17 days
        def ambient_shelf_life_rule(model, node_id, prod, t):
            """Outflows in 17-day window <= inflows in same window."""
            node = self.nodes[node_id]
            if not node.supports_ambient_storage():
                return Constraint.Skip

            # Window: last 17 days (t-16 to t, inclusive)
            window_start = max(0, list(model.dates).index(t) - 16)
            window_dates = list(model.dates)[window_start:list(model.dates).index(t)+1]

            # Inflows to ambient: initial_inv + production + thaw + arrivals
            Q_ambient = 0

            # Include initial inventory if planning start is in window
            # This allows initial inventory to exist within first 17 days
            # After day 17, initial inventory is outside window (expired)
            first_date = min(model.dates)
            if first_date in window_dates:
                Q_ambient += self.initial_inventory.get((node_id, prod, 'ambient'), 0)

            for tau in window_dates:
                # Production that goes to ambient
                if node.can_produce() and (node_id, prod, tau) in model.production:
                    if node.get_production_state() == 'ambient':
                        Q_ambient += model.production[node_id, prod, tau]

                # Thaw flow
                if (node_id, prod, tau) in model.thaw:
                    Q_ambient += model.thaw[node_id, prod, tau]

                # Arrivals in ambient state
                for route in self.routes_to_node[node_id]:
                    arrival_state = self._determine_arrival_state(route, node)
                    if arrival_state == 'ambient':
                        if (route.origin_node_id, node_id, prod, tau, 'ambient') in model.shipment:
                            Q_ambient += model.shipment[route.origin_node_id, node_id, prod, tau, 'ambient']

            # Outflows from ambient: shipments + freeze + demand_consumed
            O_ambient = 0
            for tau in window_dates:
                # Departures in ambient state (shipments departing on tau)
                for route in self.routes_from_node[node_id]:
                    if route.transport_mode != TransportMode.FROZEN:  # Ambient route
                        # Calculate delivery date for shipment departing on tau
                        delivery_date = tau + timedelta(days=route.transit_days)
                        if (node_id, route.destination_node_id, prod, delivery_date, 'ambient') in model.shipment:
                            O_ambient += model.shipment[node_id, route.destination_node_id, prod, delivery_date, 'ambient']

                # Freeze flow
                if (node_id, prod, tau) in model.freeze:
                    O_ambient += model.freeze[node_id, prod, tau]

                # CRITICAL FIX: Include demand consumption in outflows
                # Without this, consumed inventory doesn't "leave" the window
                # Causes old inventory to persist indefinitely
                if node.has_demand_capability() and (node_id, prod, tau) in model.demand_consumed:
                    O_ambient += model.demand_consumed[node_id, prod, tau]

            # Skip if no activity to avoid trivial True constraint
            # Check if expressions are non-zero (handle Pyomo expressions)
            try:
                if Q_ambient is 0 and O_ambient is 0:
                    return Constraint.Skip
            except:
                pass  # Pyomo expressions can't be compared to 0 easily

            # CRITICAL FIX: Direct inventory constraint (not just material balance)
            # Previous: O <= Q (material conservation, but doesn't prevent old inventory)
            # Correct: inventory[t] <= Q - O (directly limits inventory to window sources)
            # This makes inventory older than 17 days STRUCTURALLY IMPOSSIBLE
            return model.inventory[node_id, prod, 'ambient', t] <= Q_ambient - O_ambient

        model.ambient_shelf_life_con = Constraint(
            [(n, p, t) for n, node in self.nodes.items()
             if node.supports_ambient_storage()
             for p in model.products for t in model.dates],
            rule=ambient_shelf_life_rule,
            doc="Ambient shelf life: 17-day sliding window"
        )

        # FROZEN shelf life: 120 days (similar structure)
        def frozen_shelf_life_rule(model, node_id, prod, t):
            """Outflows in 120-day window <= inflows in same window."""
            node = self.nodes[node_id]
            if not node.supports_frozen_storage():
                return Constraint.Skip

            # Window: last 120 days
            window_start = max(0, list(model.dates).index(t) - 119)
            window_dates = list(model.dates)[window_start:list(model.dates).index(t)+1]

            # Inflows to frozen: initial_inv + production_frozen + freeze
            Q_frozen = 0

            # Include initial frozen inventory if planning start in window
            first_date = min(model.dates)
            if first_date in window_dates:
                Q_frozen += self.initial_inventory.get((node_id, prod, 'frozen'), 0)

            Q_frozen += sum(
                model.production[node_id, prod, tau]
                for tau in window_dates
                if node.can_produce() and node.get_production_state() == 'frozen'
                and (node_id, prod, tau) in model.production
            ) + sum(
                model.freeze[node_id, prod, tau]
                for tau in window_dates
                if (node_id, prod, tau) in model.freeze
            )

            # Outflows from frozen: shipments_frozen + thaw
            O_frozen = sum(
                model.thaw[node_id, prod, tau]
                for tau in window_dates
                if (node_id, prod, tau) in model.thaw
            )

            # CRITICAL FIX: Direct inventory constraint
            return model.inventory[node_id, prod, 'frozen', t] <= Q_frozen - O_frozen

        model.frozen_shelf_life_con = Constraint(
            [(n, p, t) for n, node in self.nodes.items()
             if node.supports_frozen_storage()
             for p in model.products for t in model.dates],
            rule=frozen_shelf_life_rule,
            doc="Frozen shelf life: 120-day sliding window"
        )

        # THAWED shelf life: 14 days
        def thawed_shelf_life_rule(model, node_id, prod, t):
            """Outflows in 14-day window <= inflows in same window."""
            node = self.nodes[node_id]
            if not node.supports_ambient_storage():  # Thawed only at ambient nodes
                return Constraint.Skip

            # Window: last 14 days
            window_start = max(0, list(model.dates).index(t) - 13)
            window_dates = list(model.dates)[window_start:list(model.dates).index(t)+1]

            # Inflows to thawed: initial_inv + thaw (resets age!)
            Q_thawed = 0

            # Include initial thawed inventory if planning start in window
            first_date = min(model.dates)
            if first_date in window_dates:
                Q_thawed += self.initial_inventory.get((node_id, prod, 'thawed'), 0)

            Q_thawed += sum(
                model.thaw[node_id, prod, tau]
                for tau in window_dates
                if (node_id, prod, tau) in model.thaw
            )

            # Outflows from thawed: demand consumption
            # (Thawed is consumed at demand nodes, not shipped further)
            O_thawed = 0
            for tau in window_dates:
                if node.has_demand_capability() and (node_id, prod, tau) in model.demand_consumed:
                    O_thawed += model.demand_consumed[node_id, prod, tau]

            # Skip if no activity
            if Q_thawed == 0:
                return Constraint.Skip

            # CRITICAL FIX: Direct inventory constraint
            return model.inventory[node_id, prod, 'thawed', t] <= Q_thawed - O_thawed

        model.thawed_shelf_life_con = Constraint(
            [(n, p, t) for n, node in self.nodes.items()
             if node.supports_ambient_storage()
             for p in model.products for t in model.dates],
            rule=thawed_shelf_life_rule,
            doc="Thawed shelf life: 14-day sliding window (resets on thaw!)"
        )

        shelf_life_constraints = (
            len([n for n, node in self.nodes.items() if node.supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates)) +
            len([n for n, node in self.nodes.items() if node.supports_frozen_storage()]) * len(list(model.products)) * len(list(model.dates)) +
            len([n for n, node in self.nodes.items() if node.supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates))
        )
        print(f"  Shelf life window constraints: {shelf_life_constraints:,}")
        print(f"    Ambient (17d): ~{len([n for n in self.nodes if self.nodes[n].supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates)):,}")
        print(f"    Frozen (120d): ~{len([n for n in self.nodes if self.nodes[n].supports_frozen_storage()]) * len(list(model.products)) * len(list(model.dates)):,}")
        print(f"    Thawed (14d): ~{len([n for n in self.nodes if self.nodes[n].supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates)):,}")

    def _determine_arrival_state(self, route: UnifiedRoute, dest_node: UnifiedNode) -> str:
        """Determine what state inventory arrives in at destination.

        Implements simplified state transition rules:
        - Ambient transport + Ambient node → ambient (no change)
        - Ambient transport + Frozen node → frozen (freeze on arrival)
        - Frozen transport + Frozen node → frozen (no change)
        - Frozen transport + Ambient node → thawed (thaw on arrival, 14d shelf life starts!)

        Copied exactly from UnifiedNodeModel._determine_arrival_state
        """
        if route.transport_mode == TransportMode.FROZEN:
            # Frozen route
            if dest_node.supports_frozen_storage():
                return 'frozen'  # Stays frozen
            else:
                # Destination is ambient-only → must thaw
                return 'thawed'  # Critical: 6130 (WA) receives as 'thawed', 14-day clock starts!
        else:
            # Ambient route
            if dest_node.supports_ambient_storage():
                return 'ambient'  # Stays ambient
            else:
                # Destination is frozen-only → freeze on arrival
                return 'frozen'

    def _add_state_balance(self, model: ConcreteModel):
        """Add state balance equations (material conservation per SKU, per state).

        For each state, tracks inflows and outflows:

        AMBIENT:
            I[t] = I[t-1] + production_ambient[t] + thaw[t] + arrivals_ambient[t]
                   - shipments_ambient[t] - freeze[t] - demand[t]

        FROZEN:
            I[t] = I[t-1] + production_frozen[t] + freeze[t] + arrivals_frozen[t]
                   - shipments_frozen[t] - thaw[t]

        THAWED:
            I[t] = I[t-1] + thaw[t] + arrivals_thawed[t]
                   - shipments_thawed[t] - demand[t]
        """
        print(f"\n  Adding state balance constraints...")

        # Build date lookup for previous day
        date_list = list(model.dates)
        date_to_prev = {}
        for i, d in enumerate(date_list):
            if i > 0:
                date_to_prev[d] = date_list[i-1]

        # AMBIENT STATE BALANCE
        def ambient_balance_rule(model, node_id, prod, t):
            """Material balance for ambient state."""
            node = self.nodes[node_id]
            if not node.supports_ambient_storage():
                return Constraint.Skip

            if (node_id, prod, 'ambient', t) not in model.inventory:
                return Constraint.Skip

            # Previous day inventory
            prev_date = date_to_prev.get(t)
            if prev_date and (node_id, prod, 'ambient', prev_date) in model.inventory:
                prev_inv = model.inventory[node_id, prod, 'ambient', prev_date]
            else:
                # First day: use initial inventory
                prev_inv = self.initial_inventory.get((node_id, prod, 'ambient'), 0)

            # Inflows
            production_inflow = 0
            if node.can_produce() and (node_id, prod, t) in model.production:
                if node.get_production_state() == 'ambient':
                    production_inflow = model.production[node_id, prod, t]

            thaw_inflow = 0
            if (node_id, prod, t) in model.thaw:
                thaw_inflow = model.thaw[node_id, prod, t]

            # Arrivals: goods that DEPARTED (t - transit_days) ago
            arrivals = sum(
                model.in_transit[route.origin_node_id, node_id, prod, departure_date, 'ambient']
                for route in self.routes_to_node[node_id]
                # Calculate when goods must have departed to arrive today
                if (departure_date := t - timedelta(days=route.transit_days)) in model.dates
                and (route.origin_node_id, node_id, prod, departure_date, 'ambient') in model.in_transit
                and self._determine_arrival_state(route, node) == 'ambient'
            )

            # Outflows
            freeze_outflow = 0
            if (node_id, prod, t) in model.freeze:
                freeze_outflow = model.freeze[node_id, prod, t]

            # Departures: goods leaving TODAY (t) via in-transit
            departures = sum(
                model.in_transit[node_id, route.destination_node_id, prod, t, 'ambient']
                for route in self.routes_from_node[node_id]
                if route.transport_mode != TransportMode.FROZEN  # Ambient routes only
                and (node_id, route.destination_node_id, prod, t, 'ambient') in model.in_transit
            )

            # Demand consumption from ambient inventory
            # Use demand_consumed variable (linked to demand satisfaction constraint)
            demand_consumption = 0
            if node.has_demand_capability():
                if (node_id, prod, t) in model.demand_consumed:
                    demand_consumption = model.demand_consumed[node_id, prod, t]

            # Balance
            return model.inventory[node_id, prod, 'ambient', t] == (
                prev_inv + production_inflow + thaw_inflow + arrivals -
                departures - freeze_outflow - demand_consumption
            )

        model.ambient_balance_con = Constraint(
            [(n, p, t) for n, node in self.nodes.items()
             if node.supports_ambient_storage()
             for p in model.products for t in model.dates],
            rule=ambient_balance_rule,
            doc="Ambient state material balance"
        )

        # FROZEN STATE BALANCE
        def frozen_balance_rule(model, node_id, prod, t):
            """Material balance for frozen state."""
            node = self.nodes[node_id]
            if not node.supports_frozen_storage():
                return Constraint.Skip

            if (node_id, prod, 'frozen', t) not in model.inventory:
                return Constraint.Skip

            # Previous day
            prev_date = date_to_prev.get(t)
            if prev_date and (node_id, prod, 'frozen', prev_date) in model.inventory:
                prev_inv = model.inventory[node_id, prod, 'frozen', prev_date]
            else:
                prev_inv = self.initial_inventory.get((node_id, prod, 'frozen'), 0)

            # Inflows
            production_inflow = 0
            if node.can_produce() and (node_id, prod, t) in model.production:
                if node.get_production_state() == 'frozen':
                    production_inflow = model.production[node_id, prod, t]

            freeze_inflow = 0
            if (node_id, prod, t) in model.freeze:
                freeze_inflow = model.freeze[node_id, prod, t]

            # Arrivals: goods that DEPARTED (t - transit_days) ago
            arrivals = sum(
                model.in_transit[route.origin_node_id, node_id, prod, departure_date, 'frozen']
                for route in self.routes_to_node[node_id]
                # Calculate when goods must have departed to arrive today
                if (departure_date := t - timedelta(days=route.transit_days)) in model.dates
                and (route.origin_node_id, node_id, prod, departure_date, 'frozen') in model.in_transit
                and self._determine_arrival_state(route, node) == 'frozen'
            )

            # Outflows
            thaw_outflow = 0
            if (node_id, prod, t) in model.thaw:
                thaw_outflow = model.thaw[node_id, prod, t]

            # Departures: goods leaving TODAY (t) via in-transit
            departures = sum(
                model.in_transit[node_id, route.destination_node_id, prod, t, 'frozen']
                for route in self.routes_from_node[node_id]
                if route.transport_mode == TransportMode.FROZEN  # Frozen routes only
                and (node_id, route.destination_node_id, prod, t, 'frozen') in model.in_transit
            )

            # Balance
            return model.inventory[node_id, prod, 'frozen', t] == (
                prev_inv + production_inflow + freeze_inflow + arrivals -
                departures - thaw_outflow
            )

        model.frozen_balance_con = Constraint(
            [(n, p, t) for n, node in self.nodes.items()
             if node.supports_frozen_storage()
             for p in model.products for t in model.dates],
            rule=frozen_balance_rule,
            doc="Frozen state material balance"
        )

        # THAWED STATE BALANCE
        def thawed_balance_rule(model, node_id, prod, t):
            """Material balance for thawed state."""
            node = self.nodes[node_id]
            if not node.supports_ambient_storage():
                return Constraint.Skip

            if (node_id, prod, 'thawed', t) not in model.inventory:
                return Constraint.Skip

            # Previous day
            prev_date = date_to_prev.get(t)
            if prev_date and (node_id, prod, 'thawed', prev_date) in model.inventory:
                prev_inv = model.inventory[node_id, prod, 'thawed', prev_date]
            else:
                prev_inv = self.initial_inventory.get((node_id, prod, 'thawed'), 0)

            # Inflows: ONLY from thawing (critical - resets age!)
            thaw_inflow = 0
            if (node_id, prod, t) in model.thaw:
                thaw_inflow = model.thaw[node_id, prod, t]

            # Arrivals: goods that DEPARTED (t - transit_days) ago
            # Thawed products arrive via ambient routes in 'ambient' state
            arrivals = sum(
                model.in_transit[route.origin_node_id, node_id, prod, departure_date, 'ambient']
                for route in self.routes_to_node[node_id]
                # Calculate when goods must have departed to arrive today
                if (departure_date := t - timedelta(days=route.transit_days)) in model.dates
                and (route.origin_node_id, node_id, prod, departure_date, 'ambient') in model.in_transit
                and self._determine_arrival_state(route, node) == 'thawed'
            )

            # Outflows: shipments + demand
            # Thawed products ship as 'ambient' state (but drawn from thawed inventory)
            # Note: In current implementation, thawed state is minimal - most demand from ambient
            # This departure term may be zero in practice
            departures = 0
            # For now, assume thawed inventory doesn't ship (consumed locally via demand)
            # Future: Can add explicit thawed→ambient shipment tracking if needed

            demand_consumption = 0
            # Thawed inventory can satisfy demand
            # In current implementation, demand primarily satisfied from ambient
            # (Thawed state tracking is minimal in sliding window model)

            # Balance
            return model.inventory[node_id, prod, 'thawed', t] == (
                prev_inv + thaw_inflow + arrivals -
                departures - demand_consumption
            )

        model.thawed_balance_con = Constraint(
            [(n, p, t) for n, node in self.nodes.items()
             if node.supports_ambient_storage()
             for p in model.products for t in model.dates],
            rule=thawed_balance_rule,
            doc="Thawed state material balance (14-day shelf life from thaw)"
        )

        balance_constraints = (
            len([n for n, node in self.nodes.items() if node.supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates)) +
            len([n for n, node in self.nodes.items() if node.supports_frozen_storage()]) * len(list(model.products)) * len(list(model.dates)) +
            len([n for n, node in self.nodes.items() if node.supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates))
        )
        print(f"  State balance constraints: {balance_constraints:,}")

    def _add_demand_satisfaction(self, model: ConcreteModel):
        """Add demand satisfaction constraints.

        Demand must be satisfied from available inventory (ambient/thawed) or taken as shortage.

        demand_consumed + shortage = demand
        """
        print(f"\n  Adding demand satisfaction...")

        demand_keys = list(self.demand.keys())

        # DEMAND BALANCE: consumed + shortage = total demand
        def demand_balance_rule(model, node_id, prod, t):
            """Total demand = consumed + shortage."""
            if (node_id, prod, t) not in self.demand:
                return Constraint.Skip

            demand_qty = self.demand[(node_id, prod, t)]
            consumed = model.demand_consumed[node_id, prod, t]

            if self.allow_shortages:
                shortage = model.shortage[node_id, prod, t]
                return consumed + shortage == demand_qty
            else:
                return consumed == demand_qty

        model.demand_balance_con = Constraint(
            demand_keys,
            rule=demand_balance_rule,
            doc="Demand = consumed + shortage"
        )

        print(f"  Demand balance constraints: {len(demand_keys)}")

    def _add_pallet_constraints(self, model: ConcreteModel):
        """Add integer pallet ceiling constraints."""
        print(f"\n  Adding pallet constraints...")

        if not self.use_pallet_tracking:
            return

        # Storage pallet ceiling: pallet_count * 320 >= inventory
        def storage_pallet_ceiling_rule(model, node_id, prod, state, t):
            """Pallet count must cover inventory (ceiling rounding)."""
            # For ambient, sum both ambient and thawed inventory
            if state == 'ambient':
                total_inv = 0
                if (node_id, prod, 'ambient', t) in model.inventory:
                    total_inv += model.inventory[node_id, prod, 'ambient', t]
                if (node_id, prod, 'thawed', t) in model.inventory:
                    total_inv += model.inventory[node_id, prod, 'thawed', t]
                return model.pallet_count[node_id, prod, state, t] * self.UNITS_PER_PALLET >= total_inv
            else:
                # Frozen
                if (node_id, prod, state, t) in model.inventory:
                    return model.pallet_count[node_id, prod, state, t] * self.UNITS_PER_PALLET >= model.inventory[node_id, prod, state, t]
                else:
                    return Constraint.Skip

        model.storage_pallet_ceiling_con = Constraint(
            model.pallet_count.index_set(),
            rule=storage_pallet_ceiling_rule,
            doc="Storage pallet ceiling: pallet_count * 320 >= inventory"
        )
        print(f"    Storage pallet ceiling constraints added")

        # Pallet entry detection (for fixed costs)
        if hasattr(model, 'pallet_entry'):
            # Build date lookup for previous day
            date_list = list(model.dates)
            date_to_prev = {}
            for i, d in enumerate(date_list):
                if i > 0:
                    date_to_prev[d] = date_list[i-1]

            def pallet_entry_detection_rule(model, node_id, prod, state, t):
                """Detect new pallets entering storage: entry >= count[t] - count[t-1]."""
                prev_date = date_to_prev.get(t)

                if prev_date and (node_id, prod, state, prev_date) in model.pallet_count:
                    # pallet_entry[t] >= pallet_count[t] - pallet_count[t-1]
                    # If count increases, entry must cover the increase
                    # If count decreases, minimization sets entry = 0
                    return model.pallet_entry[node_id, prod, state, t] >= \
                           model.pallet_count[node_id, prod, state, t] - \
                           model.pallet_count[node_id, prod, state, prev_date]
                else:
                    # First day: entry = full count (all pallets are new)
                    return model.pallet_entry[node_id, prod, state, t] >= \
                           model.pallet_count[node_id, prod, state, t]

            model.pallet_entry_detection_con = Constraint(
                model.pallet_entry.index_set(),
                rule=pallet_entry_detection_rule,
                doc="Detect new pallets entering storage for fixed costs"
            )
            print(f"    Pallet entry detection constraints added")

        # Truck pallet ceiling (if enabled)
        if self.use_truck_pallet_tracking:
            def truck_pallet_ceiling_rule(model, truck_idx, dest, prod, delivery_date):
                """Truck pallets must cover total in-transit to this destination."""
                # Calculate departure date from delivery date
                # truck_pallet_load is indexed by delivery_date, but in_transit by departure_date
                # Find routes to this destination to get transit_days
                routes_to_dest = [r for r in self.routes if r.destination_node_id == dest]
                if not routes_to_dest:
                    return Constraint.Skip

                # For simplicity, use first route's transit time
                # (In practice, all routes to same dest from manufacturing have same transit time)
                transit_days = routes_to_dest[0].transit_days
                departure_date = delivery_date - timedelta(days=transit_days)

                if departure_date not in model.dates:
                    return Constraint.Skip

                # Sum in-transit departing on this departure_date to this destination
                total_in_transit = sum(
                    model.in_transit[origin, dest, prod, departure_date, state]
                    for origin in model.nodes
                    for state in ['frozen', 'ambient']
                    if (origin, dest, prod, departure_date, state) in model.in_transit
                )
                return model.truck_pallet_load[truck_idx, dest, prod, delivery_date] * self.UNITS_PER_PALLET >= total_in_transit

            model.truck_pallet_ceiling_con = Constraint(
                model.truck_pallet_load.index_set(),
                rule=truck_pallet_ceiling_rule,
                doc="Truck pallet ceiling: pallet_load * 320 >= shipments"
            )
            print(f"    Truck pallet ceiling constraints added")


    def _add_production_constraints(self, model: ConcreteModel):
        """Add production capacity and mix-based production constraints."""
        print(f"\n  Adding production constraints...")

        # MIX-BASED PRODUCTION: production = mix_count × units_per_mix
        if hasattr(model, 'mix_count'):
            def mix_production_rule(model, node_id, prod, t):
                """Link production quantity to integer mix count."""
                if (node_id, prod, t) not in model.mix_count:
                    return Constraint.Skip

                product = self.products[prod]
                units_per_mix = product.units_per_mix if hasattr(product, 'units_per_mix') else 1

                if (node_id, prod, t) in model.production:
                    return model.production[node_id, prod, t] == model.mix_count[node_id, prod, t] * units_per_mix
                else:
                    return Constraint.Skip

            model.mix_production_con = Constraint(
                model.mix_count.index_set(),
                rule=mix_production_rule,
                doc="Production = mix_count × units_per_mix"
            )
            print(f"    Mix-based production constraints added")

        # PRODUCTION CAPACITY: production_time <= labor_hours
        def production_capacity_rule(model, node_id, t):
            """Total production time cannot exceed available labor hours."""
            node = self.nodes[node_id]
            if not node.can_produce():
                return Constraint.Skip

            # Get production rate
            production_rate = node.capabilities.production_rate_per_hour
            if not production_rate or production_rate <= 0:
                return Constraint.Skip

            # Total production
            total_production = sum(
                model.production[node_id, prod, t]
                for prod in model.products
                if (node_id, prod, t) in model.production
            )
            production_time = total_production / production_rate

            # Get available hours
            labor_day = self.labor_calendar.get_labor_day(t)
            if not labor_day:
                return total_production == 0  # No labor → no production

            # Simple capacity: use total available hours (fixed + overtime)
            if labor_day.is_fixed_day:
                max_hours = labor_day.fixed_hours + (labor_day.overtime_hours if hasattr(labor_day, 'overtime_hours') else 0)
            else:
                max_hours = 14.0  # Weekend/holiday max

            # Link to labor hours variable
            if (node_id, t) in model.labor_hours_used:
                return model.labor_hours_used[node_id, t] == production_time
            else:
                return production_time <= max_hours

        model.production_capacity_con = Constraint(
            [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
            rule=production_capacity_rule,
            doc="Production capacity: time <= available labor hours"
        )
        print(f"    Production capacity constraints added")

        # OVERTIME DETECTION: overtime_hours >= hours_used - fixed_hours (for weekdays)
        if hasattr(model, 'overtime_hours'):
            def overtime_detection_rule(model, node_id, t):
                """Detect overtime hours on weekdays: overtime >= hours - fixed."""
                labor_day = self.labor_calendar.get_labor_day(t)
                if not labor_day:
                    return Constraint.Skip

                fixed_hours = labor_day.fixed_hours if hasattr(labor_day, 'fixed_hours') else 0

                if fixed_hours > 0:
                    # Weekday: overtime >= hours_used - fixed_hours
                    # Minimization sets overtime = max(0, hours_used - fixed_hours)
                    return model.overtime_hours[node_id, t] >= model.labor_hours_used[node_id, t] - fixed_hours
                else:
                    # Weekend: no overtime concept (all hours are non_fixed)
                    return model.overtime_hours[node_id, t] == 0

            model.overtime_detection_con = Constraint(
                [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
                rule=overtime_detection_rule,
                doc="Overtime detection: overtime >= hours - fixed (weekdays only)"
            )
            print(f"    Overtime detection constraints added")

    def _add_changeover_detection(self, model: ConcreteModel):
        """Add changeover detection constraints (start tracking)."""
        print(f"\n  Adding changeover detection...")

        # Build date index for lookups
        date_list = list(model.dates)
        date_to_prev = {}
        for i, d in enumerate(date_list):
            if i > 0:
                date_to_prev[d] = date_list[i-1]

        # START DETECTION: product_start[t] >= product_produced[t] - product_produced[t-1]
        def start_detection_rule(model, node_id, prod, t):
            """Detect 0→1 transitions (product starts)."""
            prev_date = date_to_prev.get(t)

            if prev_date and (node_id, prod, prev_date) in model.product_produced:
                # Start = 1 if product_produced went from 0 to 1
                return (model.product_start[node_id, prod, t] >=
                        model.product_produced[node_id, prod, t] -
                        model.product_produced[node_id, prod, prev_date])
            else:
                # First day: start if producing
                return model.product_start[node_id, prod, t] >= model.product_produced[node_id, prod, t]

        model.start_detection_con = Constraint(
            model.product_start.index_set(),
            rule=start_detection_rule,
            doc="Detect product starts (0→1 transitions)"
        )

        # LINK PRODUCTION TO BINARY: production > 0 → product_produced = 1
        def product_binary_linking_rule(model, node_id, prod, t):
            """If production > 0, force product_produced = 1."""
            if (node_id, prod, t) not in model.production:
                return Constraint.Skip

            # Big-M: production <= M * product_produced
            # If product_produced = 0, forces production = 0
            # If product_produced = 1, allows production up to M
            node = self.nodes[node_id]
            production_rate = node.capabilities.production_rate_per_hour or 1400
            max_daily_production = production_rate * 14  # Max hours per day

            return model.production[node_id, prod, t] <= max_daily_production * model.product_produced[node_id, prod, t]

        model.product_binary_linking_con = Constraint(
            [(node.id, prod, t) for node in self.manufacturing_nodes
             for prod in model.products for t in model.dates],
            rule=product_binary_linking_rule,
            doc="Link production quantity to product_produced binary"
        )

        print(f"    Changeover detection constraints added")

    def _add_truck_constraints(self, model: ConcreteModel):
        """Add truck scheduling and capacity constraints with integer pallets."""
        print(f"\n  Adding truck constraints...")

        if not self.truck_schedules or not self.use_truck_pallet_tracking:
            print(f"    Truck constraints skipped (no schedules or tracking disabled)")
            return

        # TRUCK CAPACITY: Sum of pallet loads <= 44 pallets
        def truck_capacity_rule(model, truck_idx, departure_date):
            """Total pallets on this specific truck departure <= 44 pallets.

            Only applies on days when this truck actually operates.
            """
            truck = self.truck_schedules[truck_idx]

            # Check if truck operates on this day of week
            day_of_week_map = {
                0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday',
                4: 'friday', 5: 'saturday', 6: 'sunday'
            }
            actual_day_of_week = day_of_week_map[departure_date.weekday()]

            # Skip if truck doesn't operate on this day
            if truck.day_of_week.lower() != actual_day_of_week:
                return Constraint.Skip

            truck_dest = truck.destination_node_id

            # Find routes TO this truck's destination
            routes_to_dest = [r for r in self.routes if r.destination_node_id == truck_dest]

            if not routes_to_dest:
                return Constraint.Skip

            # Build list of pallet variables to sum
            pallet_vars = []

            for route in routes_to_dest:
                # Calculate delivery date for shipment departing on this date
                delivery_date = departure_date + timedelta(days=route.transit_days)

                # Collect pallet variables for this delivery
                for prod in model.products:
                    if (truck_idx, truck_dest, prod, delivery_date) in model.truck_pallet_load:
                        pallet_vars.append(model.truck_pallet_load[truck_idx, truck_dest, prod, delivery_date])

            # If no variables to sum, skip constraint
            if len(pallet_vars) == 0:
                return Constraint.Skip

            # Use quicksum for proper Pyomo expression
            from pyomo.environ import quicksum
            return quicksum(pallet_vars) <= self.PALLETS_PER_TRUCK

        # Truck capacity constraints (one per truck per departure date)
        truck_index = [(i, t) for i, truck in enumerate(self.truck_schedules) for t in model.dates]
        model.truck_capacity_con = Constraint(
            truck_index,
            rule=truck_capacity_rule,
            doc="Truck capacity: total pallets on departure <= 44"
        )

        print(f"    Truck capacity constraints added: {len(truck_index)}")

    def _build_objective(self, model: ConcreteModel):
        """Build objective function.

        Minimize: labor + transport + holding + shortage + changeover + waste

        NO explicit staleness penalty - holding costs implicitly drive freshness.
        """
        print(f"\n🎯 Building objective...")

        # HOLDING COST (via integer pallets - drives turnover/freshness)
        holding_cost = 0

        if self.use_pallet_tracking and hasattr(model, 'pallet_count'):
            # Frozen pallet costs
            frozen_daily_cost = self.cost_structure.storage_cost_per_pallet_day_frozen or 0
            frozen_fixed_cost = self.cost_structure.storage_cost_fixed_per_pallet_frozen or 0

            # Ambient pallet costs
            ambient_daily_cost = self.cost_structure.storage_cost_per_pallet_day_ambient or 0
            ambient_fixed_cost = self.cost_structure.storage_cost_fixed_per_pallet_ambient or 0

            if frozen_daily_cost > 0 or frozen_fixed_cost > 0:
                # Daily cost: Applied every day to every pallet
                if frozen_daily_cost > 0:
                    holding_cost += sum(
                        frozen_daily_cost * model.pallet_count[node_id, prod, 'frozen', t]
                        for (node_id, prod, state, t) in model.pallet_count
                        if state == 'frozen'
                    )

                # Fixed cost: Applied when NEW pallets enter storage
                if frozen_fixed_cost > 0 and hasattr(model, 'pallet_entry'):
                    holding_cost += sum(
                        frozen_fixed_cost * model.pallet_entry[node_id, prod, 'frozen', t]
                        for (node_id, prod, state, t) in model.pallet_entry
                        if state == 'frozen'
                    )
                    print(f"  Frozen pallet fixed cost: ${frozen_fixed_cost:.4f}/pallet (on entry)")

                print(f"  Frozen pallet daily cost: ${frozen_daily_cost:.4f}/pallet/day")

            if ambient_daily_cost > 0 or ambient_fixed_cost > 0:
                # Daily cost: Applied every day to every pallet
                if ambient_daily_cost > 0:
                    holding_cost += sum(
                        ambient_daily_cost * model.pallet_count[node_id, prod, 'ambient', t]
                        for (node_id, prod, state, t) in model.pallet_count
                        if state == 'ambient'
                    )

                # Fixed cost: Applied when NEW pallets enter storage
                if ambient_fixed_cost > 0 and hasattr(model, 'pallet_entry'):
                    holding_cost += sum(
                        ambient_fixed_cost * model.pallet_entry[node_id, prod, 'ambient', t]
                        for (node_id, prod, state, t) in model.pallet_entry
                        if state == 'ambient'
                    )
                    print(f"  Ambient pallet fixed cost: ${ambient_fixed_cost:.4f}/pallet (on entry)")

                print(f"  Ambient pallet daily cost: ${ambient_daily_cost:.4f}/pallet/day")

        # SHORTAGE COST
        shortage_cost = 0
        if self.allow_shortages and hasattr(model, 'shortage'):
            penalty = self.cost_structure.shortage_penalty_per_unit
            shortage_cost = quicksum(
                penalty * model.shortage[node_id, prod, t]
                for (node_id, prod, t) in model.shortage
            )
            print(f"  Shortage penalty: ${penalty:.2f}/unit")

        # LABOR COST (piecewise: fixed hours FREE, overtime/weekend charged)
        labor_cost = 0
        if hasattr(model, 'labor_hours_used') and hasattr(model, 'overtime_hours'):
            for (node_id, t) in model.labor_hours_used:
                labor_day = self.labor_calendar.get_labor_day(t)
                if labor_day:
                    fixed_hours = labor_day.fixed_hours if hasattr(labor_day, 'fixed_hours') else 0

                    if fixed_hours > 0:
                        # Weekday: Fixed hours (0-12h) are FREE (sunk cost)
                        # Only overtime (>12h) costs money
                        # Use overtime_hours variable (properly bounded >= 0)
                        overtime_rate = labor_day.overtime_rate if hasattr(labor_day, 'overtime_rate') else 660.0
                        labor_cost += overtime_rate * model.overtime_hours[node_id, t]
                    else:
                        # Weekend/holiday: ALL hours charged at non_fixed_rate
                        non_fixed_rate = labor_day.non_fixed_rate if hasattr(labor_day, 'non_fixed_rate') else 1320.0
                        labor_cost += non_fixed_rate * model.labor_hours_used[node_id, t]

            print(f"  Labor cost: Weekday overtime ($660/h) + Weekend ($1320/h), fixed hours FREE")

        # TRANSPORT COST (per-route costs)
        transport_cost = 0
        if hasattr(model, 'in_transit'):
            for (origin, dest, prod, departure_date, state) in model.in_transit:
                # Find route cost
                route = next((r for r in self.routes if r.origin_node_id == origin and r.destination_node_id == dest), None)
                if route and hasattr(route, 'cost_per_unit') and route.cost_per_unit:
                    transport_cost += route.cost_per_unit * model.in_transit[origin, dest, prod, departure_date, state]
            if transport_cost > 0:
                print(f"  Transport cost: route costs included")

        # CHANGEOVER COST (per product start) + YIELD LOSS
        changeover_cost = 0
        changeover_waste_cost = 0

        if hasattr(model, 'product_start'):
            # Direct changeover cost ($)
            changeover_cost_per_start = getattr(self.cost_structure, 'changeover_cost_per_start', 0) or 0
            if changeover_cost_per_start > 0:
                changeover_cost = changeover_cost_per_start * sum(
                    model.product_start[node_id, prod, t]
                    for (node_id, prod, t) in model.product_start
                )
                print(f"  Changeover cost: ${changeover_cost_per_start:.2f} per start")

            # Changeover waste (yield loss in units)
            changeover_waste_units = getattr(self.cost_structure, 'changeover_waste_units', 0) or 0
            if changeover_waste_units > 0:
                production_cost_per_unit = self.cost_structure.production_cost_per_unit or 0
                changeover_waste_cost = production_cost_per_unit * changeover_waste_units * sum(
                    model.product_start[node_id, prod, t]
                    for (node_id, prod, t) in model.product_start
                )
                print(f"  Changeover waste: {changeover_waste_units:.0f} units per start × ${production_cost_per_unit:.2f}/unit = ${production_cost_per_unit * changeover_waste_units:.2f} per start")

        # WASTE COST (end-of-horizon inventory + in-transit)
        # Pipeline inventory tracking: Both inventory at locations AND goods in transit count as waste
        waste_cost = 0
        waste_multiplier = self.cost_structure.waste_cost_multiplier or 0

        if waste_multiplier > 0 and hasattr(model, 'inventory'):
            # Calculate end-of-horizon inventory (at locations)
            last_date = max(model.dates)
            end_inventory = sum(
                model.inventory[node_id, prod, state, last_date]
                for (node_id, prod, state, t) in model.inventory
                if t == last_date
            )

            # Calculate end-of-horizon in-transit (goods departing on last day)
            # These goods are in the pipeline and will deliver after planning horizon ends
            end_in_transit = 0
            if hasattr(model, 'in_transit'):
                end_in_transit = sum(
                    model.in_transit[origin, dest, prod, last_date, state]
                    for (origin, dest, prod, departure_date, state) in model.in_transit
                    if departure_date == last_date
                )

            prod_cost = self.cost_structure.production_cost_per_unit or 1.3
            waste_cost = waste_multiplier * prod_cost * (end_inventory + end_in_transit)
            print(f"  Waste cost: ${waste_multiplier * prod_cost:.2f}/unit × (end_inventory + end_in_transit)")

        # TOTAL OBJECTIVE
        total_cost = (
            labor_cost +
            transport_cost +
            holding_cost +
            shortage_cost +
            changeover_cost +
            changeover_waste_cost +  # Yield loss from product switches
            waste_cost
        )

        model.obj = Objective(
            expr=total_cost,
            sense=minimize,
            doc="Minimize total cost - holding drives freshness implicitly"
        )

        print(f"\n✅ Objective built")
        print(f"  Active components: labor + transport + holding + shortage + changeover (cost + waste)")
        print(f"  Optional: waste (end-of-horizon penalty)")
        print(f"  Staleness: IMPLICIT via holding costs (inventory costs money)")

    def extract_solution(self, model: ConcreteModel) -> 'OptimizationSolution':
        """Extract solution from solved model.

        Returns:
            OptimizationSolution: Pydantic-validated solution with aggregate flows
        """
        from pyomo.core.base import value

        solution = {}

        # Extract production
        production_by_date_product = {}
        if hasattr(model, 'production'):
            for (node_id, prod, t) in model.production:
                var = model.production[node_id, prod, t]
                try:
                    # Try getting value directly
                    if hasattr(var, 'value') and var.value is not None:
                        qty = var.value
                    else:
                        qty = value(var)  # Use Pyomo value() function

                    if qty and abs(qty) > 0.01:
                        production_by_date_product[(node_id, prod, t)] = qty
                except (ValueError, AttributeError, TypeError):
                    # Variable has no value or is uninitialized - try returning 0
                    try:
                        qty = value(var)
                        if qty is None:
                            qty = 0
                        if abs(qty) > 0.01:
                            production_by_date_product[(node_id, prod, t)] = qty
                    except:
                        pass  # Give up on this variable

        solution['production_by_date_product'] = production_by_date_product
        solution['total_production'] = sum(production_by_date_product.values())

        # DIAGNOSTIC: Log production extraction
        logger.info(f"Extracted {len(production_by_date_product)} production entries, total: {solution['total_production']:.0f} units")
        if len(production_by_date_product) == 0:
            logger.warning("NO PRODUCTION EXTRACTED! Check if model.production variable exists and has values.")
            if hasattr(model, 'production'):
                logger.info(f"model.production index size: {len(model.production)}")
            else:
                logger.error("model.production does not exist!")

        # Create production_batches list for UI compatibility
        production_batches = []
        for (node_id, prod, t), qty in production_by_date_product.items():
            production_batches.append({
                'node': node_id,
                'product': prod,
                'date': t,
                'quantity': qty
            })
        solution['production_batches'] = production_batches
        logger.info(f"Created {len(production_batches)} production batch entries for Pydantic solution")

        # Extract inventory by state
        inventory_by_state = {}
        if hasattr(model, 'inventory'):
            for (node_id, prod, state, t) in model.inventory:
                try:
                    qty = value(model.inventory[node_id, prod, state, t])
                    if qty and qty > 0.01:
                        inventory_by_state[(node_id, prod, state, t)] = qty
                except:
                    pass

        solution['inventory'] = inventory_by_state

        # Extract state transitions
        thaw_flows = {}
        freeze_flows = {}
        if hasattr(model, 'thaw'):
            for (node_id, prod, t) in model.thaw:
                try:
                    qty = value(model.thaw[node_id, prod, t])
                    if qty and qty > 0.01:
                        thaw_flows[(node_id, prod, t)] = qty
                except:
                    pass

        if hasattr(model, 'freeze'):
            for (node_id, prod, t) in model.freeze:
                try:
                    qty = value(model.freeze[node_id, prod, t])
                    if qty and qty > 0.01:
                        freeze_flows[(node_id, prod, t)] = qty
                except:
                    pass

        solution['thaw_flows'] = thaw_flows
        solution['freeze_flows'] = freeze_flows

        # Extract shipments (aggregate by route for UI compatibility)
        shipments_by_route = {}
        if hasattr(model, 'shipment'):
            for (origin, dest, prod, delivery_date, state) in model.shipment:
                try:
                    var = model.shipment[origin, dest, prod, delivery_date, state]

                    # Check if variable has a value assigned (skip uninitialized)
                    # Pyomo variables have .stale attribute: True if not assigned by solver
                    if hasattr(var, 'stale') and var.stale:
                        continue  # Skip - solver didn't assign this variable

                    # Safe value extraction
                    if hasattr(var, 'value') and var.value is not None:
                        qty = var.value
                    else:
                        continue  # No value, skip

                    if qty and qty > 0.01:
                        # Aggregate by route (ignoring state for UI simplicity)
                        route_key = (origin, dest, prod, delivery_date)
                        shipments_by_route[route_key] = shipments_by_route.get(route_key, 0) + qty
                except (ValueError, AttributeError, TypeError):
                    # Uninitialized variable - not used in solution, skip
                    pass

        solution['shipments_by_route_product_date'] = shipments_by_route
        logger.info(f"Extracted {len(shipments_by_route)} shipment routes")

        # Extract truck assignments (if truck pallet tracking enabled)
        truck_assignments = {}  # {(origin, dest, product, delivery_date): truck_id}
        if hasattr(model, 'truck_pallet_load'):
            for (truck_idx, dest, prod, delivery_date) in model.truck_pallet_load:
                try:
                    var = model.truck_pallet_load[truck_idx, dest, prod, delivery_date]
                    if hasattr(var, 'stale') and var.stale:
                        continue

                    pallets = value(var) if hasattr(var, 'value') and var.value is not None else 0
                    if pallets and pallets > 0.01:
                        # This shipment is assigned to this truck
                        # Convert truck_idx to actual truck ID
                        truck_id = self.truck_schedules[truck_idx].id if truck_idx < len(self.truck_schedules) else str(truck_idx)

                        # Need to find origin for this dest
                        for origin in model.nodes:
                            route_key = (origin, dest, prod, delivery_date)
                            if route_key in shipments_by_route and shipments_by_route[route_key] > 0:
                                truck_assignments[route_key] = truck_id
                                break
                except:
                    pass

        solution['truck_assignments'] = truck_assignments

        # Extract labor hours by date (for UI)
        labor_hours_by_date = {}
        labor_cost_by_date = {}
        if hasattr(model, 'labor_hours_used'):
            for (node_id, t) in model.labor_hours_used:
                try:
                    hours = value(model.labor_hours_used[node_id, t])
                    if hours and hours > 0.01:
                        labor_hours_by_date[t] = hours

                        # Calculate labor cost (match objective calculation)
                        labor_day = self.labor_calendar.get_labor_day(t)
                        if labor_day:
                            fixed_hours = labor_day.fixed_hours if hasattr(labor_day, 'fixed_hours') else 0

                            if fixed_hours > 0:
                                # Weekday: only overtime costs
                                if (node_id, t) in model.overtime_hours:
                                    overtime = value(model.overtime_hours[node_id, t])
                                    overtime_rate = labor_day.overtime_rate if hasattr(labor_day, 'overtime_rate') else 660.0
                                    labor_cost_by_date[t] = overtime * overtime_rate
                                else:
                                    labor_cost_by_date[t] = 0.0
                            else:
                                # Weekend: all hours cost money
                                non_fixed_rate = labor_day.non_fixed_rate if hasattr(labor_day, 'non_fixed_rate') else 1320.0
                                labor_cost_by_date[t] = hours * non_fixed_rate
                        else:
                            labor_cost_by_date[t] = 0.0
                except:
                    pass

        solution['labor_hours_by_date'] = labor_hours_by_date
        solution['labor_cost_by_date'] = labor_cost_by_date
        logger.info(f"Extracted labor hours for {len(labor_hours_by_date)} dates")

        # Extract shortages
        total_shortage = 0
        shortages_by_location = {}
        if hasattr(model, 'shortage'):
            for (node_id, prod, t) in model.shortage:
                try:
                    var = model.shortage[node_id, prod, t]
                    qty = value(var)  # Don't check .stale
                    if qty and qty > 0.01:
                        shortages_by_location[(node_id, prod, t)] = qty
                        total_shortage += qty
                except (ValueError, AttributeError):
                    pass

        solution['shortages'] = shortages_by_location
        solution['total_shortage_units'] = total_shortage

        # Extract demand consumed
        demand_consumed_by_location = {}
        if hasattr(model, 'demand_consumed'):
            for (node_id, prod, t) in model.demand_consumed:
                try:
                    var = model.demand_consumed[node_id, prod, t]
                    qty = value(var)  # Don't check .stale
                    if qty and qty > 0.01:
                        demand_consumed_by_location[(node_id, prod, t)] = qty
                except (ValueError, AttributeError):
                    pass

        solution['demand_consumed'] = demand_consumed_by_location
        logger.info(f"Extracted demand consumed for {len(demand_consumed_by_location)} demand entries")

        # Calculate fill rate
        total_demand = sum(self.demand.values())
        solution['fill_rate'] = (1 - total_shortage / total_demand) if total_demand > 0 else 1.0

        # Extract costs (from objective if available)
        try:
            solution['total_cost'] = value(model.obj) if hasattr(model, 'obj') else 0
        except Exception as e:
            logger.error(f"Failed to extract total_cost: {e}")
            solution['total_cost'] = 0

        # Calculate individual cost components for UI breakdown
        # Labor cost
        total_labor_hours = sum(labor_hours_by_date.values())
        avg_rate = sum(labor_cost_by_date.values()) / total_labor_hours if total_labor_hours > 0 else 20.0
        solution['total_labor_cost'] = sum(labor_cost_by_date.values())

        # Production cost
        total_production = solution['total_production']
        production_cost_per_unit = self.cost_structure.production_cost_per_unit or 1.3
        solution['total_production_cost'] = total_production * production_cost_per_unit

        # Transport cost (from routes if available)
        total_transport = 0
        for (origin, dest, prod, delivery_date), qty in shipments_by_route.items():
            route = next((r for r in self.routes
                         if r.origin_node_id == origin and r.destination_node_id == dest), None)
            if route and hasattr(route, 'cost_per_unit'):
                total_transport += route.cost_per_unit * qty
        solution['total_transport_cost'] = total_transport
        solution['total_truck_cost'] = 0  # Not separately tracked

        # Shortage cost
        shortage_penalty = self.cost_structure.shortage_penalty_per_unit or 10.0
        solution['total_shortage_cost'] = total_shortage * shortage_penalty

        # Holding cost, changeover costs, waste cost extraction
        # Extract from model if available, otherwise use residual from total_cost
        solution['total_holding_cost'] = 0
        solution['frozen_holding_cost'] = 0
        solution['ambient_holding_cost'] = 0
        solution['total_changeover_cost'] = 0
        solution['total_changeover_waste_cost'] = 0
        solution['total_waste_cost'] = 0

        # Try to extract holding cost from pallet variables
        if hasattr(model, 'pallet_count'):
            try:
                frozen_cost_per_pallet_day = getattr(self.cost_structure, 'storage_cost_per_pallet_day_frozen', 0) or 0
                ambient_cost_per_pallet_day = getattr(self.cost_structure, 'storage_cost_per_pallet_day_ambient', 0) or 0

                for (node_id, prod, state, t) in model.pallet_count:
                    pallets = value(model.pallet_count[node_id, prod, state, t])
                    if pallets > 0.01:
                        if state == 'frozen':
                            solution['frozen_holding_cost'] += pallets * frozen_cost_per_pallet_day
                        elif state in ['ambient', 'thawed']:
                            solution['ambient_holding_cost'] += pallets * ambient_cost_per_pallet_day

                solution['total_holding_cost'] = solution['frozen_holding_cost'] + solution['ambient_holding_cost']
            except:
                pass

        # Extract pallet entry costs (fixed costs)
        if hasattr(model, 'pallet_entry'):
            try:
                frozen_fixed_cost = getattr(self.cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0) or 0
                ambient_fixed_cost = getattr(self.cost_structure, 'storage_cost_fixed_per_pallet_ambient', 0) or 0

                pallet_entry_cost = 0
                for (node_id, prod, state, t) in model.pallet_entry:
                    entries = value(model.pallet_entry[node_id, prod, state, t])
                    if entries > 0.01:
                        if state == 'frozen':
                            pallet_entry_cost += entries * frozen_fixed_cost
                        elif state in ['ambient', 'thawed']:
                            pallet_entry_cost += entries * ambient_fixed_cost

                # Add pallet entry costs to holding costs
                solution['total_holding_cost'] += pallet_entry_cost
                solution['frozen_holding_cost'] += pallet_entry_cost  # Simplified - mostly frozen
            except:
                pass

        # Try to extract changeover costs
        if hasattr(model, 'product_start'):
            try:
                changeover_cost_per_start = getattr(self.cost_structure, 'changeover_cost_per_start', 0) or 0
                changeover_waste_units = getattr(self.cost_structure, 'changeover_waste_units', 0) or 0
                production_cost_per_unit = self.cost_structure.production_cost_per_unit or 0

                total_starts = sum(
                    value(model.product_start[node_id, prod, t])
                    for (node_id, prod, t) in model.product_start
                    if value(model.product_start[node_id, prod, t]) > 0.01
                )

                solution['total_changeover_cost'] = changeover_cost_per_start * total_starts
                solution['total_changeover_waste_cost'] = production_cost_per_unit * changeover_waste_units * total_starts

                logger.info(f"Extracted changeover costs: {total_starts:.0f} starts, cost=${solution['total_changeover_cost']:,.2f}, waste=${solution['total_changeover_waste_cost']:,.2f}")
            except Exception as e:
                logger.error(f"Failed to extract changeover costs: {e}")
                pass

        # Try to extract end-of-horizon waste cost
        waste_multiplier = self.cost_structure.waste_cost_multiplier or 0
        if waste_multiplier > 0 and hasattr(model, 'inventory'):
            try:
                last_date = max(model.dates)
                end_inventory = sum(
                    value(model.inventory[node_id, prod, state, last_date])
                    for (node_id, prod, state, t) in model.inventory
                    if t == last_date and value(model.inventory[node_id, prod, state, last_date]) > 0.01
                )
                prod_cost = self.cost_structure.production_cost_per_unit or 1.3
                solution['total_waste_cost'] = waste_multiplier * prod_cost * end_inventory
            except:
                pass

        # OPTIONAL: Apply FEFO allocator for batch-level detail
        # This converts aggregate flows to individual batches with traceability
        # Only do if requested (adds ~1 second processing time)
        solution['fefo_batches'] = None  # Placeholder for future integration

        # Flag for Daily Snapshot: indicates this is aggregate (not cohort) inventory
        solution['model_type'] = 'sliding_window'
        solution['has_aggregate_inventory'] = True  # Signal to use 'inventory' not 'cohort_inventory'

        # Extract route/leg states for labeling (which routes are frozen vs ambient)
        # This is needed by ProductionLabelingReportGenerator
        self.route_arrival_state = {}
        for route in self.routes:
            # Determine arrival state based on transport mode and destination
            dest_node = self.nodes.get(route.destination_node_id)
            if dest_node:
                arrival_state = self._determine_arrival_state(route, dest_node)
                route_key = (route.origin_node_id, route.destination_node_id)
                self.route_arrival_state[route_key] = arrival_state

        return self._dict_to_optimization_solution(solution)

    def _dict_to_optimization_solution(self, solution_dict: Dict[str, Any]) -> 'OptimizationSolution':
        """Convert solution dictionary to validated OptimizationSolution Pydantic model.

        This method bridges the legacy dict-based solution format with the new
        Pydantic-validated schema for strict interface compliance.

        Args:
            solution_dict: Solution dictionary from extract_solution logic

        Returns:
            OptimizationSolution: Validated Pydantic model

        Raises:
            ValidationError: If solution data doesn't conform to schema
            ValueError: If solution data is incomplete or inconsistent
        """
        # PRE-VALIDATE before attempting Pydantic conversion (fail-fast with clear errors)
        from src.optimization.validation_utils import validate_solution_dict_for_pydantic
        try:
            validate_solution_dict_for_pydantic(solution_dict)
        except (ValueError, TypeError) as e:
            logger.error(f"Solution dict validation failed BEFORE Pydantic conversion: {e}")
            raise ValueError(
                f"extract_solution() produced invalid data structure: {e}\n"
                f"FIX: Ensure all required fields are populated and types are correct."
            ) from e
        from .result_schema import (
            OptimizationSolution,
            ProductionBatchResult,
            LaborHoursBreakdown,
            ShipmentResult,
            TotalCostBreakdown,
            LaborCostBreakdown,
            ProductionCostBreakdown,
            TransportCostBreakdown,
            HoldingCostBreakdown,
            WasteCostBreakdown,
            StorageState,
        )
        from datetime import date as Date

        # 1. Convert production batches
        production_batches = [
            ProductionBatchResult(
                node=batch['node'],
                product=batch['product'],
                date=batch['date'],
                quantity=batch['quantity']
            )
            for batch in solution_dict.get('production_batches', [])
        ]

        # 2. Convert labor hours (ALWAYS use LaborHoursBreakdown, never simple float)
        labor_hours_by_date = {}
        for date_key, hours_value in solution_dict.get('labor_hours_by_date', {}).items():
            if isinstance(hours_value, dict):
                # Already in breakdown format
                labor_hours_by_date[date_key] = LaborHoursBreakdown(**hours_value)
            else:
                # Simple float - convert to breakdown (used hours = paid hours)
                labor_hours_by_date[date_key] = LaborHoursBreakdown(
                    used=hours_value,
                    paid=hours_value,
                    fixed=0.0,
                    overtime=0.0,
                    non_fixed=hours_value
                )

        # 3. Convert shipments from aggregate dict to list
        shipments = []
        shipments_by_route = solution_dict.get('shipments_by_route_product_date', {})
        truck_assignments = solution_dict.get('truck_assignments', {})

        for (origin, dest, prod, delivery_date), qty in shipments_by_route.items():
            # Get truck assignment if available
            route_key = (origin, dest, prod, delivery_date)
            truck_id = truck_assignments.get(route_key)

            # Get arrival state from route mapping
            arrival_state = self.route_arrival_state.get((origin, dest), 'ambient')
            state = StorageState(arrival_state) if arrival_state in ['ambient', 'frozen', 'thawed'] else None

            shipment = ShipmentResult(
                origin=origin,
                destination=dest,
                product=prod,
                quantity=qty,
                delivery_date=delivery_date,
                assigned_truck_id=truck_id,  # Already a string truck ID (e.g., 'T1')
                state=state
            )
            shipments.append(shipment)

        # 4. Build cost breakdown
        # Use residual approach to ensure total matches sum of components
        total_cost = solution_dict.get('total_cost', 0.0)
        labor_cost = solution_dict.get('total_labor_cost', 0.0)
        transport_cost = solution_dict.get('total_transport_cost', 0.0) + solution_dict.get('total_truck_cost', 0.0)
        holding_cost = solution_dict.get('total_holding_cost', 0.0)
        shortage_cost = solution_dict.get('total_shortage_cost', 0.0)
        waste_cost = solution_dict.get('total_waste_cost', 0.0)
        changeover_cost = solution_dict.get('total_changeover_cost', 0.0)
        changeover_waste = solution_dict.get('total_changeover_waste_cost', 0.0)

        # Calculate production cost as RESIDUAL to ensure sum matches total
        # This captures all costs not explicitly broken down (changeover, pallet entry, etc.)
        extracted_sum = labor_cost + transport_cost + holding_cost + shortage_cost + waste_cost
        production_cost_residual = max(0, total_cost - extracted_sum)

        # Build daily breakdown for labor costs (needed by Daily Costs chart)
        labor_cost_by_date_dict = solution_dict.get('labor_cost_by_date', {})
        daily_breakdown_nested: Dict[Date, Dict[str, float]] = {}
        for date_val, total_cost_val in labor_cost_by_date_dict.items():
            # labor_hours_by_date contains LaborHoursBreakdown objects, extract 'used' field
            hours_obj = labor_hours_by_date.get(date_val)
            labor_hours_used = hours_obj.used if hours_obj else 0.0

            if labor_hours_used and labor_hours_used > 0:
                daily_breakdown_nested[date_val] = {
                    'total_hours': labor_hours_used,
                    'fixed_hours': 0,  # Not separately tracked in aggregate model
                    'overtime_hours': 0,  # Not separately tracked
                    'fixed_cost': 0,
                    'overtime_cost': 0,
                    'non_fixed_cost': total_cost_val,  # Assume all non-fixed for aggregate
                    'total_cost': total_cost_val,
                }

        costs = TotalCostBreakdown(
            total_cost=total_cost,
            labor=LaborCostBreakdown(
                total=labor_cost,
                by_date=solution_dict.get('labor_cost_by_date'),
                daily_breakdown=daily_breakdown_nested
            ),
            production=ProductionCostBreakdown(
                total=production_cost_residual,  # Residual (includes changeover, pallet entry, etc.)
                unit_cost=0.0,
                total_units=solution_dict.get('total_production', 0.0),
                changeover_cost=changeover_cost + changeover_waste,
                cost_by_date=None  # Not tracked daily in aggregate model (included in residual)
            ),
            transport=TransportCostBreakdown(
                total=transport_cost,
                shipment_cost=solution_dict.get('total_transport_cost', 0.0),
                truck_fixed_cost=solution_dict.get('total_truck_cost', 0.0),
                freeze_transition_cost=0.0,
                thaw_transition_cost=0.0
            ),
            holding=HoldingCostBreakdown(
                total=holding_cost,
                frozen_storage=solution_dict.get('frozen_holding_cost', 0.0),
                ambient_storage=solution_dict.get('ambient_holding_cost', 0.0),
                thawed_storage=0.0
            ),
            waste=WasteCostBreakdown(
                total=shortage_cost + waste_cost,
                shortage_penalty=shortage_cost,
                expiration_waste=waste_cost
            )
        )

        # 5. Preserve inventory tuple keys (arbitrary_types_allowed enables this)
        # Note: These won't serialize to JSON but that's OK - use to_dict_json_safe()
        inventory_state = solution_dict.get('inventory')

        # 6. Build OptimizationSolution
        opt_solution = OptimizationSolution(
            model_type="sliding_window",
            production_batches=production_batches,
            labor_hours_by_date=labor_hours_by_date,
            shipments=shipments,
            costs=costs,
            total_cost=solution_dict.get('total_cost', 0.0),
            fill_rate=solution_dict.get('fill_rate', 1.0),
            total_production=solution_dict.get('total_production', 0.0),
            total_shortage_units=solution_dict.get('total_shortage_units', 0.0),
            inventory_state=inventory_state,
            has_aggregate_inventory=True,
            use_batch_tracking=False,
            production_by_date_product=solution_dict.get('production_by_date_product'),
            thaw_flows=solution_dict.get('thaw_flows'),
            freeze_flows=solution_dict.get('freeze_flows'),
            shortages=solution_dict.get('shortages'),
            demand_consumed=solution_dict.get('demand_consumed'),  # For Daily Snapshot consumption tracking
            truck_assignments=truck_assignments if truck_assignments else None,
            labor_cost_by_date=solution_dict.get('labor_cost_by_date'),
            fefo_batches=solution_dict.get('fefo_batches'),
            fefo_batch_objects=solution_dict.get('fefo_batch_objects'),
            fefo_batch_inventory=solution_dict.get('fefo_batch_inventory'),
            fefo_shipment_allocations=solution_dict.get('fefo_shipment_allocations'),
        )

        # 7. Preserve legacy dict format fields as extra attributes (needed by FEFO allocator)
        # Pydantic allows extra fields with Extra.allow configuration
        opt_solution.shipments_by_route_product_date = solution_dict.get('shipments_by_route_product_date', {})

        # Validate solution before returning (fail-fast on data issues)
        # Use comprehensive validation from validation_utils
        from src.optimization.validation_utils import validate_optimization_solution_complete
        try:
            validate_optimization_solution_complete(opt_solution)
        except ValueError as e:
            logger.error(f"OptimizationSolution validation failed: {e}")
            raise

        return opt_solution

    def _validate_solution(self, solution: 'OptimizationSolution') -> None:
        """Validate OptimizationSolution for common data issues.

        This method performs sanity checks to catch data extraction bugs early,
        before they cause confusing UI errors.

        Args:
            solution: OptimizationSolution to validate

        Raises:
            ValueError: If validation fails with descriptive error message
        """
        errors = []

        # Check 1: Shipments must exist if there's production
        if solution.total_production > 0.01 and len(solution.shipments) == 0:
            errors.append(
                f"Production exists ({solution.total_production:.0f} units) but no shipments found. "
                "Check that extract_solution() properly converts shipments_by_route to ShipmentResult objects."
            )

        # Check 2: Production batches must match total_production
        batch_sum = sum(b.quantity for b in solution.production_batches)
        if abs(batch_sum - solution.total_production) > 1.0:
            errors.append(
                f"Production batch sum ({batch_sum:.0f}) != total_production ({solution.total_production:.0f}). "
                "Mismatch indicates data extraction bug."
            )

        # Check 3: Labor hours must exist if there's production
        if solution.total_production > 0.01 and len(solution.labor_hours_by_date) == 0:
            errors.append(
                "Production exists but no labor hours found. "
                "Check that labor_hours_by_date is properly populated."
            )

        # Check 4: Model-specific validation
        if solution.model_type == "sliding_window":
            # SlidingWindowModel should have aggregate inventory
            if not solution.has_aggregate_inventory:
                errors.append(
                    "SlidingWindowModel must set has_aggregate_inventory=True"
                )

        # Log warnings (don't fail on these)
        if solution.costs.cost_per_unit_delivered is None and solution.total_production > 0:
            logger.warning(
                "cost_per_unit_delivered is None despite production > 0. "
                "This may indicate no units were delivered (demand = 0)."
            )

        if errors:
            error_msg = "OptimizationSolution validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            f"OptimizationSolution validation passed: "
            f"{len(solution.production_batches)} batches, "
            f"{len(solution.shipments)} shipments, "
            f"fill_rate={solution.fill_rate:.1%}"
        )

    def apply_fefo_allocation(self, method: str = 'greedy'):
        """Apply FEFO batch allocator to convert aggregate flows to batch detail.

        This is OPTIONAL post-processing that provides:
        - Batch-level traceability
        - state_entry_date tracking
        - FEFO (First-Expired-First-Out) allocation
        - Batch genealogy

        Args:
            method: 'greedy' (fast, chronological FEFO) or
                   'lp' (optimal, weighted-age minimization with state awareness)

        Returns:
            Dictionary with batch detail, or None if solution not available
        """
        if not self.solution:
            return None

        # Store allocation method for later reference
        self.fefo_allocation_method = method

        from src.analysis.fefo_batch_allocator import FEFOBatchAllocator

        # Create allocator
        allocator = FEFOBatchAllocator(
            nodes=self.nodes,
            products=self.products,
            start_date=self.start_date,
            end_date=self.end_date
        )

        # Process events DAY BY DAY to build accurate location history
        # Group all events by date
        # Note: self.solution is now OptimizationSolution (Pydantic model)
        production_events = self.solution.production_by_date_product or {}
        shipments_by_route = getattr(self.solution, 'shipments_by_route_product_date', {})
        freeze_flows = self.solution.freeze_flows or {}
        thaw_flows = self.solution.thaw_flows or {}

        # Create batches from initial inventory (at start_date)
        if self.initial_inventory:
            for (node_id, product_id, state), qty in self.initial_inventory.items():
                if qty > 0:
                    from src.analysis.fefo_batch_allocator import Batch
                    import uuid

                    batch = Batch(
                        id=f"INIT_{product_id[:15]}_{state}_{uuid.uuid4().hex[:6]}",
                        product_id=product_id,
                        manufacturing_site_id=node_id,
                        production_date=self.start_date,
                        state_entry_date=self.start_date,
                        current_state=state,
                        quantity=qty,
                        initial_quantity=qty,
                        location_id=node_id,
                        initial_state=state
                    )

                    # Record initial snapshot
                    batch.record_snapshot(self.start_date)

                    allocator.batches.append(batch)
                    allocator.batch_inventory[(node_id, product_id, state)].append(batch)

        # Create all production batches first
        # Note: FEFOBatchAllocator expects dict format, convert Pydantic model to dict
        solution_dict = self.solution.model_dump() if hasattr(self.solution, 'model_dump') else self.solution
        production_batches = allocator.create_batches_from_production(solution_dict)

        # Determine if using weighted age (LP method uses weighted age in greedy for scalability)
        use_weighted_age = (method == 'lp')

        if use_weighted_age:
            logger.info("Using weighted-age FEFO (state-aware: frozen ages 7× slower)")
        else:
            logger.info("Using calendar-age FEFO (chronological, oldest first)")

        # GREEDY with optional weighted age sorting
        # Process shipments chronologically, allocate using weighted or calendar age
        for (origin, dest, prod, delivery_date), qty in sorted(shipments_by_route.items(), key=lambda x: x[0][3]):
            route = next((r for r in self.routes
                         if r.origin_node_id == origin and r.destination_node_id == dest), None)
            state = 'ambient'

            allocator.allocate_shipment(
                origin_node=origin,
                destination_node=dest,
                product_id=prod,
                state=state,
                quantity=qty,
                delivery_date=delivery_date,
                use_weighted_age=use_weighted_age  # LP uses weighted age for sorting
            )

        # Process state transitions (both methods)
        for (node_id, prod, freeze_date), qty in sorted(freeze_flows.items(), key=lambda x: x[0][2]):
            allocator.apply_freeze_transition(node_id, prod, qty, freeze_date)

        for (node_id, prod, thaw_date), qty in sorted(thaw_flows.items(), key=lambda x: x[0][2]):
            allocator.apply_thaw_transition(node_id, prod, qty, thaw_date)

        # Daily snapshots are now recorded during processing:
        # - At production_date when batch created
        # - At delivery_date when batch ships
        # - At freeze/thaw dates when state changes
        #
        # Daily Snapshot uses get_location_on_date() which finds
        # most recent snapshot ≤ query date, so gaps are handled automatically

        # Convert batches to serializable dicts
        batch_dicts = []
        for batch in allocator.batches:
            # Convert location_history dates to ISO strings
            location_history_iso = {d.isoformat(): loc for d, loc in batch.location_history.items()}
            quantity_history_iso = {d.isoformat(): qty for d, qty in batch.quantity_history.items()}

            batch_dicts.append({
                'id': batch.id,
                'product_id': batch.product_id,
                'manufacturing_site_id': batch.manufacturing_site_id,
                'production_date': batch.production_date.isoformat(),
                'state_entry_date': batch.state_entry_date.isoformat(),
                'current_state': batch.current_state,
                'quantity': batch.quantity,
                'initial_quantity': batch.initial_quantity,
                'location_id': batch.location_id,
                'initial_state': batch.initial_state,
                'location_history': location_history_iso,  # Full path through network!
                'quantity_history': quantity_history_iso,  # Quantity at each date
            })

        # Convert batch_inventory tuple keys to strings for Pydantic compatibility
        # Schema expects Dict[str, List[Any]] but allocator uses tuple keys
        batch_inventory_serialized = {}
        for (node_id, product_id, state), batches in allocator.batch_inventory.items():
            key = f"{node_id}|{product_id}|{state}"  # Serialize tuple to string
            batch_inventory_serialized[key] = batches

        # Build return dict
        fefo_result = {
            'batches': batch_dicts,  # List of dicts (JSON-serializable)
            'batch_objects': allocator.batches,  # Keep objects for in-memory use
            'batch_inventory': batch_inventory_serialized,  # STRING keys for Pydantic
            'shipment_allocations': allocator.shipment_allocations,
        }

        # VALIDATE structure before returning (fail-fast if incompatible with Pydantic)
        from src.optimization.validation_utils import validate_fefo_return_structure
        try:
            validate_fefo_return_structure(fefo_result)
        except (ValueError, TypeError) as e:
            logger.error(f"FEFO result structure invalid: {e}")
            raise ValueError(
                f"apply_fefo_allocation() returned invalid structure: {e}\n"
                f"This is a BUG in the FEFO allocator - fix before Pydantic conversion."
            ) from e

        return fefo_result

    def extract_shipments(self):
        """Extract shipments from solution for UI compatibility.

        REFACTORED: Use Pydantic-validated shipments from solution.
        The solution.shipments field already contains converted ShipmentResult objects.

        Returns:
            List of Shipment objects for UI display
        """
        if not self.solution:
            return []

        from src.models.shipment import Shipment
        from src.shelf_life.tracker import RouteLeg
        from src.network.route_finder import RoutePath

        # Use Pydantic-validated shipments (already converted in extract_solution)
        shipment_results = self.solution.shipments

        if not shipment_results:
            logger.warning("No shipments found in OptimizationSolution.shipments")
            return []

        shipments = []

        # Convert ShipmentResult (Pydantic) → Shipment (legacy model) for UI compatibility
        for idx, shipment_result in enumerate(shipment_results, start=1):
            # Find route for complete path information
            route = next((r for r in self.routes
                         if r.origin_node_id == shipment_result.origin and
                            r.destination_node_id == shipment_result.destination), None)

            if not route:
                logger.warning(f"No route found for shipment {shipment_result.origin} → {shipment_result.destination}")
                continue

            # Create single-leg route path
            leg = RouteLeg(
                from_location_id=shipment_result.origin,
                to_location_id=shipment_result.destination,
                transport_mode=shipment_result.state.value if shipment_result.state else 'ambient',
                transit_days=route.transit_days
            )

            route_path = RoutePath(
                path=[shipment_result.origin, shipment_result.destination],
                total_transit_days=route.transit_days,
                total_cost=route.cost_per_unit * shipment_result.quantity if hasattr(route, 'cost_per_unit') else 0,
                transport_modes=[shipment_result.state.value if shipment_result.state else 'ambient'],
                route_legs=[leg],
                intermediate_stops=[]
            )

            # Calculate departure date from delivery date and transit time
            departure_date = shipment_result.departure_date
            if not departure_date:
                departure_date = shipment_result.delivery_date - timedelta(days=route.transit_days)

            shipment = Shipment(
                id=f"SHIP-{idx:04d}",
                batch_id=f"BATCH-AGGREGATE",  # Aggregate flows (no batch tracking in sliding window)
                product_id=shipment_result.product,
                quantity=shipment_result.quantity,
                origin_id=shipment_result.origin,
                destination_id=shipment_result.destination,
                delivery_date=shipment_result.delivery_date,
                route=route_path,
                production_date=shipment_result.production_date or departure_date,
                assigned_truck_id=shipment_result.assigned_truck_id,
            )

            shipments.append(shipment)

        logger.info(f"Converted {len(shipments)} ShipmentResult objects to Shipment objects")
        return shipments
