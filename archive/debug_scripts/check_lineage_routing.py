"""Check if Lineage intermediate stop routing is working correctly."""

from datetime import date, timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection

def check_lineage_routing():
    """Verify Lineage intermediate stop configuration."""

    print("=" * 80)
    print("LINEAGE INTERMEDIATE STOP ROUTING CHECK")
    print("=" * 80)
    print()

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    _, _, _, _, truck_schedules_list, _ = parser.parse_all()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    # Find T3 (Wednesday truck with Lineage intermediate stop)
    print("TRUCK T3 CONFIGURATION:")
    print("-" * 80)

    t3 = None
    t3_idx = None
    for i, truck in enumerate(truck_schedules.schedules):
        if truck.id == 'T3':
            t3 = truck
            t3_idx = i
            break

    if not t3:
        print("ERROR: Truck T3 not found!")
        return

    print(f"ID: {t3.id}")
    print(f"Name: {t3.truck_name}")
    print(f"Departure Type: {t3.departure_type}")
    print(f"Final Destination: {t3.destination_id}")
    print(f"Day of Week: {t3.day_of_week if t3.day_of_week else 'DAILY (ERROR!)'}")
    print(f"Has Intermediate Stops: {t3.has_intermediate_stops()}")
    print(f"Intermediate Stops: {t3.intermediate_stops}")
    print()

    # Check if T3 runs on Wednesdays only
    print("DATE APPLICABILITY TEST:")
    print("-" * 80)
    test_dates = [
        date(2025, 1, 6),   # Monday
        date(2025, 1, 7),   # Tuesday
        date(2025, 1, 8),   # Wednesday
        date(2025, 1, 9),   # Thursday
        date(2025, 1, 10),  # Friday
    ]

    for test_date in test_dates:
        applies = t3.applies_on_date(test_date)
        status = "✓ RUNS" if applies else "✗ Does not run"
        expected = "Wednesday" if test_date.weekday() == 2 else "Not Wednesday"
        print(f"{test_date} ({test_date.strftime('%A'):9s}): {status:15s} [{expected}]")
    print()

    # Check if model would recognize both destinations
    print("DESTINATION MAPPING:")
    print("-" * 80)
    print(f"T3 serves final destination: {t3.destination_id}")
    print(f"T3 serves intermediate stops: {', '.join(t3.intermediate_stops) if t3.intermediate_stops else 'None'}")
    print()
    print("Expected behavior:")
    print("  - Model should create truck_load variables for T3 to BOTH Lineage AND 6125")
    print("  - On Wednesday, T3 can load:")
    print("    * Some quantity for Lineage (frozen for WA buffer)")
    print("    * Some quantity for 6125 (VIC/TAS/SA region)")
    print("  - Total across both destinations ≤ 14,080 units (truck capacity)")
    print()

    # Check Wednesday truck availability
    print("WEDNESDAY AVAILABILITY:")
    print("-" * 80)
    wednesday = date(2025, 1, 8)
    morning_trucks = truck_schedules.get_trucks_on_date(wednesday, departure_type='morning')

    print(f"Morning trucks on {wednesday} (Wednesday):")
    for truck in morning_trucks:
        stops_info = f" via {', '.join(truck.intermediate_stops)}" if truck.intermediate_stops else ""
        print(f"  - {truck.id}: {truck.truck_name} → {truck.destination_id}{stops_info}")
    print()

    # Check destinations reachable on Wednesday
    reachable = truck_schedules.get_routes_available_on_date(wednesday)
    print(f"Destinations reachable on Wednesday: {', '.join(sorted(reachable))}")
    print()

    # Verify Lineage is reachable on Wednesday
    if 'Lineage' in reachable:
        print("✅ SUCCESS: Lineage is reachable on Wednesday")
    else:
        print("❌ ERROR: Lineage is NOT reachable on Wednesday (intermediate stop not configured correctly)")
    print()

    # Check capacity allocation
    print("CAPACITY ALLOCATION SCENARIO:")
    print("-" * 80)
    print("Example Wednesday allocation for T3:")
    print(f"  Truck capacity: {t3.capacity:,.0f} units ({t3.pallet_capacity} pallets)")
    print()
    print("  Scenario A: Balanced")
    print(f"    Lineage:  6,400 units (20 pallets) - Frozen buffer for WA")
    print(f"    6125:     7,680 units (24 pallets) - VIC/TAS/SA region")
    print(f"    Total:   14,080 units (44 pallets) - 100% utilization")
    print()
    print("  Scenario B: Priority to 6125")
    print(f"    Lineage:  3,200 units (10 pallets) - Minimal frozen buffer")
    print(f"    6125:    10,880 units (34 pallets) - Maximum VIC/TAS/SA")
    print(f"    Total:   14,080 units (44 pallets) - 100% utilization")
    print()
    print("  The model will choose allocation based on:")
    print("    - 6130 (WA) frozen inventory level (lower = more to Lineage)")
    print("    - 6125 region demand urgency (higher = more to 6125)")
    print("    - Cost trade-offs (transport, holding, shortage penalties)")


if __name__ == "__main__":
    check_lineage_routing()
