"""Integrated production-distribution optimization model.

This module provides an integrated optimization model that combines production
scheduling with distribution routing decisions to minimize total cost.

Decision Variables:
- production[date, product]: Quantity to produce
- shipment[route_index, product, delivery_date]: Quantity to ship on each route
- shortage[dest, product, date]: Demand shortage (if allow_shortages=True)
- (batch tracking mode) demand_from_cohort[loc, prod, prod_date, curr_date]: Demand satisfied by specific production cohort

Constraints:
- Demand satisfaction: Shipments (+ shortage) arriving at each location meet demand
- Flow conservation: Total shipments ≤ total production
- Labor capacity: Production hours ≤ available labor hours per day
- Production capacity: Production ≤ max capacity per day
- Timing feasibility: Shipments depart on/after production date
- Shelf life: Routes filtered to exclude transit times > max_product_age_days (default: 10 days)
- Production smoothing (optional): Limits day-to-day production variation to prevent concentration

Objective:
- Minimize: labor cost + production cost + transport cost + shortage penalty

Note on Batch Tracking Mode (use_batch_tracking=True):
- Enables age-cohort tracking for shelf life enforcement
- Production smoothing constraint enabled by default to prevent concentration
- Previous FIFO penalty (lines 2215-2234) disabled due to perverse incentives
"""

from typing import Dict, List, Tuple, Set, Optional, Any
from datetime import date as Date, timedelta
from collections import defaultdict
import warnings
import math

from pyomo.environ import (
    ConcreteModel,
    Var,
    Constraint,
    Objective,
    NonNegativeReals,
    NonNegativeIntegers,
    Binary,
    minimize,
    value,
)

from src.models.forecast import Forecast
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.shipment import Shipment
from src.models.production_batch import ProductionBatch
from src.models.truck_schedule import TruckScheduleCollection

from src.network import NetworkGraphBuilder
from .route_enumerator import RouteEnumerator, EnumeratedRoute
from .base_model import BaseOptimizationModel
from .solver_config import SolverConfig


class IntegratedProductionDistributionModel(BaseOptimizationModel):
    """
    Integrated production-distribution optimization model.

    Optimizes production scheduling AND distribution routing to minimize
    total cost (labor + production + transport) while satisfying demand
    at each destination location.

    This model extends the simple ProductionOptimizationModel by:
    - Disaggregating demand by location (not just product total)
    - Adding shipment decision variables for routing
    - Including transport costs in objective
    - Enforcing demand satisfaction per location-date-product

    Example:
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
        )

        result = model.solve(time_limit_seconds=60)
        if result.is_optimal():
            shipments = model.get_shipment_plan()
            print(f"Total cost: ${result.objective_value:,.2f}")
            print(f"Shipments: {len(shipments)}")
    """

    # Production rate: 1,400 units per hour
    PRODUCTION_RATE = 1400.0

    # Max hours per day (with overtime)
    MAX_HOURS_PER_DAY = 14.0

    # Shelf life constants (days)
    AMBIENT_SHELF_LIFE = 17  # Ambient/thawed products expire after 17 days
    FROZEN_SHELF_LIFE = 120  # Frozen products can be stored for 120 days
    THAWED_SHELF_LIFE = 14   # Products that are thawed (e.g., at 6130) get 14 days

    def __init__(
        self,
        forecast: Forecast,
        labor_calendar: LaborCalendar,
        manufacturing_site: ManufacturingSite,
        cost_structure: CostStructure,
        locations: List[Location],
        routes: List[Route],
        solver_config: Optional[SolverConfig] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None,
        max_routes_per_destination: int = 5,
        allow_shortages: bool = False,
        enforce_shelf_life: bool = True,
        max_product_age_days: int = 10,
        validate_feasibility: bool = True,
        truck_schedules: Optional[TruckScheduleCollection] = None,
        initial_inventory: Optional[Dict[Tuple[str, str], float]] = None,
        inventory_snapshot_date: Optional[Date] = None,
        use_batch_tracking: bool = False,
        enable_production_smoothing: Optional[bool] = None,
    ):
        """
        Initialize integrated production-distribution model.

        Args:
            forecast: Demand forecast (with location-specific demand)
            labor_calendar: Labor availability and costs
            manufacturing_site: Manufacturing site data
            cost_structure: Cost parameters
            locations: All network locations
            routes: All network routes
            solver_config: Solver configuration (optional)
            start_date: Planning horizon start (default: first forecast date)
            end_date: Planning horizon end (default: last forecast date)
            max_routes_per_destination: Maximum routes to enumerate per destination
            allow_shortages: If True, allow demand shortages with penalty cost
            enforce_shelf_life: If True, filter routes exceeding shelf life limits
            max_product_age_days: Maximum product age at delivery (17-day shelf life - 7-day min = 10 days)
            validate_feasibility: If True, validate feasibility before building model (default: True)
            truck_schedules: Optional collection of truck schedules (if None, no truck constraints)
            initial_inventory: Optional dict mapping (dest_id, product_id) to initial inventory quantity
            inventory_snapshot_date: Optional date when initial inventory was measured (for production date assignment)
            use_batch_tracking: If True, use age-cohort batch tracking model for shelf life and FIFO.
                                If False, use legacy aggregated inventory model (default: False)
            enable_production_smoothing: If True, add production smoothing constraint to limit day-to-day variation.
                                         If None, defaults to True when use_batch_tracking=True, False otherwise.
                                         Prevents production concentration on single days.
        """
        super().__init__(solver_config)

        self.forecast = forecast
        self.labor_calendar = labor_calendar
        self.manufacturing_site = manufacturing_site
        self.cost_structure = cost_structure
        self.locations = locations
        self.routes = routes
        self.max_routes_per_destination = max_routes_per_destination
        self.allow_shortages = allow_shortages
        self.enforce_shelf_life = enforce_shelf_life
        self.max_product_age_days = max_product_age_days
        self._validate_feasibility_flag = validate_feasibility
        self.initial_inventory = initial_inventory or {}
        self.inventory_snapshot_date = inventory_snapshot_date
        self.use_batch_tracking = use_batch_tracking

        # Production smoothing: Disabled by default - natural constraints should handle spreading
        # If production still concentrates, investigate missing cost components (e.g., holding costs)
        if enable_production_smoothing is None:
            self.enable_production_smoothing = False  # Let natural constraints work
        else:
            self.enable_production_smoothing = enable_production_smoothing

        # Validate truck_schedules type
        if truck_schedules is not None:
            if isinstance(truck_schedules, list):
                raise TypeError(
                    "truck_schedules must be a TruckScheduleCollection, not a list. "
                    "Wrap your list: TruckScheduleCollection(schedules=your_list)"
                )
            if not isinstance(truck_schedules, TruckScheduleCollection):
                raise TypeError(
                    f"truck_schedules must be a TruckScheduleCollection, got {type(truck_schedules).__name__}"
                )

        self.truck_schedules = truck_schedules

        # Store user-provided dates
        self._user_start_date = start_date
        self._user_end_date = end_date

        # Determine initial planning horizon (will be adjusted after route enumeration)
        if forecast.entries:
            forecast_start = min(e.forecast_date for e in forecast.entries)
            forecast_end = max(e.forecast_date for e in forecast.entries)
            # Use a conservative initial horizon for route enumeration
            self.start_date = forecast_start - timedelta(days=7)  # 7-day buffer
            self.end_date = forecast_end
        else:
            raise ValueError("Forecast must have at least one entry")

        # Extract sets and parameters (this will enumerate routes)
        self._extract_data()

        # Now adjust planning horizon based on actual transit times
        self._adjust_planning_horizon(forecast_start, forecast_end)

        # Validate feasibility before building model (if enabled)
        if self._validate_feasibility_flag:
            self._validate_feasibility()

    def _extract_data(self) -> None:
        """Extract sets and parameters from input data."""
        # Set of production dates (all dates in planning horizon)
        self.production_dates: Set[Date] = set()
        current = self.start_date
        while current <= self.end_date:
            self.production_dates.add(current)
            current += timedelta(days=1)

        # Set of products
        self.products: Set[str] = {e.product_id for e in self.forecast.entries}

        # Set of destination locations (from forecast)
        self.destinations: Set[str] = {e.location_id for e in self.forecast.entries}

        # STATE TRACKING: Location storage mode categorization
        # Create location lookup dictionary
        self.location_by_id: Dict[str, Location] = {loc.id: loc for loc in self.locations}

        # Categorize locations by storage capability
        self.locations_frozen_storage: Set[str] = {
            loc.id for loc in self.locations
            if loc.storage_mode in [StorageMode.FROZEN, StorageMode.BOTH]
        } | {'6122_Storage'}  # Virtual storage also supports frozen inventory
        self.locations_ambient_storage: Set[str] = {
            loc.id for loc in self.locations
            if loc.storage_mode in [StorageMode.AMBIENT, StorageMode.BOTH]
        } | {'6122_Storage'}  # Virtual storage at manufacturing site

        # Locations that support both frozen and ambient storage (can freeze/thaw)
        self.locations_with_freezing: Set[str] = {
            loc.id for loc in self.locations
            if loc.storage_mode == StorageMode.BOTH
        }  # NOTE: 6122_Storage should NOT freeze/thaw - only Lineage and 6130 perform state transitions

        # Identify intermediate storage locations (storage type, no demand)
        self.intermediate_storage: Set[str] = {
            loc.id for loc in self.locations
            if loc.type == LocationType.STORAGE and loc.id not in self.destinations
        }

        # All locations that need inventory tracking (destinations + intermediate + 6122_Storage)
        # 6122_Storage is a virtual location that receives production from 6122 and supplies trucks
        self.inventory_locations: Set[str] = self.destinations | self.intermediate_storage | {'6122_Storage'}

        # Disaggregate demand by location-date-product
        # Filter to only include demand within planning horizon
        self.demand: Dict[Tuple[str, str, Date], float] = {}
        filtered_demand_count = 0
        for entry in self.forecast.entries:
            # Only include demand within planning horizon
            if self.start_date <= entry.forecast_date <= self.end_date:
                key = (entry.location_id, entry.product_id, entry.forecast_date)
                self.demand[key] = entry.quantity
            else:
                filtered_demand_count += 1

        if filtered_demand_count > 0:
            warnings.warn(
                f"Filtered {filtered_demand_count} demand entries outside planning horizon "
                f"[{self.start_date}, {self.end_date}]. "
                f"Extend planning horizon to include all forecast demand."
            )

        # Total demand by product (for reporting)
        self.total_demand_by_product: Dict[str, float] = defaultdict(float)
        for entry in self.forecast.entries:
            self.total_demand_by_product[entry.product_id] += entry.quantity

        # Labor availability by date
        self.labor_by_date: Dict[Date, LaborDay] = {}
        for prod_date in self.production_dates:
            labor_day = self.labor_calendar.get_labor_day(prod_date)
            if labor_day:
                self.labor_by_date[prod_date] = labor_day

                # Validate: Non-fixed days must have non_fixed_rate specified
                if not labor_day.is_fixed_day and labor_day.non_fixed_rate is None:
                    raise ValueError(
                        f"Labor calendar validation failed: "
                        f"Non-fixed day {prod_date} ({prod_date.strftime('%A')}) "
                        f"has no non_fixed_rate specified. "
                        f"Weekend/holiday rates must be provided in labor calendar."
                    )

        # Max production capacity per day (units)
        self.max_capacity_per_day = self.MAX_HOURS_PER_DAY * self.PRODUCTION_RATE

        # Enumerate routes using RouteEnumerator
        self._enumerate_routes()

        # Extract truck schedule data if provided
        if self.truck_schedules:
            self._extract_truck_data()

        # Preprocess initial inventory to consistent format
        self._preprocess_initial_inventory()

    def _preprocess_initial_inventory(self) -> None:
        """
        Preprocess initial_inventory to consistent 4-tuple format.

        UI passes: {(loc, prod): qty}
        Model needs: {(loc, prod, prod_date, state): qty}

        This method converts 2-tuple format to 4-tuple format by:
        1. Setting prod_date to one day before planning horizon starts
        2. Determining state based on location storage_mode
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
            # Initial inventory production date: use snapshot date if provided, else one day before planning horizon
            if self.inventory_snapshot_date:
                init_prod_date = self.inventory_snapshot_date
            else:
                init_prod_date = self.start_date - timedelta(days=1)

            converted_inventory = {}
            for (loc, prod), qty in self.initial_inventory.items():
                if qty <= 0:
                    continue

                # Determine state based on location storage mode
                location = self.location_by_id.get(loc)
                if not location:
                    warnings.warn(f"Initial inventory location {loc} not found in locations list. Skipping.")
                    continue

                # Default state based on storage mode
                if location.storage_mode == StorageMode.FROZEN:
                    state = 'frozen'
                elif location.storage_mode == StorageMode.AMBIENT:
                    state = 'ambient'
                elif location.storage_mode == StorageMode.BOTH:
                    # For locations with both modes, assume frozen (longer shelf life)
                    # User can override by passing 4-tuple format if needed
                    state = 'frozen'
                else:
                    warnings.warn(f"Unknown storage mode for location {loc}. Defaulting to ambient.")
                    state = 'ambient'

                # Store in 4-tuple format
                converted_inventory[(loc, prod, init_prod_date, state)] = qty

            self.initial_inventory = converted_inventory
            print(f"\n📦 Preprocessed initial inventory: {len(converted_inventory)} items, prod_date={init_prod_date}")

        elif len(first_key) == 3:
            # 3-tuple format: (loc, prod, state) -> needs prod_date
            if self.inventory_snapshot_date:
                init_prod_date = self.inventory_snapshot_date
            else:
                init_prod_date = self.start_date - timedelta(days=1)

            converted_inventory = {}
            for (loc, prod, state), qty in self.initial_inventory.items():
                if qty > 0:
                    converted_inventory[(loc, prod, init_prod_date, state)] = qty

            self.initial_inventory = converted_inventory
            print(f"\n📦 Preprocessed initial inventory: {len(converted_inventory)} items, prod_date={init_prod_date}")

        else:
            warnings.warn(f"Unknown initial_inventory format with key length {len(first_key)}. Expected 2, 3, or 4.")

    def _extract_truck_data(self) -> None:
        """
        Extract truck schedule data for optimization.

        Creates:
        - truck_indices: Set of truck indices (0, 1, 2, ...)
        - truck_by_index: Mapping from index to TruckSchedule object
        - trucks_on_date: Dict[date, List[truck_index]] - trucks available each date
        - trucks_to_destination: Dict[destination_id, List[truck_index]] - trucks serving each destination
        - truck_destination: Dict[truck_index, destination_id] - destination for each truck
        - truck_capacity: Dict[truck_index, capacity] - capacity of each truck
        - trucks_with_intermediate_stops: Dict[truck_index, List[stop_ids]] - trucks with intermediate stops
        - wednesday_lineage_trucks: Set[truck_index] - trucks serving Lineage on Wednesdays
        """
        # Create truck indices (enumerate all truck schedules)
        self.truck_indices: Set[int] = set()
        self.truck_by_index: Dict[int, 'TruckSchedule'] = {}
        self.truck_destination: Dict[int, str] = {}
        self.truck_capacity: Dict[int, float] = {}
        self.truck_pallet_capacity: Dict[int, int] = {}
        self.trucks_with_intermediate_stops: Dict[int, List[str]] = {}
        self.wednesday_lineage_trucks: Set[int] = set()

        for idx, truck in enumerate(self.truck_schedules.schedules):
            self.truck_indices.add(idx)
            self.truck_by_index[idx] = truck
            if truck.destination_id:  # Fixed-route trucks
                self.truck_destination[idx] = truck.destination_id
            self.truck_capacity[idx] = truck.capacity
            self.truck_pallet_capacity[idx] = truck.pallet_capacity

            # Track trucks with intermediate stops
            if truck.has_intermediate_stops():
                self.trucks_with_intermediate_stops[idx] = truck.intermediate_stops

                # Special case: Wednesday morning truck to Lineage + 6125
                # Check if this truck goes to Lineage as intermediate stop and 6125 as final
                if 'Lineage' in truck.intermediate_stops and truck.destination_id == '6125':
                    # This is the Wednesday special truck
                    self.wednesday_lineage_trucks.add(idx)

        # For each date in planning horizon, determine which trucks are available
        self.trucks_on_date: Dict[Date, List[int]] = defaultdict(list)
        for prod_date in self.production_dates:
            for truck_idx in self.truck_indices:
                truck = self.truck_by_index[truck_idx]
                if truck.applies_on_date(prod_date):
                    self.trucks_on_date[prod_date].append(truck_idx)

        # Map trucks to destinations they serve (including intermediate stops)
        self.trucks_to_destination: Dict[str, List[int]] = defaultdict(list)
        for truck_idx, dest_id in self.truck_destination.items():
            self.trucks_to_destination[dest_id].append(truck_idx)

        # Also add trucks that have intermediate stops to those destinations
        for truck_idx, stops in self.trucks_with_intermediate_stops.items():
            for stop_id in stops:
                self.trucks_to_destination[stop_id].append(truck_idx)

    def _is_frozen_route(self, route: EnumeratedRoute) -> bool:
        """
        Check if a route uses frozen transport throughout.

        Args:
            route: EnumeratedRoute object to check

        Returns:
            True if all legs of the route use frozen transport
        """
        # Check the route_path object for transport modes
        # The route_path has a list of Route objects that we can check
        if hasattr(route.route_path, 'route_legs') and route.route_path.route_legs:
            # Check if all legs are frozen
            from src.models.location import StorageMode
            return all(
                leg.transport_mode == StorageMode.FROZEN
                for leg in route.route_path.route_legs
            )
        # Fallback: check if destination is frozen storage (like Lineage)
        # or if route goes through Lineage (frozen buffer for WA)
        return 'Lineage' in route.path or route.destination_id == 'Lineage'

    def _is_route_shelf_life_feasible(self, route: EnumeratedRoute) -> bool:
        """
        Check if a route satisfies shelf life constraints.

        Shelf life limits:
        - Ambient routes: 17 days production shelf life - 7 days breadroom minimum = 10 days max transit
        - Frozen routes: 120 days frozen shelf life (very long, rarely a constraint)
        - Thawed routes to 6130 (WA): 14 days post-thaw shelf life - 7 days minimum = 7 days max
          (Note: This is a simplified check. Full thawing logic requires state tracking in Phase 4)

        Args:
            route: EnumeratedRoute object to check

        Returns:
            True if route satisfies shelf life constraints
        """
        transit_days = route.total_transit_days

        # Special case: Thawed route to 6130 (WA)
        # After thawing, product has 14 days shelf life, needs 7 days at breadroom
        # So maximum time from thaw to breadroom is 7 days
        # TODO Phase 4: This is simplified. Need to model thawing timing explicitly.
        if route.destination_id == '6130':
            # For WA route via Lineage with thawing:
            # Product frozen at Lineage (no shelf life loss)
            # Shipped frozen to 6130 (no shelf life loss)
            # Thawed at 6130 → 14 days remaining
            # Need 7 days at breadroom minimum
            # So we need thaw → breadroom transit ≤ 7 days
            # Since we don't track thawing timing yet, conservatively allow routes
            # up to 7 days from 6130 to final destination
            # For now, just check total transit isn't absurdly long
            return transit_days <= 120  # Frozen route, generous limit

        # Frozen routes: 120-day frozen shelf life
        if self._is_frozen_route(route):
            return transit_days <= 120

        # Ambient routes: 17-day shelf life - 7-day minimum = 10 days max transit
        return transit_days <= self.max_product_age_days

    def _get_truck_transit_days(self, truck_idx: int, dest_id: str) -> int:
        """
        Get transit days for truck from manufacturing to first-leg destination.

        This is used to convert between departure dates and delivery dates:
        - delivery_date = departure_date + transit_days
        - departure_date = delivery_date - transit_days

        Args:
            truck_idx: Truck index
            dest_id: Destination ID (first-leg from manufacturing)

        Returns:
            Transit time in days (integer, rounded up for fractional days)
        """
        import math

        truck = self.truck_by_index[truck_idx]

        # Find routes from manufacturing to this destination
        for route_idx in self.route_indices:
            route = self.route_enumerator.get_route(route_idx)
            if route and route.origin_id == self.manufacturing_site.id:
                # Check if this route's first leg goes to dest_id
                first_leg_dest = route.path[1] if len(route.path) >= 2 else route.destination_id

                if first_leg_dest == dest_id:
                    # Get first leg transit time
                    # Use ceil() to round up: 1.5 days → 2 days
                    # This ensures delivery_date accounts for full transit duration
                    if route.route_path and route.route_path.route_legs:
                        return math.ceil(route.route_path.route_legs[0].transit_days)

        # Default: 1 day transit if not found (conservative)
        return 1

    def _enumerate_routes(self) -> None:
        """Enumerate feasible routes from manufacturing to destinations."""
        # Build network graph
        graph_builder = NetworkGraphBuilder(self.locations, self.routes)
        graph_builder.build_graph()

        # Create route enumerator
        self.route_enumerator = RouteEnumerator(
            graph_builder=graph_builder,
            manufacturing_site_id=self.manufacturing_site.id,
            max_routes_per_destination=self.max_routes_per_destination,
        )

        # Enumerate routes to all destinations in forecast
        enumerated_routes_dict = self.route_enumerator.enumerate_routes_for_destinations(
            destinations=list(self.destinations),
            rank_by='cost'
        )

        # Store enumerated routes
        all_routes = self.route_enumerator.get_all_routes()

        # Filter routes based on shelf life constraints if enforced
        if self.enforce_shelf_life:
            self.enumerated_routes: List[EnumeratedRoute] = []
            filtered_by_type = {'frozen_ok': 0, 'ambient_ok': 0, 'frozen_too_long': 0, 'ambient_too_long': 0, 'thawed_6130_ok': 0, 'thawed_6130_too_long': 0}

            for route in all_routes:
                if self._is_route_shelf_life_feasible(route):
                    self.enumerated_routes.append(route)
                    # Categorize for logging
                    if self._is_frozen_route(route):
                        filtered_by_type['frozen_ok'] += 1
                    elif route.destination_id == '6130':
                        filtered_by_type['thawed_6130_ok'] += 1
                    else:
                        filtered_by_type['ambient_ok'] += 1
                else:
                    # Categorize filtered routes
                    if self._is_frozen_route(route):
                        filtered_by_type['frozen_too_long'] += 1
                    elif route.destination_id == '6130':
                        filtered_by_type['thawed_6130_too_long'] += 1
                    else:
                        filtered_by_type['ambient_too_long'] += 1

            # Log filtered routes with detail
            total_filtered = len(all_routes) - len(self.enumerated_routes)
            if total_filtered > 0:
                import warnings
                msg = f"Shelf life filtering: Kept {len(self.enumerated_routes)}/{len(all_routes)} routes. Filtered: "
                details = []
                if filtered_by_type['ambient_too_long'] > 0:
                    details.append(f"{filtered_by_type['ambient_too_long']} ambient (>{self.max_product_age_days}d)")
                if filtered_by_type['frozen_too_long'] > 0:
                    details.append(f"{filtered_by_type['frozen_too_long']} frozen (>120d)")
                if filtered_by_type['thawed_6130_too_long'] > 0:
                    details.append(f"{filtered_by_type['thawed_6130_too_long']} thawed to 6130 (>7d)")
                warnings.warn(msg + ', '.join(details))
        else:
            self.enumerated_routes: List[EnumeratedRoute] = all_routes

        # Create route indices set
        self.route_indices: Set[int] = {r.index for r in self.enumerated_routes}

        # Create mapping: route_index -> destination
        self.route_destination: Dict[int, str] = {
            r.index: r.destination_id for r in self.enumerated_routes
        }

        # Create mapping: route_index -> transit_days
        self.route_transit_days: Dict[int, int] = {
            r.index: r.total_transit_days for r in self.enumerated_routes
        }

        # Create mapping: route_index -> cost
        self.route_cost: Dict[int, float] = {
            r.index: r.total_cost for r in self.enumerated_routes
        }

        # Create mapping: destination -> list of route indices
        self.routes_to_destination: Dict[str, List[int]] = defaultdict(list)
        for r in self.enumerated_routes:
            self.routes_to_destination[r.destination_id].append(r.index)

        # STATE TRACKING: Determine arrival state for each route
        # frozen route + frozen-only destination → frozen
        # anything else → ambient (thaws if needed)
        self.route_arrival_state: Dict[int, str] = {}  # route_index -> 'frozen' or 'ambient'

        for route in self.enumerated_routes:
            dest_loc = self.location_by_id.get(route.destination_id)

            # Check if route is frozen throughout
            is_frozen_route = self._is_frozen_route(route)

            # Determine arrival state
            if is_frozen_route and dest_loc and dest_loc.storage_mode == StorageMode.FROZEN:
                # Frozen route to frozen-only storage → stays frozen
                self.route_arrival_state[route.index] = 'frozen'
            else:
                # Everything else arrives as ambient
                # (thaws if frozen route to non-frozen destination)
                self.route_arrival_state[route.index] = 'ambient'

        # LEG-BASED ROUTING: Enumerate all network legs for flexible hub buffering
        # This enables strategic inventory decisions at intermediate locations (hubs, Lineage)
        self.network_legs = self.route_enumerator.enumerate_network_legs()

        # Create leg-based index structures
        self.leg_keys: Set[Tuple[str, str]] = set(self.network_legs.keys())

        # Mapping: (origin, destination) -> leg attributes
        self.leg_transit_days: Dict[Tuple[str, str], int] = {
            leg_key: leg_data['transit_days']
            for leg_key, leg_data in self.network_legs.items()
        }

        self.leg_cost: Dict[Tuple[str, str], float] = {
            leg_key: leg_data['cost_per_unit']
            for leg_key, leg_data in self.network_legs.items()
        }

        self.leg_transport_mode: Dict[Tuple[str, str], str] = {
            leg_key: leg_data['transport_mode']
            for leg_key, leg_data in self.network_legs.items()
        }

        # Mappings for efficient lookup:
        # legs_from_location: origin -> list of (origin, destination) tuples
        # legs_to_location: destination -> list of (origin, destination) tuples
        self.legs_from_location: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.legs_to_location: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

        for (origin, destination) in self.leg_keys:
            self.legs_from_location[origin].append((origin, destination))
            self.legs_to_location[destination].append((origin, destination))

        # REPLACE real manufacturing legs with virtual 6122_Storage legs
        # Production flows into 6122_Storage cohorts, which then ship via these virtual legs
        # We must use virtual legs (not real legs) for proper truck constraint enforcement
        mfg_site_id = self.manufacturing_site.location_id
        legs_to_replace = []

        if mfg_site_id in self.legs_from_location:
            # Collect legs to replace (can't modify dict during iteration)
            legs_to_replace = list(self.legs_from_location[mfg_site_id])

            for (origin, destination) in legs_to_replace:
                actual_leg = (origin, destination)
                virtual_leg = ('6122_Storage', destination)

                # Remove real leg from all data structures
                self.legs_from_location[origin].remove(actual_leg)
                self.legs_to_location[destination].remove(actual_leg)
                self.leg_keys.discard(actual_leg)

                # Remove leg attributes
                if actual_leg in self.leg_transit_days:
                    transit_days = self.leg_transit_days.pop(actual_leg)
                else:
                    transit_days = 1  # Default

                if actual_leg in self.leg_cost:
                    cost = self.leg_cost.pop(actual_leg)
                else:
                    cost = 0.0

                if actual_leg in self.leg_transport_mode:
                    transport_mode = self.leg_transport_mode.pop(actual_leg)
                else:
                    transport_mode = 'ambient'

                # Add virtual leg with same attributes
                self.legs_from_location['6122_Storage'].append(virtual_leg)
                self.legs_to_location[destination].append(virtual_leg)
                self.leg_keys.add(virtual_leg)

                self.leg_transit_days[virtual_leg] = transit_days
                self.leg_cost[virtual_leg] = cost
                self.leg_transport_mode[virtual_leg] = transport_mode

        # Determine arrival state for each leg (similar to routes)
        self.leg_arrival_state: Dict[Tuple[str, str], str] = {}

        for leg_key in self.leg_keys:
            origin, destination = leg_key
            dest_loc = self.location_by_id.get(destination)
            transport_mode = self.leg_transport_mode[leg_key]

            # Frozen transport mode + frozen-only destination → stays frozen
            if transport_mode == 'frozen' and dest_loc and dest_loc.storage_mode == StorageMode.FROZEN:
                self.leg_arrival_state[leg_key] = 'frozen'
            else:
                # Everything else arrives as ambient
                self.leg_arrival_state[leg_key] = 'ambient'

        # Pre-compute locations with outbound ambient legs (for performance in cohort constraints)
        # These locations need departure calculations in inventory balance
        self.locations_with_outbound_ambient_legs: Set[str] = {
            origin for (origin, dest), state in self.leg_arrival_state.items()
            if state == 'ambient'
        }

    def _calculate_required_planning_horizon(self) -> Tuple[Date, Date]:
        """
        Calculate required planning horizon accounting for transit times AND truck loading timing.

        To satisfy demand on a given date, production must occur earlier
        by the transit time. Additionally, morning trucks require D-1 production
        (production from the previous day), so we need an extra day at the start.

        Returns:
            (earliest_start_date, latest_end_date) tuple
        """
        # Find earliest and latest delivery dates in forecast
        earliest_delivery = min(e.forecast_date for e in self.forecast.entries)
        latest_delivery = max(e.forecast_date for e in self.forecast.entries)

        # Find maximum transit time across all enumerated routes
        max_transit_days = 0
        if self.enumerated_routes:
            max_transit_days = max(r.total_transit_days for r in self.enumerated_routes)

        # Production must start (max_transit_days) before earliest delivery
        # to allow time for shipments to reach destinations
        # PLUS 1 additional day for D-1 production requirement (morning trucks load previous day's production)
        required_start = earliest_delivery - timedelta(days=int(max_transit_days) + 1)

        return required_start, latest_delivery

    def _adjust_planning_horizon(self, forecast_start: Date, forecast_end: Date) -> None:
        """
        Adjust planning horizon after route enumeration based on transit times.

        Args:
            forecast_start: Earliest forecast date
            forecast_end: Latest forecast date
        """
        import warnings

        # Calculate required horizon
        required_start, required_end = self._calculate_required_planning_horizon()

        # Determine final start date with priority:
        # 1. User explicit override (highest priority)
        # 2. Inventory snapshot date (if initial inventory provided)
        # 3. Auto-calculated required_start (fallback)
        if self._user_start_date:
            final_start = self._user_start_date
        elif self.inventory_snapshot_date:
            final_start = self.inventory_snapshot_date
        else:
            final_start = required_start

        final_end = self._user_end_date or required_end

        # Check if user-provided start date is too late
        if final_start > required_start:
            days_short = (final_start - required_start).days
            max_transit = max(r.total_transit_days for r in self.enumerated_routes) if self.enumerated_routes else 0
            warnings.warn(
                f"\nPlanning horizon may be insufficient:\n"
                f"  Current start: {final_start}\n"
                f"  Required start: {required_start} ({days_short} days earlier)\n"
                f"  Max transit time: {max_transit} days\n"
                f"  Early demand (on {forecast_start}) cannot be satisfied.\n"
                f"  Solution: Extend planning horizon or accept reduced demand satisfaction."
            )

        # Check if user-provided end date is too early
        if final_end < required_end:
            days_short = (required_end - final_end).days
            warnings.warn(
                f"\nPlanning horizon end date may be insufficient:\n"
                f"  Current end: {final_end}\n"
                f"  Required end: {required_end} ({days_short} days later)\n"
                f"  Late demand (on {forecast_end}) will be filtered out.\n"
                f"  Solution: Extend planning horizon end date to include all demand."
            )

        # Update planning horizon
        self.start_date = final_start
        self.end_date = final_end

        # Rebuild production dates with new horizon
        self.production_dates = set()
        current = self.start_date
        while current <= self.end_date:
            self.production_dates.add(current)
            current += timedelta(days=1)

        # Update labor by date with new production dates
        self.labor_by_date = {}
        for prod_date in self.production_dates:
            labor_day = self.labor_calendar.get_labor_day(prod_date)
            if labor_day:
                self.labor_by_date[prod_date] = labor_day

        # Re-filter demand to ensure consistency with adjusted planning horizon
        # This handles the case where dates were extended after initial demand creation
        filtered_demand = {}
        filtered_count = 0
        for (dest, prod, deliv_date), qty in self.demand.items():
            if self.start_date <= deliv_date <= self.end_date:
                filtered_demand[(dest, prod, deliv_date)] = qty
            else:
                filtered_count += 1

        if filtered_count > 0:
            warnings.warn(
                f"Re-filtered {filtered_count} demand entries after planning horizon adjustment. "
                f"Adjusted horizon: [{self.start_date}, {self.end_date}]"
            )

        self.demand = filtered_demand

    def _validate_feasibility(self) -> None:
        """
        Validate problem feasibility before building optimization model.

        Checks for common infeasibility causes:
        - Route coverage to all demanded destinations
        - Sufficient production capacity for total demand
        - Weekly capacity with regular labor hours
        - Labor calendar coverage for all production dates

        Raises:
            ValueError: If problem is obviously infeasible
        """
        import warnings

        issues = []

        # Check 1: Route coverage - are there routes to all demanded destinations?
        destinations_without_routes = []
        for dest in self.destinations:
            if dest not in self.routes_to_destination or len(self.routes_to_destination[dest]) == 0:
                destinations_without_routes.append(dest)

        if destinations_without_routes:
            issues.append(
                f"No routes found to {len(destinations_without_routes)} destination(s): "
                f"{', '.join(sorted(destinations_without_routes)[:5])}"
                + (f" (and {len(destinations_without_routes) - 5} more)" if len(destinations_without_routes) > 5 else "")
            )

        # Check 2: Production capacity - is total demand achievable?
        total_demand = sum(self.demand.values())
        num_production_days = len(self.production_dates)
        total_capacity = num_production_days * self.max_capacity_per_day

        if total_demand > total_capacity * 1.001:  # 0.1% tolerance for rounding
            issues.append(
                f"Total demand ({total_demand:,.0f} units) exceeds total production capacity "
                f"({total_capacity:,.0f} units over {num_production_days} days). "
                f"Shortfall: {total_demand - total_capacity:,.0f} units ({(total_demand / total_capacity - 1) * 100:.1f}% over capacity)"
            )

        # Check 3: Weekly capacity with regular labor - is overtime required every week?
        if num_production_days >= 7:
            weeks = num_production_days / 7
            avg_weekly_demand = total_demand / weeks
            # Assume 5 weekdays per week with 12h regular labor each
            weekly_regular_capacity = 5 * 12 * self.PRODUCTION_RATE  # 84,000 units

            if avg_weekly_demand > weekly_regular_capacity:
                overtime_required_pct = (avg_weekly_demand / weekly_regular_capacity - 1) * 100
                if overtime_required_pct > 15:  # More than 15% over regular capacity
                    warnings.warn(
                        f"Average weekly demand ({avg_weekly_demand:,.0f} units) exceeds regular capacity "
                        f"({weekly_regular_capacity:,.0f} units) by {overtime_required_pct:.1f}%. "
                        f"Overtime or weekend production will be required frequently."
                    )

        # Check 4: Labor calendar coverage - do we have labor data for all production dates?
        # Distinguish between critical (needed for forecast) and non-critical (extended horizon) dates
        # Missing weekday dates are critical errors (production should be possible Mon-Fri)
        # Missing weekend dates are warnings (optional production, zero capacity if not provided)

        # Calculate critical date range (needed to satisfy forecast demand)
        forecast_start = min(e.forecast_date for e in self.forecast.entries)
        forecast_end = max(e.forecast_date for e in self.forecast.entries)
        max_transit_days = max(r.total_transit_days for r in self.enumerated_routes) if self.enumerated_routes else 0

        # Critical range: must have labor data to produce and deliver forecast demand
        critical_start = forecast_start - timedelta(days=int(max_transit_days) + 1)
        critical_end = forecast_end

        # Separate missing dates into critical vs. non-critical buckets
        critical_missing_weekdays = []
        noncritical_missing_weekdays = []
        critical_missing_weekends = []
        noncritical_missing_weekends = []

        for prod_date in self.production_dates:
            if prod_date not in self.labor_by_date:
                is_weekday = prod_date.weekday() < 5  # Monday-Friday
                is_critical = critical_start <= prod_date <= critical_end

                if is_weekday and is_critical:
                    critical_missing_weekdays.append(prod_date)
                elif is_weekday and not is_critical:
                    noncritical_missing_weekdays.append(prod_date)
                elif not is_weekday and is_critical:
                    critical_missing_weekends.append(prod_date)
                else:
                    noncritical_missing_weekends.append(prod_date)

        # Get labor calendar date range for error messages
        labor_dates = [d for d in self.production_dates if d in self.labor_by_date]
        labor_start = min(labor_dates) if labor_dates else None
        labor_end = max(labor_dates) if labor_dates else None

        # Critical error for missing weekdays in critical date range
        if critical_missing_weekdays:
            if len(critical_missing_weekdays) <= 5:
                date_str = ', '.join(str(d) for d in sorted(critical_missing_weekdays))
            else:
                date_str = ', '.join(str(d) for d in sorted(critical_missing_weekdays)[:5]) + f" (and {len(critical_missing_weekdays) - 5} more)"

            issues.append(
                f"Labor calendar missing entries for {len(critical_missing_weekdays)} critical weekday production date(s): {date_str}\n"
                f"     Forecast range: {forecast_start} to {forecast_end}\n"
                f"     Required production start (with {max_transit_days}-day transit buffer): {critical_start}\n"
                f"     Labor calendar coverage: {labor_start} to {labor_end}\n"
                f"     → To fix: Extend labor calendar to cover {critical_start} through {critical_end}"
            )

        # Warning for missing weekdays in non-critical range (extended planning horizon)
        if noncritical_missing_weekdays:
            if len(noncritical_missing_weekdays) <= 5:
                date_str = ', '.join(str(d) for d in sorted(noncritical_missing_weekdays))
            else:
                date_str = ', '.join(str(d) for d in sorted(noncritical_missing_weekdays)[:5]) + f" (and {len(noncritical_missing_weekdays) - 5} more)"

            warnings.warn(
                f"Labor calendar missing {len(noncritical_missing_weekdays)} weekday entries outside critical forecast range: {date_str}. "
                f"These dates (before {critical_start} or after {critical_end}) are not needed to satisfy forecast demand. "
                f"The model will proceed, but extend labor calendar if production is desired on these dates.",
                UserWarning
            )

        # Warning for missing weekends in critical range (optional capacity)
        if critical_missing_weekends:
            if len(critical_missing_weekends) <= 5:
                date_str = ', '.join(str(d) for d in sorted(critical_missing_weekends))
            else:
                date_str = ', '.join(str(d) for d in sorted(critical_missing_weekends)[:5]) + f" (and {len(critical_missing_weekends) - 5} more)"

            warnings.warn(
                f"Labor calendar missing weekend dates in critical forecast range: {date_str}. "
                f"These dates will have zero production capacity. "
                f"Add weekend labor entries if weekend production should be available.",
                UserWarning
            )

        # Info only for missing weekends in non-critical range
        if noncritical_missing_weekends:
            if len(noncritical_missing_weekends) <= 5:
                date_str = ', '.join(str(d) for d in sorted(noncritical_missing_weekends))
            else:
                date_str = ', '.join(str(d) for d in sorted(noncritical_missing_weekends)[:5]) + f" (and {len(noncritical_missing_weekends) - 5} more)"

            warnings.warn(
                f"Labor calendar missing {len(noncritical_missing_weekends)} weekend dates outside critical range: {date_str}. "
                f"These dates will have zero production capacity (weekend production is optional).",
                UserWarning
            )

        # Check 5: Shelf life constraints - are any destinations unreachable within shelf life?
        if self.enforce_shelf_life:
            unreachable_destinations = {}
            for dest in self.destinations:
                routes = self.routes_to_destination.get(dest, [])
                if routes:
                    # Check if all routes were filtered out by shelf life
                    all_routes_before_filter = [
                        r for r in self.route_enumerator.get_all_routes()
                        if r.destination_id == dest
                    ]
                    if len(all_routes_before_filter) > 0 and len(routes) == 0:
                        min_transit = min(r.total_transit_days for r in all_routes_before_filter)
                        unreachable_destinations[dest] = min_transit

            if unreachable_destinations:
                dest_details = ', '.join(
                    f"{dest} (min {days}d transit)"
                    for dest, days in sorted(unreachable_destinations.items())[:3]
                )
                issues.append(
                    f"Shelf life constraints filter out ALL routes to {len(unreachable_destinations)} destination(s): "
                    f"{dest_details}"
                    + (f" and {len(unreachable_destinations) - 3} more" if len(unreachable_destinations) > 3 else "")
                )

        # Raise error if critical issues found
        if issues:
            error_msg = "Feasibility validation failed. Problem is likely infeasible:\n"
            for i, issue in enumerate(issues, 1):
                error_msg += f"\n  {i}. {issue}"
            error_msg += "\n\nPlease fix these issues before attempting optimization."
            raise ValueError(error_msg)

    def _cohort_is_reachable(self, loc: str, prod: str, prod_date: Date, curr_date: Date) -> bool:
        """
        Check if a cohort (production from prod_date) can exist at location on curr_date.

        A cohort is reachable if:
        1. loc is manufacturing site (6122_Storage) - production flows here directly
        2. There is initial inventory at this location with this production date
        3. loc can be reached from manufacturing via a multi-hop route with compatible timing

        Args:
            loc: Location ID
            prod: Product ID
            prod_date: Date when product was produced
            curr_date: Current date (when we check if cohort exists)

        Returns:
            True if cohort can exist at this location
        """
        # Manufacturing storage: always reachable if production exists
        if loc == '6122_Storage':
            return True

        # Check if there's initial inventory at this location for this cohort
        # This handles inventory that's already present at locations before planning starts
        if self.initial_inventory:
            # Check both frozen and ambient states
            for state in ['frozen', 'ambient']:
                if (loc, prod, prod_date, state) in self.initial_inventory:
                    return True

        # For demand locations: check if reachable via enumerated routes (includes multi-hop paths)
        # Find minimum transit time from manufacturing to this location
        min_transit_time = None
        for route in self.enumerated_routes:
            if route.destination_id == loc:
                # This route reaches the destination (may be multi-hop via hubs)
                # Use total transit time including all hops
                total_transit = route.total_transit_days
                if min_transit_time is None or total_transit < min_transit_time:
                    min_transit_time = total_transit

        if min_transit_time is not None:
            earliest_arrival = prod_date + timedelta(days=min_transit_time)
            if earliest_arrival <= curr_date:
                return True

        # For intermediate storage locations (e.g., Lineage): check via direct legs
        # These can receive shipments but aren't enumerated route destinations
        for leg in self.legs_to_location.get(loc, []):
            transit_days = self.leg_transit_days.get(leg, 0)
            earliest_arrival = prod_date + timedelta(days=transit_days)

            # Can this cohort have arrived by curr_date?
            if earliest_arrival <= curr_date:
                return True

        return False

    def _build_cohort_indices(self, sorted_dates: List[Date]) -> Tuple[Set, Set, Set, Set, Set]:
        """
        Build sparse cohort indices for 4D inventory and shipment variables.

        This is critical for performance - naive 4D indexing would create millions of variables.
        We only create variables for valid (location, product, production_date, current_date) tuples.

        Valid cohort conditions:
        1. production_date <= current_date (can't have inventory from the future)
        2. age = current_date - production_date <= SHELF_LIFE (expired cohorts don't exist)
        3. location has received shipments from production_date OR is manufacturing site

        Returns:
            Tuple of (frozen_cohorts, ambient_cohorts, shipment_cohorts, demand_cohorts, freeze_thaw_cohorts)
            Each is a set of tuples defining valid indices
        """
        frozen_cohorts = set()
        ambient_cohorts = set()
        shipment_cohorts = set()
        demand_cohorts = set()

        print("\nBuilding sparse cohort indices...")

        # Collect all production dates: planning horizon + initial inventory
        all_prod_dates = set(sorted_dates)

        # Add initial inventory production dates (before planning horizon)
        if self.use_batch_tracking and self.initial_inventory:
            for key in self.initial_inventory.keys():
                if len(key) == 4:  # (loc, prod, prod_date, state)
                    prod_date = key[2]
                    all_prod_dates.add(prod_date)

        all_prod_dates_sorted = sorted(all_prod_dates)
        print(f"  Production dates: {len(sorted_dates)} in horizon + {len(all_prod_dates) - len(sorted_dates)} from initial inventory")

        # Store for use in constraint rules (includes initial inventory production dates)
        self.all_production_dates_with_initial_inventory = all_prod_dates_sorted

        # For each production date
        for prod_date in all_prod_dates_sorted:
            # For each current date >= production date
            for curr_date in [d for d in sorted_dates if d >= prod_date]:
                age_days = (curr_date - prod_date).days

                # For each location and product
                for loc in self.inventory_locations:
                    for prod in self.products:
                        # Frozen cohorts: long shelf life (120 days)
                        if loc in self.locations_frozen_storage and age_days <= self.FROZEN_SHELF_LIFE:
                            if self._cohort_is_reachable(loc, prod, prod_date, curr_date):
                                frozen_cohorts.add((loc, prod, prod_date, curr_date))

                        # Ambient cohorts: short shelf life (17 days for ambient, 14 for thawed)
                        if loc in self.locations_ambient_storage:
                            # 6130 (WA) uses thawed shelf life (14 days)
                            shelf_life = self.THAWED_SHELF_LIFE if loc == '6130' else self.AMBIENT_SHELF_LIFE
                            if age_days <= shelf_life:
                                if self._cohort_is_reachable(loc, prod, prod_date, curr_date):
                                    ambient_cohorts.add((loc, prod, prod_date, curr_date))

        # Shipment cohorts: for each leg, product, production_date, delivery_date
        for leg in self.leg_keys:
            for prod in self.products:
                transit_days = self.leg_transit_days.get(leg, 0)
                for delivery_date in sorted_dates:
                    # Departure date must be >= production date
                    departure_date = delivery_date - timedelta(days=transit_days)
                    for prod_date in all_prod_dates_sorted:
                        if prod_date <= departure_date and prod_date <= delivery_date:
                            # Check if this shipment makes sense (don't create too many indices)
                            # Only create if the cohort could exist at origin location
                            origin_loc = leg[0]
                            if origin_loc == '6122_Storage' or self._cohort_is_reachable(origin_loc, prod, prod_date, departure_date):
                                shipment_cohorts.add((leg, prod, prod_date, delivery_date))

        # Demand cohorts: for each demand point, which cohorts could satisfy it?
        for (loc, prod, demand_date) in self.demand.keys():
            # Any cohort produced before demand date and still fresh
            for prod_date in [d for d in all_prod_dates_sorted if d <= demand_date]:
                age_days = (demand_date - prod_date).days
                # Check shelf life
                shelf_life = self.THAWED_SHELF_LIFE if loc == '6130' else self.AMBIENT_SHELF_LIFE
                if age_days <= shelf_life:
                    # Check if cohort could exist at this location
                    if self._cohort_is_reachable(loc, prod, prod_date, demand_date):
                        demand_cohorts.add((loc, prod, prod_date, demand_date))

        # Freeze/thaw cohorts: for locations that support both frozen and ambient storage
        # These can convert inventory between storage modes
        freeze_thaw_cohorts = set()
        for loc in self.locations_with_freezing:
            for prod in self.products:
                for prod_date in all_prod_dates_sorted:
                    for curr_date in [d for d in sorted_dates if d >= prod_date]:
                        # Check if cohort could exist at this location on this date
                        # Apply same age constraints as regular cohorts
                        age_days = (curr_date - prod_date).days

                        # Can freeze if within ambient shelf life AND frozen shelf life
                        # Can thaw if within frozen shelf life
                        if age_days <= self.FROZEN_SHELF_LIFE:
                            if self._cohort_is_reachable(loc, prod, prod_date, curr_date):
                                freeze_thaw_cohorts.add((loc, prod, prod_date, curr_date))

        # Report index sizes
        print(f"  Frozen cohorts: {len(frozen_cohorts):,}")
        print(f"  Ambient cohorts: {len(ambient_cohorts):,}")
        print(f"  Shipment cohorts: {len(shipment_cohorts):,}")
        print(f"  Demand cohorts: {len(demand_cohorts):,}")
        print(f"  Freeze/thaw cohorts: {len(freeze_thaw_cohorts):,}")
        print(f"  Total: {len(frozen_cohorts) + len(ambient_cohorts) + len(shipment_cohorts) + len(demand_cohorts) + len(freeze_thaw_cohorts):,}")

        # Validate size is reasonable
        total_cohort_vars = len(frozen_cohorts) + len(ambient_cohorts) + len(shipment_cohorts) + len(demand_cohorts) + len(freeze_thaw_cohorts)
        if total_cohort_vars > 200000:
            warnings.warn(
                f"Cohort model is very large: {total_cohort_vars:,} cohort variables. "
                f"This may cause slow solve times. Consider reducing planning horizon or using rolling horizon."
            )

        return frozen_cohorts, ambient_cohorts, shipment_cohorts, demand_cohorts, freeze_thaw_cohorts

    def build_model(self) -> ConcreteModel:
        """
        Build integrated production-distribution optimization model.

        Returns:
            Pyomo ConcreteModel
        """
        model = ConcreteModel()

        # Sets
        model.dates = list(self.production_dates)
        model.products = list(self.products)
        model.routes = list(self.route_indices)  # LEGACY: Keep for backward compatibility
        model.legs = list(self.leg_keys)  # LEG-BASED ROUTING: (origin, destination) tuples

        # INVENTORY TRACKING: Sort dates for sequential processing
        # This ensures proper inventory balance calculations day-by-day
        sorted_dates = sorted(model.dates)
        model.dates_ordered = sorted_dates  # Store ordered list for constraint iteration

        # Create helper index for date sequencing
        # Maps each date to its previous date (None for first date)
        self.date_previous = {}
        for i, current_date in enumerate(sorted_dates):
            if i == 0:
                self.date_previous[current_date] = None  # First date has no previous
            else:
                self.date_previous[current_date] = sorted_dates[i - 1]

        # STATE TRACKING: Create sparse index sets for state-specific inventory variables
        # Include both demand locations and intermediate storage (e.g., Lineage)
        self.inventory_frozen_index_set = set()
        self.inventory_ambient_index_set = set()

        for loc in self.inventory_locations:
            # Special handling for virtual location 6122_Storage
            if loc == '6122_Storage':
                # 6122_Storage supports BOTH frozen and ambient (via freeze operations)
                for prod in self.products:
                    for date in sorted_dates:
                        self.inventory_ambient_index_set.add((loc, prod, date))
                        self.inventory_frozen_index_set.add((loc, prod, date))  # Add frozen too!
                continue  # Skip to next location

            # Regular locations: look up in location_by_id
            loc_obj = self.location_by_id.get(loc)
            if not loc_obj:
                continue

            for prod in self.products:
                for date in sorted_dates:
                    # Add frozen inventory if location supports frozen storage
                    if loc in self.locations_frozen_storage:
                        self.inventory_frozen_index_set.add((loc, prod, date))

                    # Add ambient inventory if location supports ambient storage
                    if loc in self.locations_ambient_storage:
                        self.inventory_ambient_index_set.add((loc, prod, date))

        model.inventory_frozen_index = list(self.inventory_frozen_index_set)
        model.inventory_ambient_index = list(self.inventory_ambient_index_set)

        # BATCH TRACKING: Build cohort indices if enabled
        if self.use_batch_tracking:
            (
                self.cohort_frozen_index_set,
                self.cohort_ambient_index_set,
                self.cohort_shipment_index_set,
                self.cohort_demand_index_set,
                self.cohort_freeze_thaw_index_set
            ) = self._build_cohort_indices(sorted_dates)

            model.cohort_frozen_index = list(self.cohort_frozen_index_set)
            model.cohort_ambient_index = list(self.cohort_ambient_index_set)
            model.cohort_shipment_index = list(self.cohort_shipment_index_set)
            model.cohort_demand_index = list(self.cohort_demand_index_set)
            model.cohort_freeze_thaw_index = list(self.cohort_freeze_thaw_index_set)

        # Decision variables: production[date, product]
        model.production = Var(
            model.dates,
            model.products,
            within=NonNegativeReals,
            doc="Production quantity by date and product"
        )

        # Packaging constraint: production in whole cases (10 units per case)
        model.production_cases = Var(
            model.dates,
            model.products,
            within=NonNegativeIntegers,
            doc="Number of cases produced (10 units per case)"
        )

        # Constraint: Link production to cases (production must be in whole cases)
        def production_case_link_rule(model, d, p):
            """Production quantity must equal number of cases times 10 units per case."""
            return model.production[d, p] == model.production_cases[d, p] * 10

        model.production_case_link_con = Constraint(
            model.dates,
            model.products,
            rule=production_case_link_rule,
            doc="Production must be in whole cases (10 units per case)"
        )

        # LEG-BASED ROUTING: Decision variables shipment[origin, dest, product, delivery_date]
        # Each network leg is an independent shipping decision
        # This enables strategic buffering at intermediate hubs (Lineage, 6104, 6125)
        # delivery_date = date when product arrives at destination
        model.shipment_leg = Var(
            model.legs,  # (origin, destination) tuples
            model.products,
            model.dates,
            within=NonNegativeReals,
            doc="Shipment quantity by network leg, product, and delivery date"
        )

        # Prevent phantom shipments: shipment_leg must be zero if departure would be before horizon
        def no_phantom_shipments_rule(model, origin, dest, prod, delivery_date):
            """Prevent shipments that would depart before planning horizon starts."""
            leg = (origin, dest)
            transit_days = self.leg_transit_days.get(leg, 0)
            departure_date = delivery_date - timedelta(days=transit_days)

            if departure_date < self.start_date:
                # This shipment would require departure before planning horizon
                return model.shipment_leg[leg, prod, delivery_date] == 0
            else:
                return Constraint.Skip

        model.no_phantom_shipments_con = Constraint(
            model.legs,
            model.products,
            model.dates,
            rule=no_phantom_shipments_rule,
            doc="Prevent shipments with departure before planning horizon"
        )

        # LEGACY: Keep route-based shipment for backward compatibility (DEPRECATED)
        # TODO: Remove after full migration to leg-based routing
        model.shipment = Var(
            model.routes,
            model.products,
            model.dates,
            within=NonNegativeReals,
            doc="[DEPRECATED] Route-based shipment - use shipment_leg instead"
        )

        # Truck scheduling variables (if truck schedules provided)
        if self.truck_schedules:
            model.trucks = list(self.truck_indices)

            # Get all unique destinations served by trucks
            truck_destinations = set(self.truck_destination.values())
            # Add intermediate stop destinations (like Lineage)
            for stops in self.trucks_with_intermediate_stops.values():
                truck_destinations.update(stops)
            model.truck_destinations = list(truck_destinations)

            # Binary variable: truck_used[truck_index, date]
            # 1 if truck is used on this date, 0 otherwise
            model.truck_used = Var(
                model.trucks,
                model.dates,
                within=Binary,
                doc="Binary indicator if truck is used on DELIVERY DATE"
            )

            # Continuous variable: truck_load[truck_index, destination, product, delivery_date]
            # Quantity of product loaded on truck going to specific destination
            # IMPORTANT: Indexed by DELIVERY DATE (not departure date)
            # delivery_date = departure_date + transit_days
            # This allows trucks with intermediate stops (like Wednesday Lineage route)
            # to carry different products to different destinations
            model.truck_load = Var(
                model.trucks,
                model.truck_destinations,
                model.products,
                model.dates,
                within=NonNegativeReals,
                doc="Quantity loaded on truck to destination by product and DELIVERY DATE"
            )

            # Integer variable: pallets_loaded[truck_index, destination, product, delivery_date]
            # Number of pallets loaded on truck (accounts for partial pallets taking full pallet space)
            # A pallet holds 320 units (32 cases * 10 units/case)
            # Partial pallets consume full pallet space (e.g., 1 case = 1 pallet space)
            model.pallets_loaded = Var(
                model.trucks,
                model.truck_destinations,
                model.products,
                model.dates,
                within=NonNegativeIntegers,
                doc="Number of pallets loaded on truck (320 units per full pallet)"
            )

        # Decision variables: shortage[dest, product, delivery_date] (if allowed)
        if self.allow_shortages:
            # Create shortage variables only for demand keys
            demand_keys = list(self.demand.keys())
            model.shortage = Var(
                [(dest, prod, deliv_date) for dest, prod, deliv_date in demand_keys],
                within=NonNegativeReals,
                doc="Demand shortage by destination, product, and delivery date"
            )

            # Shortage upper bound constraint: shortage cannot exceed demand
            def shortage_bound_rule(model, dest, prod, date):
                """Shortage cannot exceed demand quantity."""
                demand_qty = self.demand.get((dest, prod, date), 0)
                return model.shortage[dest, prod, date] <= demand_qty

            model.shortage_bound_con = Constraint(
                [(dest, prod, date) for dest, prod, date in self.demand.keys()],
                rule=shortage_bound_rule,
                doc="Shortage cannot exceed demand"
            )

        # STATE TRACKING: Decision variables for frozen and ambient inventory
        # inventory_frozen[loc, product, date]: Frozen inventory at location (no shelf life decay)
        # inventory_ambient[loc, product, date]: Ambient inventory at location (subject to shelf life)
        # Represents inventory level at location at END of each date
        # After shipments arrive and demand is satisfied
        model.inventory_frozen = Var(
            model.inventory_frozen_index,
            within=NonNegativeReals,
            doc="Frozen inventory at location by product and date (no shelf life decay)"
        )

        model.inventory_ambient = Var(
            model.inventory_ambient_index,
            within=NonNegativeReals,
            doc="Ambient/thawed inventory at location by product and date (subject to shelf life)"
        )

        # BATCH TRACKING: Cohort-based inventory variables (4D: location, product, production_date, current_date)
        if self.use_batch_tracking:
            model.inventory_frozen_cohort = Var(
                model.cohort_frozen_index,
                within=NonNegativeReals,
                doc="Frozen inventory by age cohort (loc, product, production_date, current_date)"
            )

            model.inventory_ambient_cohort = Var(
                model.cohort_ambient_index,
                within=NonNegativeReals,
                doc="Ambient inventory by age cohort (production_date enables shelf life tracking)"
            )

            # Shipment variables with cohort tracking
            model.shipment_leg_cohort = Var(
                model.cohort_shipment_index,
                within=NonNegativeReals,
                doc="Shipment quantity by leg and production cohort (leg, product, production_date, delivery_date)"
            )

            # Demand allocation by cohort (which cohort satisfies each demand)
            model.demand_from_cohort = Var(
                model.cohort_demand_index,
                within=NonNegativeReals,
                doc="Demand satisfied from specific cohort (enables FIFO allocation)"
            )

            # Freeze/thaw operations: Convert inventory between storage modes
            # freeze[loc, prod, prod_date, curr_date]: Quantity frozen from ambient to frozen state
            # thaw[loc, prod, prod_date, curr_date]: Quantity thawed from frozen to ambient state
            # Note: Thawing resets shelf life - thawed inventory on date X becomes a cohort with prod_date=X (14 days fresh)
            model.freeze = Var(
                model.cohort_freeze_thaw_index,
                within=NonNegativeReals,
                doc="Quantity frozen from ambient to frozen storage (loc, prod, prod_date, curr_date)"
            )

            model.thaw = Var(
                model.cohort_freeze_thaw_index,
                within=NonNegativeReals,
                doc="Quantity thawed from frozen to ambient storage - resets shelf life to 14 days"
            )

        # Auxiliary variables for labor cost calculation
        model.labor_hours = Var(
            model.dates,
            within=NonNegativeReals,
            doc="Labor hours used on each date"
        )

        model.fixed_hours_used = Var(
            model.dates,
            within=NonNegativeReals,
            doc="Fixed labor hours used on each date"
        )

        model.overtime_hours_used = Var(
            model.dates,
            within=NonNegativeReals,
            doc="Overtime hours used on each date"
        )

        model.non_fixed_hours_paid = Var(
            model.dates,
            within=NonNegativeReals,
            doc="Hours paid on non-fixed days (includes minimum commitment)"
        )

        # Binary variable to track if production happens on each date
        # Needed for fixed-day labor cost calculation
        model.production_day = Var(
            model.dates,
            within=Binary,
            doc="Binary indicator: 1 if production happens on this date, 0 otherwise"
        )

        # Constraint: Labor hours = production / production_rate
        def labor_hours_rule(model, d):
            return model.labor_hours[d] == sum(
                model.production[d, p] for p in model.products
            ) / self.PRODUCTION_RATE

        model.labor_hours_con = Constraint(
            model.dates,
            rule=labor_hours_rule,
            doc="Labor hours required"
        )

        # Constraint: Labor hours ≤ max hours per day
        def max_hours_rule(model, d):
            return model.labor_hours[d] <= self.MAX_HOURS_PER_DAY

        model.max_hours_con = Constraint(
            model.dates,
            rule=max_hours_rule,
            doc="Maximum labor hours per day"
        )

        # Constraint: Production capacity per day
        def max_capacity_rule(model, d):
            return sum(model.production[d, p] for p in model.products) <= self.max_capacity_per_day

        model.max_capacity_con = Constraint(
            model.dates,
            rule=max_capacity_rule,
            doc="Maximum production capacity per day"
        )

        # Constraint: Link production_day binary to actual production
        # If any production happens, production_day = 1
        def production_day_rule(model, d):
            total_production = sum(model.production[d, p] for p in model.products)
            # Big-M constraint: if production > 0, then production_day must be 1
            # We use max_capacity_per_day as the big-M value
            return total_production <= self.max_capacity_per_day * model.production_day[d]

        model.production_day_con = Constraint(
            model.dates,
            rule=production_day_rule,
            doc="Link production_day binary to actual production (forward direction)"
        )

        # CRITICAL FIX: Add reverse direction to prevent production_day=1 with zero production
        # Without this, solver can set production_day=1 even with no production,
        # causing idle labor costs (weekdays) or minimum payments (weekends: 4h × $40 = $160)
        def production_day_minimum_rule(model, d):
            """
            Enforce reverse direction: if production_day = 1, then production must be > 0.

            Together with production_day_rule, creates bi-directional enforcement:
            - production_day_rule: production > 0 => production_day = 1 (forward)
            - production_day_minimum_rule: production_day = 1 => production > 0 (reverse)

            This prevents:
            - Weekends showing $160 labor cost (4h minimum) with zero production
            - Production_day binary being "loose" and not tied to actual production

            Result: production_day = 1 if and only if production > 0
            """
            epsilon = 1.0  # Minimum production quantity (at least 1 unit)
            total_production = sum(model.production[d, p] for p in model.products)
            return total_production >= epsilon * model.production_day[d]

        model.production_day_minimum_con = Constraint(
            model.dates,
            rule=production_day_minimum_rule,
            doc="Link production_day binary to actual production (reverse direction)"
        )

        # Constraints: Calculate fixed hours and overtime for fixed days
        def fixed_hours_rule(model, d):
            """
            CRITICAL FIX: On fixed days (weekdays), workers are salaried and paid
            for fixed hours REGARDLESS of production volume. This is a sunk cost.

            Business Rule:
            - Weekdays: Pay 12 fixed hours whether production = 0 or production > 0
            - Weekends/Holidays: No fixed hours (only pay if production occurs)

            This ensures the model prefers weekday production (effectively "free"
            since labor is already paid) over weekend production ($40/hr + 4h minimum).
            """
            labor_day = self.labor_by_date.get(d)
            if not labor_day or not labor_day.is_fixed_day:
                return model.fixed_hours_used[d] == 0
            else:
                # Weekdays: ALWAYS pay for fixed hours (sunk cost)
                return model.fixed_hours_used[d] == labor_day.fixed_hours

        model.fixed_hours_rule = Constraint(
            model.dates,
            rule=fixed_hours_rule,
            doc="Fixed hours calculation"
        )

        def overtime_hours_rule(model, d):
            """
            Overtime hours calculation for fixed days.

            Overtime only occurs if labor_hours > fixed_hours.
            With the new fixed_hours_used = fixed_hours * production_day logic,
            we need: overtime = max(0, labor_hours - fixed_hours)
            """
            labor_day = self.labor_by_date.get(d)
            if not labor_day or not labor_day.is_fixed_day:
                return model.overtime_hours_used[d] == 0
            else:
                # Overtime is the excess over fixed hours (if any)
                # Must be >= 0 and >= (labor_hours - fixed_hours)
                return model.overtime_hours_used[d] >= model.labor_hours[d] - labor_day.fixed_hours

        def overtime_hours_lower_rule(model, d):
            """Overtime hours must be non-negative."""
            return model.overtime_hours_used[d] >= 0

        model.overtime_hours_rule = Constraint(
            model.dates,
            rule=overtime_hours_rule,
            doc="Overtime hours calculation"
        )

        model.overtime_hours_lower = Constraint(
            model.dates,
            rule=overtime_hours_lower_rule,
            doc="Overtime hours non-negative"
        )

        # Constraints: Non-fixed day labor calculation
        def non_fixed_hours_rule(model, d):
            labor_day = self.labor_by_date.get(d)
            if not labor_day or labor_day.is_fixed_day:
                return model.non_fixed_hours_paid[d] == 0
            else:
                return model.non_fixed_hours_paid[d] >= model.labor_hours[d]

        model.non_fixed_hours_min_rule = Constraint(
            model.dates,
            rule=non_fixed_hours_rule,
            doc="Non-fixed hours >= actual hours"
        )

        def non_fixed_hours_minimum_rule(model, d):
            """
            CRITICAL FIX: Weekend/holiday minimum payment should only apply when production occurs.

            Business Rule:
            - If production_day = 1 (production occurs): Pay at least minimum_hours (4h × $40 = $160)
            - If production_day = 0 (no production): Pay nothing

            Without production_day factor, the model pays $160 on idle weekends (e.g., Nov 8, Nov 9).
            """
            labor_day = self.labor_by_date.get(d)
            if not labor_day or labor_day.is_fixed_day:
                return Constraint.Skip
            else:
                # Minimum payment only when production_day = 1
                return model.non_fixed_hours_paid[d] >= labor_day.minimum_hours * model.production_day[d]

        model.non_fixed_hours_minimum = Constraint(
            model.dates,
            rule=non_fixed_hours_minimum_rule,
            doc="Non-fixed hours >= minimum commitment (only when producing)"
        )

        # PRODUCTION SMOOTHING CONSTRAINT (optional, enabled by default with batch tracking)
        # Prevents production concentration on single days by limiting day-to-day variation.
        # This replaces the broken FIFO penalty that previously caused this issue.
        if self.enable_production_smoothing:
            # Calculate maximum daily production capacity
            max_daily_production = self.PRODUCTION_RATE * self.MAX_HOURS_PER_DAY

            # Maximum allowed day-to-day change (20% of max capacity)
            max_production_change = 0.20 * max_daily_production

            def production_smoothing_rule(model, p, d):
                """
                Limit day-to-day production variation to prevent concentration.

                For each product on each date (except first date):
                |production[d] - production[d-1]| <= 20% of max_daily_capacity

                Implemented as two linear constraints:
                - production[d] - production[d-1] <= max_change
                - production[d-1] - production[d] <= max_change

                This prevents the optimizer from concentrating all production on one day
                while still allowing reasonable flexibility for demand patterns.
                """
                dates_list = sorted(model.dates)
                if d == dates_list[0]:
                    # Skip first date (no previous day to compare)
                    return Constraint.Skip

                # Find previous date
                d_idx = dates_list.index(d)
                prev_d = dates_list[d_idx - 1]

                # Return as tuple for automatic two-sided constraint
                # -max_change <= production[d] - production[d-1] <= max_change
                return (
                    -max_production_change,
                    model.production[prev_d, p] - model.production[d, p],
                    max_production_change
                )

            model.production_smoothing_con = Constraint(
                model.products,
                model.dates,
                rule=production_smoothing_rule,
                doc="Limit day-to-day production variation (prevents concentration)"
            )

        # STATE TRACKING: INVENTORY BALANCE CONSTRAINTS
        # Two separate constraints for frozen and ambient inventory states
        #
        # FROZEN BALANCE: frozen[t] = frozen[t-1] + frozen_arrivals[t] - frozen_outflows[t]
        # AMBIENT BALANCE: ambient[t] = ambient[t-1] + ambient_arrivals[t] - demand[t] - shortage[t]
        #
        # Key rule: Frozen routes to non-frozen destinations automatically thaw → arrive as ambient

        def inventory_frozen_balance_rule(model, loc, prod, date):
            """
            Frozen inventory balance at location.

            frozen_inv[t] = frozen_inv[t-1] + frozen_arrivals[t] - frozen_outflows[t]

            Frozen inventory:
            - Increases from frozen route arrivals (frozen route + frozen-only destination)
            - Decreases from outbound shipments on frozen routes (for intermediate storage)
            - Does NOT satisfy demand directly (must thaw first)
            - No shelf life decay (120-day limit is generous)

            Args:
                loc: Location ID (destination or intermediate storage)
                prod: Product ID
                date: Date (end of day)
            """
            # LEG-BASED ROUTING: Get legs delivering frozen to this location
            legs_frozen_arrival = [
                (o, d) for (o, d) in self.legs_to_location.get(loc, [])
                if self.leg_arrival_state.get((o, d)) == 'frozen'
            ]

            # Frozen arrivals
            frozen_arrivals = sum(
                model.shipment_leg[(o, d), prod, date]
                for (o, d) in legs_frozen_arrival
            )

            # LEG-BASED ROUTING: Frozen outflows (shipments departing from this location)
            # CRITICAL FIX: Include ANY location with frozen outbound legs (not just intermediate_storage)
            frozen_outflows = 0
            legs_from_loc = self.legs_from_location.get(loc, [])
            if legs_from_loc:
                # Sum outbound frozen shipments departing on this date
                for (origin, dest) in legs_from_loc:
                    # Only count frozen legs (check leg_arrival_state)
                    if self.leg_arrival_state.get((origin, dest)) != 'frozen':
                        continue

                    # Shipment variable is indexed by delivery_date
                    # To find shipments departing on 'date', we need delivery_date where:
                    # departure_date = delivery_date - transit_days = date
                    # Therefore: delivery_date = date + transit_days
                    transit_days = self.leg_transit_days[(origin, dest)]
                    delivery_date = date + timedelta(days=transit_days)
                    if delivery_date in model.dates:
                        frozen_outflows += model.shipment_leg[(origin, dest), prod, delivery_date]

            # Previous frozen inventory
            prev_date = self.date_previous.get(date)
            if prev_date is None:
                # First date: use initial inventory if provided, otherwise 0
                # Note: initial_inventory can be Dict[(loc, prod), qty] or Dict[(loc, prod, state), qty]
                # Try state-specific first, then fallback to non-state
                prev_frozen = self.initial_inventory.get((loc, prod, 'frozen'),
                              self.initial_inventory.get((loc, prod), 0))
            else:
                # Check if previous date inventory exists in sparse index
                if (loc, prod, prev_date) in self.inventory_frozen_index_set:
                    prev_frozen = model.inventory_frozen[loc, prod, prev_date]
                else:
                    prev_frozen = 0

            # Balance equation
            return model.inventory_frozen[loc, prod, date] == (
                prev_frozen + frozen_arrivals - frozen_outflows
            )

        model.inventory_frozen_balance_con = Constraint(
            model.inventory_frozen_index,
            rule=inventory_frozen_balance_rule,
            doc="Frozen inventory balance at locations (no shelf life decay)"
        )

        def inventory_ambient_balance_rule(model, loc, prod, date):
            """
            Ambient inventory balance at location.

            ambient_inv[t] = ambient_inv[t-1] + ambient_arrivals[t] - demand[t] + shortage[t]

            Note: shortage represents UNSATISFIED demand. Actual consumption = demand - shortage.
            Therefore: inventory = prev + arrivals - (demand - shortage) - outflows
                                 = prev + arrivals - demand + shortage - outflows

            Special case for 6122_Storage (virtual manufacturing storage):
            - Arrivals = production on that date
            - Departures = truck loads departing on that date
            - No demand or shortage

            Ambient inventory:
            - Increases from ambient route arrivals (includes automatic thawing from frozen routes)
            - Decreases from demand satisfaction (only at demand locations)
            - Subject to shelf life constraints (17 days ambient, 14 days post-thaw)

            Args:
                loc: Location ID (destination or intermediate storage)
                prod: Product ID
                date: Date (end of day)
            """
            # Special case: 6122_Storage virtual location
            if loc == '6122_Storage':
                # Previous inventory
                prev_date = self.date_previous.get(date)
                if prev_date is None:
                    # First date: use initial inventory
                    prev_ambient = self.initial_inventory.get(('6122_Storage', prod, 'ambient'),
                                   self.initial_inventory.get(('6122_Storage', prod), 0))
                else:
                    if (loc, prod, prev_date) in self.inventory_ambient_index_set:
                        prev_ambient = model.inventory_ambient[loc, prod, prev_date]
                    else:
                        prev_ambient = 0

                # Arrivals = production on this date
                production_arrival = model.production[date, prod] if date in model.dates else 0

                # Departures = truck loads departing on this date
                # Find all trucks that depart on this date
                truck_outflows = 0
                if self.truck_schedules:
                    for truck_idx in model.trucks:
                        for dest in model.truck_destinations:
                            # Calculate transit days for this truck-destination pair
                            transit_days = self._get_truck_transit_days(truck_idx, dest)

                            # For each delivery date, check if departure is on current date
                            for delivery_date in model.dates:
                                departure_date = delivery_date - timedelta(days=transit_days)
                                # BUG FIX: Only count departures within planning horizon
                                # Departures before start_date are handled by initial_inventory
                                if departure_date == date and departure_date in model.dates:
                                    # This truck-destination-delivery combination departs on current date
                                    truck_outflows += model.truck_load[truck_idx, dest, prod, delivery_date]

                # Balance: inventory = previous + production - truck outflows
                return model.inventory_ambient[loc, prod, date] == (
                    prev_ambient + production_arrival - truck_outflows
                )

            # Standard inventory balance for other locations
            # LEG-BASED ROUTING: Get legs delivering ambient to this location
            # This includes:
            # - True ambient legs
            # - Frozen legs that thaw on arrival (frozen leg to non-frozen destination)
            legs_ambient_arrival = [
                (o, d) for (o, d) in self.legs_to_location.get(loc, [])
                if self.leg_arrival_state.get((o, d)) == 'ambient'
            ]

            # Ambient arrivals (includes automatic thawing)
            ambient_arrivals = sum(
                model.shipment_leg[(o, d), prod, date]
                for (o, d) in legs_ambient_arrival
            )

            # Demand on this date (0 if no demand or intermediate storage)
            demand_qty = self.demand.get((loc, prod, date), 0.0)

            # Shortage
            shortage_qty = 0
            if self.allow_shortages and (loc, prod, date) in self.demand:
                shortage_qty = model.shortage[loc, prod, date]

            # LEG-BASED ROUTING: Calculate ambient outflows from this location
            # Similar to frozen outflows at Lineage, we need to account for shipments
            # departing from hub locations (6104, 6125) to their spoke destinations
            ambient_outflows = 0
            legs_from_loc = self.legs_from_location.get(loc, [])
            for (origin, dest) in legs_from_loc:
                if self.leg_arrival_state.get((origin, dest)) == 'ambient':
                    # Shipments are indexed by delivery date
                    # To get outflows on current date, find shipments that deliver in the future
                    transit_days = self.leg_transit_days[(origin, dest)]
                    delivery_date = date + timedelta(days=transit_days)
                    if delivery_date in model.dates:
                        ambient_outflows += model.shipment_leg[(origin, dest), prod, delivery_date]

            # Previous ambient inventory
            prev_date = self.date_previous.get(date)
            if prev_date is None:
                # First date: use initial inventory if provided, otherwise 0
                prev_ambient = self.initial_inventory.get((loc, prod, 'ambient'),
                               self.initial_inventory.get((loc, prod), 0))
            else:
                # Check if previous date inventory exists in sparse index
                if (loc, prod, prev_date) in self.inventory_ambient_index_set:
                    prev_ambient = model.inventory_ambient[loc, prod, prev_date]
                else:
                    prev_ambient = 0

            # Balance equation
            # Correct formulation: shortage represents UNSATISFIED demand
            # Actual consumption from inventory = demand - shortage
            # Therefore: inventory[t] = prev + arrivals - (demand - shortage) - outflows
            #                          = prev + arrivals - demand + shortage - outflows
            return model.inventory_ambient[loc, prod, date] == (
                prev_ambient + ambient_arrivals - demand_qty + shortage_qty - ambient_outflows
            )

        model.inventory_ambient_balance_con = Constraint(
            model.inventory_ambient_index,
            rule=inventory_ambient_balance_rule,
            doc="Ambient inventory balance at locations (subject to shelf life)"
        )

        # BATCH TRACKING: Cohort-based inventory balance constraints
        if self.use_batch_tracking:
            def inventory_frozen_cohort_balance_rule(model, loc, prod, prod_date, curr_date):
                """
                Frozen inventory balance by age cohort.

                frozen_cohort[t] = frozen_cohort[t-1] + frozen_arrivals[t] + freeze_input[t] - frozen_departures[t] - thaw_output[t]

                Shelf life enforcement: Frozen products have 120-day shelf life (handled by sparse indexing).
                """
                # Previous cohort inventory
                prev_date = self.date_previous.get(curr_date)
                if prev_date is None:
                    # First date: initial inventory (if any)
                    prev_cohort = self.initial_inventory.get((loc, prod, prod_date, 'frozen'), 0)
                else:
                    if (loc, prod, prod_date, prev_date) in self.cohort_frozen_index_set:
                        prev_cohort = model.inventory_frozen_cohort[loc, prod, prod_date, prev_date]
                    else:
                        prev_cohort = 0

                # Frozen arrivals from shipments with this production_date
                frozen_arrivals = 0
                for (origin, dest) in self.legs_to_location.get(loc, []):
                    if self.leg_arrival_state.get((origin, dest)) == 'frozen':
                        leg = (origin, dest)
                        if (leg, prod, prod_date, curr_date) in self.cohort_shipment_index_set:
                            frozen_arrivals += model.shipment_leg_cohort[leg, prod, prod_date, curr_date]

                # Frozen departures (for ANY location with outbound frozen legs)
                # CRITICAL FIX: Include 6122_Storage, not just intermediate_storage
                frozen_departures = 0
                legs_from_loc = self.legs_from_location.get(loc, [])
                if legs_from_loc:
                    for (origin, dest) in legs_from_loc:
                        if self.leg_arrival_state.get((origin, dest)) == 'frozen':
                            transit_days = self.leg_transit_days[(origin, dest)]
                            delivery_date = curr_date + timedelta(days=transit_days)
                            leg = (origin, dest)
                            if (leg, prod, prod_date, delivery_date) in self.cohort_shipment_index_set:
                                frozen_departures += model.shipment_leg_cohort[leg, prod, prod_date, delivery_date]

                # Freeze input: ambient inventory converted to frozen (if location supports freezing)
                freeze_input = 0
                if loc in self.locations_with_freezing:
                    if (loc, prod, prod_date, curr_date) in self.cohort_freeze_thaw_index_set:
                        freeze_input = model.freeze[loc, prod, prod_date, curr_date]

                # Thaw output: frozen inventory converted to ambient (if location supports thawing)
                thaw_output = 0
                if loc in self.locations_with_freezing:
                    if (loc, prod, prod_date, curr_date) in self.cohort_freeze_thaw_index_set:
                        thaw_output = model.thaw[loc, prod, prod_date, curr_date]

                # Balance equation
                return model.inventory_frozen_cohort[loc, prod, prod_date, curr_date] == (
                    prev_cohort + frozen_arrivals + freeze_input - frozen_departures - thaw_output
                )

            model.inventory_frozen_cohort_balance_con = Constraint(
                model.cohort_frozen_index,
                rule=inventory_frozen_cohort_balance_rule,
                doc="Frozen inventory balance by age cohort"
            )

            def inventory_ambient_cohort_balance_rule(model, loc, prod, prod_date, curr_date):
                """
                Ambient inventory balance by age cohort.

                ambient_cohort[t] = ambient_cohort[t-1] + production[t] + ambient_arrivals[t] + thaw_input[t] -
                                     demand_consumption[t] - ambient_departures[t] - freeze_output[t]

                CRITICAL DESIGN: Thawing resets shelf life
                - When inventory is thawed on date X, it becomes an ambient cohort with prod_date=X
                - This gives it 14 days of fresh shelf life from the thaw date
                - Therefore, thaw_input sums over ALL production dates (all thawed inventory becomes prod_date=curr_date)

                Shelf life enforcement: cohort variables only created for age <= SHELF_LIFE (sparse indexing).
                """
                # Previous cohort inventory
                prev_date = self.date_previous.get(curr_date)
                if prev_date is None:
                    # First date: initial inventory
                    prev_cohort = self.initial_inventory.get((loc, prod, prod_date, 'ambient'), 0)
                else:
                    if (loc, prod, prod_date, prev_date) in self.cohort_ambient_index_set:
                        prev_cohort = model.inventory_ambient_cohort[loc, prod, prod_date, prev_date]
                    else:
                        prev_cohort = 0

                # Production input (only at 6122_Storage on production date)
                production_input = 0
                if loc == '6122_Storage' and prod_date == curr_date:
                    production_input = model.production[curr_date, prod]

                # Ambient arrivals from shipments
                ambient_arrivals = 0
                for (origin, dest) in self.legs_to_location.get(loc, []):
                    if self.leg_arrival_state.get((origin, dest)) == 'ambient':
                        leg = (origin, dest)
                        if (leg, prod, prod_date, curr_date) in self.cohort_shipment_index_set:
                            ambient_arrivals += model.shipment_leg_cohort[leg, prod, prod_date, curr_date]

                # Ambient departures (for locations with outbound ambient legs: intermediate storage, 6122_Storage, and destination hubs)
                # BUG FIX: Previously only calculated for intermediate_storage and 6122_Storage,
                # missing hub locations (6104, 6125) which also have outbound legs to spokes.
                # This caused inventory accumulation at hubs as spoke shipments weren't deducted.
                ambient_departures = 0
                # Check if this location has outbound ambient legs (using pre-computed set for performance)
                if loc in self.locations_with_outbound_ambient_legs:
                    legs_from_loc = self.legs_from_location[loc]
                    for (origin, dest) in legs_from_loc:
                        if self.leg_arrival_state.get((origin, dest)) == 'ambient':
                            transit_days = self.leg_transit_days[(origin, dest)]
                            delivery_date = curr_date + timedelta(days=transit_days)
                            leg = (origin, dest)
                            # Only add if this cohort shipment exists in sparse index (performance)
                            if (leg, prod, prod_date, delivery_date) in self.cohort_shipment_index_set:
                                ambient_departures += model.shipment_leg_cohort[leg, prod, prod_date, delivery_date]

                # Demand consumption from this cohort
                demand_consumption = 0
                if loc in self.destinations and (loc, prod, curr_date) in self.demand:
                    if (loc, prod, prod_date, curr_date) in self.cohort_demand_index_set:
                        demand_consumption = model.demand_from_cohort[loc, prod, prod_date, curr_date]

                # Freeze output: ambient inventory converted to frozen (if location supports freezing)
                freeze_output = 0
                if loc in self.locations_with_freezing:
                    if (loc, prod, prod_date, curr_date) in self.cohort_freeze_thaw_index_set:
                        freeze_output = model.freeze[loc, prod, prod_date, curr_date]

                # Thaw input: frozen inventory converted to ambient (if location supports thawing)
                # KEY DESIGN: Thawed inventory on date X becomes a cohort with prod_date=X (resets shelf life to 14 days)
                # Therefore, we sum ALL thaw operations on curr_date that affect this cohort
                thaw_input = 0
                if loc in self.locations_with_freezing and prod_date == curr_date:
                    # This cohort receives all inventory thawed on curr_date (regardless of original prod_date)
                    # Sum over all production dates that could be thawed on this date
                    for original_prod_date in sorted_dates:
                        if original_prod_date <= curr_date:  # Can't thaw future production
                            if (loc, prod, original_prod_date, curr_date) in self.cohort_freeze_thaw_index_set:
                                thaw_input += model.thaw[loc, prod, original_prod_date, curr_date]

                # Balance equation
                return model.inventory_ambient_cohort[loc, prod, prod_date, curr_date] == (
                    prev_cohort + production_input + ambient_arrivals + thaw_input - demand_consumption - ambient_departures - freeze_output
                )

            model.inventory_ambient_cohort_balance_con = Constraint(
                model.cohort_ambient_index,
                rule=inventory_ambient_cohort_balance_rule,
                doc="Ambient inventory balance by age cohort (shelf life enforced via sparse indexing)"
            )

            # AUTOMATIC FREEZE/THAW CONSTRAINTS
            # Freeze/thaw operations are AUTOMATIC (not optional) based on storage mode mismatches
            # - Ambient arriving at frozen-only storage → must freeze
            # - Frozen arriving at ambient-only storage → must thaw

            def automatic_freeze_rule(model, loc, prod, prod_date, curr_date):
                """Force freeze operation when ambient shipments arrive at frozen storage facility.

                Business rule: If a location is a FROZEN STORAGE FACILITY (type=STORAGE with frozen capability),
                any ambient arrivals must be automatically frozen. This is not optional.

                Example: Lineage (frozen storage) receives ambient from 6122 → must freeze upon arrival.

                Note: storage_mode can be FROZEN or BOTH, but type must be STORAGE.
                """
                # Only apply to storage-type locations with frozen capability
                loc_obj = self.location_by_id.get(loc)
                if not loc_obj:
                    return Constraint.Skip

                # Check if this is a frozen storage facility (Lineage)
                is_frozen_storage = (
                    loc_obj.type == LocationType.STORAGE and
                    loc in self.locations_frozen_storage
                )

                if not is_frozen_storage:
                    return Constraint.Skip

                # Build list of ambient shipment variables that could arrive
                ambient_shipment_vars = []
                for (origin, dest) in self.legs_to_location.get(loc, []):
                    if self.leg_arrival_state.get((origin, dest)) == 'ambient':
                        leg = (origin, dest)
                        if (leg, prod, prod_date, curr_date) in self.cohort_shipment_index_set:
                            ambient_shipment_vars.append(model.shipment_leg_cohort[leg, prod, prod_date, curr_date])

                # Skip if no ambient shipment variables exist
                if not ambient_shipment_vars:
                    return Constraint.Skip

                # Sum ambient arrivals (Pyomo expression)
                ambient_arrivals_expr = sum(ambient_shipment_vars)

                # Check if freeze variable exists
                if (loc, prod, prod_date, curr_date) not in self.cohort_freeze_thaw_index_set:
                    return Constraint.Skip

                # Constraint: freeze must equal ambient arrivals (automatic freezing!)
                freeze_op = model.freeze[loc, prod, prod_date, curr_date]
                return freeze_op == ambient_arrivals_expr

            model.automatic_freeze_con = Constraint(
                model.cohort_frozen_index,
                rule=automatic_freeze_rule,
                doc="Automatic freeze when ambient arrives at frozen-only storage"
            )

            def automatic_thaw_rule(model, loc, prod, prod_date, curr_date):
                """Force thaw operation when frozen shipments arrive at ambient storage.

                Business rule: If frozen product arrives at a location that stores ambient/thawed,
                it must be automatically thawed upon arrival. This is not optional.

                Example: 6130 (WA) receives frozen from Lineage → must thaw upon arrival.

                Note: This applies to BREADROOM locations (final destinations), not storage facilities.
                """
                # Only apply to destination locations (breadrooms)
                loc_obj = self.location_by_id.get(loc)
                if not loc_obj or loc_obj.type != LocationType.BREADROOM:
                    return Constraint.Skip

                # Check if location can only store ambient (not frozen)
                if loc not in self.locations_ambient_storage:
                    return Constraint.Skip

                # Only apply to cohorts that receive thawed inventory (prod_date == curr_date)
                if prod_date != curr_date:
                    return Constraint.Skip

                # Build list of frozen shipment cohorts that could arrive at this location
                frozen_shipment_vars = []
                for (origin, dest) in self.legs_to_location.get(loc, []):
                    if self.leg_arrival_state.get((origin, dest)) == 'frozen':
                        leg = (origin, dest)
                        if (leg, prod, prod_date, curr_date) in self.cohort_shipment_index_set:
                            frozen_shipment_vars.append(model.shipment_leg_cohort[leg, prod, prod_date, curr_date])

                # Skip if no frozen shipment variables exist (nothing to thaw)
                if not frozen_shipment_vars:
                    return Constraint.Skip

                # Sum frozen arrivals (this is a Pyomo expression)
                frozen_arrivals_expr = sum(frozen_shipment_vars)

                # Build list of thaw operation variables
                thaw_vars = []
                for original_prod_date in sorted_dates:
                    if original_prod_date <= curr_date:
                        if (loc, prod, original_prod_date, curr_date) in self.cohort_freeze_thaw_index_set:
                            thaw_vars.append(model.thaw[loc, prod, original_prod_date, curr_date])

                # If no thaw variables exist, can't create constraint
                if not thaw_vars:
                    return Constraint.Skip

                # Sum all thaw operations creating this cohort (Pyomo expression)
                total_thaw_expr = sum(thaw_vars)

                # Constraint: thaw operations must equal frozen arrivals (automatic thawing)
                return total_thaw_expr == frozen_arrivals_expr

            model.automatic_thaw_con = Constraint(
                model.cohort_ambient_index,
                rule=automatic_thaw_rule,
                doc="Automatic thaw when frozen arrives at ambient-only storage"
            )

            # Demand allocation constraint: sum of cohorts = demand - shortage
            def demand_cohort_allocation_rule(model, loc, prod, curr_date):
                """Total demand from all cohorts = actual demand - shortage."""
                if (loc, prod, curr_date) not in self.demand:
                    return Constraint.Skip

                demand_qty = self.demand[(loc, prod, curr_date)]

                # Sum consumption from all cohorts (all production dates)
                total_from_cohorts = sum(
                    model.demand_from_cohort[loc, prod, prod_date, curr_date]
                    for prod_date in sorted_dates
                    if (loc, prod, prod_date, curr_date) in self.cohort_demand_index_set
                )

                # Shortage (if allowed)
                shortage_qty = 0
                if self.allow_shortages and (loc, prod, curr_date) in self.demand:
                    shortage_qty = model.shortage[loc, prod, curr_date]

                return total_from_cohorts + shortage_qty == demand_qty

            model.demand_cohort_allocation_con = Constraint(
                [(loc, prod, date) for loc, prod, date in self.demand.keys()],
                rule=demand_cohort_allocation_rule,
                doc="Demand satisfied from cohorts + shortage = total demand"
            )

            # Cohort aggregation: shipment_leg_cohort sums to shipment_leg
            def shipment_cohort_aggregation_rule(model, origin, dest, prod, delivery_date):
                """Sum of cohort shipments = total leg shipment."""
                leg = (origin, dest)
                # Use all_production_dates_with_initial_inventory to include initial inventory production dates
                prod_dates_to_sum = self.all_production_dates_with_initial_inventory if hasattr(self, 'all_production_dates_with_initial_inventory') else sorted_dates
                total_cohorts = sum(
                    model.shipment_leg_cohort[leg, prod, prod_date, delivery_date]
                    for prod_date in prod_dates_to_sum
                    if (leg, prod, prod_date, delivery_date) in self.cohort_shipment_index_set
                )
                return total_cohorts == model.shipment_leg[leg, prod, delivery_date]

            model.shipment_cohort_aggregation_con = Constraint(
                model.legs,
                model.products,
                model.dates,
                rule=shipment_cohort_aggregation_rule,
                doc="Cohort shipments aggregate to total leg shipments"
            )

        # NOTE: Flow conservation is now handled by 6122_Storage inventory balance
        # Production flows into 6122_Storage, trucks load from 6122_Storage
        # The inventory balance equation automatically ensures production >= truck loads

        # Truck scheduling constraints (if truck schedules provided)
        if self.truck_schedules:
            # Constraint: Truck capacity
            def truck_capacity_rule(model, truck_idx, d):
                """Total load on truck (across all destinations) cannot exceed capacity."""
                total_load = sum(
                    model.truck_load[truck_idx, dest, p, d]
                    for dest in model.truck_destinations
                    for p in model.products
                )
                capacity = self.truck_capacity[truck_idx]
                return total_load <= capacity * model.truck_used[truck_idx, d]

            model.truck_capacity_con = Constraint(
                model.trucks,
                model.dates,
                rule=truck_capacity_rule,
                doc="Truck capacity constraint (sum across all destinations)"
            )

            # Constraint: Pallet lower bound (pallets must be enough to hold truck_load)
            # pallets_loaded * 320 >= truck_load
            # This ensures we have at least ceil(truck_load / 320) pallets
            def pallet_lower_bound_rule(model, truck_idx, dest, prod, d):
                """Pallets loaded must be sufficient to hold all units (accounts for partial pallets)."""
                return model.pallets_loaded[truck_idx, dest, prod, d] * 320 >= model.truck_load[truck_idx, dest, prod, d]

            model.pallet_lower_bound_con = Constraint(
                model.trucks,
                model.truck_destinations,
                model.products,
                model.dates,
                rule=pallet_lower_bound_rule,
                doc="Pallets must be sufficient to hold truck load (lower bound)"
            )

            # Constraint: Pallet upper bound (pallets cannot exceed ceiling of truck_load / 320)
            # pallets_loaded * 320 <= truck_load + 319
            # This ensures we don't allocate more pallets than needed: pallets = ceil(truck_load / 320)
            def pallet_upper_bound_rule(model, truck_idx, dest, prod, d):
                """Pallets loaded cannot exceed ceiling of units divided by 320."""
                return model.pallets_loaded[truck_idx, dest, prod, d] * 320 <= model.truck_load[truck_idx, dest, prod, d] + 319

            model.pallet_upper_bound_con = Constraint(
                model.trucks,
                model.truck_destinations,
                model.products,
                model.dates,
                rule=pallet_upper_bound_rule,
                doc="Pallets cannot exceed ceiling of truck load divided by 320 (upper bound)"
            )

            # Constraint: Pallet capacity (total pallets on truck cannot exceed pallet capacity)
            # sum(pallets_loaded) <= pallet_capacity * truck_used
            # Typically pallet_capacity = 44 pallets per truck
            def pallet_capacity_rule(model, truck_idx, d):
                """Total pallets on truck (across all destinations and products) cannot exceed pallet capacity."""
                total_pallets = sum(
                    model.pallets_loaded[truck_idx, dest, p, d]
                    for dest in model.truck_destinations
                    for p in model.products
                )
                pallet_capacity = self.truck_pallet_capacity[truck_idx]
                return total_pallets <= pallet_capacity * model.truck_used[truck_idx, d]

            model.pallet_capacity_con = Constraint(
                model.trucks,
                model.dates,
                rule=pallet_capacity_rule,
                doc="Pallet capacity constraint (sum across all destinations and products)"
            )

            # Constraint: Truck availability (day-specific scheduling)
            def truck_availability_rule(model, truck_idx, delivery_date):
                """Truck can only be used on delivery dates corresponding to valid departure dates."""
                # Check if this truck can deliver on delivery_date
                # Get truck object
                truck = self.truck_by_index[truck_idx]

                # Check primary destination
                dest_id = truck.destination_id
                transit_days = self._get_truck_transit_days(truck_idx, dest_id)
                departure_date = delivery_date - timedelta(days=transit_days)

                # Check if truck runs on the required departure date
                trucks_available = self.trucks_on_date.get(departure_date, [])
                can_deliver = truck_idx in trucks_available

                # Also check intermediate stops if any
                if not can_deliver and truck_idx in self.trucks_with_intermediate_stops:
                    for stop_id in self.trucks_with_intermediate_stops[truck_idx]:
                        transit_days = self._get_truck_transit_days(truck_idx, stop_id)
                        departure_date = delivery_date - timedelta(days=transit_days)
                        trucks_available = self.trucks_on_date.get(departure_date, [])
                        if truck_idx in trucks_available:
                            can_deliver = True
                            break

                if not can_deliver:
                    # Truck cannot deliver on this date (no valid departure date)
                    return model.truck_used[truck_idx, delivery_date] == 0
                else:
                    # Truck can deliver on this date - no constraint (can be 0 or 1)
                    return Constraint.Skip

            model.truck_availability_con = Constraint(
                model.trucks,
                model.dates,
                rule=truck_availability_rule,
                doc="Truck availability by day of week"
            )

            # Constraint: Prevent phantom truck loads (departures before planning horizon)
            def no_phantom_truck_loads_rule(model, truck_idx, dest, prod, delivery_date):
                """Prevent truck loads when required departure would be before planning horizon."""
                transit_days = self._get_truck_transit_days(truck_idx, dest)
                departure_date = delivery_date - timedelta(days=transit_days)

                if departure_date < self.start_date:
                    # This truck load would require departure before planning horizon
                    return model.truck_load[truck_idx, dest, prod, delivery_date] == 0
                else:
                    return Constraint.Skip

            model.no_phantom_truck_loads_con = Constraint(
                model.trucks,
                model.truck_destinations,
                model.products,
                model.dates,
                rule=no_phantom_truck_loads_rule,
                doc="Prevent truck loads with departure before planning horizon"
            )

            # Constraint: Link truck loads to route shipments
            # For routes from manufacturing to immediate destinations (first leg),
            # the shipment of each product on those routes must equal truck loads for that product
            def truck_route_linking_rule(model, dest_id, product_id, d):
                """
                Shipments of a specific product from manufacturing to destination on date d
                must equal truck loads of that product to that destination on date d.

                CRITICAL: This constraint must be indexed by (dest, PRODUCT, date) to ensure
                that shipments of each product match truck loads of that same product.
                Without the product dimension, products can be mixed (e.g., shipments of
                product A "satisfied" by truck loads of product B).
                """
                # LEG-BASED ROUTING: Check if leg exists from manufacturing storage to this destination
                # CRITICAL: Use 6122_Storage (not 6122) because inventory flows through virtual storage
                manufacturing_storage_id = '6122_Storage'
                leg_key = (manufacturing_storage_id, dest_id)

                if leg_key not in self.leg_keys:
                    return Constraint.Skip

                # Get trucks that go to this destination
                trucks_to_dest = self.trucks_to_destination.get(dest_id, [])

                if not trucks_to_dest:
                    # No trucks to this destination - leg shipments must be zero
                    return model.shipment_leg[leg_key, product_id, d] == 0

                # Shipment on this leg of THIS PRODUCT = sum of truck loads
                leg_shipment = model.shipment_leg[leg_key, product_id, d]

                total_truck_loads = sum(
                    model.truck_load[t, dest_id, product_id, d]
                    for t in trucks_to_dest
                )

                return leg_shipment == total_truck_loads

            # LEG-BASED ROUTING: Get all destinations that have legs from manufacturing storage
            # Create constraints for ALL leg destinations from 6122_Storage (virtual storage)
            leg_destinations = set()
            for (origin, dest) in self.leg_keys:
                if origin == '6122_Storage':
                    leg_destinations.add(dest)

            model.truck_leg_linking_con = Constraint(
                list(leg_destinations),  # Destinations reachable via legs from manufacturing storage
                model.products,  # CRITICAL: Include product dimension to prevent product mixing
                model.dates,
                rule=truck_route_linking_rule,
                doc="Link truck loads to leg shipments from 6122_Storage (by destination, product, and date)"
            )

            # CRITICAL CONSTRAINT: Force real manufacturing (6122) legs to zero
            # All flow must go through 6122_Storage virtual location for proper truck tracking
            def no_direct_manufacturing_shipments_rule(model, dest_id, product_id, d):
                """Prevent direct shipments from 6122 (all must go via 6122_Storage)."""
                real_manufacturing_id = self.manufacturing_site.id  # "6122"
                leg_key = (real_manufacturing_id, dest_id)

                if leg_key in self.leg_keys:
                    # This real leg exists - force it to zero (use virtual leg instead)
                    return model.shipment_leg[leg_key, product_id, d] == 0
                else:
                    return Constraint.Skip

            model.no_direct_mfg_shipments_con = Constraint(
                list(leg_destinations),
                model.products,
                model.dates,
                rule=no_direct_manufacturing_shipments_rule,
                doc="Force all manufacturing outbound flow through 6122_Storage (prevents bypass of truck constraints)"
            )

            # NEW CONSTRAINT: Truck loading timing (D-1 vs D0)
            # Morning trucks can only load D-1 production (previous day)
            # Afternoon trucks can load D-1 or D0 production (previous day or same day)

            # Build sparse index set of valid (truck_idx, dest, date) tuples
            # Only create constraints for trucks that:
            # 1. Actually serve each destination
            # 2. Actually run on each date (excluding weekends/holidays)
            # Build valid (truck, dest, delivery_date) tuples
            # Convert from departure dates to delivery dates based on transit time
            valid_truck_dest_date_tuples = []
            for departure_date in model.dates:
                # Only consider trucks that run on this date
                for truck_idx in self.trucks_on_date.get(departure_date, []):
                    # Only consider destinations this truck serves
                    truck = self.truck_by_index[truck_idx]

                    # Primary destination
                    if truck.destination_id in model.truck_destinations:
                        transit_days = self._get_truck_transit_days(truck_idx, truck.destination_id)
                        delivery_date = departure_date + timedelta(days=transit_days)

                        # Only include if delivery_date is within planning horizon
                        if delivery_date in model.dates:
                            valid_truck_dest_date_tuples.append((truck_idx, truck.destination_id, delivery_date))

                    # Intermediate stop destinations
                    if truck_idx in self.trucks_with_intermediate_stops:
                        for stop_id in self.trucks_with_intermediate_stops[truck_idx]:
                            if stop_id in model.truck_destinations:
                                transit_days = self._get_truck_transit_days(truck_idx, stop_id)
                                delivery_date = departure_date + timedelta(days=transit_days)

                                # Only include if delivery_date is within planning horizon
                                if delivery_date in model.dates:
                                    valid_truck_dest_date_tuples.append((truck_idx, stop_id, delivery_date))


            def truck_production_timing_rule(model, truck_idx, dest, departure_date, prod):
                """
                Restrict truck loads based on production timing:
                - Morning trucks (8am): Can only load production from (departure_date - 1)
                - Afternoon trucks: Can load production from (departure_date - 1) or departure_date

                This prevents the physically impossible scenario of morning trucks loading
                same-day production that hasn't been produced yet.
                """
                truck = self.truck_by_index[truck_idx]

                # Check if production dates are in range
                d_minus_1 = departure_date - timedelta(days=1)

                # Skip if D-1 is not in production dates (departure_date is first day)
                if d_minus_1 not in model.dates:
                    # Force truck load to zero (can't load nonexistent production)
                    return model.truck_load[truck_idx, dest, prod, departure_date] == 0

                # Morning trucks: Can ONLY use D-1 production
                if truck.departure_type == 'morning':
                    # truck_load <= production from previous day
                    return model.truck_load[truck_idx, dest, prod, departure_date] <= model.production[d_minus_1, prod]

                # Afternoon trucks: Can use D-1 OR D0 production
                else:  # departure_type == 'afternoon'
                    # truck_load <= production from D-1 + production from D0
                    # Both dates are guaranteed to be in model.dates (D0 = departure_date, D-1 checked above)
                    return model.truck_load[truck_idx, dest, prod, departure_date] <= (
                        model.production[d_minus_1, prod] + model.production[departure_date, prod]
                    )

            # D-1/D0 Timing Constraint: Restrict truck loading based on production timing
            # Morning trucks can only load D-1 production (previous day)
            # Afternoon trucks can load D-1 or D0 production (previous or same day)
            #
            # PERFORMANCE OPTIMIZATION: Use aggregated formulation over products
            # This reduces constraints by 5x and breaks dense per-product coupling

            def truck_morning_timing_agg_rule(model, truck_idx, dest, delivery_date):
                """Morning trucks: load on DELIVERY_DATE <= 6122_Storage inventory at D-1 (aggregated over products)."""
                truck = self.truck_by_index[truck_idx]
                if truck.departure_type != 'morning':
                    return Constraint.Skip

                # Calculate departure date from delivery date
                # delivery_date = departure_date + transit_days
                # Therefore: departure_date = delivery_date - transit_days
                transit_days = self._get_truck_transit_days(truck_idx, dest)
                departure_date = delivery_date - timedelta(days=transit_days)

                # Can't depart before planning horizon
                if departure_date not in model.dates:
                    return sum(model.truck_load[truck_idx, dest, p, delivery_date] for p in model.products) == 0

                # Morning trucks load from 6122_Storage inventory at D-1 (relative to departure)
                d_minus_1 = departure_date - timedelta(days=1)

                # Calculate storage inventory available at D-1
                # BUG FIX: Use initial_inventory when d_minus_1 is before planning horizon
                if d_minus_1 not in model.dates:
                    # d_minus_1 is before planning horizon - use initial inventory
                    storage_inventory = sum(
                        self.initial_inventory.get(('6122_Storage', p, 'ambient'),
                                                   self.initial_inventory.get(('6122_Storage', p), 0))
                        for p in model.products
                    )
                else:
                    # d_minus_1 is within planning horizon - use inventory variable
                    storage_inventory = sum(
                        model.inventory_ambient['6122_Storage', p, d_minus_1]
                        if ('6122_Storage', p, d_minus_1) in self.inventory_ambient_index_set else 0
                        for p in model.products
                    )

                return (sum(model.truck_load[truck_idx, dest, p, delivery_date] for p in model.products) <=
                        storage_inventory)

            def truck_afternoon_timing_agg_rule(model, truck_idx, dest, delivery_date):
                """Afternoon trucks: load <= 6122_Storage inventory at D-1 + D0 production (aggregated over products)."""
                truck = self.truck_by_index[truck_idx]
                if truck.departure_type != 'afternoon':
                    return Constraint.Skip

                # Calculate departure date from delivery date
                transit_days = self._get_truck_transit_days(truck_idx, dest)
                departure_date = delivery_date - timedelta(days=transit_days)

                # Can't depart before planning horizon
                if departure_date not in model.dates:
                    return sum(model.truck_load[truck_idx, dest, p, delivery_date] for p in model.products) == 0

                # Afternoon trucks can load from 6122_Storage inventory at D-1 + same-day production
                d_minus_1 = departure_date - timedelta(days=1)

                # Calculate storage inventory available at D-1
                # BUG FIX: Use initial_inventory when d_minus_1 is before planning horizon
                if d_minus_1 not in model.dates:
                    # d_minus_1 is before planning horizon - use initial inventory
                    storage_inventory = sum(
                        self.initial_inventory.get(('6122_Storage', p, 'ambient'),
                                                   self.initial_inventory.get(('6122_Storage', p), 0))
                        for p in model.products
                    )
                else:
                    # d_minus_1 is within planning horizon - use inventory variable
                    storage_inventory = sum(
                        model.inventory_ambient['6122_Storage', p, d_minus_1]
                        if ('6122_Storage', p, d_minus_1) in self.inventory_ambient_index_set else 0
                        for p in model.products
                    )

                same_day_production = sum(model.production[departure_date, p] for p in model.products)

                return (sum(model.truck_load[truck_idx, dest, p, delivery_date] for p in model.products) <=
                        storage_inventory + same_day_production)

            # Create separate constraints for morning and afternoon trucks
            morning_tuples = [(t, d, dt) for (t, d, dt) in valid_truck_dest_date_tuples
                            if self.truck_by_index[t].departure_type == 'morning']
            afternoon_tuples = [(t, d, dt) for (t, d, dt) in valid_truck_dest_date_tuples
                              if self.truck_by_index[t].departure_type == 'afternoon']

            if morning_tuples:
                model.truck_morning_timing_agg_con = Constraint(
                    morning_tuples,
                    rule=truck_morning_timing_agg_rule,
                    doc="Morning trucks load from 6122_Storage inventory at D-1 (aggregated over products)"
                )

            if afternoon_tuples:
                model.truck_afternoon_timing_agg_con = Constraint(
                    afternoon_tuples,
                    rule=truck_afternoon_timing_agg_rule,
                    doc="Afternoon trucks load from 6122_Storage inventory at D-1 + D0 production (aggregated over products)"
                )

        # Objective: Minimize total cost = labor + production + transport + shortage penalty
        def objective_rule(model):
            # Labor cost (same as production model)
            labor_cost = 0.0
            for d in model.dates:
                labor_day = self.labor_by_date.get(d)
                if labor_day:
                    if labor_day.is_fixed_day:
                        # Add defensive checks for None rates
                        regular_rate = labor_day.regular_rate if labor_day.regular_rate is not None else 0.0
                        overtime_rate = labor_day.overtime_rate if labor_day.overtime_rate is not None else 0.0
                        labor_cost += (
                            regular_rate * model.fixed_hours_used[d]
                            + overtime_rate * model.overtime_hours_used[d]
                        )
                    else:
                        # Non-fixed day (weekend/holiday) - rate must be specified
                        if labor_day.non_fixed_rate is None:
                            raise ValueError(
                                f"Non-fixed labor rate is None for {d}. "
                                f"Weekend/holiday rates must be specified in labor calendar."
                            )
                        rate = labor_day.non_fixed_rate
                        labor_cost += rate * model.non_fixed_hours_paid[d]

            # Production cost
            production_cost = 0.0
            prod_cost_per_unit = self.cost_structure.production_cost_per_unit
            # Defensive check for None or infinity
            if prod_cost_per_unit is None or not math.isfinite(prod_cost_per_unit):
                prod_cost_per_unit = 0.0
            for d in model.dates:
                for p in model.products:
                    production_cost += prod_cost_per_unit * model.production[d, p]

            # LEG-BASED ROUTING: Transport cost (sum of leg costs)
            transport_cost = 0.0
            for (origin, dest) in model.legs:
                leg_cost_value = self.leg_cost.get((origin, dest), 0.0)
                # Defensive check for None or infinity
                if leg_cost_value is None or not math.isfinite(leg_cost_value):
                    leg_cost_value = 0.0
                for p in model.products:
                    for d in model.dates:
                        transport_cost += leg_cost_value * model.shipment_leg[(origin, dest), p, d]

            # STATE TRACKING: INVENTORY HOLDING COST (state-specific rates)
            # Frozen storage typically more expensive than ambient
            # Cost incentivizes JIT delivery while allowing strategic buffering
            inventory_cost = 0.0

            # Get holding cost rates (with defensive checks)
            frozen_holding_rate = self.cost_structure.storage_cost_frozen_per_unit_day
            if frozen_holding_rate is None or not math.isfinite(frozen_holding_rate):
                frozen_holding_rate = 0.0

            ambient_holding_rate = self.cost_structure.storage_cost_ambient_per_unit_day
            if ambient_holding_rate is None or not math.isfinite(ambient_holding_rate):
                ambient_holding_rate = 0.0

            # Sum frozen inventory costs
            for loc, prod, date in model.inventory_frozen_index:
                inventory_cost += frozen_holding_rate * model.inventory_frozen[loc, prod, date]

            # Sum ambient inventory costs
            for loc, prod, date in model.inventory_ambient_index:
                inventory_cost += ambient_holding_rate * model.inventory_ambient[loc, prod, date]

            # Freeze/thaw operation costs (if batch tracking enabled)
            freeze_thaw_cost = 0.0
            if self.use_batch_tracking:
                # Get freeze/thaw cost rates from cost structure (with defaults)
                freeze_cost_rate = getattr(self.cost_structure, 'freeze_cost_per_unit', 0.05)
                if freeze_cost_rate is None or not math.isfinite(freeze_cost_rate):
                    freeze_cost_rate = 0.05  # Default: $0.05 per unit

                thaw_cost_rate = getattr(self.cost_structure, 'thaw_cost_per_unit', 0.05)
                if thaw_cost_rate is None or not math.isfinite(thaw_cost_rate):
                    thaw_cost_rate = 0.05  # Default: $0.05 per unit

                # Sum freeze operation costs
                for loc, prod, prod_date, curr_date in model.cohort_freeze_thaw_index:
                    freeze_thaw_cost += freeze_cost_rate * model.freeze[loc, prod, prod_date, curr_date]
                    freeze_thaw_cost += thaw_cost_rate * model.thaw[loc, prod, prod_date, curr_date]

            # Shortage penalty cost (if shortages allowed)
            shortage_cost = 0.0
            if self.allow_shortages:
                penalty = self.cost_structure.shortage_penalty_per_unit
                # Defensive check: if penalty is None or infinity, use large finite number
                if penalty is None or not math.isfinite(penalty):
                    penalty = 1e6  # Large but finite penalty to discourage shortages
                for dest, prod, delivery_date in self.demand.keys():
                    shortage_cost += penalty * model.shortage[dest, prod, delivery_date]

            # Truck fixed costs (if truck schedules provided)
            truck_cost = 0.0
            if self.truck_schedules:
                for truck_idx in model.trucks:
                    truck = self.truck_by_index[truck_idx]
                    # Defensive checks for truck costs
                    fixed_cost = truck.cost_fixed if truck.cost_fixed is not None else 0.0
                    var_cost = truck.cost_per_unit if truck.cost_per_unit is not None else 0.0

                    for d in model.dates:
                        # Fixed cost if truck is used
                        truck_cost += fixed_cost * model.truck_used[truck_idx, d]
                        # Variable cost per unit (sum across all destinations)
                        for dest in model.truck_destinations:
                            for p in model.products:
                                truck_cost += var_cost * model.truck_load[truck_idx, dest, p, d]

            # BATCH TRACKING: FIFO penalty cost (soft constraint)
            # DISABLED: This penalty creates a perverse incentive that concentrates production
            #
            # PROBLEM: The formula `freshness_penalty = remaining_shelf_life * fifo_penalty_weight`
            # penalizes inventory age DIVERSITY rather than old inventory itself.
            # Result: Optimizer concentrates ALL production on ONE day to minimize age diversity.
            #
            # SOLUTION: Production smoothing constraint added below (around line 1437+) provides
            # more direct control over production concentration without distorting FIFO behavior.
            #
            # Original code kept for reference:
            # fifo_penalty_cost = 0.0
            # if self.use_batch_tracking:
            #     fifo_penalty_weight = 0.01  # $0.01 per unit per day younger
            #     for loc, prod, prod_date, curr_date in model.cohort_demand_index:
            #         age_days = (curr_date - prod_date).days
            #         shelf_life = self.THAWED_SHELF_LIFE if loc == '6130' else self.AMBIENT_SHELF_LIFE
            #         remaining_shelf_life = shelf_life - age_days
            #         freshness_penalty = remaining_shelf_life * fifo_penalty_weight
            #         fifo_penalty_cost += freshness_penalty * model.demand_from_cohort[loc, prod, prod_date, curr_date]

            fifo_penalty_cost = 0.0  # Disabled - see comment above

            # Total cost = labor + production + transport + inventory + freeze/thaw + truck + shortage
            # Note: fifo_penalty_cost removed from objective (now always 0)
            return labor_cost + production_cost + transport_cost + inventory_cost + freeze_thaw_cost + truck_cost + shortage_cost + fifo_penalty_cost

        model.obj = Objective(
            rule=objective_rule,
            sense=minimize,
            doc="Minimize total cost (labor + production + transport + inventory + freeze/thaw + truck + shortage penalty)"
        )

        # BATCH TRACKING: Validate cohort model if enabled
        if self.use_batch_tracking:
            self._validate_cohort_model(model)

        return model

    def _validate_cohort_model(self, model: ConcreteModel) -> None:
        """
        Validate cohort model structure before solving.

        Checks:
        1. Cohort variable count is reasonable (not too large)
        2. All production flows into cohorts
        3. Demand allocation variables exist for all demand
        4. Mass balance constraints are correctly formulated

        Raises:
            ValueError: If validation fails
        """
        print("\nValidating cohort model structure...")

        # Check 1: Sparse indexing size is reasonable
        cohort_vars = (
            len(model.cohort_frozen_index) +
            len(model.cohort_ambient_index) +
            len(model.cohort_shipment_index) +
            len(model.cohort_demand_index)
        )
        total_vars = sum(1 for _ in model.component_map(Var))
        print(f"  Cohort variables: {cohort_vars:,} / {total_vars:,} total ({cohort_vars/total_vars*100:.1f}%)")

        if cohort_vars > 100000:
            warnings.warn(
                f"Cohort model is large: {cohort_vars:,} cohort variables. "
                f"Solve time may be slow. Consider reducing planning horizon."
            )

        # Check 2: All production flows into cohorts
        for date in model.dates:
            for prod in model.products:
                # Must have corresponding 6122_Storage cohort for production on this date
                if ('6122_Storage', prod, date, date) not in self.cohort_ambient_index_set:
                    raise ValueError(
                        f"Missing cohort for production[{date}, {prod}]. "
                        f"Production must flow into 6122_Storage ambient cohort."
                    )

        # Check 3: Demand allocation variables exist for all demand
        missing_demand_cohorts = []
        for (loc, prod, date) in self.demand.keys():
            cohorts_available = [
                (loc, prod, pd, date)
                for pd in model.dates if pd <= date
                if (loc, prod, pd, date) in self.cohort_demand_index_set
            ]
            if not cohorts_available and not self.allow_shortages:
                missing_demand_cohorts.append((loc, prod, date))

        if missing_demand_cohorts:
            raise ValueError(
                f"No cohorts available for {len(missing_demand_cohorts)} demand points. "
                f"First 3: {missing_demand_cohorts[:3]}. "
                f"Enable allow_shortages=True or extend planning horizon."
            )

        # Check 4: Verify cohort aggregation makes sense
        # For each leg shipment, there should be corresponding cohort shipments
        sample_legs = list(model.legs)[:3]  # Check first 3 legs
        for leg in sample_legs:
            for prod in list(model.products)[:2]:  # Check first 2 products
                for date in list(model.dates)[:2]:  # Check first 2 dates
                    # Count how many cohorts feed this leg shipment
                    cohort_count = sum(
                        1 for pd in model.dates
                        if (leg, prod, pd, date) in self.cohort_shipment_index_set
                    )
                    if cohort_count == 0:
                        # This is OK if the leg/date combination is infeasible
                        # (e.g., departure before planning horizon)
                        pass

        print("  ✓ Cohort model validation passed")

    def extract_solution(self, model: ConcreteModel) -> Dict[str, Any]:
        """
        Extract solution from solved model.

        Args:
            model: Solved Pyomo model

        Returns:
            Dictionary with production schedule, shipments, and costs
        """
        # Extract production quantities
        production_by_date_product: Dict[Tuple[Date, str], float] = {}
        for d in model.dates:
            for p in model.products:
                qty = value(model.production[d, p])
                if qty > 1e-6:  # Only include non-zero production
                    production_by_date_product[(d, p)] = qty

        # Extract labor hours
        labor_hours_by_date: Dict[Date, float] = {}
        for d in model.dates:
            hours = value(model.labor_hours[d])
            if hours > 1e-6:
                labor_hours_by_date[d] = hours

        # LEG-BASED ROUTING: Extract shipment decisions by leg
        shipments_by_leg_product_date: Dict[Tuple[Tuple[str, str], str, Date], float] = {}
        for (origin, dest) in model.legs:
            for p in model.products:
                for d in model.dates:
                    var = model.shipment_leg[(origin, dest), p, d]
                    # Only extract if variable has a value (is initialized)
                    if var.value is not None:
                        qty = value(var)
                        if qty > 1e-6:  # Only include non-zero shipments
                            shipments_by_leg_product_date[((origin, dest), p, d)] = qty

        # LEGACY: Keep route-based shipments for backward compatibility (DEPRECATED)
        shipments_by_route_product_date: Dict[Tuple[int, str, Date], float] = {}
        # Note: This will be empty in leg-based routing, included for backward compatibility

        # Calculate costs
        total_labor_cost = 0.0
        labor_cost_by_date: Dict[Date, float] = {}
        for d in model.dates:
            labor_day = self.labor_by_date.get(d)
            if labor_day:
                if labor_day.is_fixed_day:
                    fixed_cost = labor_day.regular_rate * value(model.fixed_hours_used[d])
                    overtime_cost = labor_day.overtime_rate * value(model.overtime_hours_used[d])
                    day_cost = fixed_cost + overtime_cost
                else:
                    # Non-fixed day - rate must be specified
                    if labor_day.non_fixed_rate is None:
                        raise ValueError(
                            f"Non-fixed labor rate is None for {d}. "
                            f"Weekend/holiday rates must be specified in labor calendar."
                        )
                    rate = labor_day.non_fixed_rate
                    day_cost = rate * value(model.non_fixed_hours_paid[d])

                if day_cost > 1e-6:
                    labor_cost_by_date[d] = day_cost
                    total_labor_cost += day_cost

        total_production_cost = 0.0
        for d in model.dates:
            for p in model.products:
                qty = value(model.production[d, p])
                total_production_cost += self.cost_structure.production_cost_per_unit * qty

        # LEG-BASED ROUTING: Calculate transport cost (sum of leg costs)
        total_transport_cost = 0.0
        for (origin, dest) in model.legs:
            leg_cost_value = self.leg_cost[(origin, dest)]
            for p in model.products:
                for d in model.dates:
                    qty = value(model.shipment_leg[(origin, dest), p, d])
                    total_transport_cost += leg_cost_value * qty

        # Extract shortage quantities (if shortages allowed)
        shortages_by_dest_product_date: Dict[Tuple[str, str, Date], float] = {}
        total_shortage_cost = 0.0
        total_shortage_units = 0.0
        if self.allow_shortages:
            for dest, prod, delivery_date in self.demand.keys():
                qty = value(model.shortage[dest, prod, delivery_date])
                if qty > 1e-6:
                    shortages_by_dest_product_date[(dest, prod, delivery_date)] = qty
                    total_shortage_units += qty
                    total_shortage_cost += self.cost_structure.shortage_penalty_per_unit * qty

        # STATE TRACKING: Extract state-specific inventory levels
        inventory_frozen_by_loc_product_date: Dict[Tuple[str, str, Date], float] = {}
        inventory_ambient_by_loc_product_date: Dict[Tuple[str, str, Date], float] = {}
        total_inventory_cost = 0.0

        # Get holding cost rates
        frozen_holding_rate = self.cost_structure.storage_cost_frozen_per_unit_day or 0.0
        ambient_holding_rate = self.cost_structure.storage_cost_ambient_per_unit_day or 0.0

        # Extract frozen inventory
        for loc, prod, date in model.inventory_frozen_index:
            qty = value(model.inventory_frozen[loc, prod, date])
            if qty > 1e-6:  # Only include non-zero inventory
                inventory_frozen_by_loc_product_date[(loc, prod, date)] = qty
                total_inventory_cost += frozen_holding_rate * qty

        # Extract ambient inventory
        for loc, prod, date in model.inventory_ambient_index:
            qty = value(model.inventory_ambient[loc, prod, date])
            if qty > 1e-6:  # Only include non-zero inventory
                inventory_ambient_by_loc_product_date[(loc, prod, date)] = qty
                total_inventory_cost += ambient_holding_rate * qty

        # Extract truck assignment data (if truck schedules provided)
        truck_used_by_date: Dict[Tuple[int, Date], bool] = {}
        truck_loads_by_truck_dest_product_date: Dict[Tuple[int, str, str, Date], float] = {}
        total_truck_cost = 0.0
        if self.truck_schedules:
            for truck_idx in model.trucks:
                truck = self.truck_by_index[truck_idx]
                for d in model.dates:
                    # Extract truck usage
                    used = value(model.truck_used[truck_idx, d])
                    if used > 0.5:  # Binary variable, use 0.5 threshold
                        truck_used_by_date[(truck_idx, d)] = True
                        total_truck_cost += truck.cost_fixed

                    # Extract truck loads (now includes destination)
                    for dest in model.truck_destinations:
                        for p in model.products:
                            load = value(model.truck_load[truck_idx, dest, p, d])
                            if load > 1e-6:
                                truck_loads_by_truck_dest_product_date[(truck_idx, dest, p, d)] = load
                                total_truck_cost += truck.cost_per_unit * load


        # BATCH TRACKING: Extract cohort inventory (if enabled)
        # This provides batch-level detail for inventory at each location
        cohort_inventory_frozen: Dict[Tuple[str, str, Date, Date, str], float] = {}
        cohort_inventory_ambient: Dict[Tuple[str, str, Date, Date, str], float] = {}
        cohort_demand_consumption: Dict[Tuple[str, str, Date, Date], float] = {}

        if self.use_batch_tracking:
            # Extract frozen cohort inventory
            # Index: (location, product, production_date, current_date, state)
            if hasattr(model, 'inventory_frozen_cohort'):
                for (loc, prod, prod_date, curr_date) in model.cohort_frozen_index:
                    qty = value(model.inventory_frozen_cohort[loc, prod, prod_date, curr_date])
                    if qty > 1e-6:  # Only non-zero inventory
                        cohort_inventory_frozen[(loc, prod, prod_date, curr_date, 'frozen')] = qty

            # Extract ambient cohort inventory
            # Index: (location, product, production_date, current_date, state)
            if hasattr(model, 'inventory_ambient_cohort'):
                for (loc, prod, prod_date, curr_date) in model.cohort_ambient_index:
                    qty = value(model.inventory_ambient_cohort[loc, prod, prod_date, curr_date])
                    if qty > 1e-6:  # Only non-zero inventory
                        cohort_inventory_ambient[(loc, prod, prod_date, curr_date, 'ambient')] = qty

            # Extract demand consumption by cohort (which batches satisfied demand)
            if hasattr(model, 'demand_from_cohort'):
                for (loc, prod, prod_date, demand_date) in model.cohort_demand_index:
                    qty = value(model.demand_from_cohort[loc, prod, prod_date, demand_date])
                    if qty > 1e-6:
                        cohort_demand_consumption[(loc, prod, prod_date, demand_date)] = qty

        # BATCH TRACKING: Create ProductionBatch objects with full traceability
        # Build batch ID map for linking shipments to batches
        batch_id_map: Dict[Tuple[Date, str], str] = {}
        production_batch_objects: List[ProductionBatch] = []
        batch_id_counter = 1
        
        for (prod_date, product_id), quantity in production_by_date_product.items():
            # Generate unique, deterministic batch ID
            batch_id = f"BATCH-{prod_date.strftime('%Y%m%d')}-{product_id}-{batch_id_counter:04d}"
            batch_id_map[(prod_date, product_id)] = batch_id
            
            # Pro-rate labor hours across products produced on same day
            labor_hours = labor_hours_by_date.get(prod_date, 0.0)
            production_on_date = [
                qty for (d, p), qty in production_by_date_product.items()
                if d == prod_date
            ]
            num_products = len(production_on_date)
            labor_hours_allocated = labor_hours / num_products if num_products > 0 else 0.0
            
            # Calculate production cost
            production_cost = quantity * self.cost_structure.production_cost_per_unit
            
            # Create ProductionBatch object
            from src.models.product import ProductState
            batch = ProductionBatch(
                id=batch_id,
                product_id=product_id,
                manufacturing_site_id=self.manufacturing_site.location_id,
                production_date=prod_date,
                quantity=quantity,
                initial_state=ProductState.AMBIENT,  # Always starts ambient
                labor_hours_used=labor_hours_allocated,
                production_cost=production_cost
            )
            
            production_batch_objects.append(batch)
            batch_id_counter += 1
        
        # Convert production_batches to dict format for backward compatibility
        # This format is expected by some UI components
        production_batches = []
        for (prod_date, product_id), quantity in production_by_date_product.items():
            production_batches.append({
                'date': prod_date,
                'product': product_id,
                'quantity': quantity,
            })
        
        # BATCH TRACKING: Extract batch-linked shipments (if cohort tracking enabled)
        batch_shipments: List[Shipment] = []
        shipment_id_counter = 1
        
        if self.use_batch_tracking and hasattr(model, 'shipment_leg_cohort'):
            # Extract cohort shipments (batch-aware)
            from src.shelf_life.tracker import RouteLeg
            from src.network.route_finder import RoutePath
            
            for (leg, product_id, prod_date, delivery_date) in model.cohort_shipment_index:
                qty = value(model.shipment_leg_cohort[leg, product_id, prod_date, delivery_date])
                
                if qty > 0.01:  # Significant shipment
                    origin, dest = leg
                    
                    # Find corresponding batch
                    batch_id = batch_id_map.get((prod_date, product_id))
                    if not batch_id:
                        # Shouldn't happen - fallback to unknown
                        batch_id = f"BATCH-UNKNOWN-{prod_date.strftime('%Y%m%d')}-{product_id}"
                    
                    # Generate shipment ID (deterministic)
                    shipment_id = f"SHIP-{delivery_date.strftime('%Y%m%d')}-{origin}-{dest}-{shipment_id_counter:05d}"
                    
                    # Create single-leg route
                    transit_days = self.leg_transit_days.get(leg, 0)
                    leg_obj = RouteLeg(
                        from_location_id=origin,
                        to_location_id=dest,
                        transport_mode='ambient',  # Simplified - could track frozen/ambient
                        transit_days=transit_days
                    )
                    single_leg_route = RoutePath(
                        path=[origin, dest],
                        total_transit_days=transit_days,
                        total_cost=0.0,
                        transport_modes=['ambient'],
                        route_legs=[leg_obj],
                        intermediate_stops=[]
                    )
                    
                    # Create shipment with batch linkage
                    shipment = Shipment(
                        id=shipment_id,
                        batch_id=batch_id,
                        product_id=product_id,
                        quantity=qty,
                        origin_id=origin,
                        destination_id=dest,
                        delivery_date=delivery_date,
                        route=single_leg_route,
                        production_date=prod_date  # Key: links to batch
                    )
                    
                    batch_shipments.append(shipment)
                    shipment_id_counter += 1

        # FREEZE/THAW: Extract freeze and thaw operations (if batch tracking enabled)
        freeze_operations: Dict[Tuple[str, str, Date, Date], float] = {}
        thaw_operations: Dict[Tuple[str, str, Date, Date], float] = {}
        total_freeze_cost = 0.0
        total_thaw_cost = 0.0

        if self.use_batch_tracking and hasattr(model, 'freeze') and hasattr(model, 'thaw'):
            # Get freeze/thaw costs
            freeze_cost_rate = self.cost_structure.freeze_cost_per_unit if hasattr(self.cost_structure, 'freeze_cost_per_unit') else 0.05
            thaw_cost_rate = self.cost_structure.thaw_cost_per_unit if hasattr(self.cost_structure, 'thaw_cost_per_unit') else 0.05

            # Extract freeze operations
            for (loc, prod, prod_date, curr_date) in model.cohort_freeze_thaw_index:
                freeze_qty = value(model.freeze[loc, prod, prod_date, curr_date])
                if freeze_qty > 1e-6:
                    freeze_operations[(loc, prod, prod_date, curr_date)] = freeze_qty
                    total_freeze_cost += freeze_cost_rate * freeze_qty

                # Extract thaw operations
                thaw_qty = value(model.thaw[loc, prod, prod_date, curr_date])
                if thaw_qty > 1e-6:
                    thaw_operations[(loc, prod, prod_date, curr_date)] = thaw_qty
                    total_thaw_cost += thaw_cost_rate * thaw_qty

        return {
            'production_by_date_product': production_by_date_product,
            'production_batches': production_batches,  # Dict format for backward compatibility
            'production_batch_objects': production_batch_objects,  # NEW: ProductionBatch objects
            'batch_id_map': batch_id_map,  # NEW: Mapping for batch lookups
            'batch_shipments': batch_shipments if self.use_batch_tracking else [],  # NEW: Batch-linked shipments
            'labor_hours_by_date': labor_hours_by_date,
            'labor_cost_by_date': labor_cost_by_date,
            'shipments_by_route_product_date': shipments_by_route_product_date,  # DEPRECATED - kept for backward compatibility
            'shipments_by_leg_product_date': shipments_by_leg_product_date,  # LEG-BASED ROUTING
            'shortages_by_dest_product_date': shortages_by_dest_product_date,
            # STATE TRACKING: State-specific inventory data
            'inventory_frozen_by_loc_product_date': inventory_frozen_by_loc_product_date,
            'inventory_ambient_by_loc_product_date': inventory_ambient_by_loc_product_date,
            # Backward compatibility: combined inventory (for existing UI code)
            'inventory_by_dest_product_date': {
                **{k: v for k, v in inventory_frozen_by_loc_product_date.items()},
                **{k: v for k, v in inventory_ambient_by_loc_product_date.items()}
            },
            'truck_used_by_date': truck_used_by_date if self.truck_schedules else {},
            # BATCH TRACKING: Cohort-level inventory data
            'use_batch_tracking': self.use_batch_tracking,
            'cohort_inventory_frozen': cohort_inventory_frozen if self.use_batch_tracking else {},
            'cohort_inventory_ambient': cohort_inventory_ambient if self.use_batch_tracking else {},
            'cohort_demand_consumption': cohort_demand_consumption if self.use_batch_tracking else {},
            # Combined cohort inventory for backward compatibility
            'cohort_inventory': {**cohort_inventory_frozen, **cohort_inventory_ambient} if self.use_batch_tracking else {},
            # FREEZE/THAW: State transition operations
            'freeze_operations': freeze_operations if self.use_batch_tracking else {},
            'thaw_operations': thaw_operations if self.use_batch_tracking else {},
            'total_freeze_cost': total_freeze_cost,
            'total_thaw_cost': total_thaw_cost,
            'truck_loads_by_truck_dest_product_date': truck_loads_by_truck_dest_product_date if self.truck_schedules else {},
            'total_labor_cost': total_labor_cost,
            'total_production_cost': total_production_cost,
            'total_transport_cost': total_transport_cost,
            'total_inventory_cost': total_inventory_cost,
            'total_truck_cost': total_truck_cost,
            'total_shortage_cost': total_shortage_cost,
            'total_shortage_units': total_shortage_units,
            'total_cost': total_labor_cost + total_production_cost + total_transport_cost + total_inventory_cost + total_truck_cost + total_shortage_cost + total_freeze_cost + total_thaw_cost,  # Updated
        }


    def get_shipment_plan(self) -> Optional[List[Shipment]]:
        """
        Convert optimization solution to list of Shipment objects.

        Returns:
            List of Shipment objects (one per leg), or None if not solved

        Example:
            model = IntegratedProductionDistributionModel(...)
            result = model.solve()
            if result.is_optimal():
                shipments = model.get_shipment_plan()
                print(f"Total shipments: {len(shipments)}")
        """
        if not self.solution:
            return None

        # LEG-BASED ROUTING: Use leg shipments instead of deprecated route shipments
        shipments_by_leg_product_date = self.solution['shipments_by_leg_product_date']

        # Create production batches first (needed for shipment.batch_id)
        production_by_date_product = self.solution['production_by_date_product']
        batch_id_map: Dict[Tuple[Date, str], str] = {}
        batch_id_counter = 1

        for (prod_date, product_id), quantity in production_by_date_product.items():
            batch_id = f"BATCH-{batch_id_counter:04d}"
            batch_id_map[(prod_date, product_id)] = batch_id
            batch_id_counter += 1

        # Create shipments from legs
        # Each leg represents a shipment segment (e.g., 6122→6125, then 6125→6123)
        shipments: List[Shipment] = []
        shipment_id_counter = 1

        for ((origin_id, dest_id), product_id, arrival_date), quantity in shipments_by_leg_product_date.items():
            # Calculate departure date for this leg
            transit_days = self.leg_transit_days.get((origin_id, dest_id), 0)
            departure_date = arrival_date - timedelta(days=transit_days)

            # Find matching production batch (for shipments from manufacturing)
            batch_id = batch_id_map.get((departure_date, product_id))
            if not batch_id:
                # Not from manufacturing or no exact match - use generic batch ID
                batch_id = f"BATCH-UNKNOWN"

            # Create single-leg route for this shipment
            # Use RoutePath with RouteLeg for proper shipment model compatibility
            from src.shelf_life.tracker import RouteLeg
            from src.network.route_finder import RoutePath

            leg = RouteLeg(
                from_location_id=origin_id,
                to_location_id=dest_id,
                transport_mode='ambient',  # Simplified - actual mode tracking could be added
                transit_days=transit_days
            )
            single_leg_route = RoutePath(
                path=[origin_id, dest_id],
                total_transit_days=transit_days,
                total_cost=0.0,  # Cost tracking could be added if needed
                transport_modes=['ambient'],
                route_legs=[leg],
                intermediate_stops=[]
            )

            # Create shipment
            shipment = Shipment(
                id=f"SHIP-{shipment_id_counter:04d}",
                batch_id=batch_id,
                product_id=product_id,
                quantity=quantity,
                origin_id=origin_id,
                destination_id=dest_id,
                delivery_date=arrival_date,
                route=single_leg_route,
                production_date=departure_date,  # Track when goods departed this leg
            )
            shipments.append(shipment)
            shipment_id_counter += 1

        # Map truck assignments to shipments
        # Only shipments from manufacturing can be assigned to trucks
        truck_loads = self.solution.get('truck_loads_by_truck_dest_product_date', {})
        if truck_loads and self.truck_schedules:
            for shipment in shipments:
                # Only assign trucks for shipments originating from manufacturing
                if shipment.origin_id == self.manufacturing_site.location_id:
                    # The immediate destination is the shipment's destination
                    immediate_destination = shipment.destination_id

                    # Match on leg arrival date (which is shipment.delivery_date)
                    matching_date = shipment.delivery_date

                    for (truck_idx, dest, prod, date), quantity in truck_loads.items():
                        if (dest == immediate_destination and
                            prod == shipment.product_id and
                            date == matching_date):
                            # Found matching truck - assign it
                            truck = self.truck_by_index[truck_idx]
                            shipment.assigned_truck_id = truck.id
                            break

        return shipments

    def print_solution_summary(self) -> None:
        """
        Print summary of optimization solution.

        Example:
            model = IntegratedProductionDistributionModel(...)
            model.solve()
            model.print_solution_summary()
        """
        if not self.solution:
            print("No solution available. Model not solved or infeasible.")
            return

        print("=" * 70)
        print("Integrated Production-Distribution Solution")
        print("=" * 70)

        solution = self.solution

        print(f"\nPlanning Horizon: {self.start_date} to {self.end_date}")
        print(f"Products: {len(self.products)}")
        print(f"Destinations: {len(self.destinations)}")
        print(f"Routes Enumerated: {len(self.enumerated_routes)}")
        print(f"Production Days: {len([d for d, h in solution['labor_hours_by_date'].items() if h > 0])}")

        print(f"\nTotal Costs:")
        print(f"  Labor Cost:      ${solution['total_labor_cost']:>12,.2f}")
        print(f"  Production Cost: ${solution['total_production_cost']:>12,.2f}")
        print(f"  Transport Cost:  ${solution['total_transport_cost']:>12,.2f}")
        if solution.get('total_inventory_cost', 0) > 0:
            print(f"  Inventory Cost:  ${solution['total_inventory_cost']:>12,.2f}")
        if self.truck_schedules and solution.get('total_truck_cost', 0) > 0:
            print(f"  Truck Cost:      ${solution['total_truck_cost']:>12,.2f}")
        if self.allow_shortages and solution.get('total_shortage_cost', 0) > 0:
            print(f"  Shortage Cost:   ${solution['total_shortage_cost']:>12,.2f}")
        print(f"  {'─' * 30}")
        print(f"  Total Cost:      ${solution['total_cost']:>12,.2f}")

        # Production summary
        total_units = sum(solution['production_by_date_product'].values())
        print(f"\nProduction Summary:")
        print(f"  Total Units: {total_units:,.0f}")

        # By product
        by_product: Dict[str, float] = defaultdict(float)
        for (_, product_id), qty in solution['production_by_date_product'].items():
            by_product[product_id] += qty

        print(f"\n  By Product:")
        for product_id, qty in sorted(by_product.items()):
            print(f"    {product_id}: {qty:,.0f} units")

        # Shipment summary
        total_shipments = len([k for k, v in solution['shipments_by_route_product_date'].items() if v > 0])
        total_shipped = sum(solution['shipments_by_route_product_date'].values())
        print(f"\nShipment Summary:")
        print(f"  Total Shipments: {total_shipments}")
        print(f"  Total Units Shipped: {total_shipped:,.0f}")

        # Demand satisfaction
        print(f"\nDemand Satisfaction:")

        # Calculate shortage by product if applicable
        shortage_by_product: Dict[str, float] = defaultdict(float)
        if self.allow_shortages:
            for (_, product_id, _), qty in solution.get('shortages_by_dest_product_date', {}).items():
                shortage_by_product[product_id] += qty

        for product_id, demand in self.total_demand_by_product.items():
            produced = by_product.get(product_id, 0.0)
            shortage = shortage_by_product.get(product_id, 0.0)
            satisfied = produced - shortage
            pct = (satisfied / demand * 100) if demand > 0 else 0
            status = "✓" if satisfied >= demand * 0.999 else "✗"
            if shortage > 0.1:
                print(f"  {status} {product_id}: {satisfied:,.0f} / {demand:,.0f} ({pct:.1f}%) [shortage: {shortage:,.0f}]")
            else:
                print(f"  {status} {product_id}: {satisfied:,.0f} / {demand:,.0f} ({pct:.1f}%)")

        # Truck utilization summary (if truck schedules provided)
        if self.truck_schedules:
            truck_used = solution.get('truck_used_by_date', {})
            truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})

            if truck_used:
                print(f"\nTruck Utilization:")
                trucks_used_count = len(truck_used)
                print(f"  Trucks Used: {trucks_used_count}")

                # Calculate average load per truck
                # truck_loads is now Dict[(truck_idx, dest, product, date), qty]
                total_loaded = sum(truck_loads.values())
                avg_load = total_loaded / trucks_used_count if trucks_used_count > 0 else 0
                print(f"  Total Units Shipped: {total_loaded:,.0f}")
                print(f"  Average Load per Truck: {avg_load:,.0f} units")

                # Show Wednesday Lineage routing if applicable
                wednesday_loads = {}
                for (truck_idx, dest, prod, date), qty in truck_loads.items():
                    if date.weekday() == 2:  # Wednesday
                        truck = self.truck_by_index.get(truck_idx)
                        if truck and truck_idx in self.wednesday_lineage_trucks:
                            if truck_idx not in wednesday_loads:
                                wednesday_loads[truck_idx] = {'Lineage': 0, '6125': 0}
                            wednesday_loads[truck_idx][dest] = wednesday_loads[truck_idx].get(dest, 0) + qty

                if wednesday_loads:
                    print(f"\n  Wednesday Lineage Split:")
                    for truck_idx, loads in wednesday_loads.items():
                        truck = self.truck_by_index[truck_idx]
                        lineage_load = loads.get('Lineage', 0)
                        hub_load = loads.get('6125', 0)
                        total = lineage_load + hub_load
                        print(f"    {truck.truck_name}: Lineage={lineage_load:,.0f}, 6125={hub_load:,.0f}, Total={total:,.0f}")

        print("=" * 70)

    def get_demand_diagnostics(self) -> Dict[str, Any]:
        """
        Analyze demand satisfaction and identify issues.

        Returns:
            Dictionary with diagnostic information:
            - satisfied_demand: List of satisfied demands
            - unsatisfied_demand: List of unsatisfied demands with reasons
            - total_satisfied: Total units satisfied
            - total_demand: Total units demanded
            - satisfaction_rate: Percentage satisfied
        """
        if not self.solution:
            return {"error": "Model not solved"}

        shipments_by_route_product_date = self.solution['shipments_by_route_product_date']

        satisfied = []
        unsatisfied = []
        total_satisfied_qty = 0
        total_demand_qty = 0

        for (dest, prod, deliv_date), demand_qty in self.demand.items():
            total_demand_qty += demand_qty

            # Calculate total shipments arriving at this destination-product-date
            route_list = self.routes_to_destination.get(dest, [])
            total_arriving = sum(
                shipments_by_route_product_date.get((r, prod, deliv_date), 0.0)
                for r in route_list
            )

            if total_arriving >= demand_qty * 0.999:  # Satisfied
                satisfied.append({
                    'location': dest,
                    'product': prod,
                    'date': deliv_date,
                    'demand': demand_qty,
                    'delivered': total_arriving,
                })
                total_satisfied_qty += demand_qty
            else:  # Unsatisfied
                # Diagnose why
                reasons = []

                # Check if any routes exist
                if not route_list:
                    reasons.append("No routes to destination")
                else:
                    # Check transit time requirements
                    earliest_feasible_depart = None
                    for route_idx in route_list:
                        route = self.route_enumerator.get_route(route_idx)
                        required_depart = deliv_date - timedelta(days=route.total_transit_days)

                        if required_depart < self.start_date:
                            if earliest_feasible_depart is None or required_depart > earliest_feasible_depart:
                                earliest_feasible_depart = required_depart

                    if earliest_feasible_depart:
                        days_short = (self.start_date - earliest_feasible_depart).days
                        reasons.append(
                            f"Planning horizon starts too late. Need to start production {days_short} days earlier "
                            f"(start date {self.start_date} → {earliest_feasible_depart})"
                        )

                    # Check production capacity constraints
                    # Check if daily capacity was exceeded on required production days
                    for route_idx in route_list:
                        route = self.route_enumerator.get_route(route_idx)
                        required_depart = deliv_date - timedelta(days=route.total_transit_days)

                        if required_depart >= self.start_date and required_depart <= self.end_date:
                            # This route timing is within planning horizon
                            # Check if we have labor on that day
                            labor_day = self.labor_by_date.get(required_depart)
                            if not labor_day:
                                reasons.append(
                                    f"No labor available on required production date {required_depart}"
                                )
                            # Note: Can't easily check if capacity was exceeded without model variables
                            # That would require summing production across all products on that day

                    # Check shelf life violations (if enforced)
                    if self.enforce_shelf_life:
                        # Check if all routes were filtered due to shelf life
                        all_routes_before_filter = [
                            r for r in self.route_enumerator.get_all_routes()
                            if r.destination_id == dest
                        ]
                        if len(all_routes_before_filter) > 0 and len(route_list) == 0:
                            min_transit = min(r.total_transit_days for r in all_routes_before_filter)
                            reasons.append(
                                f"All routes exceed shelf life limit "
                                f"(minimum transit {min_transit}d > {self.max_product_age_days}d max)"
                            )

                unsatisfied.append({
                    'location': dest,
                    'product': prod,
                    'date': deliv_date,
                    'demand': demand_qty,
                    'delivered': total_arriving,
                    'shortage': demand_qty - total_arriving,
                    'reasons': reasons,
                })

        return {
            'satisfied_demand': satisfied,
            'unsatisfied_demand': unsatisfied,
            'total_satisfied': total_satisfied_qty,
            'total_demand': total_demand_qty,
            'satisfaction_rate': (total_satisfied_qty / total_demand_qty * 100) if total_demand_qty > 0 else 0,
            'num_satisfied': len(satisfied),
            'num_unsatisfied': len(unsatisfied),
        }

    def print_demand_diagnostics(self) -> None:
        """Print detailed demand satisfaction diagnostics."""
        diag = self.get_demand_diagnostics()

        if 'error' in diag:
            print(f"Error: {diag['error']}")
            return

        print("=" * 70)
        print("Demand Satisfaction Diagnostics")
        print("=" * 70)

        print(f"\nOverall:")
        print(f"  Satisfied: {diag['num_satisfied']}/{diag['num_satisfied'] + diag['num_unsatisfied']} demands")
        print(f"  Total quantity: {diag['total_satisfied']:,.0f}/{diag['total_demand']:,.0f} units")
        print(f"  Satisfaction rate: {diag['satisfaction_rate']:.1f}%")

        if diag['unsatisfied_demand']:
            print(f"\nUnsatisfied Demands ({len(diag['unsatisfied_demand'])}):")
            for item in diag['unsatisfied_demand']:
                print(f"\n  Location: {item['location']}, Product: {item['product']}, Date: {item['date']}")
                print(f"    Demand: {item['demand']:,.0f}, Delivered: {item['delivered']:,.0f}, Short: {item['shortage']:,.0f}")
                if item['reasons']:
                    print(f"    Reasons:")
                    for reason in item['reasons']:
                        print(f"      - {reason}")
        else:
            print("\n  ✓ All demands satisfied!")

        print("=" * 70)
