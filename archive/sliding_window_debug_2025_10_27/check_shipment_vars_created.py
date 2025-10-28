"""Check what shipment variables are actually created."""
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

pyomo_model = model_wrapper.build_model()

print("=" * 80)
print("CHECK SHIPMENT VARIABLE CREATION")
print("=" * 80)

print(f"\nPlanning horizon: {start} to {end}")

# Get unique delivery dates in shipment variables
delivery_dates = set()
for idx in pyomo_model.shipment:
    origin, dest, prod, delivery_date, state = idx
    delivery_dates.add(delivery_date)

print(f"\nDelivery dates in shipment variables:")
for d in sorted(delivery_dates):
    print(f"  {d}")

# Check specific shipment
first_product = product_ids[0]
test_shipment = ('6122', '6104', first_product, start, 'ambient')  # Deliver on START date
if test_shipment in pyomo_model.shipment:
    print(f"\n✅ shipment['6122','6104',{first_product[:20]},{start},ambient] EXISTS")
    print(f"   This shipment would need to depart on {start - timedelta(days=1)} (BEFORE planning!)")
else:
    print(f"\n❌ shipment['6122','6104',{first_product[:20]},{start},ambient] MISSING")
    print(f"   Arrivals on first day cannot happen (no shipment variables)!")

# Check the extended date calculation
max_transit = max(r.transit_days for r in unified_routes)
extended_end = end + timedelta(days=int(max_transit))

print(f"\n" + "=" * 80)
print(f"SHIPMENT DATE RANGE:")
print(f"=" * 80)
print(f"  Planning start: {start}")
print(f"  Planning end: {end}")
print(f"  Max transit days: {max_transit}")
print(f"  Extended end (for departures at end): {extended_end}")
print(f"  Min delivery date in vars: {min(delivery_dates)}")
print(f"  Max delivery date in vars: {max(delivery_dates)}")

print(f"\n  Issue: We extended END but not START!")
print(f"  Need shipments for delivery BEFORE start (for arrivals on day 1)")
