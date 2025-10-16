#!/usr/bin/env python
"""Quick check of data files and labor calendar coverage."""

from pathlib import Path
from datetime import datetime

# Check data directory
data_dir = Path("data/examples")
print("Files in data/examples/:")
for f in sorted(data_dir.glob("*")):
    print(f"  {f.name}")
print()

# Try to load labor calendar
try:
    from src.parsers.excel_parser import ExcelParser

    network_file = data_dir / "Network_Config.xlsx"
    if network_file.exists():
        print(f"Loading labor calendar from {network_file.name}...")
        parser = ExcelParser(network_file)
        labor_calendar = parser.parse_labor_calendar()

        # Get date range
        dates = sorted([d.date for d in labor_calendar.days])
        print(f"  Start date: {dates[0]}")
        print(f"  End date:   {dates[-1]}")
        print(f"  Total days: {len(dates)}")
        print(f"  Weekdays:   {sum(1 for d in dates if d.weekday() < 5)}")
        print(f"  Weekends:   {sum(1 for d in dates if d.weekday() >= 5)}")
        print()

        # Check coverage of forecast period
        forecast_file = data_dir / "Gfree Forecast.xlsm"
        if forecast_file.exists():
            forecast_parser = ExcelParser(forecast_file)
            forecast = forecast_parser.parse_forecast()

            forecast_dates = sorted(set([e.forecast_date for e in forecast.entries]))
            print(f"Forecast coverage:")
            print(f"  Start date: {forecast_dates[0]}")
            print(f"  End date:   {forecast_dates[-1]}")
            print(f"  Total days: {len(forecast_dates)}")
            print()

            # Check if all forecast weekdays are covered
            missing_weekdays = [d for d in forecast_dates if d not in dates and d.weekday() < 5]
            if missing_weekdays:
                print(f"⚠ Missing {len(missing_weekdays)} forecast weekdays in labor calendar:")
                print(f"  First few: {missing_weekdays[:10]}")
            else:
                print("✓ All forecast weekdays covered by labor calendar")

    else:
        print(f"Network config file not found: {network_file}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
