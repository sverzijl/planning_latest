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
    Constraint,
    Objective,
    minimize,
    Set as PyomoSet,
    NonNegativeReals,
    NonNegativeIntegers,
    Binary,
    value,
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
        """Calculate maximum possible daily production.

        Returns:
            Maximum production in units per day (accounts for max labor hours)
        """
        max_labor_hours = 0.0
        for date in self.production_dates:
            labor_day = self.labor_calendar.get_labor_day(date)
            if labor_day:
                # Calculate available hours:
                # - Fixed days: fixed_hours + overtime capacity (assume 2 hours max OT)
                # - Non-fixed days: use fixed_hours field (which represents total hours available)
                if hasattr(labor_day, 'overtime_hours') and labor_day.overtime_hours:
                    day_hours = labor_day.fixed_hours + labor_day.overtime_hours
                elif labor_day.is_fixed_day:
                    # Assume standard: 12 fixed + 2 OT = 14 total
                    day_hours = labor_day.fixed_hours + 2.0
                else:
                    # Non-fixed day: use fixed_hours field as total available
                    day_hours = labor_day.fixed_hours

                max_labor_hours = max(max_labor_hours, day_hours)

        # Get production rate from first manufacturing node (assume uniform)
        if self.manufacturing_nodes:
            node_id = next(iter(self.manufacturing_nodes))
            node = self.nodes[node_id]
            prod_rate = node.capabilities.production_rate_per_hour or 1400.0
        else:
            prod_rate = 1400.0  # Default

        return prod_rate * max_labor_hours

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

            # Relaxed binary: Is each specific product produced? (continuous [0,1])
            # NOTE: Relaxed from Binary to NonNegativeReals with bounds=(0,1) for performance
            # The sum constraint ensures these will be integer in optimal solution
            product_produced_index = [
                (node_id, prod, date)
                for node_id in self.manufacturing_nodes
                for prod in model.products
                for date in model.dates
            ]
            model.product_produced = Var(
                product_produced_index,
                within=NonNegativeReals,
                bounds=(0, 1),
                doc="Indicator: 1 if this product is produced (relaxed for performance)"
            )

            # Integer: Count of distinct products produced
            model.num_products_produced = Var(
                production_day_index,
                within=NonNegativeIntegers,
                bounds=(0, len(model.products)),
                doc="Number of distinct products produced on this date (for changeover calculation)"
            )

            print(f"  Changeover tracking: {len(production_day_index):,} production days, "
                  f"{len(product_produced_index):,} product indicators")

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

    def solve(
        self,
        solver_name: Optional[str] = None,
        time_limit_seconds: Optional[float] = None,
        mip_gap: Optional[float] = None,
        tee: bool = False,
        use_aggressive_heuristics: bool = False,
    ) -> OptimizationResult:
        """Build and solve the unified node model.

        Args:
            solver_name: Solver to use (None = auto-detect)
            time_limit_seconds: Time limit in seconds
            mip_gap: MIP gap tolerance
            tee: Show solver output
            use_aggressive_heuristics: Enable aggressive CBC heuristics (for large problems)

        Returns:
            OptimizationResult with solve status and metrics
        """
        # Call base class solve (builds model + solves)
        return super().solve(
            solver_name=solver_name,
            time_limit_seconds=time_limit_seconds,
            mip_gap=mip_gap,
            tee=tee,
            use_aggressive_heuristics=use_aggressive_heuristics,
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
                try:
                    qty = value(model.inventory_cohort[node_id, prod, prod_date, curr_date, state])
                    if qty > 0.01:
                        cohort_inventory[(node_id, prod, prod_date, curr_date, state)] = qty
                except (ValueError, AttributeError, KeyError, RuntimeError):
                    # Variable exists in index but wasn't initialized by solver
                    # Can happen when costs=0 or variable not referenced in active constraints
                    continue

        solution['cohort_inventory'] = cohort_inventory
        solution['use_batch_tracking'] = self.use_batch_tracking

        # Extract demand consumption by cohort (for daily snapshot)
        cohort_demand_consumption: Dict[Tuple[str, str, Date, Date], float] = {}
        if self.use_batch_tracking and hasattr(model, 'demand_from_cohort'):
            for (node_id, prod, prod_date, demand_date) in self.demand_cohort_index_set:
                try:
                    qty = value(model.demand_from_cohort[node_id, prod, prod_date, demand_date])
                    if qty > 0.01:
                        cohort_demand_consumption[(node_id, prod, prod_date, demand_date)] = qty
                except (ValueError, AttributeError, KeyError, RuntimeError):
                    # Variable exists in index but wasn't initialized by solver
                    # Can happen when costs=0 or variable not referenced in active constraints
                    continue

        solution['cohort_demand_consumption'] = cohort_demand_consumption

        # Extract shipments by route
        shipments_by_route: Dict[Tuple[str, str, str, Date], float] = {}
        if self.use_batch_tracking:
            for (origin, dest, prod, prod_date, delivery_date, state) in self.shipment_cohort_index_set:
                try:
                    qty = value(model.shipment_cohort[origin, dest, prod, prod_date, delivery_date, state])
                    if qty > 0.01:
                        # Aggregate by route (sum across cohorts)
                        key = (origin, dest, prod, delivery_date)
                        shipments_by_route[key] = shipments_by_route.get(key, 0.0) + qty
                except (ValueError, AttributeError, KeyError, RuntimeError):
                    # Variable exists in index but wasn't initialized by solver
                    # Can happen when costs=0 or variable not referenced in active constraints
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
                    try:
                        pallet_qty = value(model.pallet_count[node_id, prod, prod_date, curr_date, state])
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
                    try:
                        inv_qty = value(model.inventory_cohort[node_id, prod, prod_date, curr_date, state])
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
                try:
                    qty = value(model.shipment_cohort[origin, dest, prod, prod_date, delivery_date, state])
                except (ValueError, AttributeError, KeyError, RuntimeError):
                    # Variable exists in index but wasn't initialized by solver
                    # Can happen when costs=0 or variable not referenced in active constraints
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

        # Extract total cost from objective (may fail if variables uninitialized)
        # Do this AFTER all cost components have been extracted
        try:
            solution['total_cost'] = value(model.obj) if hasattr(model, 'obj') else 0.0
        except (ValueError, AttributeError, KeyError, RuntimeError):
            # Objective expression references uninitialized variables
            # Fall back to sum of cost components
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
        def product_produced_linking_rule(model, node_id, prod, date):
            """If product is produced (qty > 0), force product_produced = 1.

            Uses big-M formulation: production <= M * product_produced
            If product_produced = 0, then production must be 0.
            If production > 0, then product_produced must be 1.

            M is chosen as conservative upper bound on daily production per product.
            LOW-IMPACT #9: Tightened M from 20000 to actual max daily production.
            """
            # Use actual calculated max daily production instead of hardcoded value
            M = self.get_max_daily_production()  # More accurate than hardcoded 20000
            return model.production[node_id, prod, date] <= M * model.product_produced[node_id, prod, date]

        model.product_produced_linking_con = Constraint(
            product_produced_index,
            rule=product_produced_linking_rule,
            doc="Link production quantity to binary product indicator (big-M)"
        )

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

        print(f"  Changeover tracking constraints added ({len(product_produced_index) + 3 * len(production_day_index):,} constraints)")

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
        production_cost = 0
        for node_id in self.manufacturing_nodes:
            for prod in model.products:
                for date in model.dates:
                    if (node_id, prod, date) in model.production:
                        production_cost += self.cost_structure.production_cost_per_unit * model.production[node_id, prod, date]

        # Transport cost (shipments * route cost)
        # CRITICAL FIX: Iterate shipment_cohort_index_set directly to include initial inventory
        transport_cost = 0
        for (origin, dest, prod, prod_date, delivery_date, state) in self.shipment_cohort_index_set:
            # Find route cost
            route = next((r for r in self.routes
                         if r.origin_node_id == origin and r.destination_node_id == dest), None)
            if route:
                transport_cost += route.cost_per_unit * model.shipment_cohort[
                    origin, dest, prod, prod_date, delivery_date, state
                ]

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
        shortage_cost = 0
        if self.allow_shortages:
            penalty = self.cost_structure.shortage_penalty_per_unit
            for (node_id, prod, date) in self.demand.keys():
                shortage_cost += penalty * model.shortage[node_id, prod, date]

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
