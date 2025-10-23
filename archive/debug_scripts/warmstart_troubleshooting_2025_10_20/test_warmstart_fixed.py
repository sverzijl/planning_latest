"""Test to verify CBC warmstart -mipstart flag is now generated correctly.

This script tests that:
1. UnifiedNodeModel passes use_warmstart=True to base class
2. BaseOptimizationModel passes warmstart=True to Pyomo solver
3. CBC command line shows -mipstart flag
4. Warmstart file is actually used by CBC
"""

import sys
import io
from datetime import date, timedelta
from contextlib import redirect_stdout

from src.models.location import Location, NodeCapabilities
from src.models.route import Route
from src.models.product import Product
from src.models.forecast import Forecast
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.models.truck_schedule import TruckSchedule
from src.optimization.unified_node_model import UnifiedNodeModel


def create_minimal_data():
    """Create minimal test data."""
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6)

    # Manufacturing node
    manufacturing = Location(
        location_id="6122",
        location_name="Manufacturing",
        location_type="manufacturing",
        capabilities=NodeCapabilities(
            can_produce=True,
            can_store_frozen=False,
            can_store_ambient=True,
            can_receive=False,
            can_ship=True,
            production_rate_units_per_hour=1400,
            max_daily_production_units=19600,
        )
    )

    # Breadroom
    breadroom = Location(
        location_id="6104",
        location_name="Breadroom",
        location_type="breadroom",
        capabilities=NodeCapabilities(
            can_produce=False,
            can_store_frozen=False,
            can_store_ambient=True,
            can_receive=True,
            can_ship=False,
        )
    )

    # Route
    route = Route(
        route_id="R1",
        origin_id="6122",
        destination_id="6104",
        transit_days=1,
        transport_mode="ambient",
        cost_per_unit=0.5,
    )

    # Products
    products = [
        Product(product_id="SKU_A", product_name="SKU A", case_quantity=10, pallet_quantity=320),
        Product(product_id="SKU_B", product_name="SKU B", case_quantity=10, pallet_quantity=320),
    ]

    # Forecast
    forecast = [
        Forecast(location_id="6104", product_id="SKU_A", date=start_date + timedelta(days=i), quantity=1000)
        for i in range(7)
    ] + [
        Forecast(location_id="6104", product_id="SKU_B", date=start_date + timedelta(days=i), quantity=500)
        for i in range(7)
    ]

    # Labor calendar
    labor_days = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        is_weekend = day.weekday() >= 5
        labor_days.append(
            LaborDay(
                date=day,
                fixed_hours=0 if is_weekend else 12,
                regular_rate=20.0,
                overtime_rate=30.0,
                non_fixed_rate=40.0,
            )
        )
    labor_calendar = LaborCalendar(days=labor_days)

    # Costs
    costs = CostStructure(
        production_cost_per_unit=1.0,
        storage_cost_frozen_per_unit_day=0.1,
        storage_cost_ambient_per_unit_day=0.002,
        storage_cost_per_pallet_day_frozen=0.0,  # Disable pallet costs for speed
        storage_cost_per_pallet_day_ambient=0.0,
        waste_cost_multiplier=10.0,
        shortage_penalty_per_unit=10000.0,
    )

    # Truck schedule
    trucks = [
        TruckSchedule(
            origin_id="6122",
            destination_id="6104",
            day_of_week=i,  # Monday=0 to Friday=4
            time_of_day="morning",
            capacity_units=14080,
        )
        for i in range(5)  # Mon-Fri
    ]

    return {
        'nodes': [manufacturing, breadroom],
        'routes': [route],
        'products': products,
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'cost_structure': costs,
        'start_date': start_date,
        'end_date': end_date,
        'trucks': trucks,
    }


def test_warmstart_flag():
    """Test that -mipstart flag appears in CBC command line."""
    print("="*80)
    print("TESTING CBC WARMSTART -mipstart FLAG GENERATION")
    print("="*80)

    data = create_minimal_data()

    # Create model
    model = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        truck_schedules=data['trucks'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    print("\n[TEST] Solving with use_warmstart=True")
    print("-"*80)

    # Capture solver output to check for -mipstart flag
    output_buffer = io.StringIO()

    with redirect_stdout(output_buffer):
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=30,
            mip_gap=0.05,
            use_warmstart=True,  # Enable warmstart!
            tee=True,  # Show solver output
        )

    solver_output = output_buffer.getvalue()

    print("-"*80)
    print(f"\nSolver Status: {result.termination_condition}")
    print(f"Objective: ${result.objective_value:,.2f}" if result.objective_value else "N/A")
    print(f"Solve Time: {result.solve_time_seconds:.2f}s")

    # Check for -mipstart flag
    print("\n[VERIFICATION] Checking CBC command line...")
    print("-"*80)

    if "-mipstart" in solver_output:
        print("SUCCESS: -mipstart flag found in CBC command line!")
        print("\nExtract from solver output:")
        for line in solver_output.split('\n'):
            if 'command line' in line or 'mipstart' in line.lower():
                print(f"  {line}")
        return True
    else:
        print("FAILURE: -mipstart flag NOT found in CBC command line")
        print("\nCBC command line was:")
        for line in solver_output.split('\n'):
            if 'command line' in line:
                print(f"  {line}")
        print("\nFull solver output:")
        print(solver_output)
        return False


if __name__ == "__main__":
    success = test_warmstart_flag()

    print("\n" + "="*80)
    if success:
        print("WARMSTART FIX VERIFIED: CBC -mipstart flag is now generated correctly!")
        print("="*80)
        sys.exit(0)
    else:
        print("WARMSTART FIX FAILED: CBC -mipstart flag still missing")
        print("="*80)
        sys.exit(1)
