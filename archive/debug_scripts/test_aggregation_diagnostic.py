"""Diagnostic: Verify temporal aggregation reduces production dates."""

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.models.forecast import Forecast
from src.models.truck_schedule import TruckScheduleCollection
from src.models.time_period import BucketGranularity, VariableGranularityConfig
from src.models.forecast_aggregator import aggregate_forecast_to_buckets
from src.models.time_period import create_variable_granularity_buckets
from src.optimization import IntegratedProductionDistributionModel

print("=" * 70)
print("TEMPORAL AGGREGATION DIAGNOSTIC")
print("=" * 70)

# Load data
print("\nLoading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Filter for 3 weeks (21 days)
start_date = date(2025, 6, 2)
end_date = start_date + timedelta(days=20)  # 21 days

filtered_entries = [
    e for e in full_forecast.entries
    if start_date <= e.forecast_date <= end_date
]
forecast_daily = Forecast(name="3Weeks_Daily", entries=filtered_entries, creation_date=date.today())

print(f"\n3-Week Problem (Daily Forecast):")
print(f"  Dates: {start_date} to {end_date} (21 days)")
print(f"  Forecast entries: {len(forecast_daily.entries)}")
unique_dates = sorted(set(e.forecast_date for e in forecast_daily.entries))
print(f"  Unique forecast dates: {len(unique_dates)}")

# Test 1: Build model with daily forecast
print("\n" + "=" * 70)
print("TEST 1: Daily Forecast (No Aggregation)")
print("=" * 70)

model_daily = IntegratedProductionDistributionModel(
    forecast=forecast_daily,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    validate_feasibility=False,  # Skip validation for speed
)

print(f"\nModel production_dates: {len(model_daily.production_dates)}")
print(f"  Production dates: {sorted(model_daily.production_dates)}")

# Test 2: Build model with aggregated forecast
print("\n" + "=" * 70)
print("TEST 2: Aggregated Forecast (3-day buckets)")
print("=" * 70)

granularity_config = VariableGranularityConfig(
    near_term_days=7,
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.THREE_DAY,
)

# Create buckets
buckets = create_variable_granularity_buckets(
    start_date=start_date,
    end_date=end_date,
    config=granularity_config
)

print(f"\nTime buckets created: {len(buckets)}")
for i, bucket in enumerate(buckets, 1):
    print(f"  {i}. {bucket.start_date} to {bucket.end_date} ({bucket.granularity.value}, rep: {bucket.representative_date})")

# Aggregate forecast
forecast_aggregated = aggregate_forecast_to_buckets(
    forecast=forecast_daily,
    buckets=buckets
)

print(f"\nAggregated forecast:")
print(f"  Forecast entries: {len(forecast_aggregated.entries)}")
unique_agg_dates = sorted(set(e.forecast_date for e in forecast_aggregated.entries))
print(f"  Unique forecast dates: {len(unique_agg_dates)}")
print(f"  Dates: {unique_agg_dates}")

# Build model with aggregated forecast
model_aggregated = IntegratedProductionDistributionModel(
    forecast=forecast_aggregated,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    validate_feasibility=False,  # Skip validation for speed
)

print(f"\nModel production_dates: {len(model_aggregated.production_dates)}")
print(f"  Production dates: {sorted(model_aggregated.production_dates)}")

# Comparison
print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)

daily_count = len(model_daily.production_dates)
aggregated_count = len(model_aggregated.production_dates)
reduction_pct = (1 - aggregated_count / daily_count) * 100 if daily_count > 0 else 0

print(f"\nProduction dates:")
print(f"  Daily forecast: {daily_count} dates")
print(f"  Aggregated forecast: {aggregated_count} dates")
print(f"  Reduction: {reduction_pct:.1f}%")

# Estimate variable reduction
# Rough estimate: binary vars ≈ dates × products × routes
products = len(model_daily.products)
routes = len(model_daily.enumerated_routes)
print(f"\nRough variable count estimate:")
print(f"  Products: {products}")
print(f"  Routes: {routes}")
print(f"  Daily: ~{daily_count * products * routes} route vars + truck vars")
print(f"  Aggregated: ~{aggregated_count * products * routes} route vars + truck vars")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)

if aggregated_count < daily_count:
    print(f"\n✅ Temporal aggregation working!")
    print(f"   Reduced production dates from {daily_count} to {aggregated_count}")
else:
    print(f"\n❌ Temporal aggregation NOT working!")
    print(f"   Production dates should be reduced but stayed at {aggregated_count}")
    print(f"\nPossible issues:")
    print(f"  - Model extracting all dates instead of forecast dates")
    print(f"  - Aggregation not properly reducing forecast entries")
print("\n" + "=" * 70)
