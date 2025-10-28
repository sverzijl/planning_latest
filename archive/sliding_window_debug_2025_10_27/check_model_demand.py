"""Check what demand the model actually sees."""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=1)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model_wrapper = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

print("=" * 80)
print("CHECK MODEL DEMAND")
print("=" * 80)

print(f"\nPlanning horizon: {start} to {end}")
print(f"Forecast entries in model.forecast: {len(model_wrapper.forecast.entries)}")
print(f"Demand entries in model.demand: {len(model_wrapper.demand)}")

# Group by date
demand_by_date = {}
for (node, prod, date_val), qty in model_wrapper.demand.items():
    demand_by_date[date_val] = demand_by_date.get(date_val, 0) + qty

print(f"\nDemand by date IN MODEL:")
for date_key in sorted(demand_by_date.keys()):
    print(f"  {date_key}: {demand_by_date[date_key]:,.0f} units")

print(f"\nTotal demand IN MODEL: {sum(model_wrapper.demand.values()):,.0f} units")

# Check if model.demand is correct
forecast_demand_in_horizon = sum(
    e.quantity for e in forecast.entries
    if start <= e.forecast_date <= end
)
print(f"Total demand from forecast (in horizon): {forecast_demand_in_horizon:,.0f} units")

if abs(sum(model_wrapper.demand.values()) - forecast_demand_in_horizon) > 1:
    print(f"\n⚠️  MISMATCH! Model demand != forecast demand")
else:
    print(f"\n✅ Model demand matches forecast")

# Check minimum shelf life filtering
print(f"\n" + "=" * 80)
print(f"SHELF LIFE FILTERING CHECK")
print(f"=" * 80)

# Check if any routes are filtered out due to shelf life
for route in unified_routes:
    if route.destination_node_id in model_wrapper.demand_nodes:
        # Check transit time
        effective_age = route.transit_days + 7  # Minimum shelf life days
        if effective_age > 17:  # Ambient shelf life
            print(f"  Route {route.origin_node_id} → {route.destination_node_id}:")
            print(f"    Transit: {route.transit_days} days")
            print(f"    Effective age at delivery: {effective_age} days")
            print(f"    ⚠️  EXCEEDS 17-day shelf life!")
