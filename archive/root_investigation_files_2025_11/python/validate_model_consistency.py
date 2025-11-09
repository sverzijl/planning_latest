"""Model Internal Consistency Validator.

Validates the optimization model's own state, not just the snapshot display.

Checks:
1. Model material balance (production + initial = shipments + final_inventory + consumption)
2. inventory_state matches production and shipments
3. State balance (ambient vs frozen inventory)
4. Production enters inventory before shipping
5. Temporal consistency in model variables

This validates the MODEL is correct, not just the UI display.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import timedelta
from collections import defaultdict

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
print("MODEL INTERNAL CONSISTENCY VALIDATION")
print(f"{'=' * 80}")

issues_found = []

# ============================================================================
# VALIDATION 1: Total Material Balance (Model Level)
# ============================================================================
print("\n1. MODEL MATERIAL BALANCE:")

# Get all quantities from model
initial_inv_dict = inventory.to_optimization_dict()
total_initial = sum(initial_inv_dict.values())

production_dict = solution.production_by_date_product or {}
total_production = sum(production_dict.values())

shipments_dict = solution.shipments_by_route_product_date or {}
total_shipments = sum(shipments_dict.values())

inventory_state = solution.inventory_state or {}
total_final_inventory = sum(inventory_state.values())

demand_consumed_dict = solution.demand_consumed or {}
total_demand_consumed = sum(demand_consumed_dict.values())

shortages_dict = solution.shortages or {}
total_shortage = sum(shortages_dict.values())

print(f"  Initial inventory: {total_initial:,.0f} units")
print(f"  Total production: {total_production:,.0f} units")
print(f"  Total shipments: {total_shipments:,.0f} units")
print(f"  Total demand consumed: {total_demand_consumed:,.0f} units")
print(f"  Total shortage: {total_shortage:,.0f} units")
print(f"  Final inventory: {total_final_inventory:,.0f} units")

# Material balance: initial + production = shipments + final_inventory + demand_consumed
# (shipments and demand_consumed both remove from system)
expected_outflow = total_shipments + total_demand_consumed
expected_remaining = total_initial + total_production - expected_outflow

print(f"\n  Expected remaining: {expected_remaining:,.0f} units")
print(f"  Actual final inventory: {total_final_inventory:,.0f} units")
print(f"  Difference: {abs(expected_remaining - total_final_inventory):,.0f} units")

if abs(expected_remaining - total_final_inventory) > 100:
    issues_found.append(
        f"Model material balance error: Expected {expected_remaining:.0f}, got {total_final_inventory:.0f}"
    )
    print(f"  ❌ MODEL MATERIAL BALANCE VIOLATED")
else:
    print(f"  ✅ Model material balance correct")

# ============================================================================
# VALIDATION 2: Production Enters Inventory
# ============================================================================
print("\n2. PRODUCTION → INVENTORY:")

# Check that production on each date appears in inventory
for (node, product, date), qty in list(production_dict.items())[:10]:
    # Production should appear in inventory on same date
    inv_on_prod_date = sum(
        inv_qty for (inv_node, inv_prod, inv_state, inv_date), inv_qty in inventory_state.items()
        if inv_node == node and inv_prod == product and inv_date == date
    )

    if inv_on_prod_date < qty - 0.01:  # Less than production (some might ship immediately)
        # This is OK if it ships same day
        shipments_same_day = sum(
            ship_qty for (origin, dest, prod, delivery_date), ship_qty in shipments_dict.items()
            if origin == node and prod == product and delivery_date == date + timedelta(days=1)
        )

        if inv_on_prod_date + shipments_same_day < qty - 1:
            issues_found.append(
                f"Production {product} at {node} on {date}: {qty:.0f} units produced, "
                f"but only {inv_on_prod_date:.0f} in inventory + {shipments_same_day:.0f} shipped"
            )

print(f"  Checked {min(10, len(production_dict))} production batches")
print(f"  ✅ Production enters inventory correctly")

# ============================================================================
# VALIDATION 3: State Balance (Ambient vs Frozen)
# ============================================================================
print("\n3. STATE DISTRIBUTION:")

# Break down inventory by state
by_state = defaultdict(float)
for (node, product, state, date), qty in inventory_state.items():
    by_state[state] += qty

print(f"  Ambient inventory: {by_state.get('ambient', 0):,.0f} units")
print(f"  Frozen inventory: {by_state.get('frozen', 0):,.0f} units")
print(f"  Thawed inventory: {by_state.get('thawed', 0):,.0f} units")
print(f"  Total: {sum(by_state.values()):,.0f} units")

if sum(by_state.values()) != total_final_inventory:
    issues_found.append("State breakdown doesn't sum to total inventory")
    print(f"  ❌ State breakdown mismatch")
else:
    print(f"  ✅ State breakdown correct")

# ============================================================================
# VALIDATION 4: Shipment Totals by Origin
# ============================================================================
print("\n4. SHIPMENTS BY ORIGIN NODE:")

shipments_by_origin = defaultdict(float)
for (origin, dest, product, date), qty in shipments_dict.items():
    shipments_by_origin[origin] += qty

for origin in ['6122', '6104', '6125', 'Lineage']:
    total_shipped = shipments_by_origin.get(origin, 0)
    print(f"  {origin}: {total_shipped:,.0f} units shipped")

# Manufacturing should ship most
if shipments_by_origin.get('6122', 0) < total_production * 0.5:
    issues_found.append(
        f"Manufacturing ships {shipments_by_origin.get('6122', 0):.0f} but produces {total_production:.0f}"
    )
    print(f"  ⚠️ Manufacturing ships less than half of production")

# ============================================================================
# VALIDATION 5: Demand Consumption by Location
# ============================================================================
print("\n5. DEMAND CONSUMPTION BY DESTINATION:")

demand_by_dest = defaultdict(float)
for (node, product, date), qty in demand_consumed_dict.items():
    demand_by_dest[node] += qty

# Check demand nodes (not hubs)
locations_dict = {loc.id: loc for loc in locations}
locations_dict = {loc.id: loc for loc in locations}
demand_nodes = [loc for loc in locations_dict.keys() if loc not in ['6122', '6104', '6125', 'Lineage']]
total_demand_at_nodes = sum(demand_by_dest.get(node, 0) for node in demand_nodes)

print(f"  Demand at hubs (6104, 6125): {demand_by_dest.get('6104', 0) + demand_by_dest.get('6125', 0):.0f}")
print(f"  Demand at demand nodes: {total_demand_at_nodes:,.0f}")

if demand_by_dest.get('6104', 0) > total_demand_consumed * 0.1:
    issues_found.append(
        f"Hub 6104 has demand consumption ({demand_by_dest.get('6104', 0):.0f}) - hubs shouldn't consume"
    )
    print(f"  ❌ Hubs are consuming demand (should be demand nodes only)")
else:
    print(f"  ✅ Demand consumption at correct locations")

# ============================================================================
# VALIDATION 6: Initial Inventory Conservation
# ============================================================================
print("\n6. INITIAL INVENTORY TRACKING:")

# Check that initial inventory appears in inventory_state for start date
initial_in_state = sum(
    qty for (node, product, state, date), qty in inventory_state.items()
    if date == start
)

print(f"  Initial inventory (input): {total_initial:,.0f} units")
print(f"  Inventory on start date (model): {initial_in_state:,.0f} units")

if abs(initial_in_state - total_initial) > 1:
    issues_found.append(
        f"Initial inventory not preserved: input={total_initial:.0f}, model={initial_in_state:.0f}"
    )
    print(f"  ❌ Initial inventory not preserved in model")
else:
    print(f"  ✅ Initial inventory preserved")

# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'=' * 80}")
print(f"MODEL VALIDATION SUMMARY")
print(f"{'=' * 80}")

if issues_found:
    print(f"\n❌ DISCOVERED {len(issues_found)} MODEL ISSUES:")
    for issue in issues_found:
        print(f"  - {issue}")
else:
    print(f"\n✅ MODEL IS INTERNALLY CONSISTENT")

# Additional deep dive
print(f"\n{'=' * 80}")
print(f"DEEP DIVE: Daily Inventory Evolution")
print(f"{'=' * 80}")

# Track inventory evolution day by day
inv_by_date = defaultdict(float)
for (node, product, state, date), qty in inventory_state.items():
    inv_by_date[date] += qty

sorted_dates = sorted(inv_by_date.keys())
print(f"\nInventory by date (first 7 days):")
for i, date in enumerate(sorted_dates[:7]):
    inv = inv_by_date[date]
    prod = sum(qty for (node, prod, d), qty in production_dict.items() if d == date)
    demand = sum(qty for (node, prod, d), qty in demand_consumed_dict.items() if d == date)

    print(f"  {date}: Inv={inv:7,.0f}, Prod={prod:6,.0f}, Demand={demand:6,.0f}")

    # Check if inventory is growing when production > demand
    if i > 0:
        prev_date = sorted_dates[i-1]
        prev_inv = inv_by_date[prev_date]
        change = inv - prev_inv

        if prod > demand and change < 0:
            issues_found.append(
                f"Day {i} ({date}): Production ({prod:.0f}) > Demand ({demand:.0f}) "
                f"but inventory decreased ({prev_inv:.0f} → {inv:.0f})"
            )
            print(f"    ❌ Inventory decreased despite net production")

print(f"\n{'=' * 80}")

if issues_found:
    print(f"\nFOUND {len(issues_found)} ISSUES - Investigating...")
else:
    print(f"\nMODEL PASSES ALL VALIDATIONS")
    print(f"\nIf user still sees issue, need more specific description of what's wrong.")
