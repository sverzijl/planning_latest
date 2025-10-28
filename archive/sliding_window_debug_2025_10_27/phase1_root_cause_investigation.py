"""Phase 1: Root Cause Investigation - Shipment/Production Bug

Gather evidence to understand WHERE and WHY shipments exist without production.
"""
from datetime import date, timedelta
from pyomo.core.base import value
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("PHASE 1: ROOT CAUSE INVESTIGATION")
print("=" * 80)

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Simple 2-day test
start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=1)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Build and solve
pyomo_model = model.build_model()
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)

print(f"\nSolve status: {result.termination_condition}, optimal={result.is_optimal()}")

# ============================================================================
# EVIDENCE 1: Check route transit times
# ============================================================================
print("\n" + "=" * 80)
print("EVIDENCE 1: Route Transit Times")
print("=" * 80)

routes_from_mfg = [r for r in unified_routes if r.origin_node_id == '6122']
print(f"\nRoutes from manufacturing (6122): {len(routes_from_mfg)}")
for route in routes_from_mfg[:10]:
    print(f"  {route.origin_node_id} → {route.destination_node_id}")
    print(f"    Transit days: {route.transit_days}")
    print(f"    Transport mode: {route.transport_mode}")

# ============================================================================
# EVIDENCE 2: Manufacturing node balance constraint
# ============================================================================
print("\n" + "=" * 80)
print("EVIDENCE 2: Manufacturing Node Balance Constraint")
print("=" * 80)

mfg_id = '6122'
first_date = start
first_product = product_ids[0]

if (mfg_id, first_product, first_date) in pyomo_model.ambient_balance_con:
    con = pyomo_model.ambient_balance_con[mfg_id, first_product, first_date]
    print(f"\nManufacturing balance for {mfg_id}, {first_product[:30]}, {first_date}:")
    print(f"\nConstraint expression:")
    print(f"  {con.expr}")

    # Parse the expression to identify terms
    print(f"\nExpected form:")
    print(f"  inventory[t] = prev_inv + production[t] + arrivals - departures - freeze[t] - demand")

# ============================================================================
# EVIDENCE 3: Shipment variable indexing
# ============================================================================
print("\n" + "=" * 80)
print("EVIDENCE 3: Shipment Variable Indexing")
print("=" * 80)

# Check how shipments are indexed
shipment_indices = list(pyomo_model.shipment)[:10]
print(f"\nSample shipment variable indices:")
for idx in shipment_indices:
    origin, dest, prod, date, state = idx
    print(f"  shipment[{origin}, {dest}, {prod[:25]}, date={date}, {state}]")

print(f"\nQuestion: Is 'date' the DELIVERY date or DEPARTURE date?")
print(f"Expected: DELIVERY date (when goods arrive at destination)")

# ============================================================================
# EVIDENCE 4: Check actual shipment values
# ============================================================================
print("\n" + "=" * 80)
print("EVIDENCE 4: Actual Shipment Values (Departing from Manufacturing)")
print("=" * 80)

shipments_from_mfg = []
for idx in pyomo_model.shipment:
    origin, dest, prod, delivery_date, state = idx
    if origin == '6122':  # Manufacturing
        try:
            val = value(pyomo_model.shipment[idx])
            if val and val > 0.1:
                shipments_from_mfg.append({
                    'origin': origin,
                    'dest': dest,
                    'product': prod,
                    'delivery_date': delivery_date,
                    'state': state,
                    'quantity': val
                })
        except:
            pass

print(f"\nNon-zero shipments FROM manufacturing: {len(shipments_from_mfg)}")
for s in shipments_from_mfg[:10]:
    print(f"  {s['origin']} → {s['dest']}, deliver={s['delivery_date']}, {s['state']}: {s['quantity']:.1f} units")

total_shipments_from_mfg = sum(s['quantity'] for s in shipments_from_mfg)
print(f"\nTotal shipments from manufacturing: {total_shipments_from_mfg:,.0f} units")

# ============================================================================
# EVIDENCE 5: Check production values
# ============================================================================
print("\n" + "=" * 80)
print("EVIDENCE 5: Production Values at Manufacturing")
print("=" * 80)

production_at_mfg = []
for idx in pyomo_model.production:
    node_id, prod, date = idx
    if node_id == '6122':
        val = value(pyomo_model.production[idx])
        if val and val > 0.1:
            production_at_mfg.append({'product': prod, 'date': date, 'quantity': val})

print(f"\nNon-zero production at manufacturing: {len(production_at_mfg)}")
for p in production_at_mfg[:10]:
    print(f"  {p['product'][:30]}, {p['date']}: {p['quantity']:.1f} units")

total_production = sum(p['quantity'] for p in production_at_mfg)
print(f"\nTotal production: {total_production:,.0f} units")

# ============================================================================
# EVIDENCE 6: Check inventory at manufacturing
# ============================================================================
print("\n" + "=" * 80)
print("EVIDENCE 6: Inventory at Manufacturing")
print("=" * 80)

inventory_at_mfg = []
for idx in pyomo_model.inventory:
    node_id, prod, state, date = idx
    if node_id == '6122':
        val = value(pyomo_model.inventory[idx])
        if abs(val) > 0.1:  # Can be negative if bug
            inventory_at_mfg.append({
                'product': prod,
                'state': state,
                'date': date,
                'quantity': val
            })

print(f"\nNon-zero inventory at manufacturing: {len(inventory_at_mfg)}")
for i in inventory_at_mfg[:10]:
    print(f"  {i['product'][:30]}, {i['state']}, {i['date']}: {i['quantity']:.1f} units")

# Check for NEGATIVE inventory (indicates bug)
negative_inv = [i for i in inventory_at_mfg if i['quantity'] < -0.01]
if negative_inv:
    print(f"\n⚠️  NEGATIVE INVENTORY FOUND (BUG!):")
    for i in negative_inv[:5]:
        print(f"  {i['product'][:30]}, {i['state']}, {i['date']}: {i['quantity']:.1f} units")

# ============================================================================
# EVIDENCE 7: Material Balance Check
# ============================================================================
print("\n" + "=" * 80)
print("EVIDENCE 7: Material Balance at Manufacturing (First Date)")
print("=" * 80)

# For first date, check: production + arrivals = shipments + inventory
first_date = start

prod_on_first = sum(p['quantity'] for p in production_at_mfg if p['date'] == first_date)
ship_from_first = sum(s['quantity'] for s in shipments_from_mfg if s['delivery_date'] == first_date)
inv_end_first = sum(i['quantity'] for i in inventory_at_mfg if i['date'] == first_date)

print(f"\nFirst date: {first_date}")
print(f"  Production: {prod_on_first:,.0f}")
print(f"  Shipments (delivery on first date): {ship_from_first:,.0f}")
print(f"  End inventory: {inv_end_first:,.0f}")
print(f"\nExpected: Production = Shipments departing + End inventory")
print(f"  (Note: Shipments indexed by DELIVERY date, not departure date!)")

# ============================================================================
# CONCLUSION
# ============================================================================
print("\n" + "=" * 80)
print("ROOT CAUSE HYPOTHESIS")
print("=" * 80)

print(f"""
Based on evidence gathered:

1. Routes have transit times (evidence 1)
2. Manufacturing balance constraint exists (evidence 2)
3. Shipments indexed by DELIVERY date (evidence 3)
4. Shipments from manufacturing: {total_shipments_from_mfg:,.0f} units (evidence 4)
5. Production at manufacturing: {total_production:,.0f} units (evidence 5)
6. Inventory at manufacturing: {len(inventory_at_mfg)} entries (evidence 6)

MATERIAL BALANCE VIOLATION:
  Shipments > Production (by {total_shipments_from_mfg - total_production:,.0f} units)

HYPOTHESIS:
The state balance constraint calculates departure dates incorrectly.
Shipments are indexed by DELIVERY date, but the constraint may not be
properly converting delivery dates to departure dates based on transit time.

Next: Inspect the actual constraint expression to verify hypothesis.
""")
