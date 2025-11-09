#!/usr/bin/env python3
"""Check demand distribution by day."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, _, _, _, _, _ = parser.parse_all()

# 7-day
start = date(2025, 10, 17)
end = start + timedelta(days=6)

print("="*80)
print("DEMAND BY DAY (7-day horizon)")
print("="*80)

by_day = {}
for entry in forecast.entries:
    if start <= entry.forecast_date <= end:
        day = entry.forecast_date
        if day not in by_day:
            by_day[day] = 0
        by_day[day] += entry.quantity

print(f"\nDaily demand:")
total = 0
for day in sorted(by_day.keys()):
    qty = by_day[day]
    total += qty
    print(f"  {day}: {qty:,.0f} units")

print(f"\nTotal: {total:,.0f} units")

print(f"\nExpected behavior:")
print(f"  Day 1: Take as shortage (can't produce+ship same day)")
print(f"  Days 2-7: Should produce on days 1-6 to meet demand")
print(f"  Expected production: ~{total - by_day[start]:,.0f} units (total - day1)")

print("="*80)
