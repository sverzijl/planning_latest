"""Minimal test case to isolate overtime preference issue.

Ultra-simple scenario with no complexity - pure labor cost optimization.
"""

import pytest
from datetime import datetime, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.optimization.unified_node_model import UnifiedNodeModel


def test_minimal_overtime_preference():
    """Ultra-minimal test: 1 product, 1 demand, should use weekday overtime.

    Scenario:
    - 1 product only
    - 18,000 units demand on Wednesday (= 13h production @ 1,400 units/h)
    - Overhead: 1h (startup + shutdown, no changeover)
    - Total: 14h (fits exactly in weekday with 2h overtime)
    - No storage costs, no shelf life constraints, no complexity

    Expected:
    - Production on Monday OR Tuesday (before Wednesday delivery)
    - Labor: 12h regular (@ $0) + 2h overtime (@ $660) = $1,320 total
    - NOT weekend production (would be 14h × $1,320 = $18,480)
    """

    # Manufacturing node
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

    # Demand node
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

    # Route (1 day transit)
    route = UnifiedRoute(
        id='R1',
        origin_node_id='6122',
        destination_node_id='6110',
        transport_mode=TransportMode.AMBIENT,
        transit_days=1.0,
        cost_per_unit=0.0,  # Zero transport cost to focus on labor
    )
    routes = [route]

    # Labor calendar - Monday through Sunday
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
                regular_rate=0.0,  # Salaried (free)
                overtime_rate=660.0,  # Expensive but cheaper than weekend
                non_fixed_rate=1320.0,  # Most expensive
                minimum_hours=0.0,
            ))
        else:  # Saturday-Sunday
            labor_days.append(LaborDay(
                date=date,
                fixed_hours=0.0,
                overtime_hours=0.0,
                is_fixed_day=False,
                regular_rate=0.0,
                overtime_rate=660.0,
                non_fixed_rate=1320.0,  # Most expensive
                minimum_hours=4.0,
            ))

    labor_calendar = LaborCalendar(name="Minimal Test", days=labor_days)

    # Forecast: Single product, single delivery date
    wednesday = start_date + timedelta(days=2)  # Wednesday

    forecast = Forecast(name="Minimal Test", entries=[
        ForecastEntry(
            location_id='6110',
            product_id='PRODUCT_A',
            forecast_date=wednesday,
            quantity=18200.0,  # 13h production @ 1400 units/h
        )
    ])

    # Cost structure - zero everything except labor
    cost_structure = CostStructure(
        production_cost_per_unit=0.0,
        storage_cost_frozen_per_unit_day=0.0,
        storage_cost_ambient_per_unit_day=0.0,
        storage_cost_per_pallet_day_frozen=0.0,
        storage_cost_per_pallet_day_ambient=0.0,
        shortage_penalty_per_unit=10000.0,
    )

    # Build model
    print("\n" + "="*80)
    print("BUILDING MINIMAL TEST MODEL")
    print("="*80)

    model_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=start_date + timedelta(days=6),
        use_batch_tracking=True,
        allow_shortages=False,
        enforce_shelf_life=False,  # Disable to remove complexity
    )

    # Solve
    result = model_obj.solve(time_limit_seconds=60, mip_gap=0.01)

    print(f"\nSolver status: {result.termination_condition}")
    print(f"Success: {result.success}")
    print(f"Objective: ${result.objective_value:,.2f}")

    assert result.success, f"Should solve successfully: {result.infeasibility_message}"

    # Extract solution
    solution = model_obj.get_solution()

    production_by_date = solution.get('production_by_date_product', {})
    labor_breakdown = solution.get('labor_cost_breakdown', {})

    print("\n" + "="*80)
    print("PRODUCTION SCHEDULE")
    print("="*80)

    weekday_production_hours = 0
    weekend_production_hours = 0
    weekday_overtime_used = 0
    weekend_hours_used = 0

    for (date, prod), qty in production_by_date.items():
        if qty > 100:
            day_name = date.strftime('%A')
            labor_day = labor_calendar.get_labor_day(date)
            is_weekend = not labor_day.is_fixed_day if labor_day else False

            prod_hours = qty / 1400.0
            labor_info = labor_breakdown.get(date, {})

            print(f"\n{date} ({day_name}):")
            print(f"  Production: {qty:,.0f} units ({prod_hours:.2f}h)")

            if labor_info:
                print(f"  Fixed hours: {labor_info.get('fixed_hours_used', 0):.2f}h")
                print(f"  Overtime hours: {labor_info.get('overtime_hours_used', 0):.2f}h")
                print(f"  Cost: ${labor_info.get('total_cost', 0):,.2f}")

                if is_weekend:
                    weekend_production_hours += prod_hours
                    weekend_hours_used += labor_info.get('hours_paid', 0)
                else:
                    weekday_production_hours += prod_hours
                    weekday_overtime_used += labor_info.get('overtime_hours_used', 0)

    print("\n" + "="*80)
    print("VALIDATION")
    print("="*80)

    print(f"Weekday production hours: {weekday_production_hours:.2f}h")
    print(f"Weekday overtime used: {weekday_overtime_used:.2f}h (max available: 10h)")
    print(f"Weekend production hours: {weekend_production_hours:.2f}h")
    print(f"Weekend hours charged: {weekend_hours_used:.2f}h")

    print(f"\nWeekday overtime cost: ${weekday_overtime_used * 660:,.2f}")
    print(f"Weekend cost: ${weekend_hours_used * 1320:,.2f}")

    # Critical checks
    if weekend_hours_used > 0:
        print(f"\n❌ FAIL: Weekend production detected when overtime available!")
        print(f"   Should use {min(weekend_hours_used, 10 - weekday_overtime_used):.2f}h overtime instead")
        print(f"   Potential savings: ${min(weekend_hours_used, 10 - weekday_overtime_used) * (1320 - 660):,.2f}")

        assert False, "Model should prefer weekday overtime over weekend production"
    else:
        print(f"\n✅ PASS: No weekend production (all done on weekdays)")

    # Check that overtime was actually used
    if weekday_production_hours > 60:  # More than 5 days × 12h regular
        expected_ot = weekday_production_hours - 60
        print(f"\nExpected overtime: ~{expected_ot:.2f}h")
        print(f"Actual overtime: {weekday_overtime_used:.2f}h")

        assert weekday_overtime_used > 0, "Should use overtime when production > 60h"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
