"""Test overtime vs non-work day cost preference.

This test validates that the model correctly prefers cheaper weekday overtime
over more expensive weekend/holiday production.
"""

import pytest
from datetime import datetime, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import Location
from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.optimization.unified_node_model import UnifiedNodeModel


def test_overtime_preference_over_weekend():
    """Test that model prefers weekday overtime over weekend production.

    Scenario:
    - Weekday: 12h fixed @ $20/h, 2h OT @ $30/h = $240 + $60 = $300 for 14h
    - Weekend: 14h @ $40/h = $560 for 14h
    - Demand requires 13h of production (needs 1h overtime)
    - Expected: Schedule on weekday with 1h overtime, NOT weekend
    """

    # Create manufacturing node
    mfg_node = UnifiedNode(
        id='MFG',
        name='Manufacturing',
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            production_rate_per_hour=1000.0,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    # Create demand node
    demand_node = UnifiedNode(
        id='DEMAND',
        name='Customer',
        capabilities=NodeCapabilities(
            has_demand=True,
            can_store=True,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    nodes = [mfg_node, demand_node]

    # Create route
    route = UnifiedRoute(
        id='R1',
        origin_node_id='MFG',
        destination_node_id='DEMAND',
        transport_mode=TransportMode.AMBIENT,
        transit_days=1.0,
        cost_per_unit=0.1,  # Small transport cost
    )
    routes = [route]

    # Create labor calendar with clear cost structure
    # Monday-Friday: Fixed days with overtime
    # Saturday-Sunday: Non-fixed days
    start_date = datetime(2025, 1, 6).date()  # Monday

    labor_days = []
    for i in range(7):
        date = start_date + timedelta(days=i)
        day_of_week = date.weekday()  # 0=Monday, 6=Sunday

        if day_of_week < 5:  # Monday-Friday
            labor_days.append(LaborDay(
                date=date,
                fixed_hours=12.0,
                overtime_hours=2.0,
                is_fixed_day=True,
                regular_rate=20.0,
                overtime_rate=30.0,
                non_fixed_rate=40.0,  # Not used on fixed days but needs a value
                minimum_hours=0.0,
            ))
        else:  # Saturday-Sunday
            labor_days.append(LaborDay(
                date=date,
                fixed_hours=0.0,
                overtime_hours=0.0,
                is_fixed_day=False,
                regular_rate=20.0,  # Not used on non-fixed days
                overtime_rate=30.0,  # Not used on non-fixed days
                non_fixed_rate=40.0,  # Most expensive
                minimum_hours=4.0,
            ))

    labor_calendar = LaborCalendar(labor_days=labor_days)

    # Create forecast: 13,000 units needed on Wed (requires 13h production)
    wednesday = start_date + timedelta(days=2)

    forecast = Forecast(entries=[
        ForecastEntry(
            location_id='DEMAND',
            product_id='PRODUCT_A',
            forecast_date=wednesday,
            quantity=13000.0,  # 13,000 units = 13h @ 1000 units/h
        )
    ])

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=0.0,  # Focus on labor costs only
        storage_cost_frozen_per_unit_day=0.0,
        storage_cost_ambient_per_unit_day=0.0,
        shortage_penalty_per_unit=10000.0,
    )

    # Create model
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=start_date + timedelta(days=6),
        use_batch_tracking=False,  # Simpler for this test
        allow_shortages=False,
        enforce_shelf_life=False,
    )

    # Solve
    result = model.solve(time_limit_seconds=60, mip_gap=0.01)

    print("\n" + "="*80)
    print("OVERTIME PREFERENCE TEST RESULTS")
    print("="*80)
    print(f"Solver Status: {result.termination_condition}")
    print(f"Success: {result.success}")
    print(f"Total Cost: ${result.objective_value:,.2f}")
    print()

    # Validate solution
    assert result.success, f"Solution should succeed. Error: {result.infeasibility_message}"
    assert result.is_optimal(), "Solution should be optimal"

    # Get solution details
    solution = model.get_solution()

    # Check production schedule
    production_by_date = solution.get('production_by_date_product', {})
    labor_by_date = solution.get('labor_hours_by_date', {})
    labor_breakdown = solution.get('labor_cost_breakdown', {})

    print("Production Schedule:")
    for (date, prod), qty in production_by_date.items():
        if qty > 100:
            day_name = date.strftime('%A')
            print(f"  {date} ({day_name}): {qty:,.0f} units")

    print("\nLabor Hours Used:")
    for date, hours in labor_by_date.items():
        day_name = date.strftime('%A')
        labor_info = labor_breakdown.get(date, {})
        print(f"  {date} ({day_name}): {hours:.2f}h used")
        if labor_info:
            print(f"    Fixed hours: {labor_info.get('fixed_hours_used', 0):.2f}h")
            print(f"    Overtime hours: {labor_info.get('overtime_hours_used', 0):.2f}h")
            print(f"    Cost: ${labor_info.get('total_cost', 0):.2f}")

    print("\nLabor Cost Breakdown:")
    total_labor = solution.get('total_labor_cost', 0)
    print(f"  Total Labor Cost: ${total_labor:,.2f}")

    # CRITICAL CHECKS
    print("\n" + "="*80)
    print("VALIDATION CHECKS")
    print("="*80)

    # Check 1: Production should occur on a weekday (Monday-Friday)
    weekday_production = sum(
        qty for (date, prod), qty in production_by_date.items()
        if date.weekday() < 5
    )
    weekend_production = sum(
        qty for (date, prod), qty in production_by_date.items()
        if date.weekday() >= 5
    )

    print(f"Weekday production: {weekday_production:,.0f} units")
    print(f"Weekend production: {weekend_production:,.0f} units")

    assert weekday_production >= 13000, \
        f"Should produce on weekday! Weekday={weekday_production}, Weekend={weekend_production}"

    # Check 2: Overtime should be used (not weekend)
    weekday_with_production = [
        date for (date, prod), qty in production_by_date.items()
        if qty > 100 and date.weekday() < 5
    ]

    assert len(weekday_with_production) > 0, "Should have weekday production"

    # Check for overtime usage
    production_date = weekday_with_production[0]
    labor_info = labor_breakdown.get(production_date, {})

    overtime_used = labor_info.get('overtime_hours_used', 0)
    print(f"\nOvertime hours used on {production_date}: {overtime_used:.2f}h")

    assert overtime_used > 0.5, \
        f"Should use overtime! Only {overtime_used:.2f}h overtime used"

    # Check 3: Labor cost should reflect overtime rate, not weekend rate
    # Expected: ~$20/h * 12h + $30/h * 1h = $240 + $30 = $270
    # NOT: $40/h * 13h = $520

    print(f"\nExpected cost: ~$270 (weekday with 1h OT)")
    print(f"Actual cost: ${total_labor:.2f}")
    print(f"Weekend cost would be: ~$560 (14h @ $40/h with 4h minimum)")

    assert total_labor < 400, \
        f"Labor cost too high! Got ${total_labor:.2f}, expected ~$270 (weekday OT), not ~$560 (weekend)"

    print("\n✅ ALL CHECKS PASSED: Model correctly prefers weekday overtime over weekend")
    print("="*80)


def test_weekend_only_when_necessary():
    """Test that weekends are only used when weekday capacity is exhausted.

    Scenario:
    - High demand that exceeds weekday capacity
    - Weekdays: 12h + 2h OT = 14h max
    - Weekend needed for overflow demand
    """

    # Create manufacturing node
    mfg_node = UnifiedNode(
        id='MFG',
        name='Manufacturing',
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            production_rate_per_hour=1000.0,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    demand_node = UnifiedNode(
        id='DEMAND',
        name='Customer',
        capabilities=NodeCapabilities(
            has_demand=True,
            can_store=True,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    nodes = [mfg_node, demand_node]

    route = UnifiedRoute(
        id='R1',
        origin_node_id='MFG',
        destination_node_id='DEMAND',
        transport_mode=TransportMode.AMBIENT,
        transit_days=1.0,
        cost_per_unit=0.1,
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
                regular_rate=20.0,
                overtime_rate=30.0,
                non_fixed_rate=40.0,  # Not used on fixed days but needs a value
                minimum_hours=0.0,
            ))
        else:  # Saturday-Sunday
            labor_days.append(LaborDay(
                date=date,
                fixed_hours=0.0,
                overtime_hours=0.0,
                is_fixed_day=False,
                regular_rate=20.0,  # Not used on non-fixed days
                overtime_rate=30.0,  # Not used on non-fixed days
                non_fixed_rate=40.0,
                minimum_hours=4.0,
            ))

    labor_calendar = LaborCalendar(labor_days=labor_days)

    # Very high demand: 100,000 units (100h of production)
    # Weekdays can only do: 5 days × 14h = 70h = 70,000 units
    # Need weekend to meet demand
    wednesday = start_date + timedelta(days=2)

    forecast = Forecast(entries=[
        ForecastEntry(
            location_id='DEMAND',
            product_id='PRODUCT_A',
            forecast_date=wednesday,
            quantity=100000.0,  # Very high demand
        )
    ])

    cost_structure = CostStructure(
        production_cost_per_unit=0.0,
        storage_cost_frozen_per_unit_day=0.0,
        storage_cost_ambient_per_unit_day=0.0,
        shortage_penalty_per_unit=10000.0,
    )

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=start_date + timedelta(days=6),
        use_batch_tracking=False,
        allow_shortages=False,
        enforce_shelf_life=False,
    )

    result = model.solve(time_limit_seconds=60, mip_gap=0.01)

    print("\n" + "="*80)
    print("WEEKEND USAGE TEST (HIGH DEMAND)")
    print("="*80)

    assert result.success, f"Solution should succeed. Error: {result.infeasibility_message}"

    solution = model.get_solution()
    production_by_date = solution.get('production_by_date_product', {})

    weekday_production = sum(
        qty for (date, prod), qty in production_by_date.items()
        if date.weekday() < 5
    )
    weekend_production = sum(
        qty for (date, prod), qty in production_by_date.items()
        if date.weekday() >= 5
    )

    print(f"Weekday production: {weekday_production:,.0f} units")
    print(f"Weekend production: {weekend_production:,.0f} units")
    print(f"Total production: {weekday_production + weekend_production:,.0f} units")

    # Weekdays should be maxed out first
    assert weekday_production > 60000, \
        f"Weekdays should be fully utilized! Only {weekday_production:,.0f} units on weekdays"

    # Weekend should be used for overflow
    assert weekend_production > 0, \
        f"Weekend should be used for high demand! {weekend_production:,.0f} units on weekend"

    print("\n✅ Weekend correctly used only when weekday capacity exhausted")
    print("="*80)


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
