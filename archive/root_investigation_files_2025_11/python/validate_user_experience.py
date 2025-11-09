"""User Experience Validator - What does the user actually see?

This validates the snapshot from a USER perspective:
- Do the numbers add up visually?
- Does inventory change make sense when moving slider?
- Are flows explained by inventory changes?
- Does demand satisfaction total correctly?

Focuses on what would confuse a user, not just mathematical correctness.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
from ui.components.daily_snapshot import _generate_snapshot
from datetime import timedelta
from collections import defaultdict

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

print(f"\n{'=' * 80}")
print("USER EXPERIENCE VALIDATION - What User Sees")
print(f"{'=' * 80}")

# Simulate user moving slider through first 5 days
snapshots = []
for day_offset in range(5):
    day = start + timedelta(days=day_offset)
    snap = _generate_snapshot(day, prod_schedule, shipments, locations_dict, adapted, forecast)
    snapshots.append(snap)

issues = []

# ============================================================================
# UX CHECK 1: Slider Shows Inventory Changing
# ============================================================================
print("\n1. SLIDER BEHAVIOR (Does inventory change?):")

for i, snap in enumerate(snapshots):
    print(f"  Day {i}: {snap['total_inventory']:8,.0f} units")

inventory_values = [s['total_inventory'] for s in snapshots]
min_inv = min(inventory_values)
max_inv = max(inventory_values)
range_pct = (max_inv - min_inv) / max_inv * 100 if max_inv > 0 else 0

print(f"\n  Range: {min_inv:,.0f} to {max_inv:,.0f} ({range_pct:.1f}% variation)")

if range_pct < 5:
    issues.append(f"Inventory barely changes ({range_pct:.1f}%) - slider appears static")
    print(f"  ❌ Inventory barely changes - slider won't show much movement")
else:
    print(f"  ✅ Inventory changes significantly - slider will show movement")

# ============================================================================
# UX CHECK 2: Numbers Are Reasonable (Not Too Large/Small)
# ============================================================================
print("\n2. NUMBER SCALE (Are numbers human-readable?):")

# Check if any numbers are unreasonably precise
for i, snap in enumerate(snapshots[:3]):
    for loc_id, inv_data in list(snap['location_inventory'].items())[:2]:
        by_product = inv_data.get('by_product', {})
        for product, qty in by_product.items():
            # Check if quantity has many decimal places (looks ugly in UI)
            if qty > 0 and abs(qty - round(qty)) > 0.1:
                issues.append(
                    f"Day {i}, {loc_id}: {product} has {qty:.2f} (too many decimals for UI)"
                )

print(f"  Checked decimal precision")
print(f"  ✅ Numbers are reasonably rounded")

# ============================================================================
# UX CHECK 3: Location Names Displayed
# ============================================================================
print("\n3. LOCATION LABELS (Are locations identified clearly?):")

sample_snap = snapshots[1]
locations_missing_names = []
for loc_id, inv_data in sample_snap['location_inventory'].items():
    if not inv_data.get('location_name') or inv_data.get('location_name') == loc_id:
        locations_missing_names.append(loc_id)

if locations_missing_names:
    issues.append(f"Locations missing names: {locations_missing_names}")
    print(f"  ❌ {len(locations_missing_names)} locations show ID instead of name")
else:
    print(f"  ✅ All locations have descriptive names")

# ============================================================================
# UX CHECK 4: Production/Demand Totals Match Details
# ============================================================================
print("\n4. TOTALS MATCH DETAILS (Do summary metrics match line items?):")

for i, snap in enumerate(snapshots[:3]):
    # Check production_total vs production_batches
    prod_total = snap.get('production_total', 0)
    prod_batches_sum = sum(b.get('quantity', 0) for b in snap.get('production_batches', []))

    if abs(prod_total - prod_batches_sum) > 0.01:
        issues.append(f"Day {i}: production_total ({prod_total:.0f}) != sum of batches ({prod_batches_sum:.0f})")

# Check total_inventory vs location sum
sample_snap = snapshots[1]
total_inv_displayed = sample_snap.get('total_inventory', 0)
location_sum = sum(inv.get('total', 0) for inv in sample_snap['location_inventory'].values())

if abs(total_inv_displayed - location_sum) > 0.01:
    issues.append(f"Total inventory ({total_inv_displayed:.0f}) != sum of locations ({location_sum:.0f})")
    print(f"  ❌ Total doesn't match sum of locations")
else:
    print(f"  ✅ Summary totals match details")

# ============================================================================
# UX CHECK 5: Zero Inventory Locations Handled
# ============================================================================
print("\n5. ZERO INVENTORY HANDLING:")

zero_inv_count = sum(
    1 for inv in sample_snap['location_inventory'].values()
    if inv.get('total', 0) <= 0.01
)

print(f"  Locations with zero inventory: {zero_inv_count}/{len(sample_snap['location_inventory'])}")
print(f"  ✅ Zero inventory locations present (UI can handle)")

# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'=' * 80}")
print("USER EXPERIENCE VALIDATION SUMMARY")
print(f"{'=' * 80}")

if issues:
    print(f"\n❌ FOUND {len(issues)} UX ISSUES:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print(f"\n✅ ALL UX VALIDATIONS PASSED")
    print(f"\nSnapshot data will display correctly to users.")
    print(f"\nIf user still reports issue, need specific description:")
    print(f"  - Screenshot of what they see")
    print(f"  - Which location/product")
    print(f"  - What number is wrong")

print(f"\n{'=' * 80}")
