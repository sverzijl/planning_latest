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
"""

from __future__ import annotations

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
    NonNegativeReals,
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

        # Extract and organize data
        self._extract_data()

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
            doc="Production quantity at manufacturing nodes"
        )

        # Inventory variables (cohort-based if batch tracking enabled)
        if self.use_batch_tracking:
            # inventory_cohort[node, product, prod_date, curr_date, state]
            model.inventory_cohort = Var(
                model.cohort_index,
                within=NonNegativeReals,
                doc="Inventory by node, product, production cohort, date, and state"
            )
        else:
            # Aggregated inventory[node, product, date]
            model.inventory = Var(
                model.inventory_index,
                within=NonNegativeReals,
                doc="Aggregated inventory by node, product, and date"
            )

        # Shipment variables (route-based)
        if self.use_batch_tracking:
            # Build shipment cohort indices
            self.shipment_cohort_index_set = self._build_shipment_cohort_indices(model.dates)
            model.shipment_cohort_index = list(self.shipment_cohort_index_set)

            # shipment_cohort[route, product, prod_date, delivery_date, arrival_state]
            model.shipment_cohort = Var(
                model.shipment_cohort_index,
                within=NonNegativeReals,
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
                doc="Shipment quantity by route, product, and delivery date"
            )

        # Demand satisfaction variables
        if self.use_batch_tracking:
            # Demand allocated from each cohort
            self.demand_cohort_index_set = self._build_demand_cohort_indices(model.dates)
            model.demand_cohort_index = list(self.demand_cohort_index_set)

            model.demand_from_cohort = Var(
                model.demand_cohort_index,
                within=NonNegativeReals,
                doc="Demand satisfied from specific production cohort"
            )
            print(f"  Demand cohort indices: {len(self.demand_cohort_index_set):,}")

        # Shortage variables (if allowed)
        if self.allow_shortages:
            shortage_index = list(self.demand.keys())
            model.shortage = Var(
                shortage_index,
                within=NonNegativeReals,
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

            # truck_load[truck_idx, product, delivery_date]
            truck_load_index = [
                (truck_idx, prod, date)
                for truck_idx in model.trucks
                for prod in model.products
                for date in model.dates
            ]
            model.truck_load = Var(
                truck_load_index,
                within=NonNegativeReals,
                doc="Quantity loaded on truck by product and delivery date"
            )

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
        self._add_objective(model)

        print(f"  Core constraints added")
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

        # For each node that can store inventory
        for node in self.nodes_list:
            if not node.capabilities.can_store:
                continue

            for prod in self.products:
                for prod_date in dates:
                    for curr_date in dates:
                        if curr_date < prod_date:
                            continue  # Can't have inventory from the future

                        age_days = (curr_date - prod_date).days

                        # Create cohorts for each state the node supports
                        # Frozen cohorts
                        if node.supports_frozen_storage():
                            if age_days <= self.FROZEN_SHELF_LIFE:
                                cohorts.add((node.id, prod, prod_date, curr_date, 'frozen'))

                        # Ambient cohorts
                        if node.supports_ambient_storage():
                            shelf_life = self.AMBIENT_SHELF_LIFE
                            if age_days <= shelf_life:
                                cohorts.add((node.id, prod, prod_date, curr_date, 'ambient'))

                        # Thawed cohorts (for nodes that can thaw frozen product)
                        # Thawed state resets shelf life to 14 days
                        if node.can_freeze_thaw():
                            if age_days <= self.THAWED_SHELF_LIFE:
                                cohorts.add((node.id, prod, prod_date, curr_date, 'thawed'))

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

        for route in self.routes:
            origin_node = self.nodes[route.origin_node_id]
            dest_node = self.nodes[route.destination_node_id]

            # Determine arrival state based on route transport mode and destination storage mode
            arrival_state = self._determine_arrival_state(route, dest_node)

            for prod in self.products:
                for delivery_date in dates:
                    # Calculate departure date
                    departure_date = delivery_date - timedelta(days=route.transit_days)

                    # Only create if departure is within or before planning horizon
                    if departure_date > self.end_date:
                        continue

                    # For each production date that could supply this shipment
                    for prod_date in dates:
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

        for (node_id, prod, demand_date) in self.demand.keys():
            # Any cohort produced before demand date and still fresh
            for prod_date in dates:
                if prod_date <= demand_date:
                    age_days = (demand_date - prod_date).days

                    # Check shelf life
                    node = self.nodes[node_id]
                    if node.supports_ambient_storage():
                        shelf_life = self.AMBIENT_SHELF_LIFE
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

        Implements clean state transition rules:
        - Ambient transport + Ambient node → ambient (no change)
        - Ambient transport + Frozen node → frozen (freeze, reset to 120d)
        - Frozen transport + Frozen node → frozen (no change)
        - Frozen transport + Ambient node → thawed (reset to 14d)

        Args:
            route: Route being traveled
            destination_node: Destination node

        Returns:
            State string: 'frozen', 'ambient', or 'thawed'
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
                # Frozen arriving at ambient-only node → thaw
                return 'thawed'
            else:
                # Frozen arriving at frozen-capable node → stays frozen
                return 'frozen'

    def solve(
        self,
        solver_name: Optional[str] = None,
        time_limit_seconds: Optional[float] = None,
        mip_gap: Optional[float] = None,
        tee: bool = False,
    ) -> OptimizationResult:
        """Build and solve the unified node model.

        Args:
            solver_name: Solver to use (None = auto-detect)
            time_limit_seconds: Time limit in seconds
            mip_gap: MIP gap tolerance
            tee: Show solver output

        Returns:
            OptimizationResult with solve status and metrics
        """
        # Call base class solve (builds model + solves)
        return super().solve(
            solver_name=solver_name,
            time_limit_seconds=time_limit_seconds,
            mip_gap=mip_gap,
            tee=tee,
        )

    def extract_solution(self, model: ConcreteModel) -> Dict[str, Any]:
        """Extract solution from solved model (required by BaseOptimizationModel).

        Args:
            model: Solved Pyomo model

        Returns:
            Solution dictionary (empty until Phase 5+ when solving works)
        """
        # TODO Phase 5+: Extract actual solution values
        return {}

    def get_solution(self) -> Optional[Dict[str, Any]]:
        """Extract solution from solved model.

        Returns:
            Solution dictionary (None until Phase 5+ when solving works)
        """
        return None

    def extract_production_schedule(self):
        """Extract production schedule from solution.

        Returns:
            ProductionSchedule object (None until Phase 5+)
        """
        return None

    def extract_shipments(self):
        """Extract shipments from solution.

        Returns:
            List of Shipment objects (None until Phase 5+)
        """
        return None

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
                    departure_date = delivery_date - timedelta(days=route.transit_days)

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
                        demand_consumption = model.demand_from_cohort[node_id, prod, prod_date, curr_date]

            # State transitions (Phase 6 - for now, simplified)
            # TODO Phase 6: Add explicit freeze/thaw operations for BOTH nodes
            state_transitions_in = 0
            state_transitions_out = 0

            # Balance equation
            return model.inventory_cohort[node_id, prod, prod_date, curr_date, state] == (
                prev_inv + production_inflow + arrivals + state_transitions_in -
                demand_consumption - departures - state_transitions_out
            )

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
            cohort_supply = sum(
                model.demand_from_cohort[node_id, prod, prod_date, demand_date]
                for prod_date in model.dates
                if (node_id, prod, prod_date, demand_date) in self.demand_cohort_index_set
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

    def _add_aggregated_inventory_balance(self, model: ConcreteModel) -> None:
        """Add aggregated inventory balance (no batch tracking - simplified)."""
        # TODO: Implement for non-batch-tracking mode if needed
        pass

    def _add_aggregated_demand_satisfaction(self, model: ConcreteModel) -> None:
        """Add aggregated demand satisfaction (no batch tracking)."""
        # TODO: Implement for non-batch-tracking mode if needed
        pass

    def _add_production_capacity_constraints(self, model: ConcreteModel) -> None:
        """Add production capacity constraints for manufacturing nodes."""

        def production_capacity_rule(model, node_id, date):
            """Total production cannot exceed capacity at manufacturing nodes."""

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

            # Calculate capacity: production_rate * labor_hours
            production_rate = node.capabilities.production_rate_per_hour
            labor_hours = labor_day.fixed_hours + (labor_day.overtime_hours if hasattr(labor_day, 'overtime_hours') else 0)

            # If this is a non-fixed day, use minimum hours
            if not labor_day.is_fixed_day and hasattr(labor_day, 'minimum_hours'):
                labor_hours = max(labor_hours, labor_day.minimum_hours)

            capacity = production_rate * labor_hours

            # Total production across all products cannot exceed capacity
            total_prod = sum(
                model.production[node_id, prod, date]
                for prod in model.products
                if (node_id, prod, date) in model.production
            )

            return total_prod <= capacity

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

    def _add_objective(self, model: ConcreteModel) -> None:
        """Add objective function: minimize total cost.

        Total cost = production cost + labor cost + transport cost + shortage penalty
        """

        # Production cost (units produced * cost per unit)
        production_cost = 0
        for node_id in self.manufacturing_nodes:
            for prod in model.products:
                for date in model.dates:
                    if (node_id, prod, date) in model.production:
                        production_cost += self.cost_structure.production_cost_per_unit * model.production[node_id, prod, date]

        # Transport cost (shipments * route cost)
        transport_cost = 0
        for route in self.routes:
            cost_per_unit = route.cost_per_unit

            for prod in model.products:
                for prod_date in model.dates:
                    for delivery_date in model.dates:
                        if (route.origin_node_id, route.destination_node_id, prod, prod_date, delivery_date, 'ambient') in self.shipment_cohort_index_set:
                            transport_cost += cost_per_unit * model.shipment_cohort[
                                route.origin_node_id, route.destination_node_id,
                                prod, prod_date, delivery_date, 'ambient'
                            ]

                        if (route.origin_node_id, route.destination_node_id, prod, prod_date, delivery_date, 'frozen') in self.shipment_cohort_index_set:
                            transport_cost += cost_per_unit * model.shipment_cohort[
                                route.origin_node_id, route.destination_node_id,
                                prod, prod_date, delivery_date, 'frozen'
                            ]

                        if (route.origin_node_id, route.destination_node_id, prod, prod_date, delivery_date, 'thawed') in self.shipment_cohort_index_set:
                            transport_cost += cost_per_unit * model.shipment_cohort[
                                route.origin_node_id, route.destination_node_id,
                                prod, prod_date, delivery_date, 'thawed'
                            ]

        # Labor cost (simplified - will refine in later phase)
        # For now, assume fixed cost per day based on labor calendar
        labor_cost = 0
        for date in model.dates:
            labor_day = self.labor_calendar.get_labor_day(date)
            if labor_day:
                # Simplified: assume using all available hours
                labor_cost += labor_day.fixed_hours * labor_day.regular_rate

        # Shortage penalty (if shortages allowed)
        shortage_cost = 0
        if self.allow_shortages:
            penalty = self.cost_structure.shortage_penalty_per_unit
            for (node_id, prod, date) in self.demand.keys():
                shortage_cost += penalty * model.shortage[node_id, prod, date]

        # Total cost
        total_cost = production_cost + transport_cost + labor_cost + shortage_cost

        model.obj = Objective(
            expr=total_cost,
            sense=minimize,
            doc="Minimize total cost (production + transport + labor + shortage penalty)"
        )
