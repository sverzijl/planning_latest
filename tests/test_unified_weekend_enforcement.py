"""Test unified model weekend truck enforcement."""

import pytest
from datetime import timedelta, date
from pyomo.environ import value
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel


def test_unified_model_weekend_truck_enforcement():
    """Test that unified model properly enforces day-of-week truck constraints."""

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Convert
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules_list, forecast
    )

    # 1-week horizon (includes weekend)
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=6)

    print("\n" + "=" * 80)
    print("TESTING WEEKEND TRUCK ENFORCEMENT")
    print("=" * 80)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=90, mip_gap=0.05)

    print(f"\nSolve Status: {result.termination_condition}")
    print(f"Solve Time: {result.solve_time_seconds:.1f}s")

    assert result.is_optimal() or result.is_feasible(), "Model should solve"

    # Extract truck usage from model
    truck_used_violations = []

    if hasattr(model.model, 'truck_used'):
        for truck_idx in model.model.trucks:
            truck = model.truck_by_index[truck_idx]

            for date_val in model.model.dates:
                truck_used_var = model.model.truck_used[truck_idx, date_val]
                used = value(truck_used_var) if truck_used_var.value is not None else 0

                if used > 0.5:  # Binary threshold
                    # Find route for this truck
                    route = next((r for r in model.routes
                                 if r.origin_node_id == truck.origin_node_id
                                 and r.destination_node_id == truck.destination_node_id), None)

                    if route:
                        departure_date = date_val - timedelta(days=route.transit_days)

                        # Check if truck should run on this departure date
                        if not truck.applies_on_date(departure_date):
                            truck_used_violations.append((
                                truck.id,
                                departure_date,
                                departure_date.strftime('%A'),
                                truck.day_of_week.value if truck.day_of_week else 'DAILY'
                            ))

    print(f"\nWEEKEND TRUCK VIOLATIONS:")
    print("-" * 80)

    if truck_used_violations:
        print(f"❌ FOUND {len(truck_used_violations)} VIOLATIONS:")
        for truck_id, dep_date, day_name, scheduled_day in truck_used_violations:
            print(f"  Truck {truck_id} (scheduled: {scheduled_day}) departed on {dep_date} ({day_name})")
        print()
        assert False, f"Found {len(truck_used_violations)} truck schedule violations"
    else:
        print("✅ NO VIOLATIONS - All trucks respect day-of-week constraints!")
        print("   Unified model properly enforces truck schedules")

    print("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
