"""Test labor capacity fix with 4-week horizon."""

from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products

def test_labor_fix_4_week():
    """Test labor capacity fix with 4-week horizon."""

    print("=" * 80)
    print("LABOR CAPACITY FIX VALIDATION - 4 WEEK")
    print("=" * 80)

    # Parse data
    print("\n1. Parsing data files...")
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gluten Free Forecast - Latest.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=None
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    print("✅ Data parsed successfully")

    # Get manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")
    manuf_loc = manufacturing_locations[0]

    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=manuf_loc.production_rate if hasattr(manuf_loc, 'production_rate') and manuf_loc.production_rate else 1400.0,
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

    # Set planning horizon (4 weeks)
    start_date = date(2025, 1, 6)
    end_date = start_date + timedelta(days=27)  # 4 weeks

    # Create products
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    print(f"\n2. Building model (horizon: {start_date} to {end_date})...")

    # Build model
    model_builder = SlidingWindowModel(
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
        mipgap=0.01,
        timelimit=300,
        use_pallet_tracking=True,
        use_mix_based_production=True,
        use_truck_pallet_tracking=False
    )

    model = model_builder.build_model()
    print("✅ Model built successfully")

    # Solve
    print("\n3. Solving model...")
    solve_start = time.time()
    result = model_builder.solve(model)
    solve_time = time.time() - solve_start

    print(f"\n✅ Solve completed in {solve_time:.1f}s")
    print(f"   Status: {result.solver.termination_condition}")
    print(f"   Objective: ${result.problem.lower_bound:,.2f}")

    # Extract solution
    print("\n4. Extracting solution...")
    solution = model_builder.extract_solution(model, result)

    print(f"   Total production: {solution.total_production_quantity:,} units")
    print(f"   Total demand: {solution.total_demand:,} units")
    print(f"   Fill rate: {solution.fill_rate:.1%}")

    # Check for labor violations
    print("\n5. Checking for labor violations...")
    violations_found = 0

    for batch in solution.production_batches:
        # Get labor hours for this date
        labor_day = labor_calendar.get_labor_day(batch.production_date)
        if not labor_day:
            continue

        # Calculate max hours
        if labor_day.is_fixed_day:
            max_hours = labor_day.fixed_hours + 2.0  # Max 2h overtime on weekdays
        else:
            max_hours = 14.0  # Weekend/holiday max (up to 14h OT, but typical is 8h)

        # Calculate actual production time
        production_rate = manufacturing_site.production_rate
        production_time = batch.quantity / production_rate

        if production_time > max_hours + 0.01:  # Allow small tolerance
            violations_found += 1
            print(f"   ❌ VIOLATION: {batch.production_date}")
            print(f"      Production: {batch.quantity:,} units")
            print(f"      Time required: {production_time:.2f} hours")
            print(f"      Max allowed: {max_hours:.2f} hours")
            print(f"      Excess: {production_time - max_hours:.2f} hours")

    if violations_found == 0:
        print("   ✅ No labor violations found!")
    else:
        print(f"\n   ❌ Found {violations_found} labor violations")

    print("\n" + "=" * 80)
    if violations_found == 0:
        print("SUCCESS: Labor capacity constraints are working correctly")
    else:
        print("FAILURE: Labor capacity constraints still violated")
    print("=" * 80)

    return violations_found == 0

if __name__ == "__main__":
    success = test_labor_fix_4_week()
    exit(0 if success else 1)
