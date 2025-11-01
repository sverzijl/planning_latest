"""Check if demand is being filtered correctly to planning horizon.

Hypothesis: Demand outside planning horizon might be included,
causing infeasibility when there's no way to meet it.
"""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Planning horizon
start_date = date(2025, 10, 17)
end_date = date(2025, 11, 13)

print(f"Planning horizon: {start_date} to {end_date}")
print(f"Total days: {(end_date - start_date).days + 1}")

# Check forecast date range
forecast_dates = set(e.forecast_date for e in forecast.entries)
min_forecast = min(forecast_dates)
max_forecast = max(forecast_dates)

print(f"\nForecast data range: {min_forecast} to {max_forecast}")

# Count demand by date relative to planning
before_planning = sum(e.quantity for e in forecast.entries if e.forecast_date < start_date)
in_planning = sum(e.quantity for e in forecast.entries if start_date <= e.forecast_date <= end_date)
after_planning = sum(e.quantity for e in forecast.entries if e.forecast_date > end_date)

print(f"\nDemand distribution:")
print(f"  Before planning ({min_forecast} to {start_date - timedelta(days=1)}): {before_planning:,.0f} units")
print(f"  In planning ({start_date} to {end_date}): {in_planning:,.0f} units")
print(f"  After planning ({end_date + timedelta(days=1)} to {max_forecast}): {after_planning:,.0f} units")

# SlidingWindowModel should only include demand in planning horizon
print(f"\nSlidingWindowModel demand filtering:")
demand_dict = {}
for entry in forecast.entries:
    if start_date <= entry.forecast_date <= end_date:
        key = (entry.location_id, entry.product_id, entry.forecast_date)
        demand_dict[key] = demand_dict.get(key, 0) + entry.quantity

print(f"  Demand entries in model: {len(demand_dict)}")
print(f"  Total demand in model: {sum(demand_dict.values()):,.0f} units")

if before_planning > 0:
    print(f"\n  WARNING: {before_planning:,.0f} units of demand BEFORE planning start")
    print(f"  This demand should be EXCLUDED from model (can't meet past demand)")
