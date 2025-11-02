#!/usr/bin/env python3
"""Check actual disposal and shortage values in solution."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from pyomo.environ import value

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Parse inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()
inventory_data.snapshot_date = date(2025, 10, 16)

# Convert
inv_2tuple = inventory_data.to_optimization_dict()
initial_inv = {}
loc_dict = {loc.id: loc for loc in locations}
for (location, product), quantity in inv_2tuple.items():
    loc_node = loc_dict.get(location)
    if loc_node and str(loc_node.storage_mode) == 'frozen':
        state = 'frozen'
    else:
        state = 'ambient'
    initial_inv[(location, product, state)] = quantity

# 1-week
start = date(2025, 10, 17)
end = start + timedelta(days=6)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Calculate demand
total_demand = sum(e.quantity for e in forecast.entries if start <= e.forecast_date <= end)

print("="*80)
print("SOLUTION VALUES CHECK")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv,
    inventory_snapshot_date=inventory_data.snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=True
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\nSolve: {result.termination_condition}")
print(f"Objective: ${result.objective_value:,.2f}")

if result.is_optimal():
    pyomo_model = model.model

    # Extract disposal
    total_disposal = 0
    if hasattr(pyomo_model, 'disposal'):
        for key in pyomo_model.disposal:
            val = value(pyomo_model.disposal[key])
            if val and abs(val) > 0.01:
                total_disposal += val

    # Extract shortages
    total_shortage = 0
    if hasattr(pyomo_model, 'shortage'):
        for key in pyomo_model.shortage:
            val = value(pyomo_model.shortage[key])
            if val and abs(val) > 0.01:
                total_shortage += val

    # Extract production
    total_production = 0
    if hasattr(pyomo_model, 'production'):
        for key in pyomo_model.production:
            val = value(pyomo_model.production[key])
            if val and abs(val) > 0.01:
                total_production += val

    # Extract consumption
    total_consumed = 0
    if hasattr(pyomo_model, 'demand_consumed'):
        for key in pyomo_model.demand_consumed:
            val = value(pyomo_model.demand_consumed[key])
            if val and abs(val) > 0.01:
                total_consumed += val

    print(f"\nSolution breakdown:")
    print(f"  Total demand: {total_demand:,.0f} units")
    print(f"  Total consumed: {total_consumed:,.0f} units")
    print(f"  Total shortage: {total_shortage:,.0f} units")
    print(f"  Total production: {total_production:,.0f} units")
    print(f"  Total disposal: {total_disposal:,.0f} units")
    print(f"  Initial inventory: {sum(initial_inv.values()):,.0f} units")

    print(f"\nBalance check:")
    print(f"  consumed + shortage = {total_consumed + total_shortage:,.0f}")
    print(f"  Should equal demand = {total_demand:,.0f}")
    print(f"  Match: {abs(total_consumed + total_shortage - total_demand) < 1}")

    # Economic rationality
    print(f"\nEconomic rationality:")
    if total_disposal > total_shortage:
        print(f"  ✗ FAIL: Disposing more ({total_disposal:.0f}) than shortages ({total_shortage:.0f})")
        print(f"    Model should prefer shortages over disposing usable inventory")
    else:
        print(f"  ✓ PASS: Disposal ({total_disposal:.0f}) < Shortages ({total_shortage:.0f})")

    if total_production == 0 and total_shortage > 10000:
        print(f"  ✗ FAIL: Zero production with large shortages ({total_shortage:.0f})")
        print(f"    Model should produce to avoid shortage penalties")
    elif total_production > 0:
        print(f"  ✓ PASS: Model is producing ({total_production:.0f} units)")

print("="*80)
