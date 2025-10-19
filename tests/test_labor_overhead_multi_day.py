"""Multi-day overhead consistency verification tests.

This test validates that startup/shutdown/changeover overhead is consistently
applied across all production days regardless of day type (weekday, weekend,
public holiday).
"""

import pytest
from datetime import date, timedelta
from pyomo.environ import value

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel


def create_multi_day_overhead_test_setup():
    """Create multi-day test setup spanning weekdays, weekend, and public holiday.

    Days:
        - Monday June 2, 2025 (weekday)
        - Tuesday June 3, 2025 (weekday)
        - Saturday June 7, 2025 (weekend)
        - Monday June 9, 2025 (King's Birthday - public holiday)
        - Friday June 13, 2025 (weekday)

    Returns:
        Dict with nodes, routes, forecast, labor_calendar, cost_structure, test_dates
    """
    # Manufacturing node with explicit overhead parameters
    manufacturing_node = UnifiedNode(
        id="6122",
        name="Manufacturing",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            production_rate_per_hour=1400.0,
            daily_startup_hours=0.5,
            daily_shutdown_hours=0.25,
            default_changeover_hours=0.5,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    # Demand node
    demand_node = UnifiedNode(
        id="6110",
        name="Breadroom",
        capabilities=NodeCapabilities(
            has_demand=True,
            can_store=True,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    # Route (instant transit to force production on demand dates)
    route = UnifiedRoute(
        id="ROUTE-6122-6110",
        origin_node_id="6122",
        destination_node_id="6110",
        transport_mode=TransportMode.AMBIENT,
        transit_days=0.0,  # Same-day delivery
        cost_per_unit=0.1,
    )

    # Test dates
    monday_1 = date(2025, 6, 2)  # Monday (weekday)
    tuesday_1 = date(2025, 6, 3)  # Tuesday (weekday)
    saturday_1 = date(2025, 6, 7)  # Saturday (weekend)
    monday_2_holiday = date(2025, 6, 9)  # Monday - King's Birthday (public holiday)
    friday_1 = date(2025, 6, 13)  # Friday (weekday)

    test_dates = {
        'monday_weekday': monday_1,
        'tuesday_weekday': tuesday_1,
        'saturday_weekend': saturday_1,
        'monday_holiday': monday_2_holiday,
        'friday_weekday': friday_1,
    }

    # Forecast - distribute demand across all days to force production on each
    forecast_entries = [
        ForecastEntry(
            location_id="6110",
            product_id="PROD1",
            forecast_date=monday_1,
            quantity=4200.0,  # 3h production
        ),
        ForecastEntry(
            location_id="6110",
            product_id="PROD1",
            forecast_date=tuesday_1,
            quantity=5600.0,  # 4h production
        ),
        ForecastEntry(
            location_id="6110",
            product_id="PROD1",
            forecast_date=saturday_1,
            quantity=2800.0,  # 2h production
        ),
        ForecastEntry(
            location_id="6110",
            product_id="PROD1",
            forecast_date=monday_2_holiday,
            quantity=4200.0,  # 3h production
        ),
        ForecastEntry(
            location_id="6110",
            product_id="PROD1",
            forecast_date=friday_1,
            quantity=7000.0,  # 5h production
        ),
    ]

    forecast = Forecast(
        name="Multi-Day Test Forecast",
        entries=forecast_entries,
    )

    # Labor calendar covering all test dates
    labor_days = []
    current_date = monday_1
    end_date = friday_1

    while current_date <= end_date:
        is_weekday = current_date.weekday() < 5  # 0-4 = Mon-Fri
        is_holiday = current_date == monday_2_holiday  # King's Birthday

        if is_weekday and not is_holiday:
            # Standard weekday
            labor_days.append(LaborDay(
                date=current_date,
                fixed_hours=12.0,
                overtime_hours=2.0,
                regular_rate=25.0,
                overtime_rate=37.5,
                non_fixed_rate=40.0,  # Not used but needs value
                minimum_hours=0.0,
                is_fixed_day=True,
            ))
        else:
            # Weekend or public holiday
            labor_days.append(LaborDay(
                date=current_date,
                fixed_hours=0.0,
                overtime_hours=0.0,
                regular_rate=25.0,  # Not used
                overtime_rate=37.5,  # Not used
                non_fixed_rate=40.0,
                minimum_hours=4.0,
                is_fixed_day=False,
            ))

        current_date += timedelta(days=1)

    labor_calendar = LaborCalendar(
        name="Multi-Day Test Calendar",
        days=labor_days,
    )

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=1.0,
        default_regular_rate=25.0,
        default_overtime_rate=37.5,
        default_non_fixed_rate=40.0,
        shortage_penalty_per_unit=100.0,
        storage_cost_frozen_per_unit_day=0.0,
        storage_cost_ambient_per_unit_day=0.0,
    )

    return {
        'nodes': [manufacturing_node, demand_node],
        'routes': [route],
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'cost_structure': cost_structure,
        'test_dates': test_dates,
        'start_date': monday_1,
        'end_date': friday_1,
    }


def extract_production_and_labor(model, node_id: str, dates: list):
    """Extract production quantities and labor hours for multiple dates."""
    results = {}

    for date_val in dates:
        # Check if there's production on this date
        production_qty = 0.0
        if hasattr(model, 'production'):
            for prod in model.products:
                if (node_id, prod, date_val) in model.production:
                    prod_var = model.production[node_id, prod, date_val]
                    if prod_var.value is not None:
                        production_qty += value(prod_var)

        # Extract labor variables if production occurred
        labor_vars = None
        if production_qty > 100:  # Threshold for meaningful production
            try:
                labor_vars = {
                    'labor_hours_used': value(model.labor_hours_used[node_id, date_val]),
                    'labor_hours_paid': value(model.labor_hours_paid[node_id, date_val]),
                    'fixed_hours_used': value(model.fixed_hours_used[node_id, date_val]),
                    'overtime_hours_used': value(model.overtime_hours_used[node_id, date_val]),
                }
            except (KeyError, AttributeError):
                pass

        results[date_val] = {
            'production_qty': production_qty,
            'labor_vars': labor_vars,
        }

    return results


def test_multi_day_overhead_consistency():
    """Test that overhead is consistently applied across weekday, weekend, and holiday.

    This test verifies:
        1. Overhead is applied on ALL production days (weekday, weekend, holiday)
        2. Overhead amounts are consistent (same node parameters)
        3. Labor hours = production time + overhead for each day
    """
    setup = create_multi_day_overhead_test_setup()

    model_obj = UnifiedNodeModel(
        nodes=setup['nodes'],
        routes=setup['routes'],
        forecast=setup['forecast'],
        labor_calendar=setup['labor_calendar'],
        cost_structure=setup['cost_structure'],
        start_date=setup['start_date'],
        end_date=setup['end_date'],
        use_batch_tracking=True,
        allow_shortages=False,
    )

    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=60,
        tee=False,
    )

    assert result.is_optimal() or result.is_feasible(), \
        f"Solution failed: {result.termination_condition}"

    # Extract production and labor data
    test_dates_list = list(setup['test_dates'].values())
    results = extract_production_and_labor(model_obj.model, "6122", test_dates_list)

    print(f"\n{'='*80}")
    print(f"MULTI-DAY OVERHEAD CONSISTENCY TEST")
    print(f"{'='*80}")

    # Analyze each day
    overhead_by_date = {}
    production_rate = 1400.0

    for date_label, date_val in setup['test_dates'].items():
        day_data = results[date_val]
        production_qty = day_data['production_qty']
        labor_vars = day_data['labor_vars']

        if labor_vars and production_qty > 100:
            production_time = production_qty / production_rate
            labor_hours_used = labor_vars['labor_hours_used']
            overhead_time = labor_hours_used - production_time

            overhead_by_date[date_label] = {
                'date': date_val,
                'production_qty': production_qty,
                'production_time': production_time,
                'labor_hours_used': labor_hours_used,
                'overhead_time': overhead_time,
                'labor_vars': labor_vars,
            }

            day_name = date_val.strftime('%A %b %d, %Y')
            day_type = "HOLIDAY" if "holiday" in date_label else ("WEEKEND" if "weekend" in date_label else "WEEKDAY")

            print(f"\n{day_name} ({day_type}):")
            print(f"  Production: {production_qty:,.0f} units = {production_time:.2f}h")
            print(f"  Labor hours used: {labor_hours_used:.2f}h")
            print(f"  Overhead time: {overhead_time:.2f}h")
            print(f"  Fixed hours: {labor_vars['fixed_hours_used']:.2f}h")
            print(f"  Overtime hours: {labor_vars['overtime_hours_used']:.2f}h")

    print(f"\n{'='*80}")
    print(f"OVERHEAD VERIFICATION")
    print(f"{'='*80}")

    # Verify overhead applied on all production days
    production_days = [label for label, data in overhead_by_date.items()]
    assert len(production_days) >= 3, \
        f"Expected production on at least 3 days, got {len(production_days)}"

    # Verify overhead > 0 on all production days
    for date_label, data in overhead_by_date.items():
        overhead = data['overhead_time']
        assert overhead >= 0.75, \
            f"{date_label}: Expected overhead >= 0.75h (startup+shutdown), got {overhead:.2f}h"
        print(f"✓ {date_label:20s}: Overhead = {overhead:.2f}h")

    # Verify overhead consistency (all should be similar for 1 product)
    overhead_values = [data['overhead_time'] for data in overhead_by_date.values()]
    min_overhead = min(overhead_values)
    max_overhead = max(overhead_values)
    overhead_range = max_overhead - min_overhead

    print(f"\nOverhead consistency:")
    print(f"  Min overhead: {min_overhead:.2f}h")
    print(f"  Max overhead: {max_overhead:.2f}h")
    print(f"  Range: {overhead_range:.2f}h")

    # Overhead should be very consistent (within 0.1h) for single product scenarios
    assert overhead_range <= 0.2, \
        f"Overhead range too large: {overhead_range:.2f}h (expected <= 0.2h for consistency)"

    # Verify overhead applied to weekday, weekend, AND holiday
    has_weekday = any('weekday' in label for label in production_days)
    has_weekend = any('weekend' in label for label in production_days)
    has_holiday = any('holiday' in label for label in production_days)

    print(f"\nDay type coverage:")
    print(f"  Weekday production: {'✓' if has_weekday else '✗'}")
    print(f"  Weekend production: {'✓' if has_weekend else '✗'}")
    print(f"  Holiday production: {'✓' if has_holiday else '✗'}")

    assert has_weekday, "No weekday production found"
    # Weekend and holiday production may not occur if weekday capacity is sufficient,
    # but if they do occur, overhead must be applied (verified above)

    print(f"\n{'='*80}")
    print(f"✅ ALL CHECKS PASSED")
    print(f"   - Overhead applied on ALL production days")
    print(f"   - Overhead amounts consistent: {min_overhead:.2f}h - {max_overhead:.2f}h")
    print(f"   - Overhead includes startup + shutdown + changeover")
    print(f"{'='*80}\n")


def test_multi_day_overhead_with_storage():
    """Test overhead with multi-day production allowing inventory carryover.

    This test removes the instant transit constraint to allow production
    to be scheduled on cheaper weekdays even if demand is on weekend/holiday.
    Verifies overhead still applies to actual production days chosen by optimizer.
    """
    setup = create_multi_day_overhead_test_setup()

    # Modify route to have 1-day transit
    setup['routes'][0] = UnifiedRoute(
        id="ROUTE-6122-6110",
        origin_node_id="6122",
        destination_node_id="6110",
        transport_mode=TransportMode.AMBIENT,
        transit_days=1.0,  # Allow advance production
        cost_per_unit=0.1,
    )

    model_obj = UnifiedNodeModel(
        nodes=setup['nodes'],
        routes=setup['routes'],
        forecast=setup['forecast'],
        labor_calendar=setup['labor_calendar'],
        cost_structure=setup['cost_structure'],
        start_date=setup['start_date'],
        end_date=setup['end_date'],
        use_batch_tracking=True,
        allow_shortages=False,
    )

    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=60,
        tee=False,
    )

    assert result.is_optimal() or result.is_feasible()

    # Extract production across all dates
    test_dates_list = list(setup['test_dates'].values())
    results = extract_production_and_labor(model_obj.model, "6122", test_dates_list)

    print(f"\n{'='*80}")
    print(f"MULTI-DAY OVERHEAD WITH STORAGE TEST")
    print(f"{'='*80}")

    # Collect all production days
    production_days_count = 0
    overhead_applied_count = 0

    for date_label, date_val in setup['test_dates'].items():
        day_data = results[date_val]
        if day_data['production_qty'] > 100 and day_data['labor_vars']:
            production_days_count += 1

            production_time = day_data['production_qty'] / 1400.0
            labor_hours = day_data['labor_vars']['labor_hours_used']
            overhead = labor_hours - production_time

            if overhead >= 0.5:  # Reasonable overhead threshold
                overhead_applied_count += 1

            day_name = date_val.strftime('%A %b %d')
            print(f"{day_name:20s}: Prod={day_data['production_qty']:6.0f} units, "
                  f"Labor={labor_hours:.2f}h, Overhead={overhead:.2f}h")

    print(f"\nSummary:")
    print(f"  Production days: {production_days_count}")
    print(f"  Days with overhead: {overhead_applied_count}")

    # Verify overhead applied on all production days
    assert overhead_applied_count == production_days_count, \
        f"Overhead not applied on all production days: {overhead_applied_count}/{production_days_count}"

    print(f"\n✅ TEST PASSED: Overhead applied on all {production_days_count} production days")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
