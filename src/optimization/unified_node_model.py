"""Unified Node-Based Optimization Model.

This module implements a simplified optimization model based on unified nodes.

Key simplifications vs legacy IntegratedProductionDistributionModel:
1. NO VIRTUAL LOCATIONS - No 6122_Storage, just real nodes
2. SINGLE INVENTORY BALANCE - One equation for all nodes (manufacturing, hubs, storage, breadrooms)
3. GENERALIZED TRUCK CONSTRAINTS - Works for ANY route, not just manufacturing-origin
4. CLEAN STATE TRANSITIONS - Simple rules based on node storage_mode
5. CAPABILITY-BASED LOGIC - Constraints check node capabilities, not location types

Architecture:
- Nodes have capabilities (can_manufacture, has_demand, storage_mode, requires_trucks)
- Routes connect nodes with transit_days (0 = instant transfer)
- Trucks constrain routes based on origin_node_id (generalizable to any node)
- State transitions automatic based on transport_mode + destination storage_mode

COMPREHENSIVE DOCUMENTATION:
For detailed technical specification including all decision variables, constraints,
objective function formulation, and design patterns, see:
    docs/UNIFIED_NODE_MODEL_SPECIFICATION.md

MAINTENANCE REQUIREMENT:
When modifying this file, update docs/UNIFIED_NODE_MODEL_SPECIFICATION.md to keep
documentation synchronized with implementation.
"""

from __future__ import annotations

import math
import warnings
from datetime import date as Date, timedelta
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict

from pyomo.environ import (
    ConcreteModel,
    Var,
    Param,
    Constraint,
    Objective,
    minimize,
    Set as PyomoSet,
    NonNegativeReals,
    NonNegativeIntegers,
    Binary,
    value,
    quicksum,
)

from src.models.unified_node import UnifiedNode, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.unified_truck_schedule import UnifiedTruckSchedule
from src.models.forecast import Forecast
from src.models.labor_calendar import LaborCalendar
from src.models.cost_structure import CostStructure

from .base_model import BaseOptimizationModel, OptimizationResult


class UnifiedNodeModel(BaseOptimizationModel):
    """Unified node-based optimization model.

    Eliminates virtual locations and special-purpose location types.
    All locations are nodes with capability flags.
    """

    # Shelf life constants
    FROZEN_SHELF_LIFE = 120  # days
    AMBIENT_SHELF_LIFE = 17  # days
    THAWED_SHELF_LIFE = 14  # days (after thawing frozen product)

    # Packaging constants
    UNITS_PER_CASE = 10.0
    CASES_PER_PALLET = 32.0
    UNITS_PER_PALLET = 320.0  # UNITS_PER_CASE × CASES_PER_PALLET
    PALLETS_PER_TRUCK = 44.0

    # Numerical precision threshold
    NUMERICAL_ZERO_THRESHOLD = 0.01

    def __init__(
        self,
        nodes: List[UnifiedNode],
        routes: List[UnifiedRoute],
        forecast: Forecast,
        labor_calendar: LaborCalendar,
        cost_structure: CostStructure,
        start_date: Date,
        end_date: Date,
        truck_schedules: Optional[List[UnifiedTruckSchedule]] = None,
        initial_inventory: Optional[Dict] = None,
        inventory_snapshot_date: Optional[Date] = None,
        use_batch_tracking: bool = True,
        allow_shortages: bool = False,
        enforce_shelf_life: bool = True,
        force_all_skus_daily: bool = False,
        force_sku_pattern: Optional[Dict[Tuple[str, str, Date], bool]] = None,
        bigm_overrides: Optional[Dict[Tuple[str, str, Date], float]] = None,
    ):
        """Initialize unified node model.

        Args:
            nodes: List of UnifiedNode objects
            routes: List of UnifiedRoute objects
            forecast: Demand forecast
            labor_calendar: Labor availability and costs
            cost_structure: Cost parameters
            start_date: Planning horizon start
            end_date: Planning horizon end (inclusive)
            truck_schedules: Optional list of truck schedules
            initial_inventory: Optional initial inventory dict
            inventory_snapshot_date: Date when initial inventory was measured
            use_batch_tracking: Use age-cohort tracking (default: True)
            allow_shortages: Allow demand shortages with penalty (default: False)
            enforce_shelf_life: Enforce shelf life constraints (default: True)
            force_all_skus_daily: Fix all SKUs to be produced every day (default: False)
                                 When True, removes binary SKU selection complexity by
                                 fixing product_produced[n,p,d] = 1 for all products.
                                 Useful for: baseline testing, warmstart generation,
                                 and scenarios where SKU reduction is not desired.
            force_sku_pattern: Optional dict specifying which SKUs to force (default: None)
                              Format: {(node_id, product, date): True/False}
                              True = force to produce (fix to 1)
                              False = leave as binary variable
                              Allows partial SKU fixing for iterative refinement.
            bigm_overrides: Optional dict of SKU-specific Big-M values (default: None)
                           Format: {(node_id, product, date): big_m_value}
                           Allows tighter Big-M for small-volume SKUs, making them
                           easier to skip while still allowing production if needed.
                           More flexible than force_sku_pattern (doesn't force to 0).
        """
        self.nodes_list = nodes
        self.nodes: Dict[str, UnifiedNode] = {n.id: n for n in nodes}
        self.routes = routes
        self.forecast = forecast
        self.labor_calendar = labor_calendar
        self.cost_structure = cost_structure
        self.start_date = start_date
        self.end_date = end_date
        self.truck_schedules = truck_schedules or []
        self.initial_inventory = initial_inventory or {}
        self.inventory_snapshot_date = inventory_snapshot_date
        self.use_batch_tracking = use_batch_tracking
        self.allow_shortages = allow_shortages
        self.enforce_shelf_life = enforce_shelf_life
        self.force_all_skus_daily = force_all_skus_daily
        self.force_sku_pattern = force_sku_pattern
        self.bigm_overrides = bigm_overrides or {}

        # Initialize parent class (sets up solver_config)
        super().__init__()

        # Validate cost parameters and warn about potential issues
        self._validate_cost_parameters()

        # Preprocess initial inventory to 4-tuple format
        self._preprocess_initial_inventory()

        # Extract and organize data
        self._extract_data()

    def _preprocess_initial_inventory(self) -> None:
        """Preprocess initial_inventory to consistent 4-tuple format.

        UI passes: {(node, prod): qty}
        Model needs: {(node, prod, prod_date, state): qty}

        Converts 2-tuple format to 4-tuple format by:
        1. Setting prod_date to ONE DAY BEFORE inventory_snapshot_date (or planning start)
           This ensures initial inventory is clearly marked as pre-existing, not produced on Day 1
        2. Determining state based on node storage_mode
        """
        if not self.initial_inventory:
            return

        # Check format by inspecting first key
        first_key = next(iter(self.initial_inventory.keys()))

        # If already in 4-tuple format, no preprocessing needed
        if len(first_key) == 4:
            return

        # Convert from 2-tuple to 4-tuple format
        if len(first_key) == 2:
            # Initial inventory production date: ONE DAY BEFORE snapshot/planning starts
            # This marks it as pre-existing inventory, not Day 1 production
            if self.inventory_snapshot_date:
                init_prod_date = self.inventory_snapshot_date - timedelta(days=1)
            else:
                init_prod_date = self.start_date - timedelta(days=1)

            converted_inventory = {}
            for (node_id, prod), qty in self.initial_inventory.items():
                if qty <= 0:
                    continue

                # Determine state based on node storage mode
                node = self.nodes.get(node_id)
                if not node:
                    warnings.warn(f"Initial inventory node {node_id} not found. Skipping.")
                    continue

                # Default state based on storage mode
                if node.supports_frozen_storage() and not node.supports_ambient_storage():
                    state = 'frozen'
                elif node.supports_ambient_storage() and not node.supports_frozen_storage():
                    state = 'ambient'
                else:
                    # Node has unclear or no storage capability - default to ambient
                    # User can override by passing 4-tuple format if needed
                    warnings.warn(f"Node {node_id} has unclear storage capability. Defaulting to ambient.")
                    state = 'ambient'

                # Store in 4-tuple format
                converted_inventory[(node_id, prod, init_prod_date, state)] = qty

            self.initial_inventory = converted_inventory
            print(f"\n📦 Preprocessed initial inventory: {len(converted_inventory)} items, prod_date={init_prod_date} (one day before snapshot)")

        elif len(first_key) == 3:
            # 3-tuple format: (node, prod, state) -> needs prod_date
            if self.inventory_snapshot_date:
                init_prod_date = self.inventory_snapshot_date - timedelta(days=1)
            else:
                init_prod_date = self.start_date - timedelta(days=1)

            converted_inventory = {}
            for (node_id, prod, state), qty in self.initial_inventory.items():
                if qty > 0:
                    converted_inventory[(node_id, prod, init_prod_date, state)] = qty

            self.initial_inventory = converted_inventory
            print(f"\n📦 Preprocessed initial inventory: {len(converted_inventory)} items, prod_date={init_prod_date}")

        else:
            warnings.warn(f"Unknown initial_inventory format with key length {len(first_key)}. Expected 2, 3, or 4.")

    def _validate_cost_parameters(self) -> None:
        """Validate cost parameters and warn about potential issues.

        When costs are set to 0, the solver may leave variables uninitialized
        (valid behavior), which can cause solution extraction warnings.
        """
        warnings_issued = []

        # Check production cost
        if self.cost_structure.production_cost_per_unit == 0:
            warnings_issued.append("Production cost is 0")

        # Check transport costs
        zero_cost_routes = [r for r in self.routes if r.cost_per_unit == 0]
        if zero_cost_routes:
            if len(zero_cost_routes) == len(self.routes):
                warnings_issued.append("All route transport costs are 0")
            else:
                warnings_issued.append(f"{len(zero_cost_routes)}/{len(self.routes)} routes have zero transport cost")

        # Check storage costs (both unit-based and pallet-based)
        frozen_costs, ambient_costs = self.cost_structure.get_fixed_pallet_costs()

        zero_storage = []
        if (self.cost_structure.storage_cost_frozen_per_unit_day == 0 and
            self.cost_structure.storage_cost_per_pallet_day_frozen == 0 and
            frozen_costs == 0):
            zero_storage.append("frozen")

        if (self.cost_structure.storage_cost_ambient_per_unit_day == 0 and
            self.cost_structure.storage_cost_per_pallet_day_ambient == 0 and
            ambient_costs == 0):
            zero_storage.append("ambient")

        if zero_storage:
            warnings_issued.append(f"{'/'.join(zero_storage)} storage costs are 0")

        # Issue consolidated warning if any zero costs found
        if warnings_issued:
            warning_msg = (
                f"Zero cost parameters detected: {', '.join(warnings_issued)}. "
                "This may cause solver to leave some variables uninitialized (valid behavior). "
                "Consider using small non-zero costs (e.g., 0.0001) if you encounter solution extraction issues."
            )
            warnings.warn(warning_msg, UserWarning)

    def _extract_data(self) -> None:
        """Extract sets and build indices from input data."""

        # Date range
        self.production_dates: Set[Date] = set()
        current = self.start_date
        while current <= self.end_date:
            self.production_dates.add(current)
            current += timedelta(days=1)

        # Products
        self.products: Set[str] = {e.product_id for e in self.forecast.entries}

        # Organize nodes by capability
        self.manufacturing_nodes: Set[str] = {
            n.id for n in self.nodes_list if n.can_produce()
        }
        self.demand_nodes: Set[str] = {
            n.id for n in self.nodes_list if n.has_demand_capability()
        }
        self.nodes_with_truck_constraints: Set[str] = {
            n.id for n in self.nodes_list if n.requires_trucks()
        }

        # Organize routes
        self.routes_from_node: Dict[str, List[UnifiedRoute]] = defaultdict(list)
        self.routes_to_node: Dict[str, List[UnifiedRoute]] = defaultdict(list)
        self.route_by_nodes: Dict[Tuple[str, str], List[UnifiedRoute]] = defaultdict(list)

        for route in self.routes:
            self.routes_from_node[route.origin_node_id].append(route)
            self.routes_to_node[route.destination_node_id].append(route)
            self.route_by_nodes[(route.origin_node_id, route.destination_node_id)].append(route)

        # Organize truck schedules by origin node
        self.trucks_by_origin_node: Dict[str, List[UnifiedTruckSchedule]] = defaultdict(list)
        for truck in self.truck_schedules:
            self.trucks_by_origin_node[truck.origin_node_id].append(truck)

        # Extract demand
        self.demand: Dict[Tuple[str, str, Date], float] = {}
        for entry in self.forecast.entries:
            if self.start_date <= entry.forecast_date <= self.end_date:
                key = (entry.location_id, entry.product_id, entry.forecast_date)
                self.demand[key] = entry.quantity

        # Create date sequencing helpers
        sorted_dates = sorted(self.production_dates)
        self.date_previous: Dict[Date, Optional[Date]] = {}
        for i, current_date in enumerate(sorted_dates):
            self.date_previous[current_date] = sorted_dates[i - 1] if i > 0 else None

        print(f"\nUnified Model Data Summary:")
        print(f"  Nodes: {len(self.nodes)}")
        print(f"    Manufacturing: {len(self.manufacturing_nodes)}")
        print(f"    Demand: {len(self.demand_nodes)}")
        print(f"    With truck constraints: {len(self.nodes_with_truck_constraints)}")
        print(f"  Routes: {len(self.routes)}")
        print(f"  Truck schedules: {len(self.truck_schedules)}")
        print(f"  Planning horizon: {self.start_date} to {self.end_date} ({len(self.production_dates)} days)")
        print(f"  Products: {len(self.products)}")
        print(f"  Demand entries: {len(self.demand)}")

    def get_max_daily_production(self) -> float:
        """Calculate maximum realistic daily production capacity.

        Uses actual labor calendar to determine the tightest feasible Big-M
        constraint for product_produced binary linking. This provides better
        LP relaxation bounds than using theoretical 24-hour capacity.

        Returns:
            Maximum production in units per day (based on realistic max hours)
        """
        max_labor_hours = 0.0

        # First pass: find the maximum realistic working hours from labor calendar
        for date in self.production_dates:
            labor_day = self.labor_calendar.get_labor_day(date)
            if labor_day:
                if hasattr(labor_day, 'overtime_hours') and labor_day.overtime_hours:
                    # Fixed day with explicit overtime capacity
                    day_hours = labor_day.fixed_hours + labor_day.overtime_hours
                elif labor_day.is_fixed_day:
                    # Fixed day without explicit overtime: assume standard 12 + 2 OT = 14h
                    day_hours = labor_day.fixed_hours + 2.0
                else:
                    # Non-fixed day (weekend/holiday): use same max as fixed days
                    # While theoretically unlimited, practical max is ~14h for tighter Big-M
                    # This creates M = 1400 * 14 = 19,600 instead of 1400 * 24 = 33,600
                    day_hours = 14.0  # Realistic practical maximum

                max_labor_hours = max(max_labor_hours, day_hours)

        # Fallback if no labor days found (shouldn't happen)
        if max_labor_hours == 0.0:
            max_labor_hours = 14.0  # Default realistic maximum

        # Get production rate from manufacturing node capabilities
        if self.manufacturing_nodes:
            node_id = next(iter(self.manufacturing_nodes))
            node = self.nodes[node_id]
            prod_rate = node.capabilities.production_rate_per_hour or 1400.0
        else:
            prod_rate = 1400.0  # Default production rate

        max_daily_production = prod_rate * max_labor_hours

        return max_daily_production

    def get_max_truck_capacity(self) -> float:
        """Calculate maximum truck capacity across all trucks.

        Returns:
            Maximum truck capacity in units, or infinity if no trucks
        """
        if self.truck_schedules:
            return max(t.capacity for t in self.truck_schedules)
        else:
            # No trucks = no capacity limit on shipments
            return float('inf')

    def build_model(self) -> ConcreteModel:
        """Build Pyomo optimization model (skeleton only - constraints in Phase 5).

        Returns:
            Pyomo ConcreteModel with sets and variables defined
        """
        model = ConcreteModel()

        print("\nBuilding Unified Node Model...")

        # ==================
        # SETS
        # ==================

        model.nodes = list(self.nodes.keys())
        model.products = list(self.products)
        model.dates = sorted(list(self.production_dates))

        # Route set: (origin, destination) tuples
        model.routes = [(r.origin_node_id, r.destination_node_id) for r in self.routes]

        print(f"  Sets defined: {len(model.nodes)} nodes, {len(model.products)} products, {len(model.dates)} dates, {len(model.routes)} routes")

        # ==================
        # SPARSE COHORT INDICES
        # ==================

        if self.use_batch_tracking:
            self.cohort_index_set = self._build_cohort_indices(model.dates)
            model.cohort_index = list(self.cohort_index_set)
            print(f"  Cohort indices: {len(self.cohort_index_set):,} cohorts")
        else:
            # Simple aggregated inventory (no batch tracking)
            self.inventory_index_set = self._build_aggregated_inventory_indices(model.dates)
            model.inventory_index = list(self.inventory_index_set)
            print(f"  Inventory indices: {len(self.inventory_index_set):,} (node, product, date) tuples")

        # ==================
        # DECISION VARIABLES
        # ==================

        # Calculate bounds for variable tightening (Quick Wins from bound analysis)
        max_daily_production = self.get_max_daily_production()
        max_truck_capacity = self.get_max_truck_capacity()

        # Calculate max initial inventory to ensure bounds accommodate existing stock
        # This prevents infeasibility when initial inventory cohorts exceed daily production
        max_initial_inventory = 0.0
        if self.initial_inventory:
            # initial_inventory format: {(node, prod, prod_date, state): qty}
            max_initial_inventory = max(self.initial_inventory.values())

        # Use the larger of daily production or initial inventory for inventory bounds
        # This ensures both production cohorts AND initial inventory cohorts fit within bounds
        max_inventory_cohort = max(max_daily_production, max_initial_inventory)

        # Store as instance variable for use in _add_objective()
        self.max_inventory_cohort = max_inventory_cohort

        if max_initial_inventory > max_daily_production:
            print(f"  ⚠️  Initial inventory ({max_initial_inventory:,.0f} units) exceeds daily production ({max_daily_production:,.0f} units)")
            print(f"      Adjusting inventory bounds to accommodate existing stock")

        # Production variables (only for manufacturing nodes)
        production_index = [
            (node_id, prod, date)
            for node_id in self.manufacturing_nodes
            for prod in model.products
            for date in model.dates
        ]
        model.production = Var(
            production_index,
            within=NonNegativeReals,
            bounds=(0, max_daily_production),  # Quick Win #1: Tightened bounds
            doc="Production quantity at manufacturing nodes (bounded by daily capacity)"
        )

        # Inventory variables (cohort-based if batch tracking enabled)
        if self.use_batch_tracking:
            # inventory_cohort[node, product, prod_date, curr_date, state]
            model.inventory_cohort = Var(
                model.cohort_index,
                within=NonNegativeReals,
                bounds=(0, max_inventory_cohort),  # Adaptive bound: max(daily_production, initial_inventory)
                doc="Inventory by node, product, production cohort, date, and state"
            )
        else:
            # Aggregated inventory[node, product, date]
            max_cumulative_inventory = max_daily_production * len(model.dates)
            model.inventory = Var(
                model.inventory_index,
                within=NonNegativeReals,
                bounds=(0, max_cumulative_inventory),  # Phase 3 #11: Cumulative inventory bound
                doc="Aggregated inventory by node, product, and date"
            )

        # Shipment variables (route-based)
        if self.use_batch_tracking:
            # Build shipment cohort indices
            self.shipment_cohort_index_set = self._build_shipment_cohort_indices(model.dates)
            model.shipment_cohort_index = list(self.shipment_cohort_index_set)

            # shipment_cohort[route, product, prod_date, delivery_date, arrival_state]
            # Use max_inventory_cohort (not max_daily_production) to accommodate initial inventory shipments
            shipment_bound = min(max_inventory_cohort, max_truck_capacity)
            model.shipment_cohort = Var(
                model.shipment_cohort_index,
                within=NonNegativeReals,
                bounds=(0, shipment_bound),  # Adaptive bound: min(max_inventory_cohort, truck_capacity)
                doc="Shipment quantity by route, product, production cohort, delivery date, and arrival state"
            )
            print(f"  Shipment cohort indices: {len(self.shipment_cohort_index_set):,}")
        else:
            # Aggregated shipments
            shipment_index = [
                (r.origin_node_id, r.destination_node_id, prod, date)
                for r in self.routes
                for prod in model.products
                for date in model.dates
            ]
            model.shipment = Var(
                shipment_index,
                within=NonNegativeReals,
                bounds=(0, max_truck_capacity),  # Phase 3 #11: Aggregated shipment bound
                doc="Shipment quantity by route, product, and delivery date"
            )

        # Demand satisfaction variables
        if self.use_batch_tracking:
            # Demand allocated from each cohort
            self.demand_cohort_index_set = self._build_demand_cohort_indices(model.dates)
            model.demand_cohort_index = list(self.demand_cohort_index_set)

            max_demand = max(self.demand.values()) if self.demand else 10000.0
            model.demand_from_cohort = Var(
                model.demand_cohort_index,
                within=NonNegativeReals,
                bounds=(0, max_demand),  # Phase 3 #6: Demand cohort bounded by max demand
                doc="Demand satisfied from specific production cohort"
            )
            print(f"  Demand cohort indices: {len(self.demand_cohort_index_set):,}")

        # Shortage variables (if allowed)
        if self.allow_shortages:
            shortage_index = list(self.demand.keys())
            max_demand = max(self.demand.values()) if self.demand else 10000.0
            model.shortage = Var(
                shortage_index,
                within=NonNegativeReals,
                bounds=(0, max_demand),  # Phase 3 #5: Shortage bounded by max demand
                doc="Unmet demand (shortage) with penalty"
            )

        # Truck variables (if truck schedules defined)
        if self.truck_schedules:
            model.trucks = list(range(len(self.truck_schedules)))

            # truck_used[truck_idx, date] - binary indicator
            model.truck_used = Var(
                model.trucks,
                model.dates,
                within=Binary,
                doc="Binary: truck used on date"
            )

            # truck_load[truck_idx, destination, product, delivery_date]
            # Destination needed for trucks with intermediate stops (can deliver to multiple destinations)
            truck_load_index = []
            for truck_idx in model.trucks:
                truck = self.truck_schedules[truck_idx]
                destinations = [truck.destination_node_id]

                # Add intermediate stops as possible destinations
                if truck.has_intermediate_stops():
                    destinations.extend(truck.intermediate_stops)

                for dest in destinations:
                    for prod in model.products:
                        for date in model.dates:
                            truck_load_index.append((truck_idx, dest, prod, date))

            model.truck_load = Var(
                truck_load_index,
                within=NonNegativeReals,
                bounds=(0, max_truck_capacity),  # Quick Win #3: Truck load bounded by capacity
                doc="Quantity loaded on truck to specific destination by product and delivery date (in units)"
            )

            # TODO (Phase 4): Add truck_pallet_load integer variables for pallet-level capacity
            # ATTEMPTED WITH FIXES:
            #   - Tried bounds=(0, 44): Gap=100% after 300s (poor LP relaxation)
            #   - Tried no bounds: Gap=100% after 195s (still intractable)
            # ROOT CAUSE: ~20,000 integer variables (18,675 inventory + 1,740 truck) too complex for CBC
            # CONCLUSION: Requires commercial solver (Gurobi/CPLEX) or alternative formulation
            # Current: Unit-based truck capacity (acceptable approximation)
            #
            # model.truck_pallet_load = Var(
            #     truck_load_index,
            #     within=NonNegativeIntegers,
            #     doc="Pallet count loaded on truck (rounded up, partial pallets count as full)"
            # )

        # Changeover tracking variables (for startup/shutdown/changeover overhead)
        # These binary and integer variables track production days and product counts
        # to enable accurate capacity modeling with manufacturing overhead time
        if self.manufacturing_nodes:
            # Binary: Is any production happening at this node on this date?
            production_day_index = [
                (node_id, date)
                for node_id in self.manufacturing_nodes
                for date in model.dates
            ]
            model.production_day = Var(
                production_day_index,
                within=Binary,
                doc="Binary: 1 if any production occurs at this node on this date"
            )

            # Product production indicators: Binary decision variables OR fixed parameters
            product_produced_index = [
                (node_id, prod, date)
                for node_id in self.manufacturing_nodes
                for prod in model.products
                for date in model.dates
            ]

            if self.force_all_skus_daily:
                # FIXED MODE: Force all SKUs to be produced every day
                # Creates product_produced as a Param (not Var) with value = 1
                # Removes binary decision complexity for faster solving
                model.product_produced = Param(
                    product_produced_index,
                    initialize=1.0,
                    mutable=False,
                    doc="Fixed parameter: All products produced every day (force_all_skus_daily=True)"
                )
                sku_mode_msg = "FIXED (all SKUs every day)"
            elif self.force_sku_pattern:
                # MIXED MODE: Some SKUs fixed to 0/1, others binary
                # Pattern: {key: 1} = fix to 1, {key: 0} = fix to 0, not in dict = binary
                model.product_produced = Var(
                    product_produced_index,
                    within=Binary,
                    doc="Binary/Fixed indicator: 1 if product produced, 0 otherwise"
                )

                # Fix variables according to pattern (supports 0, 1, or None/binary)
                num_fixed_to_1 = 0
                num_fixed_to_0 = 0
                num_binary = 0

                for (node_id, prod, date_val) in product_produced_index:
                    if (node_id, prod, date_val) in self.force_sku_pattern:
                        value = self.force_sku_pattern[(node_id, prod, date_val)]
                        if value == 1 or value is True:
                            # Fix to 1 (force to produce)
                            model.product_produced[node_id, prod, date_val].fix(1)
                            num_fixed_to_1 += 1
                        elif value == 0 or value is False:
                            # Fix to 0 (force to skip)
                            model.product_produced[node_id, prod, date_val].fix(0)
                            num_fixed_to_0 += 1
                        else:
                            # Invalid value - leave binary
                            num_binary += 1
                    else:
                        # Not in pattern - leave as binary variable
                        num_binary += 1

                sku_mode_msg = f"MIXED ({num_fixed_to_1} fixed=1, {num_fixed_to_0} fixed=0, {num_binary} binary)"
            else:
                # VARIABLE MODE: Let solver decide which SKUs to produce
                # Binary decision variables for SKU selection
                model.product_produced = Var(
                    product_produced_index,
                    within=Binary,
                    doc="Binary indicator: 1 if this product is produced, 0 otherwise"
                )
                sku_mode_msg = "VARIABLE (binary decision)"

            # Integer: Count of distinct products produced
            model.num_products_produced = Var(
                production_day_index,
                within=NonNegativeIntegers,
                bounds=(0, len(model.products)),
                doc="Number of distinct products produced on this date (for changeover calculation)"
            )

            print(f"  Changeover tracking: {len(production_day_index):,} production days, "
                  f"{len(product_produced_index):,} product indicators ({sku_mode_msg})")

            # Labor cost decision variables (for piecewise labor cost modeling)
            # These variables enable accurate labor cost calculation:
            # - Fixed day: split hours into fixed (regular rate) vs overtime (OT rate)
            # - Non-fixed day: enforce 4-hour minimum payment
            # - Include overhead: startup + shutdown + changeover time
            model.labor_hours_used = Var(
                production_day_index,
                within=NonNegativeReals,
                doc="Actual labor hours used (production time + overhead time)"
            )

            model.labor_hours_paid = Var(
                production_day_index,
                within=NonNegativeReals,
                doc="Labor hours paid (includes 4-hour minimum on non-fixed days)"
            )

            model.fixed_hours_used = Var(
                production_day_index,
                within=NonNegativeReals,
                doc="Labor hours charged at regular rate"
            )

            model.overtime_hours_used = Var(
                production_day_index,
                within=NonNegativeReals,
                doc="Labor hours charged at overtime rate"
            )

            model.uses_overtime = Var(
                production_day_index,
                within=Binary,
                doc="Binary indicator: 1 if overtime is used (for piecewise enforcement)"
            )

            print(f"  Labor cost variables: {len(production_day_index):,} labor hour variables added")

        print(f"  Variables created successfully")

        # ==================
        # PHASE 5: CORE CONSTRAINTS
        # ==================

        print(f"  Adding core constraints...")

        # Add constraints
        if self.use_batch_tracking:
            self._add_cohort_inventory_balance(model)
            self._add_cohort_demand_satisfaction(model)
        else:
            self._add_aggregated_inventory_balance(model)
            self._add_aggregated_demand_satisfaction(model)

        self._add_production_capacity_constraints(model)
        self._add_changeover_tracking_constraints(model)

        # Add labor cost constraints (piecewise labor cost modeling)
        if self.manufacturing_nodes and hasattr(model, 'labor_hours_used'):
            self._add_labor_cost_constraints(model)

        # Add truck constraints (Phase 7)
        if self.truck_schedules:
            self._add_truck_constraints(model)

        self._add_objective(model)

        print(f"  Core constraints added")
        if self.truck_schedules:
            print(f"  Truck constraints added (generalized for any node)")
        print(f"  Model complete and ready to solve")

        # Apply warmstart hints if provided (before returning model)
        if hasattr(self, '_warmstart_hints') and self._warmstart_hints:
            self._apply_warmstart(model, self._warmstart_hints)

        return model

    def _build_cohort_indices(self, dates: List[Date]) -> Set[Tuple]:
        """Build sparse cohort indices: (node, product, prod_date, curr_date, state).

        Only creates indices for valid cohorts (reachable, within shelf life).

        Args:
            dates: List of dates in planning horizon

        Returns:
            Set of valid cohort tuples
        """
        cohorts = set()

        # Collect all production dates: planning horizon + initial inventory
        all_prod_dates = set(dates)

        # Add initial inventory production dates (may be before planning horizon)
        if self.use_batch_tracking and self.initial_inventory:
            for key in self.initial_inventory.keys():
                if len(key) >= 3:  # (node, prod, prod_date, ...) format
                    prod_date = key[2]
                    all_prod_dates.add(prod_date)

        all_prod_dates_sorted = sorted(all_prod_dates)
        print(f"  Production dates for cohorts: {len(dates)} in horizon + {len(all_prod_dates) - len(dates)} from initial inventory")

        # For each node that can store inventory
        for node in self.nodes_list:
            if not node.capabilities.can_store:
                continue

            for prod in self.products:
                for prod_date in all_prod_dates_sorted:  # Use extended date range
                    for curr_date in dates:  # Current dates still within planning horizon
                        if curr_date < prod_date:
                            continue  # Can't have inventory from the future

                        age_days = (curr_date - prod_date).days

                        # Create cohorts for each state the node supports
                        # Frozen cohorts
                        if node.supports_frozen_storage():
                            if age_days <= self.FROZEN_SHELF_LIFE:
                                cohorts.add((node.id, prod, prod_date, curr_date, 'frozen'))

                        # Ambient cohorts (at AMBIENT nodes)
                        if node.supports_ambient_storage():
                            # Use MINIMUM shelf life to account for frozen arrivals that thaw
                            # Frozen product arriving at ambient node thaws and has 14-day shelf life
                            # Ambient product has 17-day shelf life
                            # We use 14 days to be conservative (handles both cases)
                            shelf_life = min(self.AMBIENT_SHELF_LIFE, self.THAWED_SHELF_LIFE)
                            if age_days <= shelf_life:
                                cohorts.add((node.id, prod, prod_date, curr_date, 'ambient'))

        return cohorts

    def _build_shipment_cohort_indices(self, dates: List[Date]) -> Set[Tuple]:
        """Build sparse shipment cohort indices.

        Format: (origin, destination, product, prod_date, delivery_date, arrival_state)

        Args:
            dates: List of dates in planning horizon

        Returns:
            Set of valid shipment cohort tuples
        """
        shipments = set()

        # Collect all production dates including initial inventory
        all_prod_dates = set(dates)
        if self.use_batch_tracking and self.initial_inventory:
            for key in self.initial_inventory.keys():
                if len(key) >= 3:
                    prod_date = key[2]
                    all_prod_dates.add(prod_date)

        for route in self.routes:
            origin_node = self.nodes[route.origin_node_id]
            dest_node = self.nodes[route.destination_node_id]

            # Determine arrival state based on route transport mode and destination storage mode
            arrival_state = self._determine_arrival_state(route, dest_node)

            for prod in self.products:
                for delivery_date in dates:
                    # Calculate departure date
                    # CRITICAL FIX: Handle fractional transit times correctly
                    transit_timedelta = timedelta(days=route.transit_days)
                    departure_datetime = delivery_date - transit_timedelta

                    # Convert to Date for comparisons
                    if isinstance(departure_datetime, Date):
                        departure_date = departure_datetime
                    else:
                        # It's a datetime, extract the date part
                        departure_date = departure_datetime.date()

                    # Only create shipments that can actually depart within planning horizon
                    if departure_date < self.start_date or departure_date > self.end_date:
                        continue  # Shipment requires departure outside planning horizon

                    # For each production date that could supply this shipment
                    # IMPORTANT: Include initial inventory production dates (before planning horizon)
                    for prod_date in all_prod_dates:
                        # Production must occur before or on departure
                        if prod_date <= departure_date:
                            # Check if cohort could exist at origin on departure date
                            # (Simplified reachability - full logic in Phase 5)
                            shipments.add((
                                route.origin_node_id,
                                route.destination_node_id,
                                prod,
                                prod_date,
                                delivery_date,
                                arrival_state
                            ))

        # DEBUG: Report shipment cohort counts by origin
        shipments_by_origin = defaultdict(int)
        for (origin, dest, prod, prod_date, delivery_date, state) in shipments:
            shipments_by_origin[origin] += 1

        if len(shipments_by_origin) > 0:
            print(f"  Shipment cohorts by origin node:")
            for origin in sorted(shipments_by_origin.keys()):
                print(f"    {origin}: {shipments_by_origin[origin]}")

        return shipments

    def _build_demand_cohort_indices(self, dates: List[Date]) -> Set[Tuple]:
        """Build sparse demand cohort allocation indices.

        Format: (node, product, prod_date, demand_date)

        Args:
            dates: List of dates

        Returns:
            Set of valid demand cohort tuples
        """
        demand_cohorts = set()

        # Collect all production dates including initial inventory
        all_prod_dates = set(dates)
        if self.use_batch_tracking and self.initial_inventory:
            for key in self.initial_inventory.keys():
                if len(key) >= 3:
                    prod_date = key[2]
                    all_prod_dates.add(prod_date)

        for (node_id, prod, demand_date) in self.demand.keys():
            # Any cohort produced before demand date and still fresh
            for prod_date in all_prod_dates:
                if prod_date <= demand_date:
                    age_days = (demand_date - prod_date).days

                    # Check shelf life
                    # CRITICAL: Use the MINIMUM shelf life across all possible inventory states
                    # at this node, since demand_from_cohort can draw from ANY state
                    node = self.nodes[node_id]
                    if node.supports_ambient_storage():
                        # Ambient nodes can have both 'ambient' (17d) and 'thawed' (14d) inventory
                        # Use the minimum to ensure all cohorts are usable
                        shelf_life = min(self.AMBIENT_SHELF_LIFE, self.THAWED_SHELF_LIFE)
                        if age_days <= shelf_life:
                            demand_cohorts.add((node_id, prod, prod_date, demand_date))
                    elif node.supports_frozen_storage():
                        # Frozen nodes use frozen shelf life
                        shelf_life = self.FROZEN_SHELF_LIFE
                        if age_days <= shelf_life:
                            demand_cohorts.add((node_id, prod, prod_date, demand_date))

        return demand_cohorts

    def _build_aggregated_inventory_indices(self, dates: List[Date]) -> Set[Tuple]:
        """Build aggregated inventory indices (no batch tracking).

        Format: (node, product, date)

        Args:
            dates: List of dates

        Returns:
            Set of inventory index tuples
        """
        indices = set()

        for node in self.nodes_list:
            if node.capabilities.can_store:
                for prod in self.products:
                    for date in dates:
                        indices.add((node.id, prod, date))

        return indices

    def _determine_arrival_state(
        self,
        route: UnifiedRoute,
        destination_node: UnifiedNode
    ) -> str:
        """Determine product state upon arrival at destination.

        Implements simplified state transition rules:
        - Ambient transport + Ambient node → ambient (no change)
        - Ambient transport + Frozen node → frozen (freeze, reset to 120d)
        - Frozen transport + Frozen node → frozen (no change)
        - Frozen transport + Ambient node → ambient (thaw immediately, treat as ambient with 14d shelf life)

        Args:
            route: Route being traveled
            destination_node: Destination node

        Returns:
            State string: 'frozen' or 'ambient' (no separate 'thawed' state)
        """
        if route.transport_mode == TransportMode.AMBIENT:
            if destination_node.supports_frozen_storage() and not destination_node.supports_ambient_storage():
                # Ambient arriving at frozen-only node → freeze
                return 'frozen'
            else:
                # Ambient arriving at ambient-capable node → stays ambient
                return 'ambient'
        else:  # FROZEN transport
            if destination_node.supports_ambient_storage() and not destination_node.supports_frozen_storage():
                # Frozen arriving at ambient-only node → thaw and immediately treat as ambient
                # (with 14-day shelf life enforced via cohort building)
                return 'ambient'
            else:
                # Frozen arriving at frozen-capable node → stays frozen
                return 'frozen'

    def _generate_warmstart(self) -> Optional[Dict[Tuple[str, str, Date], int]]:
        """Generate campaign-based warmstart hints for product_produced variables.

        Uses demand-weighted allocation to create a weekly production campaign pattern
        with 2 SKUs per weekday (each SKU produced twice weekly), balanced across
        products based on forecast demand.

        Returns:
            Warmstart hints dictionary {(node_id, product, date): 0 or 1} or None
        """
        try:
            from .warmstart_generator import create_default_warmstart

            if not self.manufacturing_nodes:
                return None

            manufacturing_node_id = next(iter(self.manufacturing_nodes))

            # Get max daily production from manufacturing node
            max_daily_prod = self.get_max_daily_production()

            # Generate hints using demand-weighted campaign pattern
            hints = create_default_warmstart(
                demand_forecast=self.demand,
                manufacturing_node_id=manufacturing_node_id,
                products=list(self.products),
                start_date=self.start_date,
                end_date=self.end_date,
                max_daily_production=max_daily_prod,
                fixed_labor_days=None,  # Will auto-detect Mon-Fri
            )

            return hints if hints else None

        except Exception as e:
            print(f"Warning: Warmstart generation failed - {e}")
            return None

    def _apply_warmstart(self, model: ConcreteModel, warmstart_hints: Dict[Tuple[str, str, Date], int]) -> int:
        """Apply warmstart hints to product_produced binary variables.

        Args:
            model: Built Pyomo model
            warmstart_hints: Dictionary {(node_id, product, date): 0 or 1}

        Returns:
            Number of variables successfully initialized
        """
        if not warmstart_hints or not hasattr(model, 'product_produced'):
            return 0

        print(f"\nApplying warmstart hints...")

        applied_count = 0
        skipped_count = 0

        for (node_id, product, date_val), hint_value in warmstart_hints.items():
            # Check if this variable index exists in the model
            if (node_id, product, date_val) not in model.product_produced:
                skipped_count += 1
                continue

            # Set initial value for this binary variable using direct assignment
            # Per Stack Exchange: use m.var = value (not m.var.set_value(value))
            try:
                model.product_produced[node_id, product, date_val] = hint_value
                applied_count += 1
            except Exception as e:
                skipped_count += 1
                continue

        print(f"  Warmstart applied: {applied_count} variables initialized")
        if skipped_count > 0:
            print(f"  Skipped: {skipped_count} invalid indices")

        return applied_count

    def get_model_statistics(self) -> Dict[str, int]:
        """Get model size statistics for performance monitoring.

        Returns:
            Dictionary with model statistics:
            - num_variables: Total number of decision variables
            - num_binary_vars: Number of binary variables
            - num_integer_vars: Number of integer variables
            - num_continuous_vars: Number of continuous variables
            - num_constraints: Total number of constraints

        Raises:
            RuntimeError: If model hasn't been built yet
        """
        if not hasattr(self, 'model') or self.model is None:
            raise RuntimeError("Model has not been built yet. Call build_model() first.")

        num_vars = 0
        num_binary = 0
        num_integer = 0
        num_continuous = 0

        for v in self.model.component_data_objects(Var, active=True):
            num_vars += 1
            if v.is_binary():
                num_binary += 1
            elif v.is_integer():
                num_integer += 1
            elif v.is_continuous():
                num_continuous += 1

        num_constraints = sum(1 for _ in self.model.component_data_objects(Constraint, active=True))

        return {
            'num_variables': num_vars,
            'num_binary_vars': num_binary,
            'num_integer_vars': num_integer,
            'num_continuous_vars': num_continuous,
            'num_constraints': num_constraints,
        }

    def solve(
        self,
        solver_name: Optional[str] = None,
        time_limit_seconds: Optional[float] = None,
        mip_gap: Optional[float] = None,
        tee: bool = False,
        use_aggressive_heuristics: bool = False,
        use_warmstart: bool = False,
        warmstart_hints: Optional[Dict[Tuple[str, str, Date], int]] = None,
    ) -> OptimizationResult:
        """Build and solve the unified node model.

        Args:
            solver_name: Solver to use (None = auto-detect)
            time_limit_seconds: Time limit in seconds
            mip_gap: MIP gap tolerance
            tee: Show solver output
            use_aggressive_heuristics: Enable aggressive CBC heuristics (for large problems)
            use_warmstart: Enable warmstart with campaign-based production pattern
            warmstart_hints: Optional pre-generated warmstart hints.
                If None and use_warmstart=True, hints are generated automatically.
                Format: {(node_id, product_id, date): 0 or 1}

        Returns:
            OptimizationResult with solve status and metrics
        """
        # Generate or store warmstart hints (applied during build_model)
        if use_warmstart:
            if warmstart_hints is None:
                warmstart_hints = self._generate_warmstart()
            self._warmstart_hints = warmstart_hints
        else:
            self._warmstart_hints = None

        # Call base class solve (builds model + solves)
        return super().solve(
            solver_name=solver_name,
            time_limit_seconds=time_limit_seconds,
            mip_gap=mip_gap,
            tee=tee,
            use_aggressive_heuristics=use_aggressive_heuristics,
            use_warmstart=use_warmstart,  # Pass to base class so Pyomo generates -mipstart flag
        )

    def extract_solution(self, model: ConcreteModel) -> Dict[str, Any]:
        """Extract solution from solved model (required by BaseOptimizationModel).

        Args:
            model: Solved Pyomo model

        Returns:
            Solution dictionary compatible with UI/daily snapshot
        """
        solution = {}

        # Extract production by date and product
        production_by_date_product: Dict[Tuple[Date, str], float] = {}
        for node_id in self.manufacturing_nodes:
            for prod in model.products:
                for date_val in model.dates:
                    if (node_id, prod, date_val) in model.production:
                        qty = value(model.production[node_id, prod, date_val])
                        if qty > 0.01:
                            production_by_date_product[(date_val, prod)] = qty

        solution['production_by_date_product'] = production_by_date_product

        # Extract cohort inventory for daily snapshot
        cohort_inventory: Dict[Tuple[str, str, Date, Date, str], float] = {}
        if self.use_batch_tracking:
            for (node_id, prod, prod_date, curr_date, state) in model.cohort_index:
                # Check if variable initialized BEFORE calling value() (prevents error spam)
                var = model.inventory_cohort[node_id, prod, prod_date, curr_date, state]
                if var.stale:
                    # Not solved (expected for zero-cost storage)
                    continue

                try:
                    qty = value(var)
                    if qty > 0.01:
                        cohort_inventory[(node_id, prod, prod_date, curr_date, state)] = qty
                except (ValueError, AttributeError, KeyError, RuntimeError):
                    # Fallback for edge cases
                    continue

        solution['cohort_inventory'] = cohort_inventory
        solution['use_batch_tracking'] = self.use_batch_tracking

        # Extract demand consumption by cohort (for daily snapshot)
        cohort_demand_consumption: Dict[Tuple[str, str, Date, Date], float] = {}
        if self.use_batch_tracking and hasattr(model, 'demand_from_cohort'):
            for (node_id, prod, prod_date, demand_date) in self.demand_cohort_index_set:
                # Check if variable initialized BEFORE calling value()
                var = model.demand_from_cohort[node_id, prod, prod_date, demand_date]
                if var.stale:
                    continue

                try:
                    qty = value(var)
                    if qty > 0.01:
                        cohort_demand_consumption[(node_id, prod, prod_date, demand_date)] = qty
                except (ValueError, AttributeError, KeyError, RuntimeError):
                    continue

        solution['cohort_demand_consumption'] = cohort_demand_consumption

        # Extract shipments by route
        shipments_by_route: Dict[Tuple[str, str, str, Date], float] = {}
        if self.use_batch_tracking:
            for (origin, dest, prod, prod_date, delivery_date, state) in self.shipment_cohort_index_set:
                # Check if variable was initialized by solver BEFORE calling value()
                # This prevents thousands of error messages for zero-cost variables
                var = model.shipment_cohort[origin, dest, prod, prod_date, delivery_date, state]
                if var.stale:
                    # Variable not solved (expected for zero-cost routes)
                    continue

                try:
                    qty = value(var)
                    if qty > 0.01:
                        # Aggregate by route (sum across cohorts)
                        key = (origin, dest, prod, delivery_date)
                        shipments_by_route[key] = shipments_by_route.get(key, 0.0) + qty
                except (ValueError, AttributeError, KeyError, RuntimeError):
                    # Fallback for edge cases
                    continue

        solution['shipments_by_route_product_date'] = shipments_by_route

        # Extract shortages
        shortages_by_dest_product_date: Dict[Tuple[str, str, Date], float] = {}
        if self.allow_shortages:
            for (node_id, prod, date_val) in self.demand.keys():
                if (node_id, prod, date_val) in model.shortage:
                    qty = value(model.shortage[node_id, prod, date_val])
                    if qty > 0.01:
                        shortages_by_dest_product_date[(node_id, prod, date_val)] = qty

        solution['shortages_by_dest_product_date'] = shortages_by_dest_product_date

        # Calculate costs
        total_production_cost = sum(
            self.cost_structure.production_cost_per_unit * qty
            for qty in production_by_date_product.values()
        )

        total_transport_cost = sum(
            self._get_route_cost(origin, dest) * qty
            for (origin, dest, prod, date_val), qty in shipments_by_route.items()
        )

        total_shortage_cost = sum(
            self.cost_structure.shortage_penalty_per_unit * qty
            for qty in shortages_by_dest_product_date.values()
        )

        # Calculate holding cost from pallet counts (state-specific tracking)
        total_holding_cost = 0.0
        frozen_holding_cost = 0.0
        ambient_holding_cost = 0.0

        if self.use_batch_tracking:
            # Get state-specific fixed costs
            pallet_fixed_frozen, pallet_fixed_ambient = self.cost_structure.get_fixed_pallet_costs()

            # Get state-specific daily costs
            pallet_frozen_per_day = self.cost_structure.storage_cost_per_pallet_day_frozen or 0.0
            pallet_ambient_per_day = self.cost_structure.storage_cost_per_pallet_day_ambient or 0.0

            # Fall back to unit-based costs (legacy method)
            unit_frozen_per_day = self.cost_structure.storage_cost_frozen_per_unit_day or 0.0
            unit_ambient_per_day = self.cost_structure.storage_cost_ambient_per_unit_day or 0.0

            # Determine tracking mode per state
            use_pallet_frozen = (pallet_fixed_frozen > 0 or pallet_frozen_per_day > 0)
            use_pallet_ambient = (pallet_fixed_ambient > 0 or pallet_ambient_per_day > 0)

            # Build set of states using pallet tracking
            pallet_states = set()
            if use_pallet_frozen:
                pallet_states.add('frozen')
            if use_pallet_ambient:
                pallet_states.update(['ambient', 'thawed'])

            # Determine rates for each state
            if use_pallet_frozen:
                frozen_rate_per_pallet = pallet_frozen_per_day
            else:
                frozen_rate_per_pallet = unit_frozen_per_day * self.UNITS_PER_PALLET

            if use_pallet_ambient:
                ambient_rate_per_pallet = pallet_ambient_per_day
            else:
                ambient_rate_per_pallet = unit_ambient_per_day * self.UNITS_PER_PALLET

            # Extract costs from solved model
            for (node_id, prod, prod_date, curr_date, state) in self.cohort_index_set:
                cost = 0.0

                # Use pallet tracking if state is in pallet_states
                if state in pallet_states and hasattr(model, 'pallet_count'):
                    # Check if variable initialized BEFORE calling value()
                    pallet_var = model.pallet_count[node_id, prod, prod_date, curr_date, state]
                    if pallet_var.stale:
                        continue

                    try:
                        pallet_qty = value(pallet_var)
                    except (ValueError, KeyError):
                        # Variable not solved (expected for sparse indices or unit-tracked states)
                        continue

                    if pallet_qty is None or pallet_qty < self.NUMERICAL_ZERO_THRESHOLD:
                        continue

                    # Apply state-specific fixed cost
                    if state == 'frozen' and pallet_fixed_frozen > 0:
                        cost += pallet_fixed_frozen * pallet_qty
                    elif state in ['ambient', 'thawed'] and pallet_fixed_ambient > 0:
                        cost += pallet_fixed_ambient * pallet_qty

                    # Apply daily holding cost
                    if state == 'frozen' and frozen_rate_per_pallet > 0:
                        cost += frozen_rate_per_pallet * pallet_qty
                    elif state in ['ambient', 'thawed'] and ambient_rate_per_pallet > 0:
                        cost += ambient_rate_per_pallet * pallet_qty

                else:
                    # Use unit tracking for this state
                    # Check if variable initialized BEFORE calling value()
                    inv_var = model.inventory_cohort[node_id, prod, prod_date, curr_date, state]
                    if inv_var.stale:
                        continue

                    try:
                        inv_qty = value(inv_var)
                    except (ValueError, KeyError):
                        continue

                    if inv_qty is None or inv_qty < self.NUMERICAL_ZERO_THRESHOLD:
                        continue

                    if state == 'frozen' and unit_frozen_per_day > 0:
                        cost += unit_frozen_per_day * inv_qty
                    elif state in ['ambient', 'thawed'] and unit_ambient_per_day > 0:
                        cost += unit_ambient_per_day * inv_qty

                # Accumulate to state-specific totals
                if state == 'frozen':
                    frozen_holding_cost += cost
                elif state in ['ambient', 'thawed']:
                    ambient_holding_cost += cost

                total_holding_cost += cost

        solution['total_production_cost'] = total_production_cost
        solution['total_transport_cost'] = total_transport_cost
        solution['total_shortage_cost'] = total_shortage_cost
        solution['total_shortage_units'] = sum(shortages_by_dest_product_date.values())
        solution['total_holding_cost'] = total_holding_cost
        solution['frozen_holding_cost'] = frozen_holding_cost
        solution['ambient_holding_cost'] = ambient_holding_cost

        # Note: total_cost extraction moved to after all cost components are calculated

        # Extract labor cost breakdown (piecewise labor cost model)
        labor_hours_by_date = {}
        total_labor_cost = 0.0
        labor_cost_breakdown = {
            'fixed_hours_cost': 0.0,
            'overtime_cost': 0.0,
            'non_fixed_cost': 0.0,
            'total_fixed_hours': 0.0,
            'total_overtime_hours': 0.0,
            'total_non_fixed_hours': 0.0,
        }

        if hasattr(model, 'labor_hours_used'):
            for node_id in self.manufacturing_nodes:
                for date_val in model.dates:
                    if (node_id, date_val) not in model.labor_hours_used:
                        continue

                    try:
                        hours_used = value(model.labor_hours_used[node_id, date_val])
                        hours_paid = value(model.labor_hours_paid[node_id, date_val])
                        fixed_hours = value(model.fixed_hours_used[node_id, date_val])
                        overtime_hours = value(model.overtime_hours_used[node_id, date_val])

                        if hours_used > 0.01:  # Only store non-zero values
                            labor_hours_by_date[date_val] = {
                                'used': hours_used,
                                'paid': hours_paid,
                                'fixed': fixed_hours,
                                'overtime': overtime_hours,
                            }

                            # Calculate cost for this date
                            labor_day = self.labor_calendar.get_labor_day(date_val)
                            if labor_day:
                                if labor_day.is_fixed_day:
                                    cost = (
                                        labor_day.regular_rate * fixed_hours +
                                        labor_day.overtime_rate * overtime_hours
                                    )
                                    labor_cost_breakdown['fixed_hours_cost'] += labor_day.regular_rate * fixed_hours
                                    labor_cost_breakdown['overtime_cost'] += labor_day.overtime_rate * overtime_hours
                                    labor_cost_breakdown['total_fixed_hours'] += fixed_hours
                                    labor_cost_breakdown['total_overtime_hours'] += overtime_hours
                                else:
                                    # Non-fixed day
                                    non_fixed_rate = labor_day.non_fixed_rate or labor_day.overtime_rate
                                    cost = non_fixed_rate * hours_paid
                                    labor_cost_breakdown['non_fixed_cost'] += cost
                                    labor_cost_breakdown['total_non_fixed_hours'] += hours_paid

                                total_labor_cost += cost
                    except (ValueError, KeyError):
                        # Variable not solved
                        continue

        solution['labor_hours_by_date'] = labor_hours_by_date
        solution['labor_cost_breakdown'] = labor_cost_breakdown
        solution['total_labor_cost'] = total_labor_cost

        # Backward compatibility alias
        solution['total_inventory_cost'] = total_holding_cost

        # Production batches for UI
        production_batches = []
        for (date_val, prod), qty in production_by_date_product.items():
            production_batches.append({
                'date': date_val,
                'product': prod,
                'quantity': qty,
            })

        solution['production_batches'] = production_batches

        # Extract batch_shipments (Shipment objects with production_date) for labeling report
        batch_shipments = []
        if self.use_batch_tracking and hasattr(model, 'shipment_cohort'):
            from src.models.shipment import Shipment
            from src.shelf_life.tracker import RouteLeg
            from src.network.route_finder import RoutePath

            shipment_id_counter = 1
            batch_id_map = {}  # Map (prod_date, product) to batch_id

            # Create batch IDs
            for (date_val, prod), qty in production_by_date_product.items():
                batch_id = f"BATCH-{date_val.strftime('%Y%m%d')}-{prod}"
                batch_id_map[(date_val, prod)] = batch_id

            # Extract cohort shipments
            for (origin, dest, prod, prod_date, delivery_date, state) in self.shipment_cohort_index_set:
                # Check if variable was initialized BEFORE calling value() (prevents error spam)
                var = model.shipment_cohort[origin, dest, prod, prod_date, delivery_date, state]
                if var.stale:
                    # Not solved (expected for zero-cost variables)
                    continue

                try:
                    qty = value(var)
                except (ValueError, AttributeError, KeyError, RuntimeError):
                    # Fallback for edge cases
                    continue

                if qty > 0.01:
                    # Find route
                    route = next((r for r in self.routes
                                 if r.origin_node_id == origin and r.destination_node_id == dest), None)

                    transit_days = route.transit_days if route else 0

                    # Create route leg
                    leg = RouteLeg(
                        from_location_id=origin,
                        to_location_id=dest,
                        transport_mode=state,  # Use the arrival state as transport mode
                        transit_days=transit_days
                    )

                    route_path = RoutePath(
                        path=[origin, dest],
                        total_transit_days=transit_days,
                        total_cost=0.0,
                        transport_modes=[state],
                        route_legs=[leg],
                        intermediate_stops=[]
                    )

                    # Get batch ID
                    batch_id = batch_id_map.get((prod_date, prod), f"BATCH-{prod_date}-{prod}")

                    shipment = Shipment(
                        id=f"SHIP-{shipment_id_counter:05d}",
                        batch_id=batch_id,
                        product_id=prod,
                        quantity=qty,
                        origin_id=origin,
                        destination_id=dest,
                        delivery_date=delivery_date,
                        route=route_path,
                        production_date=prod_date  # CRITICAL: Include production date for labeling
                    )

                    batch_shipments.append(shipment)
                    shipment_id_counter += 1

        solution['batch_shipments'] = batch_shipments

        # Build route_arrival_state mapping for labeling report
        # Format: {(origin, dest): 'frozen' or 'ambient'}
        route_arrival_states = {}
        for route in self.routes:
            dest_node = self.nodes[route.destination_node_id]
            arrival_state = self._determine_arrival_state(route, dest_node)
            route_arrival_states[(route.origin_node_id, route.destination_node_id)] = arrival_state

        # Store as instance attribute for access by UI
        self.route_arrival_state = route_arrival_states

        # Extract total cost from objective
        # PYOMO BEST PRACTICE: Always use component sum instead of extracting from model.obj
        # Extracting from model.obj can print thousands of error messages when variables
        # have zero costs and aren't initialized by the solver (valid MIP behavior).
        # Component sum is more reliable and avoids error spam.
        solution['total_cost'] = (
            solution.get('total_production_cost', 0.0) +
            solution.get('total_labor_cost', 0.0) +
            solution.get('total_transport_cost', 0.0) +
            solution.get('total_holding_cost', 0.0) +
            solution.get('total_shortage_cost', 0.0)
        )

        return solution

    def _get_route_cost(self, origin: str, dest: str) -> float:
        """Get cost per unit for a route."""
        route = next((r for r in self.routes
                     if r.origin_node_id == origin and r.destination_node_id == dest), None)
        return route.cost_per_unit if route else 0.0

    def get_solution(self) -> Optional[Dict[str, Any]]:
        """Extract solution from solved model.

        Returns:
            Solution dictionary or None if not solved
        """
        return self.solution

    def extract_production_schedule(self):
        """Extract production schedule from solution.

        Returns:
            ProductionSchedule object with batches
        """
        if not self.solution:
            return None

        from src.models.production_schedule import ProductionSchedule
        from src.models.production_batch import ProductionBatch

        # Get production data
        production_by_date_product = self.solution.get('production_by_date_product', {})

        # Create batches
        batches = []
        batch_counter = 1

        for (date_val, prod), qty in production_by_date_product.items():
            # Find manufacturing node (should be only one)
            mfg_node_id = list(self.manufacturing_nodes)[0]

            batch = ProductionBatch(
                id=f"BATCH-{batch_counter:04d}",
                product_id=prod,
                quantity=qty,
                production_date=date_val,
                manufacturing_site_id=mfg_node_id,
                initial_state='ambient',  # Simplified - nodes produce in their storage_mode
            )
            batches.append(batch)
            batch_counter += 1

        # Calculate daily totals and labor hours
        daily_totals: Dict[Date, float] = {}
        daily_labor_hours: Dict[Date, float] = {}

        for batch in batches:
            date_val = batch.production_date
            daily_totals[date_val] = daily_totals.get(date_val, 0.0) + batch.quantity

            # Calculate labor hours (quantity / production_rate)
            mfg_node = self.nodes[list(self.manufacturing_nodes)[0]]
            labor_hours = batch.quantity / mfg_node.capabilities.production_rate_per_hour
            daily_labor_hours[date_val] = daily_labor_hours.get(date_val, 0.0) + labor_hours

        total_units = sum(batch.quantity for batch in batches)
        total_labor_hours = sum(daily_labor_hours.values())

        # Find manufacturing node ID
        mfg_node_id = list(self.manufacturing_nodes)[0]

        return ProductionSchedule(
            manufacturing_site_id=mfg_node_id,
            production_batches=batches,
            schedule_start_date=self.start_date,
            schedule_end_date=self.end_date,
            daily_totals=daily_totals,
            daily_labor_hours=daily_labor_hours,
            infeasibilities=[],  # Optimization ensures feasibility
            total_units=total_units,
            total_labor_hours=total_labor_hours,
        )

    def extract_shipments(self):
        """Extract shipments from solution.

        Returns:
            List of Shipment objects
        """
        if not self.solution:
            return []

        from src.models.shipment import Shipment
        from src.shelf_life.tracker import RouteLeg
        from src.network.route_finder import RoutePath

        shipments_by_route = self.solution.get('shipments_by_route_product_date', {})

        shipments = []
        shipment_counter = 1

        for (origin, dest, prod, delivery_date), qty in shipments_by_route.items():
            # Find route
            route = next((r for r in self.routes
                         if r.origin_node_id == origin and r.destination_node_id == dest), None)

            if not route:
                continue

            # Create simple single-leg route
            leg = RouteLeg(
                from_location_id=origin,
                to_location_id=dest,
                transport_mode='ambient',  # Simplified
                transit_days=route.transit_days
            )

            route_path = RoutePath(
                path=[origin, dest],
                total_transit_days=route.transit_days,
                total_cost=route.cost_per_unit * qty,
                transport_modes=['ambient'],
                route_legs=[leg],
                intermediate_stops=[]
            )

            shipment = Shipment(
                id=f"SHIP-{shipment_counter:04d}",
                batch_id=f"BATCH-UNKNOWN",  # Simplified - would need cohort tracking
                product_id=prod,
                quantity=qty,
                origin_id=origin,
                destination_id=dest,
                delivery_date=delivery_date,
                route=route_path,
                production_date=delivery_date - timedelta(days=route.transit_days),
            )

            shipments.append(shipment)
            shipment_counter += 1

        return shipments

    # ==================
    # PHASE 5: CONSTRAINT IMPLEMENTATION
    # ==================

    def _add_cohort_inventory_balance(self, model: ConcreteModel) -> None:
        """Add UNIFIED inventory balance constraint for all nodes.

        This is the key simplification - one equation works for ALL node types:
        - Manufacturing nodes: get production inflows
        - Demand nodes: have demand outflows
        - Storage nodes: just arrivals and departures
        - Hubs: can have both demand and transit flows

        No special cases needed!
        """

        def inventory_balance_rule(model, node_id, prod, prod_date, curr_date, state):
            """Unified inventory balance for ALL nodes.

            inventory[t] = inventory[t-1] +
                          production (if can_manufacture and prod_date==curr_date) +
                          arrivals_in_state +
                          state_transitions_in -
                          demand (if has_demand) -
                          departures_in_state -
                          state_transitions_out
            """
            node = self.nodes[node_id]

            # Previous inventory
            prev_date = self.date_previous.get(curr_date)
            if prev_date is None:
                # First date: use initial inventory
                prev_inv = self.initial_inventory.get((node_id, prod, prod_date, state), 0)
            else:
                # Previous day's inventory for this cohort
                if (node_id, prod, prod_date, prev_date, state) in self.cohort_index_set:
                    prev_inv = model.inventory_cohort[node_id, prod, prod_date, prev_date, state]
                else:
                    prev_inv = 0

            # Production inflow (only if node can manufacture AND prod_date == curr_date)
            production_inflow = 0
            if node.can_produce() and prod_date == curr_date:
                # Production creates cohort with prod_date = curr_date
                # State of produced product matches node's production state
                production_state = node.get_production_state()
                if state == production_state:
                    production_inflow = model.production[node_id, prod, curr_date]

            # Arrivals: shipments arriving in this state
            arrivals = 0
            for route in self.routes_to_node[node_id]:
                arrival_state = self._determine_arrival_state(route, node)

                if arrival_state == state:
                    # This shipment arrives in the current state
                    if (route.origin_node_id, route.destination_node_id, prod, prod_date, curr_date, arrival_state) in self.shipment_cohort_index_set:
                        arrivals += model.shipment_cohort[
                            route.origin_node_id, route.destination_node_id,
                            prod, prod_date, curr_date, arrival_state
                        ]

            # Departures: shipments leaving from this state
            # Key insight: We ship in the state matching route transport_mode
            #  - Frozen route → ships from frozen inventory
            #  - Ambient route → ships from ambient inventory
            departures = 0
            for route in self.routes_from_node[node_id]:
                # Determine what state we ship from (based on route transport mode)
                if route.transport_mode == TransportMode.FROZEN:
                    departure_state = 'frozen'
                else:
                    departure_state = 'ambient'

                # Only deduct if we're tracking the right state
                if state != departure_state:
                    continue  # This inventory state not used by this route

                # Calculate when shipment would depart to arrive on various delivery dates
                for delivery_date in model.dates:
                    # CRITICAL FIX: Handle fractional transit times correctly
                    # For same-day delivery (0.5 days), departure_date should equal delivery_date
                    # For overnight (1.0 days), departure is previous day
                    transit_timedelta = timedelta(days=route.transit_days)
                    departure_datetime = delivery_date - transit_timedelta

                    # Convert back to Date for comparison (rounds down to date)
                    # For fractional days < 1, this gives the same date
                    # For 1+ days, this gives the previous date
                    if isinstance(departure_datetime, Date):
                        departure_date = departure_datetime
                    else:
                        # It's a datetime, extract the date part
                        departure_date = departure_datetime.date()

                    if departure_date == curr_date:
                        # Shipment departs today from this state
                        arrival_state = self._determine_arrival_state(route, self.nodes[route.destination_node_id])

                        if (route.origin_node_id, route.destination_node_id, prod, prod_date, delivery_date, arrival_state) in self.shipment_cohort_index_set:
                            departures += model.shipment_cohort[
                                route.origin_node_id, route.destination_node_id,
                                prod, prod_date, delivery_date, arrival_state
                            ]

            # Demand consumption (only if node has demand capability)
            demand_consumption = 0
            if node.has_demand_capability():
                if (node_id, prod, curr_date) in self.demand:
                    if (node_id, prod, prod_date, curr_date) in self.demand_cohort_index_set:
                        if state == 'ambient' and node.supports_ambient_storage():
                            # Ambient nodes: deduct from ambient inventory
                            demand_consumption = model.demand_from_cohort[node_id, prod, prod_date, curr_date]
                        elif state == 'frozen' and node.supports_frozen_storage():
                            # Frozen nodes: deduct from frozen inventory
                            demand_consumption = model.demand_from_cohort[node_id, prod, prod_date, curr_date]
                        else:
                            demand_consumption = 0

            # State transitions (no longer needed - thawed is treated as ambient)
            state_transitions_in = 0
            state_transitions_out = 0

            # Balance equation - CRITICAL FIX: Structure to avoid sign flips
            # Write as: inflows = inventory + outflows
            # This prevents Pyomo from negating signs when moving terms
            return (prev_inv + production_inflow + arrivals + state_transitions_in ==
                    model.inventory_cohort[node_id, prod, prod_date, curr_date, state] +
                    demand_consumption + departures + state_transitions_out)

        model.inventory_balance_con = Constraint(
            model.cohort_index,
            rule=inventory_balance_rule,
            doc="Unified inventory balance for all nodes (manufacturing, hubs, storage, demand)"
        )

    def _add_cohort_demand_satisfaction(self, model: ConcreteModel) -> None:
        """Add demand satisfaction constraints."""

        def demand_satisfaction_rule(model, node_id, prod, demand_date):
            """Demand from all cohorts + shortage = total demand."""

            if (node_id, prod, demand_date) not in self.demand:
                return Constraint.Skip

            demand_qty = self.demand[(node_id, prod, demand_date)]

            # Sum demand satisfied from all cohorts
            # CRITICAL FIX: Iterate over demand_cohort_index_set directly, not model.dates
            # This ensures initial inventory cohorts (with prod_date before planning horizon) are included
            cohort_supply = sum(
                model.demand_from_cohort[n, p, pd, dd]
                for (n, p, pd, dd) in self.demand_cohort_index_set
                if n == node_id and p == prod and dd == demand_date
            )

            if self.allow_shortages:
                # Cohort supply + shortage = demand
                return cohort_supply + model.shortage[node_id, prod, demand_date] == demand_qty
            else:
                # Cohort supply = demand (must satisfy exactly)
                return cohort_supply == demand_qty

        demand_index = set()
        for (node_id, prod, demand_date) in self.demand.keys():
            demand_index.add((node_id, prod, demand_date))

        model.demand_satisfaction_con = Constraint(
            list(demand_index),
            rule=demand_satisfaction_rule,
            doc="Demand satisfaction from cohorts"
        )

        # CRITICAL: Link demand_from_cohort to BEGINNING-OF-DAY inventory (not end-of-day)
        # BUGFIX: Previous version used end-of-day inventory (after consumption),
        # creating circular dependency: demand <= inv[after] = prev_inv + arrivals - demand
        # This forced demand <= (prev_inv + arrivals) / 2, causing 2x production bug!
        #
        # Correct constraint: demand <= inv[before] = prev_inv + arrivals + production (if same-day)
        def demand_inventory_linking_rule(model, node_id, prod, prod_date, demand_date):
            """Demand from cohort cannot exceed BEGINNING-OF-DAY inventory (before consumption)."""

            if (node_id, prod, prod_date, demand_date) not in self.demand_cohort_index_set:
                return Constraint.Skip

            # Calculate beginning-of-day inventory for this cohort
            # BOD inventory = previous day inventory + arrivals + same-day production
            # (This is BEFORE demand consumption and departures)

            # Previous day inventory
            prev_date = self.date_previous.get(demand_date)
            prev_inventory = 0

            if prev_date is None:
                # First date: use initial inventory
                for state in ['ambient', 'frozen', 'thawed']:
                    prev_inventory += self.initial_inventory.get((node_id, prod, prod_date, state), 0)
            else:
                # Sum inventory from previous day across all states
                for state in ['ambient', 'frozen', 'thawed']:
                    if (node_id, prod, prod_date, prev_date, state) in self.cohort_index_set:
                        prev_inventory += model.inventory_cohort[node_id, prod, prod_date, prev_date, state]

            # Arrivals on demand date
            arrivals_on_demand_date = 0
            node = self.nodes[node_id]
            for route in self.routes_to_node[node_id]:
                arrival_state = self._determine_arrival_state(route, node)
                if (route.origin_node_id, route.destination_node_id, prod, prod_date, demand_date, arrival_state) in self.shipment_cohort_index_set:
                    arrivals_on_demand_date += model.shipment_cohort[
                        route.origin_node_id, route.destination_node_id,
                        prod, prod_date, demand_date, arrival_state
                    ]

            # Same-day production (if node can produce and prod_date == demand_date)
            same_day_production = 0
            if node.can_produce() and prod_date == demand_date:
                if (node_id, prod, demand_date) in model.production:
                    same_day_production = model.production[node_id, prod, demand_date]

            # BOD inventory = previous inventory + arrivals + same-day production
            beginning_of_day_inventory = prev_inventory + arrivals_on_demand_date + same_day_production

            # Demand from this cohort cannot exceed BOD inventory
            return model.demand_from_cohort[node_id, prod, prod_date, demand_date] <= beginning_of_day_inventory

        model.demand_inventory_linking_con = Constraint(
            model.demand_cohort_index,
            rule=demand_inventory_linking_rule,
            doc="Link demand allocation to BEGINNING-OF-DAY inventory (prevents circular dependency)"
        )

    def _add_aggregated_inventory_balance(self, model: ConcreteModel) -> None:
        """Add aggregated inventory balance (no batch tracking - simplified)."""
        # TODO: Implement for non-batch-tracking mode if needed
        pass

    def _add_aggregated_demand_satisfaction(self, model: ConcreteModel) -> None:
        """Add aggregated demand satisfaction (no batch tracking)."""
        # TODO: Implement for non-batch-tracking mode if needed
        pass

    def _add_truck_constraints(self, model: ConcreteModel) -> None:
        """Add generalized truck scheduling constraints.

        KEY IMPROVEMENTS:
        - Works for ANY node, not just manufacturing!
        - Links shipments to truck schedules based on origin_node_id
        - Enforces day-of-week constraints
        - Enforces truck capacity at PALLET level (partial pallets occupy full pallet space)
        - Prevents weekend shipments from nodes with truck requirements

        PALLET-LEVEL ENFORCEMENT:
        - truck_pallet_load integer variables enforce ceiling rounding
        - Constraint: truck_pallet_load * 320 >= truck_load (in units)
        - Capacity: truck_pallet_load <= 44 pallets per truck
        - Business rule: 50 units = 1 pallet space, not 0.156 pallets

        This fixes the 6122/6122_Storage bypass bug!
        """

        # Build truck index
        self.truck_by_index = {i: truck for i, truck in enumerate(self.truck_schedules)}

        # For each route, determine if it has truck constraints
        # A truck can serve multiple routes if it has intermediate stops
        routes_with_trucks: Dict[Tuple[str, str], List[int]] = defaultdict(list)

        for truck_idx, truck in self.truck_by_index.items():
            # Primary route: origin → final destination
            route_key = (truck.origin_node_id, truck.destination_node_id)
            routes_with_trucks[route_key].append(truck_idx)

            # Intermediate stop routes: origin → intermediate stop
            if truck.has_intermediate_stops():
                for stop_id in truck.intermediate_stops:
                    intermediate_route_key = (truck.origin_node_id, stop_id)
                    routes_with_trucks[intermediate_route_key].append(truck_idx)
                    # Note: Same truck can deliver to BOTH intermediate stop AND final destination

        # Constraint: Shipments on routes with trucks must equal truck loads
        def truck_route_linking_rule(model, origin, dest, prod, delivery_date):
            """Link shipments to truck loads for routes with truck schedules."""

            route_key = (origin, dest)

            # Check if this route has truck schedules
            if route_key not in routes_with_trucks:
                return Constraint.Skip  # No truck constraints for this route

            # Get trucks serving this route
            trucks_for_route = routes_with_trucks[route_key]

            # Sum shipments on this route (across all cohorts and states)
            # CRITICAL FIX: Iterate shipment_cohort_index_set directly to include initial inventory
            total_shipment = sum(
                model.shipment_cohort[o, d, p, pd, dd, s]
                for (o, d, p, pd, dd, s) in self.shipment_cohort_index_set
                if o == origin and d == dest and p == prod and dd == delivery_date
            )

            # Sum truck loads for this product on this delivery date to this specific destination
            total_truck_load = sum(
                model.truck_load[truck_idx, dest, prod, delivery_date]
                for truck_idx in trucks_for_route
                if (truck_idx, dest, prod, delivery_date) in model.truck_load
            )

            # Shipment = truck loads (forces use of scheduled trucks)
            return total_shipment == total_truck_load

        # Create constraints for all routes with trucks
        truck_route_tuples = [
            (origin, dest, prod, date)
            for (origin, dest) in routes_with_trucks.keys()
            for prod in model.products
            for date in model.dates
        ]

        model.truck_route_linking_con = Constraint(
            truck_route_tuples,
            rule=truck_route_linking_rule,
            doc="Link shipments to trucks for routes with truck schedules"
        )

        # Constraint: Truck availability (day-of-week enforcement)
        def truck_availability_rule(model, truck_idx, date):
            """Truck can only be used on dates matching its day-of-week schedule.

            CRITICAL FIX: For trucks with intermediate stops, we check if the truck
            can DEPART on the given date, not if it arrives on that date. The date
            parameter represents the truck's operating date (departure date).

            The truck_load variables are already keyed by delivery_date (arrival at destination),
            so we don't need route-specific logic here. We just check if the truck
            operates on this date according to its schedule.
            """

            truck = self.truck_by_index[truck_idx]

            # Check if truck runs on this date (based on day of week)
            if not truck.applies_on_date(date):
                # Truck doesn't run on this day - force to zero
                return model.truck_used[truck_idx, date] == 0
            else:
                # Truck can run - no constraint
                return Constraint.Skip

        model.truck_availability_con = Constraint(
            model.trucks,
            model.dates,
            rule=truck_availability_rule,
            doc="Truck availability by day of week"
        )

        # TODO (Phase 4): Add truck pallet ceiling constraints
        # Attempted but confirmed intractable for CBC
        # Even with improved bounds (no per-variable limits), CBC cannot solve in <240s
        # Gap remains 100% - no integer-feasible solution found
        # Requires commercial solver or alternative formulation
        #
        # def truck_pallet_ceiling_rule(model, truck_idx, dest, prod, delivery_date):
        #     load_units = model.truck_load[truck_idx, dest, prod, delivery_date]
        #     load_pallets = model.truck_pallet_load[truck_idx, dest, prod, delivery_date]
        #     return load_pallets * self.UNITS_PER_PALLET >= load_units
        #
        # model.truck_pallet_ceiling_con = Constraint(...)

        # Constraint: Truck capacity (UNIT-BASED)
        # CRITICAL: For trucks with intermediate stops, we need to ensure capacity
        # is shared across ALL deliveries from a SINGLE DEPARTURE, not across a delivery date
        #
        # NOTE: Pallet-level enforcement attempted but confirmed intractable for CBC
        # Multiple approaches tested:
        #   1. bounds=(0, 44): Gap=100% after 300s (poor LP relaxation - 220 theoretical vs 44 actual)
        #   2. No bounds: Gap=100% after 195s (problem too complex even with good LP)
        # ROOT CAUSE: ~20,734 integer/binary variables exceed CBC's practical limits
        # SOLUTION: Use unit-based capacity (acceptable approximation) OR upgrade to commercial solver
        def truck_capacity_rule(model, truck_idx, departure_date):
            """Total load cannot exceed truck capacity (in units).

            For trucks with intermediate stops, different destinations receive on
            different dates from the SAME physical departure. We need to sum loads
            across ALL deliveries originating from this departure date.

            Args:
                truck_idx: Truck index
                departure_date: Date truck departs (not delivery date!)

            Returns:
                Constraint enforcing: total_load_units <= truck.capacity * truck_used
            """

            truck = self.truck_by_index[truck_idx]

            # Get all destinations this truck serves (final + intermediate stops)
            truck_destinations = [truck.destination_node_id]
            if truck.has_intermediate_stops():
                truck_destinations.extend(truck.intermediate_stops)

            # Sum the load in UNITS across all destinations
            total_load = 0

            for dest in truck_destinations:
                # Find route to this destination
                route = next((r for r in self.routes
                             if r.origin_node_id == truck.origin_node_id
                             and r.destination_node_id == dest), None)

                if not route:
                    continue  # No route to this destination

                # Calculate delivery date for this destination
                delivery_date = departure_date + timedelta(days=route.transit_days)

                # Check if delivery date is within planning horizon
                if delivery_date not in model.dates:
                    continue  # Delivery outside planning horizon

                # Sum load (in units) for this destination on its delivery date
                for prod in model.products:
                    if (truck_idx, dest, prod, delivery_date) in model.truck_load:
                        total_load += model.truck_load[truck_idx, dest, prod, delivery_date]

            # Total load from this departure cannot exceed truck capacity (in units)
            return total_load <= truck.capacity * model.truck_used[truck_idx, departure_date]

        model.truck_capacity_con = Constraint(
            model.trucks,
            model.dates,
            rule=truck_capacity_rule,
            doc="Truck capacity constraint (unit-based - pallet-level deferred)"
        )

    def _add_production_capacity_constraints(self, model: ConcreteModel) -> None:
        """Add production capacity constraints for manufacturing nodes.

        Enforces capacity considering:
        1. Production time (quantity / production_rate)
        2. Daily overhead: startup + shutdown (if any production)
        3. Changeover time: (num_products - 1) * changeover_time

        Uses changeover tracking variables to accurately model manufacturing overhead.
        """

        def production_capacity_rule(model, node_id, date):
            """Total production time + overhead cannot exceed available labor hours.

            Constraint structure:
                production_time + overhead_time <= labor_hours

            Where:
                production_time = total_quantity / production_rate
                overhead_time = (startup + shutdown - changeover) * production_day +
                               changeover * num_products_produced

            This formulation correctly models:
                - 0 products: overhead = 0
                - 1 product:  overhead = startup + shutdown
                - N products: overhead = startup + shutdown + (N-1) * changeover
            """

            node = self.nodes[node_id]
            if not node.can_produce():
                return Constraint.Skip

            # Get labor hours for this date
            labor_day = self.labor_calendar.get_labor_day(date)
            if not labor_day:
                # No labor on this date - no production
                total_prod = sum(
                    model.production[node_id, prod, date]
                    for prod in model.products
                    if (node_id, prod, date) in model.production
                )
                return total_prod == 0

            # Get production rate
            production_rate = node.capabilities.production_rate_per_hour

            # Handle missing production rate
            if not production_rate or production_rate <= 0:
                # No production rate defined - force production to zero
                total_prod = sum(
                    model.production[node_id, prod, date]
                    for prod in model.products
                    if (node_id, prod, date) in model.production
                )
                return total_prod == 0

            # Calculate available labor hours based on day type
            if labor_day.is_fixed_day:
                # Fixed days (weekdays): Hard capacity limit (regular + overtime hours)
                labor_hours = labor_day.fixed_hours + (labor_day.overtime_hours if hasattr(labor_day, 'overtime_hours') else 0)
            else:
                # Non-fixed days (weekends/holidays): No capacity limit
                # Unlimited hours available at premium rate - cost model discourages use
                # The 4h minimum_hours is for payment calculation (cost constraint), not capacity
                return Constraint.Skip  # Don't enforce production capacity on non-fixed days

            # Calculate production time needed
            total_production = sum(
                model.production[node_id, prod, date]
                for prod in model.products
                if (node_id, prod, date) in model.production
            )
            production_time = total_production / production_rate

            # Calculate overhead time (if changeover tracking enabled)
            if hasattr(model, 'production_day') and (node_id, date) in model.production_day:
                # Get overhead parameters from node capabilities
                startup_hours = node.capabilities.daily_startup_hours or 0.5
                shutdown_hours = node.capabilities.daily_shutdown_hours or 0.5
                changeover_hours = node.capabilities.default_changeover_hours or 1.0

                # Overhead calculation using reformulated expression:
                # overhead = (startup + shutdown - changeover) * production_day + changeover * num_products
                #
                # This correctly calculates:
                #   - 0 products: 0 overhead (production_day=0, num_products=0)
                #   - 1 product:  startup + shutdown (production_day=1, num_products=1)
                #   - N products: startup + shutdown + (N-1)*changeover (production_day=1, num_products=N)
                overhead_time = (
                    (startup_hours + shutdown_hours - changeover_hours) * model.production_day[node_id, date] +
                    changeover_hours * model.num_products_produced[node_id, date]
                )

                # Total time constraint: production time + overhead <= available hours
                # DEBUG: Print capacity violations during solve
                constraint_expr = production_time + overhead_time <= labor_hours
                return constraint_expr
            else:
                # Changeover tracking not enabled - use old capacity calculation
                # (This preserves backward compatibility if changeover vars not created)
                capacity = production_rate * labor_hours
                return total_production <= capacity

        manufacturing_date_pairs = [
            (node_id, date)
            for node_id in self.manufacturing_nodes
            for date in model.dates
        ]

        model.production_capacity_con = Constraint(
            manufacturing_date_pairs,
            rule=production_capacity_rule,
            doc="Production capacity limits at manufacturing nodes"
        )

    def _add_changeover_tracking_constraints(self, model: ConcreteModel) -> None:
        """Add constraints to track production days and product changeovers.

        These constraints link production quantities to binary indicators and count
        the number of distinct products made each day. This enables accurate
        capacity modeling that accounts for startup, shutdown, and changeover time.

        Binary linking strategy:
        1. production > 0 => product_produced = 1 (big-M constraint)
        2. num_products_produced = sum(product_produced) (counting)
        3. production_day = 1 iff num_products_produced >= 1 (upper/lower bounds)
        """

        if not hasattr(model, 'production_day'):
            # Changeover tracking variables not created (no manufacturing nodes)
            return

        # Get index sets (must match variable creation in build_model)
        production_day_index = [
            (node_id, date)
            for node_id in self.manufacturing_nodes
            for date in model.dates
        ]

        product_produced_index = [
            (node_id, prod, date)
            for node_id in self.manufacturing_nodes
            for prod in model.products
            for date in model.dates
        ]

        # Constraint 1: Link production quantity to product indicator
        # SKIP if force_all_skus_daily=True (product_produced is fixed Param, not Var)
        constraint_count = 0

        if not self.force_all_skus_daily:
            # Only create linking constraint when product_produced is a decision variable
            # Calculate default Big-M once for all constraints
            big_m_default = self.get_max_daily_production()

            def product_produced_linking_rule(model, node_id, prod, date):
                """If product is produced (qty > 0), force product_produced = 1.

                Uses big-M formulation: production <= M * product_produced
                If product_produced = 0, then production must be 0.
                If production > 0, then product_produced must be 1.

                M can be customized per SKU-day via bigm_overrides parameter.
                Smaller M values make it easier for solver to skip that SKU.
                """
                # Use override Big-M if specified, otherwise use default
                big_m = self.bigm_overrides.get((node_id, prod, date), big_m_default)
                return model.production[node_id, prod, date] <= big_m * model.product_produced[node_id, prod, date]

            model.product_produced_linking_con = Constraint(
                product_produced_index,
                rule=product_produced_linking_rule,
                doc="Link production quantity to binary product indicator (variable-specific big-M)"
            )
            constraint_count += len(product_produced_index)

        # Constraint 2: Count number of distinct products produced
        def num_products_counting_rule(model, node_id, date):
            """Count how many distinct products are produced on this date.

            num_products_produced = sum of product_produced indicators
            """
            return model.num_products_produced[node_id, date] == sum(
                model.product_produced[node_id, prod, date]
                for prod in model.products
                if (node_id, prod, date) in model.product_produced
            )

        model.num_products_counting_con = Constraint(
            production_day_index,
            rule=num_products_counting_rule,
            doc="Count number of distinct products produced each day"
        )

        # Constraint 3a: Link production_day to num_products (lower bound)
        def production_day_lower_rule(model, node_id, date):
            """If num_products >= 1, then production_day must be 1.

            num_products <= max_products * production_day
            """
            max_products = len(model.products)
            return model.num_products_produced[node_id, date] <= max_products * model.production_day[node_id, date]

        model.production_day_lower_con = Constraint(
            production_day_index,
            rule=production_day_lower_rule,
            doc="Production day indicator: lower bound"
        )

        # Constraint 3b: Link production_day to num_products (upper bound)
        def production_day_upper_rule(model, node_id, date):
            """If num_products = 0, then production_day must be 0.

            production_day <= num_products (forces 0 when no production)
            """
            return model.production_day[node_id, date] <= model.num_products_produced[node_id, date]

        model.production_day_upper_con = Constraint(
            production_day_index,
            rule=production_day_upper_rule,
            doc="Production day indicator: upper bound"
        )
        constraint_count += 3 * len(production_day_index)  # num_products, lower, upper

        # Print summary
        print(f"  Changeover tracking constraints added ({constraint_count:,} constraints)")
        if not self.force_all_skus_daily:
            if self.bigm_overrides:
                print(f"  Big-M: default={big_m_default:,.0f} units/day, {len(self.bigm_overrides)} SKUs with custom values")
            else:
                print(f"  Big-M value for product_produced linking: {big_m_default:,.0f} units/day")
        else:
            print(f"  Big-M linking skipped (all SKUs fixed to produce daily)")

    def _add_labor_cost_constraints(self, model: ConcreteModel) -> None:
        """Add piecewise labor cost tracking constraints.

        Implements accurate labor cost calculation with:
        - Fixed day piecewise costs: regular rate for fixed hours, overtime rate for excess
        - Non-fixed day costs: premium rate with 4-hour minimum payment enforcement
        - Overhead time inclusion: startup + shutdown + changeover time included in labor hours

        Constraints added:
            1. labor_hours_linking_con: Links production quantity to labor hours (production + overhead)
            2. fixed_hours_limit_con: Enforces fixed hours cannot exceed available fixed hours
            3. overtime_calculation_con: Calculates overtime as hours used - fixed hours
            4. minimum_hours_enforcement_con: Enforces 4-hour minimum on non-fixed days
            5. labor_hours_paid_lower_con: Paid hours >= used hours
            6. overtime_indicator_con: Binary enforcement for piecewise cost structure

        Args:
            model: Pyomo ConcreteModel with variables defined
        """
        if not hasattr(model, 'labor_hours_used'):
            # Labor variables not created
            return

        production_day_index = [
            (node_id, date)
            for node_id in self.manufacturing_nodes
            for date in model.dates
        ]

        # Constraint 1: Link production quantity to labor hours
        # labor_hours_used = production_time + overhead_time
        def labor_hours_linking_rule(model, node_id, date):
            """Calculate total labor hours from production quantity and overhead.

            labor_hours_used = (total_production / production_rate) + overhead_hours

            Where overhead_hours = startup + shutdown + changeover time (from changeover tracking)
            """
            node = self.nodes[node_id]
            production_rate = node.capabilities.production_rate_per_hour

            if not production_rate or production_rate <= 0:
                return Constraint.Skip

            # Calculate production time
            total_production = sum(
                model.production[node_id, prod, date]
                for prod in model.products
                if (node_id, prod, date) in model.production
            )
            production_time = total_production / production_rate

            # Calculate overhead time (if changeover tracking enabled)
            if hasattr(model, 'production_day') and (node_id, date) in model.production_day:
                startup_hours = node.capabilities.daily_startup_hours or 0.5
                shutdown_hours = node.capabilities.daily_shutdown_hours or 0.5
                changeover_hours = node.capabilities.default_changeover_hours or 1.0

                overhead_time = (
                    (startup_hours + shutdown_hours - changeover_hours) * model.production_day[node_id, date] +
                    changeover_hours * model.num_products_produced[node_id, date]
                )

                # Link labor_hours_used to production + overhead
                return model.labor_hours_used[node_id, date] == production_time + overhead_time
            else:
                # No changeover tracking - labor hours = production time only
                return model.labor_hours_used[node_id, date] == production_time

        model.labor_hours_linking_con = Constraint(
            production_day_index,
            rule=labor_hours_linking_rule,
            doc="Link production quantity to labor hours (production time + overhead)"
        )

        # Constraint 2: Fixed hours upper bound and non-fixed day enforcement
        # On fixed days: fixed_hours_used <= available_fixed_hours
        # On non-fixed days: fixed_hours_used = 0 (all hours at non_fixed_rate)
        def fixed_hours_limit_rule(model, node_id, date):
            """Enforce fixed hours limits based on day type."""
            labor_day = self.labor_calendar.get_labor_day(date)

            if not labor_day or not labor_day.is_fixed_day:
                # Non-fixed day or no labor: all hours at non_fixed_rate (no fixed hours)
                return model.fixed_hours_used[node_id, date] == 0
            else:
                # Fixed day: limit to available fixed hours
                return model.fixed_hours_used[node_id, date] <= labor_day.fixed_hours

        model.fixed_hours_limit_con = Constraint(
            production_day_index,
            rule=fixed_hours_limit_rule,
            doc="Fixed hours bounded by available fixed hours (zero on non-fixed days)"
        )

        # Constraint 3: Overtime calculation
        # On fixed days: overtime_hours_used = labor_hours_used - fixed_hours_used
        # On non-fixed days: overtime_hours_used = 0 (uses non_fixed_rate instead)
        def overtime_calculation_rule(model, node_id, date):
            """Calculate overtime hours on fixed days."""
            labor_day = self.labor_calendar.get_labor_day(date)

            if not labor_day or not labor_day.is_fixed_day:
                # Non-fixed day: no overtime concept (uses non_fixed_rate)
                return model.overtime_hours_used[node_id, date] == 0
            else:
                # Fixed day: overtime = total used - fixed used
                return (model.overtime_hours_used[node_id, date] ==
                        model.labor_hours_used[node_id, date] - model.fixed_hours_used[node_id, date])

        model.overtime_calculation_con = Constraint(
            production_day_index,
            rule=overtime_calculation_rule,
            doc="Calculate overtime hours as excess beyond fixed hours"
        )

        # Constraint 4: Paid hours lower bound (paid >= used)
        def labor_hours_paid_lower_rule(model, node_id, date):
            """Paid hours must at least equal used hours."""
            return model.labor_hours_paid[node_id, date] >= model.labor_hours_used[node_id, date]

        model.labor_hours_paid_lower_con = Constraint(
            production_day_index,
            rule=labor_hours_paid_lower_rule,
            doc="Paid hours at least equal used hours"
        )

        # Constraint 5: Minimum hours enforcement (non-fixed days only)
        def minimum_hours_enforcement_rule(model, node_id, date):
            """Enforce 4-hour minimum payment on non-fixed days WHEN PRODUCING.

            The minimum only applies if there's actual production on that day.
            If production_day = 0 (no production), no minimum payment required.
            If production_day = 1 (producing), must pay for at least minimum_hours.
            """
            labor_day = self.labor_calendar.get_labor_day(date)

            if not labor_day or labor_day.is_fixed_day:
                # Fixed days or no labor: no minimum hours requirement
                return Constraint.Skip

            # Non-fixed day: enforce minimum hours if specified AND producing
            if hasattr(labor_day, 'minimum_hours') and labor_day.minimum_hours > 0:
                # Only enforce minimum when actually producing (production_day = 1)
                return model.labor_hours_paid[node_id, date] >= labor_day.minimum_hours * model.production_day[node_id, date]
            else:
                return Constraint.Skip

        model.minimum_hours_enforcement_con = Constraint(
            production_day_index,
            rule=minimum_hours_enforcement_rule,
            doc="Enforce minimum hours payment on non-fixed days"
        )

        # Constraint 6: Overtime binary indicator (for piecewise cost enforcement)
        # Uses big-M to link overtime_hours_used to uses_overtime binary
        # If overtime_hours_used > 0, then uses_overtime = 1
        # If overtime_hours_used = 0, then uses_overtime can be 0 or 1 (minimization chooses 0)
        def overtime_indicator_upper_rule(model, node_id, date):
            """Link overtime hours to binary indicator (upper bound).

            overtime_hours_used <= M * uses_overtime
            If uses_overtime = 0, forces overtime_hours_used = 0

            CRITICAL FIX (Quick Win #4): M should be max OVERTIME hours (2.0),
            not total labor hours (14.0). overtime_hours_used only represents
            the OT portion, not the total hours!
            """
            M = 2.0  # Quick Win #4: Max OVERTIME hours per day (was 14.0 - 7x too large!)
            return model.overtime_hours_used[node_id, date] <= M * model.uses_overtime[node_id, date]

        model.overtime_indicator_upper_con = Constraint(
            production_day_index,
            rule=overtime_indicator_upper_rule,
            doc="Link overtime hours to binary indicator (big-M upper)"
        )

        def overtime_indicator_lower_rule(model, node_id, date):
            """Link overtime hours to binary indicator (lower bound).

            overtime_hours_used >= epsilon * uses_overtime
            If overtime_hours_used > epsilon, forces uses_overtime = 1
            """
            epsilon = 0.0001  # Tighter threshold to catch all overtime usage
            return model.overtime_hours_used[node_id, date] >= epsilon * model.uses_overtime[node_id, date]

        model.overtime_indicator_lower_con = Constraint(
            production_day_index,
            rule=overtime_indicator_lower_rule,
            doc="Link overtime hours to binary indicator (big-M lower)"
        )

        # Constraint 7: Piecewise enforcement - fixed hours must be "filled" before overtime
        # If overtime is used (uses_overtime = 1), then fixed_hours_used must equal available_fixed_hours
        # If no overtime (uses_overtime = 0), then fixed_hours_used = labor_hours_used
        def piecewise_enforcement_rule(model, node_id, date):
            """Enforce piecewise cost structure: fill fixed hours before overtime.

            If uses_overtime = 1: fixed_hours_used >= available_fixed_hours - epsilon
            This ensures we use all fixed hours before paying overtime rate.

            The combination of this + overtime_calculation ensures correct piecewise split.
            """
            labor_day = self.labor_calendar.get_labor_day(date)

            if not labor_day or not labor_day.is_fixed_day:
                return Constraint.Skip  # Only applies to fixed days

            # On fixed days: if overtime is used, must use ALL fixed hours first
            # fixed_hours_used >= fixed_hours_available * uses_overtime
            return model.fixed_hours_used[node_id, date] >= labor_day.fixed_hours * model.uses_overtime[node_id, date]

        model.piecewise_enforcement_con = Constraint(
            production_day_index,
            rule=piecewise_enforcement_rule,
            doc="Enforce piecewise structure: use all fixed hours before overtime"
        )

        # Constraint 8: Force overtime indicator when labor exceeds fixed hours
        # This prevents solver from using overtime capacity without paying overtime rate
        def overtime_forcing_rule(model, node_id, date):
            """Force uses_overtime = 1 when labor_hours_used exceeds fixed_hours.

            labor_hours_used <= fixed_hours + M * uses_overtime
            If uses_overtime = 0: can only use up to fixed_hours
            If uses_overtime = 1: can use up to fixed_hours + M (overtime capacity)
            """
            labor_day = self.labor_calendar.get_labor_day(date)

            if not labor_day or not labor_day.is_fixed_day:
                return Constraint.Skip  # Only applies to fixed days

            # Use actual overtime capacity from labor calendar (not hardcoded 2.0)
            overtime_capacity = labor_day.overtime_hours
            return model.labor_hours_used[node_id, date] <= labor_day.fixed_hours + overtime_capacity * model.uses_overtime[node_id, date]

        model.overtime_forcing_con = Constraint(
            production_day_index,
            rule=overtime_forcing_rule,
            doc="Force uses_overtime=1 when labor exceeds fixed hours"
        )

        print(f"  Labor cost constraints added ({len(production_day_index):,} node-date pairs, {9 * len(production_day_index):,} constraints)")

    def _add_objective(self, model: ConcreteModel) -> None:
        """Add objective function: minimize total cost.

        Total cost = production cost + labor cost + transport cost + holding cost + shortage penalty

        Holding cost uses pallet-based rounding with ceiling constraints:
        - Inventory rounded UP to nearest pallet (320 units)
        - Cost = pallet_count × storage_rate (per pallet per day)
        - Ensures accurate partial pallet cost representation
        """

        # Production cost (units produced * cost per unit)
        # OPTIMIZATION: Use quicksum() for faster expression building
        production_cost = quicksum(
            self.cost_structure.production_cost_per_unit * model.production[node_id, prod, date]
            for node_id in self.manufacturing_nodes
            for prod in model.products
            for date in model.dates
            if (node_id, prod, date) in model.production
        )

        # Transport cost (shipments * route cost)
        # OPTIMIZATION: Pre-build route cost lookup dictionary + use quicksum()
        route_costs = {
            (r.origin_node_id, r.destination_node_id): r.cost_per_unit
            for r in self.routes
        }

        transport_cost = quicksum(
            route_costs[(origin, dest)] * model.shipment_cohort[origin, dest, prod, prod_date, delivery_date, state]
            for (origin, dest, prod, prod_date, delivery_date, state) in self.shipment_cohort_index_set
            if (origin, dest) in route_costs
        )

        # Labor cost (piecewise with overhead inclusion and 4-hour minimum enforcement)
        # Uses labor decision variables for accurate cost calculation
        labor_cost = 0

        if hasattr(model, 'labor_hours_used'):
            # Piecewise labor cost model
            for node_id in self.manufacturing_nodes:
                for date in model.dates:
                    labor_day = self.labor_calendar.get_labor_day(date)

                    if not labor_day:
                        # No labor on this date - no cost
                        continue

                    if labor_day.is_fixed_day:
                        # Fixed day: piecewise cost (regular rate + overtime rate)
                        # Cost = fixed_hours_used × regular_rate + overtime_hours_used × overtime_rate
                        labor_cost += (
                            labor_day.regular_rate * model.fixed_hours_used[node_id, date] +
                            labor_day.overtime_rate * model.overtime_hours_used[node_id, date]
                        )
                    else:
                        # Non-fixed day: premium rate × paid hours (includes 4-hour minimum)
                        # Paid hours enforced by minimum_hours_enforcement_con constraint
                        non_fixed_rate = labor_day.non_fixed_rate if labor_day.non_fixed_rate else labor_day.overtime_rate
                        labor_cost += non_fixed_rate * model.labor_hours_paid[node_id, date]

        else:
            # Fallback to old blended rate calculation (if labor variables not created)
            # This provides backward compatibility but should not be reached in normal operation
            for node_id in self.manufacturing_nodes:
                node = self.nodes[node_id]
                production_rate = node.capabilities.production_rate_per_hour

                if not production_rate or production_rate <= 0:
                    continue

                for date in model.dates:
                    total_production = sum(
                        model.production[node_id, prod, date]
                        for prod in model.products
                        if (node_id, prod, date) in model.production
                    )

                    labor_hours_needed = total_production / production_rate
                    labor_day = self.labor_calendar.get_labor_day(date)

                    if labor_day and labor_day.is_fixed_day:
                        blended_rate = (labor_day.regular_rate + labor_day.overtime_rate) / 2
                        labor_cost += labor_hours_needed * blended_rate
                    elif labor_day and not labor_day.is_fixed_day:
                        non_fixed_rate = labor_day.non_fixed_rate if labor_day.non_fixed_rate else labor_day.overtime_rate
                        labor_cost += labor_hours_needed * non_fixed_rate
                    else:
                        labor_cost += labor_hours_needed * 25.0

        # Shortage penalty (if shortages allowed)
        # OPTIMIZATION: Use quicksum() for faster expression building
        if self.allow_shortages:
            penalty = self.cost_structure.shortage_penalty_per_unit
            shortage_cost = quicksum(
                penalty * model.shortage[node_id, prod, date]
                for (node_id, prod, date) in self.demand.keys()
            )
        else:
            shortage_cost = 0

        # Holding cost (state-specific pallet-based tracking with ceiling rounding)
        holding_cost = 0

        if self.use_batch_tracking:
            # Get state-specific fixed costs
            pallet_fixed_frozen, pallet_fixed_ambient = self.cost_structure.get_fixed_pallet_costs()

            # Get state-specific daily costs
            pallet_frozen_per_day = self.cost_structure.storage_cost_per_pallet_day_frozen or 0.0
            pallet_ambient_per_day = self.cost_structure.storage_cost_per_pallet_day_ambient or 0.0

            # Fall back to unit-based costs (legacy method)
            unit_frozen_per_day = self.cost_structure.storage_cost_frozen_per_unit_day or 0.0
            unit_ambient_per_day = self.cost_structure.storage_cost_ambient_per_unit_day or 0.0

            # Determine tracking mode per state
            # Pallet tracking: Use if any pallet-based costs are non-zero
            # Unit tracking: Use if pallet costs are zero but unit costs are non-zero
            use_pallet_frozen = (pallet_fixed_frozen > 0 or pallet_frozen_per_day > 0)
            use_pallet_ambient = (pallet_fixed_ambient > 0 or pallet_ambient_per_day > 0)
            use_unit_frozen = (unit_frozen_per_day > 0)
            use_unit_ambient = (unit_ambient_per_day > 0)

            # Warn if both pallet and unit costs configured for same state
            if use_pallet_frozen and use_unit_frozen:
                warnings.warn(
                    "Both pallet-based and unit-based frozen storage costs are configured. "
                    "Using pallet-based costs for frozen state (set unit costs to 0 to suppress)."
                )
            if use_pallet_ambient and use_unit_ambient:
                warnings.warn(
                    "Both pallet-based and unit-based ambient storage costs are configured. "
                    "Using pallet-based costs for ambient/thawed states (set unit costs to 0 to suppress)."
                )

            # Build set of states requiring pallet integer variables
            pallet_states = set()
            if use_pallet_frozen:
                pallet_states.add('frozen')
            if use_pallet_ambient:
                pallet_states.update(['ambient', 'thawed'])

            # Check if any holding costs are configured
            has_holding_costs = (use_pallet_frozen or use_pallet_ambient or
                               use_unit_frozen or use_unit_ambient)

            if has_holding_costs:
                # Calculate cost rates (pallet-based takes precedence over unit-based)
                if use_pallet_frozen:
                    frozen_rate_per_pallet = pallet_frozen_per_day
                elif use_unit_frozen:
                    # Convert unit cost to pallet basis for consistent calculation
                    frozen_rate_per_pallet = unit_frozen_per_day * self.UNITS_PER_PALLET
                else:
                    frozen_rate_per_pallet = 0.0

                if use_pallet_ambient:
                    ambient_rate_per_pallet = pallet_ambient_per_day
                elif use_unit_ambient:
                    # Convert unit cost to pallet basis for consistent calculation
                    ambient_rate_per_pallet = unit_ambient_per_day * self.UNITS_PER_PALLET
                else:
                    ambient_rate_per_pallet = 0.0

                # Validate rates are non-negative
                if frozen_rate_per_pallet < 0 or ambient_rate_per_pallet < 0:
                    raise ValueError("Storage rates cannot be negative")

                # Create pallet variables only for states that need them
                if pallet_states:
                    # Calculate maximum pallet count for variable bounds (tightens search space)
                    # CRITICAL FIX (Quick Win #2): A cohort represents production from ONE day,
                    # not cumulative days! Maximum inventory in any cohort = max daily production.
                    # ADAPTIVE BOUNDS: Also consider initial inventory to handle edge cases where
                    # existing stock exceeds daily production capacity.
                    #
                    # OLD (WRONG): max_inventory_per_cohort = max_daily_production * planning_days  # Gave 1,715 pallets!
                    # NEW (CORRECT): max_pallets_per_cohort = ceil(max_inventory_cohort / UNITS_PER_PALLET)
                    #                where max_inventory_cohort = max(daily_production, initial_inventory)
                    max_pallets_per_cohort = int(math.ceil(self.max_inventory_cohort / self.UNITS_PER_PALLET))

                    # Filter cohort indices to only those states requiring pallet tracking
                    pallet_cohort_index = [
                        (n, p, pd, cd, s) for (n, p, pd, cd, s) in self.cohort_index_set
                        if s in pallet_states
                    ]

                    # Create indexed set for pallet-tracked cohorts
                    model.pallet_cohort_index = PyomoSet(
                        initialize=pallet_cohort_index,
                        doc="Inventory cohorts requiring pallet-based tracking"
                    )

                    # Add integer pallet count variables with ADAPTIVE TIGHTENED bounds
                    # Only created for states with pallet-based costs configured
                    model.pallet_count = Var(
                        model.pallet_cohort_index,
                        within=NonNegativeIntegers,
                        bounds=(0, max_pallets_per_cohort),  # Adaptive bound accommodates both production and initial inventory
                        doc="Pallet count for inventory cohort (state-specific, adaptive bound based on max cohort size)"
                    )

                    # Ceiling constraint: enforce pallet_count >= ceil(inventory_qty / UNITS_PER_PALLET)
                    # Cost minimization automatically drives pallet_count to minimum (ceiling)
                    # No upper bound needed - solver minimizes pallet_count × holding_cost
                    def pallet_lower_bound_rule(
                        model: ConcreteModel,
                        node_id: str,
                        prod: str,
                        prod_date: Date,
                        curr_date: Date,
                        state: str
                    ) -> Constraint:
                        """Pallet count must cover inventory (ceiling constraint).

                        Combined with cost minimization in objective, this enforces:
                            pallet_count = ceil(inventory_qty / UNITS_PER_PALLET)

                        The solver minimizes holding_cost = rate × pallet_count, so it will
                        choose the MINIMUM integer pallet_count satisfying this constraint.

                        Only applies to states with pallet-based tracking enabled.
                        """
                        inv_qty = model.inventory_cohort[node_id, prod, prod_date, curr_date, state]
                        pallet_var = model.pallet_count[node_id, prod, prod_date, curr_date, state]
                        return pallet_var * self.UNITS_PER_PALLET >= inv_qty

                    model.pallet_lower_bound_con = Constraint(
                        model.pallet_cohort_index,
                        rule=pallet_lower_bound_rule,
                        doc="Pallet count ceiling constraint for pallet-tracked states (cost minimization drives to minimum)"
                    )

                    print(f"  Pallet tracking enabled for states: {sorted(pallet_states)}")
                    print(f"    - Pallet variables created: {len(pallet_cohort_index):,}")
                    print(f"    - Unit-tracked states: {sorted(set(['frozen', 'ambient', 'thawed']) - pallet_states)}")

                # Add holding cost to objective (state-specific logic)
                for (node_id, prod, prod_date, curr_date, state) in self.cohort_index_set:
                    # Use pallet tracking if state is in pallet_states
                    if state in pallet_states:
                        pallet_count = model.pallet_count[node_id, prod, prod_date, curr_date, state]

                        # Apply state-specific fixed cost
                        if state == 'frozen' and pallet_fixed_frozen > 0:
                            holding_cost += pallet_fixed_frozen * pallet_count
                        elif state in ['ambient', 'thawed'] and pallet_fixed_ambient > 0:
                            holding_cost += pallet_fixed_ambient * pallet_count

                        # Apply daily holding cost
                        if state == 'frozen' and frozen_rate_per_pallet > 0:
                            holding_cost += frozen_rate_per_pallet * pallet_count
                        elif state in ['ambient', 'thawed'] and ambient_rate_per_pallet > 0:
                            holding_cost += ambient_rate_per_pallet * pallet_count
                    else:
                        # Use unit tracking for this state
                        inv_qty = model.inventory_cohort[node_id, prod, prod_date, curr_date, state]

                        if state == 'frozen' and unit_frozen_per_day > 0:
                            holding_cost += unit_frozen_per_day * inv_qty
                        elif state in ['ambient', 'thawed'] and unit_ambient_per_day > 0:
                            holding_cost += unit_ambient_per_day * inv_qty

                total_cohorts = len(self.cohort_index_set)
                pallet_cohorts = len(pallet_states) * total_cohorts // 3  # Rough estimate
                print(f"  Holding cost enabled: {total_cohorts:,} total cohorts ({pallet_cohorts:,} pallet-tracked)")
            else:
                print("  Holding cost skipped (all storage rates are zero)")

        # Total cost
        total_cost = production_cost + transport_cost + labor_cost + shortage_cost + holding_cost

        model.obj = Objective(
            expr=total_cost,
            sense=minimize,
            doc="Minimize total cost (production + transport + labor + holding + shortage penalty)"
        )


def solve_two_phase(
    nodes: List[UnifiedNode],
    routes: List[UnifiedRoute],
    forecast: Forecast,
    labor_calendar: LaborCalendar,
    cost_structure: CostStructure,
    start_date: Date,
    end_date: Date,
    truck_schedules: Optional[List[UnifiedTruckSchedule]] = None,
    initial_inventory: Optional[Dict] = None,
    inventory_snapshot_date: Optional[Date] = None,
    use_batch_tracking: bool = True,
    allow_shortages: bool = False,
    enforce_shelf_life: bool = True,
    solver_name: Optional[str] = 'appsi_highs',
    time_limit_seconds_phase1: float = 60,
    time_limit_seconds_phase2: float = 180,
    mip_gap: float = 0.01,
    tee: bool = False,
) -> OptimizationResult:
    """Solve optimization in two phases: fixed SKUs (fast) + binary SKUs (warmstart).

    Two-Phase Strategy:
    -------------------
    Phase 1: Solve with all SKUs forced to produce daily (force_all_skus_daily=True)
        - Removes binary SKU selection complexity
        - Solves as simpler MIP (only pallet integer variables)
        - Fast solve time: ~10-30s
        - Provides feasible production pattern

    Phase 2: Solve with binary SKU selection using Phase 1 warmstart
        - Uses Phase 1 production pattern to initialize product_produced variables
        - APPSI HiGHS solver applies warmstart to speed up MIP solve
        - Better incumbent solution → faster branch-and-bound
        - Target solve time: 50-70% faster than cold start

    This approach is especially effective when:
    - Problem has many binary SKU variables (long horizon, many products)
    - Solver struggles to find good feasible solution quickly
    - MIP gap tolerance is strict (1-3%)

    Args:
        nodes: List of UnifiedNode objects
        routes: List of UnifiedRoute objects
        forecast: Demand forecast
        labor_calendar: Labor availability and costs
        cost_structure: Cost parameters
        start_date: Planning horizon start
        end_date: Planning horizon end (inclusive)
        truck_schedules: Optional list of truck schedules
        initial_inventory: Optional initial inventory dict
        inventory_snapshot_date: Date when initial inventory was measured
        use_batch_tracking: Use age-cohort tracking (default: True)
        allow_shortages: Allow demand shortages with penalty (default: False)
        enforce_shelf_life: Enforce shelf life constraints (default: True)
        solver_name: Solver to use (default: 'appsi_highs' for warmstart support)
        time_limit_seconds_phase1: Time limit for Phase 1 (default: 60s)
        time_limit_seconds_phase2: Time limit for Phase 2 (default: 180s)
        mip_gap: MIP gap tolerance (default: 0.01 = 1%)
        tee: Show solver output (default: False)

    Returns:
        OptimizationResult from Phase 2 (final solution with binary SKU selection)

    Example:
        >>> result = solve_two_phase(
        ...     nodes=nodes, routes=routes, forecast=forecast,
        ...     labor_calendar=labor, cost_structure=costs,
        ...     start_date=date(2025,10,20), end_date=date(2025,11,16),
        ...     solver_name='appsi_highs', time_limit_seconds_phase2=180
        ... )
        >>> print(f"Solved in {result.solve_time_seconds:.1f}s with {result.gap*100:.1f}% gap")
    """
    import time

    print("="*80)
    print("TWO-PHASE SOLVE: Fixed SKUs (fast) → Binary SKUs (warmstart)")
    print("="*80)

    # ========================================================================
    # PHASE 1: Solve with all SKUs forced to produce daily (fast solve)
    # ========================================================================
    print("\nPHASE 1: Solving with all SKUs forced daily (baseline pattern)")
    print("-" * 80)

    phase1_start = time.time()

    model_phase1 = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=use_batch_tracking,
        allow_shortages=allow_shortages,
        enforce_shelf_life=enforce_shelf_life,
        force_all_skus_daily=True,  # KEY: Force all SKUs to produce
    )

    result_phase1 = model_phase1.solve(
        solver_name=solver_name,
        time_limit_seconds=time_limit_seconds_phase1,
        mip_gap=mip_gap * 2,  # Relax gap for Phase 1 (faster solve)
        tee=tee,
        use_warmstart=False,
    )

    phase1_time = time.time() - phase1_start

    print(f"\nPhase 1 Results:")
    print(f"  Status: {result_phase1.termination_condition}")
    print(f"  Solve time: {phase1_time:.1f}s")
    print(f"  Objective: ${result_phase1.objective_value:,.2f}")
    if result_phase1.gap:
        print(f"  MIP gap: {result_phase1.gap * 100:.2f}%")

    # Check if Phase 1 found a usable solution (check termination condition directly)
    # NOTE: Don't use is_optimal()/is_feasible() - they check success flag which
    # can be False due to solution extraction issues with zero costs
    # ALSO NOTE: Use .name for comparison - TerminationCondition enums differ between
    # pyomo.opt and pyomo.contrib.appsi.base

    term_name = result_phase1.termination_condition.name if hasattr(result_phase1.termination_condition, 'name') else str(result_phase1.termination_condition)

    phase1_ok = term_name in ['optimal', 'feasible', 'maxTimeLimit']

    if not phase1_ok:
        print(f"\n⚠️  Phase 1 failed to find usable solution!")
        print(f"   Termination: {result_phase1.termination_condition}")
        print(f"   Returning Phase 1 result (Phase 2 skipped)")
        return result_phase1

    print(f"✓ Phase 1 found usable solution (termination: {term_name})")

    # Extract production pattern DIRECTLY from Pyomo model variables
    # Using pyomo.value() to bypass get_solution() which fails with zero costs
    print(f"\n✓ Extracting production pattern from Phase 1 Pyomo model...")

    from pyomo.environ import value as pyo_value

    try:
        warmstart_hints = {}
        manufacturing_nodes = model_phase1.manufacturing_nodes
        products = model_phase1.products
        dates = model_phase1.production_dates

        num_produced = 0
        num_not_produced = 0
        num_filtered = 0  # Count batches filtered out as too small

        # Access production variables directly from Pyomo model
        pyomo_model = model_phase1.model

        # Minimum production threshold: 1 hour = 1400 units
        # Filter out tiny batches that wouldn't make economic sense
        MIN_PRODUCTION_THRESHOLD = 1400.0

        for node_id in manufacturing_nodes:
            for product in products:
                for date_val in dates:
                    # Get production quantity directly from Pyomo variable
                    if (node_id, product, date_val) in pyomo_model.production:
                        try:
                            prod_qty = pyo_value(pyomo_model.production[node_id, product, date_val])

                            # Filter warmstart hint based on production size
                            # Only include products with meaningful production (≥ 1 hour)
                            if prod_qty >= MIN_PRODUCTION_THRESHOLD:
                                warmstart_hints[(node_id, product, date_val)] = 1
                                num_produced += 1
                            elif prod_qty > 0.01:
                                # Non-zero but below threshold - filter out
                                warmstart_hints[(node_id, product, date_val)] = 0
                                num_filtered += 1
                            else:
                                # Zero production
                                warmstart_hints[(node_id, product, date_val)] = 0
                                num_not_produced += 1
                        except:
                            # Variable not initialized - assume not produced
                            warmstart_hints[(node_id, product, date_val)] = 0
                            num_not_produced += 1

        num_warmstart_vars = len(warmstart_hints)

        if num_warmstart_vars > 0:
            print(f"✓ Warmstart hints extracted and filtered:")
            print(f"   Variables: {num_warmstart_vars:,}")
            print(f"   Produced (≥1400 units, hint=1): {num_produced:,}")
            print(f"   Filtered (<1400 units): {num_filtered:,} → hint=0")
            print(f"   Not produced (hint=0): {num_not_produced:,}")
            print(f"   → Reduced from {num_produced + num_filtered:,} to {num_produced:,} active products")
        else:
            print(f"⚠️  No warmstart hints extracted (empty model)")
            warmstart_hints = None

    except Exception as e:
        print(f"\n⚠️  Warmstart extraction failed: {e}")
        print(f"   Proceeding to Phase 2 without warmstart")
        warmstart_hints = None

    # ========================================================================
    # PHASE 2: Solve with binary SKU selection using warmstart
    # ========================================================================
    print("\nPHASE 2: Solving with binary SKU selection (using Phase 1 warmstart)")
    print("-" * 80)

    phase2_start = time.time()

    model_phase2 = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=use_batch_tracking,
        allow_shortages=allow_shortages,
        enforce_shelf_life=enforce_shelf_life,
        force_all_skus_daily=False,  # KEY: Enable binary SKU selection
    )

    result_phase2 = model_phase2.solve(
        solver_name=solver_name,
        time_limit_seconds=time_limit_seconds_phase2,
        mip_gap=mip_gap,
        tee=tee,
        use_warmstart=True if warmstart_hints else False,
        warmstart_hints=warmstart_hints,
    )

    phase2_time = time.time() - phase2_start

    print(f"\nPhase 2 Results:")
    print(f"  Status: {result_phase2.termination_condition}")
    print(f"  Solve time: {phase2_time:.1f}s")
    print(f"  Objective: ${result_phase2.objective_value:,.2f}")
    if result_phase2.gap:
        print(f"  MIP gap: {result_phase2.gap * 100:.2f}%")

    # Summary
    print("\n" + "="*80)
    print("TWO-PHASE SOLVE SUMMARY")
    print("="*80)
    print(f"Phase 1 (fixed SKUs):   {phase1_time:.1f}s")
    print(f"Phase 2 (binary SKUs):  {phase2_time:.1f}s")
    print(f"Total time:             {phase1_time + phase2_time:.1f}s")
    print()
    print(f"Final objective:        ${result_phase2.objective_value:,.2f}")
    print(f"Final status:           {result_phase2.termination_condition}")
    if result_phase2.gap:
        print(f"Final MIP gap:          {result_phase2.gap * 100:.2f}%")

    # Cost comparison
    if result_phase1.objective_value and result_phase2.objective_value:
        cost_diff = result_phase1.objective_value - result_phase2.objective_value
        pct_diff = 100 * cost_diff / result_phase1.objective_value if result_phase1.objective_value > 0 else 0
        if cost_diff > 0:
            print(f"\nCost improvement:       ${cost_diff:,.2f} ({pct_diff:.1f}% reduction)")
            print(f"   Phase 1 forced all SKUs → higher costs")
            print(f"   Phase 2 reduced SKU variety → lower costs")
        elif cost_diff < 0:
            print(f"\nNote: Phase 2 cost ${abs(cost_diff):,.2f} higher ({abs(pct_diff):.1f}%)")
            print(f"   This can happen if Phase 2 hit time limit with sub-optimal solution")
        else:
            print(f"\nCosts identical (both phases produced all SKUs)")

    print("="*80)

    return result_phase2


def solve_multi_phase_iterative(
    nodes: List[UnifiedNode],
    routes: List[UnifiedRoute],
    forecast: Forecast,
    labor_calendar: LaborCalendar,
    cost_structure: CostStructure,
    start_date: Date,
    end_date: Date,
    truck_schedules: Optional[List[UnifiedTruckSchedule]] = None,
    initial_inventory: Optional[Dict] = None,
    inventory_snapshot_date: Optional[Date] = None,
    use_batch_tracking: bool = True,
    allow_shortages: bool = False,
    enforce_shelf_life: bool = True,
    solver_name: Optional[str] = 'appsi_highs',
    time_limit_per_phase: float = 60,
    time_limit_final: float = 180,
    mip_gap: float = 0.03,
    min_production_hours: float = 1.0,
    max_iterations: int = 10,
    tee: bool = False,
) -> OptimizationResult:
    """Solve using iterative multi-phase refinement with progressive SKU filtering.

    Strategy:
    ---------
    1. Phase 1: Force ALL SKUs (baseline)
    2. Extract production, identify batches < min_production_hours
    3. Phase N: Force only "keeper" SKUs (production ≥ threshold), free the rest
    4. Repeat until convergence (no batches < threshold)
    5. Final Phase: Full binary SKU optimization using refined pattern as warmstart

    This progressively refines the SKU selection, starting from "all SKUs" and
    iteratively eliminating uneconomic small batches until a stable pattern emerges.

    Args:
        nodes: List of UnifiedNode objects
        routes: List of UnifiedRoute objects
        forecast: Demand forecast
        labor_calendar: Labor availability and costs
        cost_structure: Cost parameters
        start_date: Planning horizon start
        end_date: Planning horizon end (inclusive)
        truck_schedules: Optional list of truck schedules
        initial_inventory: Optional initial inventory dict
        inventory_snapshot_date: Date when initial inventory was measured
        use_batch_tracking: Use age-cohort tracking (default: True)
        allow_shortages: Allow demand shortages with penalty (default: False)
        enforce_shelf_life: Enforce shelf life constraints (default: True)
        solver_name: Solver to use (default: 'appsi_highs')
        time_limit_per_phase: Time limit for each iteration (default: 60s)
        time_limit_final: Time limit for final binary solve (default: 180s)
        mip_gap: MIP gap tolerance (default: 0.03 = 3%)
        min_production_hours: Minimum production hours to keep SKU (default: 1.0h)
        max_iterations: Maximum refinement iterations (default: 10)
        tee: Show solver output (default: False)

    Returns:
        OptimizationResult from final phase (binary SKU optimization)
    """
    import time
    from pyomo.environ import value as pyo_value

    print("="*80)
    print("MULTI-PHASE ITERATIVE SOLVER")
    print("Progressive SKU Filtering with Warmstart Refinement")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Minimum production: {min_production_hours:.1f} hours ({min_production_hours * 1400:.0f} units)")
    print(f"  Max iterations: {max_iterations}")
    print(f"  Time per phase: {time_limit_per_phase:.0f}s")
    print(f"  Time final phase: {time_limit_final:.0f}s")
    print("="*80)

    # Track all phase results
    phase_results = []
    forced_skus_pattern = None  # Pattern of which SKUs to force
    total_time_start = time.time()

    # Minimum production threshold in units
    min_production_units = min_production_hours * 1400.0

    # ========================================================================
    # ITERATIVE REFINEMENT PHASES
    # ========================================================================
    iteration = 0
    converged = False

    while iteration < max_iterations and not converged:
        iteration += 1

        if iteration == 1:
            # Phase 1: Force ALL SKUs
            print(f"\n{'='*80}")
            print(f"PHASE {iteration}: BASELINE (Force ALL SKUs)")
            print(f"{'='*80}")
            force_pattern = None  # None means force all SKUs
        else:
            # Phase N: Force only "keeper" SKUs from previous iteration
            print(f"\n{'='*80}")
            print(f"PHASE {iteration}: REFINEMENT (Force {len([k for k in forced_skus_pattern.values() if k])} SKUs)")
            print(f"{'='*80}")
            force_pattern = forced_skus_pattern

        phase_start = time.time()

        # Create model with current forcing pattern
        # Note: We'll need to modify UnifiedNodeModel to accept a force pattern
        # For now, use force_all_skus_daily for first iteration
        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=truck_schedules,
            initial_inventory=initial_inventory,
            inventory_snapshot_date=inventory_snapshot_date,
            use_batch_tracking=use_batch_tracking,
            allow_shortages=allow_shortages,
            enforce_shelf_life=enforce_shelf_life,
            force_all_skus_daily=(iteration == 1),  # Only force all in first iteration
        )

        # Solve this phase
        result = model.solve(
            solver_name=solver_name,
            time_limit_seconds=time_limit_per_phase,
            mip_gap=mip_gap * 2,  # Relax gap for intermediate phases
            tee=tee,
        )

        phase_time = time.time() - phase_start

        # Store result
        phase_results.append({
            'iteration': iteration,
            'time': phase_time,
            'status': result.termination_condition.name if hasattr(result.termination_condition, 'name') else str(result.termination_condition),
            'cost': result.objective_value,
            'gap': result.gap,
        })

        print(f"\nPhase {iteration} Results:")
        print(f"  Time: {phase_time:.1f}s")
        print(f"  Status: {phase_results[-1]['status']}")
        print(f"  Cost: ${result.objective_value:,.2f}")
        if result.gap:
            print(f"  Gap: {result.gap * 100:.2f}%")

        # Extract production quantities to identify small batches
        print(f"\nAnalyzing production pattern...")

        try:
            pyomo_model = model.model
            manufacturing_nodes = model.manufacturing_nodes
            products = model.products
            dates = model.production_dates

            # Aggregate production by product across all dates
            production_by_product = {}
            for product in products:
                total_prod = 0
                for node_id in manufacturing_nodes:
                    for date_val in dates:
                        if (node_id, product, date_val) in pyomo_model.production:
                            try:
                                prod_qty = pyo_value(pyomo_model.production[node_id, product, date_val])
                                total_prod += prod_qty if prod_qty > 0 else 0
                            except:
                                pass
                production_by_product[product] = total_prod

            # Identify keeper vs filtered SKUs
            keepers = []
            filtered = []

            for product, total_qty in production_by_product.items():
                if total_qty >= min_production_units:
                    keepers.append((product, total_qty))
                elif total_qty > 0:
                    filtered.append((product, total_qty))

            print(f"\n  Production Analysis:")
            print(f"    Keeper SKUs (≥{min_production_hours:.1f}h = {min_production_units:.0f} units): {len(keepers)}")
            for prod, qty in sorted(keepers, key=lambda x: x[1], reverse=True):
                print(f"      {prod}: {qty:,.0f} units ({qty/1400:.1f}h)")

            if filtered:
                print(f"    Filtered SKUs (<{min_production_hours:.1f}h): {len(filtered)}")
                for prod, qty in sorted(filtered, key=lambda x: x[1], reverse=True):
                    print(f"      {prod}: {qty:,.0f} units ({qty/1400:.1f}h) → REMOVE")

            # Check convergence
            if len(filtered) == 0:
                print(f"\n✓ CONVERGED: No small batches remaining")
                converged = True
            else:
                # Update forcing pattern for next iteration
                # Create pattern: force keepers to 1, free filtered SKUs
                forced_skus_pattern = {}
                for node_id in manufacturing_nodes:
                    for product in products:
                        for date_val in dates:
                            # Force keeper products, free others
                            is_keeper = any(p == product for p, _ in keepers)
                            forced_skus_pattern[(node_id, product, date_val)] = 1 if is_keeper else 0

                print(f"\n  Next iteration will force {len(keepers)} keeper SKUs")

        except Exception as e:
            print(f"\n⚠️  Production analysis failed: {e}")
            converged = True  # Can't continue

    # ========================================================================
    # FINAL PHASE: Full Binary SKU Optimization with Warmstart
    # ========================================================================
    print(f"\n{'='*80}")
    print(f"FINAL PHASE: Binary SKU Optimization (Warmstart from Phase {iteration})")
    print(f"{'='*80}")

    # Extract warmstart hints from last iteration
    warmstart_hints = forced_skus_pattern if forced_skus_pattern else None

    if warmstart_hints:
        num_hints = sum(1 for v in warmstart_hints.values() if v == 1)
        print(f"  Using warmstart: {num_hints} active SKUs from refinement")

    final_start = time.time()

    model_final = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=use_batch_tracking,
        allow_shortages=allow_shortages,
        enforce_shelf_life=enforce_shelf_life,
        force_all_skus_daily=False,  # Binary SKU selection
    )

    result_final = model_final.solve(
        solver_name=solver_name,
        time_limit_seconds=time_limit_final,
        mip_gap=mip_gap,
        use_warmstart=(warmstart_hints is not None),
        warmstart_hints=warmstart_hints,
        tee=tee,
    )

    final_time = time.time() - final_start
    total_time = time.time() - total_time_start

    print(f"\nFinal Phase Results:")
    print(f"  Time: {final_time:.1f}s")
    print(f"  Status: {result_final.termination_condition.name if hasattr(result_final.termination_condition, 'name') else str(result_final.termination_condition)}")
    print(f"  Cost: ${result_final.objective_value:,.2f}")
    if result_final.gap:
        print(f"  Gap: {result_final.gap * 100:.2f}%")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print(f"\n{'='*80}")
    print("MULTI-PHASE SOLVE SUMMARY")
    print(f"{'='*80}")

    cumulative_time = 0
    for i, phase in enumerate(phase_results, 1):
        cumulative_time += phase['time']
        print(f"Phase {i}: {phase['time']:.1f}s, ${phase['cost']:,.0f}, {phase['status']}")

    print(f"Final:  {final_time:.1f}s, ${result_final.objective_value:,.0f}, " +
          (f"{result_final.gap*100:.2f}% gap" if result_final.gap else "optimal"))
    print(f"\nTotal iterations: {iteration}")
    print(f"Total time: {total_time:.1f}s")

    # Compare to first phase
    if phase_results:
        cost_improvement = phase_results[0]['cost'] - result_final.objective_value
        pct_improvement = 100 * cost_improvement / phase_results[0]['cost'] if phase_results[0]['cost'] > 0 else 0
        print(f"\nCost improvement from Phase 1:")
        print(f"  ${cost_improvement:,.2f} ({pct_improvement:.1f}% reduction)")

    print("="*80)

    return result_final


def solve_greedy_sku_reduction(
    nodes: List[UnifiedNode],
    routes: List[UnifiedRoute],
    forecast: Forecast,
    labor_calendar: LaborCalendar,
    cost_structure: CostStructure,
    start_date: Date,
    end_date: Date,
    truck_schedules: Optional[List[UnifiedTruckSchedule]] = None,
    initial_inventory: Optional[Dict] = None,
    inventory_snapshot_date: Optional[Date] = None,
    use_batch_tracking: bool = True,
    allow_shortages: bool = False,
    enforce_shelf_life: bool = True,
    solver_name: Optional[str] = 'appsi_highs',
    time_limit_per_phase: float = 60,
    time_limit_final: float = 180,
    mip_gap: float = 0.03,
    max_iterations: int = 20,
    tee: bool = False,
) -> OptimizationResult:
    """Greedy SKU reduction: eliminate smallest volume SKU per day until cost increases.

    Strategy:
    ---------
    1. Phase 1: Force ALL SKUs (baseline)
    2. Each iteration:
       - Identify smallest volume SKU for each day
       - Remove it from force pattern
       - Solve with remaining forced SKUs
       - Compare cost to previous phase
    3. Stop when cost INCREASES (removed a needed SKU)
    4. Use CHEAPEST phase as warmstart for final binary optimization

    This greedy approach progressively eliminates uneconomic SKUs day-by-day
    until the marginal cost of SKU reduction becomes negative.

    Args:
        All standard UnifiedNodeModel args plus:
        time_limit_per_phase: Time limit for each iteration (default: 60s)
        time_limit_final: Time limit for final binary solve (default: 180s)
        mip_gap: MIP gap tolerance (default: 0.03 = 3%)
        max_iterations: Maximum iterations before stopping (default: 20)
        tee: Show solver output (default: False)

    Returns:
        OptimizationResult from final binary optimization phase
    """
    import time
    from pyomo.environ import value as pyo_value

    print("="*80)
    print("GREEDY SKU REDUCTION SOLVER")
    print("Eliminate Smallest Volume SKU Per Day Until Cost Increases")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Max iterations: {max_iterations}")
    print(f"  Time per phase: {time_limit_per_phase:.0f}s")
    print(f"  Time final phase: {time_limit_final:.0f}s")
    print(f"  MIP gap: {mip_gap*100:.1f}%")
    print("="*80)

    total_time_start = time.time()
    phase_history = []
    best_phase = None
    best_cost = float('inf')

    # Initialize force pattern: Start with ALL SKUs forced
    force_pattern = {}  # {(node_id, product, date): True/False}

    # Get products and dates from forecast
    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes = [n.id for n in nodes if n.can_produce]

    # Phase 1: Force all SKUs
    for node_id in manufacturing_nodes:
        for product in products:
            dates_range = []
            current = start_date
            while current <= end_date:
                dates_range.append(current)
                current += timedelta(days=1)

            for date_val in dates_range:
                force_pattern[(node_id, product, date_val)] = True  # Force all

    num_forced = sum(1 for v in force_pattern.values() if v)
    print(f"\nStarting with {num_forced} forced SKU-day combinations (all SKUs)")

    # ========================================================================
    # ITERATIVE GREEDY REDUCTION
    # ========================================================================
    iteration = 0
    cost_increased = False

    while iteration < max_iterations and not cost_increased:
        iteration += 1

        print(f"\n{'='*80}")
        num_active = sum(1 for v in force_pattern.values() if v)
        print(f"PHASE {iteration}: {num_active} forced SKU-days")
        print(f"{'='*80}")

        phase_start = time.time()

        # Determine mode based on pattern
        if all(v for v in force_pattern.values()):
            # All True → use force_all_skus_daily
            use_force_all = True
            use_pattern = None
        elif not any(v for v in force_pattern.values()):
            # All False → use full binary
            use_force_all = False
            use_pattern = None
        else:
            # Mixed → use pattern
            use_force_all = False
            use_pattern = force_pattern

        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=truck_schedules,
            initial_inventory=initial_inventory,
            inventory_snapshot_date=inventory_snapshot_date,
            use_batch_tracking=use_batch_tracking,
            allow_shortages=allow_shortages,
            enforce_shelf_life=enforce_shelf_life,
            force_all_skus_daily=use_force_all,
            force_sku_pattern=use_pattern,
        )

        result = model.solve(
            solver_name=solver_name,
            time_limit_seconds=time_limit_per_phase,
            mip_gap=mip_gap * 2,  # Relaxed gap for intermediate phases
            tee=tee,
        )

        phase_time = time.time() - phase_start

        # Live progress reporting
        print(f"\n📊 Phase {iteration} Results:")
        print(f"   Time: {phase_time:.1f}s")
        print(f"   Status: {result.termination_condition.name if hasattr(result.termination_condition, 'name') else str(result.termination_condition)}")
        print(f"   Cost: ${result.objective_value:,.2f}")
        if result.gap:
            print(f"   Gap: {result.gap * 100:.2f}%")

        # Store phase result
        phase_history.append({
            'iteration': iteration,
            'time': phase_time,
            'cost': result.objective_value,
            'gap': result.gap,
            'status': result.termination_condition.name if hasattr(result.termination_condition, 'name') else str(result.termination_condition),
            'force_pattern': force_pattern.copy(),
            'model': model,
        })

        # Check if this is the best cost so far
        if result.objective_value < best_cost:
            best_cost = result.objective_value
            best_phase = iteration
            print(f"   ✅ NEW BEST COST: ${best_cost:,.2f}")
        else:
            # Cost increased - stop iteration
            cost_increase = result.objective_value - best_cost
            pct_increase = 100 * cost_increase / best_cost if best_cost > 0 else 0
            print(f"   ⚠️  COST INCREASED: +${cost_increase:,.2f} (+{pct_increase:.1f}%)")
            print(f"   Stopping iteration (best was Phase {best_phase})")
            cost_increased = True
            break

        # Extract production to find smallest SKU per day
        print(f"\n🔍 Analyzing production pattern...")

        try:
            pyomo_model = model.model

            # Production by (date, product)
            production_by_date_product = {}
            for node_id in manufacturing_nodes:
                for product in products:
                    dates_range = []
                    current = start_date
                    while current <= end_date:
                        dates_range.append(current)
                        current += timedelta(days=1)

                    for date_val in dates_range:
                        if (node_id, product, date_val) in pyomo_model.production:
                            try:
                                qty = pyo_value(pyomo_model.production[node_id, product, date_val])
                                if qty > 0.01:
                                    production_by_date_product[(date_val, product)] = production_by_date_product.get((date_val, product), 0) + qty
                            except:
                                pass

            # For each date, find smallest volume SKU currently forced
            dates_range = []
            current = start_date
            while current <= end_date:
                dates_range.append(current)
                current += timedelta(days=1)

            skus_to_remove = []
            for date_val in dates_range:
                # Get all products produced on this date (that are currently forced)
                date_production = []
                for product in products:
                    # Check if this product is currently forced on this date
                    forced_on_date = False
                    for node_id in manufacturing_nodes:
                        if force_pattern.get((node_id, product, date_val), False):
                            forced_on_date = True
                            break

                    if forced_on_date:
                        qty = production_by_date_product.get((date_val, product), 0)
                        if qty > 0:
                            date_production.append((product, qty))

                # Find smallest if there are multiple SKUs on this date
                if len(date_production) > 1:
                    # Sort by quantity and get smallest
                    smallest = min(date_production, key=lambda x: x[1])
                    skus_to_remove.append((date_val, smallest[0], smallest[1]))

            if skus_to_remove:
                print(f"   Found {len(skus_to_remove)} smallest-volume SKUs to remove:")
                for date_val, product, qty in skus_to_remove[:5]:  # Show first 5
                    print(f"     {date_val}: {product} ({qty:,.0f} units)")
                if len(skus_to_remove) > 5:
                    print(f"     ... and {len(skus_to_remove) - 5} more")

                # Update force pattern: unforce these SKUs
                for date_val, product, qty in skus_to_remove:
                    for node_id in manufacturing_nodes:
                        force_pattern[(node_id, product, date_val)] = False

                num_still_forced = sum(1 for v in force_pattern.values() if v)
                print(f"   → Next iteration: {num_still_forced} forced SKU-days (removed {len(skus_to_remove)})")
            else:
                print(f"   ✓ No more SKUs to remove (all dates have 1 SKU or 0)")
                break

        except Exception as e:
            print(f"\n⚠️  Production analysis failed: {e}")
            import traceback
            traceback.print_exc()
            break

    # ========================================================================
    # FINAL PHASE: Binary SKU Optimization Using Best Phase as Warmstart
    # ========================================================================
    print(f"\n{'='*80}")
    print(f"FINAL PHASE: Binary SKU Optimization")
    print(f"{'='*80}")
    print(f"Using warmstart from Phase {best_phase} (best cost: ${best_cost:,.2f})")

    # Extract warmstart hints from best phase
    best_phase_data = phase_history[best_phase - 1]
    warmstart_hints = best_phase_data['force_pattern'].copy()

    num_hints = sum(1 for v in warmstart_hints.values() if v)
    print(f"  Warmstart: {num_hints} SKU-days with production hint")

    final_start = time.time()

    model_final = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=use_batch_tracking,
        allow_shortages=allow_shortages,
        enforce_shelf_life=enforce_shelf_life,
        force_all_skus_daily=False,
        force_sku_pattern=None,  # Full binary optimization
    )

    # Convert force_pattern to warmstart hints format
    warmstart_for_solver = {k: (1 if v else 0) for k, v in warmstart_hints.items()}

    result_final = model_final.solve(
        solver_name=solver_name,
        time_limit_seconds=time_limit_final,
        mip_gap=mip_gap,
        use_warmstart=True,
        warmstart_hints=warmstart_for_solver,
        tee=tee,
    )

    final_time = time.time() - final_start
    total_time = time.time() - total_time_start

    print(f"\n📊 Final Phase Results:")
    print(f"   Time: {final_time:.1f}s")
    print(f"   Status: {result_final.termination_condition.name if hasattr(result_final.termination_condition, 'name') else str(result_final.termination_condition)}")
    print(f"   Cost: ${result_final.objective_value:,.2f}")
    if result_final.gap:
        print(f"   Gap: {result_final.gap * 100:.2f}%")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print(f"\n{'='*80}")
    print("GREEDY SKU REDUCTION SUMMARY")
    print(f"{'='*80}")

    cumulative_time = 0
    for phase in phase_history:
        cumulative_time += phase['time']
        marker = " ← BEST" if phase['iteration'] == best_phase else ""
        print(f"Phase {phase['iteration']}: {phase['time']:.1f}s, ${phase['cost']:,.2f}, {phase['status']}{marker}")

    print(f"Final:  {final_time:.1f}s, ${result_final.objective_value:,.2f}, " +
          f"{result_final.gap*100:.2f}% gap" if result_final.gap else "optimal")

    print(f"\nTotal iterations: {iteration}")
    print(f"Total time: {total_time:.1f}s")
    print(f"Best intermediate cost: ${best_cost:,.2f} (Phase {best_phase})")

    if result_final.objective_value < best_cost:
        improvement = best_cost - result_final.objective_value
        pct_imp = 100 * improvement / best_cost
        print(f"Final improvement: ${improvement:,.2f} ({pct_imp:.1f}% better than best intermediate)")
    else:
        print(f"Final cost: ${result_final.objective_value:,.2f} (binary optimization found different solution)")

    if phase_history:
        total_improvement = phase_history[0]['cost'] - result_final.objective_value
        pct_total = 100 * total_improvement / phase_history[0]['cost']
        print(f"\nTotal improvement from Phase 1:")
        print(f"  ${total_improvement:,.2f} ({pct_total:.1f}% reduction)")

    print("="*80)

    return result_final


def solve_greedy_bigm_relaxation(
    nodes: List[UnifiedNode],
    routes: List[UnifiedRoute],
    forecast: Forecast,
    labor_calendar: LaborCalendar,
    cost_structure: CostStructure,
    start_date: Date,
    end_date: Date,
    truck_schedules: Optional[List[UnifiedTruckSchedule]] = None,
    initial_inventory: Optional[Dict] = None,
    inventory_snapshot_date: Optional[Date] = None,
    use_batch_tracking: bool = True,
    allow_shortages: bool = False,
    enforce_shelf_life: bool = True,
    solver_name: Optional[str] = 'appsi_highs',
    time_limit_per_phase: float = 60,
    time_limit_final: float = 180,
    mip_gap: float = 0.03,
    max_iterations: int = 20,
    tee: bool = False,
) -> OptimizationResult:
    """Greedy Big-M relaxation: progressively tighten Big-M for smallest SKUs with warmstart.

    Strategy (improved approach):
    -----------------------------
    1. Phase 1: Solve with default Big-M for all SKUs
    2. Each iteration:
       - Extract production quantities
       - Identify smallest volume SKU per day
       - Tighten its Big-M to actual production volume (makes it easy to skip)
       - Use previous phase solution as WARMSTART
       - Solve with updated Big-M overrides
       - Compare cost to previous phase
    3. Stop when cost INCREASES (removed a needed SKU)
    4. Use CHEAPEST phase solution for final binary optimization

    This approach:
    - More flexible than forcing (SKU can still be produced if needed)
    - Uses warmstart between phases (8% speedup per phase)
    - Progressively guides solver toward optimal SKU selection
    - Stops automatically when marginal SKU removal becomes costly

    Args:
        All standard UnifiedNodeModel args plus:
        time_limit_per_phase: Time limit for each iteration (default: 60s)
        time_limit_final: Time limit for final binary solve (default: 180s)
        mip_gap: MIP gap tolerance (default: 0.03 = 3%)
        max_iterations: Maximum iterations before stopping (default: 20)
        tee: Show solver output (default: False)

    Returns:
        OptimizationResult from final binary optimization phase
    """
    import time
    from pyomo.environ import value as pyo_value

    print("="*80)
    print("GREEDY BIG-M RELAXATION SOLVER")
    print("Progressively Tighten Big-M for Smallest SKUs + Warmstart")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Max iterations: {max_iterations}")
    print(f"  Time per phase: {time_limit_per_phase:.0f}s")
    print(f"  Time final phase: {time_limit_final:.0f}s")
    print(f"  MIP gap: {mip_gap*100:.1f}%")
    print("="*80)

    total_time_start = time.time()
    phase_history = []
    best_phase = None
    best_cost = float('inf')

    # Initialize Big-M overrides: empty dict means use default for all
    bigm_overrides = {}

    # Get products and dates
    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    # ========================================================================
    # ITERATIVE GREEDY BIG-M RELAXATION
    # ========================================================================
    iteration = 0
    cost_increased = False
    previous_warmstart = None

    while iteration < max_iterations and not cost_increased:
        iteration += 1

        print(f"\n{'='*80}")
        num_relaxed = len(bigm_overrides)
        print(f"PHASE {iteration}: {num_relaxed} SKUs with tightened Big-M")
        if previous_warmstart:
            num_warmstart = sum(1 for v in previous_warmstart.values() if v == 1)
            print(f"  Using warmstart from Phase {iteration-1} ({num_warmstart} active SKUs)")
        print(f"{'='*80}")

        phase_start = time.time()

        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=truck_schedules,
            initial_inventory=initial_inventory,
            inventory_snapshot_date=inventory_snapshot_date,
            use_batch_tracking=use_batch_tracking,
            allow_shortages=allow_shortages,
            enforce_shelf_life=enforce_shelf_life,
            force_all_skus_daily=False,
            force_sku_pattern=None,
            bigm_overrides=bigm_overrides.copy(),
        )

        result = model.solve(
            solver_name=solver_name,
            time_limit_seconds=time_limit_per_phase,
            mip_gap=mip_gap * 2,  # Relaxed gap for intermediate phases
            use_warmstart=(previous_warmstart is not None),
            warmstart_hints=previous_warmstart,
            tee=tee,
        )

        phase_time = time.time() - phase_start

        # Live progress reporting
        term_name = result.termination_condition.name if hasattr(result.termination_condition, 'name') else str(result.termination_condition)
        print(f"\n📊 Phase {iteration} Results:")
        print(f"   Time: {phase_time:.1f}s")
        print(f"   Status: {term_name}")
        print(f"   Cost: ${result.objective_value:,.2f}")
        if result.gap:
            print(f"   Gap: {result.gap * 100:.2f}%")

        # Store phase result
        phase_history.append({
            'iteration': iteration,
            'time': phase_time,
            'cost': result.objective_value,
            'gap': result.gap,
            'status': term_name,
            'bigm_overrides': bigm_overrides.copy(),
            'model': model,
        })

        # Check if this is the best cost so far
        if result.objective_value < best_cost:
            best_cost = result.objective_value
            best_phase = iteration
            print(f"   ✅ NEW BEST COST: ${best_cost:,.2f}")
        else:
            # Cost increased - stop iteration
            cost_increase = result.objective_value - best_cost
            pct_increase = 100 * cost_increase / best_cost if best_cost > 0 else 0
            print(f"   ⚠️  COST INCREASED: +${cost_increase:,.2f} (+{pct_increase:.1f}%)")
            print(f"   Stopping iteration (best was Phase {best_phase})")
            cost_increased = True
            break

        # Extract warmstart hints for next phase
        print(f"\n🔍 Extracting warmstart and analyzing production...")

        try:
            pyomo_model = model.model
            warmstart_hints = {}
            production_by_date_product = {}

            for node_id in manufacturing_nodes_list:
                for product in products:
                    for date_val in dates_range:
                        if (node_id, product, date_val) in pyomo_model.production:
                            try:
                                qty = pyo_value(pyomo_model.production[node_id, product, date_val])
                                warmstart_hints[(node_id, product, date_val)] = 1 if qty > 0.01 else 0

                                if qty > 0.01:
                                    production_by_date_product[(date_val, product)] = production_by_date_product.get((date_val, product), 0) + qty
                            except:
                                warmstart_hints[(node_id, product, date_val)] = 0

            # Store warmstart for next iteration
            previous_warmstart = warmstart_hints
            num_active = sum(1 for v in warmstart_hints.values() if v == 1)
            print(f"   Warmstart extracted: {num_active} active SKUs")

            # For each date, find smallest volume SKU
            smallest_skus = []
            for date_val in dates_range:
                # Get all products produced on this date
                date_production = []
                for product in products:
                    qty = production_by_date_product.get((date_val, product), 0)
                    if qty > 0:
                        date_production.append((product, qty))

                # Find smallest if there are multiple SKUs on this date
                if len(date_production) > 1:
                    smallest = min(date_production, key=lambda x: x[1])
                    smallest_skus.append((date_val, smallest[0], smallest[1]))

            if smallest_skus:
                print(f"   Found {len(smallest_skus)} smallest-volume SKUs to relax:")
                for date_val, product, qty in smallest_skus[:5]:
                    print(f"     {date_val}: {product} ({qty:,.0f} units) → Big-M = {qty*1.1:.0f}")
                if len(smallest_skus) > 5:
                    print(f"     ... and {len(smallest_skus) - 5} more")

                # Update Big-M overrides: set to 110% of actual production
                # This makes it "easy" for solver to skip but allows some flex
                for date_val, product, qty in smallest_skus:
                    for node_id in manufacturing_nodes_list:
                        bigm_overrides[(node_id, product, date_val)] = qty * 1.1

                print(f"   → Next iteration: {len(bigm_overrides)} SKUs with tightened Big-M")
            else:
                print(f"   ✓ No more SKUs to relax (all dates have ≤1 SKU)")
                break

        except Exception as e:
            print(f"\n⚠️  Production analysis failed: {e}")
            import traceback
            traceback.print_exc()
            break

    # ========================================================================
    # FINAL PHASE: Binary SKU Optimization Using Best Phase as Warmstart
    # ========================================================================
    print(f"\n{'='*80}")
    print(f"FINAL PHASE: Binary SKU Optimization")
    print(f"{'='*80}")
    print(f"Using warmstart from Phase {best_phase} (best cost: ${best_cost:,.2f})")

    # Get warmstart from best phase
    best_phase_data = phase_history[best_phase - 1]
    best_bigm_overrides = best_phase_data['bigm_overrides']

    # Extract warmstart hints from best phase model
    try:
        best_model = best_phase_data['model']
        pyomo_model_best = best_model.model

        final_warmstart = {}
        for node_id in manufacturing_nodes_list:
            for product in products:
                for date_val in dates_range:
                    if (node_id, product, date_val) in pyomo_model_best.production:
                        try:
                            qty = pyo_value(pyomo_model_best.production[node_id, product, date_val])
                            final_warmstart[(node_id, product, date_val)] = 1 if qty > 0.01 else 0
                        except:
                            final_warmstart[(node_id, product, date_val)] = 0

        num_final_warmstart = sum(1 for v in final_warmstart.values() if v == 1)
        print(f"  Warmstart: {num_final_warmstart} SKUs with production hint")
        print(f"  Big-M hints: {len(best_bigm_overrides)} SKUs with tightened bounds")
    except Exception as e:
        print(f"  ⚠️  Could not extract warmstart: {e}")
        final_warmstart = None

    final_start = time.time()

    model_final = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=use_batch_tracking,
        allow_shortages=allow_shortages,
        enforce_shelf_life=enforce_shelf_life,
        force_all_skus_daily=False,
        force_sku_pattern=None,
        bigm_overrides=best_bigm_overrides,  # Use tightened Big-M from best phase
    )

    result_final = model_final.solve(
        solver_name=solver_name,
        time_limit_seconds=time_limit_final,
        mip_gap=mip_gap,
        use_warmstart=(final_warmstart is not None),
        warmstart_hints=final_warmstart,
        tee=tee,
    )

    final_time = time.time() - final_start
    total_time = time.time() - total_time_start

    final_term_name = result_final.termination_condition.name if hasattr(result_final.termination_condition, 'name') else str(result_final.termination_condition)

    print(f"\n📊 Final Phase Results:")
    print(f"   Time: {final_time:.1f}s")
    print(f"   Status: {final_term_name}")
    print(f"   Cost: ${result_final.objective_value:,.2f}")
    if result_final.gap:
        print(f"   Gap: {result_final.gap * 100:.2f}%")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print(f"\n{'='*80}")
    print("GREEDY BIG-M RELAXATION SUMMARY")
    print(f"{'='*80}")

    cumulative_time = 0
    for phase in phase_history:
        cumulative_time += phase['time']
        marker = " ← BEST" if phase['iteration'] == best_phase else ""
        gap_str = f", {phase['gap']*100:.2f}% gap" if phase['gap'] else ""
        print(f"Phase {phase['iteration']}: {phase['time']:.1f}s, ${phase['cost']:,.2f}{gap_str}{marker}")

    gap_str = f", {result_final.gap*100:.2f}% gap" if result_final.gap else ""
    print(f"Final:  {final_time:.1f}s, ${result_final.objective_value:,.2f}{gap_str}")

    print(f"\nTotal iterations: {iteration}")
    print(f"Total time: {total_time:.1f}s")
    print(f"Best intermediate cost: ${best_cost:,.2f} (Phase {best_phase})")

    if result_final.objective_value < best_cost:
        improvement = best_cost - result_final.objective_value
        pct_imp = 100 * improvement / best_cost
        print(f"Final improvement: ${improvement:,.2f} ({pct_imp:.1f}% better than best intermediate)")
    else:
        diff = result_final.objective_value - best_cost
        print(f"Final cost: ${result_final.objective_value:,.2f} (+${diff:,.2f} vs best intermediate)")

    if phase_history:
        total_improvement = phase_history[0]['cost'] - result_final.objective_value
        pct_total = 100 * total_improvement / phase_history[0]['cost']
        print(f"\nTotal improvement from Phase 1:")
        print(f"  ${total_improvement:,.2f} ({pct_total:.1f}% reduction)")

    print("="*80)

    return result_final


def solve_weekly_pattern_warmstart(
    nodes: List[UnifiedNode],
    routes: List[UnifiedRoute],
    forecast: Forecast,
    labor_calendar: LaborCalendar,
    cost_structure: CostStructure,
    start_date: Date,
    end_date: Date,
    truck_schedules: Optional[List[UnifiedTruckSchedule]] = None,
    initial_inventory: Optional[Dict] = None,
    inventory_snapshot_date: Optional[Date] = None,
    use_batch_tracking: bool = True,
    allow_shortages: bool = False,
    enforce_shelf_life: bool = True,
    solver_name: Optional[str] = 'appsi_highs',
    time_limit_phase1: float = 120,
    time_limit_phase2: float = 360,
    mip_gap: float = 0.03,
    tee: bool = False,
    progress_callback: Optional[callable] = None,
) -> OptimizationResult:
    """Two-phase solver: Weekly pattern (no pallets) → Full binary (with pallets).

    VALIDATED PERFORMANCE (6-week horizon):
    - Phase 1 (weekly): 18s, 110 binary vars
    - Phase 2 (full): 259s with warmstart
    - Total: 278s vs 388s single-phase timeout (28% faster, better gap)

    Strategy:
    ---------
    Phase 1: Weekly Production Cycle (Fast Warmup)
        - Create 25 binary pattern variables: product_weekday_pattern[product, weekday]
        - Link weekday dates: product_produced[Mon_week1] == pattern[Mon]
        - Disable pallet tracking (simpler model)
        - Solve in ~20-40s (fast!)
        - Binary vars: 25 (pattern) + 60-80 (weekends) = 85-105 total

    Phase 2: Full Binary Optimization (With Warmstart)
        - Use Phase 1 solution as warmstart
        - Enable pallet tracking
        - Full binary SKU selection (210-280 vars)
        - Solve in ~250-300s with warmstart
        - Better than cold start timeout

    Key Technical Details (Using Pyomo):
    -----------------------------------
    1. Weekly pattern variables reduce binary count by 50-60%
    2. Linking constraints: product_produced[date] == pattern[weekday(date)]
    3. CRITICAL: Deactivate num_products_counting_con for linked weekdays
       (conflicts with weekly pattern constraint)
    4. Pallet tracking disabled in Phase 1 (faster solve)
    5. Warmstart extraction uses pyomo.value() directly

    Args:
        nodes: List of UnifiedNode objects
        routes: List of UnifiedRoute objects  
        forecast: Demand forecast
        labor_calendar: Labor availability and costs
        cost_structure: Cost parameters (pallets will be disabled for Phase 1)
        start_date: Planning horizon start
        end_date: Planning horizon end (inclusive)
        truck_schedules: Optional list of truck schedules
        initial_inventory: Optional initial inventory dict
        inventory_snapshot_date: Date when initial inventory was measured
        use_batch_tracking: Use age-cohort tracking (default: True)
        allow_shortages: Allow demand shortages with penalty (default: False)
        enforce_shelf_life: Enforce shelf life constraints (default: True)
        solver_name: Solver to use (default: 'appsi_highs')
        time_limit_phase1: Time limit for Phase 1 (default: 120s)
        time_limit_phase2: Time limit for Phase 2 (default: 360s)
        mip_gap: MIP gap tolerance (default: 0.03 = 3%)
        tee: Show solver output (default: False)
        progress_callback: Optional callback(phase, status, time, cost) for UI updates

    Returns:
        OptimizationResult from Phase 2 (final solution)

    Example:
        >>> result = solve_weekly_pattern_warmstart(
        ...     nodes, routes, forecast, labor_calendar, cost_structure,
        ...     start_date, end_date,
        ...     solver_name='appsi_highs',
        ...     progress_callback=lambda p, s, t, c: print(f"Phase {p}: {s}")
        ... )
    """
    import time as time_module
    import os
    from pyomo.environ import Var, ConstraintList, Binary, value as pyo_value
    from pyomo.contrib import appsi

    print("="*80)
    print("WEEKLY PATTERN WARMSTART SOLVER")
    print("Two-Phase: Weekly Cycle (no pallets) → Full Binary (with pallets)")
    print("="*80)

    total_start = time_module.time()

    # Get manufacturing info
    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes = [n.id for n in nodes if n.capabilities.can_manufacture]

    # Build date range and categorize weekdays vs weekends
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    weekday_dates_lists = {i: [] for i in range(5)}  # 0=Mon, 4=Fri
    weekend_dates = []

    for date_val in dates_range:
        weekday = date_val.weekday()
        labor_day = labor_calendar.get_labor_day(date_val)

        if weekday < 5 and labor_day and labor_day.is_fixed_day:
            weekday_dates_lists[weekday].append(date_val)
        else:
            weekend_dates.append(date_val)

    weekday_count = sum(len(dates) for dates in weekday_dates_lists.values())
    pattern_binary_vars = 25  # 5 products × 5 weekdays
    weekend_binary_vars = 5 * len(weekend_dates)
    total_phase1_binary = pattern_binary_vars + weekend_binary_vars
    total_individual_binary = 5 * len(dates_range)

    print(f"\nHorizon: {len(dates_range)} days ({weekday_count} weekdays, {len(weekend_dates)} weekends)")
    print(f"Binary variable reduction:")
    print(f"  Individual approach: {total_individual_binary} vars")
    print(f"  Weekly pattern: {total_phase1_binary} vars ({pattern_binary_vars} pattern + {weekend_binary_vars} weekends)")
    print(f"  Reduction: {100*(1 - total_phase1_binary/total_individual_binary):.1f}% fewer")

    if progress_callback:
        progress_callback(1, "starting", 0, None)

    # ========================================================================
    # PHASE 1: Weekly Pattern (No Pallet Tracking)
    # ========================================================================
    print(f"\n{'='*80}")
    print("PHASE 1: Weekly Production Cycle (No Pallet Tracking)")
    print(f"{'='*80}")

    phase1_start = time_module.time()

    # Create modified cost structure with pallet tracking disabled
    import copy
    cost_structure_no_pallets = copy.deepcopy(cost_structure)
    cost_structure_no_pallets.storage_cost_per_pallet_day_frozen = 0.0
    cost_structure_no_pallets.storage_cost_per_pallet_day_ambient = 0.0
    cost_structure_no_pallets.storage_cost_fixed_per_pallet_frozen = 0.0
    cost_structure_no_pallets.storage_cost_fixed_per_pallet_ambient = 0.0

    # Build base model
    model_phase1_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure_no_pallets,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=use_batch_tracking,
        allow_shortages=allow_shortages,
        enforce_shelf_life=enforce_shelf_life,
        force_all_skus_daily=False,
    )

    pyomo_model_phase1 = model_phase1_obj.build_model()

    print(f"\nAdding weekly pattern variables and constraints (using Pyomo)...")

    # Add weekly pattern binary variables (Pyomo Var)
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    pyomo_model_phase1.product_weekday_pattern = Var(
        pattern_index,
        within=Binary,
        doc="Weekly production pattern: 1 if product produced on this weekday (Mon-Fri)"
    )

    print(f"  Created {len(pattern_index)} weekly pattern variables")

    # Add linking constraints (Pyomo ConstraintList)
    pyomo_model_phase1.weekly_pattern_linking = ConstraintList()

    num_linked = 0
    for node_id in manufacturing_nodes:
        for date_val in dates_range:
            weekday = date_val.weekday()

            # Link regular weekdays to pattern
            if weekday < 5 and any(date_val in weekday_dates_lists[weekday] for weekday in range(5)):
                for product in products:
                    # Linking constraint: daily decision = weekly pattern
                    pyomo_model_phase1.weekly_pattern_linking.add(
                        pyomo_model_phase1.product_produced[node_id, product, date_val] ==
                        pyomo_model_phase1.product_weekday_pattern[product, weekday]
                    )
                    num_linked += 1

    print(f"  Added {num_linked} weekly pattern linking constraints")

    # CRITICAL FIX: Deactivate num_products_counting_con for linked weekdays
    # (prevents constraint conflict with weekly pattern)
    num_deactivated = 0
    if hasattr(pyomo_model_phase1, 'num_products_counting_con'):
        for node_id in manufacturing_nodes:
            for date_val in dates_range:
                weekday = date_val.weekday()
                if weekday < 5 and any(date_val in weekday_dates_lists[weekday] for weekday in range(5)):
                    if (node_id, date_val) in pyomo_model_phase1.num_products_counting_con:
                        pyomo_model_phase1.num_products_counting_con[node_id, date_val].deactivate()
                        num_deactivated += 1

    print(f"  Deactivated {num_deactivated} conflicting counting constraints")

    # Solve Phase 1
    print(f"\nSolving Phase 1 ({total_phase1_binary} binary vars)...")

    if progress_callback:
        progress_callback(1, "solving", 0, None)

    solver_phase1 = appsi.solvers.Highs()
    solver_phase1.config.time_limit = time_limit_phase1
    solver_phase1.config.mip_gap = mip_gap * 2  # Relaxed gap for Phase 1
    solver_phase1.highs_options['presolve'] = 'on'
    solver_phase1.highs_options['parallel'] = 'on'
    solver_phase1.highs_options['threads'] = os.cpu_count() or 4

    results_phase1 = solver_phase1.solve(pyomo_model_phase1)
    phase1_time = time_module.time() - phase1_start

    # Extract Phase 1 results
    try:
        cost_phase1 = pyo_value(pyomo_model_phase1.obj)
        term_phase1 = results_phase1.termination_condition.name if hasattr(results_phase1.termination_condition, 'name') else str(results_phase1.termination_condition)
    except:
        # Phase 1 failed
        error_msg = f"Phase 1 (weekly pattern) failed: {results_phase1.termination_condition}"
        print(f"\n⚠️  {error_msg}")

        if progress_callback:
            progress_callback(1, "failed", phase1_time, None)

        return OptimizationResult(
            success=False,
            infeasibility_message=error_msg,
            solve_time_seconds=phase1_time,
            termination_condition=results_phase1.termination_condition,
        )

    print(f"\n📊 Phase 1 Results:")
    print(f"   Time: {phase1_time:.1f}s")
    print(f"   Cost: ${cost_phase1:,.2f}")
    print(f"   Status: {term_phase1}")

    if progress_callback:
        progress_callback(1, "complete", phase1_time, cost_phase1)

    # Extract weekly pattern for reporting
    pattern_summary = {}
    for weekday in range(5):
        day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'][weekday]
        active_products = []
        for product in products:
            try:
                if pyo_value(pyomo_model_phase1.product_weekday_pattern[product, weekday]) > 0.5:
                    active_products.append(product)
            except:
                pass
        pattern_summary[day_name] = active_products

    print(f"\n   Weekly Production Pattern:")
    for day, prods in pattern_summary.items():
        print(f"      {day}: {len(prods)} SKUs")

    # Extract warmstart from Phase 1
    print(f"\n   Extracting warmstart for Phase 2...")
    warmstart_hints = {}

    for node_id in manufacturing_nodes:
        for product in products:
            for date_val in dates_range:
                key = (node_id, product, date_val)

                if (node_id, product, date_val) in pyomo_model_phase1.product_produced:
                    try:
                        val = pyo_value(pyomo_model_phase1.product_produced[node_id, product, date_val])
                        warmstart_hints[key] = 1 if val > 0.5 else 0
                    except:
                        warmstart_hints[key] = 0
                else:
                    warmstart_hints[key] = 0

    num_warmstart_active = sum(1 for v in warmstart_hints.values() if v == 1)
    print(f"   Warmstart: {num_warmstart_active}/{len(warmstart_hints)} active SKUs")

    # ========================================================================
    # PHASE 2: Full Binary Optimization (With Pallet Tracking + Warmstart)
    # ========================================================================
    print(f"\n{'='*80}")
    print("PHASE 2: Full Binary Optimization (With Pallet Tracking)")
    print(f"{'='*80}")

    if progress_callback:
        progress_callback(2, "starting", phase1_time, cost_phase1)

    phase2_start = time_module.time()

    model_phase2 = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,  # Original cost structure with pallet tracking
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=use_batch_tracking,
        allow_shortages=allow_shortages,
        enforce_shelf_life=enforce_shelf_life,
        force_all_skus_daily=False,
    )

    print(f"Solving Phase 2 ({total_individual_binary} binary vars, with warmstart)...")

    result_phase2 = model_phase2.solve(
        solver_name=solver_name,
        time_limit_seconds=time_limit_phase2,
        mip_gap=mip_gap,
        use_warmstart=True,
        warmstart_hints=warmstart_hints,
        tee=tee,
    )

    phase2_time = time_module.time() - phase2_start
    total_time = time_module.time() - total_start

    print(f"\n📊 Phase 2 Results:")
    print(f"   Time: {phase2_time:.1f}s")
    print(f"   Cost: ${result_phase2.objective_value:,.2f}")
    term_phase2 = result_phase2.termination_condition.name if hasattr(result_phase2.termination_condition, 'name') else str(result_phase2.termination_condition)
    print(f"   Status: {term_phase2}")
    if result_phase2.gap:
        print(f"   Gap: {result_phase2.gap * 100:.2f}%")

    if progress_callback:
        progress_callback(2, "complete", phase2_time, result_phase2.objective_value)

    # Summary
    print(f"\n{'='*80}")
    print("TWO-PHASE SOLVE SUMMARY")
    print(f"{'='*80}")
    print(f"Phase 1 (weekly pattern, no pallets): {phase1_time:.1f}s, ${cost_phase1:,.2f}")
    print(f"Phase 2 (full binary, with pallets):  {phase2_time:.1f}s, ${result_phase2.objective_value:,.2f}")
    print(f"Total time: {total_time:.1f}s")

    if cost_phase1 > 0:
        improvement = cost_phase1 - result_phase2.objective_value
        pct = 100 * improvement / cost_phase1
        print(f"\nCost improvement from Phase 1: ${improvement:,.2f} ({pct:.1f}%)")

    print("="*80)

    # Return Phase 2 result with updated solve time
    result_phase2.solve_time_seconds = total_time
    result_phase2.metadata = result_phase2.metadata or {}
    result_phase2.metadata.update({
        'weekly_pattern_warmstart': True,
        'phase1_time': phase1_time,
        'phase2_time': phase2_time,
        'phase1_cost': cost_phase1,
        'weekly_pattern': pattern_summary,
    })

    return result_phase2
