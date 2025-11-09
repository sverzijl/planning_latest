"""Deep analysis of Daily Snapshot to discover subtle issues.

This goes beyond duplicate checking to validate:
- Product name display (truncation, wrong names)
- Inventory quantities (unrealistic values)
- Flow quantities (match source data)
- Product coverage (all expected products appear)
- Slider behavior (inventory changes correctly)
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
from src.analysis.daily_snapshot import DailySnapshotGenerator
from datetime import timedelta

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

print("Solving model...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)

adapted = adapt_optimization_results(
    model=model,
    result={'result': result},
    inventory_snapshot_date=inventory.snapshot_date
)

prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']
solution = model.get_solution()

locations_dict = {loc.id: loc for loc in locations}
generator = DailySnapshotGenerator(
    production_schedule=prod_schedule,
    shipments=shipments,
    locations_dict=locations_dict,
    forecast=forecast,
    model_solution=solution
)

print(f"\n{'=' * 80}")
print("DEEP SNAPSHOT ANALYSIS - Discovering Subtle Issues")
print(f"{'=' * 80}")

# Check Day 2 (user would be moving slider and seeing this)
day2 = start + timedelta(days=1)
snapshot = generator._generate_single_snapshot(day2)

print(f"\nDay 2 ({day2}) Snapshot:")

# 1. Check product names in all components
print(f"\n1. PRODUCT NAMES:")
production_products = {b.product_id for b in snapshot.production_activity}
print(f"   Production: {sorted(production_products)}")

inflow_products = {f.product_id for f in snapshot.inflows}
print(f"   Inflows: {sorted(inflow_products)}")

outflow_products = {f.product_id for f in snapshot.outflows}
print(f"   Outflows: {sorted(outflow_products)}")

demand_products = {d.product_id for d in snapshot.demand_satisfied}
print(f"   Demand: {sorted(demand_products)}")

# Check inventory products
inventory_products = set()
for loc_inv in snapshot.location_inventory.values():
    if hasattr(loc_inv, 'product_inventory'):
        inventory_products.update(loc_inv.product_inventory.keys())
print(f"   Inventory: {sorted(inventory_products)}")

# 2. Check for UNKNOWN or truncated names
print(f"\n2. PRODUCT NAME ISSUES:")
all_snapshot_products = production_products | inflow_products | outflow_products | demand_products | inventory_products
unknown_count = sum(1 for p in all_snapshot_products if p == 'UNKNOWN')
truncated_count = sum(1 for p in all_snapshot_products if len(p) < 10 and p != 'UNKNOWN')

if unknown_count > 0:
    print(f"   ❌ {unknown_count} components show 'UNKNOWN' product")
    # Show which components
    if 'UNKNOWN' in inflow_products:
        unknown_inflows = [f for f in snapshot.inflows if f.product_id == 'UNKNOWN']
        print(f"      Inflows with UNKNOWN: {len(unknown_inflows)}")
        for f in unknown_inflows[:2]:
            print(f"        {f.flow_type} at {f.location_id}: {f.quantity:.0f} units")
    if 'UNKNOWN' in outflow_products:
        unknown_outflows = [f for f in snapshot.outflows if f.product_id == 'UNKNOWN']
        print(f"      Outflows with UNKNOWN: {len(unknown_outflows)}")
else:
    print(f"   ✅ No UNKNOWN products")

if truncated_count > 0:
    print(f"   ⚠️ {truncated_count} suspiciously short product names")
else:
    print(f"   ✅ All product names reasonable length")

# 3. Check inventory quantities
print(f"\n3. INVENTORY QUANTITIES:")
total_inventory = 0
for loc_id, loc_inv in snapshot.location_inventory.items():
    if hasattr(loc_inv, 'product_inventory'):
        for product, details in loc_inv.product_inventory.items():
            qty = details.get('total', 0) if isinstance(details, dict) else 0
            total_inventory += qty

print(f"   Total system inventory: {total_inventory:,.0f} units")

if total_inventory <= 0:
    print(f"   ❌ ISSUE: Zero or negative total inventory!")
elif total_inventory > 1_000_000:
    print(f"   ⚠️ WARNING: Unrealistically high inventory")
else:
    print(f"   ✅ Inventory quantity reasonable")

# 4. Check slider behavior (compare consecutive days)
print(f"\n4. SLIDER BEHAVIOR (Inventory Changes):")
day1 = start
day1_snapshot = generator._generate_single_snapshot(day1)
day2_snapshot = generator._generate_single_snapshot(day2)

day1_total = sum(
    details.get('total', 0) if isinstance(details, dict) else 0
    for loc_inv in day1_snapshot.location_inventory.values()
    if hasattr(loc_inv, 'product_inventory')
    for details in loc_inv.product_inventory.values()
)

day2_total = sum(
    details.get('total', 0) if isinstance(details, dict) else 0
    for loc_inv in day2_snapshot.location_inventory.values()
    if hasattr(loc_inv, 'product_inventory')
    for details in loc_inv.product_inventory.values()
)

print(f"   Day 1 total inventory: {day1_total:,.0f} units")
print(f"   Day 2 total inventory: {day2_total:,.0f} units")
print(f"   Change: {day2_total - day1_total:+,.0f} units")

if abs(day1_total - day2_total) < 1:
    print(f"   ⚠️ WARNING: Inventory barely changed (slider might not show movement)")

# 5. Production totals match
print(f"\n5. PRODUCTION MATCHING:")
day2_production_total = sum(b.quantity for b in day2_snapshot.production_activity)
print(f"   Day 2 production shown: {day2_production_total:,.0f} units")

# Cross-check with solution
solution_production_day2 = sum(
    qty for (node, prod, date), qty in (solution.production_by_date_product or {}).items()
    if date == day2
)
print(f"   Day 2 production in model: {solution_production_day2:,.0f} units")

if abs(day2_production_total - solution_production_day2) > 0.01:
    print(f"   ❌ MISMATCH: Snapshot shows different production than model!")
else:
    print(f"   ✅ Production matches model")

# 6. Check for empty/missing sections
print(f"\n6. SECTION COMPLETENESS:")
print(f"   Production activity: {len(snapshot.production_activity)} records")
print(f"   Inflows: {len(snapshot.inflows)} records")
print(f"   Outflows: {len(snapshot.outflows)} records")
print(f"   Demand satisfied: {len(snapshot.demand_satisfied)} records")
print(f"   Locations with inventory: {len(snapshot.location_inventory)}")

if len(snapshot.production_activity) == 0:
    print(f"   ⚠️ No production activity (might be correct for this day)")
if len(snapshot.inflows) == 0:
    print(f"   ⚠️ No inflows")
if len(snapshot.outflows) == 0:
    print(f"   ⚠️ No outflows")

print(f"\n{'=' * 80}")
print("DEEP ANALYSIS COMPLETE")
print(f"{'=' * 80}")
print("\nIf all checks pass but user still sees issue, it's likely:")
print("  - UI rendering problem (not data)")
print("  - Display formatting issue")
print("  - Specific product/location showing wrong")
print("  - Or I need even more specific validation")
