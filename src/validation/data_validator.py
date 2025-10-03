"""Comprehensive data validation for production planning.

This module performs pre-flight checks to identify data quality issues,
capacity constraints, and configuration problems before planning runs.
Provides actionable guidance for fixing detected issues.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.models.forecast import Forecast
from src.models.location import Location, LocationType
from src.models.route import Route
from src.models.labor_calendar import LaborCalendar
from src.models.truck_schedule import TruckSchedule
from src.models.cost_structure import CostStructure
from src.models.manufacturing import ManufacturingSite


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a single validation issue.

    Attributes:
        id: Unique identifier for the issue type
        category: Category of validation (e.g., "Completeness", "Capacity")
        severity: Severity level (INFO, WARNING, ERROR, CRITICAL)
        title: Short title describing the issue
        description: Detailed description of the issue
        impact: Explanation of how this affects planning
        fix_guidance: Step-by-step guidance on how to fix the issue
        affected_data: Optional DataFrame showing affected data
        fix_action: Optional action identifier for auto-fix
        fix_action_label: Optional label for auto-fix button
        metadata: Additional metadata about the issue
    """
    id: str
    category: str
    severity: ValidationSeverity
    title: str
    description: str
    impact: str
    fix_guidance: str
    affected_data: Optional[pd.DataFrame] = None
    fix_action: Optional[str] = None
    fix_action_label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DataValidator:
    """Performs comprehensive data validation for production planning.

    Validates:
    - Completeness: All required data present
    - Consistency: Cross-reference validation
    - Capacity: Production and transport capacity
    - Shelf life: Transit time validation
    - Date ranges: Planning horizon coverage
    - Data quality: Outliers and anomalies
    - Business rules: Manufacturing and distribution constraints
    """

    # Manufacturing constants
    PRODUCTION_RATE = 1400  # units/hour
    MAX_REGULAR_HOURS = 12
    MAX_OVERTIME_HOURS = 2
    MAX_DAILY_HOURS = 14
    TRUCK_CAPACITY = 14080  # units per truck (44 pallets × 320 units)
    PALLET_SIZE = 320  # units per pallet
    CASE_SIZE = 10  # units per case
    AMBIENT_SHELF_LIFE_DAYS = 17
    FROZEN_SHELF_LIFE_DAYS = 120
    THAWED_SHELF_LIFE_DAYS = 14
    BREADROOM_MIN_SHELF_LIFE_DAYS = 7
    MAX_SAFE_TRANSIT_DAYS = 10

    def __init__(
        self,
        forecast: Optional[Forecast] = None,
        locations: Optional[List[Location]] = None,
        routes: Optional[List[Route]] = None,
        labor_calendar: Optional[LaborCalendar] = None,
        truck_schedules: Optional[List[TruckSchedule]] = None,
        cost_structure: Optional[CostStructure] = None,
        manufacturing_site: Optional[ManufacturingSite] = None,
    ):
        """Initialize validator with data to validate.

        Args:
            forecast: Forecast object with demand data
            locations: List of location definitions
            routes: List of route definitions
            labor_calendar: Labor calendar with daily availability
            truck_schedules: List of truck schedules
            cost_structure: Cost parameters
            manufacturing_site: Manufacturing site configuration
        """
        self.forecast = forecast
        self.locations = locations
        self.routes = routes
        self.labor_calendar = labor_calendar
        self.truck_schedules = truck_schedules
        self.cost_structure = cost_structure
        self.manufacturing_site = manufacturing_site
        self.issues: List[ValidationIssue] = []

    def validate_all(self) -> List[ValidationIssue]:
        """Run all validation checks and return list of issues.

        Returns:
            List of ValidationIssue objects found during validation
        """
        self.issues = []

        # Run all validation categories
        self.check_completeness()
        self.check_consistency()
        self.check_production_capacity()
        self.check_transport_capacity()
        self.check_shelf_life()
        self.check_date_ranges()
        self.check_data_quality()
        self.check_business_rules()

        return self.issues

    def check_completeness(self):
        """Validate all required data is present."""

        # Check forecast data
        if self.forecast is None or len(self.forecast.entries) == 0:
            self.issues.append(ValidationIssue(
                id="COMPL_001",
                category="Completeness",
                severity=ValidationSeverity.CRITICAL,
                title="No forecast data loaded",
                description="Planning requires forecast data to proceed.",
                impact="Planning cannot run without demand forecast. All planning steps will fail.",
                fix_guidance=(
                    "**How to fix:**\n"
                    "1. Go to Upload Data page\n"
                    "2. Select forecast Excel file (must contain 'Forecast' sheet)\n"
                    "3. Click 'Parse Files' button\n\n"
                    "**Required format:**\n"
                    "- Sheet name: 'Forecast'\n"
                    "- Columns: location_id, product_id, date, quantity"
                ),
                fix_action="navigate_to_upload"
            ))

        # Check locations
        if self.locations is None or len(self.locations) == 0:
            self.issues.append(ValidationIssue(
                id="COMPL_002",
                category="Completeness",
                severity=ValidationSeverity.CRITICAL,
                title="No locations defined",
                description="Network configuration requires location definitions.",
                impact="Cannot plan distribution without knowing locations and their properties.",
                fix_guidance=(
                    "**How to fix:**\n"
                    "1. Go to Upload Data page\n"
                    "2. Select network configuration Excel file\n"
                    "3. Ensure file contains 'Locations' sheet\n\n"
                    "**Required columns:**\n"
                    "- id, name, type, storage_mode, capacity"
                )
            ))

        # Check routes
        if self.routes is None or len(self.routes) == 0:
            self.issues.append(ValidationIssue(
                id="COMPL_003",
                category="Completeness",
                severity=ValidationSeverity.CRITICAL,
                title="No routes defined",
                description="Distribution planning requires route definitions.",
                impact="Cannot create shipment plans without routes between locations.",
                fix_guidance=(
                    "**How to fix:**\n"
                    "1. Ensure network configuration file contains 'Routes' sheet\n"
                    "2. Define routes from manufacturing site to all destinations\n\n"
                    "**Required columns:**\n"
                    "- origin_id, destination_id, transit_time_days, transport_mode, cost_per_unit"
                )
            ))

        # Check labor calendar
        if self.labor_calendar is None or len(self.labor_calendar.days) == 0:
            self.issues.append(ValidationIssue(
                id="COMPL_004",
                category="Completeness",
                severity=ValidationSeverity.CRITICAL,
                title="No labor calendar loaded",
                description="Production scheduling requires labor calendar.",
                impact="Cannot calculate labor costs or production capacity without calendar.",
                fix_guidance=(
                    "**How to fix:**\n"
                    "1. Ensure network configuration file contains 'LaborCalendar' sheet\n"
                    "2. Define daily labor availability for planning horizon\n\n"
                    "**Required columns:**\n"
                    "- date, fixed_hours, cost_per_fixed_hour, cost_per_overtime_hour, cost_per_non_fixed_hour"
                )
            ))

        # Check truck schedules
        if self.truck_schedules is None or len(self.truck_schedules) == 0:
            self.issues.append(ValidationIssue(
                id="COMPL_005",
                category="Completeness",
                severity=ValidationSeverity.ERROR,
                title="No truck schedules loaded",
                description="Distribution planning requires truck departure schedules.",
                impact="Cannot assign shipments to trucks without schedule. May need to assume unlimited trucks.",
                fix_guidance=(
                    "**How to fix:**\n"
                    "1. Ensure network configuration file contains 'TruckSchedules' sheet\n"
                    "2. Define truck departure times and destinations\n\n"
                    "**Required columns:**\n"
                    "- truck_name, departure_type (morning/afternoon), destination_id, day_of_week"
                )
            ))

        # Check cost parameters
        if self.cost_structure is None:
            self.issues.append(ValidationIssue(
                id="COMPL_006",
                category="Completeness",
                severity=ValidationSeverity.WARNING,
                title="No cost parameters loaded",
                description="Cost optimization requires cost structure definition.",
                impact="Will use default costs. Cost calculations may be inaccurate.",
                fix_guidance=(
                    "**How to fix:**\n"
                    "1. Ensure network configuration file contains 'CostParameters' sheet\n"
                    "2. Define all cost components\n\n"
                    "**Required parameters:**\n"
                    "- production_cost_per_unit, storage_cost_per_unit_per_day, waste_cost_multiplier"
                )
            ))

        # Check manufacturing site
        if self.manufacturing_site is None:
            if self.locations and len(self.locations) > 0:
                # Check if any location is marked as manufacturing
                has_manufacturing = any(loc.type == LocationType.MANUFACTURING for loc in self.locations)
                if not has_manufacturing:
                    self.issues.append(ValidationIssue(
                        id="COMPL_007",
                        category="Completeness",
                        severity=ValidationSeverity.CRITICAL,
                        title="No manufacturing location found",
                        description="At least one location must be designated as MANUFACTURING type.",
                        impact="Cannot plan production without manufacturing site (typically Location ID: 6122).",
                        fix_guidance=(
                            "**How to fix:**\n"
                            "1. Edit 'Locations' sheet in network configuration file\n"
                            "2. Set type='MANUFACTURING' for your production facility\n"
                            "3. Typical manufacturing location ID: 6122\n\n"
                            "**Example:**\n"
                            "id=6122, name='Manufacturing Site', type='MANUFACTURING', storage_mode='AMBIENT'"
                        )
                    ))

    def check_consistency(self):
        """Validate cross-reference consistency between data entities."""

        if self.forecast is None or self.locations is None:
            return  # Can't check consistency without both

        # Build location ID set for fast lookup
        location_ids = {loc.id for loc in self.locations}

        # Check forecast references valid locations
        invalid_forecast_locations = []
        for entry in self.forecast.entries:
            if entry.location_id not in location_ids:
                invalid_forecast_locations.append({
                    'location_id': entry.location_id,
                    'product_id': entry.product_id,
                    'date': entry.forecast_date,
                    'quantity': entry.quantity
                })

        if invalid_forecast_locations:
            df = pd.DataFrame(invalid_forecast_locations)
            unique_invalid = df['location_id'].unique()

            self.issues.append(ValidationIssue(
                id="CONS_001",
                category="Consistency",
                severity=ValidationSeverity.ERROR,
                title="Forecast references undefined locations",
                description=f"Found {len(invalid_forecast_locations)} forecast entries for {len(unique_invalid)} undefined locations: {list(unique_invalid)[:5]}",
                impact="Planning will fail for these destinations. Demand cannot be satisfied.",
                fix_guidance=(
                    "**How to fix:**\n"
                    "1. Add missing locations to 'Locations' sheet in network config\n"
                    "2. OR remove invalid forecast entries\n"
                    "3. Verify location IDs match between forecast and locations\n\n"
                    "**Common causes:**\n"
                    "- Typo in location ID\n"
                    "- Location decommissioned but still in forecast\n"
                    "- Locations file incomplete"
                ),
                affected_data=df.head(50),
                metadata={'invalid_location_ids': list(unique_invalid)}
            ))

        # Check routes reference valid locations
        if self.routes:
            invalid_route_origins = []
            invalid_route_destinations = []

            for route in self.routes:
                if route.origin_id not in location_ids:
                    invalid_route_origins.append({
                        'origin_id': route.origin_id,
                        'destination_id': route.destination_id,
                        'transit_time_days': route.transit_time_days
                    })
                if route.destination_id not in location_ids:
                    invalid_route_destinations.append({
                        'origin_id': route.origin_id,
                        'destination_id': route.destination_id,
                        'transit_time_days': route.transit_time_days
                    })

            if invalid_route_origins:
                df = pd.DataFrame(invalid_route_origins)
                self.issues.append(ValidationIssue(
                    id="CONS_002",
                    category="Consistency",
                    severity=ValidationSeverity.ERROR,
                    title="Routes reference undefined origin locations",
                    description=f"Found {len(invalid_route_origins)} routes with invalid origins",
                    impact="These routes cannot be used for distribution planning.",
                    fix_guidance=(
                        "**How to fix:**\n"
                        "1. Add missing origin locations to 'Locations' sheet\n"
                        "2. OR correct origin_id in 'Routes' sheet\n"
                        "3. Ensure all route origins exist in locations table"
                    ),
                    affected_data=df.head(20)
                ))

            if invalid_route_destinations:
                df = pd.DataFrame(invalid_route_destinations)
                self.issues.append(ValidationIssue(
                    id="CONS_003",
                    category="Consistency",
                    severity=ValidationSeverity.ERROR,
                    title="Routes reference undefined destination locations",
                    description=f"Found {len(invalid_route_destinations)} routes with invalid destinations",
                    impact="Cannot ship to these destinations. Planning may be infeasible.",
                    fix_guidance=(
                        "**How to fix:**\n"
                        "1. Add missing destination locations to 'Locations' sheet\n"
                        "2. OR correct destination_id in 'Routes' sheet"
                    ),
                    affected_data=df.head(20)
                ))

        # Check truck schedules reference valid destinations
        if self.truck_schedules:
            invalid_truck_destinations = []

            for schedule in self.truck_schedules:
                if schedule.destination_id and schedule.destination_id not in location_ids:
                    invalid_truck_destinations.append({
                        'truck_name': schedule.truck_name,
                        'destination_id': schedule.destination_id,
                        'day_of_week': schedule.day_of_week.name if schedule.day_of_week else None,
                        'departure_type': schedule.departure_type.name
                    })

            if invalid_truck_destinations:
                df = pd.DataFrame(invalid_truck_destinations)
                self.issues.append(ValidationIssue(
                    id="CONS_004",
                    category="Consistency",
                    severity=ValidationSeverity.WARNING,
                    title="Truck schedules reference undefined destinations",
                    description=f"Found {len(invalid_truck_destinations)} truck schedules with invalid destinations",
                    impact="These trucks cannot be used. May reduce available shipping capacity.",
                    fix_guidance=(
                        "**How to fix:**\n"
                        "1. Add missing destinations to 'Locations' sheet\n"
                        "2. OR correct destination_id in 'TruckSchedules' sheet"
                    ),
                    affected_data=df.head(20)
                ))

    def check_production_capacity(self):
        """Check if demand is within production capacity constraints."""

        if self.forecast is None or self.labor_calendar is None:
            return

        # Calculate total demand
        total_demand = sum(entry.quantity for entry in self.forecast.entries)

        # Get forecast date range
        forecast_dates = [entry.forecast_date for entry in self.forecast.entries]
        if not forecast_dates:
            return

        start_date = min(forecast_dates)
        end_date = max(forecast_dates)
        planning_days = (end_date - start_date).days + 1

        # Calculate available production capacity
        # Regular capacity: 12h/day * 1400 units/h * working days
        daily_regular_capacity = self.MAX_REGULAR_HOURS * self.PRODUCTION_RATE  # 16,800
        daily_max_capacity = self.MAX_DAILY_HOURS * self.PRODUCTION_RATE  # 19,600

        # Count working days (days with fixed hours > 0)
        working_days = len([day for day in self.labor_calendar.days
                           if day.fixed_hours > 0])
        total_days_in_calendar = len(self.labor_calendar.days)

        regular_capacity = working_days * daily_regular_capacity
        max_capacity_weekdays = working_days * daily_max_capacity

        # Absolute max includes weekends (if needed)
        weekend_days = total_days_in_calendar - working_days
        absolute_max_capacity = max_capacity_weekdays + (weekend_days * daily_max_capacity)

        # Check capacity levels
        capacity_utilization = (total_demand / max_capacity_weekdays * 100) if max_capacity_weekdays > 0 else 0

        if total_demand > absolute_max_capacity:
            self.issues.append(ValidationIssue(
                id="CAP_001",
                category="Capacity",
                severity=ValidationSeverity.CRITICAL,
                title="Demand exceeds absolute maximum production capacity",
                description=(
                    f"Total demand: {total_demand:,.0f} units\n"
                    f"Maximum capacity (with weekends): {absolute_max_capacity:,.0f} units\n"
                    f"Shortfall: {total_demand - absolute_max_capacity:,.0f} units ({(total_demand - absolute_max_capacity) / total_demand * 100:.1f}%)"
                ),
                impact="Planning is mathematically infeasible. Cannot meet demand even with all overtime and weekend work.",
                fix_guidance=(
                    "**Options to resolve:**\n"
                    "1. **Reduce demand:** Adjust forecast quantities downward\n"
                    "2. **Extend planning horizon:** Spread demand over more days\n"
                    "3. **Increase production rate:** If equipment allows (currently 1,400 units/hour)\n"
                    "4. **Add production shifts:** If not already at 24-hour operation\n\n"
                    "**Immediate action:**\n"
                    "Review demand forecast for errors or one-time spikes that can be smoothed."
                ),
                metadata={
                    'total_demand': total_demand,
                    'max_capacity': absolute_max_capacity,
                    'shortfall': total_demand - absolute_max_capacity,
                    'shortfall_pct': (total_demand - absolute_max_capacity) / total_demand * 100
                }
            ))

        elif total_demand > max_capacity_weekdays:
            weekend_units_needed = total_demand - max_capacity_weekdays
            weekend_days_needed = np.ceil(weekend_units_needed / daily_max_capacity)

            self.issues.append(ValidationIssue(
                id="CAP_002",
                category="Capacity",
                severity=ValidationSeverity.ERROR,
                title="Demand requires weekend production",
                description=(
                    f"Total demand: {total_demand:,.0f} units\n"
                    f"Weekday capacity (with OT): {max_capacity_weekdays:,.0f} units\n"
                    f"Weekend production needed: {weekend_units_needed:,.0f} units\n"
                    f"Estimated weekend days: {int(weekend_days_needed)}"
                ),
                impact=(
                    f"Must run production on ~{int(weekend_days_needed)} weekend days. "
                    "Significantly higher labor costs (4-hour minimum payments, premium rates)."
                ),
                fix_guidance=(
                    "**Options:**\n"
                    "1. **Accept weekend work:** Enable weekend production in planning\n"
                    "2. **Reduce demand:** Lower forecast by {0:,.0f} units to avoid weekends\n"
                    "3. **Smooth demand:** Redistribute peak demand to earlier/later days\n\n"
                    "**Cost impact:**\n"
                    "Weekend production has 4-hour minimum payments even if only 1 hour needed. "
                    "Consider batching weekend production to full days where possible."
                ).format(weekend_units_needed),
                metadata={
                    'weekend_units_needed': weekend_units_needed,
                    'weekend_days_needed': int(weekend_days_needed)
                }
            ))

        elif total_demand > regular_capacity:
            overtime_needed = total_demand - regular_capacity
            overtime_hours = overtime_needed / self.PRODUCTION_RATE
            overtime_pct = (total_demand - regular_capacity) / total_demand * 100

            self.issues.append(ValidationIssue(
                id="CAP_003",
                category="Capacity",
                severity=ValidationSeverity.WARNING,
                title="Demand requires overtime production",
                description=(
                    f"Total demand: {total_demand:,.0f} units\n"
                    f"Regular capacity: {regular_capacity:,.0f} units\n"
                    f"Overtime needed: {overtime_needed:,.0f} units ({overtime_pct:.1f}% of demand)\n"
                    f"Overtime hours: {overtime_hours:.1f} hours"
                ),
                impact=(
                    "Planning will use overtime (12-14h weekdays). Higher labor costs but feasible. "
                    f"Capacity utilization: {capacity_utilization:.1f}%"
                ),
                fix_guidance=(
                    "**This is normal for high demand periods.**\n\n"
                    "Overtime is built into the cost model. No action needed unless:\n"
                    "- Overtime percentage is very high (>30%)\n"
                    "- Labor availability is constrained\n\n"
                    "**To reduce overtime:**\n"
                    "1. Smooth demand spikes by building inventory early\n"
                    "2. Review forecast for data quality issues\n"
                    "3. Consider pre-building inventory before peak periods"
                ),
                metadata={
                    'overtime_units': overtime_needed,
                    'overtime_hours': overtime_hours,
                    'overtime_pct': overtime_pct,
                    'capacity_utilization': capacity_utilization
                }
            ))
        else:
            # Capacity is sufficient - this is good news!
            capacity_headroom = regular_capacity - total_demand
            self.issues.append(ValidationIssue(
                id="CAP_004",
                category="Capacity",
                severity=ValidationSeverity.INFO,
                title="Production capacity is sufficient",
                description=(
                    f"Total demand: {total_demand:,.0f} units\n"
                    f"Regular capacity: {regular_capacity:,.0f} units\n"
                    f"Capacity headroom: {capacity_headroom:,.0f} units ({capacity_headroom / regular_capacity * 100:.1f}%)\n"
                    f"Utilization: {total_demand / regular_capacity * 100:.1f}%"
                ),
                impact="Can meet demand within regular working hours (no overtime needed).",
                fix_guidance=(
                    "**Good news!** Demand fits comfortably within regular production capacity.\n\n"
                    "**Opportunities:**\n"
                    "- Consider accepting additional orders\n"
                    "- Build safety stock for future periods\n"
                    "- Smooth production to reduce daily peaks\n"
                ),
                metadata={
                    'capacity_headroom': capacity_headroom,
                    'utilization_pct': total_demand / regular_capacity * 100
                }
            ))

        # Check for daily capacity violations
        if self.forecast:
            daily_demand = {}
            for entry in self.forecast.entries:
                date = entry.forecast_date
                daily_demand[date] = daily_demand.get(date, 0) + entry.quantity

            peak_violations = []
            for date, demand in daily_demand.items():
                if demand > daily_max_capacity:
                    peak_violations.append({
                        'date': date,
                        'demand': demand,
                        'max_capacity': daily_max_capacity,
                        'excess': demand - daily_max_capacity
                    })

            if peak_violations:
                df = pd.DataFrame(peak_violations)
                df = df.sort_values('excess', ascending=False)

                self.issues.append(ValidationIssue(
                    id="CAP_005",
                    category="Capacity",
                    severity=ValidationSeverity.CRITICAL,
                    title="Daily demand exceeds maximum daily capacity",
                    description=(
                        f"Found {len(peak_violations)} days where demand exceeds 19,600 units/day.\n"
                        f"Worst day: {peak_violations[0]['date']} with {peak_violations[0]['demand']:,.0f} units "
                        f"({peak_violations[0]['excess']:,.0f} units over capacity)"
                    ),
                    impact="These days are impossible to produce even with full overtime. Planning will fail.",
                    fix_guidance=(
                        "**Critical issue - must resolve before planning:**\n\n"
                        "**Options:**\n"
                        "1. **Produce early:** Build inventory on preceding days (requires shelf life management)\n"
                        "2. **Reduce daily demand:** Adjust forecast to smooth demand spikes\n"
                        "3. **Split demand:** Spread demand across multiple days\n\n"
                        "**Root cause analysis:**\n"
                        "- Check for data entry errors in forecast\n"
                        "- Verify demand isn't double-counted\n"
                        "- Consider if promotional events can be staggered"
                    ),
                    affected_data=df.head(20)
                ))

    def check_transport_capacity(self):
        """Check if truck capacity is sufficient for demand."""

        if self.forecast is None or self.truck_schedules is None:
            return

        if len(self.truck_schedules) == 0:
            # No truck schedules defined - can't check capacity
            self.issues.append(ValidationIssue(
                id="TRANS_001",
                category="Transport",
                severity=ValidationSeverity.WARNING,
                title="No truck schedules to validate capacity",
                description="Cannot check transport capacity without truck schedule definition.",
                impact="Planning will assume unlimited trucks. Actual logistics may not be feasible.",
                fix_guidance=(
                    "**Recommendation:**\n"
                    "Define truck schedules in 'TruckSchedules' sheet to validate logistics feasibility.\n\n"
                    "Without schedules, planning assumes:\n"
                    "- Unlimited trucks available\n"
                    "- Instantaneous shipping\n"
                    "- No capacity constraints\n\n"
                    "This may produce plans that cannot be executed."
                )
            ))
            return

        # Calculate total demand
        total_demand = sum(entry.quantity for entry in self.forecast.entries)

        # Calculate weekly truck capacity
        # Count trucks per week (assuming normal weekly pattern)
        trucks_per_week = len([s for s in self.truck_schedules if s.day_of_week is not None])

        if trucks_per_week == 0:
            return  # Can't validate without day-specific schedules

        weekly_truck_capacity = trucks_per_week * self.TRUCK_CAPACITY

        # Get forecast duration in weeks
        forecast_dates = [entry.forecast_date for entry in self.forecast.entries]
        if not forecast_dates:
            return

        start_date = min(forecast_dates)
        end_date = max(forecast_dates)
        weeks = ((end_date - start_date).days + 1) / 7.0

        total_truck_capacity = weekly_truck_capacity * weeks

        if total_demand > total_truck_capacity:
            shortfall = total_demand - total_truck_capacity
            shortfall_pct = shortfall / total_demand * 100

            self.issues.append(ValidationIssue(
                id="TRANS_002",
                category="Transport",
                severity=ValidationSeverity.ERROR,
                title="Demand exceeds available truck capacity",
                description=(
                    f"Total demand: {total_demand:,.0f} units\n"
                    f"Total truck capacity: {total_truck_capacity:,.0f} units\n"
                    f"Shortfall: {shortfall:,.0f} units ({shortfall_pct:.1f}%)\n"
                    f"Trucks per week: {trucks_per_week}\n"
                    f"Planning weeks: {weeks:.1f}"
                ),
                impact="Cannot ship all demand with current truck schedule. Planning may be infeasible.",
                fix_guidance=(
                    "**Options to resolve:**\n"
                    "1. **Add truck capacity:** Schedule additional trucks\n"
                    "2. **Reduce demand:** Adjust forecast to match logistics capacity\n"
                    "3. **Use larger trucks:** Increase truck capacity (currently 14,080 units/truck)\n"
                    "4. **Extend planning horizon:** Spread demand over more weeks\n\n"
                    "**Quick calculation:**\n"
                    f"Need {np.ceil(shortfall / self.TRUCK_CAPACITY):.0f} additional truck trips to cover shortfall"
                ),
                metadata={
                    'shortfall': shortfall,
                    'shortfall_pct': shortfall_pct,
                    'additional_trucks_needed': int(np.ceil(shortfall / self.TRUCK_CAPACITY))
                }
            ))
        elif total_demand > total_truck_capacity * 0.85:
            # High utilization - warn about limited flexibility
            utilization = total_demand / total_truck_capacity * 100

            self.issues.append(ValidationIssue(
                id="TRANS_003",
                category="Transport",
                severity=ValidationSeverity.WARNING,
                title="High truck capacity utilization",
                description=(
                    f"Truck utilization: {utilization:.1f}%\n"
                    f"Total demand: {total_demand:,.0f} units\n"
                    f"Total truck capacity: {total_truck_capacity:,.0f} units\n"
                    f"Remaining capacity: {total_truck_capacity - total_demand:,.0f} units"
                ),
                impact="Limited flexibility for demand variations or routing constraints. May need precise scheduling.",
                fix_guidance=(
                    "**Considerations:**\n"
                    "- Minimal slack for disruptions or demand changes\n"
                    "- Efficient routing and loading critical\n"
                    "- Consider buffer capacity for robustness\n\n"
                    "**Risk mitigation:**\n"
                    "1. Identify backup truck options\n"
                    "2. Monitor forecast changes closely\n"
                    "3. Optimize pallet loading to maximize truck fill"
                ),
                metadata={'utilization_pct': utilization}
            ))

    def check_shelf_life(self):
        """Validate routes comply with shelf life constraints."""

        if self.routes is None:
            return

        # Check for routes with excessive transit times
        long_routes = []

        for route in self.routes:
            if route.transit_time_days > self.MAX_SAFE_TRANSIT_DAYS:
                long_routes.append({
                    'origin_id': route.origin_id,
                    'destination_id': route.destination_id,
                    'transit_time_days': route.transit_time_days,
                    'transport_mode': route.transport_mode.name if route.transport_mode else None,
                    'excess_days': route.transit_time_days - self.MAX_SAFE_TRANSIT_DAYS
                })

        if long_routes:
            df = pd.DataFrame(long_routes)
            df = df.sort_values('transit_time_days', ascending=False)

            self.issues.append(ValidationIssue(
                id="SHELF_001",
                category="Shelf Life",
                severity=ValidationSeverity.WARNING,
                title="Routes with excessive transit times",
                description=(
                    f"Found {len(long_routes)} routes with transit time > {self.MAX_SAFE_TRANSIT_DAYS} days.\n"
                    f"Longest route: {long_routes[0]['origin_id']} → {long_routes[0]['destination_id']} "
                    f"({long_routes[0]['transit_time_days']} days)"
                ),
                impact=(
                    f"Ambient products have {self.AMBIENT_SHELF_LIFE_DAYS}-day shelf life. "
                    f"Long transit leaves only {self.AMBIENT_SHELF_LIFE_DAYS - long_routes[0]['transit_time_days']} days at destination.\n"
                    f"Breadrooms discard stock with <{self.BREADROOM_MIN_SHELF_LIFE_DAYS} days remaining."
                ),
                fix_guidance=(
                    "**Options:**\n"
                    "1. **Use frozen transport:** Ship frozen and thaw at destination (if supported)\n"
                    "2. **Review transit times:** Verify route data accuracy\n"
                    "3. **Use intermediate hubs:** Break long routes into shorter segments\n"
                    "4. **Expedite shipping:** Use faster transport modes\n\n"
                    "**Special considerations:**\n"
                    "- WA route (to 6130) should use frozen → thawed transition\n"
                    "- Thawed shelf life: 14 days after thawing\n"
                    "- Check if intermediate storage (Lineage) is available"
                ),
                affected_data=df
            ))

        # Check for destinations that might need frozen transport
        if self.forecast:
            # Get destinations from forecast
            forecast_destinations = {entry.location_id for entry in self.forecast.entries}

            # Check each destination's best route transit time
            risky_destinations = []

            for dest_id in forecast_destinations:
                # Find shortest route to this destination
                routes_to_dest = [r for r in self.routes if r.destination_id == dest_id]

                if routes_to_dest:
                    min_transit = min(r.transit_time_days for r in routes_to_dest)

                    remaining_shelf_life = self.AMBIENT_SHELF_LIFE_DAYS - min_transit

                    if remaining_shelf_life < self.BREADROOM_MIN_SHELF_LIFE_DAYS:
                        risky_destinations.append({
                            'destination_id': dest_id,
                            'min_transit_days': min_transit,
                            'remaining_shelf_life_days': remaining_shelf_life,
                            'days_short': self.BREADROOM_MIN_SHELF_LIFE_DAYS - remaining_shelf_life
                        })

            if risky_destinations:
                df = pd.DataFrame(risky_destinations)
                df = df.sort_values('days_short', ascending=False)

                self.issues.append(ValidationIssue(
                    id="SHELF_002",
                    category="Shelf Life",
                    severity=ValidationSeverity.ERROR,
                    title="Destinations cannot receive ambient product with adequate shelf life",
                    description=(
                        f"Found {len(risky_destinations)} destinations where even fastest route "
                        f"leaves <{self.BREADROOM_MIN_SHELF_LIFE_DAYS} days shelf life."
                    ),
                    impact="These destinations must receive frozen product or planning will waste inventory.",
                    fix_guidance=(
                        "**Critical for these destinations:**\n"
                        "Must use frozen transport and thaw at destination.\n\n"
                        "**Implementation:**\n"
                        "1. Configure frozen routes in network\n"
                        "2. Add thawing capability at destination\n"
                        "3. Shelf life resets to 14 days after thawing\n\n"
                        "**Known special case:**\n"
                        "- Location 6130 (WA) requires frozen → thawed transition\n"
                        "- Ships frozen via Lineage intermediate storage\n"
                        "- Thaws on-site at breadroom"
                    ),
                    affected_data=df
                ))

    def check_date_ranges(self):
        """Validate date ranges and calendar coverage."""

        if self.forecast is None:
            return

        forecast_dates = [entry.forecast_date for entry in self.forecast.entries]
        if not forecast_dates:
            return

        forecast_start = min(forecast_dates)
        forecast_end = max(forecast_dates)
        today = datetime.now().date()

        # Check if forecast starts in the past
        if forecast_start < today - timedelta(days=7):
            days_old = (today - forecast_start).days

            self.issues.append(ValidationIssue(
                id="DATE_001",
                category="Date Range",
                severity=ValidationSeverity.WARNING,
                title="Forecast starts significantly in the past",
                description=(
                    f"Forecast start date: {forecast_start}\n"
                    f"Today: {today}\n"
                    f"Days in past: {days_old}"
                ),
                impact="May be planning for demand that has already occurred. Check if data is current.",
                fix_guidance=(
                    "**Verify data currency:**\n"
                    "1. Check if forecast file is the latest version\n"
                    "2. Confirm forecast is meant to be historical\n"
                    "3. Consider filtering out past dates if planning forward\n\n"
                    "**If intentional:**\n"
                    "- Historical analysis: No action needed\n"
                    "- Catch-up production: Ensure labor calendar covers period"
                ),
                metadata={'days_old': days_old}
            ))

        # Check labor calendar coverage
        if self.labor_calendar:
            labor_dates = [day.date for day in self.labor_calendar.days]

            if labor_dates:
                labor_start = min(labor_dates)
                labor_end = max(labor_dates)

                # Check for gaps in coverage
                missing_start = []
                missing_end = []

                if forecast_start < labor_start:
                    missing_days = (labor_start - forecast_start).days
                    missing_start = [forecast_start, labor_start, missing_days]

                if forecast_end > labor_end:
                    missing_days = (forecast_end - labor_end).days
                    missing_end = [labor_end, forecast_end, missing_days]

                if missing_start or missing_end:
                    description_parts = []
                    if missing_start:
                        description_parts.append(
                            f"Missing start: {missing_start[0]} to {missing_start[1]} ({missing_start[2]} days)"
                        )
                    if missing_end:
                        description_parts.append(
                            f"Missing end: {missing_end[0]} to {missing_end[1]} ({missing_end[2]} days)"
                        )

                    self.issues.append(ValidationIssue(
                        id="DATE_002",
                        category="Date Range",
                        severity=ValidationSeverity.ERROR,
                        title="Labor calendar does not cover full forecast period",
                        description="\n".join(description_parts),
                        impact="Cannot calculate labor costs or production capacity for dates outside calendar.",
                        fix_guidance=(
                            "**How to fix:**\n"
                            "1. Extend 'LaborCalendar' sheet to cover forecast period\n"
                            "2. OR trim forecast to match calendar dates\n\n"
                            "**Calendar requirements:**\n"
                            f"- Must start on or before: {forecast_start}\n"
                            f"- Must end on or after: {forecast_end}\n"
                            f"- Should include buffer days for transit times"
                        ),
                        metadata={
                            'forecast_start': forecast_start,
                            'forecast_end': forecast_end,
                            'labor_start': labor_start,
                            'labor_end': labor_end
                        }
                    ))

        # Check for reasonable planning horizon
        planning_days = (forecast_end - forecast_start).days + 1

        if planning_days < 7:
            self.issues.append(ValidationIssue(
                id="DATE_003",
                category="Date Range",
                severity=ValidationSeverity.WARNING,
                title="Very short planning horizon",
                description=f"Planning horizon: {planning_days} days",
                impact="Short horizon limits optimization opportunities and may not account for transit times.",
                fix_guidance=(
                    "**Recommendations:**\n"
                    "- Minimum 7 days for weekly planning\n"
                    "- 14-30 days recommended for better optimization\n"
                    "- Must exceed longest transit time in network\n\n"
                    "**Consider extending horizon to:**\n"
                    "- Allow production smoothing\n"
                    "- Build strategic inventory\n"
                    "- Account for transit and shelf life"
                )
            ))
        elif planning_days > 365:
            self.issues.append(ValidationIssue(
                id="DATE_004",
                category="Date Range",
                severity=ValidationSeverity.INFO,
                title="Very long planning horizon",
                description=f"Planning horizon: {planning_days} days ({planning_days / 365:.1f} years)",
                impact="Long horizon increases problem complexity. Consider rolling horizon approach.",
                fix_guidance=(
                    "**For horizons >1 year:**\n"
                    "- Consider rolling horizon planning (plan 4-6 weeks, re-plan weekly)\n"
                    "- Use aggregate planning for distant periods\n"
                    "- Focus detailed planning on near-term (next 30-60 days)\n\n"
                    "**Computational considerations:**\n"
                    "- Longer horizons take more time to solve\n"
                    "- Forecast accuracy degrades over time\n"
                    "- Frequent re-planning may be more effective"
                ),
                metadata={'planning_days': planning_days}
            ))

    def check_data_quality(self):
        """Check for data quality issues like outliers and anomalies."""

        if self.forecast is None or len(self.forecast.entries) == 0:
            return

        # Analyze forecast quantities
        quantities = [entry.quantity for entry in self.forecast.entries]

        if not quantities:
            return

        mean_qty = np.mean(quantities)
        std_qty = np.std(quantities)
        median_qty = np.median(quantities)

        # Check for outliers (>3 standard deviations from mean)
        outliers = []
        for entry in self.forecast.entries:
            if std_qty > 0 and abs(entry.quantity - mean_qty) > 3 * std_qty:
                z_score = (entry.quantity - mean_qty) / std_qty
                outliers.append({
                    'location_id': entry.location_id,
                    'product_id': entry.product_id,
                    'date': entry.forecast_date,
                    'quantity': entry.quantity,
                    'z_score': z_score,
                    'deviation_from_mean': entry.quantity - mean_qty
                })

        if outliers:
            df = pd.DataFrame(outliers)
            df = df.sort_values('z_score', ascending=False, key=abs)

            self.issues.append(ValidationIssue(
                id="QUAL_001",
                category="Data Quality",
                severity=ValidationSeverity.WARNING,
                title="Outlier values detected in forecast",
                description=(
                    f"Found {len(outliers)} forecast entries >3 standard deviations from mean.\n"
                    f"Mean: {mean_qty:.1f}, Std Dev: {std_qty:.1f}, Median: {median_qty:.1f}"
                ),
                impact="Outliers may indicate data errors or genuine demand spikes. Review for accuracy.",
                fix_guidance=(
                    "**Review these entries carefully:**\n"
                    "1. Verify quantities are correct (not typos)\n"
                    "2. Check for unit mismatches (cases vs. units)\n"
                    "3. Confirm promotional events or special orders\n"
                    "4. Look for duplicate entries\n\n"
                    "**Common causes:**\n"
                    "- Data entry error (extra zero: 1000 instead of 100)\n"
                    "- Unit confusion (pallets entered as units)\n"
                    "- Duplicate records\n"
                    "- Legitimate large orders (validate with sales team)"
                ),
                affected_data=df.head(20)
            ))

        # Check for zero or negative quantities
        invalid_quantities = []
        for entry in self.forecast.entries:
            if entry.quantity <= 0:
                invalid_quantities.append({
                    'location_id': entry.location_id,
                    'product_id': entry.product_id,
                    'date': entry.forecast_date,
                    'quantity': entry.quantity
                })

        if invalid_quantities:
            df = pd.DataFrame(invalid_quantities)

            self.issues.append(ValidationIssue(
                id="QUAL_002",
                category="Data Quality",
                severity=ValidationSeverity.WARNING,
                title="Zero or negative quantities in forecast",
                description=f"Found {len(invalid_quantities)} forecast entries with quantity ≤ 0",
                impact="These entries will be ignored in planning. May indicate data quality issues.",
                fix_guidance=(
                    "**Action needed:**\n"
                    "1. Remove entries with zero quantity (no demand)\n"
                    "2. Correct negative quantities (likely data errors)\n"
                    "3. Verify these aren't placeholders or test data\n\n"
                    "**Clean data approach:**\n"
                    "- Filter out zero-demand entries before upload\n"
                    "- Investigate source of negative values\n"
                    "- Validate data export process"
                ),
                affected_data=df.head(50)
            ))

        # Check for non-case quantities (should be multiples of 10)
        non_case_quantities = []
        for entry in self.forecast.entries:
            if entry.quantity % self.CASE_SIZE != 0:
                non_case_quantities.append({
                    'location_id': entry.location_id,
                    'product_id': entry.product_id,
                    'date': entry.forecast_date,
                    'quantity': entry.quantity,
                    'remainder': entry.quantity % self.CASE_SIZE,
                    'rounded_up': ((entry.quantity // self.CASE_SIZE) + 1) * self.CASE_SIZE,
                    'rounded_down': (entry.quantity // self.CASE_SIZE) * self.CASE_SIZE
                })

        if non_case_quantities:
            df = pd.DataFrame(non_case_quantities)

            self.issues.append(ValidationIssue(
                id="QUAL_003",
                category="Data Quality",
                severity=ValidationSeverity.INFO,
                title="Forecast quantities not in full cases",
                description=(
                    f"Found {len(non_case_quantities)} entries not in multiples of {self.CASE_SIZE} (case size).\n"
                    "Planning will round to nearest case."
                ),
                impact="Minor rounding will occur. Actual production will differ slightly from forecast.",
                fix_guidance=(
                    "**This is informational - no action required.**\n\n"
                    "Production and shipping require full cases (10 units).\n"
                    "Planning will automatically round:\n"
                    "- Up: To ensure demand is met (conservative)\n"
                    "- Down: If minimizing overproduction\n\n"
                    "**To avoid rounding:**\n"
                    "Pre-round forecast to case quantities before upload."
                ),
                affected_data=df.head(30)
            ))

    def check_business_rules(self):
        """Validate compliance with business rules and constraints."""

        # Check manufacturing site configuration
        if self.manufacturing_site:
            site = self.manufacturing_site

            # Validate production rate
            if site.production_rate != self.PRODUCTION_RATE:
                self.issues.append(ValidationIssue(
                    id="RULE_001",
                    category="Business Rules",
                    severity=ValidationSeverity.WARNING,
                    title="Non-standard production rate",
                    description=(
                        f"Manufacturing site production rate: {site.production_rate} units/hour\n"
                        f"Standard rate: {self.PRODUCTION_RATE} units/hour"
                    ),
                    impact="Capacity calculations may differ from standard assumptions.",
                    fix_guidance=(
                        "**Verify production rate is correct:**\n"
                        "1. Confirm with manufacturing team\n"
                        "2. Update manufacturing site configuration if needed\n"
                        "3. Ensure rate reflects actual throughput\n\n"
                        "**Standard rate: 1,400 units/hour**\n"
                        "Adjust if equipment has been upgraded or changed."
                    )
                ))

        # Check for weekend schedules
        if self.labor_calendar:
            weekend_days_with_hours = []

            for day in self.labor_calendar.days:
                if day.date.weekday() in [5, 6]:  # Saturday=5, Sunday=6
                    if day.fixed_hours > 0:
                        weekend_days_with_hours.append({
                            'date': day.date,
                            'day_of_week': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][day.date.weekday()],
                            'fixed_hours': day.fixed_hours,
                            'cost_per_hour': day.cost_per_non_fixed_hour or day.cost_per_fixed_hour
                        })

            if weekend_days_with_hours:
                df = pd.DataFrame(weekend_days_with_hours)

                self.issues.append(ValidationIssue(
                    id="RULE_002",
                    category="Business Rules",
                    severity=ValidationSeverity.INFO,
                    title="Weekend days have fixed hours scheduled",
                    description=(
                        f"Found {len(weekend_days_with_hours)} weekend days with fixed_hours > 0.\n"
                        "Standard rule: Weekends use overtime-only (4-hour minimum payment)."
                    ),
                    impact="May affect labor cost calculations. Verify this is intentional.",
                    fix_guidance=(
                        "**Standard weekend labor model:**\n"
                        "- fixed_hours = 0 (no standard shift)\n"
                        "- Use cost_per_non_fixed_hour for premium rate\n"
                        "- 4-hour minimum payment applies\n\n"
                        "**If weekend shifts are standard:**\n"
                        "This is acceptable if regular weekend operations are planned.\n"
                        "Ensure costs reflect premium weekend rates."
                    ),
                    affected_data=df
                ))

        # Check for network connectivity
        if self.locations and self.routes:
            # Find manufacturing location
            mfg_locations = [loc for loc in self.locations if loc.type == LocationType.MANUFACTURING]

            if mfg_locations:
                mfg_id = mfg_locations[0].id

                # Get all destinations from forecast
                if self.forecast:
                    forecast_destinations = {entry.location_id for entry in self.forecast.entries}

                    # Check which destinations are not directly reachable
                    direct_destinations = {r.destination_id for r in self.routes if r.origin_id == mfg_id}
                    unreachable = forecast_destinations - direct_destinations

                    # Filter out the manufacturing location itself
                    unreachable = unreachable - {mfg_id}

                    if unreachable:
                        # Check if reachable via hub (2-echelon)
                        all_destinations = {r.destination_id for r in self.routes}
                        hub_candidates = direct_destinations & all_destinations

                        indirectly_reachable = set()
                        for hub_id in hub_candidates:
                            hub_destinations = {r.destination_id for r in self.routes if r.origin_id == hub_id}
                            indirectly_reachable.update(hub_destinations & unreachable)

                        truly_unreachable = unreachable - indirectly_reachable

                        if truly_unreachable:
                            self.issues.append(ValidationIssue(
                                id="RULE_003",
                                category="Business Rules",
                                severity=ValidationSeverity.CRITICAL,
                                title="Forecast destinations not reachable from manufacturing",
                                description=(
                                    f"Found {len(truly_unreachable)} destinations in forecast with no route from manufacturing.\n"
                                    f"Unreachable locations: {list(truly_unreachable)}"
                                ),
                                impact="Cannot plan distribution to these destinations. Demand cannot be satisfied.",
                                fix_guidance=(
                                    "**Critical - must add routes:**\n"
                                    "1. Add direct routes: Manufacturing → Destination\n"
                                    "2. OR add 2-echelon routes: Manufacturing → Hub → Destination\n"
                                    "3. Verify location IDs are correct\n\n"
                                    "**Hub-and-spoke model:**\n"
                                    "- Regional hubs: 6104 (NSW/ACT), 6125 (VIC/TAS/SA)\n"
                                    "- Define routes from manufacturing to hubs\n"
                                    "- Define routes from hubs to final destinations"
                                ),
                                metadata={'unreachable_locations': list(truly_unreachable)}
                            ))

                        if indirectly_reachable:
                            self.issues.append(ValidationIssue(
                                id="RULE_004",
                                category="Business Rules",
                                severity=ValidationSeverity.INFO,
                                title="Destinations require multi-echelon routing",
                                description=(
                                    f"Found {len(indirectly_reachable)} destinations reachable only via hubs.\n"
                                    f"Hub-routed locations: {list(indirectly_reachable)[:5]}"
                                    + (f" and {len(indirectly_reachable) - 5} more" if len(indirectly_reachable) > 5 else "")
                                ),
                                impact="These destinations will use 2-echelon distribution (higher cost, longer transit).",
                                fix_guidance=(
                                    "**This is normal for hub-and-spoke networks.**\n\n"
                                    "Multi-echelon distribution:\n"
                                    "- Manufacturing → Hub → Final destination\n"
                                    "- Higher transport cost (two legs)\n"
                                    "- Longer transit time\n"
                                    "- May require inventory at hub\n\n"
                                    "**To reduce cost:**\n"
                                    "Consider direct routes if volume justifies dedicated trucks."
                                ),
                                metadata={'hub_routed_locations': list(indirectly_reachable)}
                            ))

        # Check pallet optimization potential
        if self.forecast:
            total_demand = sum(entry.quantity for entry in self.forecast.entries)

            # Calculate how much demand is not pallet-aligned
            non_pallet_aligned = total_demand % self.PALLET_SIZE
            pallets_needed = int(np.ceil(total_demand / self.PALLET_SIZE))
            wasted_space = (pallets_needed * self.PALLET_SIZE) - total_demand

            if wasted_space > total_demand * 0.05:  # More than 5% waste
                self.issues.append(ValidationIssue(
                    id="RULE_005",
                    category="Business Rules",
                    severity=ValidationSeverity.INFO,
                    title="Significant pallet space waste detected",
                    description=(
                        f"Total demand: {total_demand:,.0f} units\n"
                        f"Pallets needed: {pallets_needed:,}\n"
                        f"Pallet capacity: {pallets_needed * self.PALLET_SIZE:,.0f} units\n"
                        f"Wasted space: {wasted_space:,.0f} units ({wasted_space / total_demand * 100:.1f}%)"
                    ),
                    impact="Partial pallets waste truck space. Consider adjusting quantities for better utilization.",
                    fix_guidance=(
                        "**Pallet optimization:**\n"
                        f"- Full pallet: {self.PALLET_SIZE} units (32 cases)\n"
                        f"- Full truck: {self.TRUCK_CAPACITY} units (44 pallets)\n\n"
                        "**To improve efficiency:**\n"
                        "1. Round shipments to pallet multiples where possible\n"
                        "2. Combine small orders to full pallets\n"
                        "3. Consider minimum order quantities\n\n"
                        "**Note:** This is informational. Planning will handle partial pallets."
                    ),
                    metadata={
                        'wasted_units': wasted_space,
                        'waste_pct': wasted_space / total_demand * 100
                    }
                ))

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of validation results.

        Returns:
            Dictionary with counts by severity and category
        """
        stats = {
            'total_issues': len(self.issues),
            'by_severity': {
                'info': len([i for i in self.issues if i.severity == ValidationSeverity.INFO]),
                'warning': len([i for i in self.issues if i.severity == ValidationSeverity.WARNING]),
                'error': len([i for i in self.issues if i.severity == ValidationSeverity.ERROR]),
                'critical': len([i for i in self.issues if i.severity == ValidationSeverity.CRITICAL]),
            },
            'by_category': {}
        }

        # Count by category
        for issue in self.issues:
            category = issue.category
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

        return stats

    def has_critical_issues(self) -> bool:
        """Check if any critical issues exist.

        Returns:
            True if any critical issues found
        """
        return any(i.severity == ValidationSeverity.CRITICAL for i in self.issues)

    def has_errors_or_critical(self) -> bool:
        """Check if any errors or critical issues exist.

        Returns:
            True if any error or critical issues found
        """
        return any(i.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
                  for i in self.issues)

    def is_planning_feasible(self) -> bool:
        """Determine if planning is feasible given validation results.

        Returns:
            True if no critical issues that would prevent planning
        """
        return not self.has_critical_issues()
