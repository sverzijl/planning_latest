"""Final diagnostic with corrected model object access."""
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
solved_model = model_wrapper.model  # ACCESS THE SOLVED MODEL!

print("=" * 80)
print("FINAL DIAGNOSTIC - AFTER FIX")
print("=" * 80)

# Check production
total_prod = sum(value(solved_model.production[idx]) for idx in solved_model.production)
print(f"\nProduction: {total_prod:,.0f} units")

# Sample production values
prod_count = 0
for idx in solved_model.production:
    val = value(solved_model.production[idx])
    if val > 0.1:
        prod_count += 1
        if prod_count <= 5:
            print(f"  {idx}: {val:.1f}")

# Check shortage
total_shortage = sum(value(solved_model.shortage[idx]) for idx in solved_model.shortage)
print(f"\nShortage: {total_shortage:,.0f} units")

# Check demand consumed
total_consumed = sum(value(solved_model.demand_consumed[idx]) for idx in solved_model.demand_consumed)
print(f"Demand consumed: {total_consumed:,.0f} units")

# Check shipments from manufacturing
shipments_from_mfg = 0
for idx in solved_model.shipment:
    origin, dest, prod, delivery_date, state = idx
    if origin == '6122':
        try:
            val = value(solved_model.shipment[idx])
            if val and val > 0.1:
                shipments_from_mfg += val
        except (ValueError, AttributeError):
            # Uninitialized variable - treat as 0
            pass

print(f"Shipments from manufacturing: {shipments_from_mfg:,.0f} units")

# Material balance at manufacturing
mfg_inv_total = 0
for idx in solved_model.inventory:
    node_id, prod, state, date_val = idx
    if node_id == '6122':
        try:
            val = value(solved_model.inventory[idx])
            if abs(val) > 0.1:
                mfg_inv_total += val
        except (ValueError, AttributeError):
            pass

print(f"Manufacturing inventory (end): {mfg_inv_total:,.0f} units")

# Summary
total_demand = sum(model_wrapper.demand.values())
print(f"\n" + "=" * 80)
print(f"MATERIAL BALANCE:")
print(f"=" * 80)
print(f"  Total demand: {total_demand:,.0f}")
print(f"  Production: {total_prod:,.0f}")
print(f"  Shortage: {total_shortage:,.0f}")
print(f"  Consumed: {total_consumed:,.0f}")
print(f"  Production + Shortage = {total_prod + total_shortage:,.0f}")
print(f"  Consumed + Shortage = {total_consumed + total_shortage:,.0f}")

if total_prod > 0:
    print(f"\n✅ FIX WORKED! Model is now producing!")
elif total_shortage > 0:
    print(f"\n⚠️  Taking shortage instead of producing")
    print(f"   (Check: is shortage cheaper than production?)")
else:
    print(f"\n❌ STILL BROKEN: No production and no shortage!")
