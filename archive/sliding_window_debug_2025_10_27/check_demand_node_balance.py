"""Check demand node balance to see how it gets inventory."""
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
end = start
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
print("CHECK DEMAND NODE BALANCE")
print("=" * 80)

# Pick a demand node
demand_node_id = '6104'  # NSW/ACT hub (also has demand)
first_product = product_ids[0]
first_date = start

print(f"\nDemand node: {demand_node_id}")
print(f"Product: {first_product[:30]}")
print(f"Date: {first_date}")

# Check demand
demand_key = (demand_node_id, first_product, first_date)
if demand_key in model_wrapper.demand:
    demand_qty = model_wrapper.demand[demand_key]
    print(f"\nDemand: {demand_qty:.2f} units")
else:
    demand_qty = 0
    print(f"\nDemand: 0 (no demand on this date)")

# Check if constraint exists
if (demand_node_id, first_product, first_date) in solved_model.ambient_balance_con:
    con = solved_model.ambient_balance_con[demand_node_id, first_product, first_date]

    print(f"\nConstraint expression:")
    print(f"  {con.expr}")

    # Evaluate terms
    inv_key = (demand_node_id, first_product, 'ambient', first_date)
    inventory_val = value(solved_model.inventory[inv_key]) if inv_key in solved_model.inventory else None

    print(f"\nTerm values:")
    print(f"  inventory[{first_date}]: {inventory_val:.2f}" if inventory_val is not None else "  inventory: MISSING")

    # Check arrivals
    routes_to_node = [r for r in unified_routes if r.destination_node_id == demand_node_id]
    total_arrivals = 0
    for route in routes_to_node:
        ship_key = (route.origin_node_id, demand_node_id, first_product, first_date, 'ambient')
        if ship_key in solved_model.shipment:
            try:
                val = value(solved_model.shipment[ship_key])
                print(f"  arrival from {route.origin_node_id}: {val:.2f}")
                total_arrivals += val
            except:
                print(f"  arrival from {route.origin_node_id}: UNINITIALIZED")

    print(f"  TOTAL arrivals: {total_arrivals:.2f}")

    # Demand consumed
    demand_consumed_key = (demand_node_id, first_product, first_date)
    if demand_consumed_key in solved_model.demand_consumed:
        consumed = value(solved_model.demand_consumed[demand_consumed_key])
        print(f"  demand_consumed: {consumed:.2f}")
    else:
        consumed = 0
        print(f"  demand_consumed: 0")

    # Shortage
    if demand_consumed_key in solved_model.shortage:
        shortage = value(solved_model.shortage[demand_consumed_key])
        print(f"  shortage: {shortage:.2f}")
    else:
        shortage = 0

    print(f"\n  Analysis:")
    print(f"    Demand: {demand_qty:.0f}")
    print(f"    Consumed: {consumed:.0f}")
    print(f"    Shortage: {shortage:.0f}")
    print(f"    Arrivals: {total_arrivals:.0f}")
    print(f"    Inventory: {inventory_val:.0f}" if inventory_val is not None else "    Inventory: None")

    if consumed > 0 and total_arrivals == 0 and (inventory_val is None or inventory_val < 0.01):
        print(f"\n  ❌ BUG: Consuming {consumed:.0f} units but no arrivals and no inventory!")
