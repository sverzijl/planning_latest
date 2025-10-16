"""
Verify mass balance after adding outflow term.

Proper mass balance accounting:
Supply = Production + Initial Inventory
Usage = Direct shipments + Hub throughput + Final inventory
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
print("MASS BALANCE VERIFICATION (AFTER FIX)")
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
print("SUPPLY ACCOUNTING")
print("=" * 80)

total_production = sum(value(pyomo_model.production[d, p]) for d in pyomo_model.dates for p in pyomo_model.products)
total_initial = sum(initial_inv.values())

print(f"\nProduction:        {total_production:>12,.0f} units")
print(f"Initial Inventory: {total_initial:>12,.0f} units")
print(f"{'-' * 50}")
print(f"Total Supply:      {(total_production + total_initial):>12,.0f} units")

print(f"\n{'=' * 80}")
print("USAGE ACCOUNTING")
print("=" * 80)

# Calculate demand satisfied
total_demand = sum(v for k, v in model.demand.items())
total_shortages = 0
for idx in pyomo_model.shortage:
    total_shortages += value(pyomo_model.shortage[idx])

demand_satisfied = total_demand - total_shortages

print(f"\nTotal Demand:           {total_demand:>12,.0f} units")
print(f"Shortages:              {total_shortages:>12,.0f} units")
print(f"Demand Satisfied:       {demand_satisfied:>12,.0f} units")

# Calculate final inventory (all locations)
final_date = max(pyomo_model.dates)
total_final_inventory = 0

for loc in model.inventory_locations:
    for p in pyomo_model.products:
        # Ambient inventory
        if hasattr(pyomo_model, 'inventory_ambient') and (loc, p, final_date) in pyomo_model.inventory_ambient:
            qty = value(pyomo_model.inventory_ambient[loc, p, final_date])
            total_final_inventory += qty

        # Frozen inventory
        if hasattr(pyomo_model, 'inventory_frozen') and (loc, p, final_date) in pyomo_model.inventory_frozen:
            qty = value(pyomo_model.inventory_frozen[loc, p, final_date])
            total_final_inventory += qty

print(f"Final Inventory (all): {total_final_inventory:>12,.0f} units")
print(f"{'-' * 50}")
print(f"Total Usage:           {(demand_satisfied + total_final_inventory):>12,.0f} units")

print(f"\n{'=' * 80}")
print("MASS BALANCE")
print("=" * 80)

supply = total_production + total_initial
usage = demand_satisfied + total_final_inventory

print(f"\nSupply: {supply:,.0f} units")
print(f"Usage:  {usage:,.0f} units")
print(f"Diff:   {abs(supply - usage):,.0f} units")

if abs(supply - usage) < 1.0:
    print(f"\n✅ MASS BALANCE VERIFIED!")
    print(f"   Supply = Demand Satisfied + Final Inventory")
else:
    print(f"\n⚠️  Mass balance error: {abs(supply - usage):,.0f} units")

print(f"\n{'=' * 80}")
print("HUB FLOW VERIFICATION")
print("=" * 80)

# Check hub inventories throughout planning horizon
hubs = {'6104', '6125'}

for hub in sorted(hubs):
    print(f"\n{hub}:")

    # Get hub demand
    hub_demand = sum(v for (loc, p, d), v in model.demand.items() if loc == hub)
    print(f"  Total demand at hub: {hub_demand:,.0f} units")

    # Get total inflows
    hub_inflow = 0
    for (origin, dest) in model.leg_keys:
        if dest == hub:
            for p in pyomo_model.products:
                for d in pyomo_model.dates:
                    hub_inflow += value(pyomo_model.shipment_leg[(origin, dest), p, d])

    print(f"  Total inflows:       {hub_inflow:,.0f} units")

    # Get total outflows
    hub_outflow = 0
    for (origin, dest) in model.leg_keys:
        if origin == hub:
            for p in pyomo_model.products:
                for d in pyomo_model.dates:
                    hub_outflow += value(pyomo_model.shipment_leg[(origin, dest), p, d])

    print(f"  Total outflows:      {hub_outflow:,.0f} units")

    # Check inventory
    hub_final_inv = 0
    for p in pyomo_model.products:
        if (hub, p, final_date) in pyomo_model.inventory_ambient:
            hub_final_inv += value(pyomo_model.inventory_ambient[hub, p, final_date])

    print(f"  Final inventory:     {hub_final_inv:,.0f} units")

    # Check balance
    # Inflow should equal: Demand + Outflow + Final Inventory
    expected_inflow = hub_demand + hub_outflow + hub_final_inv
    diff = abs(hub_inflow - expected_inflow)

    print(f"  Balance check:")
    print(f"    Inflow = Demand + Outflow + Final Inv?")
    print(f"    {hub_inflow:,.0f} = {hub_demand:,.0f} + {hub_outflow:,.0f} + {hub_final_inv:,.0f}")
    print(f"    {hub_inflow:,.0f} vs {expected_inflow:,.0f} (diff: {diff:,.0f})")

    if diff < 1.0:
        print(f"    ✅ Hub balance correct!")
    else:
        print(f"    ⚠️  Hub balance error!")

print(f"\n{'=' * 80}")
print("SUMMARY")
print("=" * 80)

print(f"\nObjective: ${result.objective_value:,.2f}")
print(f"Production: {total_production:,.0f} units")
print(f"Demand satisfied: {demand_satisfied:,.0f} / {total_demand:,.0f} ({100*demand_satisfied/total_demand:.1f}%)")

if total_shortages > 0:
    print(f"Shortages: {total_shortages:,.0f} units ({100*total_shortages/total_demand:.1f}%)")
else:
    print(f"✅ No shortages - all demand satisfied")

if abs(supply - usage) < 1.0:
    print(f"✅ Mass balance verified")
else:
    print(f"⚠️  Mass balance error")

print(f"\n{'=' * 80}")
