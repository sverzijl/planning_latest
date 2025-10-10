"""
Check final inventory levels to find where 630K units are "hiding".
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

print("="  * 80)
print("FINAL INVENTORY CHECK")
print("=" * 80)

print("\nLoading data and solving...")
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

initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

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

pyomo_model = model.model
final_date = max(pyomo_model.dates)

print(f"\n{'=' * 80}")
print(f"FINAL INVENTORY BY LOCATION (date: {final_date})")
print("=" * 80)

# Check final ambient inventory at all locations
final_inv_by_loc = {}
for loc in model.inventory_locations:
    loc_total = 0
    for p in pyomo_model.products:
        if (loc, p, final_date) in model.inventory_ambient_index_set:
            qty = value(pyomo_model.inventory_ambient[loc, p, final_date])
            loc_total += qty
    if loc_total != 0:  # Only show non-zero
        final_inv_by_loc[loc] = loc_total

print("\nAmbient Inventory:")
for loc in sorted(final_inv_by_loc.keys()):
    qty = final_inv_by_loc[loc]
    sign = "+" if qty >= 0 else "-"
    print(f"  {loc:20s}: {sign}{abs(qty):>12,.0f} units")

total_final_ambient = sum(final_inv_by_loc.values())
print(f"  {'-' * 40}")
print(f"  {'Total':20s}:  {total_final_ambient:>12,.0f} units")

# Check frozen inventory if it exists
if hasattr(pyomo_model, 'inventory_frozen'):
    print("\nFrozen Inventory:")
    final_frozen_by_loc = {}
    for (loc, p, d) in pyomo_model.inventory_frozen:
        if d == final_date:
            qty = value(pyomo_model.inventory_frozen[loc, p, d])
            if loc not in final_frozen_by_loc:
                final_frozen_by_loc[loc] = 0
            final_frozen_by_loc[loc] += qty

    for loc in sorted(final_frozen_by_loc.keys()):
        qty = final_frozen_by_loc[loc]
        if qty > 0.01:
            print(f"  {loc:20s}:  {qty:>12,.0f} units")

    total_final_frozen = sum(final_frozen_by_loc.values())
    print(f"  {'-' * 40}")
    print(f"  {'Total':20s}:  {total_final_frozen:>12,.0f} units")
else:
    total_final_frozen = 0

print(f"\n{'=' * 80}")
print("MASS BALANCE ANALYSIS")
print("=" * 80)

total_production = sum(value(pyomo_model.production[d, p])
                      for d in pyomo_model.dates
                      for p in pyomo_model.products)
total_initial = sum(initial_inv.values())
total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())

print(f"\nInputs:")
print(f"  Initial inventory: {total_initial:>12,.0f} units")
print(f"  Production:        {total_production:>12,.0f} units")
print(f"  Total supply:      {total_initial + total_production:>12,.0f} units")

print(f"\nOutputs:")
print(f"  Demand satisfied:  {total_demand:>12,.0f} units (shortage = 0)")
print(f"  Final inventory:   {total_final_ambient + total_final_frozen:>12,.0f} units")
print(f"  Total usage:       {total_demand + total_final_ambient + total_final_frozen:>12,.0f} units")

gap = (total_initial + total_production) - (total_demand + total_final_ambient + total_final_frozen)
print(f"\nGap (supply - usage): {gap:>12,.0f} units")

if abs(gap) < 1.0:
    print("✅ Mass balance verified!")
else:
    print(f"⚠️  MASS BALANCE VIOLATION: {abs(gap):,.0f} units unaccounted for!")
    print("\nPossible causes:")
    print("  1. Inventory variables at some locations are unbounded/negative")
    print("  2. Outflow term in inventory balance is incorrect")
    print("  3. Missing constraints on final inventory")

print(f"\n{'=' * 80}")
