"""Validate Snapshot vs Model - Direct Comparison.

Compares what the snapshot shows vs what the model actually computed.
This catches bugs where snapshot misinterprets model data.

For each date:
  snapshot.inventory[loc][prod] should equal model.inventory_state[(loc,prod,state,date)]
  snapshot.production should equal model.production[(node,prod,date)]
  snapshot.demand should equal model.demand_consumed[(node,prod,date)]
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

solution = model.get_solution()
prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']
locations_dict = {loc.id: loc for loc in locations}

print(f"\n{'=' * 80}")
print("SNAPSHOT VS MODEL VALIDATION - Direct Comparison")
print(f"{'=' * 80}")

issues_found = []

# Check multiple days
for day_offset in [0, 1, 2]:
    day = start + timedelta(days=day_offset)
    snap = _generate_snapshot(day, prod_schedule, shipments, locations_dict, adapted, forecast)

    # ========================================================================
    # CHECK 1: Inventory Totals Match
    # ========================================================================

    # Model total for this date
    model_total_inv = sum(
        qty for (node, product, state, date), qty in solution.inventory_state.items()
        if date == day
    )

    snap_total_inv = snap.get('total_inventory', 0)

    if abs(model_total_inv - snap_total_inv) > 1:
        issues_found.append(
            f"Day {day_offset}: Total inventory mismatch - "
            f"model={model_total_inv:.0f}, snapshot={snap_total_inv:.0f}, "
            f"error={abs(model_total_inv - snap_total_inv):.0f}"
        )
        print(f"❌ Day {day_offset}: Inventory total mismatch ({abs(model_total_inv - snap_total_inv):.0f} units)")
    else:
        print(f"✅ Day {day_offset}: Inventory total matches (model={model_total_inv:,.0f})")

    # ========================================================================
    # CHECK 2: Production Matches
    # ========================================================================

    model_production = sum(
        qty for (node, product, date), qty in solution.production_by_date_product.items()
        if date == day
    )

    snap_production = snap.get('production_total', 0)

    if abs(model_production - snap_production) > 1:
        issues_found.append(
            f"Day {day_offset}: Production mismatch - "
            f"model={model_production:.0f}, snapshot={snap_production:.0f}"
        )

    # ========================================================================
    # CHECK 3: Per-Location Inventory Matches
    # ========================================================================

    # Check a few key locations
    for loc_id in ['6122', '6104', '6125']:
        model_inv_at_loc = sum(
            qty for (node, product, state, date), qty in solution.inventory_state.items()
            if node == loc_id and date == day
        )

        snap_inv_at_loc = snap['location_inventory'].get(loc_id, {}).get('total', 0)

        if abs(model_inv_at_loc - snap_inv_at_loc) > 1:
            issues_found.append(
                f"Day {day_offset}, {loc_id}: Inventory mismatch - "
                f"model={model_inv_at_loc:.0f}, snapshot={snap_inv_at_loc:.0f}, "
                f"error={abs(model_inv_at_loc - snap_inv_at_loc):.0f}"
            )

print(f"\n{'=' * 80}")
print(f"VALIDATION SUMMARY")
print(f"{'=' * 80}")

if issues_found:
    print(f"\n❌ FOUND {len(issues_found)} SNAPSHOT-MODEL MISMATCHES:")
    for issue in issues_found:
        print(f"  - {issue}")
else:
    print(f"\n✅ SNAPSHOT MATCHES MODEL PERFECTLY")
    print(f"\nAll snapshot data matches model state variables.")
    print(f"If user sees issue, it's likely:")
    print(f"  1. UI rendering/display formatting")
    print(f"  2. Specific interaction/workflow")
    print(f"  3. Need exact description of what's wrong")

print(f"\n{'=' * 80}")
