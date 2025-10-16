"""Check if cohort indices are being created for hub locations."""

from datetime import date, timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel


def check_hub_cohort_indices():
    """Verify that cohort indices exist for hubs on weekend dates."""

    print("=" * 80)
    print("HUB COHORT INDEX CHECK")
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
                id=loc.id,
                name=loc.name,
                type=loc.type,
                storage_mode=loc.storage_mode,
                capacity=loc.capacity,
                latitude=loc.latitude,
                longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Create model (don't solve - just build indices)
    print("Creating model (building indices only, not solving)...")
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=13)  # 2 weeks

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

    # Build model to create indices (don't solve)
    print(f"Planning horizon: {model.start_date} to {model.end_date}")
    print("Building Pyomo model...")
    pyomo_model = model.build_model()
    print("Model built successfully!")
    print()

    # Check cohort indices for hubs
    hubs = ['6104', '6125']
    products = list(model.products)[:2]  # Check first 2 products for brevity

    print("COHORT INDICES FOR HUBS:")
    print("-" * 80)

    # Get weekend dates in planning horizon
    test_dates = []
    current = model.start_date
    while current <= model.end_date:
        test_dates.append((current, current.strftime('%A')))
        current += timedelta(days=1)

    # Check if cohorts exist for each hub on each date
    for hub_id in hubs:
        print(f"\nHub {hub_id}:")
        print(f"  Location in inventory_locations: {hub_id in model.inventory_locations}")
        print(f"  Location in destinations: {hub_id in model.destinations}")
        print()

        # Count cohorts for this hub
        cohorts_by_date = {}
        for (loc, prod, prod_date, curr_date) in model.cohort_ambient_index_set:
            if loc == hub_id:
                if curr_date not in cohorts_by_date:
                    cohorts_by_date[curr_date] = []
                cohorts_by_date[curr_date].append((prod, prod_date))

        # Show cohorts for each date (especially weekends)
        print(f"  Cohort indices created for {len(cohorts_by_date)} dates:")
        for curr_date in sorted(cohorts_by_date.keys())[:14]:  # First 2 weeks
            day_name = curr_date.strftime('%A')
            num_cohorts = len(cohorts_by_date[curr_date])
            weekend_marker = ' <-- WEEKEND' if curr_date.weekday() in [5, 6] else ''
            print(f"    {curr_date} ({day_name:9s}): {num_cohorts:3d} cohorts{weekend_marker}")

    print()
    print("INTERPRETATION:")
    print("-" * 80)
    print("If weekends show 0 cohorts: BUG in cohort index creation")
    print("If weekends show >0 cohorts: Model CAN hold inventory, check constraint logic")


if __name__ == "__main__":
    check_hub_cohort_indices()
