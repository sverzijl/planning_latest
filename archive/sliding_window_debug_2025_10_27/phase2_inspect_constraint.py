"""Phase 2: Inspect state balance constraint expression to find bug."""
from datetime import date, timedelta
import pyomo.environ as pyo
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
end = start  # Just 1 day for simplicity
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model_wrapper = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Build model
model = model_wrapper.build_model()

print("=" * 80)
print("PHASE 2: INSPECT STATE BALANCE CONSTRAINT")
print("=" * 80)

# Get manufacturing node balance constraint
mfg_id = '6122'
first_date = start
first_product = product_ids[0]

if (mfg_id, first_product, first_date) in model.ambient_balance_con:
    con = model.ambient_balance_con[mfg_id, first_product, first_date]

    print(f"\nManufacturing balance constraint:")
    print(f"  Node: {mfg_id}")
    print(f"  Product: {first_product}")
    print(f"  Date: {first_date}")

    print(f"\n  Full expression:")
    expr_str = str(con.expr)
    # Pretty print
    parts = expr_str.split(" - ")
    print(f"    LHS (inventory): {parts[0]}")
    if len(parts) > 1:
        print(f"    RHS (sources - sinks):")
        for i, part in enumerate(parts[1:], 1):
            if " + " in part:
                subparts = part.split(" + ")
                for subpart in subparts:
                    print(f"      - {subpart}")
            else:
                print(f"      - {part}")

    # Parse to identify terms
    print(f"\n  Expected terms in RHS:")
    print(f"    ✓ Previous inventory (prev_inv)")
    print(f"    ✓ Production (production[t])")
    print(f"    ✓ Thaw inflow (thaw[t])")
    print(f"    ✓ Arrivals (sum of shipments arriving)")
    print(f"    ✓ Departures (sum of shipments departing)")  # THIS IS KEY!
    print(f"    ✓ Freeze outflow (freeze[t])")
    print(f"    ✓ Demand consumption (demand_consumed[t])")

    # Check if departures exist
    has_departures = "shipment['6122'" in expr_str
    has_production = "production['6122'" in expr_str

    print(f"\n  Analysis:")
    print(f"    Has production term: {has_production}")
    print(f"    Has departure terms: {has_departures}")

    if not has_departures:
        print(f"\n  ⚠️  WARNING: No departure terms found!")
        print(f"     Shipments may not be deducted from inventory!")

# Check if shipment variables even exist for this date
print(f"\n" + "=" * 80)
print(f"SHIPMENT VARIABLES FOR FIRST DATE")
print(f"=" * 80)

shipments_on_first_date = []
for idx in model.shipment:
    origin, dest, prod, delivery_date, state = idx
    if origin == '6122' and delivery_date == first_date:
        shipments_on_first_date.append((origin, dest, prod, delivery_date, state))

print(f"\nShipments FROM manufacturing WITH delivery_date = {first_date}:")
print(f"  Count: {len(shipments_on_first_date)}")
for s in shipments_on_first_date[:5]:
    print(f"    {s}")

# Check routes from manufacturing
print(f"\n" + "=" * 80)
print(f"ROUTES FROM MANUFACTURING")
print(f"=" * 80)

routes_from_mfg = [r for r in unified_routes if r.origin_node_id == '6122']
print(f"\nRoutes: {len(routes_from_mfg)}")
for route in routes_from_mfg:
    print(f"  {route.origin_node_id} → {route.destination_node_id}, transit={route.transit_days} days")

    # For first date, when would shipment DEPART to arrive on first date?
    # departure_date = delivery_date - transit_days
    departure_date = first_date - timedelta(days=route.transit_days)

    print(f"    To deliver on {first_date}, depart on {departure_date}")
    print(f"    Is departure_date in planning horizon? {departure_date >= start and departure_date <= end}")

print(f"\n" + "=" * 80)
print(f"ROOT CAUSE HYPOTHESIS:")
print(f"=" * 80)

print(f"""
If shipments are indexed by DELIVERY date but constraint calculates
DEPARTURE date, and departure_date is BEFORE the planning horizon,
then the shipment won't be included in the balance constraint!

Example:
  Planning horizon: Oct 16 only
  Route: 6122 → 6104, transit = 1 day
  To deliver on Oct 16, must depart Oct 15
  But Oct 15 is BEFORE planning horizon!
  So shipment is NOT deducted from Oct 16 inventory!

This allows "phantom" shipments that don't consume inventory.
""")
