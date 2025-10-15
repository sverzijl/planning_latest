"""Test 1: Basic model building without solving."""

from datetime import timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel


def test_model_building():
    """Test that model builds without errors."""

    print("=" * 80)
    print("TEST 1: MODEL BUILDING")
    print("=" * 80)
    print()

    # Load data
    print("Loading data...")
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

    # 1-week horizon
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=6)

    print("Creating model...")
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

    print("Building Pyomo model...")
    pyomo_model = model.build_model()
    print("✅ Model built successfully!")
    print()

    # Verify leg structure
    print("VERIFICATION:")
    print("-" * 80)

    legs_from_6122 = [(o, d) for (o, d) in model.leg_keys if o == '6122']
    legs_from_storage = [(o, d) for (o, d) in model.leg_keys if o == '6122_Storage']

    print(f"Legs from 6122: {len(legs_from_6122)}")
    if legs_from_6122:
        print(f"  ❌ FAIL: Real manufacturing legs still exist")
        for leg in legs_from_6122:
            print(f"    {leg}")
    else:
        print(f"  ✅ PASS: No real manufacturing legs (replaced with virtual)")

    print()
    print(f"Legs from 6122_Storage: {len(legs_from_storage)}")
    if legs_from_storage:
        print(f"  ✅ PASS: Virtual legs exist")
        for leg in legs_from_storage:
            print(f"    {leg}")
    else:
        print(f"  ❌ FAIL: Virtual legs missing!")

    print()
    print("TEST 1 RESULT:")
    if not legs_from_6122 and legs_from_storage:
        print("✅ PASSED - Model structure correct")
        return True
    else:
        print("❌ FAILED - Leg structure incorrect")
        return False


if __name__ == "__main__":
    success = test_model_building()
    sys.exit(0 if success else 1)
