#!/usr/bin/env python
"""Quick check of labor calendar coverage before running tests."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.parsers.excel_parser import ExcelParser
    from datetime import date

    # Load labor calendar
    network_file = Path("data/examples/Network_Config.xlsx")
    print(f"Loading labor calendar from: {network_file}")
    print(f"File exists: {network_file.exists()}")
    print()

    if not network_file.exists():
        print("ERROR: Network_Config.xlsx not found!")
        sys.exit(1)

    parser = ExcelParser(network_file)
    labor_calendar = parser.parse_labor_calendar()

    # Get date range
    dates = sorted([d.date for d in labor_calendar.days])
    print(f"Labor Calendar Coverage:")
    print(f"  Start date:     {dates[0]}")
    print(f"  End date:       {dates[-1]}")
    print(f"  Total days:     {len(dates)}")
    print(f"  Weekdays:       {sum(1 for d in dates if d.weekday() < 5)}")
    print(f"  Weekends:       {sum(1 for d in dates if d.weekday() >= 5)}")
    print()

    # Expected range from user request
    expected_start = date(2025, 5, 26)
    expected_end = date(2026, 12, 31)
    print(f"Expected Coverage (from user request):")
    print(f"  Expected start: {expected_start}")
    print(f"  Expected end:   {expected_end}")
    print()

    # Check if it matches
    if dates[0] == expected_start and dates[-1] == expected_end:
        print("✓ Labor calendar matches expected range!")
    else:
        print("⚠ Labor calendar does NOT match expected range")
        print(f"  Start mismatch: {dates[0]} vs {expected_start}")
        print(f"  End mismatch:   {dates[-1]} vs {expected_end}")

    print()

    # Load forecast to check coverage
    forecast_file = Path("data/examples/Gfree Forecast.xlsm")
    if forecast_file.exists():
        print(f"Loading forecast from: {forecast_file}")
        forecast_parser = ExcelParser(forecast_file)
        forecast = forecast_parser.parse_forecast()

        forecast_dates = sorted(set([e.forecast_date for e in forecast.entries]))
        print(f"Forecast Coverage:")
        print(f"  Start date:     {forecast_dates[0]}")
        print(f"  End date:       {forecast_dates[-1]}")
        print(f"  Total days:     {len(forecast_dates)}")
        print()

        # Check if all forecast weekdays are in labor calendar
        labor_date_set = set(dates)
        missing_weekdays = [d for d in forecast_dates if d not in labor_date_set and d.weekday() < 5]

        if missing_weekdays:
            print(f"⚠ Missing {len(missing_weekdays)} forecast weekdays in labor calendar:")
            print(f"  First 10: {missing_weekdays[:10]}")
            print()
            print("This means the tests will likely FAIL!")
        else:
            print("✓ All forecast weekdays covered by labor calendar")
            print()
            print("This means the tests should PASS!")

    print()
    print("=" * 80)
    print("Ready to run integration tests")
    print("=" * 80)

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
