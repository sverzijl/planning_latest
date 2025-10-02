"""Production planning optimization model.

This module provides a simple production optimization model that determines
optimal production quantities and timing to minimize total cost.

Decision Variables:
- production[date, product]: Quantity to produce

Constraints:
- Demand satisfaction: Production meets total demand
- Labor capacity: Production hours ≤ available labor hours per day
- Production capacity: Production ≤ max capacity per day
- Non-negativity: Production ≥ 0

Objective:
- Minimize: labor cost + production cost
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
from src.models.production_batch import ProductionBatch
from src.production.scheduler import ProductionSchedule

from .base_model import BaseOptimizationModel
from .solver_config import SolverConfig


class ProductionOptimizationModel(BaseOptimizationModel):
    """
    Simple production planning optimization model.

    Optimizes production scheduling to minimize total cost (labor + production)
    while satisfying demand and respecting capacity constraints.

    This is the simplest optimization model - it doesn't consider:
    - Distribution routing (assumes demand is aggregate)
    - Truck loading and timing
    - Shelf life constraints
    - Inventory at hubs

    Example:
        model = ProductionOptimizationModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
        )

        result = model.solve(time_limit_seconds=60)
        if result.is_optimal():
            schedule = model.get_production_schedule()
            print(f"Total cost: ${result.objective_value:,.2f}")
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
        solver_config: Optional[SolverConfig] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None,
    ):
        """
        Initialize production optimization model.

        Args:
            forecast: Demand forecast
            labor_calendar: Labor availability and costs
            manufacturing_site: Manufacturing site data
            cost_structure: Cost parameters
            solver_config: Solver configuration (optional)
            start_date: Planning horizon start (default: first forecast date)
            end_date: Planning horizon end (default: last forecast date)
        """
        super().__init__(solver_config)

        self.forecast = forecast
        self.labor_calendar = labor_calendar
        self.manufacturing_site = manufacturing_site
        self.cost_structure = cost_structure

        # Determine planning horizon
        if forecast.entries:
            self.start_date = start_date or min(e.forecast_date for e in forecast.entries)
            self.end_date = end_date or max(e.forecast_date for e in forecast.entries)
        else:
            raise ValueError("Forecast must have at least one entry")

        # Extract sets and parameters
        self._extract_data()

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

        # Total demand by product (aggregate across all locations and dates)
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

    def build_model(self) -> ConcreteModel:
        """
        Build production optimization model.

        Returns:
            Pyomo ConcreteModel
        """
        model = ConcreteModel()

        # Sets
        model.dates = list(self.production_dates)
        model.products = list(self.products)

        # Decision variables: production[date, product]
        model.production = Var(
            model.dates,
            model.products,
            within=NonNegativeReals,
            doc="Production quantity by date and product"
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

        # Constraint: Meet total demand for each product
        def demand_satisfaction_rule(model, p):
            total_production = sum(model.production[d, p] for d in model.dates)
            return total_production >= self.total_demand_by_product[p]

        model.demand_satisfaction_con = Constraint(
            model.products,
            rule=demand_satisfaction_rule,
            doc="Total production meets demand"
        )

        # Constraints: Calculate fixed hours and overtime for fixed days
        def fixed_hours_rule(model, d):
            labor_day = self.labor_by_date.get(d)
            if not labor_day or not labor_day.is_fixed_day:
                return model.fixed_hours_used[d] == 0
            else:
                # Fixed hours used = min(labor_hours, fixed_hours)
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
                # Overtime = labor_hours - fixed_hours (if positive)
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
                # Must pay for max(actual_hours, minimum_hours)
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

        # Objective: Minimize total cost = labor cost + production cost
        def objective_rule(model):
            # Labor cost
            labor_cost = 0.0
            for d in model.dates:
                labor_day = self.labor_by_date.get(d)
                if labor_day:
                    if labor_day.is_fixed_day:
                        # Fixed day: regular rate × fixed hours + overtime rate × overtime hours
                        labor_cost += (
                            labor_day.regular_rate * model.fixed_hours_used[d]
                            + labor_day.overtime_rate * model.overtime_hours_used[d]
                        )
                    else:
                        # Non-fixed day: non_fixed_rate × hours paid
                        rate = labor_day.non_fixed_rate or 0.0
                        labor_cost += rate * model.non_fixed_hours_paid[d]

            # Production cost
            production_cost = 0.0
            for d in model.dates:
                for p in model.products:
                    # Cost per unit × production quantity
                    production_cost += self.cost_structure.production_cost_per_unit * model.production[d, p]

            return labor_cost + production_cost

        model.obj = Objective(
            rule=objective_rule,
            sense=minimize,
            doc="Minimize total cost (labor + production)"
        )

        return model

    def extract_solution(self, model: ConcreteModel) -> Dict[str, Any]:
        """
        Extract solution from solved model.

        Args:
            model: Solved Pyomo model

        Returns:
            Dictionary with production schedule and costs
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

        return {
            'production_by_date_product': production_by_date_product,
            'labor_hours_by_date': labor_hours_by_date,
            'labor_cost_by_date': labor_cost_by_date,
            'total_labor_cost': total_labor_cost,
            'total_production_cost': total_production_cost,
            'total_cost': total_labor_cost + total_production_cost,
        }

    def get_production_schedule(self) -> Optional[ProductionSchedule]:
        """
        Convert optimization solution to ProductionSchedule.

        Returns:
            ProductionSchedule object, or None if not solved

        Example:
            model = ProductionOptimizationModel(...)
            result = model.solve()
            if result.is_optimal():
                schedule = model.get_production_schedule()
                print(f"Total batches: {len(schedule.production_batches)}")
        """
        if not self.solution:
            return None

        production_by_date_product = self.solution['production_by_date_product']
        labor_hours_by_date = self.solution['labor_hours_by_date']

        # Create production batches
        batches: List[ProductionBatch] = []
        batch_id_counter = 1

        for (prod_date, product_id), quantity in production_by_date_product.items():
            batch = ProductionBatch(
                id=f"OPT-BATCH-{batch_id_counter:04d}",
                product_id=product_id,
                manufacturing_site_id=self.manufacturing_site.location_id,
                production_date=prod_date,
                quantity=quantity,
                labor_hours_used=labor_hours_by_date.get(prod_date, 0.0),
                production_cost=self.cost_structure.production_cost_per_unit * quantity,
            )
            batches.append(batch)
            batch_id_counter += 1

        # Calculate daily totals
        daily_totals: Dict[Date, float] = defaultdict(float)
        for batch in batches:
            daily_totals[batch.production_date] += batch.quantity

        # Create schedule
        schedule = ProductionSchedule(
            manufacturing_site_id=self.manufacturing_site.location_id,
            schedule_start_date=self.start_date,
            schedule_end_date=self.end_date,
            production_batches=batches,
            daily_totals=dict(daily_totals),
            daily_labor_hours=labor_hours_by_date,
            infeasibilities=[],  # Optimization guarantees feasibility
            total_units=sum(b.quantity for b in batches),
            total_labor_hours=sum(labor_hours_by_date.values()),
        )

        return schedule

    def print_solution_summary(self) -> None:
        """
        Print summary of optimization solution.

        Example:
            model = ProductionOptimizationModel(...)
            model.solve()
            model.print_solution_summary()
        """
        if not self.solution:
            print("No solution available. Model not solved or infeasible.")
            return

        print("=" * 70)
        print("Production Optimization Solution")
        print("=" * 70)

        solution = self.solution

        print(f"\nPlanning Horizon: {self.start_date} to {self.end_date}")
        print(f"Products: {len(self.products)}")
        print(f"Production Days: {len([d for d, h in solution['labor_hours_by_date'].items() if h > 0])}")

        print(f"\nTotal Costs:")
        print(f"  Labor Cost:      ${solution['total_labor_cost']:>12,.2f}")
        print(f"  Production Cost: ${solution['total_production_cost']:>12,.2f}")
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

        # Labor summary
        total_hours = sum(solution['labor_hours_by_date'].values())
        print(f"\nLabor Summary:")
        print(f"  Total Hours: {total_hours:,.1f}")
        if total_hours > 0:
            print(f"  Average Cost per Hour: ${solution['total_labor_cost']/total_hours:,.2f}")

        # Demand satisfaction
        print(f"\nDemand Satisfaction:")
        for product_id, demand in self.total_demand_by_product.items():
            produced = by_product.get(product_id, 0.0)
            pct = (produced / demand * 100) if demand > 0 else 0
            status = "✓" if produced >= demand * 0.999 else "✗"
            print(f"  {status} {product_id}: {produced:,.0f} / {demand:,.0f} ({pct:.1f}%)")

        print("=" * 70)
