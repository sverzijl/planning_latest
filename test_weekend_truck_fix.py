"""Test that weekend truck constraints work correctly after fix."""

from datetime import date, timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel


def test_weekend_trucks():
    """Test that trucks don't run on weekends."""

    print("=" * 80)
    print("WEEKEND TRUCK CONSTRAINT TEST")
    print("=" * 80)
    print()

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    # Find manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            from src.models.manufacturing import ManufacturingSite
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Run optimization - 1 week only for speed
    print("Running 1-week optimization...")
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=6)  # 1 week

    model = IntegratedProductionDistributionModel(
        manufacturing_site=manufacturing_site,
        forecast=forecast,
        locations=locations,
        routes=routes,
        start_date=start_date,
        end_date=end_date,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        truck_schedules=truck_schedules,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=60, mip_gap=0.05)

    print(f"Status: {result.termination_condition}")
    print()

    if not (result.is_optimal() or result.is_feasible()):
        print("ERROR: Model not solved")
        return

    solution = model.get_solution()

    # Check truck usage on weekend
    truck_used_by_date = solution.get('truck_used_by_date', {})

    print("WEEKEND TRUCK USAGE:")
    print("-" * 80)

    weekend_violations = []
    for (truck_idx, date_val), used in truck_used_by_date.items():
        if used and date_val.weekday() in [5, 6]:  # Saturday or Sunday
            truck = truck_schedules.schedules[truck_idx]
            weekend_violations.append((truck.id, date_val, date_val.strftime('%A')))

    if weekend_violations:
        print(f"❌ FAILED: {len(weekend_violations)} trucks used on weekends:")
        for truck_id, date_val, day_name in weekend_violations:
            print(f"  {truck_id} on {date_val} ({day_name})")
        print()
        print("BUG STILL EXISTS!")
    else:
        print("✅ PASSED: No trucks used on weekends!")
        print()

    # Check hub inventory on weekend
    cohort_inventory = solution.get('cohort_inventory', {})

    weekend_dates = [d for d in sorted(set(d for (l, p, pd, d, s) in cohort_inventory.keys()))
                     if d.weekday() in [5, 6]]

    if weekend_dates:
        print("HUB INVENTORY ON WEEKENDS:")
        print("-" * 80)

        hubs = ['6104', '6125']
        for weekend_date in weekend_dates:
            print(f"\n{weekend_date} ({weekend_date.strftime('%A')}):")

            for hub_id in hubs:
                total = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                           if loc == hub_id and curr_date == weekend_date and qty > 0.01)

                if total > 0:
                    print(f"  {hub_id}: {total:7,.0f} units ✅")
                else:
                    print(f"  {hub_id}: 0 units ❌")

        print()
        print("Expected: Hubs should have inventory > 0 on weekends")


if __name__ == "__main__":
    test_weekend_trucks()
