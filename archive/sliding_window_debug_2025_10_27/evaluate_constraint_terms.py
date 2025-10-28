"""Evaluate each term in the balance constraint to find the bug."""
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
end = start + timedelta(days=1)  # 2-day horizon to check day 2
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
print("EVALUATE CONSTRAINT TERMS ONE BY ONE")
print("=" * 80)

mfg_id = '6122'
first_product = product_ids[0]
first_date = start

print(f"\nManufacturing ambient balance for {first_date}, {first_product[:30]}")
print(f"Expected: inventory[t] == prev_inv + production[t] + thaw[t] + arrivals - departures - freeze[t] - demand[t]")

# Evaluate each term
print(f"\nTerm values:")

# LHS
inv_key = (mfg_id, first_product, 'ambient', first_date)
if inv_key in solved_model.inventory:
    inventory_val = value(solved_model.inventory[inv_key])
    print(f"  LHS inventory[{first_date}]: {inventory_val:.2f}")
else:
    print(f"  LHS inventory: VARIABLE MISSING")
    inventory_val = None

# RHS terms
print(f"\n  RHS terms:")

# Production
prod_key = (mfg_id, first_product, first_date)
if prod_key in solved_model.production:
    production_val = value(solved_model.production[prod_key])
    print(f"    production[{first_date}]: {production_val:.2f}")
else:
    production_val = 0
    print(f"    production: 0 (variable missing)")

# Thaw
thaw_key = (mfg_id, first_product, first_date)
if thaw_key in solved_model.thaw:
    thaw_val = value(solved_model.thaw[thaw_key])
    print(f"    thaw[{first_date}]: {thaw_val:.2f}")
else:
    thaw_val = 0
    print(f"    thaw: 0")

# Freeze
freeze_key = (mfg_id, first_product, first_date)
if freeze_key in solved_model.freeze:
    freeze_val = value(solved_model.freeze[freeze_key])
    print(f"    freeze[{first_date}]: {freeze_val:.2f}")
else:
    freeze_val = 0
    print(f"    freeze: 0")

# Departures (check each route)
total_departures = 0
for route in [r for r in unified_routes if r.origin_node_id == mfg_id]:
    delivery_date = first_date + timedelta(days=route.transit_days)
    ship_key = (mfg_id, route.destination_node_id, first_product, delivery_date, 'ambient')

    if ship_key in solved_model.shipment:
        try:
            ship_val = value(solved_model.shipment[ship_key])
            print(f"    shipment[{mfg_id}→{route.destination_node_id}, deliver={delivery_date}]: {ship_val:.2f}")
            total_departures += ship_val
        except (ValueError, AttributeError):
            print(f"    shipment[{mfg_id}→{route.destination_node_id}, deliver={delivery_date}]: UNINITIALIZED")
    else:
        print(f"    shipment[{mfg_id}→{route.destination_node_id}, deliver={delivery_date}]: MISSING")

print(f"    TOTAL departures: {total_departures:.2f}")

# Demand consumption (manufacturing doesn't have demand, so should be 0)
demand_key = (mfg_id, first_product, first_date)
if demand_key in solved_model.demand_consumed:
    demand_consumed_val = value(solved_model.demand_consumed[demand_key])
    print(f"    demand_consumed[{first_date}]: {demand_consumed_val:.2f}")
else:
    demand_consumed_val = 0
    print(f"    demand_consumed: 0 (manufacturing has no demand)")

# Calculate RHS
prev_inv = 0  # No initial inventory
rhs = prev_inv + production_val + thaw_val - total_departures - freeze_val - demand_consumed_val

print(f"\n  Calculated RHS: {prev_inv} + {production_val} + {thaw_val} - {total_departures} - {freeze_val} - {demand_consumed_val} = {rhs:.2f}")
print(f"  LHS (inventory): {inventory_val:.2f}" if inventory_val is not None else "  LHS: None")

if inventory_val is not None and abs(rhs - inventory_val) < 0.01:
    print(f"  ✅ Constraint is satisfied")
else:
    print(f"  ❌ Constraint is VIOLATED or mismatch")

# Check SECOND day too
second_date = first_date + timedelta(days=1)
if second_date <= end:
    print(f"\n" + "=" * 80)
    print(f"SECOND DAY CHECK: {second_date}")
    print(f"=" * 80)

    # Production on day 2
    prod_key_2 = (mfg_id, first_product, second_date)
    if prod_key_2 in solved_model.production:
        production_val_2 = value(solved_model.production[prod_key_2])
        print(f"  production[{second_date}]: {production_val_2:.2f}")
    else:
        production_val_2 = 0
        print(f"  production: 0")

    # Inventory on day 2
    inv_key_2 = (mfg_id, first_product, 'ambient', second_date)
    if inv_key_2 in solved_model.inventory:
        inventory_val_2 = value(solved_model.inventory[inv_key_2])
        print(f"  inventory[{second_date}]: {inventory_val_2:.2f}")


print(f"\n" + "=" * 80)
if total_departures > 0 and production_val == 0 and prev_inv == 0:
    print(f"BUG IDENTIFIED: Departures = {total_departures:.0f} but production = 0 and prev_inv = 0!")
    print(f"The model is allowing shipments without source inventory!")
elif production_val > 0:
    print(f"✅ Model is producing on day 1: {production_val:.0f} units")
elif production_val_2 > 0:
    print(f"✅ Model is producing on day 2: {production_val_2:.0f} units")
