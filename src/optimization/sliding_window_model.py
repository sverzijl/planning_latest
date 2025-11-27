"""Sliding Window Shelf Life Model for Production-Distribution Planning.

This model uses sliding window constraints for shelf life enforcement instead of
explicit age-cohort tracking. It's significantly faster and simpler than the
cohort-based approach while maintaining exact shelf life enforcement.

Key Features:
- State-based inventory tracking (ambient, frozen, thawed)
- Sliding window constraints for shelf life (17d, 120d, 14d)
- Pipeline inventory tracking (in-transit indexed by departure date)
- Integer pallet tracking for storage and truck loading
- O(H) variables instead of O(H³) cohorts
- FEFO batch allocation via post-processing

Pipeline Inventory Tracking (2025-10-31 Refactor):
- in_transit[origin, dest, prod, departure_date, state] variables
- Indexed by DEPARTURE date (not delivery date)
- All variables within planning horizon only (no beyond-horizon extension)
- Material balance references in_transit[t] directly (no future date indexing)
- Symmetric scope: variables and truck constraints both cover model.dates
- Eliminates unconstrained escape valve for last-day material balance

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
from . import constants


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
        - demand_consumed_from_ambient[node, product, t]: Consumption from ambient
        - demand_consumed_from_thawed[node, product, t]: Consumption from thawed

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

    MIP Formulation Patterns:
        1. Time-Stepped State Variables: inventory[t] ← inventory[t-1] (ACYCLIC)
        2. Big-M Indicators: production ≤ M × binary (proper direction)
        3. Accounting Identities: consumption + shortage = demand
        4. Inequality Bounds: Shelf life windows O ≤ Q

    Circular Dependency Prevention:
        - Material balance is SUFFICIENT to bound consumption (no explicit limits needed)
        - Consumption bounded by: inventory[t] = inv[t-1] + prod - cons ≥ 0
        - No variable appears on both LHS and RHS of same constraint
        - Big-M constraints use correct direction (sum <= N×indicator, not indicator×N >= sum)

    Performance: O(H) variables where H = horizon length
        - 1-week: <2s, ~2,800 vars
        - 4-week: <120s, ~12,000 vars
        - vs. O(H³) for explicit age-cohort tracking (~500k vars)

    Verified Acyclic: 2025-11-05 (see docs/CONSTRAINT_STRUCTURE_AND_ACYCLICITY.md)
    """

    # Shelf life constants (days) - imported from constants module
    AMBIENT_SHELF_LIFE = constants.AMBIENT_SHELF_LIFE_DAYS
    FROZEN_SHELF_LIFE = constants.FROZEN_SHELF_LIFE_DAYS
    THAWED_SHELF_LIFE = constants.THAWED_SHELF_LIFE_DAYS
    MINIMUM_ACCEPTABLE_SHELF_LIFE_DAYS = constants.MINIMUM_ACCEPTABLE_SHELF_LIFE_DAYS

    # Packaging constants - imported from constants module
    UNITS_PER_CASE = constants.UNITS_PER_CASE
    CASES_PER_PALLET = constants.CASES_PER_PALLET
    UNITS_PER_PALLET = constants.UNITS_PER_PALLET
    PALLETS_PER_TRUCK = constants.PALLETS_PER_TRUCK

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
        self.routes = routes  # Will be expanded below
        self.products = products
        self.products_dict = products
        self.truck_schedules = truck_schedules or []

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
        self.inventory_snapshot_date = inventory_snapshot_date  # Store for shelf life calculations

        # CRITICAL FIX: Expand intermediate stops and build truck-day mapping
        # This fixes two bugs:
        # 1. Lineage not receiving goods (intermediate stop ignored)
        # 2. Trucks running on wrong days (day-of-week not enforced)
        if self.truck_schedules:
            # Expand routes to include intermediate stop legs FIRST
            self.routes = self._expand_intermediate_stop_routes()

            # CRITICAL: Add intermediate stops as proper nodes
            # Without this, inventory variables aren't created for intermediate stops!
            self._add_intermediate_stop_nodes()

            # FAIL-FAST VALIDATION: Check truck schedules AFTER expansion
            from src.validation.truck_schedule_validator import validate_truck_schedules
            is_valid, validation_issues = validate_truck_schedules(
                self.truck_schedules, self.routes, self.nodes
            )

            # Log warnings and errors
            for issue in validation_issues:
                if issue.severity == 'error':
                    print(f"  ❌ ERROR: {issue.message}")
                elif issue.severity == 'warning':
                    print(f"  ⚠️  WARNING: {issue.message}")

            if not is_valid:
                error_messages = [issue.message for issue in validation_issues if issue.severity == 'error']
                raise ValueError(
                    f"Truck schedule validation failed:\n" + "\n".join(f"  - {msg}" for msg in error_messages)
                )

            # Build mapping of which routes can run on which days
            self.truck_route_days = self._build_truck_route_day_mapping()

            # VALIDATION: Warn about first-day arrival gaps
            self._validate_first_day_arrivals()
        else:
            self.truck_route_days = {}

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

        print(f"\nPreprocessing initial inventory:")
        print(f"  Input keys sample: {list(initial_inventory.keys())[:3]}")
        print(f"  Input entry count: {len(initial_inventory)}")

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
        print(f"  Converted keys sample: {list(converted.keys())[:3]}")
        print(f"  Converted entry count: {len(converted)}")
        print(f"  Total quantity: {sum(converted.values()):,.0f} units")

        # DIAGNOSTIC: Check if any initial inventory has states that don't match node capabilities
        print(f"\nValidating initial inventory against node capabilities:")
        issues = []
        product_mismatches = []
        for (node_id, prod, state), qty in converted.items():
            node = self.nodes.get(node_id)
            if not node:
                issues.append(f"  ❌ ({node_id}, {prod[:30]}, {state}): Node not found!")
                continue

            # Check if product exists in products dict
            if prod not in self.products:
                product_mismatches.append(f"  ❌ ({node_id}, {prod[:30]}, {state}): Product not in model.products!")
                continue

            # Check if this state is valid for this node
            valid_states = []
            if node.supports_frozen_storage():
                valid_states.append('frozen')
            if node.supports_ambient_storage() or node.has_demand_capability():
                valid_states.extend(['ambient', 'thawed'])

            if state not in valid_states:
                issues.append(f"  ❌ ({node_id}, {prod[:30]}, {state}): Node doesn't support this state! Valid: {valid_states}")

        if product_mismatches:
            print(f"  Found {len(product_mismatches)} product ID mismatches:")
            for issue in product_mismatches[:10]:
                print(issue)
            print(f"  Available products: {list(self.products.keys())[:5]}...")

            # FAIL FAST: Product ID mismatches will cause incorrect results!
            # Initial inventory won't be used, leading to excessive production or shortages
            raise ValueError(
                f"\n{'='*80}\n"
                f"PRODUCT ID MISMATCH ERROR\n"
                f"{'='*80}\n"
                f"Found {len(product_mismatches)} inventory entries with product IDs that don't match model products.\n"
                f"\n"
                f"This will cause:\n"
                f"  - Initial inventory to be ignored\n"
                f"  - Incorrect production planning\n"
                f"  - Wrong shortage calculations\n"
                f"\n"
                f"Solution:\n"
                f"  1. Use validation architecture: load_validated_data() automatically resolves product IDs\n"
                f"  2. Or ensure inventory file uses same product IDs as forecast\n"
                f"  3. Or add Alias sheet to Excel file for automatic mapping\n"
                f"\n"
                f"Inventory uses: {list(set(k[1] for k in initial_inventory.keys()))[:5]}\n"
                f"Forecast uses: {list(self.products.keys())[:5]}\n"
                f"{'='*80}\n"
            )

        if issues:
            print(f"  Found {len(issues)} incompatible state assignments:")
            for issue in issues[:10]:  # Show first 10
                print(issue)
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more")

            # FAIL FAST: Incompatible states will cause constraint errors
            raise ValueError(
                f"\n{'='*80}\n"
                f"STATE COMPATIBILITY ERROR\n"
                f"{'='*80}\n"
                f"Found {len(issues)} inventory entries with incompatible storage states.\n"
                f"Nodes don't support the states specified in initial inventory.\n"
                f"{'='*80}\n"
            )

        print(f"  ✓ All {len(converted)} entries have compatible states and products")

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

        # DIAGNOSTIC: Log routes from Lineage
        lineage_routes_from = self.routes_from_node.get("Lineage", [])
        lineage_routes_to = self.routes_to_node.get("Lineage", [])
        print(f"  Routes FROM Lineage: {len(lineage_routes_from)}")
        if lineage_routes_from:
            for route in lineage_routes_from:
                print(f"    - Lineage → {route.destination_node_id} (mode={route.transport_mode}, days={route.transit_days})")
        print(f"  Routes TO Lineage: {len(lineage_routes_to)}")
        if lineage_routes_to:
            for route in lineage_routes_to:
                print(f"    - {route.origin_node_id} → Lineage (mode={route.transport_mode}, days={route.transit_days})")

    def _expand_intermediate_stop_routes(self) -> List[UnifiedRoute]:
        """Expand truck routes to include intermediate stop destinations.

        For trucks with intermediate stops (e.g., 6122 → Lineage → 6125),
        the truck can deliver to BOTH Lineage and 6125 on the same trip.

        We need to create routes: origin → each intermediate stop
        We DO NOT create intermediate_stop → final_destination (goods stay on truck)

        Example: Wednesday truck (6122 → Lineage → 6125)
        Creates: 6122 → Lineage route (drop-off at intermediate stop)
        Does NOT create: Lineage → 6125 (goods continue on same truck)

        Returns:
            Extended route list with intermediate stop destinations added
        """
        from src.models.unified_route import TransportMode

        extended_routes = self.routes.copy()
        routes_added = []

        if not self.truck_schedules:
            return extended_routes

        for truck in self.truck_schedules:
            if not truck.intermediate_stops:
                continue

            # Create routes: origin → each intermediate stop (drop-off points)
            # The truck can deliver to intermediate stop AND continue to final destination
            origin = truck.origin_node_id

            for stop in truck.intermediate_stops:
                # Check if route already exists
                route_key = (origin, stop)
                existing = any(r for r in extended_routes
                              if r.origin_node_id == origin and r.destination_node_id == stop)

                if existing:
                    continue  # Route already exists

                # Create new route: origin → intermediate_stop
                # Goods delivered here stay at intermediate stop (don't continue)
                new_route = UnifiedRoute(
                    id=f"ROUTE_{origin}_to_{stop}_drop_off",
                    origin_node_id=origin,
                    destination_node_id=stop,
                    transit_days=1.0,  # Same-day delivery for intermediate stops
                    transport_mode=TransportMode.AMBIENT,  # Will transform at destination
                    cost_per_unit=0.0  # No additional cost (included in truck)
                )

                extended_routes.append(new_route)
                routes_added.append(f"{origin} → {stop} (drop-off)")

        if routes_added:
            print(f"\n  Expanded {len(routes_added)} intermediate stop routes:")
            for route_str in routes_added:
                print(f"    + {route_str}")

        return extended_routes

    def _add_intermediate_stop_nodes(self):
        """Add intermediate stops as proper nodes in the model.

        Intermediate stops (like Lineage) are referenced in routes but may not exist
        in the nodes dict. This causes inventory variables to NOT be created for them,
        leading to constraint errors.

        This method scans all intermediate stops and adds them as frozen storage nodes.
        """
        from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode

        nodes_added = []

        for truck in self.truck_schedules:
            if not truck.intermediate_stops:
                continue

            for stop_id in truck.intermediate_stops:
                if stop_id in self.nodes:
                    continue  # Node already exists

                # Create intermediate stop as frozen storage node
                # (Lineage receives ambient goods and freezes them on arrival)
                node = UnifiedNode(
                    id=stop_id,
                    name=f"{stop_id} (Intermediate Stop)",
                    type='storage',  # Storage-only node
                    capabilities=NodeCapabilities(
                        can_store=True,
                        can_produce=False,
                        can_receive_demand=False,
                        storage_mode=StorageMode.FROZEN,  # Frozen storage
                        max_storage_pallets=None,  # Unlimited capacity
                        production_rate_per_hour=None,
                        daily_startup_hours=None,
                        daily_shutdown_hours=None,
                        default_changeover_hours=None,
                    ),
                    demand_location_ids=[],  # No demand
                    products=list(self.products.keys())  # Can store all products
                )

                self.nodes[stop_id] = node
                self.nodes_list.append(node)
                nodes_added.append(stop_id)

        if nodes_added:
            print(f"\n  ✓ Added {len(nodes_added)} intermediate stop nodes:")
            for node_id in nodes_added:
                print(f"    + {node_id} (frozen storage)")
        else:
            print(f"  ℹ No intermediate stop nodes added")

    def _build_truck_route_day_mapping(self) -> Dict[Tuple[str, str], Set[str]]:
        """Build mapping of which routes can be used on which days.

        Returns:
            Dict[(origin_id, dest_id), Set[day_of_week_name]]

        Example:
            {('6122', '6125'): {'monday', 'tuesday', 'wednesday', 'thursday', 'friday'},
             ('6122', '6104'): {'monday', 'wednesday', 'friday'},
             ('6122', '6110'): {'tuesday', 'thursday'},
             ('6122', 'Lineage'): {'wednesday'}}
        """
        truck_route_days = {}

        if not self.truck_schedules:
            # No truck schedules - all routes available every day
            return {}

        day_map = {
            0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday',
            4: 'friday', 5: 'saturday', 6: 'sunday'
        }

        for truck in self.truck_schedules:
            # This truck can deliver to:
            # 1. Final destination (origin → destination)
            # 2. Intermediate stops (origin → stop) - drop-offs

            origin = truck.origin_node_id
            destinations = [truck.destination_node_id]

            # Add intermediate stops as drop-off destinations
            if truck.intermediate_stops:
                destinations = truck.intermediate_stops + [truck.destination_node_id]

            # Create route entries for origin → each destination
            for dest in destinations:
                route_key = (origin, dest)

                if route_key not in truck_route_days:
                    truck_route_days[route_key] = set()

                if truck.day_of_week:
                    # Specific day only
                    day_str = truck.day_of_week.value if hasattr(truck.day_of_week, 'value') else str(truck.day_of_week)
                    truck_route_days[route_key].add(day_str.lower())
                else:
                    # Runs every day
                    truck_route_days[route_key].update(day_map.values())

        return truck_route_days

    def _validate_first_day_arrivals(self):
        """Validate that first-day arrivals are properly handled in initial inventory.

        Goods arriving on day 1 of planning horizon must have departed before horizon start.
        Since we don't model pre-horizon decisions, these goods should be in initial_inventory.

        This validation warns when routes have short transit times and destinations
        may be missing in-transit goods from their initial inventory.
        """
        if not self.routes or not self.dates:
            return

        first_date = min(self.dates)
        warnings = []

        for route in self.routes:
            # Check if goods could arrive on first day
            if route.transit_days <= 0:
                continue

            # Departure needed for first-day arrival
            needed_departure = first_date - timedelta(days=route.transit_days)

            # If departure is before horizon, arrivals come from initial inventory
            if needed_departure < first_date:
                dest_id = route.destination_node_id

                # Check if destination has initial inventory
                has_init_inv = any(
                    key[0] == dest_id
                    for key in self.initial_inventory.keys()
                )

                # Special warning for critical nodes
                if dest_id in ['Lineage', '6130'] and not has_init_inv:
                    warnings.append(
                        f"⚠️  Route {route.origin_node_id} → {dest_id} ({route.transit_days}d transit): "
                        f"Goods arriving on {first_date} departed {needed_departure} (before horizon). "
                        f"Should be in initial inventory at {dest_id}."
                    )

        if warnings:
            print(f"\n  First-day arrival validation:")
            for warning in warnings:
                print(f"    {warning}")

    def build_model(self) -> ConcreteModel:
        """Build the Pyomo optimization model.

        Returns:
            Pyomo ConcreteModel ready to solve
        """
        from ..utils.version import GIT_COMMIT
        print("\n" + "="*80)
        print(f"BUILDING SLIDING WINDOW MODEL [git:{GIT_COMMIT}]")
        print("="*80)

        model = ConcreteModel()

        # Define sets
        model.nodes = PyomoSet(initialize=list(self.nodes.keys()))
        model.products = PyomoSet(initialize=list(self.products.keys()))
        model.dates = PyomoSet(initialize=self.dates, ordered=True)
        model.states = PyomoSet(initialize=['ambient', 'frozen', 'thawed'])

        print(f"\nSets defined:")
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

        print(f"\nModel built successfully")
        return model

    def _add_variables(self, model: ConcreteModel):
        """Add decision variables to model."""
        print(f"\nAdding variables...")

        # PRODUCTION VARIABLES (same as cohort model)
        # production[node, product, t] - continuous quantity
        production_index = [
            (node.id, prod, t)
            for node in self.manufacturing_nodes
            for prod in model.products
            for t in model.dates
        ]
        # MIP Performance: Add explicit upper bound (validated via A/B test)
        # Production bounded by max daily capacity: 1400 units/hr × 14 hrs = 19600
        model.production = Var(
            production_index,
            within=NonNegativeReals,
            bounds=(0, 19600),
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
                        # Ambient inventory for all ambient-capable nodes
                        inventory_index.append((node_id, prod, 'ambient', t))

                        # Thawed inventory ONLY for nodes that can receive frozen goods and thaw them
                        # Typically: nodes that receive from frozen routes (like 6130 from Lineage)
                        # Don't create for pure ambient nodes like manufacturing
                        # Don't create for frozen-only nodes like Lineage (they can't thaw!)
                        has_frozen_inbound = any(
                            r.destination_node_id == node_id and r.transport_mode == TransportMode.FROZEN
                            for r in self.routes
                        )
                        # FIX (2025-11-08): Match thaw flow logic (line 753)
                        # Frozen-only nodes (Lineage) should NOT have thawed inventory
                        # Must be able to hold frozen AND use ambient/thawed
                        can_thaw = node.supports_frozen_storage() and (
                            node.supports_ambient_storage() or node.has_demand_capability()
                        )

                        if has_frozen_inbound or can_thaw:
                            inventory_index.append((node_id, prod, 'thawed', t))

                            # DIAGNOSTIC (2025-11-05): Verify 6130 gets thawed vars
                            if node_id == '6130' and prod == list(model.products)[0] and t == list(model.dates)[0]:
                                print(f"  DEBUG: Creating thawed inventory var for 6130 (has_frozen_inbound={has_frozen_inbound})")

        # MIP Performance: Add explicit upper bound (validated via A/B test)
        # Inventory bounded by storage capacity: 62 pallets × 320 units = 19840
        model.inventory = Var(
            inventory_index,
            within=NonNegativeReals,
            bounds=(0, 19840),
            doc="End-of-day inventory by node, product, state, date"
        )
        print(f"  Inventory variables: {len(inventory_index)}")

        # DIAGNOSTIC: Check if inventory variables exist for initial inventory entries
        if self.initial_inventory:
            print(f"  Checking inventory variables for initial_inventory entries:")
            for (node_id, prod, state), qty in list(self.initial_inventory.items())[:5]:
                first_date = min(model.dates)
                key = (node_id, prod, state, first_date)
                exists = key in inventory_index
                print(f"    {key}: exists={exists}, qty={qty:.0f}")

        # STATE TRANSITION VARIABLES (NEW - enables freeze/thaw flows)
        # Only create where transitions make sense!

        # Thaw: frozen → thawed (only for nodes that can BOTH hold frozen AND use ambient/thawed)
        # CRITICAL FIX: Frozen-only nodes (like Lineage) cannot thaw - they only ship frozen!
        # Ambient-only nodes receiving frozen shipments: thaw happens automatically on arrival (no thaw variable)
        thaw_index = [
            (node_id, prod, t)
            for node_id, node in self.nodes.items()
            # Can only thaw if node has frozen storage AND can use ambient/thawed inventory
            if node.supports_frozen_storage() and (node.supports_ambient_storage() or node.has_demand_capability())
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

        # IN-TRANSIT VARIABLES: Only for departures WITHIN planning horizon
        # First-day arrivals from pre-horizon departures are NOT modeled as variables
        # (You can't decide to ship goods before planning starts!)
        # Any goods in-transit at start should be in initial_inventory at destination
        #
        # CRITICAL FIX (2025-11-04): Enforce truck day-of-week restrictions
        # Only create variables for route-day combinations where a truck actually runs
        in_transit_index = []
        skipped_no_truck_days = 0

        day_of_week_map = {
            0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday',
            4: 'friday', 5: 'saturday', 6: 'sunday'
        }

        for route in self.routes:
            route_key = (route.origin_node_id, route.destination_node_id)
            valid_days = self.truck_route_days.get(route_key, set())

            # If no truck schedule for this route, allow any day (backwards compatibility)
            has_truck_schedule = len(valid_days) > 0

            for prod in model.products:
                # Create in-transit variables for planning horizon departures
                for departure_date in model.dates:
                    # CRITICAL: Check if truck runs on this day of week
                    if has_truck_schedule:
                        day_name = day_of_week_map[departure_date.weekday()]
                        if day_name not in valid_days:
                            # No truck on this day for this route - skip variable
                            skipped_no_truck_days += 2  # 2 states
                            continue

                    # In-transit can be in frozen or ambient state
                    for state in ['frozen', 'ambient']:
                        in_transit_index.append((
                            route.origin_node_id,
                            route.destination_node_id,
                            prod,
                            departure_date,  # Indexed by DEPARTURE (planning horizon only)
                            state
                        ))

        # FLOW DECOMPOSITION: Separate init_inv shipments from new production shipments
        model.shipment_from_init = Var(
            in_transit_index,
            within=NonNegativeReals,
            doc="Shipments sourced from initial inventory"
        )

        model.shipment_from_new = Var(
            in_transit_index,
            within=NonNegativeReals,
            doc="Shipments sourced from new production/arrivals"
        )

        # Total in_transit (for material balance compatibility)
        # MIP Performance: Add explicit upper bound (validated via A/B test)
        # In-transit bounded by truck capacity: 44 pallets × 320 units = 14080
        model.in_transit = Var(
            in_transit_index,
            within=NonNegativeReals,
            bounds=(0, 14080),
            doc="Total in-transit (init + new)"
        )

        print(f"  In-transit variables (decomposed): {len(in_transit_index)} × 3 (total, from_init, from_new) = {len(in_transit_index) * 3}")
        if skipped_no_truck_days > 0:
            print(f"    Skipped {skipped_no_truck_days} invalid route-day combinations (day-of-week enforcement)")

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
        # CRITICAL FIX (2025-11-05): Partition consumption by source state
        # Bug #2: Using single demand_consumed variable in BOTH ambient and thawed balances
        # caused double-counting (same consumption subtracted from both states!)
        #
        # Correct MIP formulation:
        #   - demand_consumed_from_ambient: consumption from ambient inventory
        #   - demand_consumed_from_thawed: consumption from thawed inventory
        #   - Total consumption = consumed_ambient + consumed_thawed
        #   - Each balance subtracts only its own consumption (no double-counting)
        demand_keys = list(self.demand.keys())

        # FLOW DECOMPOSITION (2025-11-14): Separate init_inv flows from new flows
        # This allows sliding windows to constrain "new" flows only, avoiding phantom inventory

        # Decomposed ambient consumption
        model.consumption_from_init_ambient = Var(
            demand_keys,
            within=NonNegativeReals,
            doc="Demand consumed from initial inventory (ambient)"
        )

        model.consumption_from_new_ambient = Var(
            demand_keys,
            within=NonNegativeReals,
            doc="Demand consumed from new production/arrivals (ambient)"
        )

        # Total ambient consumption (for material balance compatibility)
        model.demand_consumed_from_ambient = Var(
            demand_keys,
            within=NonNegativeReals,
            doc="Total demand consumed from ambient (init + new)"
        )

        # Decomposed thawed consumption
        model.consumption_from_init_thawed = Var(
            demand_keys,
            within=NonNegativeReals,
            doc="Demand consumed from initial inventory (thawed)"
        )

        model.consumption_from_new_thawed = Var(
            demand_keys,
            within=NonNegativeReals,
            doc="Demand consumed from new arrivals (thawed)"
        )

        # Total thawed consumption (for material balance compatibility)
        model.demand_consumed_from_thawed = Var(
            demand_keys,
            within=NonNegativeReals,
            doc="Total demand consumed from thawed (init + new)"
        )

        print(f"  Demand consumed variables (decomposed): {len(demand_keys)} × 2 states × 3 (total, from_init, from_new) = {len(demand_keys) * 6}")

        # SHORTAGE VARIABLES (if allowed)
        if self.allow_shortages:
            model.shortage = Var(
                demand_keys,
                within=NonNegativeReals,
                doc="Unmet demand with penalty"
            )
            print(f"  Shortage variables: {len(demand_keys)}")

        # DISPOSAL VARIABLES (for expired initial inventory)
        # MIP Technique: Add slack variables to handle expired inventory that can't be shipped/consumed
        # CRITICAL FIX: Only allow disposal when initial inventory has ACTUALLY EXPIRED
        # This prevents the model from disposing fresh inventory to avoid production costs
        if self.initial_inventory and self.inventory_snapshot_date:
            disposal_index = []
            disposal_details = []  # For diagnostic output

            for (node_id, prod, state) in self.initial_inventory.keys():
                if self.initial_inventory[(node_id, prod, state)] > 0:
                    # Determine shelf life for this state
                    if state == 'ambient':
                        shelf_life = 17
                    elif state == 'frozen':
                        shelf_life = 120
                    elif state == 'thawed':
                        shelf_life = 14
                    else:
                        continue  # Unknown state, skip

                    # Calculate expiration date (when inventory age exceeds shelf life)
                    # For 17-day ambient: ages 0-16 valid, age 17+ expired
                    expiration_date = self.inventory_snapshot_date + timedelta(days=shelf_life)

                    # Only create disposal variable for dates AT OR AFTER expiration
                    # Before expiration, inventory must flow through normal channels
                    disposal_count_for_item = 0
                    for t in model.dates:
                        if t >= expiration_date:
                            disposal_index.append((node_id, prod, state, t))
                            disposal_count_for_item += 1

                    if disposal_count_for_item > 0:
                        disposal_details.append(
                            f"{node_id}/{state[:3]}: expires {expiration_date}, {disposal_count_for_item} disposal dates"
                        )

            if disposal_index:
                model.disposal = Var(
                    disposal_index,
                    within=NonNegativeReals,
                    doc="Disposal of expired initial inventory (only after expiration date)"
                )
                print(f"  Disposal variables: {len(disposal_index)} (only for expired inventory)")
                if disposal_details and len(disposal_details) <= 10:
                    print(f"  Disposal details (sample):")
                    for detail in disposal_details[:10]:
                        print(f"    - {detail}")
                elif disposal_details:
                    print(f"  Disposal for {len(disposal_details)} inventory items")
            else:
                print(f"  No disposal variables needed (no initial inventory expires within horizon)")

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

        # CHANGEOVER OVERHEAD OPTIMIZATION: Pre-aggregated variables
        # Instead of inline sums in overhead calculation, pre-compute totals
        # This reduces constraint complexity from 2N binaries to 1 binary + 1 integer
        changeover_agg_index = [(node.id, t) for node in self.manufacturing_nodes for t in model.dates]

        model.total_starts = Var(
            changeover_agg_index,
            within=NonNegativeIntegers,
            bounds=(0, len(model.products)),
            doc="Total product starts on date (optimization: pre-aggregated sum)"
        )

        model.any_production = Var(
            changeover_agg_index,
            within=Binary,
            doc="1 if any production on date (optimization: replaces sum check)"
        )

        print(f"  Changeover aggregation variables: {len(changeover_agg_index) * 2} (overhead optimization)")

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

        # Labor hours paid (for 4-hour minimum on weekends/holidays)
        # paid_hours >= used_hours (always pay for time worked)
        # paid_hours >= 4 × any_production (4-hour minimum if producing on non-fixed day)
        model.labor_hours_paid = Var(
            labor_index,
            within=NonNegativeReals,
            doc="Labor hours paid (includes 4-hour minimum on weekends/holidays)"
        )

        print(f"  Labor variables: {len(labor_index)} (used + paid + overtime)")

        # Mix count variables (integer production batches)
        mix_index = []
        for node in self.manufacturing_nodes:
            for prod_id, product in self.products.items():
                if hasattr(product, 'units_per_mix') and product.units_per_mix > 0:
                    for t in model.dates:
                        mix_index.append((node.id, prod_id, t))

        if mix_index:
            # Calculate max mixes per product based on daily capacity
            # MIP Performance Optimization (2025-11-25): Bounded integers improve B&B
            max_daily_hours = 14  # Max hours per day (12 fixed + 2 OT)
            default_production_rate = 1400  # units/hour
            max_daily_units = default_production_rate * max_daily_hours  # 19,600 units

            # Build bounds dictionary: max_mixes = max_daily_units / units_per_mix
            mix_bounds = {}
            for (node_id, prod_id, t) in mix_index:
                product = self.products.get(prod_id)
                if product and hasattr(product, 'units_per_mix') and product.units_per_mix > 0:
                    max_mixes = int(max_daily_units / product.units_per_mix) + 1
                else:
                    max_mixes = 100  # Fallback for products without units_per_mix
                mix_bounds[(node_id, prod_id, t)] = (0, max_mixes)

            model.mix_count = Var(
                mix_index,
                within=NonNegativeIntegers,
                bounds=lambda m, n, p, t: mix_bounds.get((n, p, t), (0, 100)),
                doc="Number of production mixes (batches)"
            )
            print(f"  Mix count variables: {len(mix_index)} integers (bounded)")

        print(f"\nVariables created")
        total_vars = (len(production_index) + len(inventory_index) +
                     len(thaw_index) + len(freeze_index) + len(in_transit_index))
        total_integers = len(pallet_index) if self.use_pallet_tracking else 0
        total_binaries = len(product_produced_index) * 2
        print(f"  Continuous: {total_vars:,}")
        print(f"  Integers: {total_integers:,}")
        print(f"  Binaries: {total_binaries:,}")
        print(f"  TOTAL: {total_vars + total_integers + total_binaries:,}")
        print(f"  (vs cohort model: ~500,000 total)")


    def _add_constraints(self, model: ConcreteModel):
        """Add constraints to model."""
        print(f"\nAdding constraints...")

        # Core constraints
        self._add_consumption_decomposition(model)
        self._add_sliding_window_shelf_life(model)
        self._add_init_inv_outflow_bounds(model)
        self._add_state_balance(model)
        self._add_demand_satisfaction(model)
        self._add_pallet_constraints(model)
        self._add_production_constraints(model)
        self._add_changeover_detection(model)
        self._add_truck_constraints(model)

        print(f"\nConstraints added")

        # ====================================================================
        # DIAGNOSTIC: Check model structure to debug zero production
        # ====================================================================
        print("\n" + "="*80)
        print("MODEL STRUCTURE DIAGNOSTIC")
        print("="*80)

        # Check production variables at manufacturing node
        mfg_nodes = [n for n in self.nodes.keys() if self.nodes[n].can_produce()]
        if mfg_nodes:
            mfg_id = mfg_nodes[0]  # Usually '6122'
            mfg_prod_vars = [(n, p, t) for (n, p, t) in model.production if n == mfg_id]
            print(f"\nProduction variables at {mfg_id}: {len(mfg_prod_vars)}")
            if mfg_prod_vars:
                print(f"  Sample: {mfg_prod_vars[0]}")
            else:
                print(f"  ❌ NO PRODUCTION VARIABLES AT {mfg_id}!")

            # Check material balance constraints at manufacturing
            if hasattr(model, 'ambient_balance_con'):
                mfg_balance = [k for k in model.ambient_balance_con if k[0] == mfg_id]
                print(f"Ambient balance constraints at {mfg_id}: {len(mfg_balance)}")
                if not mfg_balance:
                    print(f"  ❌ NO MATERIAL BALANCE AT {mfg_id}!")
            else:
                print(f"  ❌ ambient_balance_con DOES NOT EXIST!")

            # Check in_transit variables FROM manufacturing
            if hasattr(model, 'in_transit'):
                intransit_from_mfg = [(o,d,p,t,s) for (o,d,p,t,s) in model.in_transit if o == mfg_id]
                print(f"In-transit variables FROM {mfg_id}: {len(intransit_from_mfg)}")
                if intransit_from_mfg:
                    print(f"  Sample: {intransit_from_mfg[0]}")
                else:
                    print(f"  ❌ NO IN_TRANSIT FROM {mfg_id}!")
            else:
                print(f"  ❌ in_transit DOES NOT EXIST!")

        # Check demand_consumed variables
        if hasattr(model, 'demand_consumed'):
            print(f"\nDemand_consumed variables: {len(model.demand_consumed)}")
            sample = list(model.demand_consumed.keys())[:3]
            if sample:
                print(f"  Sample: {sample}")
        else:
            print(f"\n❌ demand_consumed DOES NOT EXIST!")

        # Check sliding window constraints
        if hasattr(model, 'ambient_shelf_life_con'):
            mfg_sliding = [k for k in model.ambient_shelf_life_con if k[0] == mfg_id] if mfg_nodes else []
            print(f"\nSliding window constraints at {mfg_nodes[0] if mfg_nodes else 'N/A'}: {len(mfg_sliding)}")

        print(f"\nOverall model:")
        print(f"  Total variables: {model.nvariables():,}")
        print(f"  Total constraints: {model.nconstraints():,}")

        print("="*80 + "\n")
        # ====================================================================

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

            # DIAGNOSTIC: Log window on day 18
            date_list = list(model.dates)
            if len(date_list) > 17 and t == date_list[17]:  # Day 18 (index 17)
                init_inv_check = self.initial_inventory.get((node_id, prod, 'ambient'), 0)
                if init_inv_check > 1000:
                    first_date = min(model.dates)
                    days_from_start = (t - first_date).days
                    print(f"  DAY 18 ambient_shelf_life[{node_id}, {prod[:30]}]:")
                    print(f"    Window: {window_dates[0]} to {window_dates[-1]} ({len(window_dates)} days)")
                    print(f"    days_from_start: {days_from_start}")
                    print(f"    Condition (<=16): {days_from_start <= 16}")
                    print(f"    Init_inv in Q: {'YES' if days_from_start <= 16 else 'NO'}")

            # Inflows to ambient: initial_inv (if start date in window) + production + thaw + arrivals
            Q_ambient = 0

            # CRITICAL FIX: Initial inventory should only be counted ONCE
            # It should be included ONLY when the window includes Day 1 (planning start)
            # NOT on every day where age <= 16!
            #
            # WRONG (old): Add init_inv to Q on every day where age <= 16
            # RIGHT (new): Add init_inv to Q only when window includes first planning day
            #
            # REMOVED (2025-11-10): Initial inventory should NOT be added to sliding window Q
            #
            # Root cause of performance regression (fe85d03):
            # - Adding init_inv to Q on every day where window includes Day 1 (17 days!)
            # - Created phantom inventory: 6,180 × 17 = 105,060 units
            # - Massively overconstrained model (4× slower, zero production)
            #
            # Why removal is correct:
            # - Material balance (line 1714) already handles init_inv via prev_inv
            # - Sliding windows enforce shelf life on FLOWS (production, arrivals)
            # - Initial inventory is a STOCK, not a recurring FLOW
            # - Adding to Q treats it as fresh inflow on 17 different days (wrong!)
            #
            # Mathematical proof: See optimization-solver agent analysis (2025-11-10)

            for tau in window_dates:
                # Production that goes to ambient
                if node.can_produce() and (node_id, prod, tau) in model.production:
                    if node.get_production_state() == 'ambient':
                        Q_ambient += model.production[node_id, prod, tau]

                # Thaw flow
                if (node_id, prod, tau) in model.thaw:
                    Q_ambient += model.thaw[node_id, prod, tau]

                # Arrivals in ambient state (goods that departed earlier and arrive on tau)
                for route in self.routes_to_node[node_id]:
                    arrival_state = self._determine_arrival_state(route, node)
                    if arrival_state == 'ambient':
                        # Calculate departure date: goods must have left (tau - transit_days) to arrive on tau
                        # Only include if departure is within planning horizon
                        departure_date = tau - timedelta(days=route.transit_days)
                        if departure_date in model.dates and (route.origin_node_id, node_id, prod, departure_date, 'ambient') in model.in_transit:
                            Q_ambient += model.in_transit[route.origin_node_id, node_id, prod, departure_date, 'ambient']

            # Outflows from ambient: shipments FROM NEW + freeze + consumption FROM NEW
            # FLOW DECOMPOSITION (2025-11-14): Use from_new variables only
            # Init_inv flows are NOT subject to sliding window (separate bounds)
            O_ambient = 0
            for tau in window_dates:
                # Departures in ambient state - use shipment_from_new only
                for route in self.routes_from_node[node_id]:
                    if route.transport_mode != TransportMode.FROZEN:  # Ambient route
                        # Goods departing on tau - decomposed to exclude init_inv shipments
                        if (node_id, route.destination_node_id, prod, tau, 'ambient') in model.shipment_from_new:
                            O_ambient += model.shipment_from_new[node_id, route.destination_node_id, prod, tau, 'ambient']

                # Freeze flow
                if (node_id, prod, tau) in model.freeze:
                    O_ambient += model.freeze[node_id, prod, tau]

                # FLOW DECOMPOSITION: Use consumption_from_new (not total)
                # This ensures sliding window only constrains "new" flows
                # Init_inv consumption handled by separate bounds (no phantom inventory)
                if node.has_demand_capability() and (node_id, prod, tau) in model.consumption_from_new_ambient:
                    O_ambient += model.consumption_from_new_ambient[node_id, prod, tau]

            # Skip if no activity to avoid trivial True constraint
            # Check if both are constants (not Pyomo expressions)
            try:
                # If both are numeric constants
                if isinstance(Q_ambient, (int, float)) and isinstance(O_ambient, (int, float)):
                    if Q_ambient == 0 and O_ambient == 0:
                        return Constraint.Skip
                    # If both constants and constraint holds, skip to avoid "True" error
                    if O_ambient <= Q_ambient:
                        return Constraint.Feasible
            except:
                pass  # Pyomo expressions - let them through

            # DIAGNOSTIC: Log day 2 constraint for nodes with initial inventory
            if self.initial_inventory.get((node_id, prod, 'ambient'), 0) > 0:
                date_list = list(model.dates)
                if len(date_list) >= 2 and t == date_list[1]:  # Day 2
                    print(f"  DAY2 ambient_shelf_life[{node_id}, {prod[:30]}]:")
                    print(f"    Window: {len(window_dates)} days")
                    print(f"    Q (should NOT include init_inv): {Q_ambient}")
                    print(f"    O: {O_ambient}")

            # CRITICAL FIX (2025-11-03): Correct sliding window formulation
            # WRONG (causes infeasibility): inventory[t] <= Q - O
            #   - Compares cumulative inventory to window net flow
            #   - Ignores carryover from before window
            #   - Makes model infeasible when inventory includes pre-window stock
            #
            # CORRECT (standard perishables formulation): O <= Q
            #   - Outflows in window cannot exceed inflows in window
            #   - Prevents using inventory older than L days
            #   - Material balance handles actual inventory levels
            #   - Structurally prevents old inventory use (can't ship what didn't arrive in window)
            return O_ambient <= Q_ambient

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

            # Inflows to frozen: initial_inv (if start date in window) + production_frozen + freeze + arrivals_frozen
            Q_frozen = 0

            # CRITICAL FIX: Initial inventory should only be counted ONCE
            # Include only when window includes Day 1 (where init_inv enters system)
            # REMOVED (2025-11-10): Initial inventory should NOT be added to Q
            # Same fix as ambient rule - prevents 120× phantom inventory for frozen state

            for tau in window_dates:
                # Production that goes to frozen
                if node.can_produce() and (node_id, prod, tau) in model.production:
                    if node.get_production_state() == 'frozen':
                        Q_frozen += model.production[node_id, prod, tau]

                # Freeze flow (ambient → frozen)
                if (node_id, prod, tau) in model.freeze:
                    Q_frozen += model.freeze[node_id, prod, tau]

                # Arrivals in frozen state
                for route in self.routes_to_node[node_id]:
                    arrival_state = self._determine_arrival_state(route, node)
                    if arrival_state == 'frozen':
                        departure_date = tau - timedelta(days=route.transit_days)
                        if departure_date in model.dates and (route.origin_node_id, node_id, prod, departure_date, 'frozen') in model.in_transit:
                            Q_frozen += model.in_transit[route.origin_node_id, node_id, prod, departure_date, 'frozen']

            # Outflows from frozen: departures FROM NEW + thaw
            # FLOW DECOMPOSITION (2025-11-14): Use shipment_from_new only
            O_frozen = 0
            for tau in window_dates:
                # Departures in frozen state - use shipment_from_new only
                for route in self.routes_from_node[node_id]:
                    if route.transport_mode == TransportMode.FROZEN:
                        if (node_id, route.destination_node_id, prod, tau, 'frozen') in model.shipment_from_new:
                            O_frozen += model.shipment_from_new[node_id, route.destination_node_id, prod, tau, 'frozen']

                # Thaw flow (frozen → ambient/thawed)
                if (node_id, prod, tau) in model.thaw:
                    O_frozen += model.thaw[node_id, prod, tau]

            # DIAGNOSTIC: Log Lineage constraint on day 1
            if node_id == "Lineage" and t == min(model.dates):
                try:
                    q_val = value(Q_frozen, exception=False)
                    o_val = value(O_frozen, exception=False)
                    if q_val is not None or o_val is not None:
                        print(f"    Q_frozen (inflows): {q_val if q_val is not None else Q_frozen}")
                        print(f"    O_frozen (outflows): {o_val if o_val is not None else O_frozen}")
                        print(f"    Shelf life bound: inventory <= {q_val - o_val if q_val and o_val else 'Q-O'}")
                except:
                    pass

            # Skip if no activity (avoids trivial True constraint)
            try:
                if isinstance(Q_frozen, (int, float)) and isinstance(O_frozen, (int, float)):
                    if Q_frozen == 0 and O_frozen == 0:
                        return Constraint.Skip
                    if O_frozen <= Q_frozen:
                        return Constraint.Feasible
            except:
                pass

            # CRITICAL FIX (2025-11-03): Correct sliding window formulation
            # Changed from: inventory[t] <= Q - O (causes infeasibility)
            # Changed to: O <= Q (standard perishables formulation)
            return O_frozen <= Q_frozen

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

            # Skip if no thawed inventory variable exists (most nodes don't have thawed state)
            if (node_id, prod, 'thawed', t) not in model.inventory:
                return Constraint.Skip

            # Window: last 14 days
            window_start = max(0, list(model.dates).index(t) - 13)
            window_dates = list(model.dates)[window_start:list(model.dates).index(t)+1]

            # Inflows to thawed: initial_inv (if start date in window) + thaw + arrivals_from_frozen_routes
            Q_thawed = 0

            # CRITICAL FIX: Initial inventory should only be counted ONCE
            # Include only when window includes Day 1 (where init_inv enters system)
            # REMOVED (2025-11-10): Initial inventory should NOT be added to Q
            # Same fix as ambient/frozen rules - prevents 14× phantom inventory for thawed state

            for tau in window_dates:
                # Thaw flow (frozen → thawed at this node)
                if (node_id, prod, tau) in model.thaw:
                    Q_thawed += model.thaw[node_id, prod, tau]

                # CRITICAL FIX: Arrivals from frozen routes (frozen goods arriving at ambient-only nodes)
                for route in self.routes_to_node[node_id]:
                    arrival_state = self._determine_arrival_state(route, node)
                    if arrival_state == 'thawed':
                        # Frozen goods shipped to this ambient-only node arrive as thawed
                        departure_date = tau - timedelta(days=route.transit_days)
                        if departure_date in model.dates and (route.origin_node_id, node_id, prod, departure_date, 'frozen') in model.in_transit:
                            Q_thawed += model.in_transit[route.origin_node_id, node_id, prod, departure_date, 'frozen']

            # Outflows from thawed: demand consumption FROM NEW
            # FLOW DECOMPOSITION (2025-11-14): Use consumption_from_new only
            # Init_inv consumption is NOT subject to sliding window (separate bounds)
            O_thawed = 0
            for tau in window_dates:
                if node.has_demand_capability() and (node_id, prod, tau) in model.consumption_from_new_thawed:
                    O_thawed += model.consumption_from_new_thawed[node_id, prod, tau]

            # Skip if no activity (avoids trivial True constraint)
            try:
                if isinstance(Q_thawed, (int, float)) and isinstance(O_thawed, (int, float)):
                    if Q_thawed == 0 and O_thawed == 0:
                        return Constraint.Skip
                    if O_thawed <= Q_thawed:
                        return Constraint.Feasible
            except:
                pass

            # CRITICAL FIX (2025-11-03): Correct sliding window formulation
            # Changed from: inventory[t] <= Q - O (causes infeasibility)
            # Changed to: O <= Q (standard perishables formulation)
            return O_thawed <= Q_thawed

        model.thawed_shelf_life_con = Constraint(
            [(n, p, t) for n, node in self.nodes.items()
             if node.supports_ambient_storage()
             for p in model.products for t in model.dates],
            rule=thawed_shelf_life_rule,
            doc="Thawed shelf life: 14-day sliding window (resets on thaw!)"
        )


        # INITIAL INVENTORY EXPIRATION CONSTRAINT
        # MIP Formulation: Conditional constraint to ensure initial inventory doesn't persist beyond shelf life
        # If initial inventory exists, it must be consumed before it reaches expiration age
        if self.initial_inventory and self.inventory_snapshot_date:
            def init_inv_expiration_rule(model, node_id, prod, state):
                """Force initial inventory to be consumed before it expires.

                MIP Technique: Conditional consumption constraint
                - If init_inv > 0, then inventory on expiration day must only contain fresh goods
                - On expiration day, aggregate inventory can only include goods produced within window
                """
                init_qty = self.initial_inventory.get((node_id, prod, state), 0)
                if init_qty <= 0:
                    return Constraint.Skip

                # Determine expiration age for this state
                if state == 'ambient':
                    shelf_life = 17
                elif state == 'frozen':
                    shelf_life = 120
                elif state == 'thawed':
                    shelf_life = 14
                else:
                    return Constraint.Skip

                # Find the first day when initial inventory reaches expiration age
                # Expiration occurs when age > (shelf_life - 1)
                # For 17-day shelf life: ages 0-16 valid, age 17+ expired
                expiration_age = shelf_life
                expiration_date = self.inventory_snapshot_date + timedelta(days=expiration_age)

                # Only add constraint if expiration date is AFTER planning end
                # (If expiration is within horizon, shelf life constraints already handle it)
                planning_end = max(model.dates)
                if expiration_date <= planning_end:
                    # Expiration is within planning horizon
                    # Constraint: On the LAST valid day (day before expiration), consume all init_inv
                    last_valid_date = expiration_date - timedelta(days=1)
                    if last_valid_date in model.dates:
                        # On last valid day, inventory can persist
                        # But on expiration day, it must be gone
                        # Since shelf life constraints handle this, skip
                        return Constraint.Skip

                return Constraint.Skip

            # Apply to all initial inventory entries
            init_inv_entries = [
                (node_id, prod, state)
                for (node_id, prod, state) in self.initial_inventory.keys()
                if self.initial_inventory[(node_id, prod, state)] > 0
            ]

            if init_inv_entries:
                model.init_inv_expiration_con = Constraint(
                    init_inv_entries,
                    rule=init_inv_expiration_rule,
                    doc="Force initial inventory consumption before expiration"
                )
                exp_count = sum(1 for _ in model.init_inv_expiration_con)
                if exp_count > 0:
                    print(f"  Initial inventory expiration constraints: {exp_count}")

        shelf_life_constraints = (
            len([n for n, node in self.nodes.items() if node.supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates)) +
            len([n for n, node in self.nodes.items() if node.supports_frozen_storage()]) * len(list(model.products)) * len(list(model.dates)) +
            len([n for n, node in self.nodes.items() if node.supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates))
        )
        print(f"  Shelf life window constraints: {shelf_life_constraints:,}")
        print(f"    Ambient (17d): ~{len([n for n in self.nodes if self.nodes[n].supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates)):,}")
        print(f"    Frozen (120d): ~{len([n for n in self.nodes if self.nodes[n].supports_frozen_storage()]) * len(list(model.products)) * len(list(model.dates)):,}")
        print(f"    Thawed (14d): ~{len([n for n in self.nodes if self.nodes[n].supports_ambient_storage()]) * len(list(model.products)) * len(list(model.dates)):,}")

    def _add_consumption_decomposition(self, model: ConcreteModel):
        """Decompose total flows (consumption + shipments) into init_inv and new components.

        Ensures:
        - total_consumption = consumption_from_init + consumption_from_new
        - total_shipment = shipment_from_init + shipment_from_new

        This allows sliding windows to constrain "new" flows only, avoiding phantom inventory.
        """
        print("\n  Adding flow decomposition constraints...")

        # CONSUMPTION DECOMPOSITION
        def ambient_consumption_decomp_rule(model, node_id, prod, t):
            """Total ambient consumption = from_init + from_new."""
            if (node_id, prod, t) not in model.demand_consumed_from_ambient:
                return Constraint.Skip

            total = model.demand_consumed_from_ambient[node_id, prod, t]
            from_init = model.consumption_from_init_ambient[node_id, prod, t]
            from_new = model.consumption_from_new_ambient[node_id, prod, t]

            return total == from_init + from_new

        def thawed_consumption_decomp_rule(model, node_id, prod, t):
            """Total thawed consumption = from_init + from_new."""
            if (node_id, prod, t) not in model.demand_consumed_from_thawed:
                return Constraint.Skip

            total = model.demand_consumed_from_thawed[node_id, prod, t]
            from_init = model.consumption_from_init_thawed[node_id, prod, t]
            from_new = model.consumption_from_new_thawed[node_id, prod, t]

            return total == from_init + from_new

        demand_keys = list(self.demand.keys())

        model.ambient_consumption_decomp = Constraint(
            demand_keys,
            rule=ambient_consumption_decomp_rule,
            doc="Decompose ambient consumption into init_inv and new flows"
        )

        model.thawed_consumption_decomp = Constraint(
            demand_keys,
            rule=thawed_consumption_decomp_rule,
            doc="Decompose thawed consumption into init_inv and new flows"
        )

        # SHIPMENT DECOMPOSITION
        def shipment_decomp_rule(model, origin, dest, prod, t, state):
            """Total shipment = from_init + from_new."""
            if (origin, dest, prod, t, state) not in model.in_transit:
                return Constraint.Skip

            total = model.in_transit[origin, dest, prod, t, state]
            from_init = model.shipment_from_init[origin, dest, prod, t, state]
            from_new = model.shipment_from_new[origin, dest, prod, t, state]

            return total == from_init + from_new

        # Get all in_transit keys
        transit_keys = [(o, d, p, t, s) for (o, d, p, t, s) in model.in_transit]

        model.shipment_decomp = Constraint(
            transit_keys,
            rule=shipment_decomp_rule,
            doc="Decompose shipments into init_inv and new flows"
        )

        print(f"    Flow decomposition constraints: {len(demand_keys) * 2} consumption + {len(transit_keys)} shipment")

    def _add_init_inv_outflow_bounds(self, model: ConcreteModel):
        """Bound consumption from init_inv to available quantities.

        Simple constraints: sum(from_init flows) <= init_inv_qty
        These enforce that we can't consume more init_inv than exists,
        without adding init_inv to the sliding window Q.
        """
        print("\n  Adding initial inventory outflow bounds...")

        def ambient_init_bound_rule(model, node_id, prod):
            """Total outflows (consumption + shipments) from init_inv <= available init_inv."""
            init_inv_qty = self.initial_inventory.get((node_id, prod, 'ambient'), 0)
            if init_inv_qty == 0:
                return Constraint.Skip

            # Sum ALL outflows from init over shelf life (17 days)
            shelf_life_days = 17
            shelf_life_dates = list(model.dates)[:min(shelf_life_days, len(model.dates))]

            # Consumption from init (for demand nodes)
            total_consumed_from_init = sum(
                model.consumption_from_init_ambient[node_id, prod, t]
                for t in shelf_life_dates
                if (node_id, prod, t) in model.consumption_from_init_ambient
            )

            # Shipments from init (for all nodes with outbound routes)
            total_shipped_from_init = sum(
                model.shipment_from_init[node_id, route.destination_node_id, prod, t, 'ambient']
                for t in shelf_life_dates
                for route in self.routes_from_node[node_id]
                if route.transport_mode != TransportMode.FROZEN
                and (node_id, route.destination_node_id, prod, t, 'ambient') in model.shipment_from_init
            )

            total_from_init = total_consumed_from_init + total_shipped_from_init

            # Skip if trivial (prevents "0 <= constant" → True)
            if isinstance(total_from_init, (int, float)) and total_from_init == 0:
                return Constraint.Skip

            return total_from_init <= init_inv_qty

        def thawed_init_bound_rule(model, node_id, prod):
            """Total consumption from init_inv <= available init_inv."""
            init_inv_qty = self.initial_inventory.get((node_id, prod, 'thawed'), 0)
            if init_inv_qty == 0:
                return Constraint.Skip

            # Skip for nodes without demand
            node = self.nodes[node_id]
            if not node.has_demand_capability():
                return Constraint.Skip

            # Sum consumption from init over shelf life (14 days)
            shelf_life_days = 14
            shelf_life_dates = list(model.dates)[:min(shelf_life_days, len(model.dates))]

            total_from_init = sum(
                model.consumption_from_init_thawed[node_id, prod, t]
                for t in shelf_life_dates
                if (node_id, prod, t) in model.consumption_from_init_thawed
            )

            # Skip if trivial (prevents "0 <= constant" → True)
            if isinstance(total_from_init, (int, float)) and total_from_init == 0:
                return Constraint.Skip

            return total_from_init <= init_inv_qty

        # Create indices for nodes/products with init_inv
        ambient_init_entries = [(n, p) for (n, p, s), qty in self.initial_inventory.items()
                                if s == 'ambient' and qty > 0]
        thawed_init_entries = [(n, p) for (n, p, s), qty in self.initial_inventory.items()
                               if s == 'thawed' and qty > 0]

        model.ambient_init_bound = Constraint(
            ambient_init_entries,
            rule=ambient_init_bound_rule,
            doc="Bound ambient consumption from init_inv to available quantity"
        )

        model.thawed_init_bound = Constraint(
            thawed_init_entries,
            rule=thawed_init_bound_rule,
            doc="Bound thawed consumption from init_inv to available quantity"
        )

        total_bounds = len(ambient_init_entries) + len(thawed_init_entries)
        print(f"    Init_inv outflow bounds: {total_bounds} constraints")
        print(f"      Ambient: {len(ambient_init_entries)}")
        print(f"      Thawed: {len(thawed_init_entries)}")

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
            # CRITICAL FIX: Match on route transport mode, not arrival state!
            # in_transit state = route transport mode (how shipped)
            # arrival state = after transformation at destination
            arrivals = 0
            for route in self.routes_to_node[node_id]:
                departure_date = t - timedelta(days=route.transit_days)

                if departure_date not in model.dates:
                    continue

                # Determine how goods arrive (may transform from transport mode)
                arrival_state = self._determine_arrival_state(route, node)

                if arrival_state != 'ambient':
                    continue  # Not arriving as ambient inventory

                # Look for in_transit variable using route's TRANSPORT mode
                ship_state = 'frozen' if route.transport_mode == TransportMode.FROZEN else 'ambient'

                key = (route.origin_node_id, node_id, prod, departure_date, ship_state)

                # DIAGNOSTIC: Log for debugging arrivals issues
                if node_id in ['6104', '6125'] and t == list(model.dates)[1] if len(list(model.dates)) > 1 else False:
                    print(f"  DEBUG arrivals for {node_id}, {prod[:30]}, {t}:")
                    print(f"    Route from {route.origin_node_id}, transit={route.transit_days}")
                    print(f"    Departure date: {departure_date}")
                    print(f"    departure_date in model.dates: {departure_date in model.dates}")
                    print(f"    Key in model.in_transit: {key in model.in_transit}")
                    print(f"    Arrival state: {arrival_state}")

                if key in model.in_transit:
                    arrivals += model.in_transit[key]

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
            # CRITICAL FIX (2025-11-05): Use STATE-SPECIFIC consumption variable
            # Only subtract consumption that comes from ambient (not from thawed)
            demand_consumption = 0
            if node.has_demand_capability():
                if (node_id, prod, t) in model.demand_consumed_from_ambient:
                    demand_consumption = model.demand_consumed_from_ambient[node_id, prod, t]

            # Disposal (for expired initial inventory)
            disposal_outflow = 0
            if hasattr(model, 'disposal') and (node_id, prod, 'ambient', t) in model.disposal:
                disposal_outflow = model.disposal[node_id, prod, 'ambient', t]

            # Balance
            return model.inventory[node_id, prod, 'ambient', t] == (
                prev_inv + production_inflow + thaw_inflow + arrivals -
                departures - freeze_outflow - demand_consumption - disposal_outflow
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
            # CRITICAL FIX: Match on route transport mode, not arrival state!
            # Example: Lineage receives ambient goods that become frozen on arrival
            #   - in_transit variable state = 'ambient' (route mode)
            #   - arrival state = 'frozen' (transformation at destination)
            arrivals = 0
            for route in self.routes_to_node[node_id]:
                departure_date = t - timedelta(days=route.transit_days)

                if departure_date not in model.dates:
                    continue

                # Determine how goods arrive (may transform from transport mode)
                arrival_state = self._determine_arrival_state(route, node)

                if arrival_state != 'frozen':
                    continue  # Not arriving as frozen inventory

                # Look for in_transit variable using route's TRANSPORT mode
                # (Not arrival state! in_transit state = how goods are shipped)
                ship_state = 'frozen' if route.transport_mode == TransportMode.FROZEN else 'ambient'

                key = (route.origin_node_id, node_id, prod, departure_date, ship_state)

                if key in model.in_transit:
                    arrivals += model.in_transit[key]

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

            # DIAGNOSTIC: Log Lineage frozen balance on day 1
            if node_id == "Lineage" and t == min(model.dates):
                print(f"  DEBUG frozen_balance[{node_id}, {prod[:30]}, {t}]:")
                print(f"    prev_inv: {prev_inv}")
                print(f"    production_inflow: {production_inflow}")
                print(f"    freeze_inflow: {freeze_inflow}")
                print(f"    arrivals: {arrivals}")

                # DETAILED: Check each incoming route
                print(f"    Routes TO Lineage: {len(self.routes_to_node[node_id])}")
                for route in self.routes_to_node[node_id]:
                    dep_date = t - timedelta(days=route.transit_days)
                    arrival_state = self._determine_arrival_state(route, node)
                    ship_state = 'frozen' if route.transport_mode == TransportMode.FROZEN else 'ambient'
                    key = (route.origin_node_id, node_id, prod, dep_date, ship_state)

                    print(f"      Route: {route.origin_node_id} → {node_id}")
                    print(f"        Transport mode: {route.transport_mode}")
                    print(f"        Ship state: {ship_state}")
                    print(f"        Arrival state: {arrival_state}")
                    print(f"        Departure date: {dep_date}")
                    print(f"        Dep in horizon: {dep_date in model.dates}")
                    print(f"        Key in model: {key in model.in_transit}")

                print(f"    thaw_outflow: {thaw_outflow}")
                print(f"    departures: {departures}")
                # Check if departure variables exist
                for route in self.routes_from_node[node_id]:
                    if route.transport_mode == TransportMode.FROZEN:
                        key = (node_id, route.destination_node_id, prod, t, 'frozen')
                        exists = key in model.in_transit
                        print(f"    in_transit[{key}] exists: {exists}")
                print(f"    Expected: inventory = {prev_inv} + {production_inflow} + {freeze_inflow} + arrivals - departures - {thaw_outflow}")

            # Disposal (for expired initial inventory)
            disposal_outflow = 0
            if hasattr(model, 'disposal') and (node_id, prod, 'frozen', t) in model.disposal:
                disposal_outflow = model.disposal[node_id, prod, 'frozen', t]

            # Balance
            return model.inventory[node_id, prod, 'frozen', t] == (
                prev_inv + production_inflow + freeze_inflow + arrivals -
                departures - thaw_outflow - disposal_outflow
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

            # Arrivals: goods that DEPARTED (t - transit_days) ago and arrive as 'thawed'
            # CRITICAL: Frozen goods arriving at ambient-only nodes become thawed
            # Must look for in_transit in FROZEN state (departure state), not ambient!
            arrivals = sum(
                model.in_transit[route.origin_node_id, node_id, prod, departure_date, 'frozen']
                for route in self.routes_to_node[node_id]
                # Calculate when goods must have departed to arrive today
                if (departure_date := t - timedelta(days=route.transit_days)) in model.dates
                and (route.origin_node_id, node_id, prod, departure_date, 'frozen') in model.in_transit
                and self._determine_arrival_state(route, node) == 'thawed'
            )

            # Outflows: shipments + demand
            # Thawed products ship as 'ambient' state (but drawn from thawed inventory)
            # Note: In current implementation, thawed state is minimal - most demand from ambient
            # This departure term may be zero in practice
            departures = 0
            # For now, assume thawed inventory doesn't ship (consumed locally via demand)
            # Future: Can add explicit thawed→ambient shipment tracking if needed

            # CRITICAL FIX (2025-11-05): Thawed inventory MUST satisfy demand
            # Bug #2: 6130 receives ONLY thawed goods (frozen → thawed upon arrival)
            # Without this, 6130 has 100% shortage despite receiving shipments!
            # Use STATE-SPECIFIC consumption variable (prevents double-counting)
            demand_consumption = 0
            if node.has_demand_capability():
                if (node_id, prod, t) in model.demand_consumed_from_thawed:
                    demand_consumption = model.demand_consumed_from_thawed[node_id, prod, t]

            # DIAGNOSTIC: Log 6130 thawed balance when receiving from Lineage
            if node_id == "6130" and prod == "HELGAS GFREE MIXED GRAIN 500G":
                date_list = list(model.dates)
                if t == date_list[0] or (len(date_list) > 7 and t == date_list[7]):  # Day 1 or Day 8
                    print(f"  DEBUG thawed_balance[{node_id}, {prod[:30]}, {t}]:")
                    print(f"    prev_inv: {prev_inv}")
                    print(f"    thaw_inflow: {thaw_inflow}")
                    print(f"    arrivals: {arrivals}")
                    print(f"    demand_consumption: {demand_consumption}  ← FIX: Now included!")
                    print(f"    Expected: inventory = {prev_inv} + thaw + arrivals - demand")

            # Disposal (for expired initial inventory)
            disposal_outflow = 0
            if hasattr(model, 'disposal') and (node_id, prod, 'thawed', t) in model.disposal:
                disposal_outflow = model.disposal[node_id, prod, 'thawed', t]

            # Balance
            return model.inventory[node_id, prod, 'thawed', t] == (
                prev_inv + thaw_inflow + arrivals -
                departures - demand_consumption - disposal_outflow
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

        # Build date lookup for previous day (needed for consumption limit fix)
        date_list = list(model.dates)
        date_to_prev = {}
        for i, d in enumerate(date_list):
            if i > 0:
                date_to_prev[d] = date_list[i-1]

        demand_keys = list(self.demand.keys())

        # DEMAND BALANCE: consumed + shortage = total demand
        # CRITICAL FIX (2025-11-05): Sum consumption from BOTH states
        def demand_balance_rule(model, node_id, prod, t):
            """Total demand = (consumed_from_ambient + consumed_from_thawed) + shortage."""
            if (node_id, prod, t) not in self.demand:
                return Constraint.Skip

            demand_qty = self.demand[(node_id, prod, t)]

            # Total consumption = sum of consumption from both states
            consumed_from_ambient = model.demand_consumed_from_ambient[node_id, prod, t]
            consumed_from_thawed = model.demand_consumed_from_thawed[node_id, prod, t]
            total_consumed = consumed_from_ambient + consumed_from_thawed

            if self.allow_shortages:
                shortage = model.shortage[node_id, prod, t]
                return total_consumed + shortage == demand_qty
            else:
                return total_consumed == demand_qty

        model.demand_balance_con = Constraint(
            demand_keys,
            rule=demand_balance_rule,
            doc="Demand = consumed + shortage"
        )

        print(f"  Demand balance constraints: {len(demand_keys)}")

        # DEMAND CONSUMPTION UPPER BOUNDS (MIP Best Practice)
        # CRITICAL FIX (2025-11-06): These constraints are NECESSARY, not redundant!
        #
        # WHY NEEDED - MIP Formulation Theory:
        # The combination of:
        #   (1) demand_consumed + shortage = demand
        #   (2) inventory[t] = inventory[t-1] + production - consumption
        #
        # Does NOT prevent over-consumption! Here's why:
        #   - Demand equation allows: consumption = demand (if shortage = 0)
        #   - Consumption is set as a CHOICE variable
        #   - Material balance then tries to SATISFY this consumption via production
        #   - If production is expensive, model minimizes it
        #   - Result: consumption = demand, production = minimal → PHANTOM SUPPLY!
        #
        # The explicit upper bound PREVENTS this:
        #   consumption <= inventory[t]
        #
        # This enforces: "Can't consume what you don't have YET"
        # Material balance ensures inventory is built up BEFORE it can be consumed.
        #
        # VERIFIED: Removing these constraints (commit 3a71197) caused underproduction bug.
        #   - With bounds (94883bc): 285k production ✅
        #   - Without bounds (3a71197): 18k production ❌
        #
        # The previous commit message claiming "circular dependency" was incorrect.
        # There is no circular dependency - these are coupling constraints (correct MIP pattern).
        def demand_consumption_ambient_limit_rule(model, node_id, prod, t):
            """Consumption from ambient cannot exceed available supply.

            FIX (2025-11-08): Bound consumption against INFLOWS, not inventory[t]!

            The previous formulation created a CIRCULAR DEPENDENCY:
                consumption[t] <= inventory[t]
                inventory[t] = prev_inv + inflows - consumption[t] - outflows

            This limited consumption to (prev_inv + inflows - outflows) / 2
            causing the disposal bug where only 50% of init_inv could be consumed.

            CORRECT formulation: Bound against available supply BEFORE consumption:
                consumption[t] <= prev_inv + production + arrivals + thaw - shipments - freeze - disposal
            """
            if (node_id, prod, t) not in self.demand:
                return Constraint.Skip

            node = self.nodes[node_id]
            if not node.has_demand_capability():
                return Constraint.Skip

            if (node_id, prod, 'ambient', t) not in model.inventory:
                # No ambient inventory at this node - consumption must be 0
                return model.demand_consumed_from_ambient[node_id, prod, t] == 0

            # Calculate available supply (BEFORE consumption is subtracted)
            # This is: prev_inv + inflows - outflows (excluding consumption)

            # Previous inventory
            prev_date = date_to_prev.get(t)
            if prev_date and (node_id, prod, 'ambient', prev_date) in model.inventory:
                available = model.inventory[node_id, prod, 'ambient', prev_date]
            else:
                # Day 1: use initial inventory
                available = self.initial_inventory.get((node_id, prod, 'ambient'), 0)

            # Add production inflow
            if node.can_produce() and (node_id, prod, t) in model.production:
                if node.get_production_state() == 'ambient':
                    available += model.production[node_id, prod, t]

            # Add thaw inflow
            if (node_id, prod, t) in model.thaw:
                available += model.thaw[node_id, prod, t]

            # Add arrivals
            for route in self.routes_to_node[node_id]:
                arrival_state = self._determine_arrival_state(route, node)
                if arrival_state == 'ambient':
                    departure_date = t - timedelta(days=route.transit_days)
                    if departure_date in model.dates:
                        key = (route.origin_node_id, node_id, prod, departure_date, 'ambient')
                        if key in model.in_transit:
                            available += model.in_transit[key]

            # Subtract departures (shipments)
            for route in self.routes_from_node[node_id]:
                if route.transport_mode != TransportMode.FROZEN:
                    key = (node_id, route.destination_node_id, prod, t, 'ambient')
                    if key in model.in_transit:
                        available -= model.in_transit[key]

            # Subtract freeze outflow
            if (node_id, prod, t) in model.freeze:
                available -= model.freeze[node_id, prod, t]

            # DON'T subtract disposal! (would create another circular dependency)
            # disposal[t] depends on inventory[t], which depends on consumption[t]
            # If we bound consumption by (prev_inv - disposal), we get:
            #   consumption <= prev_inv - disposal
            # But disposal is high when consumption is low, creating circular dependency
            # The state balance equation handles disposal separately.

            # Bound consumption by available supply
            return model.demand_consumed_from_ambient[node_id, prod, t] <= available

        def demand_consumption_thawed_limit_rule(model, node_id, prod, t):
            """Consumption from thawed cannot exceed available supply.

            FIX (2025-11-08): Same circular dependency fix as ambient.
            """
            if (node_id, prod, t) not in self.demand:
                return Constraint.Skip

            node = self.nodes[node_id]
            if not node.has_demand_capability():
                return Constraint.Skip

            if (node_id, prod, 'thawed', t) not in model.inventory:
                # No thawed inventory at this node - consumption must be 0
                return model.demand_consumed_from_thawed[node_id, prod, t] == 0

            # Calculate available supply (BEFORE consumption is subtracted)
            prev_date = date_to_prev.get(t)
            if prev_date and (node_id, prod, 'thawed', prev_date) in model.inventory:
                available = model.inventory[node_id, prod, 'thawed', prev_date]
            else:
                # Day 1: use initial inventory
                available = self.initial_inventory.get((node_id, prod, 'thawed'), 0)

            # Add thaw inflow
            if (node_id, prod, t) in model.thaw:
                available += model.thaw[node_id, prod, t]

            # Add arrivals (frozen goods arriving at ambient-only nodes become thawed)
            for route in self.routes_to_node[node_id]:
                arrival_state = self._determine_arrival_state(route, node)
                if arrival_state == 'thawed':
                    departure_date = t - timedelta(days=route.transit_days)
                    if departure_date in model.dates:
                        # Check both frozen and thawed in-transit
                        for state in ['frozen', 'thawed']:
                            key = (route.origin_node_id, node_id, prod, departure_date, state)
                            if key in model.in_transit:
                                available += model.in_transit[key]

            # DON'T subtract disposal! (creates circular dependency - same as ambient)
            # State balance handles disposal separately

            # Bound consumption by available supply
            return model.demand_consumed_from_thawed[node_id, prod, t] <= available

        model.demand_consumed_ambient_limit_con = Constraint(
            demand_keys,
            rule=demand_consumption_ambient_limit_rule,
            doc="Consumption from ambient <= ambient inventory"
        )

        model.demand_consumed_thawed_limit_con = Constraint(
            demand_keys,
            rule=demand_consumption_thawed_limit_rule,
            doc="Consumption from thawed <= thawed inventory"
        )

        print(f"  Demand consumption limit constraints added: ambient and thawed (prevents over-consumption)")

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
                """Truck pallets must cover total in-transit to this destination.

                IMPORTANT: Different routes to same destination may have different transit times!
                We need to check each route individually.
                """
                # Find all routes to this destination
                routes_to_dest = [r for r in self.routes if r.destination_node_id == dest]
                if not routes_to_dest:
                    return Constraint.Skip

                # Sum in-transit shipments that would DELIVER on delivery_date
                # Each route has its own transit time, so departure_date varies by origin
                total_in_transit = 0

                for route in routes_to_dest:
                    # Calculate when goods must depart from THIS origin to arrive on delivery_date
                    departure_date = delivery_date - timedelta(days=route.transit_days)

                    # Only include if departure is within planning horizon
                    if departure_date in model.dates:
                        # Add in-transit from this specific origin, departing on this date
                        for state in ['frozen', 'ambient']:
                            if (route.origin_node_id, dest, prod, departure_date, state) in model.in_transit:
                                total_in_transit += model.in_transit[route.origin_node_id, dest, prod, departure_date, state]

                # CRITICAL FIX: Skip if no in-transit shipments
                # Otherwise creates constraint: truck_pallet_load * 320 >= 0, which wastes variables
                # More importantly: prevents infeasibility from truck constraints on dates with no shipments
                try:
                    if total_in_transit == 0:
                        return Constraint.Skip
                except:
                    pass  # Pyomo expression, can't compare to 0

                # Truck pallets must be sufficient to carry all in-transit shipments
                return model.truck_pallet_load[truck_idx, dest, prod, delivery_date] * self.UNITS_PER_PALLET >= total_in_transit

            model.truck_pallet_ceiling_con = Constraint(
                model.truck_pallet_load.index_set(),
                rule=truck_pallet_ceiling_rule,
                doc="Truck pallet ceiling: pallet_load * 320 >= shipments"
            )

            # DIAGNOSTIC: Count constraints
            ceiling_count = sum(1 for _ in model.truck_pallet_ceiling_con)
            print(f"    Truck pallet ceiling constraints added: {ceiling_count}")

            # Check if any constraints reference dates beyond horizon
            truck_pallet_dates = set(d for (_, _, _, d) in model.truck_pallet_load)
            if truck_pallet_dates:
                min_truck_date = min(truck_pallet_dates)
                max_truck_date = max(truck_pallet_dates)
                planning_end = max(model.dates)
                if max_truck_date > planning_end:
                    print(f"    WARNING: Truck pallets extend beyond planning horizon!")
                    print(f"      Planning end: {planning_end}")
                    print(f"      Max truck date: {max_truck_date}")
                    print(f"      Days beyond: {(max_truck_date - planning_end).days}")


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

            # MIP Performance Optimization (2025-11-26 Phase 2):
            # Link mix_count to product_produced binary to eliminate ~85k useless branch nodes.
            # Without this, LP relaxation can set product_produced=0.001 (fractional)
            # while mix_count=5.2, exploiting the gap to get artificially low bounds.
            if hasattr(model, 'product_produced'):
                max_daily_hours = 14  # Max hours per day
                default_production_rate = 1400  # units/hour
                max_daily_units = default_production_rate * max_daily_hours  # 19,600 units

                def mix_count_product_linking_rule(model, node_id, prod, t):
                    """Force mix_count=0 when product not produced (product_produced=0)."""
                    if (node_id, prod, t) not in model.product_produced:
                        return Constraint.Skip

                    product = self.products.get(prod)
                    if product and hasattr(product, 'units_per_mix') and product.units_per_mix > 0:
                        max_mixes = int(max_daily_units / product.units_per_mix) + 1
                    else:
                        max_mixes = 100  # Fallback

                    return model.mix_count[node_id, prod, t] <= max_mixes * model.product_produced[node_id, prod, t]

                model.mix_count_product_link = Constraint(
                    model.mix_count.index_set(),
                    rule=mix_count_product_linking_rule,
                    doc="mix_count <= max_mixes × product_produced (forces mix_count=0 when not producing)"
                )
                print(f"    Mix-count to product_produced linking constraints added (MIP optimization)")

                # MIP Performance Optimization (2025-11-26 Phase 4):
                # Add LOWER bound to create tight LP relaxation.
                # Without this, LP can set product_produced=0.01 with mix_count=0, causing gap stall at ~1.6%
                # With this: product_produced=1 implies mix_count>=1, product_produced=0 implies mix_count=0
                def mix_count_lower_bound_rule(model, node_id, prod, t):
                    """Force at least 1 mix when producing (tight LP relaxation)."""
                    if (node_id, prod, t) not in model.product_produced:
                        return Constraint.Skip
                    return model.mix_count[node_id, prod, t] >= model.product_produced[node_id, prod, t]

                model.mix_count_lower_bound = Constraint(
                    model.mix_count.index_set(),
                    rule=mix_count_lower_bound_rule,
                    doc="mix_count >= product_produced (tight LP: if producing, at least 1 mix)"
                )
                print(f"    Mix-count lower bound constraints added (Phase 4: tight LP relaxation)")

        # PRODUCTION CAPACITY: production_time <= labor_hours
        # We need TWO constraints per manufacturing node-date:
        # 1. Link labor_hours_used to production_time (equality)
        # 2. Enforce labor_hours_used <= max_hours (capacity limit)

        def production_time_link_rule(model, node_id, t):
            """Link labor_hours_used to production time + overhead time.

            MIP Performance Optimization (2025-11-26 Phase 2):
            REFORMULATED to eliminate small coefficient (1/1400 = 0.000714).

            Instead of: labor_hours_used == production/1400 + overhead
            We use:     labor_hours_used * 1400 == production + overhead * 1400

            This changes the smallest coefficient from 0.000714 to 1.0,
            reducing the coefficient range from 10^7 to ~10^4.

            Overhead includes:
            - Startup time (if producing)
            - Shutdown time (if producing)
            - Changeover time (per product start)
            """
            node = self.nodes[node_id]
            if not node.can_produce():
                return Constraint.Skip

            # Get production rate
            production_rate = node.capabilities.production_rate_per_hour
            if not production_rate or production_rate <= 0:
                return Constraint.Skip

            # Total production (units)
            total_production = sum(
                model.production[node_id, prod, t]
                for prod in model.products
                if (node_id, prod, t) in model.production
            )

            # Calculate scaled overhead (overhead_time × production_rate)
            # This avoids dividing by production_rate, keeping coefficients ≥ 1.0
            scaled_overhead = 0
            if hasattr(model, 'total_starts') and (node_id, t) in model.total_starts:
                # Get overhead parameters from node capabilities
                startup_hours = node.capabilities.daily_startup_hours or 0.5
                shutdown_hours = node.capabilities.daily_shutdown_hours or 0.25
                changeover_hours = node.capabilities.default_changeover_hours or 0.5

                # Overhead calculation (scaled by production_rate):
                # - Startup/shutdown: applied once if producing (any products)
                # - Changeover: applied per product start
                # Formula: scaled_overhead = production_rate × overhead_time
                #        = production_rate × [(startup + shutdown) × any_production +
                #                             changeover × (total_starts - any_production)]
                scaled_overhead = production_rate * (
                    (startup_hours + shutdown_hours) * model.any_production[node_id, t] +
                    changeover_hours * (model.total_starts[node_id, t] - model.any_production[node_id, t])
                )

            # Get available hours
            labor_day = self.labor_calendar.get_labor_day(t)
            if not labor_day:
                return total_production == 0  # No labor → no production

            # Reformulated constraint: labor_hours × rate == production + scaled_overhead
            # This has coefficient 1.0 for production instead of 1/1400 = 0.000714
            if (node_id, t) in model.labor_hours_used:
                return model.labor_hours_used[node_id, t] * production_rate == total_production + scaled_overhead
            else:
                # No labor variable, skip linking
                return Constraint.Skip

        def production_capacity_limit_rule(model, node_id, t):
            """Enforce labor capacity: labor_hours_used <= max_hours.

            This constraint enforces the upper bound on labor hours.
            It is separate from the linking constraint to ensure both are active.
            """
            node = self.nodes[node_id]
            if not node.can_produce():
                return Constraint.Skip

            # Get production rate
            production_rate = node.capabilities.production_rate_per_hour
            if not production_rate or production_rate <= 0:
                return Constraint.Skip

            # Get available hours
            labor_day = self.labor_calendar.get_labor_day(t)
            if not labor_day:
                return Constraint.Skip  # No labor day means production=0 (handled by link constraint)

            # Calculate max hours
            if labor_day.is_fixed_day:
                max_hours = labor_day.fixed_hours + (labor_day.overtime_hours if hasattr(labor_day, 'overtime_hours') else 0)
            else:
                max_hours = 14.0  # Weekend/holiday max

            # Enforce capacity limit
            if (node_id, t) in model.labor_hours_used:
                return model.labor_hours_used[node_id, t] <= max_hours
            else:
                # No labor variable - constraint handled elsewhere
                return Constraint.Skip

        # Add both constraints
        manufacturing_date_pairs = [(node.id, t) for node in self.manufacturing_nodes for t in model.dates]

        model.production_time_link_con = Constraint(
            manufacturing_date_pairs,
            rule=production_time_link_rule,
            doc="Link labor_hours_used to production time"
        )

        model.production_capacity_limit_con = Constraint(
            manufacturing_date_pairs,
            rule=production_capacity_limit_rule,
            doc="Enforce labor capacity: labor_hours_used <= max_hours"
        )

        print(f"    Production time linking constraints added")
        print(f"    Production capacity limit constraints added")

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

        # LABOR HOURS PAID: Enforce 4-hour minimum on weekends/holidays
        if hasattr(model, 'labor_hours_paid'):
            def labor_hours_paid_lower_rule(model, node_id, t):
                """Paid hours must at least equal used hours."""
                return model.labor_hours_paid[node_id, t] >= model.labor_hours_used[node_id, t]

            model.labor_hours_paid_lower_con = Constraint(
                [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
                rule=labor_hours_paid_lower_rule,
                doc="Paid hours >= used hours (always pay for time worked)"
            )

            def minimum_payment_enforcement_rule(model, node_id, t):
                """Enforce 4-hour minimum payment on weekends/holidays when producing.

                Business rule: If you use ANY labor on a non-fixed day, you must pay
                for at least 4 hours (even if you only work 0.25 hours).

                MIP formulation:
                  paid_hours >= minimum_hours × any_production

                If any_production = 0: paid_hours >= 0 (can be 0)
                If any_production = 1: paid_hours >= 4 (minimum payment)
                """
                labor_day = self.labor_calendar.get_labor_day(t)

                if not labor_day or labor_day.is_fixed_day:
                    return Constraint.Skip  # Only applies to weekends/holidays

                # Get minimum hours (default 4.0 if not specified)
                minimum_hours = getattr(labor_day, 'minimum_hours', 4.0) or 4.0

                # Use any_production binary (already exists from changeover overhead)
                # This links minimum payment to production decision
                if (node_id, t) in model.any_production:
                    return model.labor_hours_paid[node_id, t] >= minimum_hours * model.any_production[node_id, t]
                else:
                    # No any_production variable - skip minimum enforcement
                    return Constraint.Skip

            model.minimum_payment_con = Constraint(
                [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
                rule=minimum_payment_enforcement_rule,
                doc="Enforce 4-hour minimum payment on weekends/holidays when producing"
            )

            print(f"    Labor payment constraints added (4-hour minimum on weekends)")

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
            doc="Link production quantity to product_produced binary (upper bound)"
        )

        # REVERSE LINKING: REMOVED (2025-11-25 MIP Performance Optimization)
        #
        # Previous implementation used: product_produced >= production / 19,600
        # This had coefficient 1/19,600 = 0.000051 which caused extreme numerical
        # scaling issues (coefficient range 10^8) and slow MIP gap closure.
        #
        # The upper Big-M (production <= 19,600 * product_produced) combined with
        # the binary penalty in the objective ($0.01 per product_produced) achieves
        # the same effect without the tiny coefficient:
        # - Upper Big-M: Forces production=0 when product_produced=0
        # - Binary penalty: Incentivizes product_produced=0 when not needed
        #
        # See: MIP Performance Optimization Plan (compressed-forging-pillow.md)
        print(f"    Product-binary upper-bound linking constraints added (reverse linking REMOVED for numerical stability)")

        # CHANGEOVER AGGREGATION LINKING (Overhead optimization)
        # Link pre-aggregated variables to binary sums for efficient overhead calculation
        if hasattr(model, 'total_starts'):
            def total_starts_link_rule(model, node_id, t):
                """Sum of product starts equals total_starts variable."""
                return model.total_starts[node_id, t] == sum(
                    model.product_start[node_id, prod, t]
                    for prod in model.products
                    if (node_id, prod, t) in model.product_start
                )

            model.total_starts_link_con = Constraint(
                [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
                rule=total_starts_link_rule,
                doc="Link total_starts to sum of product_start (overhead optimization)"
            )

            def any_production_upper_link_rule(model, node_id, t):
                """If ANY product is produced, any_production must be 1 (upper bound)."""
                # FIXED (2025-11-05): Strengthen constraint to force any_production=1 if ANY product produced
                # OLD BUG: any_production * N >= sum(product_produced) allows any_production=0 if sum=1, N=5
                # NEW FIX: any_production >= product_produced[p] for each product
                # This ensures: if ANY product_produced=1, then any_production=1
                #
                # Alternative formulation (same logic, more efficient):
                # sum(product_produced) <= N * any_production (reverse Big-M)
                # If any_production=0, forces sum=0 (no products)
                # If any_production=1, allows sum up to N (any number of products)
                num_products = len(model.products)
                return sum(
                    model.product_produced[node_id, prod, t]
                    for prod in model.products
                    if (node_id, prod, t) in model.product_produced
                ) <= num_products * model.any_production[node_id, t]

            def any_production_lower_link_rule(model, node_id, t):
                """If NO products produced, any_production must be 0 (lower bound)."""
                # If any_production = 1, at least one product must be produced
                # Equivalently: any_production <= sum of product_produced
                # This ensures: production = 0 → any_production = 0
                return model.any_production[node_id, t] <= sum(
                    model.product_produced[node_id, prod, t]
                    for prod in model.products
                    if (node_id, prod, t) in model.product_produced
                )

            model.any_production_upper_link_con = Constraint(
                [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
                rule=any_production_upper_link_rule,
                doc="Link any_production upper: forces 1 if producing (overhead optimization)"
            )

            model.any_production_lower_link_con = Constraint(
                [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
                rule=any_production_lower_link_rule,
                doc="Link any_production lower: forces 0 if not producing (overhead optimization)"
            )

            def total_starts_zero_when_not_producing_rule(model, node_id, t):
                """If any_production = 0, force total_starts = 0."""
                # Big-M: total_starts <= N * any_production
                # If any_production = 0, forces total_starts = 0
                # If any_production = 1, allows total_starts up to N
                num_products = len(model.products)
                return model.total_starts[node_id, t] <= num_products * model.any_production[node_id, t]

            model.total_starts_zero_link_con = Constraint(
                [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
                rule=total_starts_zero_when_not_producing_rule,
                doc="Force total_starts = 0 when any_production = 0 (overhead optimization)"
            )

            # AGGREGATE PRODUCTION ENFORCEMENT: Prevent overhead without production
            # If any_production = 1, at least one product MUST be produced
            # This prevents: any_production=1, all production[prod]=0 (phantom overhead)
            def any_production_enforcement_rule(model, node_id, t):
                """If any_production = 1, force sum(production) > 0.

                Prevents solver from setting any_production=1 when all production=0,
                which would incur overhead costs (startup/shutdown) without output.

                MIP formulation (reverse of Big-M):
                  sum(production) >= epsilon × any_production

                If any_production = 0: sum >= 0 (can be 0)
                If any_production = 1: sum >= epsilon (must produce something!)

                This is more efficient than per-product constraints (29 vs 145).
                """
                node = self.nodes[node_id]
                if not node.can_produce():
                    return Constraint.Skip

                # Sum of all production
                total_prod = sum(
                    model.production[node_id, prod, t]
                    for prod in model.products
                    if (node_id, prod, t) in model.production
                )

                # Small epsilon (1 unit minimum if producing)
                epsilon = 1.0
                return total_prod >= epsilon * model.any_production[node_id, t]

            model.any_production_enforcement_con = Constraint(
                [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
                rule=any_production_enforcement_rule,
                doc="Enforce production > 0 if any_production = 1 (prevents phantom overhead)"
            )

            print(f"    Changeover aggregation linking constraints added (overhead optimization)")

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

        Minimize: production + labor + transport + holding + shortage + disposal + changeover + waste

        NO explicit staleness penalty - holding costs implicitly drive freshness.
        """
        print(f"\nBuilding objective...")

        # PRODUCTION COST (direct manufacturing cost)
        production_cost = 0
        if hasattr(model, 'production'):
            prod_cost_per_unit = self.cost_structure.production_cost_per_unit or 1.30
            from pyomo.environ import quicksum
            production_cost = prod_cost_per_unit * quicksum(
                model.production[node_id, prod, t]
                for (node_id, prod, t) in model.production
            )
            print(f"  Production cost: ${prod_cost_per_unit:.2f}/unit")

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

        # DISPOSAL COST (for expired initial inventory)
        # MIP Technique: Penalty ensures disposal only when inventory truly expires
        # CRITICAL REQUIREMENT: disposal_penalty > shortage_penalty
        # Otherwise model will dispose everything + take shortages instead of using inventory!
        disposal_cost = 0
        if hasattr(model, 'disposal'):
            # Set disposal penalty HIGHER than shortage penalty to prevent pathological solution
            shortage_penalty = self.cost_structure.shortage_penalty_per_unit if self.allow_shortages else 1000.0
            disposal_penalty = shortage_penalty * 1.5  # 50% higher than shortage

            # Rationale: Disposing good inventory is worse than having a shortage
            # We only want disposal when inventory truly expires and can't be used
            disposal_cost = quicksum(
                disposal_penalty * model.disposal[node_id, prod, state, t]
                for (node_id, prod, state, t) in model.disposal
            )
            print(f"  Disposal penalty: ${disposal_penalty:.2f}/unit (> shortage ${shortage_penalty:.2f}/unit)")

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
                        # Use labor_hours_paid (includes 4-hour minimum if producing)
                        non_fixed_rate = labor_day.non_fixed_rate if hasattr(labor_day, 'non_fixed_rate') else 1320.0
                        if hasattr(model, 'labor_hours_paid') and (node_id, t) in model.labor_hours_paid:
                            labor_cost += non_fixed_rate * model.labor_hours_paid[node_id, t]
                        else:
                            # Fallback to labor_hours_used if labor_hours_paid doesn't exist
                            labor_cost += non_fixed_rate * model.labor_hours_used[node_id, t]

            print(f"  Labor cost: Weekday overtime ($660/h) + Weekend ($1320/h with 4h minimum), fixed hours FREE")

        # TRANSPORT COST (per-route costs)
        transport_cost = 0
        if hasattr(model, 'in_transit'):
            for (origin, dest, prod, departure_date, state) in model.in_transit:
                # Find route cost
                route = next((r for r in self.routes if r.origin_node_id == origin and r.destination_node_id == dest), None)
                if route and hasattr(route, 'cost_per_unit') and route.cost_per_unit:
                    transport_cost += route.cost_per_unit * model.in_transit[origin, dest, prod, departure_date, state]
            # Note: Can't check if transport_cost > 0 (it's a Pyomo expression)
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

        # CRITICAL DIAGNOSTIC (2025-11-05): Debug why end inventory is high despite waste cost
        print(f"  DEBUG WASTE COST:")
        print(f"    cost_structure.waste_cost_multiplier = {self.cost_structure.waste_cost_multiplier}")
        print(f"    After 'or 0' = {waste_multiplier}")
        print(f"    Type: {type(waste_multiplier)}")
        print(f"    Condition (waste_multiplier > 0): {waste_multiplier > 0}")
        print(f"    hasattr(model, 'inventory'): {hasattr(model, 'inventory')}")

        if waste_multiplier > 0 and hasattr(model, 'inventory'):
            print(f"    ✅ ENTERED waste cost block")

            # Calculate end-of-horizon inventory (at locations)
            last_date = max(model.dates)
            print(f"    Last date: {last_date}")

            # Count how many inventory vars at last date
            num_end_vars = sum(1 for (n,p,s,t) in model.inventory if t == last_date)
            print(f"    Inventory variables at last date: {num_end_vars}")

            end_inventory = sum(
                model.inventory[node_id, prod, state, last_date]
                for (node_id, prod, state, t) in model.inventory
                if t == last_date
            )
            print(f"    end_inventory expression created (Pyomo sum)")

            # Calculate end-of-horizon in-transit (goods departing on last day)
            # These goods are in the pipeline and will deliver after planning horizon ends
            end_in_transit = 0
            if hasattr(model, 'in_transit'):
                num_in_transit_end = sum(1 for (o,d,p,t,s) in model.in_transit if t == last_date)
                print(f"    In-transit variables departing on last date: {num_in_transit_end}")

                end_in_transit = sum(
                    model.in_transit[origin, dest, prod, last_date, state]
                    for (origin, dest, prod, departure_date, state) in model.in_transit
                    if departure_date == last_date
                )
                print(f"    end_in_transit expression created (Pyomo sum)")

            prod_cost = self.cost_structure.production_cost_per_unit or 1.3
            waste_cost = waste_multiplier * prod_cost * (end_inventory + end_in_transit)

            print(f"  Waste cost: ${waste_multiplier * prod_cost:.2f}/unit × (end_inventory + end_in_transit)")
            print(f"    Coefficient: ${waste_multiplier * prod_cost:.2f}/unit")
            print(f"    Expression type: {type(waste_cost)}")
            print(f"    If end_inventory=32,751, waste would be ${waste_multiplier * prod_cost * 32751:.2f}")
            print(f"    ✅ WASTE COST EXPRESSION CREATED - WILL BE IN OBJECTIVE")
        else:
            print(f"    ❌ SKIPPED waste cost block!")
            print(f"       waste_multiplier > 0: {waste_multiplier > 0}")
            print(f"       hasattr inventory: {hasattr(model, 'inventory')}")

        # BINARY INDICATOR PENALTY (MIP Expert Pattern #3: Fixed Cost)
        # Tiny cost penalty on product_produced binaries prevents solver from
        # setting them to 1 when production=0 (which would incur overhead costs)
        # This is more efficient than epsilon forcing constraints!
        binary_penalty = 0
        if hasattr(model, 'product_produced'):
            # Penalty must be tiny (< smallest real cost difference)
            # But large enough to matter in solver's objective comparisons
            # MIP Performance Optimization (2025-11-25): Increased 10x to better enforce
            # product_produced=0 when production=0, since reverse Big-M was removed
            epsilon_cost = 0.01  # $0.01 per binary (was $0.001, still negligible vs real costs $1-$1000)
            from pyomo.environ import quicksum
            binary_penalty = epsilon_cost * quicksum(
                model.product_produced[node_id, prod, t]
                for (node_id, prod, t) in model.product_produced
            )
            print(f"  Binary indicator penalty: ${epsilon_cost:.4f} per product_produced binary")

        # TOTAL OBJECTIVE
        total_cost = (
            production_cost +  # CRITICAL: Direct manufacturing cost
            labor_cost +
            transport_cost +
            holding_cost +
            shortage_cost +
            disposal_cost +  # Expired initial inventory disposal
            changeover_cost +
            changeover_waste_cost +  # Yield loss from product switches
            waste_cost +
            binary_penalty  # Prevents phantom overhead (labor without production)
        )

        model.obj = Objective(
            expr=total_cost,
            sense=minimize,
            doc="Minimize total cost - holding drives freshness implicitly"
        )

        print(f"\nObjective built")
        print(f"  Active components: production + labor + transport + holding + shortage + disposal + changeover (cost + waste) + waste")
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

                # Check if ANY production variables have non-zero values
                non_zero_count = 0
                sample_values = []
                for key in list(model.production.keys())[:20]:  # Check first 20
                    try:
                        val = value(model.production[key])
                        if val and abs(val) > 0.01:
                            non_zero_count += 1
                            if len(sample_values) < 5:
                                sample_values.append((key, val))
                    except:
                        pass

                logger.info(f"Non-zero production variables found: {non_zero_count}")
                if sample_values:
                    logger.info(f"Sample production values:")
                    for key, val in sample_values:
                        logger.info(f"  production{key} = {val:.2f}")
                else:
                    logger.error("All production variables are ZERO! This confirms zero production solution.")
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

        # Extract in-transit flows (pipeline inventory tracking)
        # Convert to shipments_by_route format for UI compatibility (using delivery_date)
        shipments_by_route = {}
        skipped_post_horizon = 0  # Counter for post-horizon shipments filtered out
        last_date = max(model.dates)  # Planning horizon end

        if hasattr(model, 'in_transit'):
            for (origin, dest, prod, departure_date, state) in model.in_transit:
                try:
                    var = model.in_transit[origin, dest, prod, departure_date, state]

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
                        # Calculate delivery date for UI compatibility
                        route = next((r for r in self.routes if r.origin_node_id == origin and r.destination_node_id == dest), None)
                        if route:
                            delivery_date = departure_date + timedelta(days=route.transit_days)

                            # CRITICAL FIX (2025-11-05): Filter post-horizon shipments
                            # Model has NO demand beyond last_date
                            # Shipments delivering after horizon serve no purpose → don't extract
                            # (Goods stay as end-inventory, penalized by waste cost)
                            if delivery_date > last_date:
                                # Don't extract as shipment - serves no known demand
                                skipped_post_horizon += 1
                                logger.debug(f"Skipping post-horizon: {origin}→{dest} {prod[:30]} delivers {delivery_date} > {last_date}")
                                continue

                            # Aggregate by route (ignoring state for UI simplicity)
                            route_key = (origin, dest, prod, delivery_date)
                            shipments_by_route[route_key] = shipments_by_route.get(route_key, 0) + qty
                except (ValueError, AttributeError, TypeError):
                    # Uninitialized variable - not used in solution, skip
                    pass

        solution['shipments_by_route_product_date'] = shipments_by_route
        logger.info(f"Extracted {len(shipments_by_route)} in-transit flows (converted to delivery dates)")
        if skipped_post_horizon > 0:
            logger.warning(f"Filtered out {skipped_post_horizon} post-horizon shipments (delivery > {last_date})")

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
                    hours_used = value(model.labor_hours_used[node_id, t])
                    if hours_used and hours_used > 0.01:
                        # Extract paid hours (may differ from used due to 4h minimum)
                        hours_paid = hours_used
                        if hasattr(model, 'labor_hours_paid') and (node_id, t) in model.labor_hours_paid:
                            hours_paid = value(model.labor_hours_paid[node_id, t])

                        # Store as LaborHoursBreakdown with both used and paid
                        from .result_schema import LaborHoursBreakdown
                        labor_hours_by_date[t] = LaborHoursBreakdown(
                            used=hours_used,
                            paid=hours_paid,
                            fixed=0.0,
                            overtime=0.0,
                            non_fixed=hours_paid
                        )

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
                                # Weekend: use paid hours (includes 4-hour minimum)
                                non_fixed_rate = labor_day.non_fixed_rate if hasattr(labor_day, 'non_fixed_rate') else 1320.0
                                labor_cost_by_date[t] = hours_paid * non_fixed_rate
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
        # CRITICAL FIX (2025-11-05): Aggregate consumption from BOTH states
        demand_consumed_by_location = {}
        if hasattr(model, 'demand_consumed_from_ambient') and hasattr(model, 'demand_consumed_from_thawed'):
            for (node_id, prod, t) in model.demand_consumed_from_ambient:
                try:
                    # Get consumption from both states
                    consumed_ambient = value(model.demand_consumed_from_ambient[node_id, prod, t])
                    consumed_thawed = value(model.demand_consumed_from_thawed[node_id, prod, t])

                    # Total consumption for UI display
                    total_consumed = consumed_ambient + consumed_thawed

                    if total_consumed > 0.01:
                        demand_consumed_by_location[(node_id, prod, t)] = total_consumed
                except (ValueError, AttributeError):
                    pass
        elif hasattr(model, 'demand_consumed'):
            # Fallback for backward compatibility (old models without state-specific vars)
            for (node_id, prod, t) in model.demand_consumed:
                try:
                    var = model.demand_consumed[node_id, prod, t]
                    qty = value(var)
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
        total_labor_hours = sum(h.used if hasattr(h, 'used') else h for h in labor_hours_by_date.values())
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

        # Extract holding cost from pallet variables
        if hasattr(model, 'pallet_count'):
            print(f"\nDEBUG: Extracting holding cost from {len(model.pallet_count)} pallet_count variables...")

            try:
                frozen_cost_per_pallet_day = getattr(self.cost_structure, 'storage_cost_per_pallet_day_frozen', 0) or 0
                ambient_cost_per_pallet_day = getattr(self.cost_structure, 'storage_cost_per_pallet_day_ambient', 0) or 0

                print(f"  Frozen cost/pallet/day: ${frozen_cost_per_pallet_day:.2f}")
                print(f"  Ambient cost/pallet/day: ${ambient_cost_per_pallet_day:.2f}")

                pallet_days_frozen = 0
                pallet_days_ambient = 0

                for (node_id, prod, state, t) in model.pallet_count:
                    # Use exception=False to avoid error messages for uninitialized vars
                    pallets = value(model.pallet_count[node_id, prod, state, t], exception=False)
                    if pallets is not None and pallets > 0.01:
                        if state == 'frozen':
                            solution['frozen_holding_cost'] += pallets * frozen_cost_per_pallet_day
                            pallet_days_frozen += pallets
                        elif state in ['ambient', 'thawed']:
                            solution['ambient_holding_cost'] += pallets * ambient_cost_per_pallet_day
                            pallet_days_ambient += pallets

                solution['total_holding_cost'] = solution['frozen_holding_cost'] + solution['ambient_holding_cost']

                print(f"  Pallet-days: frozen={pallet_days_frozen:.0f}, ambient={pallet_days_ambient:.0f}")
                print(f"  Holding cost extracted: frozen=${solution['frozen_holding_cost']:,.2f}, ambient=${solution['ambient_holding_cost']:,.2f}, total=${solution['total_holding_cost']:,.2f}")

            except Exception as e:
                print(f"  ERROR extracting holding cost: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"\nDEBUG: Model does not have pallet_count variables - holding cost will be $0")

        # Extract pallet entry costs (fixed costs)
        if hasattr(model, 'pallet_entry'):
            try:
                frozen_fixed_cost = getattr(self.cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0) or 0
                ambient_fixed_cost = getattr(self.cost_structure, 'storage_cost_fixed_per_pallet_ambient', 0) or 0

                pallet_entry_cost = 0
                for (node_id, prod, state, t) in model.pallet_entry:
                    entries = value(model.pallet_entry[node_id, prod, state, t], exception=False)
                    if entries is not None and entries > 0.01:
                        if state == 'frozen':
                            pallet_entry_cost += entries * frozen_fixed_cost
                        elif state in ['ambient', 'thawed']:
                            pallet_entry_cost += entries * ambient_fixed_cost

                # Add pallet entry costs to holding costs
                solution['total_holding_cost'] += pallet_entry_cost
                solution['frozen_holding_cost'] += pallet_entry_cost  # Simplified - mostly frozen

                logger.info(f"Pallet entry cost extracted: ${pallet_entry_cost:,.2f}")
            except Exception as e:
                logger.warning(f"Failed to extract pallet entry costs: {e}")
                pass

        # Try to extract changeover costs
        if hasattr(model, 'product_start'):
            try:
                changeover_cost_per_start = getattr(self.cost_structure, 'changeover_cost_per_start', 0) or 0
                changeover_waste_units = getattr(self.cost_structure, 'changeover_waste_units', 0) or 0
                production_cost_per_unit = self.cost_structure.production_cost_per_unit or 0

                total_starts = 0
                for (node_id, prod, t) in model.product_start:
                    val = value(model.product_start[node_id, prod, t], exception=False)
                    if val is not None and val > 0.01:
                        total_starts += val

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
                end_inventory = 0
                for (node_id, prod, state, t) in model.inventory:
                    if t == last_date:
                        val = value(model.inventory[node_id, prod, state, last_date], exception=False)
                        if val is not None and val > 0.01:
                            end_inventory += val
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
            if isinstance(hours_value, LaborHoursBreakdown):
                # Already a LaborHoursBreakdown object
                labor_hours_by_date[date_key] = hours_value
            elif isinstance(hours_value, dict):
                # Dictionary format - convert to breakdown
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

        # MANDATORY BUSINESS RULE VALIDATION
        # This catches bugs that made it through the optimization model
        # FAILS LOUDLY if solution violates business rules
        from src.validation.solution_validator import validate_solution
        try:
            is_valid, validation_errors = validate_solution(
                opt_solution,
                demand_data=self.demand,
                fail_on_error=True  # CRITICAL: Fail immediately on violation
            )
        except Exception as e:
            logger.error(f"❌ SOLUTION VALIDATION FAILED: {e}")
            logger.error(f"   Solution violates business rules - DO NOT USE")
            raise

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

                    # CRITICAL FIX (2025-11-05): Calculate realistic production date from age
                    # Initial inventory exists at inventory_snapshot_date with unknown age
                    # Estimate production date conservatively based on state shelf life
                    # This prevents showing "future" production dates in Daily Inventory Snapshot
                    #
                    # NOTE: Age estimation uses midpoint heuristics (ambient=8d, frozen=60d, thawed=7d)
                    # Future enhancement: Parse actual age/production_date from inventory data if available
                    if state == 'ambient':
                        # Ambient shelf life: 17 days
                        # Assume midpoint age (8 days) for conservative estimate
                        estimated_age_days = 8
                    elif state == 'frozen':
                        # Frozen shelf life: 120 days
                        # Assume midpoint age (60 days) for conservative estimate
                        estimated_age_days = 60
                    else:  # thawed
                        # Thawed shelf life: 14 days
                        # Assume midpoint age (7 days) for conservative estimate
                        estimated_age_days = 7

                    # Calculate production date = snapshot_date - estimated_age
                    # This ensures initial inventory batches have PAST production dates
                    if self.inventory_snapshot_date:
                        estimated_production_date = self.inventory_snapshot_date - timedelta(days=estimated_age_days)
                    else:
                        # Fallback: use start_date - estimated_age
                        estimated_production_date = self.start_date - timedelta(days=estimated_age_days)

                    batch = Batch(
                        id=f"INIT_{product_id}_{state}_{uuid.uuid4().hex[:8]}",
                        product_id=product_id,
                        manufacturing_site_id=node_id,
                        production_date=estimated_production_date,  # ✅ FIX: Past date, not start_date
                        state_entry_date=estimated_production_date,  # State entry = production for initial inventory
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

            # Derive state from route transport mode (fixes hardcoded 'ambient' bug)
            if route and hasattr(route, 'transport_mode'):
                state = route.transport_mode.value if hasattr(route.transport_mode, 'value') else str(route.transport_mode)
            else:
                state = 'ambient'  # Fallback if route not found

            allocator.allocate_shipment(
                origin_node=origin,
                destination_node=dest,
                product_id=prod,
                state=state,
                quantity=qty,
                delivery_date=delivery_date,
                use_weighted_age=use_weighted_age  # LP uses weighted age for sorting
            )

        # Apply pending batch moves AFTER all shipments allocated
        # This two-phase approach allows multiple shipments from same origin
        # to allocate from the same batch before batches are moved
        allocator.apply_pending_moves()

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
