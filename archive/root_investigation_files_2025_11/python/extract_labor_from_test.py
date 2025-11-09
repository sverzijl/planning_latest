"""Extract labor hours from the 4-week test to check for weekend labor issues."""

import sys
from pathlib import Path
from datetime import date, timedelta

# Run the test and capture the model
from tests.test_integration_ui_workflow import *

def extract_labor_details():
    """Run test and extract detailed labor information."""

    print("=" * 80)
    print("EXTRACTING LABOR DETAILS FROM 4-WEEK TEST")
    print("=" * 80)

    # Get parsed data
    from tests.test_integration_ui_workflow import data_files, parsed_data

    # Setup fixtures manually
    data_dir = Path(__file__).parent / "data" / "examples"
    forecast_file = data_dir / "Gluten Free Forecast - Latest.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory_latest.XLSX"

    files = {
        'forecast': forecast_file,
        'network': network_file,
        'inventory': inventory_file if inventory_file.exists() else None
    }

    # Parse
    from src.parsers.multi_file_parser import MultiFileParser
    parser = MultiFileParser(
        forecast_file=files['forecast'],
        network_file=files['network'],
        inventory_file=files['inventory'],
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing
    from src.models.manufacturing import ManufacturingSite
    from src.models.location import LocationType
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]

    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Convert
    from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Parse inventory
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot
    inventory_snapshot_date = inventory_snapshot.snapshot_date

    planning_start_date = inventory_snapshot_date
    planning_end_date = planning_start_date + timedelta(weeks=4)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    print(f"\nBuilding model ({planning_start_date} to {planning_end_date})...")

    from src.optimization.sliding_window_model import SlidingWindowModel
    from pyomo.environ import value

    model_builder = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict(),
        inventory_snapshot_date=inventory_snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    pyomo_model = model_builder.build_model()
    print("✅ Model built")

    # Solve
    print("\nSolving...")
    result = model_builder.solve(
        solver_name='appsi_highs',
        time_limit_seconds=120,
        mip_gap=0.02,
        tee=False
    )
    print(f"✅ Solved")

    # Extract solution
    solution = model_builder.extract_solution(pyomo_model)

    # Analyze weekends from solution object
    print("\n" + "=" * 80)
    print("WEEKEND LABOR ANALYSIS (from solution object)")
    print("=" * 80)

    # Group production by date
    production_by_date = {}
    for batch in solution.production_batches:
        production_by_date[batch.production_date] = production_by_date.get(batch.production_date, 0) + batch.quantity

    # Check labor costs by date
    if hasattr(solution, 'cost_breakdown') and hasattr(solution.cost_breakdown.labor, 'by_date'):
        labor_by_date = solution.cost_breakdown.labor.by_date or {}

        weekend_labor_issues = []

        for date_str, labor_info in sorted(labor_by_date.items()):
            # Parse date
            from datetime import datetime
            labor_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            labor_day = labor_calendar.get_labor_day(labor_date)
            if not labor_day or labor_day.is_fixed_day:
                continue  # Skip weekdays

            # Weekend day
            actual_production = production_by_date.get(labor_date, 0)
            labor_hours = labor_info.get('hours_used', 0) if isinstance(labor_info, dict) else 0

            print(f"\n{labor_date} ({labor_date.strftime('%A')}):")
            print(f"  Production: {actual_production:,} units")
            print(f"  Labor info: {labor_info}")

            if labor_hours > 0.01 and actual_production == 0:
                weekend_labor_issues.append((labor_date, labor_hours, labor_info))
                print(f"  ❌ ISSUE: {labor_hours:.4f}h labor with no production!")

        print("\n" + "=" * 80)
        if weekend_labor_issues:
            print(f"❌ Found {len(weekend_labor_issues)} weekends with spurious labor")
            for date, hours, info in weekend_labor_issues:
                print(f"  {date}: {hours:.4f}h - {info}")
        else:
            print("✅ No spurious weekend labor found!")
        print("=" * 80)
    else:
        print("❌ Labor breakdown by date not available in solution")
        print("   Checking production batches instead...")

        # Alternative: just look at weekends with no production
        all_dates = set(pyomo_model.dates)
        weekend_dates = [d for d in all_dates
                        if labor_calendar.get_labor_day(d) and not labor_calendar.get_labor_day(d).is_fixed_day]

        print(f"\nWeekend dates in horizon: {len(weekend_dates)}")
        for d in sorted(weekend_dates):
            prod = production_by_date.get(d, 0)
            print(f"  {d} ({d.strftime('%A')}): {prod:,} units")

        weekends_with_no_production = [d for d in weekend_dates if production_by_date.get(d, 0) == 0]
        print(f"\nWeekends with NO production: {len(weekends_with_no_production)}")
        for d in sorted(weekends_with_no_production):
            print(f"  {d} ({d.strftime('%A')})")

        if weekends_with_no_production:
            print(f"\n⚠️  If these weekends show 0.25h labor, there's still an issue")


if __name__ == "__main__":
    extract_labor_details()
