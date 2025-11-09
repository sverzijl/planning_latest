"""Comprehensive multi-day snapshot validation.

Validates:
1. Schema compliance for each day
2. Invariants for each day
3. Temporal consistency across days
4. Material balance across the planning horizon

This will discover issues that single-day validation misses.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
from ui.components.daily_snapshot import _generate_snapshot
from src.ui_interface.snapshot_dict_validator import SnapshotDictValidator
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

prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']
locations_dict = {loc.id: loc for loc in locations}

print(f"\n{'=' * 80}")
print("COMPREHENSIVE MULTI-DAY SNAPSHOT VALIDATION")
print(f"{'=' * 80}")

# Generate snapshots for first week
snapshots_by_date = {}
validation_errors_by_day = defaultdict(list)

for day_offset in range(7):
    snapshot_date = start + timedelta(days=day_offset)

    # Generate snapshot (EXACT UI code path)
    snapshot = _generate_snapshot(
        selected_date=snapshot_date,
        production_schedule=prod_schedule,
        shipments=shipments,
        locations=locations_dict,
        results=adapted,
        forecast=forecast  # CRITICAL: Must pass forecast for demand tracking
    )

    snapshots_by_date[snapshot_date] = snapshot

    # Validate schema and invariants
    prev_snapshot = snapshots_by_date.get(snapshot_date - timedelta(days=1))
    errors = SnapshotDictValidator.validate_comprehensive(snapshot, prev_snapshot)

    if errors:
        validation_errors_by_day[day_offset] = errors
        print(f"\n❌ Day {day_offset} ({snapshot_date}): {len(errors)} errors")
        for err in errors[:3]:
            print(f"  - {err}")
    else:
        print(f"✅ Day {day_offset} ({snapshot_date}): All validations passed")

    # Print key metrics
    print(f"   Total inventory: {snapshot['total_inventory']:,.0f} units")
    print(f"   Production: {snapshot['production_total']:,.0f} units")
    print(f"   Demand: {snapshot['demand_total']:,.0f} units")

# Material balance validation across all days
print(f"\n{'=' * 80}")
print("MATERIAL BALANCE VALIDATION (Multi-Day)")
print(f"{'=' * 80}")

initial_inventory = snapshots_by_date[start]['total_inventory']
final_inventory = snapshots_by_date[start + timedelta(days=6)]['total_inventory']

total_production = sum(s['production_total'] for s in snapshots_by_date.values())
total_demand = sum(s['demand_total'] for s in snapshots_by_date.values())

print(f"\nWeek Summary:")
print(f"  Initial inventory: {initial_inventory:,.0f} units")
print(f"  Total production: {total_production:,.0f} units")
print(f"  Total demand: {total_demand:,.0f} units")
print(f"  Final inventory: {final_inventory:,.0f} units")

expected_final = initial_inventory + total_production - total_demand
print(f"\nMaterial Balance Check:")
print(f"  Expected final inventory: {expected_final:,.0f} units")
print(f"  Actual final inventory: {final_inventory:,.0f} units")
print(f"  Difference: {abs(final_inventory - expected_final):,.0f} units")

if abs(final_inventory - expected_final) > 100:
    print(f"  ❌ MATERIAL BALANCE VIOLATION!")
    print(f"     Inventory doesn't evolve correctly across days")
else:
    print(f"  ✅ Material balance holds")

# Check for specific UI-breaking issues
print(f"\n{'=' * 80}")
print("UI-SPECIFIC ISSUE DETECTION")
print(f"{'=' * 80}")

issues_found = []

# Issue 1: Empty batches dict (UI can't render product breakdown)
for day_offset, snapshot in enumerate(snapshots_by_date.values()):
    empty_batch_locations = [
        loc_id for loc_id, inv_data in snapshot['location_inventory'].items()
        if inv_data.get('total', 0) > 0.01 and not inv_data.get('batches')
    ]

    if empty_batch_locations:
        issues_found.append(
            f"Day {day_offset}: {len(empty_batch_locations)} locations have inventory "
            f"but empty batches dict (UI can't show product breakdown)"
        )

# Issue 2: by_product doesn't match batches
for day_offset, snapshot in enumerate(snapshots_by_date.values()):
    for loc_id, inv_data in snapshot['location_inventory'].items():
        by_product_keys = set(inv_data.get('by_product', {}).keys())
        batches_keys = set(inv_data.get('batches', {}).keys())

        if by_product_keys != batches_keys:
            issues_found.append(
                f"Day {day_offset}, {loc_id}: by_product keys != batches keys. "
                f"by_product: {by_product_keys}, batches: {batches_keys}"
            )

# Issue 3: Total inventory = 0 but should have inventory
for day_offset, snapshot in enumerate(snapshots_by_date.values()):
    if snapshot['production_total'] > 0 and snapshot['total_inventory'] <= 0.01:
        # Production happened but no inventory (all consumed?)
        if snapshot['demand_total'] < snapshot['production_total']:
            issues_found.append(
                f"Day {day_offset}: Production ({snapshot['production_total']:.0f}) > Demand ({snapshot['demand_total']:.0f}) "
                f"but total_inventory = {snapshot['total_inventory']:.0f}"
            )

# Issue 4: Inventory not changing across days (slider doesn't work)
inventory_values = [s['total_inventory'] for s in snapshots_by_date.values()]
if len(set(inventory_values)) == 1 and total_production > 0:
    issues_found.append(
        f"Inventory is constant ({inventory_values[0]:.0f}) across all days despite production"
    )

if issues_found:
    print(f"\n❌ DISCOVERED {len(issues_found)} UI-SPECIFIC ISSUES:")
    for issue in issues_found:
        print(f"  - {issue}")
else:
    print(f"\n✅ No UI-specific issues detected")

print(f"\n{'=' * 80}")

if validation_errors_by_day or issues_found:
    print(f"\nTOTAL ISSUES DISCOVERED: {sum(len(e) for e in validation_errors_by_day.values()) + len(issues_found)}")
else:
    print(f"\n✅ ALL VALIDATIONS PASSED - Snapshot data is correct")
    print(f"\nIf user still sees issue, please provide:")
    print(f"  1. Screenshot of the issue")
    print(f"  2. Specific text that's wrong")
    print(f"  3. Which location/product/date shows the problem")
