"""
Trace actual unit flow through the network.

This script separates:
1. Units produced at 6122
2. Units consumed at each location (from demand)
3. Units flowing through hubs vs consumed at hubs
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

print("=" * 80)
print("UNIT FLOW TRACE")
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
    allow_shortages=True,
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
print("PRODUCTION")
print("=" * 80)

total_production = sum(value(pyomo_model.production[d, p]) for d in pyomo_model.dates for p in pyomo_model.products)
total_initial = sum(initial_inv.values())

print(f"Total Production:      {total_production:>12,.0f} units")
print(f"Initial Inventory:     {total_initial:>12,.0f} units")
print(f"Total Supply:          {(total_production + total_initial):>12,.0f} units")

print(f"\n{'=' * 80}")
print("DEMAND BY LOCATION")
print("=" * 80)

demand_by_loc = {}
for (dest, prod, date), qty in model.demand.items():
    if dest not in demand_by_loc:
        demand_by_loc[dest] = 0
    demand_by_loc[dest] += qty

print(f"\n{'Location':<10} {'Demand (units)':>15} {'Type':>15}")
print("-" * 45)

# Identify hubs (locations that have outgoing legs)
hub_locations = set()
for (origin, dest) in model.leg_keys:
    if origin != '6122' and origin != 'Lineage':  # Not manufacturing or frozen buffer
        hub_locations.add(origin)

for loc in sorted(demand_by_loc.keys(), key=lambda x: demand_by_loc[x], reverse=True):
    qty = demand_by_loc[loc]
    loc_type = "HUB + Consumer" if loc in hub_locations else "Final Consumer"
    print(f"{loc:<10} {qty:>15,.0f} {loc_type:>15}")

total_demand = sum(demand_by_loc.values())
print("-" * 45)
print(f"{'TOTAL':<10} {total_demand:>15,.0f}")

print(f"\n{'=' * 80}")
print("INFLOWS BY LOCATION")
print("=" * 80)

inflows = {}
for (origin, dest) in model.leg_keys:
    dest_total = 0
    for p in pyomo_model.products:
        for d in pyomo_model.dates:
            qty = value(pyomo_model.shipment_leg[(origin, dest), p, d])
            dest_total += qty

    if dest_total > 0:
        if dest not in inflows:
            inflows[dest] = {}
        inflows[dest][origin] = dest_total

print(f"\n{'Location':<10} {'Total Inflow':>15} {'Sources':>30}")
print("-" * 60)

for dest in sorted(inflows.keys()):
    total_in = sum(inflows[dest].values())
    sources = ", ".join([f"{o}({v:,.0f})" for o, v in sorted(inflows[dest].items(), key=lambda x: x[1], reverse=True)])
    print(f"{dest:<10} {total_in:>15,.0f}   {sources}")

print(f"\n{'=' * 80}")
print("OUTFLOWS BY LOCATION")
print("=" * 80)

outflows = {}
for (origin, dest) in model.leg_keys:
    origin_total = 0
    for p in pyomo_model.products:
        for d in pyomo_model.dates:
            qty = value(pyomo_model.shipment_leg[(origin, dest), p, d])
            origin_total += qty

    if origin_total > 0:
        if origin not in outflows:
            outflows[origin] = {}
        outflows[origin][dest] = origin_total

print(f"\n{'Location':<10} {'Total Outflow':>15} {'Destinations':>30}")
print("-" * 60)

for origin in sorted(outflows.keys()):
    total_out = sum(outflows[origin].values())
    dests = ", ".join([f"{d}({v:,.0f})" for d, v in sorted(outflows[origin].items(), key=lambda x: x[1], reverse=True)])
    print(f"{origin:<10} {total_out:>15,.0f}   {dests}")

print(f"\n{'=' * 80}")
print("FLOW BALANCE AT HUBS")
print("=" * 80)

print(f"\n{'Hub':<10} {'Demand':>12} {'Inflow':>12} {'Outflow':>12} {'Net Storage':>12}")
print("-" * 65)

for hub in sorted(hub_locations):
    hub_demand = demand_by_loc.get(hub, 0)
    hub_inflow = sum(inflows.get(hub, {}).values())
    hub_outflow = sum(outflows.get(hub, {}).values())
    net_storage = hub_inflow - hub_demand - hub_outflow

    print(f"{hub:<10} {hub_demand:>12,.0f} {hub_inflow:>12,.0f} {hub_outflow:>12,.0f} {net_storage:>12,.0f}")

print(f"\n{'=' * 80}")
print("KEY INSIGHTS")
print("=" * 80)

# Calculate units that flow through multiple legs
total_leg_flow = 0
for (origin, dest) in model.leg_keys:
    for p in pyomo_model.products:
        for d in pyomo_model.dates:
            qty = value(pyomo_model.shipment_leg[(origin, dest), p, d])
            total_leg_flow += qty

# Calculate final deliveries (inflows to non-hub locations)
final_deliveries = 0
for dest in inflows.keys():
    if dest not in hub_locations:
        final_deliveries += sum(inflows[dest].values())

print(f"\nTotal Supply:           {(total_production + total_initial):>12,.0f} units")
print(f"Total Demand:           {total_demand:>12,.0f} units")
print(f"")
print(f"Total Leg-Flow:         {total_leg_flow:>12,.0f} units (counts multi-leg routing)")
print(f"Final Deliveries:       {final_deliveries:>12,.0f} units (to non-hub locations)")
print(f"Hub Consumption:        {sum(demand_by_loc.get(h, 0) for h in hub_locations):>12,.0f} units (consumed at hubs)")
print(f"")
print(f"Expected Deliveries:    {total_demand:>12,.0f} units (all demand)")

# The question: Does supply match the actual deliveries?
print(f"\n{'=' * 80}")
print("CRITICAL QUESTION")
print("=" * 80)

print(f"\nWith supply of {(total_production + total_initial):,.0f} units:")
print(f"  Final deliveries (non-hub):    {final_deliveries:,.0f}")
print(f"  Hub consumption:                {sum(demand_by_loc.get(h, 0) for h in hub_locations):,.0f}")
print(f"  TOTAL actual deliveries:        {(final_deliveries + sum(demand_by_loc.get(h, 0) for h in hub_locations)):,.0f}")
print(f"")
print(f"  Total demand to satisfy:        {total_demand:,.0f}")
print(f"")

actual_deliveries = final_deliveries + sum(demand_by_loc.get(h, 0) for h in hub_locations)
if abs(actual_deliveries - total_demand) < 1:
    print(f"✅ All demand satisfied!")
    if actual_deliveries <= total_production + total_initial:
        print(f"✅ Supply is sufficient: {(total_production + total_initial):,.0f} >= {actual_deliveries:,.0f}")
    else:
        print(f"❌ IMPOSSIBLE: Deliveries ({actual_deliveries:,.0f}) > Supply ({total_production + total_initial:,.0f})")
        print(f"   This indicates double-counting or an error in flow calculations")
else:
    shortage = total_demand - actual_deliveries
    print(f"⚠️  Shortage: {shortage:,.0f} units not delivered")

print(f"\n{'=' * 80}")
