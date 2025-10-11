"""Utilities for packaging constraint testing.

This module provides reusable fixtures, validators, and helpers for testing
packaging constraints across different optimization models.
"""

from typing import Dict, List, Tuple, Optional, Any
from datetime import date, timedelta

from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.truck_schedule import TruckSchedule, TruckScheduleCollection


# ============================================================================
# Packaging Constants
# ============================================================================

UNITS_PER_CASE = 10
CASES_PER_PALLET = 32
UNITS_PER_PALLET = 320  # 10 * 32
PALLETS_PER_TRUCK = 44
UNITS_PER_TRUCK = 14080  # 320 * 44


# ============================================================================
# Validation Functions
# ============================================================================

def validate_case_constraints(
    production_values: Dict[Tuple[date, str], float],
    tolerance: float = 1e-6
) -> Dict[str, Any]:
    """
    Validate that all production values are multiples of 10 (whole cases).

    Args:
        production_values: Dictionary mapping (date, product_id) to quantity
        tolerance: Floating point tolerance for remainder checking

    Returns:
        Dictionary with validation results:
        - is_valid: True if all values are case multiples
        - violations: List of violation details
        - total_violations: Count of violations
        - summary: Human-readable summary
    """
    violations = []

    for (prod_date, product_id), quantity in production_values.items():
        if quantity > tolerance:  # Only check non-zero production
            remainder = quantity % UNITS_PER_CASE
            if remainder > tolerance:
                violations.append({
                    'date': prod_date,
                    'product': product_id,
                    'quantity': quantity,
                    'remainder': remainder,
                    'expected_rounded_up': quantity + (UNITS_PER_CASE - remainder),
                    'expected_rounded_down': quantity - remainder,
                })

    is_valid = len(violations) == 0

    return {
        'is_valid': is_valid,
        'violations': violations,
        'total_violations': len(violations),
        'summary': f"{'PASS' if is_valid else 'FAIL'}: {len(violations)} case constraint violations",
    }


def validate_pallet_constraints(
    shipment_values: Dict[Any, float],
    truck_capacity_pallets: int = PALLETS_PER_TRUCK,
    tolerance: float = 1e-6
) -> Dict[str, Any]:
    """
    Validate that shipments respect pallet capacity constraints.

    Args:
        shipment_values: Dictionary mapping shipment keys to quantities
        truck_capacity_pallets: Maximum pallets per truck
        tolerance: Floating point tolerance

    Returns:
        Dictionary with validation results including pallet calculations
    """
    violations = []
    pallet_details = []

    for key, quantity in shipment_values.items():
        if quantity > tolerance:
            # Calculate pallets needed (ceiling division for partial pallets)
            pallets_needed = -(-int(quantity) // UNITS_PER_PALLET)
            full_pallets = int(quantity) // UNITS_PER_PALLET
            partial_pallet_units = int(quantity) % UNITS_PER_PALLET

            details = {
                'key': key,
                'quantity': quantity,
                'pallets_needed': pallets_needed,
                'full_pallets': full_pallets,
                'partial_pallet_units': partial_pallet_units,
                'wasted_units': (UNITS_PER_PALLET - partial_pallet_units) if partial_pallet_units > 0 else 0,
                'efficiency_pct': (quantity / (pallets_needed * UNITS_PER_PALLET)) * 100,
            }

            pallet_details.append(details)

            # Check if exceeds truck capacity
            if pallets_needed > truck_capacity_pallets:
                violations.append({
                    **details,
                    'truck_capacity': truck_capacity_pallets,
                    'excess_pallets': pallets_needed - truck_capacity_pallets,
                })

    is_valid = len(violations) == 0

    return {
        'is_valid': is_valid,
        'violations': violations,
        'total_violations': len(violations),
        'pallet_details': pallet_details,
        'summary': f"{'PASS' if is_valid else 'FAIL'}: {len(violations)} truck capacity violations",
    }


def calculate_pallet_efficiency(quantity: float) -> Dict[str, Any]:
    """
    Calculate pallet packing efficiency for a given quantity.

    Args:
        quantity: Number of units to ship

    Returns:
        Dictionary with efficiency metrics
    """
    if quantity <= 0:
        return {
            'quantity': 0,
            'cases': 0,
            'full_pallets': 0,
            'partial_pallet_cases': 0,
            'total_pallets': 0,
            'wasted_pallet_space': 0,
            'efficiency_pct': 0,
        }

    cases = quantity / UNITS_PER_CASE
    full_pallets = int(cases // CASES_PER_PALLET)
    partial_pallet_cases = cases % CASES_PER_PALLET
    total_pallets = full_pallets + (1 if partial_pallet_cases > 0 else 0)
    wasted_pallet_space = (CASES_PER_PALLET - partial_pallet_cases) if partial_pallet_cases > 0 else 0
    efficiency = (cases / (total_pallets * CASES_PER_PALLET)) * 100 if total_pallets > 0 else 0

    return {
        'quantity': quantity,
        'cases': cases,
        'full_pallets': full_pallets,
        'partial_pallet_cases': partial_pallet_cases,
        'total_pallets': total_pallets,
        'wasted_pallet_space': wasted_pallet_space,
        'efficiency_pct': efficiency,
    }


def validate_solution_packaging(
    solution: Dict[str, Any],
    check_production: bool = True,
    check_shipments: bool = True,
    truck_capacity: int = PALLETS_PER_TRUCK
) -> Dict[str, Any]:
    """
    Comprehensive validation of packaging constraints in a solution.

    Args:
        solution: Optimization solution dictionary
        check_production: Whether to validate production case constraints
        check_shipments: Whether to validate shipment pallet constraints
        truck_capacity: Maximum pallets per truck

    Returns:
        Comprehensive validation results
    """
    results = {
        'overall_valid': True,
        'production_validation': None,
        'shipment_validation': None,
    }

    # Validate production (case constraints)
    if check_production and 'production_by_date_product' in solution:
        production = solution['production_by_date_product']
        prod_validation = validate_case_constraints(production)
        results['production_validation'] = prod_validation

        if not prod_validation['is_valid']:
            results['overall_valid'] = False

    # Validate shipments (pallet constraints)
    if check_shipments and 'shipments' in solution:
        shipments = {i: s.get('quantity', 0) for i, s in enumerate(solution['shipments'])}
        ship_validation = validate_pallet_constraints(shipments, truck_capacity)
        results['shipment_validation'] = ship_validation

        if not ship_validation['is_valid']:
            results['overall_valid'] = False

    return results


def print_validation_report(validation_results: Dict[str, Any]) -> None:
    """
    Print human-readable validation report.

    Args:
        validation_results: Results from validate_solution_packaging()
    """
    print("=" * 70)
    print("PACKAGING CONSTRAINT VALIDATION REPORT")
    print("=" * 70)

    overall = "PASS ✓" if validation_results['overall_valid'] else "FAIL ✗"
    print(f"\nOverall Status: {overall}")

    # Production validation
    if validation_results['production_validation']:
        print("\n" + "-" * 70)
        print("PRODUCTION - Case Constraints (10-unit multiples)")
        print("-" * 70)

        prod_val = validation_results['production_validation']
        print(f"Status: {prod_val['summary']}")

        if prod_val['violations']:
            print(f"\nViolations detected: {prod_val['total_violations']}")
            for v in prod_val['violations'][:10]:  # Show first 10
                print(f"  - {v['date']} {v['product']}: {v['quantity']} units "
                      f"(remainder: {v['remainder']:.2f})")
            if prod_val['total_violations'] > 10:
                print(f"  ... and {prod_val['total_violations'] - 10} more")

    # Shipment validation
    if validation_results['shipment_validation']:
        print("\n" + "-" * 70)
        print("SHIPMENTS - Pallet Constraints (44 pallets max per truck)")
        print("-" * 70)

        ship_val = validation_results['shipment_validation']
        print(f"Status: {ship_val['summary']}")

        if ship_val['violations']:
            print(f"\nViolations detected: {ship_val['total_violations']}")
            for v in ship_val['violations'][:10]:
                print(f"  - Shipment {v['key']}: {v['quantity']} units = "
                      f"{v['pallets_needed']} pallets "
                      f"(exceeds {v['truck_capacity']} by {v['excess_pallets']})")

        # Show efficiency summary
        if ship_val['pallet_details']:
            avg_efficiency = sum(d['efficiency_pct'] for d in ship_val['pallet_details']) / len(ship_val['pallet_details'])
            print(f"\nPallet Packing Efficiency: {avg_efficiency:.1f}% average")

    print("=" * 70)


# ============================================================================
# Test Data Generators
# ============================================================================

def generate_forecast(
    start_date: date,
    days: int,
    locations: List[str],
    products: List[str],
    base_demand: float = 1000,
    variation: float = 0.2,
    case_aligned: bool = False
) -> Forecast:
    """
    Generate test forecast with configurable parameters.

    Args:
        start_date: First forecast date
        days: Number of days to forecast
        locations: List of location IDs
        products: List of product IDs
        base_demand: Base daily demand per product
        variation: Demand variation factor (0.0 to 1.0)
        case_aligned: If True, round all demands to case multiples

    Returns:
        Forecast object
    """
    entries = []

    for day in range(days):
        forecast_date = start_date + timedelta(days=day)

        for loc_id in locations:
            for prod_id in products:
                # Add some variation
                demand = base_demand * (1.0 + variation * ((day % 7) / 7.0 - 0.5))

                # Round to case multiple if requested
                if case_aligned:
                    demand = (demand // UNITS_PER_CASE) * UNITS_PER_CASE

                entries.append(
                    ForecastEntry(
                        location_id=loc_id,
                        product_id=prod_id,
                        forecast_date=forecast_date,
                        quantity=demand
                    )
                )

    return Forecast(name="Generated Test Forecast", entries=entries)


def generate_labor_calendar(
    start_date: date,
    days: int,
    weekday_hours: float = 12.0,
    weekend_min_hours: float = 4.0,
    regular_rate: float = 50.0,
    overtime_rate: float = 75.0,
    weekend_rate: float = 100.0
) -> LaborCalendar:
    """
    Generate labor calendar for testing.

    Args:
        start_date: First calendar date
        days: Number of days
        weekday_hours: Fixed hours on weekdays
        weekend_min_hours: Minimum hours on weekends
        regular_rate: Weekday regular rate
        overtime_rate: Weekday overtime rate
        weekend_rate: Weekend rate

    Returns:
        LaborCalendar object
    """
    calendar_days = []

    for i in range(days):
        current_date = start_date + timedelta(days=i)
        day_of_week = current_date.weekday()

        if day_of_week < 5:  # Monday-Friday
            day = LaborDay(
                date=current_date,
                fixed_hours=weekday_hours,
                regular_rate=regular_rate,
                overtime_rate=overtime_rate,
                is_fixed_day=True,
            )
        else:  # Weekend
            day = LaborDay(
                date=current_date,
                fixed_hours=0.0,
                regular_rate=regular_rate,
                overtime_rate=overtime_rate,
                non_fixed_rate=weekend_rate,
                is_fixed_day=False,
                minimum_hours=weekend_min_hours,
            )

        calendar_days.append(day)

    return LaborCalendar(name="Generated Labor Calendar", days=calendar_days)


def generate_simple_network(
    manufacturing_id: str = "6122",
    hub_ids: Optional[List[str]] = None,
    destination_ids: Optional[List[str]] = None,
    include_frozen_routes: bool = False
) -> Dict[str, Any]:
    """
    Generate simple network topology for testing.

    Args:
        manufacturing_id: Manufacturing site location ID
        hub_ids: List of hub location IDs
        destination_ids: List of destination location IDs
        include_frozen_routes: Whether to include frozen alternatives

    Returns:
        Dictionary with 'locations' and 'routes' lists
    """
    if hub_ids is None:
        hub_ids = ["6104"]
    if destination_ids is None:
        destination_ids = ["6100"]

    locations = []
    routes = []

    # Manufacturing site
    manufacturing = ManufacturingSite(
        id=manufacturing_id,
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
        production_rate=1400.0,
        max_daily_capacity=19600.0,
    )
    locations.append(manufacturing)

    # Hubs
    for hub_id in hub_ids:
        hub = Location(
            id=hub_id,
            name=f"Hub {hub_id}",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
        )
        locations.append(hub)

        # Manufacturing to hub route
        routes.append(
            Route(
                id=f"R_MFG_{hub_id}",
                origin_id=manufacturing_id,
                destination_id=hub_id,
                transport_mode=StorageMode.AMBIENT,
                transit_time_days=1.0,
                cost=0.10,
            )
        )

        if include_frozen_routes:
            routes.append(
                Route(
                    id=f"R_MFG_{hub_id}_FROZEN",
                    origin_id=manufacturing_id,
                    destination_id=hub_id,
                    transport_mode=StorageMode.FROZEN,
                    transit_time_days=1.0,
                    cost=0.15,
                )
            )

    # Destinations
    for dest_id in destination_ids:
        dest = Location(
            id=dest_id,
            name=f"Destination {dest_id}",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
        )
        locations.append(dest)

        # Routes from each hub to destination
        for hub_id in hub_ids:
            routes.append(
                Route(
                    id=f"R_{hub_id}_{dest_id}",
                    origin_id=hub_id,
                    destination_id=dest_id,
                    transport_mode=StorageMode.AMBIENT,
                    transit_time_days=1.0,
                    cost=0.05,
                )
            )

        # Direct route from manufacturing
        routes.append(
            Route(
                id=f"R_MFG_{dest_id}_DIRECT",
                origin_id=manufacturing_id,
                destination_id=dest_id,
                transport_mode=StorageMode.AMBIENT,
                transit_time_days=2.0,
                cost=0.15,
            )
        )

    return {
        'locations': locations,
        'routes': routes,
        'manufacturing': manufacturing,
        'hubs': [loc for loc in locations if loc.type == LocationType.STORAGE],
        'destinations': [loc for loc in locations if loc.type == LocationType.BREADROOM],
    }


# ============================================================================
# Packaging Scenario Generators
# ============================================================================

def create_exact_truck_capacity_scenario(
    start_date: date,
    destination_id: str = "6100",
    product_id: str = "PROD_A"
) -> Forecast:
    """Create forecast with demand exactly at truck capacity."""
    entries = [
        ForecastEntry(
            location_id=destination_id,
            product_id=product_id,
            forecast_date=start_date + timedelta(days=2),
            quantity=UNITS_PER_TRUCK
        )
    ]
    return Forecast(name="Exact Truck Capacity", entries=entries)


def create_partial_pallet_scenario(
    start_date: date,
    destination_id: str = "6100",
    product_id: str = "PROD_A"
) -> Forecast:
    """Create forecast requiring partial pallets."""
    entries = [
        # 1 case (very inefficient)
        ForecastEntry(
            location_id=destination_id,
            product_id=product_id,
            forecast_date=start_date,
            quantity=UNITS_PER_CASE
        ),
        # 33 cases (1 full pallet + 1 case)
        ForecastEntry(
            location_id=destination_id,
            product_id=product_id,
            forecast_date=start_date + timedelta(days=1),
            quantity=330
        ),
    ]
    return Forecast(name="Partial Pallet", entries=entries)


def create_non_case_aligned_scenario(
    start_date: date,
    destination_id: str = "6100",
    products: Optional[List[str]] = None
) -> Forecast:
    """Create forecast with demands not aligned to case multiples."""
    if products is None:
        products = ["PROD_A", "PROD_B"]

    entries = []
    non_aligned_quantities = [1235, 847, 1506, 923]

    for i, qty in enumerate(non_aligned_quantities):
        product = products[i % len(products)]
        entries.append(
            ForecastEntry(
                location_id=destination_id,
                product_id=product,
                forecast_date=start_date + timedelta(days=i),
                quantity=qty
            )
        )

    return Forecast(name="Non-Case Aligned", entries=entries)


def create_multi_product_competition_scenario(
    start_date: date,
    destination_id: str = "6100"
) -> Forecast:
    """Create forecast where multiple products compete for truck space."""
    entries = [
        # Product A: 25 pallets
        ForecastEntry(
            location_id=destination_id,
            product_id="PROD_A",
            forecast_date=start_date + timedelta(days=2),
            quantity=8000
        ),
        # Product B: 22 pallets
        # Total: 47 pallets (exceeds 44 truck capacity)
        ForecastEntry(
            location_id=destination_id,
            product_id="PROD_B",
            forecast_date=start_date + timedelta(days=2),
            quantity=7000
        ),
    ]
    return Forecast(name="Multi-Product Competition", entries=entries)


# ============================================================================
# Assertion Helpers
# ============================================================================

def assert_all_case_multiples(
    production_values: Dict[Tuple[date, str], float],
    tolerance: float = 1e-6
) -> None:
    """
    Assert that all production values are case multiples.

    Args:
        production_values: Production dictionary
        tolerance: Floating point tolerance

    Raises:
        AssertionError: If any value is not a case multiple
    """
    validation = validate_case_constraints(production_values, tolerance)

    if not validation['is_valid']:
        violations_str = "\n".join([
            f"  {v['date']} {v['product']}: {v['quantity']} (remainder: {v['remainder']:.2f})"
            for v in validation['violations'][:5]
        ])
        raise AssertionError(
            f"Production violates case constraints:\n{violations_str}\n"
            f"... {validation['total_violations']} total violations"
        )


def assert_within_truck_capacity(
    shipment_values: Dict[Any, float],
    truck_capacity: int = PALLETS_PER_TRUCK
) -> None:
    """
    Assert that all shipments are within truck capacity.

    Args:
        shipment_values: Shipment quantity dictionary
        truck_capacity: Maximum pallets per truck

    Raises:
        AssertionError: If any shipment exceeds capacity
    """
    validation = validate_pallet_constraints(shipment_values, truck_capacity)

    if not validation['is_valid']:
        violations_str = "\n".join([
            f"  {v['key']}: {v['pallets_needed']} pallets (exceeds {v['truck_capacity']})"
            for v in validation['violations'][:5]
        ])
        raise AssertionError(
            f"Shipments exceed truck capacity:\n{violations_str}\n"
            f"... {validation['total_violations']} total violations"
        )


def assert_pallet_efficiency(
    quantity: float,
    min_efficiency_pct: float = 50.0
) -> None:
    """
    Assert that pallet packing efficiency meets minimum threshold.

    Args:
        quantity: Shipment quantity
        min_efficiency_pct: Minimum acceptable efficiency percentage

    Raises:
        AssertionError: If efficiency is below threshold
    """
    metrics = calculate_pallet_efficiency(quantity)

    if metrics['efficiency_pct'] < min_efficiency_pct:
        raise AssertionError(
            f"Pallet efficiency {metrics['efficiency_pct']:.1f}% "
            f"below minimum {min_efficiency_pct}% "
            f"(quantity: {quantity}, pallets: {metrics['total_pallets']}, "
            f"waste: {metrics['wasted_pallet_space']} cases)"
        )
