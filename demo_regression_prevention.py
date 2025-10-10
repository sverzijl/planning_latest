#!/usr/bin/env python
"""
Demonstration of Labor Calendar Regression Prevention Tests

This script demonstrates how the test suite prevents the labor_days → days
attribute error that was previously present in ui/pages/2_Planning.py.
"""

from datetime import date, timedelta
from src.models.labor_calendar import LaborCalendar, LaborDay


def demonstrate_bug():
    """Demonstrate the bug that the tests prevent."""
    print("=" * 70)
    print("DEMONSTRATING THE BUG THAT TESTS PREVENT")
    print("=" * 70)
    print()

    # Create a labor calendar
    labor_days = [
        LaborDay(
            date=date(2025, 1, 1),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0
        ),
        LaborDay(
            date=date(2025, 1, 2),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0
        ),
        LaborDay(
            date=date(2025, 1, 3),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0
        ),
    ]

    calendar = LaborCalendar(name="Test Calendar", days=labor_days)

    print("✅ CORRECT USAGE (what the tests validate):")
    print("-" * 70)
    print(f"calendar.days exists: {hasattr(calendar, 'days')}")
    print(f"calendar.days is list: {isinstance(calendar.days, list)}")
    print(f"Number of days: {len(calendar.days)}")

    # Correct pattern from fixed code (Planning.py:457-458)
    if calendar.days:
        max_date = max(day.date for day in calendar.days)
        print(f"Max date (CORRECT): {max_date}")

    print()
    print("❌ INCORRECT USAGE (the bug that was fixed):")
    print("-" * 70)
    print(f"calendar.labor_days exists: {hasattr(calendar, 'labor_days')}")

    # Try the incorrect usage (this will raise AttributeError)
    try:
        _ = max(day.date for day in calendar.labor_days)
        print("ERROR: This should have raised AttributeError!")
    except AttributeError as e:
        print(f"✅ AttributeError caught (as expected): {e}")

    print()


def demonstrate_defensive_pattern():
    """Demonstrate the defensive coding pattern."""
    print("=" * 70)
    print("DEMONSTRATING DEFENSIVE CODING PATTERN")
    print("=" * 70)
    print()

    # Simulate data dictionary as used in Planning UI
    test_cases = [
        {
            'name': 'Normal case (valid calendar with days)',
            'data': {
                'labor_calendar': LaborCalendar(
                    name="Valid",
                    days=[
                        LaborDay(date=date(2025, 1, 1), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
                        LaborDay(date=date(2025, 1, 15), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0),
                    ]
                )
            }
        },
        {
            'name': 'Empty calendar (no days)',
            'data': {
                'labor_calendar': LaborCalendar(name="Empty", days=[])
            }
        },
        {
            'name': 'None calendar',
            'data': {
                'labor_calendar': None
            }
        },
        {
            'name': 'Missing key',
            'data': {}
        },
    ]

    for test_case in test_cases:
        print(f"Test: {test_case['name']}")
        print("-" * 70)

        data = test_case['data']

        # Defensive pattern from fixed Planning.py (lines 457-465)
        if data.get('labor_calendar') and data['labor_calendar'].days:
            labor_end = max(day.date for day in data['labor_calendar'].days)
            print(f"  ✅ Labor calendar end date: {labor_end}")
        else:
            print(f"  ⚠️  Labor calendar data not available or empty")

        print()


def demonstrate_planning_horizon_check():
    """Demonstrate planning horizon validation."""
    print("=" * 70)
    print("DEMONSTRATING PLANNING HORIZON VALIDATION")
    print("=" * 70)
    print()

    # Create labor calendar covering 50 days
    start_date = date(2025, 1, 1)
    labor_days = [
        LaborDay(
            date=start_date + timedelta(days=i),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0
        )
        for i in range(50)
    ]

    calendar = LaborCalendar(name="50-Day Calendar", days=labor_days)
    labor_end = max(day.date for day in calendar.days)

    print(f"Labor calendar coverage: {start_date} to {labor_end} ({len(labor_days)} days)")
    print()

    # Test different planning horizons
    test_horizons = [
        ("4 weeks (within coverage)", 4, False),
        ("7 weeks (exact coverage)", 7, False),
        ("10 weeks (exceeds coverage)", 10, True),
    ]

    for name, weeks, should_warn in test_horizons:
        forecast_start = date(2025, 1, 1)
        planning_end = forecast_start + timedelta(days=weeks * 7)

        print(f"Planning horizon: {name}")
        print(f"  Forecast start: {forecast_start}")
        print(f"  Planning end: {planning_end}")
        print(f"  Labor end: {labor_end}")

        if planning_end > labor_end:
            days_over = (planning_end - labor_end).days
            print(f"  ⚠️  WARNING: Planning extends {days_over} days beyond labor calendar")
            assert should_warn, f"Expected warning for {name}"
        else:
            days_buffer = (labor_end - planning_end).days
            print(f"  ✅ OK: {days_buffer} days of buffer remaining")
            assert not should_warn, f"Did not expect warning for {name}"

        print()


def main():
    """Run all demonstrations."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " LABOR CALENDAR REGRESSION PREVENTION DEMONSTRATION ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    demonstrate_bug()
    print("\n")

    demonstrate_defensive_pattern()
    print("\n")

    demonstrate_planning_horizon_check()
    print("\n")

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("✅ All demonstrations completed successfully!")
    print()
    print("The test suite validates:")
    print("  1. Correct attribute usage (calendar.days, not calendar.labor_days)")
    print("  2. Defensive coding patterns (None checks, empty list handling)")
    print("  3. Planning horizon validation logic")
    print()
    print("To run the actual test suite:")
    print("  python -m pytest tests/test_planning_ui_labor_calendar.py -v")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
