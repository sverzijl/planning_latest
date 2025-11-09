"""Last Day Validator - Check end-of-horizon behavior.

The last day of planning horizon often has special issues:
1. End-of-horizon inventory (what happens to remaining stock?)
2. Shipments beyond horizon (not tracked properly)
3. Waste calculations (inventory disposal)
4. Boundary conditions (missing data past horizon)

This validator compares last day to earlier days to find anomalies.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
from ui.components.daily_snapshot import _generate_snapshot
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

adapted = adapt_optimization_results(
    model=model,
    result={'result': result},
    inventory_snapshot_date=inventory.snapshot_date
)

solution = model.get_solution()
prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']
locations_dict = {loc.id: loc for loc in locations}

print(f"\n{'=' * 80}")
print("LAST DAY VALIDATION - End-of-Horizon Behavior")
print(f"{'=' * 80}")

# Determine last day
planning_days = (end - start).days
last_day = end - timedelta(days=1)
second_last = last_day - timedelta(days=1)

print(f"\nPlanning horizon:")
print(f"  Start: {start}")
print(f"  End: {end}")
print(f"  Days: {planning_days}")
print(f"  Last day: {last_day}")

issues_found = []

# Generate snapshots for last 3 days + a middle day for comparison
middle_day = start + timedelta(days=planning_days // 2)
days_to_check = [middle_day, second_last, last_day]
snapshots = {}

for day in days_to_check:
    snapshots[day] = _generate_snapshot(day, prod_schedule, shipments, locations_dict, adapted, forecast)

# ============================================================================
# CHECK 1: Last Day Inventory Behavior
# ============================================================================
print(f"\n1. INVENTORY ON LAST DAY:")

middle_inv = snapshots[middle_day]['total_inventory']
second_last_inv = snapshots[second_last]['total_inventory']
last_inv = snapshots[last_day]['total_inventory']

print(f"  Middle day ({middle_day}): {middle_inv:,.0f} units")
print(f"  Second last ({second_last}): {second_last_inv:,.0f} units")
print(f"  Last day ({last_day}): {last_inv:,.0f} units")

# Check for unusual drop on last day
drop_pct = (second_last_inv - last_inv) / second_last_inv * 100 if second_last_inv > 0 else 0

if drop_pct > 50:
    issues_found.append(
        f"Last day inventory drops {drop_pct:.1f}% ({second_last_inv:.0f} → {last_inv:.0f}). "
        "Possible end-of-horizon disposal issue."
    )
    print(f"  ❌ Inventory drops {drop_pct:.1f}% on last day (unusual!)")
elif drop_pct < -50:
    issues_found.append(
        f"Last day inventory increases {abs(drop_pct):.1f}%. Possible boundary issue."
    )
    print(f"  ❌ Inventory increases {abs(drop_pct):.1f}% on last day (unusual!)")
else:
    print(f"  ✅ Last day inventory reasonable (change: {drop_pct:+.1f}%)")

# ============================================================================
# CHECK 2: Shipments Beyond Horizon
# ============================================================================
print(f"\n2. SHIPMENTS BEYOND HORIZON:")

# Check if there are shipments delivering after horizon end
shipments_beyond = [
    s for s in shipments
    if s.delivery_date > end
]

print(f"  Shipments delivering beyond {end}: {len(shipments_beyond)}")
if shipments_beyond:
    total_beyond = sum(s.quantity for s in shipments_beyond)
    print(f"  Total quantity: {total_beyond:,.0f} units")

    # These should appear as departures on last days but not as arrivals
    # Check if they cause material balance issues
    issues_found.append(
        f"{len(shipments_beyond)} shipments deliver beyond horizon ({total_beyond:.0f} units). "
        "These appear as departures but not arrivals, breaking material balance."
    )
    print(f"  ❌ Material balance issue: departures without matching arrivals")
else:
    print(f"  ✅ No shipments beyond horizon")

# ============================================================================
# CHECK 3: Production on Last Day
# ============================================================================
print(f"\n3. PRODUCTION ON LAST DAY:")

last_snap = snapshots[last_day]
last_production = last_snap.get('production_total', 0)
last_demand = last_snap.get('demand_total', 0)

print(f"  Production: {last_production:,.0f} units")
print(f"  Demand: {last_demand:,.0f} units")

if last_production > last_demand * 2:
    issues_found.append(
        f"Last day production ({last_production:.0f}) >> demand ({last_demand:.0f}). "
        "Producing stock that can't be used before horizon end."
    )
    print(f"  ⚠️ Producing more than needed on last day")
else:
    print(f"  ✅ Production reasonable relative to demand")

# ============================================================================
# CHECK 4: Demand Satisfaction on Last Day
# ============================================================================
print(f"\n4. DEMAND SATISFACTION ON LAST DAY:")

demand_records = last_snap.get('demand_satisfaction', [])
print(f"  Demand records: {len(demand_records)}")

if demand_records:
    total_demand_last = sum(d.get('demand', 0) for d in demand_records)
    total_supplied_last = sum(d.get('supplied', 0) for d in demand_records)
    total_shortage_last = sum(d.get('demand', 0) - d.get('supplied', 0) for d in demand_records)

    fill_rate_last = total_supplied_last / total_demand_last * 100 if total_demand_last > 0 else 100

    print(f"  Total demand: {total_demand_last:,.0f}")
    print(f"  Total supplied: {total_supplied_last:,.0f}")
    print(f"  Fill rate: {fill_rate_last:.1f}%")

    # Compare to middle day fill rate
    middle_demand_records = snapshots[middle_day].get('demand_satisfaction', [])
    middle_demand_total = sum(d.get('demand', 0) for d in middle_demand_records)
    middle_supplied_total = sum(d.get('supplied', 0) for d in middle_demand_records)
    fill_rate_middle = middle_supplied_total / middle_demand_total * 100 if middle_demand_total > 0 else 100

    print(f"  Middle day fill rate: {fill_rate_middle:.1f}%")

    if abs(fill_rate_last - fill_rate_middle) > 20:
        issues_found.append(
            f"Last day fill rate ({fill_rate_last:.1f}%) differs from middle ({fill_rate_middle:.1f}%) by >20%"
        )
        print(f"  ❌ Last day fill rate anomalous")
    else:
        print(f"  ✅ Last day fill rate consistent")
else:
    print(f"  ⚠️ No demand records on last day")

# ============================================================================
# CHECK 5: Outflows on Last Day (Check for Anomalies)
# ============================================================================
print(f"\n5. OUTFLOWS ON LAST DAY:")

last_outflows = last_snap.get('outflows', [])
last_departures = [f for f in last_outflows if 'Departure' in f.get('type', '')]
last_demand_flows = [f for f in last_outflows if 'Demand' in f.get('type', '')]

print(f"  Total outflows: {len(last_outflows)}")
print(f"  Departures: {len(last_departures)}")
print(f"  Demand: {len(last_demand_flows)}")

# Departures on last day should be minimal (nowhere to go)
departure_total = sum(f.get('quantity', 0) for f in last_departures)
print(f"  Total departed: {departure_total:,.0f} units")

if departure_total > last_production:
    issues_found.append(
        f"Last day departures ({departure_total:.0f}) > production ({last_production:.0f}). "
        "Shipping stock off horizon?"
    )
    print(f"  ❌ Departures exceed production on last day")
else:
    print(f"  ✅ Departures reasonable")

# ============================================================================
# CHECK 6: Compare Last Day to Model State
# ============================================================================
print(f"\n6. LAST DAY MODEL CONSISTENCY:")

model_inv_last = sum(
    qty for (node, product, state, date), qty in solution.inventory_state.items()
    if date == last_day
)

snap_inv_last = last_snap.get('total_inventory', 0)

print(f"  Model inventory on last day: {model_inv_last:,.0f}")
print(f"  Snapshot inventory on last day: {snap_inv_last:,.0f}")
print(f"  Difference: {abs(model_inv_last - snap_inv_last):,.0f}")

if abs(model_inv_last - snap_inv_last) > 100:
    issues_found.append(
        f"Last day snapshot ({snap_inv_last:.0f}) != model ({model_inv_last:.0f}), "
        f"difference: {abs(model_inv_last - snap_inv_last):.0f}"
    )
    print(f"  ❌ Snapshot doesn't match model on last day")
else:
    print(f"  ✅ Snapshot matches model on last day")

# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'=' * 80}")
print(f"LAST DAY VALIDATION SUMMARY")
print(f"{'=' * 80}")

if issues_found:
    print(f"\n❌ DISCOVERED {len(issues_found)} LAST-DAY ISSUES:")
    for issue in issues_found:
        print(f"  - {issue}")
else:
    print(f"\n✅ Last day behaves correctly")
    print(f"\nLast day data is consistent with earlier days.")
    print(f"\nIf user sees issue on last day, need specific description:")
    print(f"  - What's wrong? (e.g., wrong number, missing data)")
    print(f"  - Which location?")
    print(f"  - Which metric? (inventory, production, demand)")

print(f"\n{'=' * 80}")
