"""Integrated production-distribution optimization model.

This module provides an integrated optimization model that combines production
scheduling with distribution routing decisions to minimize total cost.

Decision Variables:
- production[date, product]: Quantity to produce
- shipment[route_index, product, delivery_date]: Quantity to ship on each route

Constraints:
- Demand satisfaction: Shipments arriving at each location meet demand
- Flow conservation: Total shipments ≤ total production
- Labor capacity: Production hours ≤ available labor hours per day
- Production capacity: Production ≤ max capacity per day
- Timing feasibility: Shipments depart on/after production date

Objective:
- Minimize: labor cost + production cost + transport cost
"""

from typing import Dict, List, Tuple, Set, Optional, Any
from datetime import date as Date, timedelta
from collections import defaultdict

from pyomo.environ import (
    ConcreteModel,
    Var,
    Constraint,
    Objective,
    NonNegativeReals,
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
        """
        super().__init__(solver_config)

        self.forecast = forecast
        self.labor_calendar = labor_calendar
        self.manufacturing_site = manufacturing_site
        self.cost_structure = cost_structure
        self.locations = locations
        self.routes = routes
        self.max_routes_per_destination = max_routes_per_destination

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
        self.demand: Dict[Tuple[str, str, Date], float] = {}
        for entry in self.forecast.entries:
            key = (entry.location_id, entry.product_id, entry.forecast_date)
            self.demand[key] = entry.quantity

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

        # Max production capacity per day (units)
        self.max_capacity_per_day = self.MAX_HOURS_PER_DAY * self.PRODUCTION_RATE

        # Enumerate routes using RouteEnumerator
        self._enumerate_routes()

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
        self.enumerated_routes: List[EnumeratedRoute] = self.route_enumerator.get_all_routes()

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

        # Constraints: Calculate fixed hours and overtime for fixed days
        def fixed_hours_rule(model, d):
            labor_day = self.labor_by_date.get(d)
            if not labor_day or not labor_day.is_fixed_day:
                return model.fixed_hours_used[d] == 0
            else:
                return model.fixed_hours_used[d] <= labor_day.fixed_hours

        model.fixed_hours_rule = Constraint(
            model.dates,
            rule=fixed_hours_rule,
            doc="Fixed hours calculation"
        )

        def fixed_hours_upper_rule(model, d):
            return model.fixed_hours_used[d] <= model.labor_hours[d]

        model.fixed_hours_upper = Constraint(
            model.dates,
            rule=fixed_hours_upper_rule,
            doc="Fixed hours ≤ actual hours"
        )

        def overtime_hours_rule(model, d):
            labor_day = self.labor_by_date.get(d)
            if not labor_day or not labor_day.is_fixed_day:
                return model.overtime_hours_used[d] == 0
            else:
                return model.overtime_hours_used[d] == model.labor_hours[d] - model.fixed_hours_used[d]

        model.overtime_hours_rule = Constraint(
            model.dates,
            rule=overtime_hours_rule,
            doc="Overtime hours calculation"
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

        # NEW CONSTRAINT: Demand satisfaction by location-date-product
        def demand_satisfaction_rule(model, dest, prod, delivery_date):
            # Get demand for this location-product-date
            demand_qty = self.demand.get((dest, prod, delivery_date), 0.0)

            if demand_qty == 0:
                # No demand, skip constraint
                return Constraint.Skip

            # Get all routes to this destination
            route_list = self.routes_to_destination.get(dest, [])

            if not route_list:
                # No routes to destination - will be infeasible if demand > 0
                return Constraint.Skip

            # Sum of shipments arriving on delivery_date
            total_shipments = sum(
                model.shipment[r, prod, delivery_date]
                for r in route_list
            )

            return total_shipments >= demand_qty

        # Create constraint for all location-product-date combinations with demand
        demand_keys = list(self.demand.keys())
        model.demand_satisfaction_con = Constraint(
            [(dest, prod, deliv_date) for dest, prod, deliv_date in demand_keys],
            rule=demand_satisfaction_rule,
            doc="Demand satisfaction by location-date-product"
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

        # Objective: Minimize total cost = labor cost + production cost + transport cost
        def objective_rule(model):
            # Labor cost (same as production model)
            labor_cost = 0.0
            for d in model.dates:
                labor_day = self.labor_by_date.get(d)
                if labor_day:
                    if labor_day.is_fixed_day:
                        labor_cost += (
                            labor_day.regular_rate * model.fixed_hours_used[d]
                            + labor_day.overtime_rate * model.overtime_hours_used[d]
                        )
                    else:
                        rate = labor_day.non_fixed_rate or 0.0
                        labor_cost += rate * model.non_fixed_hours_paid[d]

            # Production cost
            production_cost = 0.0
            for d in model.dates:
                for p in model.products:
                    production_cost += self.cost_structure.production_cost_per_unit * model.production[d, p]

            # NEW: Transport cost
            transport_cost = 0.0
            for r in model.routes:
                route_cost = self.route_cost[r]
                for p in model.products:
                    for d in model.dates:
                        transport_cost += route_cost * model.shipment[r, p, d]

            return labor_cost + production_cost + transport_cost

        model.obj = Objective(
            rule=objective_rule,
            sense=minimize,
            doc="Minimize total cost (labor + production + transport)"
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
                    rate = labor_day.non_fixed_rate or 0.0
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

        return {
            'production_by_date_product': production_by_date_product,
            'labor_hours_by_date': labor_hours_by_date,
            'labor_cost_by_date': labor_cost_by_date,
            'shipments_by_route_product_date': shipments_by_route_product_date,
            'total_labor_cost': total_labor_cost,
            'total_production_cost': total_production_cost,
            'total_transport_cost': total_transport_cost,
            'total_cost': total_labor_cost + total_production_cost + total_transport_cost,
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
        for product_id, demand in self.total_demand_by_product.items():
            produced = by_product.get(product_id, 0.0)
            pct = (produced / demand * 100) if demand > 0 else 0
            status = "✓" if produced >= demand * 0.999 else "✗"
            print(f"  {status} {product_id}: {produced:,.0f} / {demand:,.0f} ({pct:.1f}%)")

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
                    for route_idx in route_list:
                        route = self.route_enumerator.get_route(route_idx)
                        required_depart = deliv_date - timedelta(days=route.total_transit_days)

                        if required_depart < self.start_date:
                            reasons.append(
                                f"Route {route_idx} ({route.total_transit_days}d transit) requires "
                                f"departure on {required_depart} (before planning start {self.start_date})"
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
