"""
Diagnose mass balance violation in integrated model.

This script traces through inventory balance constraints to identify
where the mass balance is violated.
"""
import sys
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value

print("=" * 80)
print("MASS BALANCE DIAGNOSTIC")
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

print("\nBuilding model with allow_shortages=True...")
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

print(f"✅ Solved in {result.solve_time_seconds:.1f}s")
print(f"   Objective: ${result.objective_value:,.2f}")

pyomo_model = model.model

print(f"\n{'=' * 80}")
print("AGGREGATE MASS BALANCE")
print("=" * 80)

# Calculate aggregate quantities
total_production = sum(value(pyomo_model.production[d, p])
                      for d in pyomo_model.dates
                      for p in pyomo_model.products)
total_initial = sum(initial_inv.values())
total_supply = total_production + total_initial

total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())

total_shortage = 0
if hasattr(pyomo_model, 'shortage'):
    total_shortage = sum(value(pyomo_model.shortage[loc, prod, d])
                        for loc, prod, d in pyomo_model.shortage)

# Calculate final inventory (sum across all locations and states)
total_final_inventory = 0

# Ambient inventory
if hasattr(pyomo_model, 'inventory_ambient'):
    for loc, prod, d in pyomo_model.inventory_ambient:
        total_final_inventory += value(pyomo_model.inventory_ambient[loc, prod, d])

# Frozen inventory
if hasattr(pyomo_model, 'inventory_frozen'):
    for loc, prod, d in pyomo_model.inventory_frozen:
        total_final_inventory += value(pyomo_model.inventory_frozen[loc, prod, d])

print(f"\nSupply side:")
print(f"  Initial inventory:     {total_initial:>12,.0f} units")
print(f"  Production:            {total_production:>12,.0f} units")
print(f"  Total supply:          {total_supply:>12,.0f} units")

print(f"\nDemand side:")
print(f"  Total demand:          {total_demand:>12,.0f} units")
print(f"  Shortage:              {total_shortage:>12,.0f} units")
print(f"  Satisfied demand:      {total_demand - total_shortage:>12,.0f} units")

print(f"\nInventory:")
print(f"  Final inventory:       {total_final_inventory:>12,.0f} units")

print(f"\nMass balance equation:")
print(f"  Supply = Demand - Shortage + Final Inventory")
print(f"  {total_supply:,.0f} = {total_demand:,.0f} - {total_shortage:,.0f} + {total_final_inventory:,.0f}")
print(f"  {total_supply:,.0f} = {total_demand - total_shortage + total_final_inventory:,.0f}")

balance_error = total_supply - (total_demand - total_shortage + total_final_inventory)
print(f"\nBalance error: {balance_error:,.0f} units")

if abs(balance_error) < 1.0:
    print("✅ Mass balance is correct!")
else:
    print(f"❌ Mass balance violation: {abs(balance_error):,.0f} units")

print(f"\n{'=' * 80}")
print("DETAILED INVENTORY TRACE")
print("=" * 80)

# Trace through a few representative locations to understand the constraint behavior
trace_locations = ['6122_Storage', '6104', '6110', '6130']

for loc in trace_locations:
    if loc not in [l.location_id for l in locations]:
        continue

    print(f"\n{'=' * 80}")
    print(f"LOCATION: {loc}")
    print(f"{'=' * 80}")

    # For one product only (to keep output manageable)
    prod = product_ids[0]

    # Get first few dates
    dates_list = sorted(pyomo_model.dates)[:7]

    for date in dates_list:
        print(f"\n  Date: {date}")

        # Check if this location has inventory variables for this date
        has_ambient = (loc, prod, date) in pyomo_model.inventory_ambient
        has_frozen = hasattr(pyomo_model, 'inventory_frozen') and (loc, prod, date) in pyomo_model.inventory_frozen

        if has_ambient:
            inv_ambient = value(pyomo_model.inventory_ambient[loc, prod, date])
            print(f"    Ambient inventory: {inv_ambient:>10,.1f}")

        if has_frozen:
            inv_frozen = value(pyomo_model.inventory_frozen[loc, prod, date])
            print(f"    Frozen inventory:  {inv_frozen:>10,.1f}")

        # Check demand
        demand_qty = model.demand.get((loc, prod, date), 0.0)
        if demand_qty > 0:
            print(f"    Demand:            {demand_qty:>10,.1f}")

            if hasattr(pyomo_model, 'shortage') and (loc, prod, date) in pyomo_model.shortage:
                shortage_qty = value(pyomo_model.shortage[loc, prod, date])
                print(f"    Shortage:          {shortage_qty:>10,.1f}")
                print(f"    Satisfied:         {demand_qty - shortage_qty:>10,.1f}")

print(f"\n{'=' * 80}")
print("INVESTIGATING THE FORMULATION")
print("=" * 80)

print(f"""
Current inventory balance equation (line 1388-1390):
    inventory[t] = prev + arrivals - demand + shortage - outflows

This formulation treats shortage as "unsatisfied demand", meaning:
    - actual_consumption = demand - shortage
    - inventory[t] = prev + arrivals - actual_consumption - outflows
    - inventory[t] = prev + arrivals - (demand - shortage) - outflows
    - inventory[t] = prev + arrivals - demand + shortage - outflows

PROBLEM ANALYSIS:
The formulation is mathematically correct IF shortage represents "unsatisfied demand".

However, there's NO EXPLICIT constraint linking arrivals to demand satisfaction.
The model relies ONLY on:
  1. inventory >= 0  (NonNegativeReals)
  2. shortage >= 0 and shortage <= demand
  3. Minimize shortage_penalty * shortage

If the shortage penalty is too low, OR if there's a cheaper way to meet
the objective, the solver may:
  - Set shortage = 0 (good for objective)
  - Allow inventory balance to have (arrivals - demand) < 0
  - But this would violate inventory >= 0

HYPOTHESIS:
There must be inventory appearing from somewhere that we're not accounting for.
Possible sources:
  1. Initial inventory at locations other than 6122_Storage
  2. Inventory carried forward from previous dates incorrectly
  3. Shipments being counted twice (both as arrivals and in initial inventory)
  4. A bug in how we calculate total final inventory
""")

print(f"\n{'=' * 80}")
print("CHECKING FOR HIDDEN INVENTORY")
print("=" * 80)

# Check initial inventory across all locations
print(f"\nInitial inventory breakdown:")
for (loc, prod, state), qty in initial_inv.items():
    print(f"  {loc:20s} {prod:10s} {state:10s}: {qty:>10,.0f}")

# Check if there are inventory variables for locations we didn't provide initial inventory
print(f"\nLocations with inventory variables:")
locations_with_inv = set()
if hasattr(pyomo_model, 'inventory_ambient'):
    for loc, prod, d in pyomo_model.inventory_ambient:
        locations_with_inv.add(loc)
if hasattr(pyomo_model, 'inventory_frozen'):
    for loc, prod, d in pyomo_model.inventory_frozen:
        locations_with_inv.add(loc)

for loc in sorted(locations_with_inv):
    # Check if we provided initial inventory for this location
    has_initial = any(loc == l for l, p, s in initial_inv.keys())
    marker = "✓" if has_initial else "⚠️ NO INITIAL"
    print(f"  {marker} {loc}")

print(f"\n{'=' * 80}")
print("CHECKING FIRST DATE INVENTORY")
print("=" * 80)

# For the first date, inventory should equal initial inventory if no arrivals or demand
first_date = sorted(pyomo_model.dates)[0]
print(f"\nFirst date: {first_date}")

for loc in sorted(locations_with_inv):
    for prod in product_ids:
        # Check ambient
        if (loc, prod, first_date) in pyomo_model.inventory_ambient:
            inv = value(pyomo_model.inventory_ambient[loc, prod, first_date])
            initial = initial_inv.get((loc, prod, 'ambient'), 0.0)
            if abs(inv - initial) > 0.1:
                print(f"\n  {loc} {prod} ambient:")
                print(f"    First date inventory: {inv:,.1f}")
                print(f"    Expected initial:     {initial:,.1f}")
                print(f"    Difference:           {inv - initial:,.1f}")
