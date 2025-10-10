"""Check if demand is being filtered by planning horizon."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from datetime import datetime, timedelta

print("Loading forecast data...")
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
forecast = forecast_parser.parse_forecast()

# Get planning horizon from forecast
start_date = min(e.forecast_date for e in forecast.entries)
end_date = max(e.forecast_date for e in forecast.entries)
total_days = (end_date - start_date).days + 1

print(f"\nForecast date range:")
print(f"  Start: {start_date}")
print(f"  End: {end_date}")
print(f"  Total days: {total_days}")

# Model extends planning horizon by max transit time (10 days)
MAX_TRANSIT_DAYS = 10
model_end_date = end_date + timedelta(days=MAX_TRANSIT_DAYS)

print(f"\nModel planning horizon:")
print(f"  Start: {start_date}")
print(f"  End (extended): {model_end_date}")
print(f"  Total days: {(model_end_date - start_date).days + 1}")

# Check demand in last week
last_week_start = end_date - timedelta(days=6)
last_week_demand = sum(
    e.quantity for e in forecast.entries
    if e.forecast_date >= last_week_start
)

print(f"\nDemand in last week ({last_week_start} to {end_date}):")
print(f"  {last_week_demand:,.0f} units")

# Check demand by date for last 2 weeks
from collections import defaultdict
by_date = defaultdict(float)
for entry in forecast.entries:
    by_date[entry.forecast_date] += entry.quantity

last_14_days = sorted([d for d in by_date.keys() if d >= end_date - timedelta(days=13)])

print(f"\nDemand by date (last 14 days):")
total_last_14 = 0
for date in last_14_days:
    demand = by_date[date]
    total_last_14 += demand
    print(f"  {date}: {demand:>10,.0f} units")

print(f"\nTotal in last 14 days: {total_last_14:,.0f} units")

# Production would need to happen before these delivery dates
# With max 3.5 days transit, production for Dec 22 would need to happen by Dec 18.5
# So demand on Dec 19-22 might be unservable if production can only happen up to Dec 22

print(f"\n{'='*60}")
print("HYPOTHESIS:")
print(f"{'='*60}")
print("If production can only happen up to the end date (Dec 22),")
print("then demand on the last few days can't be met because")
print("production needs to happen BEFORE delivery, but there's")
print("no time left in the planning horizon.")
print(f"\nThis could explain the 154,880 unit gap (11 trucks worth).")
