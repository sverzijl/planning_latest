"""Diagnose why production = 0 in sliding window model."""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from src.models.product import Product
from pyomo.core.base import value

print("=" * 80)
print("DIAGNOSTIC: Zero Production Investigation")
print("=" * 80)

# Parse
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

# Products
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = {pid: Product(id=pid, sku=pid, name=pid, units_per_mix=400) for pid in product_ids}

# Short horizon for speed
start = date(2025, 10, 27)
end = start + timedelta(days=2)  # 3 days only

print(f"\n[1] MODEL SETUP")
print(f"  Horizon: {start} to {end}")

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_params,
    products=products, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

print(f"  Demand entries in model: {len(model.demand)}")
print(f"  Total demand: {sum(model.demand.values()):,.0f} units")

# Build and solve
print(f"\n[2] BUILD AND SOLVE")
pyomo_model = model.build_model()

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=True)

print(f"  Status: {result.termination_condition}")
print(f"  Is optimal: {result.is_optimal()}")
print(f"  Is feasible: {result.is_feasible()}")
print(f"  Objective: ${result.objective_value:,.2f}" if result.objective_value else "  Objective: N/A")

# Check if variables were actually solved
if hasattr(pyomo_model, 'shortage'):
    first_shortage = list(pyomo_model.shortage)[0]
    var = pyomo_model.shortage[first_shortage]
    print(f"  Sample shortage var stale: {var.stale}")
    print(f"  Sample shortage var value: {var.value if hasattr(var, 'value') else 'NO VALUE'}")

# Check actual variable values
print(f"\n[3] PRODUCTION VARIABLES CHECK")
if hasattr(pyomo_model, 'production'):
    prod_count = 0
    prod_total = 0
    for (node_id, prod, t) in pyomo_model.production:
        try:
            qty = value(pyomo_model.production[node_id, prod, t])
            if qty and qty > 0.01:
                print(f"  Production[{node_id}, {prod[:20]}, {t}] = {qty:.0f}")
                prod_count += 1
                prod_total += qty
        except:
            pass
    print(f"  Total production entries > 0: {prod_count}")
    print(f"  Total production qty: {prod_total:,.0f} units")

# Check shortage variables
print(f"\n[4] SHORTAGE VARIABLES CHECK")
if hasattr(pyomo_model, 'shortage'):
    shortage_count = 0
    shortage_total = 0
    shortage_count_all = 0
    for (node_id, prod, t) in pyomo_model.shortage:
        shortage_count_all += 1
        try:
            var = pyomo_model.shortage[node_id, prod, t]
            if not var.stale:  # Variable was solved
                qty = value(var)
                if qty and qty > 0.01:
                    if shortage_count < 10:  # Show first 10
                        print(f"  Shortage[{node_id}, {prod[:20]}, {t}] = {qty:.0f}")
                    shortage_count += 1
                    shortage_total += qty
        except Exception as e:
            print(f"  Error extracting shortage: {e}")
            pass
    print(f"  Total shortage variables: {shortage_count_all}")
    print(f"  Shortage variables solved (not stale): checked")
    print(f"  Shortage entries > 0: {shortage_count}")
    print(f"  Total shortage qty: {shortage_total:,.0f} units")
    print(f"  Expected demand: {sum(model.demand.values()):,.0f} units")
    if shortage_total > 0:
        print(f"  ✓ Taking shortage (demand not being met)")
    else:
        print(f"  ❌ NOT taking shortage but also not producing!")

# Check demand_consumed
print(f"\n[4b] DEMAND_CONSUMED VARIABLES CHECK")
if hasattr(pyomo_model, 'demand_consumed'):
    consumed_count = 0
    consumed_total = 0
    for (node_id, prod, t) in pyomo_model.demand_consumed:
        try:
            var = pyomo_model.demand_consumed[node_id, prod, t]
            if not var.stale:
                qty = value(var)
                if qty and qty > 0.01:
                    if consumed_count < 5:
                        print(f"  Consumed[{node_id}, {prod[:20]}, {t}] = {qty:.0f}")
                    consumed_count += 1
                    consumed_total += qty
        except:
            pass
    print(f"  Demand consumed entries > 0: {consumed_count}")
    print(f"  Total demand consumed: {consumed_total:,.0f} units")

# Check if demand is being enforced
print(f"\n[5] DEMAND CONSTRAINT CHECK")
total_demand_in_model = sum(model.demand.values())
print(f"  Demand in model.demand: {total_demand_in_model:,.0f} units")
print(f"  Shortage extracted: {shortage_total:,.0f} units")
print(f"  Production extracted: {prod_total:,.0f} units")
print(f"  Sum (shortage + production): {shortage_total + prod_total:,.0f} units")
print(f"  Should equal demand: {total_demand_in_model:,.0f} units")

if abs((shortage_total + prod_total) - total_demand_in_model) > 1:
    print(f"  ⚠️  MISMATCH! Demand not being satisfied correctly")
else:
    print(f"  ✓ Material balance correct (all demand taken as shortage)")

# Check inventory
print(f"\n[6] INVENTORY CHECK")
if hasattr(pyomo_model, 'inventory'):
    inv_entries = 0
    for (node_id, prod, state, t) in pyomo_model.inventory:
        try:
            qty = value(pyomo_model.inventory[node_id, prod, state, t])
            if qty and qty > 0.01:
                inv_entries += 1
        except:
            pass
    print(f"  Inventory entries > 0: {inv_entries}")

print(f"\n[7] CONCLUSION")
if prod_total == 0 and shortage_total == 0:
    print(f"  ❌ ISSUE: No production AND no shortage, but demand exists!")
    print(f"  → Demand satisfaction constraint may not be working")
elif prod_total == 0 and shortage_total > 0:
    print(f"  ✓ EXPECTED: Taking all demand as shortage (production costs more than penalty)")
    print(f"  → This means model is working, just prefers shortage")
    print(f"  → Check: Is shortage penalty too low? Is production cost too high?")
else:
    print(f"  ✓ NORMAL: Production and/or shortage satisfying demand")
