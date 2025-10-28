"""Test sliding window WITHOUT initial inventory - should produce."""
from datetime import date, timedelta
import time
from pyomo.core.base import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("SLIDING WINDOW - NO INITIAL INVENTORY (Should produce!)")
print("=" * 80)

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_truck_schedules = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# NO initial inventory
initial_inventory = None
planning_start_date = min(e.forecast_date for e in forecast.entries)
planning_end_date = planning_start_date + timedelta(days=6)  # 1 week

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print(f"\n📅 Planning: {planning_start_date} to {planning_end_date} (1 week)")
print(f"   Initial inventory: NONE (should force production!)")

demand_in_horizon = sum(e.quantity for e in forecast.entries
                        if planning_start_date <= e.forecast_date <= planning_end_date)
print(f"   Demand: {demand_in_horizon:,.0f} units")

# Build model WITHOUT initial inventory
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_structure, start_date=planning_start_date,
    end_date=planning_end_date, truck_schedules=unified_truck_schedules,
    initial_inventory=None,  # NO INITIAL INVENTORY - must produce!
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

print("\n🚀 Solving...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)

print(f"\n✅ Solved:")
print(f"   Status: {result.termination_condition}")
print(f"   Is optimal: {result.is_optimal()}")
print(f"   Solve time: {result.solve_time_seconds:.2f}s")
print(f"   Objective: ${result.objective_value:,.2f}")

# Check production directly
pyomo_model = model.model
all_prod = 0
prod_count = 0
for idx in pyomo_model.production:
    try:
        val = value(pyomo_model.production[idx])
        if val and val > 0.1:
            prod_count += 1
            all_prod += val
    except:
        pass

all_shortage = sum(value(pyomo_model.shortage[idx]) for idx in pyomo_model.shortage)
all_consumed = sum(value(pyomo_model.demand_consumed[idx]) for idx in pyomo_model.demand_consumed)

print(f"\n📊 RESULTS:")
print(f"   Total production: {all_prod:,.0f} units")
print(f"   Production events: {prod_count}")
print(f"   Total shortage: {all_shortage:,.0f} units")
print(f"   Demand consumed: {all_consumed:,.0f} units")
print(f"   Fill rate: {(1 - all_shortage/demand_in_horizon)*100:.1f}%")

print(f"\n🎯 VALIDATION:")
if all_prod > 0:
    print(f"   ✅ Production > 0 (model CAN produce!)")
else:
    print(f"   ❌ Production = 0 (unexpected!)")

if all_consumed > 0:
    print(f"   ✅ Demand satisfied")
else:
    print(f"   ❌ No demand satisfied")

# Material balance
print(f"\n📐 Material balance:")
print(f"   Production: {all_prod:,.0f}")
print(f"   Consumed: {all_consumed:,.0f}")
print(f"   Shortage: {all_shortage:,.0f}")
print(f"   Consumed + Shortage = {all_consumed + all_shortage:,.0f}")
print(f"   Should equal demand = {demand_in_horizon:,.0f}")

if all_prod > 0 and all_consumed > 0:
    print(f"\n🎊 SUCCESS! Model produces when no initial inventory!")
