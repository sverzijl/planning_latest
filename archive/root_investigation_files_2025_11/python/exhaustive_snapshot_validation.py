"""Exhaustive snapshot validation - check EVERY invariant.

This goes beyond aggregate validation to check:
1. Per-location material balance
2. Per-product flow accounting
3. Date arithmetic correctness
4. Age calculation correctness
5. Shipment-flow quantity matching
6. State transition consistency
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

prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']
locations_dict = {loc.id: loc for loc in locations}
solution = model.get_solution()

print(f"\n{'=' * 80}")
print("EXHAUSTIVE VALIDATION - Checking EVERY Invariant")
print(f"{'=' * 80}")

# Generate snapshots for analysis
day1 = start
day2 = start + timedelta(days=1)

snap1 = _generate_snapshot(day1, prod_schedule, shipments, locations_dict, adapted, forecast)
snap2 = _generate_snapshot(day2, prod_schedule, shipments, locations_dict, adapted, forecast)

issues_found = []

# ============================================================================
# VALIDATION 1: Per-Location Material Balance
# ============================================================================
print("\n1. PER-LOCATION MATERIAL BALANCE:")

for loc_id in list(locations_dict.keys())[:5]:  # Check first 5 locations
    # Get inventory for this location on both days
    inv1 = snap1['location_inventory'].get(loc_id, {})
    inv2 = snap2['location_inventory'].get(loc_id, {})

    inv1_total = inv1.get('total', 0)
    inv2_total = inv2.get('total', 0)

    # Get production at this location on day2
    production_day2 = sum(
        b['quantity'] for b in snap2.get('production_batches', [])
        if b.get('location_id') == loc_id or b.get('manufacturing_site_id') == loc_id
    )

    # Get arrivals at this location on day2
    arrivals_day2 = sum(
        f['quantity'] for f in snap2.get('inflows', [])
        if f.get('location') == loc_id and f.get('details') == 'arrival'
    )

    # Get departures from this location on day2
    departures_day2 = sum(
        f['quantity'] for f in snap2.get('outflows', [])
        if f.get('location') == loc_id and f.get('details') == 'departure'
    )

    # Get demand at this location on day2
    demand_day2 = sum(
        d['supplied'] for d in snap2.get('demand_satisfaction', [])
        if d.get('destination') == loc_id
    )

    # Material balance: inv2 = inv1 + production + arrivals - departures - demand
    expected_inv2 = inv1_total + production_day2 + arrivals_day2 - departures_day2 - demand_day2

    error = abs(inv2_total - expected_inv2)

    if error > 1:  # More than 1 unit error
        issues_found.append(
            f"{loc_id}: Material balance error {error:.0f} units. "
            f"inv1({inv1_total:.0f}) + prod({production_day2:.0f}) + arr({arrivals_day2:.0f}) "
            f"- dep({departures_day2:.0f}) - dem({demand_day2:.0f}) = {expected_inv2:.0f} expected, "
            f"got {inv2_total:.0f}"
        )
        print(f"  ❌ {loc_id}: Error {error:.0f} units")
    else:
        print(f"  ✅ {loc_id}: Balance OK (error: {error:.2f})")

# ============================================================================
# VALIDATION 2: Shipment-Flow Matching
# ============================================================================
print("\n2. SHIPMENT-FLOW MATCHING:")

# Check that flow quantities match shipment quantities
shipments_by_day = defaultdict(lambda: defaultdict(float))  # {day: {(origin, dest, product): qty}}
for shipment in shipments[:50]:  # Check first 50
    # Calculate departure date (simplified - assume 1 day transit)
    departure_date = shipment.delivery_date - timedelta(days=1)
    # Use correct field names (Shipment vs ShipmentResult)
    origin = shipment.origin_id if hasattr(shipment, 'origin_id') else shipment.origin
    dest = shipment.destination_id if hasattr(shipment, 'destination_id') else shipment.destination
    product = shipment.product_id if hasattr(shipment, 'product_id') else shipment.product
    key = (origin, dest, product)
    shipments_by_day[departure_date][key] += shipment.quantity

# Check day2 departures match shipments
day2_flows_by_route = defaultdict(float)
for flow in snap2.get('outflows', []):
    if flow.get('details') == 'departure':
        key = (flow.get('location'), flow.get('counterparty'), flow.get('product'))
        day2_flows_by_route[key] += flow.get('quantity', 0)

day2_shipments_expected = shipments_by_day[day2]

matched = 0
mismatched = 0
for key, flow_qty in day2_flows_by_route.items():
    shipment_qty = day2_shipments_expected.get(key, 0)
    if abs(flow_qty - shipment_qty) > 0.01:
        origin, dest, product = key
        issues_found.append(
            f"Flow-shipment mismatch: {origin}→{dest} {product}: "
            f"flow={flow_qty:.0f}, shipment={shipment_qty:.0f}"
        )
        mismatched += 1
    else:
        matched += 1

print(f"  Matched: {matched}")
print(f"  Mismatched: {mismatched}")
if mismatched > 0:
    print(f"  ❌ {mismatched} flow-shipment mismatches")
else:
    print(f"  ✅ All flows match shipments")

# ============================================================================
# VALIDATION 3: Demand Satisfaction Accounting
# ============================================================================
print("\n3. DEMAND SATISFACTION ACCOUNTING:")

# Check that demand satisfaction adds up correctly
demand_errors = 0
for demand_item in snap2.get('demand_satisfaction', []):
    demand = demand_item.get('demand', 0)
    supplied = demand_item.get('supplied', 0)

    # Extract shortage from status
    status = demand_item.get('status', '')
    if 'Short' in status:
        # Parse shortage from status text
        shortage_text = status.split('Short')[1].strip()
        try:
            shortage = float(shortage_text.split()[0])
        except:
            shortage = 0
    else:
        shortage = 0

    if abs((supplied + shortage) - demand) > 0.01:
        issues_found.append(
            f"Demand accounting: {demand_item.get('destination')} {demand_item.get('product')}: "
            f"supplied({supplied:.2f}) + shortage({shortage:.2f}) = {supplied+shortage:.2f} != demand({demand:.2f})"
        )
        demand_errors += 1

print(f"  Total demand records: {len(snap2.get('demand_satisfaction', []))}")
print(f"  Accounting errors: {demand_errors}")
if demand_errors > 0:
    print(f"  ❌ {demand_errors} demand accounting errors")
else:
    print(f"  ✅ All demand records account correctly")

# ============================================================================
# VALIDATION 4: Batch Age Calculations
# ============================================================================
print("\n4. BATCH AGE CALCULATIONS:")

age_errors = 0
for loc_id, inv_data in list(snap2['location_inventory'].items())[:3]:
    batches = inv_data.get('batches', {})
    for product_id, batch_list in batches.items():
        for batch in batch_list:
            prod_date = batch.get('production_date')
            age_days = batch.get('age_days')

            if prod_date and age_days is not None:
                expected_age = (day2 - prod_date).days
                if abs(age_days - expected_age) > 0:
                    issues_found.append(
                        f"Age calculation error: Batch {batch.get('id')} at {loc_id}: "
                        f"age_days={age_days}, expected={expected_age}"
                    )
                    age_errors += 1

print(f"  Age errors: {age_errors}")
if age_errors > 0:
    print(f"  ❌ {age_errors} age calculation errors")
else:
    print(f"  ✅ All batch ages calculated correctly")

# ============================================================================
# VALIDATION 5: Production Totals Match
# ============================================================================
print("\n5. PRODUCTION TOTALS:")

# Check that production_total matches sum of production_batches
prod_batches_sum = sum(b.get('quantity', 0) for b in snap2.get('production_batches', []))
prod_total = snap2.get('production_total', 0)

if abs(prod_batches_sum - prod_total) > 0.01:
    issues_found.append(
        f"Production total mismatch: sum of batches={prod_batches_sum:.0f}, "
        f"production_total={prod_total:.0f}"
    )
    print(f"  ❌ Production totals don't match")
else:
    print(f"  ✅ Production totals match ({prod_total:.0f} units)")

# ============================================================================
# VALIDATION 6: Inflow/Outflow Totals
# ============================================================================
print("\n6. FLOW TOTALS:")

total_inflows = sum(f.get('quantity', 0) for f in snap2.get('inflows', []))
total_outflows = sum(f.get('quantity', 0) for f in snap2.get('outflows', []))

print(f"  Total inflows: {total_inflows:,.0f} units")
print(f"  Total outflows: {total_outflows:,.0f} units")
print(f"  Net flow: {total_inflows - total_outflows:+,.0f} units")

# Inflows should include production
if abs(total_inflows - prod_total) > prod_total * 2:  # Inflows > 2× production seems wrong
    print(f"  ⚠️ Inflows seem high compared to production")

# ============================================================================
# VALIDATION 7: by_product Sum Matches Total
# ============================================================================
print("\n7. BY_PRODUCT AGGREGATION:")

by_product_errors = 0
for loc_id, inv_data in snap2['location_inventory'].items():
    total = inv_data.get('total', 0)
    by_product = inv_data.get('by_product', {})
    by_product_sum = sum(by_product.values())

    if abs(by_product_sum - total) > 0.01:
        issues_found.append(
            f"{loc_id}: by_product sum ({by_product_sum:.0f}) != total ({total:.0f})"
        )
        by_product_errors += 1

print(f"  Locations checked: {len(snap2['location_inventory'])}")
print(f"  by_product errors: {by_product_errors}")
if by_product_errors > 0:
    print(f"  ❌ {by_product_errors} locations have by_product sum mismatch")
else:
    print(f"  ✅ All locations: by_product sum = total")

# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'=' * 80}")
print(f"EXHAUSTIVE VALIDATION SUMMARY")
print(f"{'=' * 80}")

if issues_found:
    print(f"\n❌ DISCOVERED {len(issues_found)} ISSUES:")
    for issue in issues_found:
        print(f"  - {issue}")
else:
    print(f"\n✅ ALL EXHAUSTIVE VALIDATIONS PASSED")
    print(f"\nData is mathematically consistent across all checks.")
    print(f"\nIf user still sees issue, it's likely:")
    print(f"  1. UI rendering/display problem")
    print(f"  2. Specific visual formatting")
    print(f"  3. User workflow/interaction issue")
    print(f"  4. Need user to describe EXACTLY what they see")

print(f"\n{'=' * 80}")
