"""Quick test: 1 week with and without aggregation."""
from datetime import date, timedelta
from src.parsers import ExcelParser
from src.models.forecast import Forecast
from src.models.truck_schedule import TruckScheduleCollection
from src.models.time_period import BucketGranularity, create_uniform_buckets
from src.models.forecast_aggregator import aggregate_forecast_to_buckets
from src.optimization import IntegratedProductionDistributionModel

network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# 1 week only
start_date = date(2025, 6, 2)
end_date = start_date + timedelta(days=6)  # 7 days
filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
forecast_daily = Forecast(name="1Week", entries=filtered_entries, creation_date=date.today())

print("1-Week Test")
print(f"Dates: {start_date} to {end_date}")
print(f"Demand: {sum(e.quantity for e in forecast_daily.entries):,.0f}")

# Daily
print("\n1. Daily forecast...")
model_daily = IntegratedProductionDistributionModel(
    forecast=forecast_daily, labor_calendar=labor_calendar, manufacturing_site=manufacturing_site,
    cost_structure=cost_structure, locations=locations, routes=routes,
    truck_schedules=truck_schedules, allow_shortages=True, enforce_shelf_life=True
)
result_daily = model_daily.solve(solver_name='cbc', time_limit_seconds=60)
print(f"  Success: {result_daily.success}")
print(f"  Termination: {result_daily.termination_condition}")

# Aggregated (3-day buckets)
print("\n2. Aggregated forecast (3-day buckets)...")
buckets = create_uniform_buckets(start_date, end_date, BucketGranularity.THREE_DAY)
print(f"  Buckets: {len(buckets)}")
for b in buckets:
    print(f"    {b.start_date} to {b.end_date} (rep: {b.representative_date})")

forecast_agg = aggregate_forecast_to_buckets(forecast_daily, buckets)
print(f"  Aggregated entries: {len(forecast_agg.entries)} (from {len(forecast_daily.entries)})")

model_agg = IntegratedProductionDistributionModel(
    forecast=forecast_agg, labor_calendar=labor_calendar, manufacturing_site=manufacturing_site,
    cost_structure=cost_structure, locations=locations, routes=routes,
    truck_schedules=truck_schedules, allow_shortages=True, enforce_shelf_life=True
)
result_agg = model_agg.solve(solver_name='cbc', time_limit_seconds=60)
print(f"  Success: {result_agg.success}")
print(f"  Termination: {result_agg.termination_condition}")
if result_agg.infeasibility_message:
    print(f"  Message: {result_agg.infeasibility_message}")

print(f"\n" + "="*50)
print(f"Conclusion:")
print(f"  Daily: {result_daily.success}")
print(f"  Aggregated: {result_agg.success}")
if result_daily.success and not result_agg.success:
    print("  ❌ Aggregation causes infeasibility!")
elif result_agg.success:
    print("  ✅ Both work!")
    print(f"  Daily production dates: {len(model_daily.production_dates)}")
    print(f"  Aggregated production dates: {len(model_agg.production_dates)}")
