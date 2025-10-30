"""Compare Last Day vs Normal Day - Find Visual Differences.

Checks what user would actually SEE in the UI:
- Are there fewer flows shown?
- Is data missing from tables?
- Are specific fields empty?
- Does structure differ?

Compares side-by-side to find anomalies.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
from ui.components.daily_snapshot import _generate_snapshot
from datetime import timedelta

# Load and solve
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

prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']
locations_dict = {loc.id: loc for loc in locations}

# Compare normal day vs last day
planning_days = (end - start).days
normal_day = start + timedelta(days=planning_days // 2)  # Middle
last_day = end - timedelta(days=1)

normal_snap = _generate_snapshot(normal_day, prod_schedule, shipments, locations_dict, adapted, forecast)
last_snap = _generate_snapshot(last_day, prod_schedule, shipments, locations_dict, adapted, forecast)

print(f"\n{'=' * 80}")
print(f"SIDE-BY-SIDE COMPARISON: Normal Day vs Last Day")
print(f"{'=' * 80}")
print(f"\nNormal day: {normal_day}")
print(f"Last day: {last_day}")

issues = []

# ============================================================================
# Field-by-field comparison
# ============================================================================
print(f"\n{'Metric':<30s} {'Normal Day':>15s} {'Last Day':>15s} {'Issue?':>10s}")
print(f"{'-'*75}")

fields_to_compare = [
    ('total_inventory', 'Total Inventory'),
    ('production_total', 'Production'),
    ('demand_total', 'Demand'),
    ('in_transit_total', 'In Transit'),
]

for field, label in fields_to_compare:
    normal_val = normal_snap.get(field, 0)
    last_val = last_snap.get(field, 0)

    # Check if last day has anomalous value
    if isinstance(normal_val, (int, float)) and isinstance(last_val, (int, float)):
        ratio = last_val / normal_val if normal_val > 0 else 0
        anomaly = ""
        if ratio > 3 or ratio < 0.3:
            anomaly = "❌"
            issues.append(f"{label}: Last day {last_val:.0f} vs normal {normal_val:.0f} (ratio: {ratio:.2f}×)")

        print(f"{label:<30s} {normal_val:>15,.0f} {last_val:>15,.0f} {anomaly:>10s}")

# List-based fields
print(f"\n{'List Fields':<30s} {'Normal Day':>15s} {'Last Day':>15s} {'Issue?':>10s}")
print(f"{'-'*75}")

list_fields = [
    ('production_batches', 'Production Batches'),
    ('inflows', 'Inflows'),
    ('outflows', 'Outflows'),
    ('demand_satisfaction', 'Demand Records'),
    ('in_transit_shipments', 'In-Transit'),
]

for field, label in list_fields:
    normal_count = len(normal_snap.get(field, []))
    last_count = len(last_snap.get(field, []))

    anomaly = ""
    if normal_count > 0 and last_count == 0:
        anomaly = "❌ EMPTY!"
        issues.append(f"{label}: Last day has 0 items (normal day has {normal_count})")
    elif last_count > normal_count * 2:
        anomaly = "❌ 2× HIGH"
        issues.append(f"{label}: Last day has {last_count} items (normal: {normal_count})")

    print(f"{label:<30s} {normal_count:>15d} {last_count:>15d} {anomaly:>10s}")

# ============================================================================
# Location inventory comparison
# ============================================================================
print(f"\n7. LOCATION INVENTORY DETAILS:")

print(f"  Locations with inventory:")
print(f"    Normal day: {len([l for l, inv in normal_snap['location_inventory'].items() if inv.get('total', 0) > 0])}")
print(f"    Last day: {len([l for l, inv in last_snap['location_inventory'].items() if inv.get('total', 0) > 0])}")

# Check if any location has inventory on normal day but not on last
normal_locs_with_inv = {l for l, inv in normal_snap['location_inventory'].items() if inv.get('total', 0) > 0.01}
last_locs_with_inv = {l for l, inv in last_snap['location_inventory'].items() if inv.get('total', 0) > 0.01}

missing_on_last = normal_locs_with_inv - last_locs_with_inv
appeared_on_last = last_locs_with_inv - normal_locs_with_inv

if missing_on_last:
    print(f"  ⚠️ Locations with inventory on normal but not last: {missing_on_last}")
if appeared_on_last:
    print(f"  ⚠️ Locations with inventory only on last day: {appeared_on_last}")

# ============================================================================
# Check specific location detail
# ============================================================================
print(f"\n8. SAMPLE LOCATION DETAIL (6104):")

normal_6104 = normal_snap['location_inventory'].get('6104', {})
last_6104 = last_snap['location_inventory'].get('6104', {})

print(f"  Normal day:")
print(f"    Total: {normal_6104.get('total', 0):,.0f}")
print(f"    Products: {len(normal_6104.get('by_product', {}))}")
print(f"    Batches: {len(normal_6104.get('batches', {}))}")

print(f"  Last day:")
print(f"    Total: {last_6104.get('total', 0):,.0f}")
print(f"    Products: {len(last_6104.get('by_product', {}))}")
print(f"    Batches: {len(last_6104.get('batches', {}))}")

# Check if batches dict is empty on last day
if normal_6104.get('batches') and not last_6104.get('batches'):
    issues.append("Location 6104: Has batches on normal day but empty on last day")
    print(f"  ❌ Batches missing on last day!")

# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'=' * 80}")
print(f"COMPARISON SUMMARY")
print(f"{'=' * 80}")

if issues:
    print(f"\n❌ FOUND {len(issues)} VISUAL/STRUCTURAL DIFFERENCES:")
    for issue in issues:
        print(f"  - {issue}")
    print(f"\nThese differences may confuse users on the last day.")
else:
    print(f"\n✅ Last day structure matches normal days")
    print(f"\nNo anomalous differences detected.")

print(f"\n{'=' * 80}")
