"""Find where phantom inventory comes from."""
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import date, timedelta
from pyomo.core.base import value

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(days=6)  # 1 week for speed
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Build model to inspect constraint
pyomo_model = model.build_model()

# Check a demand node balance for day 2 (not first day)
node_id = '6104'
prod = 'HELGAS GFREE TRAD WHITE 470G'
check_date = start + timedelta(days=1)  # Day 2

print("=" * 80)
print(f"INSPECT BALANCE CONSTRAINT FOR DEMAND NODE")
print("=" * 80)
print(f"Node: {node_id}")
print(f"Product: {prod}")
print(f"Date: {check_date} (day 2)")

if (node_id, prod, check_date) in pyomo_model.ambient_balance_con:
    con = pyomo_model.ambient_balance_con[node_id, prod, check_date]
    print(f"\nConstraint expression:")
    expr_str = str(con.expr)

    # Check for arrivals
    if 'shipment' in expr_str:
        import re
        arrivals = re.findall(r"shipment\[[^\]]+\]", expr_str)
        print(f"\nArrival terms ({len(arrivals)}):")
        for arrival in arrivals[:5]:
            print(f"  + {arrival}")

    # Check for initial inventory
    if str(model.initial_inventory.get((node_id, prod, 'ambient'), 0)) in expr_str:
        print(f"\n⚠️  Initial inventory constant appears in expression!")
        print(f"     This should ONLY be on day 1, not day 2!")

# Solve and check
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
solved_model = model.model

# Now evaluate the balance
if (node_id, prod, check_date) in solved_model.ambient_balance_con:
    con = solved_model.ambient_balance_con[node_id, prod, check_date]

    print(f"\nSolved values:")

    # LHS
    inv_curr = value(solved_model.inventory[node_id, prod, 'ambient', check_date])
    print(f"  Inventory[day 2]: {inv_curr:.0f}")

    # RHS - previous inventory
    prev_date = start
    inv_prev = value(solved_model.inventory[node_id, prod, 'ambient', prev_date])
    print(f"  Inventory[day 1]: {inv_prev:.0f}")

    # Arrivals
    total_arrivals = 0
    for route in [r for r in unified_routes if r.destination_node_id == node_id]:
        ship_key = (route.origin_node_id, node_id, prod, check_date, 'ambient')
        if ship_key in solved_model.shipment:
            try:
                qty = value(solved_model.shipment[ship_key])
                if qty > 0.1:
                    total_arrivals += qty
                    print(f"  Arrival from {route.origin_node_id}: {qty:.0f}")
            except:
                pass

    # Demand consumed
    consumed = value(solved_model.demand_consumed[node_id, prod, check_date]) if (node_id, prod, check_date) in solved_model.demand_consumed else 0
    print(f"  Demand consumed: {consumed:.0f}")

    # Calculate expected
    expected = inv_prev + total_arrivals - consumed
    print(f"\nExpected inv[day 2] = {inv_prev:.0f} + {total_arrivals:.0f} - {consumed:.0f} = {expected:.0f}")
    print(f"Actual inv[day 2] = {inv_curr:.0f}")

    if abs(inv_curr - expected) > 1:
        print(f"\n❌ MISMATCH! Difference = {inv_curr - expected:.0f}")
        print(f"   Phantom inventory = {inv_curr - expected:.0f} units on this day alone!")
