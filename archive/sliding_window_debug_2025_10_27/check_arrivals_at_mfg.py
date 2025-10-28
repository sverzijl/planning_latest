"""Check if manufacturing is receiving arrivals (shouldn't happen!)."""
from datetime import date, timedelta
from pyomo.core.base import value
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

result = model_wrapper.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
solved_model = model_wrapper.model

print("=" * 80)
print("CHECK ARRIVALS AT MANUFACTURING")
print("=" * 80)

# Check routes TO manufacturing (shouldn't exist!)
routes_to_mfg = [r for r in unified_routes if r.destination_node_id == '6122']
print(f"\nRoutes TO manufacturing (6122): {len(routes_to_mfg)}")
for route in routes_to_mfg:
    print(f"  {route.origin_node_id} → {route.destination_node_id}")

# Check shipments arriving at manufacturing
arrivals_at_mfg = 0
shipment_count = 0
for idx in solved_model.shipment:
    origin, dest, prod, delivery_date, state = idx
    if dest == '6122':  # Arriving AT manufacturing
        try:
            val = value(solved_model.shipment[idx])
            if val and val > 0.1:
                arrivals_at_mfg += val
                shipment_count += 1
                if shipment_count <= 10:
                    print(f"  ARRIVAL: {origin} → {dest}, {prod[:25]}, {delivery_date}: {val:.1f} units")
        except:
            pass

print(f"\nTotal arrivals at manufacturing: {arrivals_at_mfg:,.0f} units")

if arrivals_at_mfg > 0:
    print(f"\n⚠️  WARNING: Manufacturing is receiving shipments!")
    print(f"   This is unusual - manufacturing is a SOURCE, not a sink.")
    print(f"   Are there circular routes in the network?")

# Also check departures
departures_from_mfg = 0
for idx in solved_model.shipment:
    origin, dest, prod, delivery_date, state = idx
    if origin == '6122':  # Departing FROM manufacturing
        try:
            val = value(solved_model.shipment[idx])
            if val and val > 0.1:
                departures_from_mfg += val
        except:
            pass

print(f"\nDepartures from manufacturing: {departures_from_mfg:,.0f} units")

# Net flow
net_flow = arrivals_at_mfg - departures_from_mfg
print(f"Net flow (arrivals - departures): {net_flow:,.0f} units")

if arrivals_at_mfg > 0:
    print(f"\n🔍 If manufacturing has arrivals, check for:")
    print(f"   1. Circular routes (A → B → A)")
    print(f"   2. Incorrect route definitions")
    print(f"   3. Network topology bugs")
