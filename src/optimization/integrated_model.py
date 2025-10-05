"""Integrated production-distribution optimization model.

This module provides an integrated optimization model that combines production
scheduling with distribution routing decisions to minimize total cost.

Decision Variables:
- production[date, product]: Quantity to produce
- shipment[route_index, product, delivery_date]: Quantity to ship on each route
- shortage[dest, product, date]: Demand shortage (if allow_shortages=True)

Constraints:
- Demand satisfaction: Shipments (+ shortage) arriving at each location meet demand
- Flow conservation: Total shipments ≤ total production
- Labor capacity: Production hours ≤ available labor hours per day
- Production capacity: Production ≤ max capacity per day
- Timing feasibility: Shipments depart on/after production date
- Shelf life: Routes filtered to exclude transit times > max_product_age_days (default: 10 days)

Objective:
- Minimize: labor cost + production cost + transport cost + shortage penalty
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
    Binary,
    minimize,
    value,
)

from src.models.forecast import Forecast
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location
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

    def _calculate_required_planning_horizon(self) -> Tuple[Date, Date]:
        """
        Calculate required planning horizon accounting for transit times.

        To satisfy demand on a given date, production must occur earlier
        by the transit time. This method calculates the earliest production
        date needed to satisfy all forecast demands.

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
        required_start = earliest_delivery - timedelta(days=int(max_transit_days))

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

        # Use user-provided dates if given, otherwise use calculated dates
        final_start = self._user_start_date or required_start
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
        # Missing weekday dates are critical errors (production should be possible Mon-Fri)
        # Missing weekend dates are warnings (optional production, zero capacity if not provided)
        missing_weekday_dates = []
        missing_weekend_dates = []

        for prod_date in self.production_dates:
            if prod_date not in self.labor_by_date:
                # weekday() returns 0=Monday, 6=Sunday
                if prod_date.weekday() < 5:  # Monday-Friday
                    missing_weekday_dates.append(prod_date)
                else:  # Saturday-Sunday
                    missing_weekend_dates.append(prod_date)

        # Critical error for missing weekdays
        if missing_weekday_dates:
            if len(missing_weekday_dates) <= 5:
                date_str = ', '.join(str(d) for d in sorted(missing_weekday_dates))
            else:
                date_str = ', '.join(str(d) for d in sorted(missing_weekday_dates)[:5]) + f" (and {len(missing_weekday_dates) - 5} more)"

            issues.append(
                f"Labor calendar missing entries for {len(missing_weekday_dates)} weekday production date(s): {date_str}"
            )

        # Warning only for missing weekends (model treats as zero capacity)
        if missing_weekend_dates:
            if len(missing_weekend_dates) <= 5:
                date_str = ', '.join(str(d) for d in sorted(missing_weekend_dates))
            else:
                date_str = ', '.join(str(d) for d in sorted(missing_weekend_dates)[:5]) + f" (and {len(missing_weekend_dates) - 5} more)"

            warnings.warn(
                f"Labor calendar missing weekend dates in planning horizon: {date_str}. "
                f"These dates will have zero production capacity. "
                f"Add weekend labor entries if weekend production should be available.",
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
        model.routes = list(self.route_indices)

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

        # Create sparse index set for inventory variables
        # Only create variables for (destination, product, date) combinations with demand
        # This significantly reduces model size
        inventory_index_set = set()
        for (dest, prod, date) in self.demand.keys():
            # Add all dates from first demand date through end of horizon for this dest-prod
            # This allows inventory to build up before first demand
            for d in sorted_dates:
                inventory_index_set.add((dest, prod, d))

        model.inventory_index = list(inventory_index_set)

        # Decision variables: production[date, product]
        model.production = Var(
            model.dates,
            model.products,
            within=NonNegativeReals,
            doc="Production quantity by date and product"
        )

        # Decision variables: shipment[route_index, product, delivery_date]
        # delivery_date = date when product arrives at destination
        model.shipment = Var(
            model.routes,
            model.products,
            model.dates,  # Use all dates as potential delivery dates
            within=NonNegativeReals,
            doc="Shipment quantity by route, product, and delivery date"
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
                doc="Binary indicator if truck is used on date"
            )

            # Continuous variable: truck_load[truck_index, destination, product, date]
            # Quantity of product loaded on truck going to specific destination
            # This allows trucks with intermediate stops (like Wednesday Lineage route)
            # to carry different products to different destinations
            model.truck_load = Var(
                model.trucks,
                model.truck_destinations,
                model.products,
                model.dates,
                within=NonNegativeReals,
                doc="Quantity loaded on truck to destination by product and date"
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

        # Decision variables: inventory[dest, product, date]
        # Represents inventory level at destination at END of each date
        # After shipments arrive and demand is satisfied
        # This enables buffer stock to accumulate and eliminate unnecessary weekend production
        model.inventory = Var(
            model.inventory_index,
            within=NonNegativeReals,
            doc="Inventory at destination at end of date (after demand satisfaction)"
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
            doc="Link production_day binary to actual production"
        )

        # Constraints: Calculate fixed hours and overtime for fixed days
        def fixed_hours_rule(model, d):
            """
            CRITICAL FIX: On fixed days (weekdays), if you produce ANYTHING,
            you must pay for ALL fixed hours (12 hours), not just the hours used.

            This prevents the optimizer from incorrectly choosing weekend work
            by under-costing weekday production.
            """
            labor_day = self.labor_by_date.get(d)
            if not labor_day or not labor_day.is_fixed_day:
                return model.fixed_hours_used[d] == 0
            else:
                # If production happens (production_day=1), must pay for all fixed hours
                # If no production (production_day=0), pay for zero fixed hours
                return model.fixed_hours_used[d] == labor_day.fixed_hours * model.production_day[d]

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
            labor_day = self.labor_by_date.get(d)
            if not labor_day or labor_day.is_fixed_day:
                return Constraint.Skip
            else:
                return model.non_fixed_hours_paid[d] >= labor_day.minimum_hours

        model.non_fixed_hours_minimum = Constraint(
            model.dates,
            rule=non_fixed_hours_minimum_rule,
            doc="Non-fixed hours >= minimum commitment"
        )

        # INVENTORY BALANCE CONSTRAINT
        # Replaces simple demand satisfaction with dynamic inventory tracking
        #
        # Balance equation: inventory[t] = inventory[t-1] + arrivals[t] - demand[t] - shortage[t]
        #
        # This enables:
        # - Buffer stock to accumulate over time
        # - Demand satisfaction from inventory + shipments (not just shipments)
        # - Strategic inventory positioning to minimize weekend production
        def inventory_balance_rule(model, dest, prod, date):
            """
            Inventory balance at destination for each date.

            inventory[t] = inventory[t-1] + shipments_arriving[t] - demand[t] - shortage[t]

            For the first date in planning horizon:
                inventory[t] = 0 + shipments[t] - demand[t] - shortage[t]
                (assumes zero initial inventory)

            Args:
                dest: Destination location ID
                prod: Product ID
                date: Date (end of day)

            Returns:
                Constraint expression
            """
            # Get routes to this destination
            route_list = self.routes_to_destination.get(dest, [])

            if not route_list:
                # No routes to destination - inventory must be zero
                # (Will be infeasible if demand > 0 and shortages not allowed)
                return model.inventory[dest, prod, date] == 0

            # Sum of shipments arriving on this date
            arrivals = sum(
                model.shipment[r, prod, date]
                for r in route_list
            )

            # Demand on this date (0 if no demand)
            demand_qty = self.demand.get((dest, prod, date), 0.0)

            # Shortage on this date (0 if shortages not allowed or no demand on this date)
            shortage_qty = 0
            if self.allow_shortages and (dest, prod, date) in self.demand:
                shortage_qty = model.shortage[dest, prod, date]

            # Previous inventory (0 if first date)
            prev_date = self.date_previous.get(date)
            if prev_date is None:
                # First date: assume zero initial inventory
                prev_inventory = 0
            else:
                # Check if previous date inventory exists in sparse index
                if (dest, prod, prev_date) in inventory_index_set:
                    prev_inventory = model.inventory[dest, prod, prev_date]
                else:
                    # Previous date not in index (shouldn't happen with our construction)
                    prev_inventory = 0

            # Balance equation:
            # inventory[t] = inventory[t-1] + arrivals[t] - demand[t] - shortage[t]
            #
            # Rearranged for Pyomo:
            # inventory[t] = prev_inventory + arrivals - demand - shortage
            return model.inventory[dest, prod, date] == (
                prev_inventory + arrivals - demand_qty - shortage_qty
            )

        model.inventory_balance_con = Constraint(
            model.inventory_index,
            rule=inventory_balance_rule,
            doc="Inventory balance at destinations (daily)"
        )

        # NEW CONSTRAINT: Flow conservation (production >= shipments)
        def flow_conservation_rule(model, prod_date, prod):
            # Calculate total shipments that depart on prod_date
            # Departure date = delivery_date - transit_days

            total_shipments = 0
            for r in model.routes:
                transit_days = self.route_transit_days[r]

                # For each delivery date, check if shipment departs on prod_date
                for delivery_date in model.dates:
                    # Calculate departure date
                    departure_date = delivery_date - timedelta(days=transit_days)

                    # If departure_date equals prod_date, include this shipment
                    if departure_date == prod_date:
                        total_shipments += model.shipment[r, prod, delivery_date]

            return model.production[prod_date, prod] >= total_shipments

        model.flow_conservation_con = Constraint(
            model.dates,
            model.products,
            rule=flow_conservation_rule,
            doc="Production >= shipments departing on each date"
        )

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

            # Constraint: Truck availability (day-specific scheduling)
            def truck_availability_rule(model, truck_idx, d):
                """Truck can only be used on dates it runs."""
                trucks_available = self.trucks_on_date.get(d, [])
                if truck_idx not in trucks_available:
                    # Truck doesn't run on this date
                    return model.truck_used[truck_idx, d] == 0
                else:
                    # Truck runs on this date - no constraint (can be 0 or 1)
                    return Constraint.Skip

            model.truck_availability_con = Constraint(
                model.trucks,
                model.dates,
                rule=truck_availability_rule,
                doc="Truck availability by day of week"
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
                # Get all routes that go directly from manufacturing to this destination
                # These are routes where origin = manufacturing_site_id and immediate destination = dest_id
                manufacturing_id = self.manufacturing_site.id

                # Find routes that start from manufacturing and go to dest_id as first destination
                direct_routes = []
                for route_idx in self.route_indices:
                    route = self.route_enumerator.get_route(route_idx)
                    if route and route.origin_id == manufacturing_id:
                        # Get first leg destination (immediate next hop from manufacturing)
                        first_leg_dest = route.path[1] if len(route.path) >= 2 else route.destination_id
                        if first_leg_dest == dest_id:
                            direct_routes.append(route_idx)

                if not direct_routes:
                    return Constraint.Skip

                # Get trucks that go to this destination
                trucks_to_dest = self.trucks_to_destination.get(dest_id, [])

                if not trucks_to_dest:
                    # No trucks to this destination - routes can't be used
                    # Force shipments of this product to be zero
                    return sum(
                        model.shipment[r, product_id, d]
                        for r in direct_routes
                    ) == 0

                # Sum of shipments of THIS PRODUCT on direct routes = sum of truck loads of THIS PRODUCT
                total_route_shipments = sum(
                    model.shipment[r, product_id, d]
                    for r in direct_routes
                )

                total_truck_loads = sum(
                    model.truck_load[t, dest_id, product_id, d]
                    for t in trucks_to_dest
                )

                return total_route_shipments == total_truck_loads

            # Get all unique first-leg destinations from routes originating at manufacturing
            # This ensures we create constraints for ALL destinations that routes actually use,
            # not just the truck final destinations
            first_leg_destinations = set()
            for route_idx in self.route_indices:
                route = self.route_enumerator.get_route(route_idx)
                if route and route.origin_id == self.manufacturing_site.id:
                    # Get first leg destination (immediate next hop from manufacturing)
                    first_leg_dest = route.path[1] if len(route.path) >= 2 else route.destination_id
                    first_leg_destinations.add(first_leg_dest)

            model.truck_route_linking_con = Constraint(
                list(first_leg_destinations),  # Use actual route first-leg destinations
                model.products,  # CRITICAL: Include product dimension to prevent product mixing
                model.dates,
                rule=truck_route_linking_rule,
                doc="Link truck loads to route shipments from manufacturing (by destination, product, and date)"
            )

            # NEW CONSTRAINT: Truck loading timing (D-1 vs D0)
            # Morning trucks can only load D-1 production (previous day)
            # Afternoon trucks can load D-1 or D0 production (previous day or same day)

            # Build sparse index set of valid (truck_idx, dest, date) tuples
            # Only create constraints for trucks that:
            # 1. Actually serve each destination
            # 2. Actually run on each date (excluding weekends/holidays)
            valid_truck_dest_date_tuples = []
            for departure_date in model.dates:
                # Only consider trucks that run on this date
                for truck_idx in self.trucks_on_date.get(departure_date, []):
                    # Only consider destinations this truck serves
                    truck = self.truck_by_index[truck_idx]
                    # Primary destination
                    if truck.destination_id in model.truck_destinations:
                        valid_truck_dest_date_tuples.append((truck_idx, truck.destination_id, departure_date))
                    # Intermediate stop destinations
                    if truck_idx in self.trucks_with_intermediate_stops:
                        for stop_id in self.trucks_with_intermediate_stops[truck_idx]:
                            if stop_id in model.truck_destinations:
                                valid_truck_dest_date_tuples.append((truck_idx, stop_id, departure_date))


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

            def truck_morning_timing_agg_rule(model, truck_idx, dest, departure_date):
                """Morning trucks: total load <= total D-1 production (aggregated over products)."""
                truck = self.truck_by_index[truck_idx]
                if truck.departure_type != 'morning':
                    return Constraint.Skip

                d_minus_1 = departure_date - timedelta(days=1)
                if d_minus_1 not in model.dates:
                    return sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) == 0

                # Aggregate: sum of loads <= sum of D-1 production
                return (sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) <=
                        sum(model.production[d_minus_1, p] for p in model.products))

            def truck_afternoon_timing_agg_rule(model, truck_idx, dest, departure_date):
                """Afternoon trucks: total load <= total D-1 + D0 production (aggregated over products)."""
                truck = self.truck_by_index[truck_idx]
                if truck.departure_type != 'afternoon':
                    return Constraint.Skip

                d_minus_1 = departure_date - timedelta(days=1)
                if d_minus_1 not in model.dates:
                    return sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) == 0

                # Aggregate: sum of loads <= sum of (D-1 + D0) production
                return (sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) <=
                        sum(model.production[d_minus_1, p] + model.production[departure_date, p] for p in model.products))

            # Create separate constraints for morning and afternoon trucks
            morning_tuples = [(t, d, dt) for (t, d, dt) in valid_truck_dest_date_tuples
                            if self.truck_by_index[t].departure_type == 'morning']
            afternoon_tuples = [(t, d, dt) for (t, d, dt) in valid_truck_dest_date_tuples
                              if self.truck_by_index[t].departure_type == 'afternoon']

            if morning_tuples:
                model.truck_morning_timing_agg_con = Constraint(
                    morning_tuples,
                    rule=truck_morning_timing_agg_rule,
                    doc="Morning trucks load D-1 production (aggregated over products)"
                )

            if afternoon_tuples:
                model.truck_afternoon_timing_agg_con = Constraint(
                    afternoon_tuples,
                    rule=truck_afternoon_timing_agg_rule,
                    doc="Afternoon trucks load D-1 or D0 production (aggregated over products)"
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

            # Transport cost
            transport_cost = 0.0
            for r in model.routes:
                route_cost = self.route_cost.get(r, 0.0)
                # Defensive check for None or infinity
                if route_cost is None or not math.isfinite(route_cost):
                    route_cost = 0.0
                for p in model.products:
                    for d in model.dates:
                        transport_cost += route_cost * model.shipment[r, p, d]

            # INVENTORY HOLDING COST (NEW)
            # Cost to hold inventory at destinations (incentivizes JIT while allowing buffering)
            # Uses ambient storage rate (frozen tracking would require mode-specific variables)
            inventory_cost = 0.0
            holding_cost_per_unit_day = self.cost_structure.storage_cost_ambient_per_unit_day
            # Defensive check for None or infinity
            if holding_cost_per_unit_day is None or not math.isfinite(holding_cost_per_unit_day):
                holding_cost_per_unit_day = 0.0

            # Sum inventory costs across all destinations, products, dates
            for dest, prod, date in model.inventory_index:
                inventory_cost += holding_cost_per_unit_day * model.inventory[dest, prod, date]

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

            # Total cost = labor + production + transport + inventory + truck + shortage
            return labor_cost + production_cost + transport_cost + inventory_cost + truck_cost + shortage_cost

        model.obj = Objective(
            rule=objective_rule,
            sense=minimize,
            doc="Minimize total cost (labor + production + transport + inventory + truck + shortage penalty)"
        )

        return model

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

        # Extract shipment decisions
        shipments_by_route_product_date: Dict[Tuple[int, str, Date], float] = {}
        for r in model.routes:
            for p in model.products:
                for d in model.dates:
                    qty = value(model.shipment[r, p, d])
                    if qty > 1e-6:  # Only include non-zero shipments
                        shipments_by_route_product_date[(r, p, d)] = qty

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

        # Calculate transport cost
        total_transport_cost = 0.0
        for r in model.routes:
            route_cost = self.route_cost[r]
            for p in model.products:
                for d in model.dates:
                    qty = value(model.shipment[r, p, d])
                    total_transport_cost += route_cost * qty

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

        # Extract inventory levels
        inventory_by_dest_product_date: Dict[Tuple[str, str, Date], float] = {}
        total_inventory_cost = 0.0
        holding_cost_per_unit_day = self.cost_structure.storage_cost_ambient_per_unit_day

        for dest, prod, date in model.inventory_index:
            qty = value(model.inventory[dest, prod, date])
            if qty > 1e-6:  # Only include non-zero inventory
                inventory_by_dest_product_date[(dest, prod, date)] = qty
                total_inventory_cost += holding_cost_per_unit_day * qty

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

        # Convert production_by_date_product to production_batches list format
        # This format is expected by UI components and matches ProductionSchedule structure
        production_batches = []
        for (prod_date, product_id), quantity in production_by_date_product.items():
            production_batches.append({
                'date': prod_date,
                'product': product_id,
                'quantity': quantity,
            })

        return {
            'production_by_date_product': production_by_date_product,
            'production_batches': production_batches,  # Add list format for UI
            'labor_hours_by_date': labor_hours_by_date,
            'labor_cost_by_date': labor_cost_by_date,
            'shipments_by_route_product_date': shipments_by_route_product_date,
            'shortages_by_dest_product_date': shortages_by_dest_product_date,
            'inventory_by_dest_product_date': inventory_by_dest_product_date,  # NEW
            'truck_used_by_date': truck_used_by_date if self.truck_schedules else {},
            'truck_loads_by_truck_dest_product_date': truck_loads_by_truck_dest_product_date if self.truck_schedules else {},
            'total_labor_cost': total_labor_cost,
            'total_production_cost': total_production_cost,
            'total_transport_cost': total_transport_cost,
            'total_inventory_cost': total_inventory_cost,  # NEW
            'total_truck_cost': total_truck_cost,
            'total_shortage_cost': total_shortage_cost,
            'total_shortage_units': total_shortage_units,
            'total_cost': total_labor_cost + total_production_cost + total_transport_cost + total_inventory_cost + total_truck_cost + total_shortage_cost,  # Updated
        }

    def get_shipment_plan(self) -> Optional[List[Shipment]]:
        """
        Convert optimization solution to list of Shipment objects.

        Returns:
            List of Shipment objects, or None if not solved

        Example:
            model = IntegratedProductionDistributionModel(...)
            result = model.solve()
            if result.is_optimal():
                shipments = model.get_shipment_plan()
                print(f"Total shipments: {len(shipments)}")
        """
        if not self.solution:
            return None

        shipments_by_route_product_date = self.solution['shipments_by_route_product_date']

        # Create production batches first (needed for shipment.batch_id)
        production_by_date_product = self.solution['production_by_date_product']
        batch_id_map: Dict[Tuple[Date, str], str] = {}
        batch_id_counter = 1

        for (prod_date, product_id), quantity in production_by_date_product.items():
            batch_id = f"BATCH-{batch_id_counter:04d}"
            batch_id_map[(prod_date, product_id)] = batch_id
            batch_id_counter += 1

        # Create shipments
        shipments: List[Shipment] = []
        shipment_id_counter = 1

        for (route_idx, product_id, delivery_date), quantity in shipments_by_route_product_date.items():
            # Get route information
            enumerated_route = self.route_enumerator.get_route(route_idx)
            if not enumerated_route:
                continue

            # Calculate departure date
            transit_days = enumerated_route.total_transit_days
            departure_date = delivery_date - timedelta(days=transit_days)

            # Find matching production batch
            # Shipment departs on departure_date, so look for batch on that date
            batch_id = batch_id_map.get((departure_date, product_id))
            if not batch_id:
                # No exact match - use closest earlier batch (simplified)
                batch_id = f"BATCH-UNKNOWN"

            # Create shipment
            shipment = Shipment(
                id=f"SHIP-{shipment_id_counter:04d}",
                batch_id=batch_id,
                product_id=product_id,
                quantity=quantity,
                origin_id=enumerated_route.origin_id,
                destination_id=enumerated_route.destination_id,
                delivery_date=delivery_date,
                route=enumerated_route.route_path,
                production_date=departure_date,  # Simplified: assume production on departure date
            )
            shipments.append(shipment)
            shipment_id_counter += 1

        # Map truck assignments to shipments
        truck_loads = self.solution.get('truck_loads_by_truck_dest_product_date', {})
        if truck_loads and self.truck_schedules:
            for shipment in shipments:
                # Only assign trucks for shipments originating from manufacturing
                if shipment.origin_id == self.manufacturing_site.location_id:
                    # Get immediate next hop from route (first leg destination)
                    immediate_destination = shipment.first_leg_destination

                    # CRITICAL FIX: truck_loads are indexed by DELIVERY date, not departure date!
                    # The model variables truck_load[truck, dest, prod, d] and shipment[route, prod, d]
                    # both use the same date index 'd', which is the delivery date (from demand_satisfaction_con).
                    # So we must match on delivery_date, not production_date/departure_date.
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
