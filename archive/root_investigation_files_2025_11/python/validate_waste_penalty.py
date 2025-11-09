"""Waste Penalty Validator - Check if end-of-horizon penalty works.

Expected Behavior:
  Model should penalize inventory remaining at end of horizon
  This incentivizes using/shipping all inventory before planning ends
  Result: Last day inventory should be ~0

Actual Behavior (discovered):
  Last day inventory: 17,520 units
  Expected: ~0 units

This validates:
1. Is waste penalty in objective function?
2. Is penalty coefficient strong enough?
3. Is penalty calculated correctly?
4. Does it actually drive inventory to zero?
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import timedelta, date

# Load data
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
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

print("Solving...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)

solution = model.get_solution()

print(f"\n{'=' * 80}")
print("WASTE PENALTY VALIDATION")
print(f"{'=' * 80}")

# Get last day from solution
inventory_dates = set(dt for (node, product, state, dt), qty in solution.inventory_state.items())
last_date = max(inventory_dates)

print(f"\nPlanning horizon:")
print(f"  Start: {start}")
print(f"  End (exclusive): {end}")
print(f"  Last date in solution: {last_date}")

# ============================================================================
# CHECK 1: End-of-Horizon Inventory
# ============================================================================
print(f"\n1. END-OF-HORIZON INVENTORY:")

last_day_inventory = sum(
    qty for (node, product, state, dt), qty in solution.inventory_state.items()
    if dt == last_date
)

print(f"  Inventory on last day: {last_day_inventory:,.0f} units")
print(f"  Expected: ~0 units (if waste penalty working)")

if last_day_inventory > 1000:
    print(f"  ❌ ISSUE: {last_day_inventory:.0f} units remain at end")
    print(f"     Waste penalty not driving inventory to zero!")
else:
    print(f"  ✅ Inventory near zero (waste penalty working)")

# ============================================================================
# CHECK 2: Waste Cost in Solution
# ============================================================================
print(f"\n2. WASTE COST IN SOLUTION:")

costs = solution.costs
waste_cost = costs.waste.total
shortage_cost = costs.waste.shortage_penalty
expiration_waste = costs.waste.expiration_waste

print(f"  Total waste cost: ${waste_cost:,.2f}")
print(f"  Shortage penalty: ${shortage_cost:,.2f}")
print(f"  Expiration waste: ${expiration_waste:,.2f}")

# Calculate expected waste cost if penalty applied
# Typical waste penalty: $1-2 per unit
expected_waste_from_inventory = last_day_inventory * 1.30  # $1.30 from code

print(f"\n  Expected waste from {last_day_inventory:.0f} units @ $1.30:")
print(f"    ${expected_waste_from_inventory:,.2f}")

if expiration_waste < expected_waste_from_inventory * 0.1:
    print(f"  ❌ Expiration waste (${expiration_waste:.2f}) << expected (${expected_waste_from_inventory:.2f})")
    print(f"     Waste penalty not being applied or coefficient wrong!")
else:
    print(f"  ✅ Waste cost reflects inventory penalty")

# ============================================================================
# CHECK 3: Model Waste Penalty Configuration
# ============================================================================
print(f"\n3. MODEL WASTE PENALTY:")

# Check if model has waste cost configured
print(f"  Model has waste calculation: {hasattr(model, 'obj')}")

# Check cost parameters
print(f"\n  Cost parameters:")
print(f"    waste_cost_multiplier: {cost_params.waste_cost_multiplier}")

# Check solution total cost breakdown
total_cost = solution.total_cost
print(f"\n  Total cost: ${total_cost:,.2f}")
print(f"  Waste as % of total: {waste_cost / total_cost * 100:.1f}%")

if waste_cost / total_cost < 0.01 and last_day_inventory > 1000:
    print(f"  ❌ Waste cost negligible despite {last_day_inventory:.0f} units remaining")
    print(f"     Penalty not strong enough or not applied!")

# ============================================================================
# CHECK 4: Inventory By Location on Last Day
# ============================================================================
print(f"\n4. WHERE IS END INVENTORY:")

inv_by_location = {}
for (node, product, state, dt), qty in solution.inventory_state.items():
    if dt == last_date and qty > 0.01:
        inv_by_location[node] = inv_by_location.get(node, 0) + qty

for loc in sorted(inv_by_location.keys(), key=lambda x: -inv_by_location[x]):
    print(f"  {loc}: {inv_by_location[loc]:,.0f} units")

# If all at manufacturing, penalty should encourage shipping
if '6122' in inv_by_location and inv_by_location['6122'] > last_day_inventory * 0.8:
    print(f"\n  ⚠️ 80%+ inventory at manufacturing on last day")
    print(f"     Waste penalty should encourage distribution")

# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'=' * 80}")
print(f"WASTE PENALTY DIAGNOSIS")
print(f"{'=' * 80}")

print(f"\nExpected behavior:")
print(f"  - Strong waste penalty on end-of-horizon inventory")
print(f"  - Model should drive inventory → 0 on last day")
print(f"  - Any remaining inventory should be heavily penalized")

print(f"\nActual behavior:")
print(f"  - Last day inventory: {last_day_inventory:,.0f} units")
print(f"  - Waste cost: ${waste_cost:,.2f}")
print(f"  - Expiration waste: ${expiration_waste:,.2f}")

if last_day_inventory > 1000:
    print(f"\n❌ WASTE PENALTY NOT WORKING CORRECTLY")
    print(f"   Possible causes:")
    print(f"   1. Waste penalty not included in objective")
    print(f"   2. Coefficient too weak")
    print(f"   3. Applied to wrong variable/date")
    print(f"   4. Constraint preventing inventory reduction")
else:
    print(f"\n✅ Waste penalty working as intended")

print(f"\n{'=' * 80}")
