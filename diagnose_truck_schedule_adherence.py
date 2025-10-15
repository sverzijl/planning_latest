"""Diagnose truck schedule adherence in optimization results.

Checks if the model is properly respecting day-of-week constraints for truck schedules.
"""

from datetime import date, timedelta
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel

def diagnose_truck_schedule():
    """Check if optimization respects truck schedule constraints."""

    print("=" * 80)
    print("TRUCK SCHEDULE ADHERENCE DIAGNOSTIC")
    print("=" * 80)
    print()

    # Load data
    forecast_file = "data/examples/Gfree Forecast.xlsm"
    network_file = "data/examples/Network_Config.xlsx"

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Convert to TruckScheduleCollection
    from src.models.truck_schedule import TruckScheduleCollection
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

    if not manufacturing_site:
        print("ERROR: No manufacturing site found")
        return

    # Print truck schedule configuration
    print("TRUCK SCHEDULE CONFIGURATION")
    print("-" * 80)
    for i, truck in enumerate(truck_schedules.schedules):
        day_str = truck.day_of_week.value if truck.day_of_week else "DAILY (all days)"
        print(f"[{i}] {truck.id:6s} {truck.truck_name:30s} -> {truck.destination_id:6s} on {day_str:10s}")
    print()

    # Check which trucks apply on sample dates
    print("TRUCK AVAILABILITY BY DATE (Sample Week)")
    print("-" * 80)
    start_date = date(2025, 1, 6)  # Monday Jan 6, 2025
    for i in range(7):
        check_date = start_date + timedelta(days=i)
        day_name = check_date.strftime("%A")
        trucks_available = []
        for truck_idx, truck in enumerate(truck_schedules.schedules):
            if truck.applies_on_date(check_date):
                trucks_available.append((truck_idx, truck.id, truck.destination_id))

        print(f"{check_date} ({day_name:9s}): {len(trucks_available)} trucks")
        for truck_idx, truck_id, dest in trucks_available:
            print(f"    [{truck_idx}] {truck_id} -> {dest}")
    print()

    # Run optimization (2-week horizon for speed)
    print("RUNNING OPTIMIZATION (2-week horizon)...")
    print("-" * 80)

    # Get 2-week date range
    start_date = forecast.get_start_date()
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

    result = model.solve(time_limit=60, mip_gap=0.01)

    if not result.is_optimal() and not result.is_feasible():
        print(f"ERROR: Model not solved successfully: {result.termination_condition}")
        return

    print(f"Status: {result.termination_condition}")
    print()

    # Extract solution
    solution = model.get_solution()
    if not solution:
        print("ERROR: Could not extract solution")
        return

    # Check truck usage in solution
    truck_used_by_date = solution.get('truck_used_by_date', {})

    print("TRUCK USAGE IN SOLUTION")
    print("-" * 80)

    # Organize by date
    from collections import defaultdict
    trucks_by_date = defaultdict(list)
    for (truck_idx, date_val), used in truck_used_by_date.items():
        if used:
            trucks_by_date[date_val].append(truck_idx)

    # Print by date
    for check_date in sorted(trucks_by_date.keys()):
        day_name = check_date.strftime("%A")
        truck_indices = sorted(trucks_by_date[check_date])
        print(f"{check_date} ({day_name:9s}): {len(truck_indices)} trucks used")

        for truck_idx in truck_indices:
            truck = truck_schedules.schedules[truck_idx]
            # Check if this truck should run on this date
            should_run = truck.applies_on_date(check_date)
            status = "✓ OK" if should_run else "✗ ERROR: Truck used on wrong day!"

            print(f"    [{truck_idx}] {truck.id:6s} -> {truck.destination_id:6s} "
                  f"(scheduled: {truck.day_of_week.value if truck.day_of_week else 'daily':10s}) {status}")
        print()

    # Check for constraint violations
    print("CONSTRAINT VIOLATION CHECK")
    print("-" * 80)
    violations = []
    for (truck_idx, check_date), used in truck_used_by_date.items():
        if used:
            truck = truck_schedules.schedules[truck_idx]
            if not truck.applies_on_date(check_date):
                violations.append((truck_idx, truck.id, check_date, truck.day_of_week))

    if violations:
        print(f"❌ FOUND {len(violations)} VIOLATIONS:")
        for truck_idx, truck_id, date_val, day_of_week in violations:
            print(f"  - Truck {truck_id} (scheduled for {day_of_week.value}) "
                  f"used on {date_val} ({date_val.strftime('%A')})")
    else:
        print("✅ No violations found - all trucks used only on their scheduled days")
    print()

    # Summary
    print("SUMMARY")
    print("-" * 80)
    total_truck_uses = len([v for v in truck_used_by_date.values() if v])
    unique_dates = len(trucks_by_date)
    print(f"Total truck uses: {total_truck_uses}")
    print(f"Days with trucks: {unique_dates}")
    print(f"Average trucks/day: {total_truck_uses / unique_dates:.1f}")
    print(f"Violations: {len(violations)}")


if __name__ == "__main__":
    diagnose_truck_schedule()
