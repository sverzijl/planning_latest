"""Inspect the actual constraint expression after fix."""
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

# Just build, don't solve yet
pyomo_model = model_wrapper.build_model()

print("=" * 80)
print("INSPECT CONSTRAINT EXPRESSION (NOT YET SOLVED)")
print("=" * 80)

mfg_id = '6122'
first_product = product_ids[0]
first_date = start

if (mfg_id, first_product, first_date) in pyomo_model.ambient_balance_con:
    con = pyomo_model.ambient_balance_con[mfg_id, first_product, first_date]

    print(f"\nManufacturing balance for {first_product}, {first_date}:")
    print(f"\n{con.expr}")

    # Check if shipments appear in the expression
    expr_str = str(con.expr)

    print(f"\nSearching for shipment terms in expression:")
    if 'shipment' in expr_str:
        print(f"  ✅ Found 'shipment' in expression")

        # Count how many shipment terms
        shipment_count = expr_str.count('shipment[')
        print(f"  Number of shipment terms: {shipment_count}")

        # Extract and show them
        import re
        shipments = re.findall(r"shipment\[[^\]]+\]", expr_str)
        for i, s in enumerate(shipments[:5], 1):
            print(f"    {i}. {s}")
    else:
        print(f"  ❌ NO 'shipment' terms in expression!")
        print(f"     Departures are not being included in the balance!")

# Also check the routes from manufacturing
routes_from_mfg = [r for r in unified_routes if r.origin_node_id == '6122']
print(f"\nRoutes from manufacturing: {len(routes_from_mfg)}")
for route in routes_from_mfg:
    # Calculate delivery date for departure on first_date
    delivery_date = first_date + timedelta(days=route.transit_days)
    print(f"  {route.origin_node_id} → {route.destination_node_id}, transit={route.transit_days}d")
    print(f"    Depart {first_date} → Deliver {delivery_date}")

    # Check if shipment variable exists
    shipment_key = (route.origin_node_id, route.destination_node_id, first_product, delivery_date, 'ambient')
    if shipment_key in pyomo_model.shipment:
        print(f"    ✅ Shipment variable EXISTS")
    else:
        print(f"    ❌ Shipment variable MISSING!")
