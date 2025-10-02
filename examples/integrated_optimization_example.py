"""Example usage of IntegratedProductionDistributionModel.

This script demonstrates how to use the integrated production-distribution
optimization model to minimize total cost (labor + production + transport).
"""

import sys
from pathlib import Path
from datetime import date, timedelta

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimization import IntegratedProductionDistributionModel
from src.models import (
    Forecast,
    ForecastEntry,
    LaborCalendar,
    LaborDay,
    ManufacturingSite,
    CostStructure,
    Location,
    LocationType,
    StorageMode,
    Route,
)


def create_example_network():
    """Create a simple 2-echelon distribution network."""
    # Manufacturing site
    manufacturing = Location(
        id="6122",
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT,
    )

    # Regional hub
    hub = Location(
        id="6125",
        name="VIC Hub",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.AMBIENT,
    )

    # Breadrooms (destinations)
    breadroom1 = Location(
        id="6103",
        name="Melbourne Breadroom",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )

    breadroom2 = Location(
        id="6105",
        name="Geelong Breadroom",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )

    breadroom3 = Location(
        id="6107",
        name="Ballarat Breadroom",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )

    locations = [manufacturing, hub, breadroom1, breadroom2, breadroom3]

    # Routes
    routes = [
        # Manufacturing to hub (1 day, $0.10/unit)
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6125",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.10,
        ),
        # Hub to breadrooms (1 day each)
        Route(
            id="R2",
            origin_id="6125",
            destination_id="6103",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.15,
        ),
        Route(
            id="R3",
            origin_id="6125",
            destination_id="6105",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.12,
        ),
        Route(
            id="R4",
            origin_id="6125",
            destination_id="6107",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.18,
        ),
        # Direct route to Melbourne (faster but more expensive)
        Route(
            id="R5",
            origin_id="6122",
            destination_id="6103",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.30,
        ),
    ]

    return locations, routes


def create_example_forecast():
    """Create a sample 5-day forecast for 2 products."""
    start_date = date(2025, 1, 20)
    entries = []

    # Product A: Higher volume
    daily_demand_prod_a = {
        "6103": 800,  # Melbourne
        "6105": 500,  # Geelong
        "6107": 300,  # Ballarat
    }

    # Product B: Lower volume
    daily_demand_prod_b = {
        "6103": 600,
        "6105": 400,
        "6107": 200,
    }

    # Create 5 days of demand
    for day_offset in range(5):
        forecast_date = start_date + timedelta(days=day_offset)

        # Product A demand
        for location_id, quantity in daily_demand_prod_a.items():
            entries.append(
                ForecastEntry(
                    location_id=location_id,
                    product_id="PROD_A",
                    forecast_date=forecast_date,
                    quantity=quantity,
                )
            )

        # Product B demand
        for location_id, quantity in daily_demand_prod_b.items():
            entries.append(
                ForecastEntry(
                    location_id=location_id,
                    product_id="PROD_B",
                    forecast_date=forecast_date,
                    quantity=quantity,
                )
            )

    return Forecast(name="Example 5-Day Forecast", entries=entries)


def create_labor_calendar():
    """Create labor calendar for 7 days (5 weekdays + 2 weekend days)."""
    start_date = date(2025, 1, 20)  # Monday
    days = []

    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
        is_weekday = day_offset < 5

        if is_weekday:
            # Weekday: 12 fixed hours, overtime available
            day = LaborDay(
                date=current_date,
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                is_fixed_day=True,
            )
        else:
            # Weekend: 4-hour minimum, premium rate
            day = LaborDay(
                date=current_date,
                fixed_hours=0.0,
                regular_rate=0.0,
                overtime_rate=0.0,
                non_fixed_rate=100.0,
                minimum_hours=4.0,
                is_fixed_day=False,
            )

        days.append(day)

    return LaborCalendar(name="Example Labor Calendar", days=days)


def main():
    """Run integrated optimization example."""
    print("=" * 70)
    print("Integrated Production-Distribution Optimization Example")
    print("=" * 70)
    print()

    # Create network
    print("Creating distribution network...")
    locations, routes = create_example_network()
    print(f"  Locations: {len(locations)}")
    print(f"  Routes: {len(routes)}")

    # Create forecast
    print("\nCreating forecast...")
    forecast = create_example_forecast()
    print(f"  Products: 2 (PROD_A, PROD_B)")
    print(f"  Destinations: 3 breadrooms")
    print(f"  Planning horizon: 5 days")
    print(f"  Total demand entries: {len(forecast.entries)}")

    # Create labor calendar
    print("\nCreating labor calendar...")
    labor_calendar = create_labor_calendar()
    print(f"  Days: 7 (5 weekdays + 2 weekend)")

    # Create manufacturing site
    manufacturing_site = ManufacturingSite(
        id="6122",
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT,
        production_rate=1400.0,  # units per hour
    )

    # Create cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=0.80,
        transport_cost_per_unit_km=0.01,
        waste_cost_multiplier=1.5,
        shortage_penalty_per_unit=1.50,
    )

    # Create integrated model
    print("\nCreating integrated optimization model...")
    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        max_routes_per_destination=3,  # Enumerate up to 3 routes per destination
    )

    # Print model info
    print(f"  Production dates: {len(model.production_dates)}")
    print(f"  Products: {len(model.products)}")
    print(f"  Destinations: {len(model.destinations)}")
    print(f"  Enumerated routes: {len(model.enumerated_routes)}")

    # Print route enumeration summary
    print("\nRoute Enumeration:")
    for dest_id in sorted(model.routes_to_destination.keys()):
        route_indices = model.routes_to_destination[dest_id]
        print(f"  {dest_id}: {len(route_indices)} routes")
        for route_idx in route_indices[:2]:  # Show first 2 routes
            route = model.route_enumerator.get_route(route_idx)
            print(f"    - {route}")

    # Build model
    print("\nBuilding optimization model...")
    model.model = model.build_model()  # Assign to self.model so stats work
    stats = model.get_model_statistics()
    print(f"  Variables: {stats['num_variables']}")
    print(f"  Constraints: {stats['num_constraints']}")

    # Solve model
    print("\nSolving optimization model...")
    print("  (This requires an optimization solver like CBC or GLPK)")
    print("  (Install solver: conda install -c conda-forge coincbc)")

    try:
        result = model.solve(time_limit_seconds=300)

        if result.is_optimal():
            print(f"\n  ✓ Optimal solution found!")
            print(f"  Solve time: {result.solve_time_seconds:.2f} seconds")
            print(f"  Total cost: ${result.objective_value:,.2f}")

            # Print detailed solution summary
            print()
            model.print_solution_summary()

            # Get shipment plan
            shipments = model.get_shipment_plan()
            if shipments:
                print(f"\nShipment Plan Details:")
                print(f"  Total shipments: {len(shipments)}")
                for i, shipment in enumerate(shipments[:5], 1):  # Show first 5
                    print(f"  {i}. {shipment}")
                if len(shipments) > 5:
                    print(f"  ... and {len(shipments) - 5} more shipments")

        elif result.is_feasible():
            print(f"\n  ⚠ Feasible solution found (not proven optimal)")
            print(f"  Solve time: {result.solve_time_seconds:.2f} seconds")
            print(f"  Total cost: ${result.objective_value:,.2f}")
        else:
            print(f"\n  ✗ No solution found")
            print(f"  Status: {result.solver_status}")
            if result.infeasibility_message:
                print(f"  Message: {result.infeasibility_message}")

    except RuntimeError as e:
        print(f"\n  ✗ Solver error: {e}")
        print("\n  Please install an optimization solver:")
        print("    conda install -c conda-forge coincbc")
        print("  or")
        print("    conda install -c conda-forge glpk")

    print("\n" + "=" * 70)
    print("Example complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
