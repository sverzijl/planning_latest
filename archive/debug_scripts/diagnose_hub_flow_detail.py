"""
Detailed day-by-day hub flow diagnostic to identify the 630K unit gap.

This script will:
1. Trace Hub 6104 inventory day-by-day showing all components
2. Verify outflow indexing is correct
3. Check initial inventory at hubs
4. Verify constraint equation arithmetic
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value
from datetime import timedelta

print("=" * 80)
print("DETAILED HUB FLOW DIAGNOSTIC")
print("=" * 80)

print("\nLoading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

product_ids = sorted(set(e.product_id for e in forecast.entries))

# Create initial inventory
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

print("\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=5,
    allow_shortages=False,
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

print("\nSolving...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=600,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

if not result.success:
    print("\n❌ Solve failed")
    sys.exit(1)

pyomo_model = model.model

print(f"\n{'=' * 80}")
print("INITIAL INVENTORY CHECK")
print("=" * 80)

# Check if hubs have initial inventory
hub = '6104'
print(f"\nInitial inventory at {hub}:")
has_initial = False
for key, val in model.initial_inventory.items():
    if key[0] == hub:
        print(f"  {key}: {val}")
        has_initial = True
if not has_initial:
    print(f"  No initial inventory at {hub}")

print(f"\n{'=' * 80}")
print("INVENTORY INDEX CHECK")
print("=" * 80)

# Check if hub is in inventory index
hub = '6104'
first_product = sorted(pyomo_model.products)[0]
dates = sorted(pyomo_model.dates)

print(f"\nHub {hub} ambient inventory index entries for product {first_product}:")
count = 0
for (loc, prod, date) in model.inventory_ambient_index_set:
    if loc == hub and prod == first_product:
        count += 1
print(f"  Total entries: {count} (expected: {len(dates)})")

print(f"\n{'=' * 80}")
print(f"DAY-BY-DAY FLOW TRACE: HUB {hub}, PRODUCT {first_product}")
print("=" * 80)

# Trace first 10 days
for i, date in enumerate(dates[:10]):
    print(f"\n--- Date {i+1}: {date} ---")

    # Previous inventory
    prev_date = model.date_previous.get(date)
    if prev_date is None:
        prev_inv = model.initial_inventory.get((hub, first_product, 'ambient'),
                   model.initial_inventory.get((hub, first_product), 0))
        print(f"  Previous inventory (initial): {prev_inv:>10.2f}")
    else:
        if (hub, first_product, prev_date) in model.inventory_ambient_index_set:
            prev_inv = value(pyomo_model.inventory_ambient[hub, first_product, prev_date])
            print(f"  Previous inventory ({prev_date}): {prev_inv:>10.2f}")
        else:
            prev_inv = 0
            print(f"  Previous inventory ({prev_date}): {prev_inv:>10.2f} (NOT IN INDEX)")

    # Arrivals (shipments that arrive on this date)
    arrivals = 0
    legs_to_hub = model.legs_to_location.get(hub, [])
    for (origin, dest) in legs_to_hub:
        if model.leg_arrival_state.get((origin, dest)) == 'ambient':
            # Shipment arrives on date
            if (origin, dest, first_product, date) in pyomo_model.shipment_leg:
                qty = value(pyomo_model.shipment_leg[(origin, dest), first_product, date])
                if qty > 0.01:
                    print(f"  Arrival from {origin}: {qty:>10.2f}")
                arrivals += qty
    print(f"  Total arrivals: {arrivals:>10.2f}")

    # Demand
    demand_qty = model.demand.get((hub, first_product, date), 0)
    print(f"  Demand: {demand_qty:>10.2f}")

    # Shortages
    if (hub, first_product, date) in pyomo_model.shortage:
        shortage_qty = value(pyomo_model.shortage[hub, first_product, date])
    else:
        shortage_qty = 0
    print(f"  Shortage: {shortage_qty:>10.2f}")

    # Outflows (shipments that DEPART on this date)
    # These are indexed by their ARRIVAL date, so we need to find future arrivals
    outflows = 0
    legs_from_hub = model.legs_from_location.get(hub, [])
    print(f"  Outflows:")
    for (origin, dest) in legs_from_hub:
        if model.leg_arrival_state.get((origin, dest)) == 'ambient':
            transit_days = model.leg_transit_days[(origin, dest)]
            delivery_date = date + timedelta(days=transit_days)
            if delivery_date in pyomo_model.dates:
                if (origin, dest, first_product, delivery_date) in pyomo_model.shipment_leg:
                    qty = value(pyomo_model.shipment_leg[(origin, dest), first_product, delivery_date])
                    if qty > 0.01:
                        print(f"    → {dest} (delivers {delivery_date}): {qty:>10.2f}")
                    outflows += qty
    print(f"  Total outflows: {outflows:>10.2f}")

    # Current inventory
    if (hub, first_product, date) in model.inventory_ambient_index_set:
        actual_inv = value(pyomo_model.inventory_ambient[hub, first_product, date])
        print(f"  Actual inventory: {actual_inv:>10.2f}")
    else:
        print(f"  Actual inventory: NOT IN INDEX")
        actual_inv = None

    # Calculated inventory
    calc_inv = prev_inv + arrivals - demand_qty - shortage_qty - outflows
    print(f"  Calculated inventory: {calc_inv:>10.2f}")

    # Check balance
    if actual_inv is not None:
        diff = abs(actual_inv - calc_inv)
        if diff < 0.01:
            print(f"  ✅ Balance OK (diff: {diff:.4f})")
        else:
            print(f"  ⚠️  IMBALANCE! (diff: {diff:.2f})")

print(f"\n{'=' * 80}")
print("TOTAL HUB FLOW SUMMARY")
print("=" * 80)

# Calculate total flows for hub
total_arrivals = 0
total_demand = 0
total_outflows = 0

for date in pyomo_model.dates:
    # Arrivals
    legs_to_hub = model.legs_to_location.get(hub, [])
    for (origin, dest) in legs_to_hub:
        if model.leg_arrival_state.get((origin, dest)) == 'ambient':
            for p in pyomo_model.products:
                if (origin, dest, p, date) in pyomo_model.shipment_leg:
                    total_arrivals += value(pyomo_model.shipment_leg[(origin, dest), p, date])

    # Demand
    for p in pyomo_model.products:
        total_demand += model.demand.get((hub, p, date), 0)

    # Outflows
    legs_from_hub = model.legs_from_location.get(hub, [])
    for (origin, dest) in legs_from_hub:
        if model.leg_arrival_state.get((origin, dest)) == 'ambient':
            transit_days = model.leg_transit_days[(origin, dest)]
            delivery_date = date + timedelta(days=transit_days)
            if delivery_date in pyomo_model.dates:
                for p in pyomo_model.products:
                    if (origin, dest, p, delivery_date) in pyomo_model.shipment_leg:
                        total_outflows += value(pyomo_model.shipment_leg[(origin, dest), p, delivery_date])

# Final inventory
final_date = max(pyomo_model.dates)
final_inv = 0
for p in pyomo_model.products:
    if (hub, p, final_date) in model.inventory_ambient_index_set:
        final_inv += value(pyomo_model.inventory_ambient[hub, p, final_date])

# Initial inventory
initial_hub_inv = 0
for key, val in model.initial_inventory.items():
    if key[0] == hub:
        initial_hub_inv += val

print(f"\n{hub} Total Flow:")
print(f"  Initial inventory: {initial_hub_inv:>12,.0f}")
print(f"  Total arrivals:    {total_arrivals:>12,.0f}")
print(f"  Total demand:      {total_demand:>12,.0f}")
print(f"  Total outflows:    {total_outflows:>12,.0f}")
print(f"  Final inventory:   {final_inv:>12,.0f}")

# Check balance: initial + arrivals = demand + outflows + final
supply = initial_hub_inv + total_arrivals
usage = total_demand + total_outflows + final_inv

print(f"\n  Supply (initial + arrivals): {supply:>12,.0f}")
print(f"  Usage (demand + outflows + final): {usage:>12,.0f}")
print(f"  Difference: {abs(supply - usage):>12,.0f}")

if abs(supply - usage) < 1.0:
    print(f"\n  ✅ Hub flow balance verified!")
else:
    print(f"\n  ⚠️  Hub flow imbalance: {abs(supply - usage):,.0f} units")

print(f"\n{'=' * 80}")
