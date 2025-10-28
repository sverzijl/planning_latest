"""Trace where 345k demand is satisfied with only 78k supply."""
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
end = start + timedelta(weeks=4)
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

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)
solved_model = model.model

print("=" * 80)
print("MATERIAL BALANCE TRACE")
print("=" * 80)

# Total sources
initial_inv_total = sum(model.initial_inventory.values())
production_total = sum(value(solved_model.production[idx]) for idx in solved_model.production)

print(f"\nSOURCES (where inventory comes from):")
print(f"  Initial inventory: {initial_inv_total:,.0f} units")
print(f"  Production: {production_total:,.0f} units")
print(f"  TOTAL SUPPLY: {initial_inv_total + production_total:,.0f} units")

# Total sinks
total_consumed = sum(value(solved_model.demand_consumed[idx]) for idx in solved_model.demand_consumed)
total_shortage = sum(value(solved_model.shortage[idx]) for idx in solved_model.shortage)

# End inventory
last_date = max(model.dates)
end_inventory = 0
for (node_id, prod, state, t) in solved_model.inventory:
    if t == last_date:
        try:
            qty = value(solved_model.inventory[node_id, prod, state, t])
            if qty > 0:
                end_inventory += qty
        except:
            pass

print(f"\nSINKS (where inventory goes):")
print(f"  Demand consumed: {total_consumed:,.0f} units")
print(f"  Shortage: {total_shortage:,.0f} units")
print(f"  End inventory: {end_inventory:,.0f} units")
print(f"  TOTAL USAGE: {total_consumed + total_shortage + end_inventory:,.0f} units")

print(f"\n" + "=" * 80)
print(f"MATERIAL BALANCE CHECK")
print(f"=" * 80)

supply = initial_inv_total + production_total
usage = total_consumed + end_inventory

print(f"Supply (initial + production): {supply:,.0f}")
print(f"Usage (consumed + end_inv): {usage:,.0f}")
print(f"Difference: {usage - supply:,.0f}")

if abs(usage - supply) > 100:
    print(f"\n❌ MATERIAL BALANCE VIOLATED!")
    print(f"   {usage:,.0f} units used but only {supply:,.0f} available")
    print(f"   PHANTOM INVENTORY: {usage - supply:,.0f} units")
    print(f"\n   This is the BUG - inventory appearing from nowhere!")
else:
    print(f"\n✅ Material balance OK")
