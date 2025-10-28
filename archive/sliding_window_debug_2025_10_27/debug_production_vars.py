"""Debug why production extraction shows 0."""
from datetime import date, timedelta
import time
from pyomo.core.base import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("DEBUG: Production Variable Extraction")
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

try:
    initial_inventory = parser.parse_inventory()
    inventory_snapshot_date = initial_inventory.snapshot_date if initial_inventory else None
except:
    initial_inventory = None
    inventory_snapshot_date = None

if inventory_snapshot_date is None:
    inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)

planning_start_date = inventory_snapshot_date
planning_end_date = planning_start_date + timedelta(days=6)  # 1 week for speed

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print(f"\nPlanning: {planning_start_date} to {planning_end_date}")

# Build model
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_structure, start_date=planning_start_date,
    end_date=planning_end_date, truck_schedules=unified_truck_schedules,
    initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
    inventory_snapshot_date=inventory_snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

print("\n🚀 Solving...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)

print(f"\n✅ Solved: {result.termination_condition}, optimal={result.is_optimal()}")
print(f"   Objective: ${result.objective_value:,.2f}")

# Direct variable inspection
print("\n📊 DIRECT VARIABLE INSPECTION:")
pyomo_model = model.model  # Get the Pyomo model

if hasattr(pyomo_model, 'production'):
    print(f"\n1. Production variables exist: YES")
    print(f"   Total production variables: {len(list(pyomo_model.production))}")

    # Sample first 10 production variables
    prod_count = 0
    prod_total = 0
    print(f"\n   Sampling production variables:")
    for idx in list(pyomo_model.production)[:20]:
        var = pyomo_model.production[idx]
        try:
            val = value(var)
            if val and val > 0.1:
                print(f"     production{idx} = {val:.1f}")
                prod_count += 1
                prod_total += val
        except:
            print(f"     production{idx} = [ERROR extracting value]")

    print(f"\n   Non-zero production variables: {prod_count}")
    print(f"   Total production (sampled): {prod_total:,.0f}")

    # Check ALL production variables
    all_prod = 0
    all_nonzero = 0
    for idx in pyomo_model.production:
        try:
            val = value(pyomo_model.production[idx])
            if val and val > 0.1:
                all_nonzero += 1
                all_prod += val
        except:
            pass

    print(f"\n   ALL production variables checked:")
    print(f"     Non-zero: {all_nonzero}")
    print(f"     Total: {all_prod:,.0f} units")

else:
    print(f"\n1. Production variables exist: NO!")

# Check inventory
if hasattr(pyomo_model, 'inventory'):
    print(f"\n2. Inventory variables:")
    inv_count = 0
    inv_total = 0
    for idx in list(pyomo_model.inventory)[:10]:
        try:
            val = value(pyomo_model.inventory[idx])
            if val and val > 0.1:
                print(f"     inventory{idx} = {val:.1f}")
                inv_count += 1
                inv_total += val
        except:
            pass

    print(f"   Non-zero inventory (sample): {inv_count}, total: {inv_total:,.0f}")

# Check demand_consumed
if hasattr(pyomo_model, 'demand_consumed'):
    print(f"\n3. Demand consumed variables:")
    consumed_total = 0
    consumed_count = 0
    for idx in list(pyomo_model.demand_consumed)[:10]:
        try:
            val = value(pyomo_model.demand_consumed[idx])
            if val and val > 0.1:
                print(f"     demand_consumed{idx} = {val:.1f}")
                consumed_count += 1
                consumed_total += val
        except:
            pass

    # Total across all
    all_consumed = sum(value(pyomo_model.demand_consumed[idx])
                       for idx in pyomo_model.demand_consumed)
    print(f"   Total demand consumed: {all_consumed:,.0f} units")

# Check shortage
if hasattr(pyomo_model, 'shortage'):
    all_shortage = sum(value(pyomo_model.shortage[idx])
                      for idx in pyomo_model.shortage)
    print(f"\n4. Total shortage: {all_shortage:,.0f} units")

# Calculate demand
demand_total = sum(model.demand.values())
print(f"\n5. Total demand in model: {demand_total:,.0f} units")

print(f"\n6. Material balance check:")
print(f"   Consumed + Shortage = {all_consumed + all_shortage:,.0f}")
print(f"   Should equal demand = {demand_total:,.0f}")
print(f"   Match: {'✓' if abs((all_consumed + all_shortage) - demand_total) < 1 else '✗'}")

# Now use get_solution() to see what extraction returns
print(f"\n📦 EXTRACTED SOLUTION:")
solution = model.get_solution()
if solution:
    print(f"   Total production: {solution.get('total_production', 0):,.0f}")
    print(f"   Total shortage: {solution.get('total_shortage_units', 0):,.0f}")
    print(f"   Fill rate: {solution.get('fill_rate', 0)*100:.1f}%")
