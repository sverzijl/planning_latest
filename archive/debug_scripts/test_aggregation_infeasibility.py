"""Debug why temporal aggregation causes infeasibility."""

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.models.forecast import Forecast
from src.models.truck_schedule import TruckScheduleCollection
from src.models.time_period import BucketGranularity, VariableGranularityConfig
from src.models.forecast_aggregator import aggregate_forecast_to_buckets
from src.models.time_period import create_variable_granularity_buckets
from src.optimization import IntegratedProductionDistributionModel

print("=" * 70)
print("TEMPORAL AGGREGATION INFEASIBILITY DEBUG")
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

# Test on 2 weeks (simpler than 3 weeks)
start_date = date(2025, 6, 2)
end_date = start_date + timedelta(days=13)  # 14 days

filtered_entries = [
    e for e in full_forecast.entries
    if start_date <= e.forecast_date <= end_date
]
forecast_daily = Forecast(name="2Weeks_Daily", entries=filtered_entries, creation_date=date.today())

print(f"\n2-Week Window:")
print(f"  Dates: {start_date} to {end_date} (14 days)")
print(f"  Forecast entries: {len(forecast_daily.entries)}")
print(f"  Total demand: {sum(e.quantity for e in forecast_daily.entries):,.0f}")

# Test 1: Daily forecast (should be feasible)
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
    enforce_shelf_life=True,
)

print(f"\nBuilding and solving daily model...")
result_daily = model_daily.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01)

print(f"\nDaily Result:")
print(f"  Success: {result_daily.success}")
print(f"  Termination: {result_daily.termination_condition}")
if result_daily.infeasibility_message:
    print(f"  Message: {result_daily.infeasibility_message}")

# Test 2: Aggregated forecast
print("\n" + "=" * 70)
print("TEST 2: Aggregated Forecast (3-day buckets)")
print("=" * 70)

# Use uniform 3-day aggregation (simpler than variable)
granularity_config = VariableGranularityConfig(
    near_term_days=0,  # No daily period
    near_term_granularity=BucketGranularity.THREE_DAY,
    far_term_granularity=BucketGranularity.THREE_DAY,
)

buckets = create_variable_granularity_buckets(
    start_date=start_date,
    end_date=end_date,
    config=granularity_config
)

print(f"\nTime buckets: {len(buckets)}")
for i, bucket in enumerate(buckets, 1):
    print(f"  {i}. {bucket.start_date} to {bucket.end_date} ({bucket.granularity.value})")

forecast_aggregated = aggregate_forecast_to_buckets(
    forecast=forecast_daily,
    buckets=buckets
)

print(f"\nAggregated forecast:")
print(f"  Entries: {len(forecast_aggregated.entries)}")
print(f"  Total demand: {sum(e.quantity for e in forecast_aggregated.entries):,.0f}")

model_aggregated = IntegratedProductionDistributionModel(
    forecast=forecast_aggregated,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print(f"\nBuilding and solving aggregated model...")
result_aggregated = model_aggregated.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01)

print(f"\nAggregated Result:")
print(f"  Success: {result_aggregated.success}")
print(f"  Termination: {result_aggregated.termination_condition}")
if result_aggregated.infeasibility_message:
    print(f"  Message: {result_aggregated.infeasibility_message}")

# Compare
print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)

print(f"\nDaily:")
print(f"  Production dates: {len(model_daily.production_dates)}")
print(f"  Feasible: {result_daily.success}")

print(f"\nAggregated:")
print(f"  Production dates: {len(model_aggregated.production_dates)}")
print(f"  Feasible: {result_aggregated.success}")

if result_daily.success and not result_aggregated.success:
    print(f"\n❌ PROBLEM: Daily is feasible but aggregated is not!")
    print(f"\nPossible causes:")
    print(f"  1. Truck schedules indexed by delivery date don't align with bucket dates")
    print(f"  2. Labor calendar missing entries for bucket representative dates")
    print(f"  3. Route enumeration affected by date changes")
    print(f"  4. Demand aggregation causing misalignment")
elif result_aggregated.success:
    print(f"\n✅ Both daily and aggregated are feasible!")
    print(f"  Daily solve time: {result_daily.solve_time:.2f}s")
    print(f"  Aggregated solve time: {result_aggregated.solve_time:.2f}s")
    if result_aggregated.solve_time < result_daily.solve_time:
        speedup = result_daily.solve_time / result_aggregated.solve_time
        print(f"  Speedup: {speedup:.1f}x faster")
else:
    print(f"\n⚠️  Both are infeasible - data/configuration issue")

print("\n" + "=" * 70)
