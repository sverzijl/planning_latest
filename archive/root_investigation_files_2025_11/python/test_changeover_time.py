"""Test that changeover time is properly included in labor capacity."""

from pathlib import Path
from datetime import date, timedelta

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products


def test_changeover_time():
    """Test changeover time is included in labor capacity constraints."""

    print("\n" + "=" * 80)
    print("CHANGEOVER TIME VERIFICATION TEST")
    print("=" * 80)

    # Parse data
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

    # Short horizon (1 week)
    start_date = date(2025, 1, 6)
    end_date = start_date + timedelta(days=6)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    print(f"\nBuilding model ({start_date} to {end_date})...")

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
    print("✅ Model built")

    # Check constraint formulation
    print("\n" + "=" * 80)
    print("CHECKING PRODUCTION TIME LINK CONSTRAINT")
    print("=" * 80)

    # Get first manufacturing node and date
    mfg_node_id = manufacturing_site.id
    first_date = start_date

    if (mfg_node_id, first_date) in pyomo_model.production_time_link_con:
        constraint = pyomo_model.production_time_link_con[mfg_node_id, first_date]

        print(f"\nConstraint for node {mfg_node_id}, date {first_date}:")
        print(f"  Constraint expression: {constraint.expr}")

        # Check if overhead terms are present
        constraint_str = str(constraint.expr)

        has_product_start = 'product_start' in constraint_str
        has_product_produced = 'product_produced' in constraint_str

        print(f"\n  Contains 'product_start' variables: {has_product_start}")
        print(f"  Contains 'product_produced' variables: {has_product_produced}")

        if has_product_start and has_product_produced:
            print("\n  ✅ OVERHEAD TIME IS INCLUDED IN CONSTRAINT")
            print(f"     Changeover time will consume production capacity!")
        else:
            print("\n  ❌ OVERHEAD TIME IS MISSING FROM CONSTRAINT")
            print(f"     Changeovers will NOT consume production capacity!")
    else:
        print(f"\n❌ Constraint not found for node {mfg_node_id}, date {first_date}")

    # Solve and check solution
    print("\n" + "=" * 80)
    print("SOLVING MODEL")
    print("=" * 80)

    result = model.solve(pyomo_model)

    print(f"\nSolve status: {result.solver.termination_condition}")
    print(f"Objective: ${result.problem.lower_bound:,.2f}")

    solution = model.extract_solution(pyomo_model, result)

    print(f"\nProduction: {solution.total_production_quantity:,} units")
    print(f"Fill rate: {solution.fill_rate:.1%}")

    # Check changeover statistics
    if hasattr(solution, 'total_changeover_cost'):
        print(f"\nChangeover cost: ${solution.total_changeover_cost:,.2f}")
    if hasattr(solution, 'total_changeover_waste_cost'):
        print(f"Changeover waste cost: ${solution.total_changeover_waste_cost:,.2f}")

    # Count unique production days and products per day
    prod_by_date = {}
    for batch in solution.production_batches:
        date_key = batch.production_date
        if date_key not in prod_by_date:
            prod_by_date[date_key] = set()
        prod_by_date[date_key].add(batch.product_id)

    print(f"\n" + "=" * 80)
    print("PRODUCTION SUMMARY")
    print("=" * 80)

    for prod_date in sorted(prod_by_date.keys()):
        products_produced = prod_by_date[prod_date]
        num_products = len(products_produced)

        # Calculate expected overhead
        startup = 0.5
        shutdown = 0.25
        changeover = 0.5

        if num_products == 1:
            expected_overhead = startup + shutdown
        else:
            expected_overhead = startup + shutdown + changeover * (num_products - 1)

        print(f"\n  {prod_date}: {num_products} products")
        print(f"    Expected overhead: {expected_overhead:.2f}h (startup + shutdown + {num_products-1} changeovers)")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_changeover_time()
