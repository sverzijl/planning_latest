"""Test labor cost optimization in isolation.

This test removes all other cost factors (storage, transport, shelf life)
to verify that overtime preference works correctly when it's purely about
labor costs.
"""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products


def test_labor_cost_only_no_storage():
    """Test with ONLY labor costs - no storage, no transport, no shelf life.

    This isolates the labor cost optimization to verify overtime preference
    works when there are no competing cost factors.
    """

    # Load real data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Note: Network_Config.xlsx already has zero transport costs and zero ambient storage
    # We only need to zero out the frozen storage costs for this test
    cost_structure.storage_cost_per_pallet_day_frozen = 0.0
    cost_structure.storage_cost_fixed_per_pallet_frozen = 0.0

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

    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules_list, forecast
    )

    # Use 2-week horizon with moderate demand
    start_date = min(e.forecast_date for e in forecast.entries)
    end_date = start_date + timedelta(weeks=2)

    print("\n" + "="*80)
    print("TEST A: LABOR COSTS ONLY (No Storage, No Shelf Life)")
    print("="*80)
    print("Purpose: Verify overtime preference works without competing cost factors")
    print()

    # Create model WITHOUT storage costs, shelf life, or truck constraints
    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=[],  # NO TRUCK CONSTRAINTS
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=False,  # NO SHELF LIFE CONSTRAINTS
    )

    result = model.solve(time_limit_seconds=120, mip_gap=0.01)

    assert result.success, f"Should solve: {result.infeasibility_message}"

    print(f"Solved: {result.termination_condition}")
    print(f"Total cost: ${result.objective_value:,.2f}")

    # Extract solution
    solution = model.get_solution()
    labor_by_date = solution.get('labor_hours_by_date', {})
    labor_breakdown = solution.get('labor_cost_breakdown', {})

    # Analyze labor usage
    weekday_overtime_hours = 0
    weekend_hours = 0
    weekdays_with_overtime = []
    weekends_with_production = []

    for date, labor_info in labor_by_date.items():
        labor_day = labor_calendar.get_labor_day(date)
        is_weekend = not labor_day.is_fixed_day if labor_day else False

        ot_hours = labor_info.get('overtime', 0)
        hours_paid = labor_info.get('paid', 0)

        if is_weekend and hours_paid > 0.01:
            weekend_hours += hours_paid
            weekends_with_production.append(date)
        elif not is_weekend and ot_hours > 0.01:
            weekday_overtime_hours += ot_hours
            weekdays_with_overtime.append(date)

    print("\n" + "="*80)
    print("LABOR USAGE ANALYSIS")
    print("="*80)
    print(f"Weekday overtime: {weekday_overtime_hours:.2f}h across {len(weekdays_with_overtime)} days")
    print(f"Weekend hours: {weekend_hours:.2f}h across {len(weekends_with_production)} days")

    if weekdays_with_overtime:
        print(f"\nWeekdays with overtime:")
        for date in weekdays_with_overtime:
            print(f"  {date}: {labor_by_date[date].get('overtime', 0):.2f}h OT")

    if weekends_with_production:
        print(f"\nWeekends with production:")
        for date in weekends_with_production:
            print(f"  {date}: {labor_by_date[date].get('paid', 0):.2f}h")

    # Calculate costs
    labor_cost = solution.get('total_labor_cost', 0)
    storage_cost = solution.get('total_holding_cost', 0)

    print(f"\nCost breakdown:")
    print(f"  Labor: ${labor_cost:,.2f}")
    print(f"  Storage: ${storage_cost:,.2f} (should be $0)")

    assert storage_cost < 1.0, "Storage cost should be zero in this test"

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)

    if weekend_hours > 0.01 and weekday_overtime_hours < 9.9:
        print(f"❌ FAIL: With ONLY labor costs, model still uses weekend over overtime!")
        print(f"   This indicates a CONSTRAINT BUG in overtime signaling")
        assert False, "Overtime should be preferred over weekend with pure labor costs"
    elif weekday_overtime_hours > 0.01:
        print(f"✅ PASS: Model uses weekday overtime when only labor costs matter")
        print(f"   If user sees weekend preference, it's due to storage/network constraints")
    else:
        print(f"ℹ️  INFO: Demand fits in regular hours ({weekend_hours:.2f}h weekend)")


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
