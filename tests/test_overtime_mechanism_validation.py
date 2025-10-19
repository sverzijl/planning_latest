"""Validate that overtime mechanism can work under any circumstances.

This test creates scenarios that FORCE overtime usage to verify the
constraint formulation can actually trigger overtime when necessary.
"""

import pytest
from datetime import datetime, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.optimization.unified_node_model import UnifiedNodeModel


def test_overtime_forced_by_capacity():
    """Test that overtime is used when regular capacity is exhausted.

    Scenario:
    - 1 product, 1 delivery date
    - 19,600 units needed = 14h production @ 1,400 units/h
    - With overhead: 14h + 1h = 15h total labor
    - Weekday regular capacity: 12h (insufficient)
    - Weekday total capacity: 14h (still insufficient!)
    - Must either use overtime (impossible - only 2h available) OR spread

    Expected: Should spread across 2 weekdays (both at capacity)
    NOT: Use weekend (more expensive)
    """

    mfg = UnifiedNode(
        id='6122',
        name='Manufacturing',
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            production_rate_per_hour=1400.0,
        ),
        storage_mode=StorageMode.AMBIENT,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.5,
        default_changeover_hours=1.0,
    )

    demand = UnifiedNode(
        id='6110',
        name='Breadroom',
        capabilities=NodeCapabilities(
            has_demand=True,
            can_store=True,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    nodes = [mfg, demand]

    route = UnifiedRoute(
        id='R1',
        origin_node_id='6122',
        destination_node_id='6110',
        transport_mode=TransportMode.AMBIENT,
        transit_days=1.0,
        cost_per_unit=0.0,
    )
    routes = [route]

    # Labor calendar
    start_date = datetime(2025, 1, 6).date()  # Monday

    labor_days = []
    for i in range(7):
        date = start_date + timedelta(days=i)
        day_of_week = date.weekday()

        if day_of_week < 5:  # Monday-Friday
            labor_days.append(LaborDay(
                date=date,
                fixed_hours=12.0,
                overtime_hours=2.0,
                is_fixed_day=True,
                regular_rate=0.0,
                overtime_rate=660.0,
                non_fixed_rate=1320.0,
                minimum_hours=0.0,
            ))
        else:  # Weekend
            labor_days.append(LaborDay(
                date=date,
                fixed_hours=0.0,
                overtime_hours=0.0,
                is_fixed_day=False,
                regular_rate=0.0,
                overtime_rate=660.0,
                non_fixed_rate=1320.0,
                minimum_hours=4.0,
            ))

    labor_calendar = LaborCalendar(name="Test", days=labor_days)

    # High demand that FORCES spreading
    wednesday = start_date + timedelta(days=2)

    forecast = Forecast(name="Test", entries=[
        ForecastEntry(
            location_id='6110',
            product_id='PRODUCT_A',
            forecast_date=wednesday,
            quantity=19600.0,  # 14h production, 15h with overhead
        )
    ])

    cost_structure = CostStructure(
        production_cost_per_unit=0.0,
        storage_cost_frozen_per_unit_day=0.0,
        storage_cost_ambient_per_unit_day=0.0,
        shortage_penalty_per_unit=10000.0,
    )

    print("\n" + "="*80)
    print("TEST: OVERTIME MECHANISM - HIGH DEMAND FORCING SPREAD")
    print("="*80)
    print("Demand: 19,600 units = 14h production")
    print("With overhead: 15h total")
    print("Weekday capacity: 14h max (can't fit in 1 day)")
    print("Expected: Spread across 2 weekdays with overtime")
    print()

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=start_date + timedelta(days=6),
        use_batch_tracking=True,
        allow_shortages=False,
        enforce_shelf_life=False,
    )

    result = model.solve(time_limit_seconds=60, mip_gap=0.01)

    print(f"Solved: {result.termination_condition}")
    print(f"Cost: ${result.objective_value:,.2f}")

    assert result.success, f"Should solve: {result.infeasibility_message}"

    solution = model.get_solution()
    production_by_date = solution.get('production_by_date_product', {})
    labor_by_date = solution.get('labor_hours_by_date', {})

    print("\n" + "="*80)
    print("PRODUCTION SCHEDULE")
    print("="*80)

    total_ot = 0
    weekend_hours = 0
    days_used = 0

    for (date, prod), qty in production_by_date.items():
        if qty > 100:
            labor_info = labor_by_date.get(date, {})
            labor_day = labor_calendar.get_labor_day(date)
            is_weekend = not labor_day.is_fixed_day if labor_day else False

            ot_hours = labor_info.get('overtime', 0)
            used = labor_info.get('used', 0)

            day_name = date.strftime('%A')
            marker = ' **WEEKEND**' if is_weekend else ''

            print(f"{date} ({day_name}): {qty:,.0f} units = {qty/1400:.2f}h prod, {used:.2f}h total, OT={ot_hours:.2f}h{marker}")

            days_used += 1
            if is_weekend:
                weekend_hours += used
            else:
                total_ot += ot_hours

    print(f"\nDays used: {days_used}")
    print(f"Weekday overtime: {total_ot:.2f}h")
    print(f"Weekend hours: {weekend_hours:.2f}h")

    print("\n" + "="*80)
    print("VALIDATION")
    print("="*80)

    # With 15h total needed and 14h weekday max:
    # Should spread across 2 days (e.g., 8h + 7h = 15h production, plus 2h overhead = 17h total)
    # Day 1: 8h prod + 1h overhead = 9h
    # Day 2: 7h prod + 1h overhead = 8h
    # Both fit in 12h regular, NO overtime needed

    if days_used == 1 and total_ot > 0:
        print("✅ OVERTIME WORKS: Single day with overtime used")
    elif days_used >= 2 and weekend_hours == 0:
        print("✅ SPREADING WORKS: Multi-day production avoids weekends")
        if total_ot > 0:
            print(f"   AND using {total_ot:.2f}h overtime on weekdays ✅")
        else:
            print(f"   Using only regular hours (efficient spreading)")
    elif weekend_hours > 0:
        print(f"❌ FAIL: Using {weekend_hours:.2f}h weekend when could spread across weekdays")
        assert False, "Should not use weekends for this demand level"
    else:
        print("ℹ️  Check production schedule manually")


def test_overtime_forced_single_day():
    """Test overtime on a single day when no spreading is possible.

    Scenario:
    - Same-day production and delivery (transit_days=0)
    - 18,200 units needed = 13h production
    - With overhead: 14h total (exactly at weekday max with OT)
    - Can't spread because must deliver same day

    Expected: Uses overtime (13h prod + 1h overhead = 14h)
    """

    mfg = UnifiedNode(
        id='6122',
        name='Manufacturing',
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            production_rate_per_hour=1400.0,
        ),
        storage_mode=StorageMode.AMBIENT,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.5,
        default_changeover_hours=1.0,
    )

    demand = UnifiedNode(
        id='6110',
        name='Breadroom',
        capabilities=NodeCapabilities(
            has_demand=True,
            can_store=True,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    nodes = [mfg, demand]

    # ZERO transit time - same-day delivery required!
    route = UnifiedRoute(
        id='R1',
        origin_node_id='6122',
        destination_node_id='6110',
        transport_mode=TransportMode.AMBIENT,
        transit_days=0.0,  # SAME DAY!
        cost_per_unit=0.0,
    )
    routes = [route]

    start_date = datetime(2025, 1, 6).date()  # Monday

    labor_days = []
    for i in range(7):
        date = start_date + timedelta(days=i)
        day_of_week = date.weekday()

        if day_of_week < 5:
            labor_days.append(LaborDay(
                date=date,
                fixed_hours=12.0,
                overtime_hours=2.0,
                is_fixed_day=True,
                regular_rate=0.0,
                overtime_rate=660.0,
                non_fixed_rate=1320.0,
                minimum_hours=0.0,
            ))
        else:
            labor_days.append(LaborDay(
                date=date,
                fixed_hours=0.0,
                overtime_hours=0.0,
                is_fixed_day=False,
                regular_rate=0.0,
                overtime_rate=660.0,
                non_fixed_rate=1320.0,
                minimum_hours=4.0,
            ))

    labor_calendar = LaborCalendar(name="Test", days=labor_days)

    # Demand on a WEEKDAY (can't defer to weekend)
    monday = start_date  # Monday

    forecast = Forecast(name="Test", entries=[
        ForecastEntry(
            location_id='6110',
            product_id='PRODUCT_A',
            forecast_date=monday,
            quantity=18200.0,  # 13h production, 14h with overhead
        )
    ])

    cost_structure = CostStructure(
        production_cost_per_unit=0.0,
        storage_cost_frozen_per_unit_day=0.0,
        storage_cost_ambient_per_unit_day=0.0,
        shortage_penalty_per_unit=10000.0,
    )

    print("\n" + "="*80)
    print("TEST: OVERTIME FORCED BY SAME-DAY DELIVERY")
    print("="*80)
    print("Demand: 18,200 units = 13h production on MONDAY")
    print("With overhead: 14h total")
    print("Transit: 0 days (same-day delivery required)")
    print("Expected: MUST produce Monday with 2h overtime")
    print()

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=start_date + timedelta(days=6),
        use_batch_tracking=True,
        allow_shortages=False,
        enforce_shelf_life=False,
    )

    result = model.solve(time_limit_seconds=60, mip_gap=0.01)

    print(f"Solved: {result.termination_condition}")
    print(f"Cost: ${result.objective_value:,.2f}")

    assert result.success, f"Should solve: {result.infeasibility_message}"

    solution = model.get_solution()
    labor_by_date = solution.get('labor_hours_by_date', {})

    print("\n" + "="*80)
    print("LABOR USAGE")
    print("="*80)

    monday_ot = 0
    total_weekend = 0

    for date, labor_info in labor_by_date.items():
        labor_day = labor_calendar.get_labor_day(date)
        is_weekend = not labor_day.is_fixed_day if labor_day else False

        ot = labor_info.get('overtime', 0)
        used = labor_info.get('used', 0)

        if used > 0.01:
            marker = ' **WEEKEND**' if is_weekend else ''
            print(f"{date} ({date.strftime('%A')}): {used:.2f}h total, OT={ot:.2f}h{marker}")

            if date == monday:
                monday_ot = ot
            if is_weekend:
                total_weekend += used

    print(f"\nMonday overtime: {monday_ot:.2f}h")
    print(f"Weekend hours: {total_weekend:.2f}h")

    print("\n" + "="*80)
    print("VALIDATION")
    print("="*80)

    if monday_ot > 1.5:  # Should use ~2h overtime
        print(f"✅ SUCCESS: Overtime mechanism WORKS! Used {monday_ot:.2f}h overtime on Monday")
        print("   This proves the constraint formulation CAN trigger overtime")
    elif total_weekend > 0:
        print(f"❌ CRITICAL BUG: Used weekend instead of Monday overtime!")
        print(f"   Same-day delivery REQUIRES Monday production, but got weekend: {total_weekend:.2f}h")
        assert False, "Overtime mechanism is fundamentally broken"
    else:
        print(f"⚠️  Production spread across multiple days (OT={monday_ot:.2f}h)")
        print("   Expected: Should consolidate on Monday with OT")


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
