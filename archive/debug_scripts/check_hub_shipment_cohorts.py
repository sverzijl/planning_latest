"""Check if shipment cohort indices exist for hub-to-spoke legs."""

from datetime import date, timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel


def check_hub_shipment_cohorts():
    """Check shipment cohort indices for hub-to-spoke legs."""

    print("=" * 80)
    print("HUB SHIPMENT COHORT INDEX CHECK")
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

    # Create model
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=6)  # 1 week for speed

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

    # Build model
    print("Building model...")
    pyomo_model = model.build_model()
    print("Model built!")
    print()

    # Check hub-to-spoke shipment cohorts
    hub_to_spoke_legs = [
        ('6104', '6105'),  # NSW Hub → Rydalmere
        ('6104', '6103'),  # NSW Hub → Canberra
        ('6125', '6123'),  # VIC Hub → Clayton
        ('6125', '6120'),  # VIC Hub → Hobart
        ('6125', '6134'),  # VIC Hub → Adelaide
    ]

    print("HUB-TO-SPOKE SHIPMENT COHORT INDICES:")
    print("-" * 80)

    for leg in hub_to_spoke_legs:
        origin, dest = leg
        # Count cohorts for this leg
        cohorts = [(prod, prod_date, delivery_date)
                  for (l, prod, prod_date, delivery_date) in model.cohort_shipment_index_set
                  if l == leg]

        print(f"\n{origin} → {dest}:")
        print(f"  Total shipment cohorts: {len(cohorts)}")

        if cohorts:
            # Group by delivery date
            by_delivery_date = {}
            for (prod, prod_date, delivery_date) in cohorts:
                if delivery_date not in by_delivery_date:
                    by_delivery_date[delivery_date] = 0
                by_delivery_date[delivery_date] += 1

            print(f"  Delivery dates with cohorts: {len(by_delivery_date)}")
            for delivery_date in sorted(by_delivery_date.keys())[:10]:
                day_name = delivery_date.strftime('%A')
                count = by_delivery_date[delivery_date]
                print(f"    {delivery_date} ({day_name:9s}): {count:3d} cohorts")
        else:
            print(f"  ❌ NO SHIPMENT COHORTS! Hubs cannot ship to spokes!")

    print()
    print("INTERPRETATION:")
    print("=" * 80)
    print("If hub-to-spoke legs have 0 cohorts: Hubs cannot distribute to spokes")
    print("If hub-to-spoke legs have >0 cohorts: Model structure is correct")


if __name__ == "__main__":
    check_hub_shipment_cohorts()
