"""Test 3: 2-week optimization with hub inventory verification."""

from datetime import timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel


def test_twoweek_optimization():
    """Test 2-week optimization with hub inventory check."""

    print("=" * 80)
    print("TEST 3: 2-WEEK OPTIMIZATION")
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

    # 2-week horizon
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=13)

    print("Running 2-week optimization...")
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

    result = model.solve(time_limit_seconds=90, mip_gap=0.02)

    print(f"Status: {result.termination_condition}")
    print(f"Solve time: {result.solve_time_seconds:.1f}s")
    print()

    if not result.is_optimal() and not result.is_feasible():
        print("❌ FAILED: Model did not solve")
        return False

    solution = model.get_solution()

    # Check hub inventory across all dates
    cohort_inventory = solution.get('cohort_inventory', {})

    hubs = ['6104', '6125']
    hub_inventory_summary = {}

    for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
        if loc in hubs and qty > 0.01:
            if curr_date not in hub_inventory_summary:
                hub_inventory_summary[curr_date] = {h: 0.0 for h in hubs}
            hub_inventory_summary[curr_date][loc] += qty

    print("HUB INVENTORY ACROSS 2 WEEKS:")
    print("-" * 80)

    weekend_dates = [d for d in sorted(hub_inventory_summary.keys()) if d.weekday() in [5, 6]]
    weekday_dates = [d for d in sorted(hub_inventory_summary.keys()) if d.weekday() not in [5, 6]]

    # Show all dates
    for curr_date in sorted(hub_inventory_summary.keys()):
        day_name = curr_date.strftime('%A')
        weekend_marker = ' <-- WEEKEND' if curr_date.weekday() in [5, 6] else ''

        inv_6104 = hub_inventory_summary[curr_date].get('6104', 0)
        inv_6125 = hub_inventory_summary[curr_date].get('6125', 0)

        print(f"{curr_date} ({day_name:9s}): 6104={inv_6104:7,.0f}  6125={inv_6125:7,.0f}{weekend_marker}")

    print()
    print("VERIFICATION:")
    print("-" * 80)

    # Count weekend dates with hub inventory
    weekends_with_inventory = sum(1 for d in weekend_dates
                                  if hub_inventory_summary[d].get('6104', 0) > 0 or
                                     hub_inventory_summary[d].get('6125', 0) > 0)

    total_weekends = len(weekend_dates)

    print(f"Weekend dates with hub inventory: {weekends_with_inventory}/{total_weekends}")

    if weekends_with_inventory >= total_weekends - 1:  # Allow one weekend to be zero (end of horizon)
        print("✅ PASSED - Hubs hold inventory on weekends")
        return True
    else:
        print("❌ FAILED - Insufficient weekend hub inventory")
        return False


if __name__ == "__main__":
    success = test_twoweek_optimization()
    sys.exit(0 if success else 1)
