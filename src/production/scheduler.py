"""
Production scheduler for determining production timing and quantities.

This module handles backward scheduling from demand forecasts,
route selection, production aggregation, and capacity validation.
"""

from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import math
import uuid

from src.models.forecast import Forecast, ForecastEntry
from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar
from src.models.production_batch import ProductionBatch
from src.models.product import ProductState
from src.network import NetworkGraphBuilder, RouteFinder, RoutePath
from src.shelf_life import ProductState as ShelfLifeProductState
from .feasibility import ProductionFeasibilityChecker
from .changeover import ProductChangeoverMatrix


@dataclass
class ProductionRequirement:
    """
    Aggregated production requirement for a specific date and product.

    Attributes:
        production_date: Date when production must occur
        product_id: Product identifier
        total_quantity: Total units required
        demand_details: List of (location_id, delivery_date, quantity, route)
    """
    production_date: date
    product_id: str
    total_quantity: float
    demand_details: List[Tuple[str, date, float, RoutePath]] = field(default_factory=list)

    def add_demand(self, location_id: str, delivery_date: date, quantity: float, route: RoutePath):
        """Add demand detail to this requirement."""
        self.demand_details.append((location_id, delivery_date, quantity, route))
        self.total_quantity += quantity

    def __str__(self) -> str:
        return f"{self.production_date}: {self.total_quantity:.0f} units of {self.product_id} ({len(self.demand_details)} destinations)"


@dataclass
class ProductionSchedule:
    """
    Complete production schedule with batches and metadata.

    Attributes:
        manufacturing_site_id: Manufacturing site identifier
        schedule_start_date: First production date
        schedule_end_date: Last production date
        production_batches: List of production batches
        daily_totals: Total units per production date
        daily_labor_hours: Labor hours required per date
        infeasibilities: List of capacity violation messages
        total_units: Total units across all batches
        total_labor_hours: Total labor hours required
        requirements: Original production requirements (before batching)
    """
    manufacturing_site_id: str
    schedule_start_date: date
    schedule_end_date: date
    production_batches: List[ProductionBatch]
    daily_totals: Dict[date, float]
    daily_labor_hours: Dict[date, float]
    infeasibilities: List[str]
    total_units: float
    total_labor_hours: float
    requirements: List[ProductionRequirement] = field(default_factory=list)

    def is_feasible(self) -> bool:
        """Check if schedule is completely feasible."""
        return len(self.infeasibilities) == 0

    def get_batches_for_date(self, production_date: date) -> List[ProductionBatch]:
        """Get all batches for a specific production date."""
        return [b for b in self.production_batches if b.production_date == production_date]

    def __str__(self) -> str:
        status = "FEASIBLE" if self.is_feasible() else f"INFEASIBLE ({len(self.infeasibilities)} issues)"
        return (
            f"ProductionSchedule ({self.schedule_start_date} to {self.schedule_end_date}): "
            f"{len(self.production_batches)} batches, {self.total_units:.0f} units total - {status}"
        )


class ProductionScheduler:
    """
    Production scheduler for backward scheduling from demand forecasts.

    This scheduler:
    1. Processes forecast entries
    2. Selects routes using RouteFinder
    3. Calculates production dates (backward scheduling)
    4. Aggregates requirements by production date
    5. Creates production batches
    6. Validates against capacity constraints
    """

    # Safety margin: produce 1 day before minimum required
    SAFETY_MARGIN_DAYS = 1

    def __init__(
        self,
        manufacturing_site: ManufacturingSite,
        labor_calendar: LaborCalendar,
        graph_builder: NetworkGraphBuilder,
        changeover_matrix: Optional[ProductChangeoverMatrix] = None,
    ):
        """
        Initialize production scheduler.

        Args:
            manufacturing_site: Manufacturing site with production capabilities
            labor_calendar: Labor calendar with daily availability
            graph_builder: Network graph builder for route finding
            changeover_matrix: Product changeover times (uses default if not provided)
        """
        self.manufacturing_site = manufacturing_site
        self.labor_calendar = labor_calendar
        self.graph_builder = graph_builder
        self.route_finder = RouteFinder(graph_builder)
        self.feasibility_checker = ProductionFeasibilityChecker(
            manufacturing_site, labor_calendar
        )

        # Use provided changeover matrix or create default
        if changeover_matrix is None:
            self.changeover_matrix = ProductChangeoverMatrix(
                default_changeover_hours=manufacturing_site.default_changeover_hours
            )
        else:
            self.changeover_matrix = changeover_matrix

    def schedule_from_forecast(
        self,
        forecast: Forecast,
        initial_product_state: ShelfLifeProductState = ShelfLifeProductState.AMBIENT
    ) -> ProductionSchedule:
        """
        Create production schedule from demand forecast.

        Args:
            forecast: Demand forecast with entries
            initial_product_state: Initial state of produced goods (AMBIENT or FROZEN)

        Returns:
            ProductionSchedule with batches and validation results
        """
        # Step 1: Process forecast entries and select routes
        requirements_dict: Dict[Tuple[date, str], ProductionRequirement] = {}

        for entry in forecast.entries:
            # Find route to destination
            route = self.route_finder.recommend_route(
                source=self.manufacturing_site.location_id,
                target=entry.location_id,
                initial_state=initial_product_state,
                prioritize='cost'  # Default to cost optimization
            )

            if route is None:
                # No feasible route - skip this entry (or could flag as error)
                continue

            # Calculate production date (backward scheduling)
            production_date = self._calculate_production_date(
                delivery_date=entry.forecast_date,
                transit_days=route.total_transit_days
            )

            # Skip if production date is in the past
            if production_date < date.today():
                continue

            # Aggregate requirements
            key = (production_date, entry.product_id)
            if key not in requirements_dict:
                requirements_dict[key] = ProductionRequirement(
                    production_date=production_date,
                    product_id=entry.product_id,
                    total_quantity=0.0,
                    demand_details=[]
                )

            requirements_dict[key].add_demand(
                location_id=entry.location_id,
                delivery_date=entry.forecast_date,
                quantity=entry.quantity,
                route=route
            )

        # Convert to list and sort by date
        requirements = sorted(requirements_dict.values(), key=lambda r: r.production_date)

        # Step 2: Round quantities to case increments
        for req in requirements:
            req.total_quantity = self._round_to_case_increment(req.total_quantity)

        # Step 3: Create production batches
        batches = self._create_batches(requirements, initial_product_state)

        # Step 3.5: Optimize daily sequence to minimize changeovers
        batches = self._optimize_daily_sequence(batches)

        # Step 3.6: Update labor hours with daily overhead (startup, shutdown, changeovers)
        self._update_labor_hours_with_overhead(batches)

        # Step 4: Calculate daily totals and labor hours
        daily_totals, daily_labor_hours = self._calculate_daily_totals(batches)

        # Step 5: Validate schedule
        infeasibilities = self._validate_schedule(batches)

        # Step 6: Calculate totals
        total_units = sum(batch.quantity for batch in batches)
        total_labor_hours = sum(daily_labor_hours.values())

        # Determine schedule date range
        if batches:
            schedule_start = min(batch.production_date for batch in batches)
            schedule_end = max(batch.production_date for batch in batches)
        else:
            schedule_start = date.today()
            schedule_end = date.today()

        return ProductionSchedule(
            manufacturing_site_id=self.manufacturing_site.location_id,
            schedule_start_date=schedule_start,
            schedule_end_date=schedule_end,
            production_batches=batches,
            daily_totals=daily_totals,
            daily_labor_hours=daily_labor_hours,
            infeasibilities=infeasibilities,
            total_units=total_units,
            total_labor_hours=total_labor_hours,
            requirements=requirements,
        )

    def _calculate_production_date(
        self,
        delivery_date: date,
        transit_days: int
    ) -> date:
        """
        Calculate production date using backward scheduling.

        Ensures production falls on a valid production day (with available labor).
        If calculated date is weekend/holiday, moves backward to previous production day.

        Args:
            delivery_date: Target delivery date
            transit_days: Transit time in days

        Returns:
            Production date (delivery_date - transit_days - safety_margin)
        """
        # Backward schedule: delivery date - transit - safety margin
        production_date = delivery_date - timedelta(days=transit_days + self.SAFETY_MARGIN_DAYS)

        # Adjust to valid production day (skip weekends/holidays with no fixed labor)
        production_date = self._adjust_to_production_day(production_date)

        return production_date

    def _adjust_to_production_day(self, target_date: date) -> date:
        """
        Adjust date to nearest valid production day using smart distribution.

        A valid production day has fixed labor hours > 0 in the labor calendar,
        or falls on a weekday (Mon-Fri) if not in calendar.

        Strategy for weekend/holiday adjustment:
        - Saturday demand: adjust backward to Friday (prevents Friday overload)
        - Sunday demand: adjust forward to Monday (distributes weekend load)
        - Weekday holidays: adjust forward to next valid day (better capacity spreading)

        This approach distributes weekend demand across two weekdays (Fri + Mon)
        instead of concentrating it all on one day.

        Args:
            target_date: Target date

        Returns:
            Adjusted date that is a valid production day
        """
        # Try to find the date in labor calendar
        labor_day = self.labor_calendar.get_labor_day(target_date)

        if labor_day:
            # Check if this day has fixed labor (standard production day)
            if labor_day.fixed_hours > 0:
                return target_date
            # Otherwise, it's a weekend/holiday - needs adjustment
        else:
            # Not in calendar, check if it's a weekday
            if target_date.weekday() < 5:  # Mon-Fri
                return target_date

        # Determine adjustment direction based on day of week
        # Saturday (weekday() == 5) → backward to Friday
        # Sunday (weekday() == 6) or weekday holidays → forward to Monday
        if target_date.weekday() == 5:  # Saturday
            # Move backward to Friday
            direction = -1
            max_search = 7
        else:  # Sunday or weekday holiday
            # Move forward to next valid day
            direction = 1
            max_search = 7

        # Start from target_date, let the loop increment
        check_date = target_date

        for _ in range(max_search):
            labor_day = self.labor_calendar.get_labor_day(check_date)

            if labor_day and labor_day.fixed_hours > 0:
                # Found a day with fixed labor
                return check_date

            if not labor_day and check_date.weekday() < 5:
                # Not in calendar but is a weekday
                return check_date

            check_date += timedelta(days=direction)

        # Fallback: return target date (should rarely happen)
        return target_date

    def _round_to_case_increment(self, quantity: float) -> float:
        """
        Round quantity up to nearest case increment (10 units).

        Args:
            quantity: Raw quantity

        Returns:
            Quantity rounded up to multiple of 10
        """
        UNITS_PER_CASE = 10
        return math.ceil(quantity / UNITS_PER_CASE) * UNITS_PER_CASE

    def _create_batches(
        self,
        requirements: List[ProductionRequirement],
        initial_state: ShelfLifeProductState
    ) -> List[ProductionBatch]:
        """
        Create production batches from requirements.

        Args:
            requirements: List of production requirements
            initial_state: Initial product state

        Returns:
            List of ProductionBatch objects
        """
        batches = []

        for req in requirements:
            # Calculate labor hours for this batch
            labor_hours = self.manufacturing_site.calculate_labor_hours(req.total_quantity)

            # Calculate production cost
            production_cost = req.total_quantity * self.manufacturing_site.production_cost_per_unit

            # Convert ShelfLifeProductState to ProductState
            if initial_state == ShelfLifeProductState.FROZEN:
                batch_state = ProductState.FROZEN
            elif initial_state == ShelfLifeProductState.AMBIENT:
                batch_state = ProductState.AMBIENT
            else:  # THAWED
                batch_state = ProductState.AMBIENT  # Thawed products treated as ambient

            # Create batch
            batch = ProductionBatch(
                id=f"BATCH-{req.production_date.strftime('%Y%m%d')}-{req.product_id}-{uuid.uuid4().hex[:6]}",
                product_id=req.product_id,
                manufacturing_site_id=self.manufacturing_site.location_id,
                production_date=req.production_date,
                quantity=req.total_quantity,
                initial_state=batch_state,
                labor_hours_used=labor_hours,
                production_cost=production_cost,
            )

            batches.append(batch)

        return batches

    def _calculate_daily_totals(
        self,
        batches: List[ProductionBatch]
    ) -> Tuple[Dict[date, float], Dict[date, float]]:
        """
        Calculate daily production totals and labor hours.

        Args:
            batches: List of production batches

        Returns:
            Tuple of (daily_totals dict, daily_labor_hours dict)
        """
        daily_totals: Dict[date, float] = {}
        daily_labor_hours: Dict[date, float] = {}

        for batch in batches:
            prod_date = batch.production_date

            daily_totals[prod_date] = daily_totals.get(prod_date, 0.0) + batch.quantity
            daily_labor_hours[prod_date] = daily_labor_hours.get(prod_date, 0.0) + batch.labor_hours_used

        return daily_totals, daily_labor_hours

    def _optimize_daily_sequence(
        self,
        batches: List[ProductionBatch]
    ) -> List[ProductionBatch]:
        """
        Optimize production sequence within each day to minimize changeover time.

        Uses a greedy campaign scheduling heuristic:
        1. Group batches by production date
        2. For each day, sequence batches to minimize total changeover time
        3. Strategy: Produce same products consecutively (campaigns)

        Args:
            batches: List of production batches to sequence

        Returns:
            Same batches with sequence_number, changeover_from_product, and changeover_time_hours set
        """
        # Group batches by production date
        batches_by_date: Dict[date, List[ProductionBatch]] = {}
        for batch in batches:
            if batch.production_date not in batches_by_date:
                batches_by_date[batch.production_date] = []
            batches_by_date[batch.production_date].append(batch)

        # Sequence batches for each day
        sequenced_batches = []

        for prod_date, day_batches in sorted(batches_by_date.items()):
            # Sort batches by product_id to group same products together (simple campaign scheduling)
            day_batches.sort(key=lambda b: b.product_id)

            # Assign sequence numbers and changeover information
            previous_product = None
            for seq_num, batch in enumerate(day_batches, start=1):
                batch.sequence_number = seq_num

                # Calculate changeover time
                changeover_time = self.changeover_matrix.get_changeover_time(
                    previous_product,
                    batch.product_id
                )

                batch.changeover_from_product = previous_product
                batch.changeover_time_hours = changeover_time

                # Update for next iteration
                previous_product = batch.product_id

            sequenced_batches.extend(day_batches)

        return sequenced_batches

    def _update_labor_hours_with_overhead(
        self,
        batches: List[ProductionBatch]
    ) -> None:
        """
        Update labor hours for all batches to include daily overhead.

        This method updates each batch's labor_hours_used to properly account for:
        - Daily startup time (allocated to first batch)
        - Daily shutdown time (allocated to last batch)
        - Changeover times (already set by _optimize_daily_sequence)
        - Production time (units / production_rate)

        Args:
            batches: List of sequenced production batches (modified in place)
        """
        # Group batches by date
        batches_by_date: Dict[date, List[ProductionBatch]] = {}
        for batch in batches:
            if batch.production_date not in batches_by_date:
                batches_by_date[batch.production_date] = []
            batches_by_date[batch.production_date].append(batch)

        # Update labor hours for each batch
        for prod_date, day_batches in batches_by_date.items():
            # Sort by sequence number to ensure correct order
            day_batches.sort(key=lambda b: b.sequence_number or 0)

            for batch in day_batches:
                # Base production time
                production_time = batch.quantity / self.manufacturing_site.production_rate

                # Start with production + changeover
                labor_hours = production_time + batch.changeover_time_hours

                # Add startup time to first batch
                if batch.sequence_number == 1:
                    labor_hours += self.manufacturing_site.daily_startup_hours

                # Add shutdown time to last batch
                if batch.sequence_number == len(day_batches):
                    labor_hours += self.manufacturing_site.daily_shutdown_hours

                batch.labor_hours_used = labor_hours

    def _validate_schedule(self, batches: List[ProductionBatch]) -> List[str]:
        """
        Validate production schedule against capacity constraints.

        Args:
            batches: List of production batches

        Returns:
            List of infeasibility messages (empty if all feasible)
        """
        infeasibilities = []

        # Group batches by date
        batches_by_date: Dict[date, List[ProductionBatch]] = {}
        for batch in batches:
            if batch.production_date not in batches_by_date:
                batches_by_date[batch.production_date] = []
            batches_by_date[batch.production_date].append(batch)

        # Check each day
        for prod_date, day_batches in batches_by_date.items():
            total_units = sum(b.quantity for b in day_batches)

            # Check daily capacity
            result = self.feasibility_checker.check_daily_capacity(
                production_date=prod_date,
                units=total_units,
                allow_overtime=True,
                allow_non_fixed_days=True
            )

            if not result.is_feasible:
                infeasibilities.append(
                    f"{prod_date}: {result.reason} (requires {total_units:.0f} units)"
                )

        return infeasibilities

    def smooth_production(
        self,
        schedule: ProductionSchedule,
        avoid_weekends: bool = True
    ) -> ProductionSchedule:
        """
        Attempt to smooth production across days to minimize costs.

        This is a simple heuristic that tries to:
        - Move production earlier to build safety stock
        - Avoid weekend production if weekday capacity exists
        - Spread load to minimize overtime

        Args:
            schedule: Original production schedule
            avoid_weekends: Try to avoid weekend production

        Returns:
            Potentially smoothed production schedule
        """
        # This is a placeholder for future optimization
        # For now, just return the original schedule
        # In a full implementation, this would use heuristics to shift production
        return schedule
