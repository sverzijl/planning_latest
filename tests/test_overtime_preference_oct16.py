"""Investigation: Overtime Preference - Oct 16 4-Week Scenario

User reported unexpected behavior:
- Weekends used in weeks 1-3 (Saturdays/Sundays)
- NO overtime in first two weeks
- Overtime only in week with public holiday

EXPECTED behavior:
- Weekday overtime (12-14h, $30/h) should be used BEFORE weekends
- Weekends (4h minimum, $40/h) should be last resort
- Economic: 2h OT = $60 vs 4h weekend minimum = $160

This test investigates WHY the model prefers weekends over overtime.
"""

import pytest
from datetime import date
from pathlib import Path
from pyomo.environ import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.location import LocationType


def test_overtime_preference_oct16_4weeks():
    """Reproduce Oct 16 4-week scenario and investigate labor allocation."""

    print("\n" + "="*80)
    print("OVERTIME PREFERENCE INVESTIGATION: Oct 16 4-Week Scenario")
    print("="*80)

    # Load data
    data_dir = Path(__file__).parent.parent / "data" / "examples"
    parser = MultiFileParser(
        forecast_file=str(data_dir / "Gluten Free Forecast - Latest.xlsm"),
        network_file=str(data_dir / "Network_Config.xlsx"),
        inventory_file=str(data_dir / "inventory_latest.XLSX"),
    )

    forecast, locations, routes, labor_calendar, trucks_list, costs = parser.parse_all()
    manufacturing_site = next((loc for loc in locations if loc.type == LocationType.MANUFACTURING), None)

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(trucks_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot
    inventory_snapshot_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # Oct 16 start, 4 weeks
    start_date = date(2025, 10, 16)
    end_date = date(2025, 11, 12)

    print(f"\nScenario: {start_date} to {end_date} (28 days)")

    model_wrapper = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=costs,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,
    )

    result = model_wrapper.solve(
        solver_name='appsi_highs',
        time_limit_seconds=600,
        mip_gap=0.02,
        tee=False,
    )

    print(f"\nSolve completed: {result.termination_condition}, {result.solve_time_seconds:.1f}s")

    from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC
    assert result.termination_condition == AppsiTC.optimal or result.is_feasible()

    pyomo_model = model_wrapper.model
    manufacturing_node = '6122'

    # Analyze labor allocation for all 28 days
    print(f"\n" + "="*80)
    print("LABOR ALLOCATION ANALYSIS")
    print("="*80)

    weekday_ot_total = 0.0
    weekend_total = 0.0
    weekday_ot_days = []
    weekend_days = []

    for date_val in sorted(list(pyomo_model.dates)):
        if (manufacturing_node, date_val) not in pyomo_model.labor_hours_used:
            continue

        labor_day = labor_calendar.get_labor_day(date_val)
        if not labor_day:
            continue

        hours_used = value(pyomo_model.labor_hours_used[manufacturing_node, date_val])

        if hours_used < 0.01:
            continue

        day_name = date_val.strftime('%a')

        if labor_day.is_fixed_day:
            # Weekday - check for overtime
            ot_hours = value(pyomo_model.overtime_hours_used[manufacturing_node, date_val]) if (manufacturing_node, date_val) in pyomo_model.overtime_hours_used else 0.0
            if ot_hours > 0.01:
                weekday_ot_total += ot_hours
                weekday_ot_days.append((date_val, day_name, hours_used, ot_hours))
                print(f"  {date_val} ({day_name}): {hours_used:.2f}h total, {ot_hours:.2f}h OT ⚡")
            else:
                print(f"  {date_val} ({day_name}): {hours_used:.2f}h (no OT)")
        else:
            # Weekend/holiday
            weekend_total += hours_used
            weekend_days.append((date_val, day_name, hours_used))
            print(f"  {date_val} ({day_name}): {hours_used:.2f}h WEEKEND 🔶")

    print(f"\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"  Weekday overtime: {weekday_ot_total:.2f}h over {len(weekday_ot_days)} days")
    print(f"  Weekend production: {weekend_total:.2f}h over {len(weekend_days)} days")

    # Cost analysis
    print(f"\n" + "="*80)
    print("COST ANALYSIS")
    print("="*80)

    # Check labor rates
    sample_weekday = next((d for d in pyomo_model.dates if labor_calendar.get_labor_day(d) and labor_calendar.get_labor_day(d).is_fixed_day), None)
    sample_weekend = next((d for d in pyomo_model.dates if labor_calendar.get_labor_day(d) and not labor_calendar.get_labor_day(d).is_fixed_day), None)

    if sample_weekday:
        wd_labor = labor_calendar.get_labor_day(sample_weekday)
        print(f"  Weekday rates:")
        print(f"    Regular: ${wd_labor.regular_rate:.2f}/h")
        print(f"    Overtime: ${wd_labor.overtime_rate:.2f}/h")
        print(f"    2h OT cost: ${wd_labor.overtime_rate * 2:.2f}")

    if sample_weekend:
        we_labor = labor_calendar.get_labor_day(sample_weekend)
        print(f"  Weekend rates:")
        print(f"    Non-fixed: ${we_labor.non_fixed_rate:.2f}/h")
        print(f"    4h minimum cost: ${we_labor.non_fixed_rate * 4:.2f}")

    # Economic comparison
    if sample_weekday and sample_weekend:
        ot_cost_2h = wd_labor.overtime_rate * 2
        weekend_min_cost = we_labor.non_fixed_rate * 4

        print(f"\n  Economic Comparison:")
        print(f"    2h weekday OT: ${ot_cost_2h:.2f}")
        print(f"    4h weekend minimum: ${weekend_min_cost:.2f}")
        print(f"    Preference: {'OT is cheaper ✓' if ot_cost_2h < weekend_min_cost else 'WEEKEND CHEAPER ⚠️'}")

    # CRITICAL CHECK: If weekends used but OT available
    weekday_dates_with_capacity = [
        d for d in pyomo_model.dates
        if labor_calendar.get_labor_day(d) and labor_calendar.get_labor_day(d).is_fixed_day
    ]

    total_ot_capacity_available = len(weekday_dates_with_capacity) * 2  # 2h OT per weekday
    total_ot_used = weekday_ot_total

    print(f"\n" + "="*80)
    print("CAPACITY CHECK")
    print("="*80)
    print(f"  Total weekday OT capacity: {total_ot_capacity_available:.0f}h")
    print(f"  Total weekday OT used: {total_ot_used:.2f}h")
    print(f"  Unused OT capacity: {total_ot_capacity_available - total_ot_used:.2f}h")

    if weekend_total > 0 and (total_ot_capacity_available - total_ot_used) > 1.0:
        print(f"\n  ❌ UNEXPECTED: Using {weekend_total:.2f}h weekend when {total_ot_capacity_available - total_ot_used:.2f}h OT available")
        print(f"     This suggests overtime preference is not working correctly!")
        print(f"     Expected: Use weekday OT first (cheaper), weekends only when OT exhausted")
    else:
        print(f"\n  ✓ OK: OT capacity exhausted or nearly exhausted before using weekends")

    print(f"\n" + "="*80)
    print("EVIDENCE GATHERING COMPLETE")
    print("="*80)


if __name__ == "__main__":
    test_overtime_preference_oct16_4weeks()
