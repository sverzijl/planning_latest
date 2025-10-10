"""Test full 29-week solve with state tracking implementation."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import datetime, timedelta
from src.parsers import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
import time

print("="*80)
print("FULL 29-WEEK MONOLITHIC SOLVE WITH STATE TRACKING")
print("="*80)

# Parse input data
print("\n1. Loading data...")
parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = parser.parse_locations()
routes = parser.parse_routes()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
truck_schedules = parser.parse_truck_schedules()
cost_params = parser.parse_cost_structure()

forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
forecast = forecast_parser.parse_forecast()
labor_calendar = parser.parse_labor_calendar()

# Extract products from forecast
products = list(set([entry.product_id for entry in forecast.entries]))

print(f"   Locations: {len(locations)}")
print(f"   Routes: {len(routes)}")
print(f"   Products: {len(products)}")
print(f"   Forecast entries: {len(forecast.entries)}")
print(f"   Date range: {forecast.start_date} to {forecast.end_date}")
print(f"   Duration: {(forecast.end_date - forecast.start_date).days} days")

# Create model
print("\n2. Building optimization model...")
start_time = time.time()

model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_params,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=False,
    enforce_shelf_life=True,
    initial_inventory={},
    solver_name='cbc'
)

build_time = time.time() - start_time
print(f"   Model built in {build_time:.1f} seconds")

# Display model size
print(f"\n3. Model statistics:")
print(f"   Decision variables: {model.model.nvariables():,}")
print(f"   Constraints: {model.model.nconstraints():,}")

# Check state tracking setup
print(f"\n4. State tracking configuration:")
print(f"   Locations with frozen storage: {sorted(model.locations_frozen_storage)}")
print(f"   Locations with ambient storage: {sorted(model.locations_ambient_storage)}")
print(f"   Intermediate storage locations: {sorted(model.intermediate_storage)}")
print(f"   Inventory tracking locations: {sorted(model.inventory_locations)}")

print(f"\n   Frozen inventory variables: {len(model.inventory_frozen_index_set):,}")
print(f"   Ambient inventory variables: {len(model.inventory_ambient_index_set):,}")

# Check Lineage specifically
if 'Lineage' in model.locations_frozen_storage:
    print(f"   ✅ Lineage has frozen storage capability")
else:
    print(f"   ❌ ERROR: Lineage missing frozen storage!")

if 'Lineage' not in model.locations_ambient_storage:
    print(f"   ✅ Lineage does NOT have ambient storage (frozen-only)")
else:
    print(f"   ❌ ERROR: Lineage has ambient storage (should be frozen-only!)")

# Check route arrival states
print(f"\n5. Route arrival state analysis:")
lineage_routes_in = [r for r, state in model.route_arrival_state.items()
                     if model.enumerated_routes[r].destination_id == 'Lineage']
lineage_routes_through = [r for r, state in model.route_arrival_state.items()
                          if 'Lineage' in model.enumerated_routes[r].path
                          and model.enumerated_routes[r].destination_id != 'Lineage']

print(f"   Routes TO Lineage: {len(lineage_routes_in)}")
for r_idx in lineage_routes_in:
    route = model.enumerated_routes[r_idx]
    state = model.route_arrival_state[r_idx]
    print(f"     Route {r_idx}: {' → '.join(route.path)} arrives as {state}")

print(f"   Routes THROUGH Lineage: {len(lineage_routes_through)}")
for r_idx in lineage_routes_through[:3]:  # Show first 3
    route = model.enumerated_routes[r_idx]
    state = model.route_arrival_state[r_idx]
    print(f"     Route {r_idx}: {' → '.join(route.path)} arrives as {state} at {route.destination_id}")

# Solve
print(f"\n6. Solving optimization model...")
print(f"   Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
solve_start = time.time()

result = model.solve(time_limit=3600, mip_gap=0.02)

solve_time = time.time() - solve_start
print(f"   End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Solve time: {solve_time:.1f} seconds ({solve_time/60:.1f} minutes)")

# Check results
print(f"\n7. Solution status:")
print(f"   Status: {result.status}")
print(f"   Objective: ${result.total_cost:,.2f}")
print(f"   MIP Gap: {result.mip_gap*100:.2f}%")

if result.status != 'optimal' and result.status != 'feasible':
    print(f"\n   ❌ Solve failed! Status: {result.status}")
    sys.exit(1)

# Extract solution details
print(f"\n8. Cost breakdown:")
print(f"   Labor cost: ${result.labor_cost:,.2f} ({result.labor_cost/result.total_cost*100:.1f}%)")
print(f"   Production cost: ${result.production_cost:,.2f} ({result.production_cost/result.total_cost*100:.1f}%)")
print(f"   Transport cost: ${result.transport_cost:,.2f} ({result.transport_cost/result.total_cost*100:.1f}%)")
print(f"   Inventory cost: ${result.inventory_cost:,.2f} ({result.inventory_cost/result.total_cost*100:.1f}%)")
print(f"   Shortage cost: ${result.shortage_cost:,.2f}")

# Analyze Lineage inventory
print(f"\n9. Lineage frozen inventory analysis:")
lineage_frozen_inv = {}
for (loc, prod, date), qty in result.ending_inventory.items():
    if loc == 'Lineage':
        if isinstance(qty, dict) and 'frozen' in qty:
            frozen_qty = qty['frozen']
        else:
            frozen_qty = qty
        if frozen_qty > 0.01:
            lineage_frozen_inv[(prod, date)] = frozen_qty

if lineage_frozen_inv:
    print(f"   ✅ Lineage has frozen inventory: {len(lineage_frozen_inv)} product-date combinations")
    total_frozen = sum(lineage_frozen_inv.values())
    print(f"   Total frozen inventory at Lineage: {total_frozen:,.0f} units")

    # Show some examples
    print(f"\n   Sample inventory (first 5):")
    for i, ((prod, date), qty) in enumerate(sorted(lineage_frozen_inv.items())[:5]):
        print(f"     {prod} on {date}: {qty:,.0f} units (frozen)")
else:
    print(f"   ⚠️  No frozen inventory at Lineage in solution")

# Analyze 6130 inventory
print(f"\n10. 6130 (WA) inventory analysis:")
dest_6130_inv = {}
for (loc, prod, date), qty in result.ending_inventory.items():
    if loc == '6130':
        if isinstance(qty, dict):
            ambient_qty = qty.get('ambient', 0)
            frozen_qty = qty.get('frozen', 0)
            if ambient_qty > 0.01 or frozen_qty > 0.01:
                dest_6130_inv[(prod, date)] = {'frozen': frozen_qty, 'ambient': ambient_qty}
        else:
            if qty > 0.01:
                dest_6130_inv[(prod, date)] = {'frozen': 0, 'ambient': qty}

if dest_6130_inv:
    print(f"   Inventory at 6130: {len(dest_6130_inv)} product-date combinations")
    total_frozen = sum(inv.get('frozen', 0) for inv in dest_6130_inv.values())
    total_ambient = sum(inv.get('ambient', 0) for inv in dest_6130_inv.values())
    print(f"   Total frozen: {total_frozen:,.0f} units")
    print(f"   Total ambient: {total_ambient:,.0f} units")

    if total_ambient > 0:
        print(f"   ✅ 6130 has ambient inventory (thawed product)")

    # Show some examples
    print(f"\n   Sample inventory (first 5):")
    for i, ((prod, date), inv) in enumerate(sorted(dest_6130_inv.items())[:5]):
        frozen = inv.get('frozen', 0)
        ambient = inv.get('ambient', 0)
        print(f"     {prod} on {date}: frozen={frozen:,.0f}, ambient={ambient:,.0f}")
else:
    print(f"   ⚠️  No inventory at 6130 in solution")

# Analyze shipments on Lineage routes
print(f"\n11. Shipments on Lineage routes:")
lineage_shipments_in = []
lineage_shipments_out = []

for shipment in result.shipments:
    route_idx = shipment['route_index']
    route = model.enumerated_routes[route_idx]

    if route.destination_id == 'Lineage':
        lineage_shipments_in.append(shipment)
    elif 'Lineage' in route.path and route.destination_id != 'Lineage':
        lineage_shipments_out.append(shipment)

if lineage_shipments_in:
    total_in = sum(s['quantity'] for s in lineage_shipments_in)
    print(f"   Shipments TO Lineage: {len(lineage_shipments_in)} shipments, {total_in:,.0f} total units")
    print(f"   ✅ Product flows to Lineage frozen buffer")
else:
    print(f"   ⚠️  No shipments TO Lineage")

if lineage_shipments_out:
    total_out = sum(s['quantity'] for s in lineage_shipments_out)
    print(f"   Shipments THROUGH Lineage: {len(lineage_shipments_out)} shipments, {total_out:,.0f} total units")
    print(f"   ✅ Product flows from Lineage to destinations")

    # Check if any go to 6130
    to_6130 = [s for s in lineage_shipments_out
               if model.enumerated_routes[s['route_index']].destination_id == '6130']
    if to_6130:
        total_6130 = sum(s['quantity'] for s in to_6130)
        print(f"   Shipments Lineage → 6130: {len(to_6130)} shipments, {total_6130:,.0f} units")
        print(f"   ✅ 6122 → Lineage → 6130 route is active")
else:
    print(f"   ⚠️  No shipments FROM Lineage")

# Check all destinations are served
print(f"\n12. Destination service check:")
destinations = [loc.id for loc in locations if loc.type == 'breadroom']
destinations_served = set()
for shipment in result.shipments:
    route = model.enumerated_routes[shipment['route_index']]
    if route.destination_id in destinations:
        destinations_served.add(route.destination_id)

print(f"   Total destinations: {len(destinations)}")
print(f"   Destinations served: {len(destinations_served)}")
print(f"   Served: {sorted(destinations_served)}")

if len(destinations_served) == len(destinations):
    print(f"   ✅ All destinations receiving shipments")
else:
    not_served = set(destinations) - destinations_served
    print(f"   ⚠️  Destinations not served: {sorted(not_served)}")

# Demand satisfaction
print(f"\n13. Demand satisfaction:")
total_demand = sum(entry.quantity for entry in forecast.entries)
total_produced = sum(s['quantity'] for s in result.shipments)
print(f"   Total demand: {total_demand:,.0f} units")
print(f"   Total shipped: {total_produced:,.0f} units")
print(f"   Fill rate: {total_produced/total_demand*100:.1f}%")

if result.shortage_cost > 0:
    print(f"   ⚠️  Shortages present: ${result.shortage_cost:,.2f}")
else:
    print(f"   ✅ 100% demand satisfaction")

print(f"\n" + "="*80)
print("VERIFICATION SUMMARY")
print("="*80)

checks_passed = 0
total_checks = 0

# Check 1: Model includes state tracking
total_checks += 1
if len(model.inventory_frozen_index_set) > 0 and len(model.inventory_ambient_index_set) > 0:
    print("✅ State tracking implemented (frozen + ambient variables)")
    checks_passed += 1
else:
    print("❌ State tracking not implemented")

# Check 2: Lineage is frozen-only
total_checks += 1
if 'Lineage' in model.locations_frozen_storage and 'Lineage' not in model.locations_ambient_storage:
    print("✅ Lineage configured as frozen-only storage")
    checks_passed += 1
else:
    print("❌ Lineage storage configuration incorrect")

# Check 3: Lineage route is active
total_checks += 1
if lineage_shipments_in and lineage_shipments_out:
    print("✅ 6122 → Lineage → 6130 route is active")
    checks_passed += 1
else:
    print("❌ Lineage route not used in solution")

# Check 4: All destinations served
total_checks += 1
if len(destinations_served) == len(destinations):
    print("✅ All destinations receiving product")
    checks_passed += 1
else:
    print("❌ Some destinations not served")

# Check 5: Demand satisfied
total_checks += 1
if result.shortage_cost == 0:
    print("✅ 100% demand satisfaction")
    checks_passed += 1
else:
    print("⚠️  Some shortages present")

# Check 6: Solution is optimal/feasible
total_checks += 1
if result.status in ['optimal', 'feasible']:
    print(f"✅ Solution status: {result.status}")
    checks_passed += 1
else:
    print(f"❌ Solution status: {result.status}")

print(f"\nChecks passed: {checks_passed}/{total_checks}")

if checks_passed == total_checks:
    print("\n🎉 ALL CHECKS PASSED - State tracking working correctly!")
else:
    print(f"\n⚠️  {total_checks - checks_passed} checks failed - review needed")

print(f"\nTotal runtime: {time.time() - start_time:.1f} seconds")
