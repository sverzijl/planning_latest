"""Test labor capacity enforcement in optimization solutions.

This test ensures that the labor capacity constraints are properly enforced
and that no solution exceeds the maximum labor hours available per day.
"""

import pytest
from datetime import date, timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products


def test_labor_capacity_enforcement():
    """Test that labor capacity constraints are enforced in 12-week horizon.

    This test specifically checks for the bug where labor_hours_used had no
    upper bound, allowing solutions with 35+ hours of labor in a single day.

    Expected behavior:
    - Weekdays (fixed days): max 14 hours (12 fixed + 2 overtime)
    - Weekends/holidays (non-fixed): max 14 hours (overtime only, but practical max ~8-14h)
    """

    # Parse data
    print("\n" + "=" * 80)
    print("LABOR CAPACITY ENFORCEMENT TEST (12-WEEK HORIZON)")
    print("=" * 80)

    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gluten Free Forecast - Latest.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=None
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    assert manufacturing_locations, "No manufacturing site found"
    manuf_loc = manufacturing_locations[0]

    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0,  # units per hour
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Set planning horizon (12 weeks)
    start_date = date(2025, 1, 6)
    end_date = start_date + timedelta(days=83)  # 12 weeks

    # Create products
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    print(f"\nBuilding model (horizon: {start_date} to {end_date})...")

    # Build model
    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        products=products,
        forecast=forecast,
        initial_inventory=None,
        labor_calendar=labor_calendar,
        truck_schedules=unified_truck_schedules,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=False
    )

    pyomo_model = model.build_model()
    print("✅ Model built successfully")

    # Solve
    print("\nSolving 12-week model...")
    result = model.solve(pyomo_model)

    print(f"✅ Solve completed")
    print(f"   Status: {result.solver.termination_condition}")

    # Extract solution
    print("\nExtracting solution...")
    solution = model.extract_solution(pyomo_model, result)

    print(f"   Total production: {solution.total_production_quantity:,} units")
    print(f"   Total demand: {solution.total_demand:,} units")
    print(f"   Fill rate: {solution.fill_rate:.1%}")

    # Check for labor violations
    print("\n" + "=" * 80)
    print("VALIDATING LABOR CAPACITY")
    print("=" * 80)

    violations_found = 0
    max_hours_seen = 0.0
    violation_details = []

    # Group production by date
    production_by_date = {}
    for batch in solution.production_batches:
        date_key = batch.production_date
        if date_key not in production_by_date:
            production_by_date[date_key] = 0
        production_by_date[date_key] += batch.quantity

    print(f"\nChecking {len(production_by_date)} production dates...")

    for prod_date, total_quantity in sorted(production_by_date.items()):
        # Get labor day info
        labor_day = labor_calendar.get_labor_day(prod_date)
        if not labor_day:
            continue

        # Calculate max hours for this day
        if labor_day.is_fixed_day:
            # Weekday: 12 fixed + 2 overtime = 14 max
            max_hours = 14.0
        else:
            # Weekend/holiday: overtime only, typically 8h but can be up to 14h
            max_hours = 14.0

        # Calculate actual production time (not including overhead)
        production_rate = manufacturing_site.production_rate  # units/hour
        production_time = total_quantity / production_rate

        max_hours_seen = max(max_hours_seen, production_time)

        # Check for violation (allow 0.01h tolerance for numerical precision)
        if production_time > max_hours + 0.01:
            violations_found += 1
            violation_details.append({
                'date': prod_date,
                'quantity': total_quantity,
                'hours': production_time,
                'max_hours': max_hours,
                'excess': production_time - max_hours,
                'is_fixed_day': labor_day.is_fixed_day
            })

    if violations_found == 0:
        print(f"✅ No labor violations found!")
        print(f"   Maximum labor hours used: {max_hours_seen:.2f}h")
        print(f"   All days within capacity limits")
    else:
        print(f"❌ Found {violations_found} labor violations:")
        for v in violation_details:
            print(f"\n   Date: {v['date']} ({'weekday' if v['is_fixed_day'] else 'weekend/holiday'})")
            print(f"   Production: {v['quantity']:,} units")
            print(f"   Time required: {v['hours']:.2f} hours")
            print(f"   Max allowed: {v['max_hours']:.2f} hours")
            print(f"   EXCESS: {v['excess']:.2f} hours")

    print("\n" + "=" * 80)

    # Assert no violations
    assert violations_found == 0, \
        f"Labor capacity violated on {violations_found} days. See details above."

    print("✅ TEST PASSED: Labor capacity constraints properly enforced")
    print("=" * 80)


if __name__ == "__main__":
    test_labor_capacity_enforcement()
