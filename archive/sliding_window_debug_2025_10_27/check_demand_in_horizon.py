"""Check if there's demand in the planning horizon."""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=1)  # 2-day horizon

print(f"Planning horizon: {start} to {end}")
print(f"\nDemand by date:")

demand_by_date = {}
for entry in forecast.entries:
    if start <= entry.forecast_date <= end:
        demand_by_date[entry.forecast_date] = demand_by_date.get(entry.forecast_date, 0) + entry.quantity

for date_key in sorted(demand_by_date.keys()):
    print(f"  {date_key}: {demand_by_date[date_key]:,.0f} units")

print(f"\nTotal demand in horizon: {sum(demand_by_date.values()):,.0f} units")

# Check if shortage penalty is reasonable
print(f"\nCost parameters:")
print(f"  Shortage penalty: ${cost_params.shortage_penalty_per_unit:.2f} /unit")
print(f"  Production cost: ${cost_params.production_cost_per_unit:.2f} /unit")

if cost_params.shortage_penalty_per_unit < cost_params.production_cost_per_unit:
    print(f"\n⚠️  WARNING: Shortage penalty < production cost!")
    print(f"   Model will prefer shortage over production!")
