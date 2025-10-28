"""Check if shipments have non-zero values."""
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
end = start + timedelta(days=1)  # 2 days
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
pyomo_model = model.model

print("=" * 80)
print("SHIPMENT VALUES")
print("=" * 80)

# Check shipments
all_shipments = 0
shipment_count = 0
print(f"\nNon-zero shipments:")
for idx in pyomo_model.shipment:
    try:
        val = value(pyomo_model.shipment[idx])
        if val and val > 0.1:
            shipment_count += 1
            all_shipments += val
            if shipment_count <= 10:
                origin, dest, prod, delivery_date, state = idx
                print(f"  {origin} → {dest}, {prod[:25]}, deliver={delivery_date}, {state}: {val:.1f} units")
    except:
        pass

print(f"\nTotal shipments: {all_shipments:,.0f} units ({shipment_count} non-zero)")

# Check production
all_prod = sum(value(pyomo_model.production[idx]) for idx in pyomo_model.production)
print(f"Total production: {all_prod:,.0f} units")

# Check if shipments match production
print(f"\nShipments = Production? {abs(all_shipments - all_prod) < 1}")
