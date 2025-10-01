"""
Test script to verify two-file workflow end-to-end.

This script demonstrates:
1. Loading Network_Config.xlsx
2. Parsing all network configuration data
3. Displaying summary statistics
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers import MultiFileParser


def main():
    """Test two-file workflow."""
    print("=" * 60)
    print("Testing Two-File Workflow")
    print("=" * 60)

    # Path to network config file
    network_file = Path("data/examples/Network_Config.xlsx")

    print(f"\n1. Loading network configuration from: {network_file}")
    if not network_file.exists():
        print(f"❌ Error: File not found: {network_file}")
        return 1

    # Create parser (network file only for now, no forecast)
    parser = MultiFileParser(network_file=network_file)

    print("\n2. Parsing network configuration sheets...")
    try:
        locations = parser.parse_locations()
        print(f"   ✅ Locations: {len(locations)} locations parsed")

        routes = parser.parse_routes()
        print(f"   ✅ Routes: {len(routes)} routes parsed")

        labor_calendar = parser.parse_labor_calendar()
        print(f"   ✅ LaborCalendar: {len(labor_calendar.days)} days parsed")

        truck_schedules = parser.parse_truck_schedules()
        print(f"   ✅ TruckSchedules: {len(truck_schedules)} truck schedules parsed")

        cost_structure = parser.parse_cost_structure()
        print(f"   ✅ CostParameters: Parsed successfully")

    except Exception as e:
        print(f"❌ Error parsing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Display summaries
    print("\n3. Summary Statistics:")
    print("\n   Locations:")
    location_types = {}
    for loc in locations:
        loc_type = loc.type.value if hasattr(loc.type, 'value') else str(loc.type)
        location_types[loc_type] = location_types.get(loc_type, 0) + 1
    for loc_type, count in sorted(location_types.items()):
        print(f"      - {loc_type}: {count}")

    print("\n   Routes:")
    route_modes = {}
    for route in routes:
        mode = route.transport_mode.value if hasattr(route.transport_mode, 'value') else str(route.transport_mode)
        route_modes[mode] = route_modes.get(mode, 0) + 1
    for mode, count in sorted(route_modes.items()):
        print(f"      - {mode}: {count}")

    print("\n   Labor Calendar:")
    first_day = labor_calendar.days[0]
    last_day = labor_calendar.days[-1]
    print(f"      - Date range: {first_day.date} to {last_day.date}")
    weekdays = sum(1 for day in labor_calendar.days if day.is_fixed_day)
    weekends = len(labor_calendar.days) - weekdays
    print(f"      - Weekdays (fixed): {weekdays} days")
    print(f"      - Weekends/holidays (non-fixed): {weekends} days")

    print("\n   Truck Schedules:")
    morning_trucks = sum(1 for t in truck_schedules if t.is_morning())
    afternoon_trucks = sum(1 for t in truck_schedules if t.is_afternoon())
    print(f"      - Morning trucks: {morning_trucks}")
    print(f"      - Afternoon trucks: {afternoon_trucks}")

    # Check Wednesday special truck
    wed_trucks = [t for t in truck_schedules if t.has_intermediate_stops()]
    if wed_trucks:
        print(f"      - Trucks with intermediate stops: {len(wed_trucks)}")
        for t in wed_trucks:
            print(f"         * {t.truck_name}: {t.intermediate_stops}")

    print("\n   Cost Structure:")
    print(f"      - Production cost: ${cost_structure.production_cost_per_unit}/unit")
    print(f"      - Regular labor rate: ${cost_structure.default_regular_rate}/hour")
    print(f"      - Overtime labor rate: ${cost_structure.default_overtime_rate}/hour")
    print(f"      - Transport (ambient): ${cost_structure.transport_cost_ambient_per_unit}/unit")
    print(f"      - Transport (frozen): ${cost_structure.transport_cost_frozen_per_unit}/unit")

    print("\n4. Validation:")
    # Create a minimal forecast for testing validation
    from src.models import Forecast, ForecastEntry
    from datetime import date

    test_entries = [
        ForecastEntry(
            location_id="6104",
            product_id="TEST",
            forecast_date=date(2025, 6, 2),
            quantity=1000.0
        ),
    ]
    test_forecast = Forecast(name="Test Forecast", entries=test_entries)

    validation = parser.validate_consistency(test_forecast, locations, routes)

    if validation["warnings"]:
        print("   ⚠️ Validation warnings (expected with test forecast):")
        for warning in validation["warnings"]:
            print(f"      - {warning}")
    else:
        print("   ✅ No validation warnings")

    print("\n" + "=" * 60)
    print("✅ Two-file workflow test completed successfully!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
