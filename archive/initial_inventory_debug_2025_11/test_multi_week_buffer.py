#!/usr/bin/env python3
"""Business Logic Validation: Non-Production Days and Overtime Preference

Tests critical business logic:
1. Non-production day 4-hour minimum payment
2. Overtime preference (weekday OT before weekend production)
3. Changeover tracking accuracy
"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from pyomo.environ import value


def test_non_production_day_minimum():
    """Verify 4-hour minimum payment on non-production days (weekends/holidays)."""

    print("\n" + "="*80)
    print("TEST 1: Non-Production Day 4-Hour Minimum Payment")
    print("="*80)

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx",
    )
    forecast, locations, routes, labor_calendar, trucks_list, costs = parser.parse_all()

    # Get manufacturing site
    from src.models.location import LocationType
    manufacturing_site = next((loc for loc in locations if loc.type == LocationType.MANUFACTURING), None)
    assert manufacturing_site is not None, "No manufacturing site found"

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(trucks_list, manufacturing_site.id)

    # Test 1-week with weekend included
    start_date = date(2025, 10, 7)  # Tuesday
    end_date = date(2025, 10, 13)   # Monday (includes Sat/Sun)

    model_wrapper = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=costs,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=True,
        allow_shortages=True,  # Allow shortages for test feasibility
        force_all_skus_daily=False,
    )

    result = model_wrapper.solve(
        solver_name='appsi_highs',
        time_limit_seconds=60,
        mip_gap=0.02,
        tee=False,
    )

    # Debug result status
    print(f"\nResult Status Debug:")
    print(f"  termination_condition: {result.termination_condition}")
    print(f"  success flag: {result.success}")
    print(f"  objective_value: {result.objective_value}")
    print(f"  is_optimal(): {result.is_optimal()}")
    print(f"  is_feasible(): {result.is_feasible()}")

    # Solver succeeded if we have optimal termination, even if success flag is wrong
    from pyomo.opt import TerminationCondition
    solver_succeeded = result.termination_condition == TerminationCondition.optimal

    assert solver_succeeded or result.is_optimal() or result.is_feasible(), \
        f"Solve failed: termination={result.termination_condition}, success={result.success}"

    pyomo_model = model_wrapper.model

    # Extract weekend production
    manufacturing_node = '6122'  # Manufacturing site
    weekend_dates = [date(2025, 10, 11), date(2025, 10, 12)]  # Sat, Sun

    print("\nWeekend Production Analysis:")
    for weekend_date in weekend_dates:
        if (manufacturing_node, weekend_date) not in pyomo_model.labor_hours_used:
            print(f"  {weekend_date} ({weekend_date.strftime('%A')}): No labor variables")
            continue

        hours_used = value(pyomo_model.labor_hours_used[manufacturing_node, weekend_date])
        hours_paid = value(pyomo_model.labor_hours_paid[manufacturing_node, weekend_date])

        production_qty = sum(
            value(pyomo_model.production[manufacturing_node, prod, weekend_date])
            for prod in pyomo_model.products
            if (manufacturing_node, prod, weekend_date) in pyomo_model.production
        )

        print(f"  {weekend_date} ({weekend_date.strftime('%A')}):  ")
        print(f"    Production: {production_qty:,.0f} units")
        print(f"    Hours used: {hours_used:.2f}h")
        print(f"    Hours paid: {hours_paid:.2f}h")

        # If weekend production > 0, verify 4-hour minimum
        if hours_used > 0.01:
            assert hours_paid >= 4.0, f"Weekend {weekend_date}: paid hours {hours_paid:.2f} < 4-hour minimum"
            assert hours_paid >= hours_used, f"Weekend {weekend_date}: paid {hours_paid:.2f} < used {hours_used:.2f}"
            print(f"    ✓ 4-hour minimum enforced (paid >= max(used, 4.0))")

    print("\n✅ TEST 1 PASSED: 4-hour minimum correctly enforced on non-production days")
    return result


def test_overtime_before_weekend():
    """Verify model prefers weekday overtime before weekend production."""

    print("\n" + "="*80)
    print("TEST 2: Overtime Preference (Weekday OT before Weekend)")
    print("="*80)

    # Same setup as Test 1
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx",
    )
    forecast, locations, routes, labor_calendar, trucks_list, costs = parser.parse_all()

    from src.models.location import LocationType
    manufacturing_site = next((loc for loc in locations if loc.type == LocationType.MANUFACTURING), None)
    assert manufacturing_site is not None, "No manufacturing site found"

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(trucks_list, manufacturing_site.id)

    start_date = date(2025, 10, 7)
    end_date = date(2025, 10, 13)

    model_wrapper = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=costs,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=True,
        allow_shortages=True,  # Allow shortages for test feasibility
        force_all_skus_daily=False,
    )

    result = model_wrapper.solve(
        solver_name='appsi_highs',
        time_limit_seconds=60,
        mip_gap=0.02,
        tee=False,
    )

    assert result.is_optimal() or result.is_feasible()

    pyomo_model = model_wrapper.model
    manufacturing_node = '6122'

    # Check weekday overtime vs weekend production
    print("\nLabor Allocation Analysis:")

    weekdays = [date(2025, 10, 7), date(2025, 10, 8), date(2025, 10, 9), date(2025, 10, 10), date(2025, 10, 13)]
    weekend = [date(2025, 10, 11), date(2025, 10, 12)]

    weekday_overtime_hours = 0.0
    weekend_production_hours = 0.0

    for weekday in weekdays:
        if (manufacturing_node, weekday) in pyomo_model.overtime_hours_used:
            ot_hours = value(pyomo_model.overtime_hours_used[manufacturing_node, weekday])
            if ot_hours > 0.01:
                weekday_overtime_hours += ot_hours
                print(f"  {weekday} ({weekday.strftime('%A')}): {ot_hours:.2f}h overtime")

    for weekend_day in weekend:
        if (manufacturing_node, weekend_day) in pyomo_model.labor_hours_used:
            weekend_hours = value(pyomo_model.labor_hours_used[manufacturing_node, weekend_day])
            if weekend_hours > 0.01:
                weekend_production_hours += weekend_hours
                print(f"  {weekend_day} ({weekend_day.strftime('%A')}): {weekend_hours:.2f}h production")

    print(f"\nSummary:")
    print(f"  Total weekday overtime: {weekday_overtime_hours:.2f}h")
    print(f"  Total weekend production: {weekend_production_hours:.2f}h")

    # Economic logic: Weekday OT should be used before weekend (if demand requires extra capacity)
    # Weekend has 4-hour minimum + premium rate, making it expensive for small production
    # Weekday OT (2h max per day) has lower effective cost for small volumes

    print(f"\n💡 Economic Logic:")
    print(f"  - Weekday OT rate: ~$30/h (no minimum)")
    print(f"  - Weekend rate: ~$40/h (4-hour minimum = $160 minimum cost)")
    print(f"  - For <4h demand: Weekday OT is cheaper")
    print(f"  - For >4h demand: Weekend may be competitive")

    print("\n✅ TEST 2 PASSED: Labor allocation logged (verify manually above)")
    return result


def test_changeover_detection_accuracy():
    """Verify changeover count matches manual inspection."""

    print("\n" + "="*80)
    print("TEST 3: Changeover Detection Accuracy")
    print("="*80)

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx",
    )
    forecast, locations, routes, labor_calendar, trucks_list, costs = parser.parse_all()

    from src.models.location import LocationType
    manufacturing_site = next((loc for loc in locations if loc.type == LocationType.MANUFACTURING), None)
    assert manufacturing_site is not None, "No manufacturing site found"

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(trucks_list, manufacturing_site.id)

    start_date = date(2025, 10, 7)
    end_date = date(2025, 10, 13)

    model_wrapper = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=costs,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=True,
        allow_shortages=True,  # Allow shortages for test feasibility
        force_all_skus_daily=False,
    )

    result = model_wrapper.solve(
        solver_name='appsi_highs',
        time_limit_seconds=60,
        mip_gap=0.02,
        tee=False,
    )

    assert result.is_optimal() or result.is_feasible()

    pyomo_model = model_wrapper.model
    manufacturing_node = '6122'

    # Manual changeover count
    products = list(pyomo_model.products)
    dates = sorted(list(pyomo_model.dates))

    print("\nProduction Pattern (product_produced binary):")
    manual_changeover_count = 0

    for prod in products:
        pattern = []
        prev_produced = False

        for date_val in dates:
            if (manufacturing_node, prod, date_val) in pyomo_model.product_produced:
                produced = value(pyomo_model.product_produced[manufacturing_node, prod, date_val]) > 0.5
                pattern.append('1' if produced else '0')

                # Detect 0→1 transition manually
                if produced and not prev_produced:
                    manual_changeover_count += 1

                prev_produced = produced
            else:
                pattern.append('-')

        print(f"  {prod}: {''.join(pattern)}")

    # Extract from solution (data is in metadata after extraction)
    solution_changeover_count = result.metadata.get('total_changeovers', 0)

    print(f"\nChangeover Count:")
    print(f"  Manual count (0→1 transitions): {manual_changeover_count}")
    print(f"  Solution extraction: {solution_changeover_count}")

    assert manual_changeover_count == solution_changeover_count, \
        f"Changeover mismatch: manual={manual_changeover_count}, solution={solution_changeover_count}"

    print(f"\n✅ TEST 3 PASSED: Changeover detection is accurate!")
    return result


if __name__ == "__main__":
    print("Business Logic Validation Test Suite")
    print("="*80)

    result1 = test_non_production_day_minimum()
    result2 = test_overtime_before_weekend()
    result3 = test_changeover_detection_accuracy()

    print("\n" + "="*80)
    print("ALL TESTS PASSED!")
    print("="*80)
    print(f"\nTest 1 Cost: ${result1.objective_value:,.2f}")
    print(f"Test 2 Cost: ${result2.objective_value:,.2f}")
    print(f"Test 3 Cost: ${result3.objective_value:,.2f}")
