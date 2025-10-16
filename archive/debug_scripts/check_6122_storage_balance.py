"""
Check 6122_Storage inventory balance specifically.
"""
import sys
from pathlib import Path
from datetime import timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value

print("=" * 80)
print("6122_STORAGE INVENTORY BALANCE CHECK")
print("=" * 80)

print("\n📊 Loading and solving...")
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

print(f"✅ Solved in {result.solve_time_seconds:.1f}s\n")

pyomo_model = model.model
dates_list = sorted(list(pyomo_model.dates))
products_list = sorted(list(pyomo_model.products))

# Check 6122_Storage inventory
print("=" * 80)
print("6122_Storage MASS BALANCE")
print("=" * 80)

# Initial inventory
total_initial = sum(initial_inv.values())
print(f"\nInitial inventory: {total_initial:,.0f} units")
print(f"  ({len(product_ids)} products × 15,000 each)")

# Total production
total_production = sum(value(pyomo_model.production[d, p])
                      for d in dates_list for p in products_list)
print(f"\nTotal production: {total_production:,.0f} units")

# Total truck loads FROM 6122_Storage
total_truck_loads = 0
for truck_idx in pyomo_model.trucks:
    for dest in pyomo_model.truck_destinations:
        for p in products_list:
            for d in dates_list:
                total_truck_loads += value(pyomo_model.truck_load[truck_idx, dest, p, d])

print(f"Total truck loads: {total_truck_loads:,.0f} units")

# Final inventory at 6122_Storage
final_date = dates_list[-1]
final_inv = 0
if ('6122_Storage', products_list[0], final_date) in model.inventory_ambient_index_set:
    final_inv = sum(
        value(pyomo_model.inventory_ambient['6122_Storage', p, final_date])
        for p in products_list
        if ('6122_Storage', p, final_date) in model.inventory_ambient_index_set
    )

print(f"Final inventory: {final_inv:,.0f} units")

# Balance check
total_supply = total_initial + total_production
total_usage = total_truck_loads + final_inv

print(f"\n{'=' * 80}")
print("BALANCE CHECK")
print("=" * 80)
print(f"\nSupply = Initial + Production:")
print(f"       = {total_initial:,.0f} + {total_production:,.0f}")
print(f"       = {total_supply:,.0f} units")

print(f"\nUsage = Truck Loads + Final Inventory:")
print(f"      = {total_truck_loads:,.0f} + {final_inv:,.0f}")
print(f"      = {total_usage:,.0f} units")

gap = total_supply - total_usage
print(f"\nGap = Supply - Usage")
print(f"    = {total_supply:,.0f} - {total_usage:,.0f}")
print(f"    = {gap:,.0f} units")

if abs(gap) < 1.0:
    print(f"\n✅ BALANCE VERIFIED: No gap at 6122_Storage")
else:
    print(f"\n⚠️  GAP FOUND: {gap:,.0f} units")
    if gap < 0:
        print(f"   Shipping out {-gap:,.0f} units MORE than available!")
        print(f"   This violates inventory conservation!")
    else:
        print(f"   Have {gap:,.0f} units surplus - model is conservative")

# Check total demand vs total truck loads
total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())
print(f"\n{'=' * 80}")
print("DEMAND VS TRUCK LOADS")
print("=" * 80)
print(f"\nTotal demand at destinations: {total_demand:,.0f} units")
print(f"Total truck loads from 6122:  {total_truck_loads:,.0f} units")
print(f"Difference:                   {total_demand - total_truck_loads:,.0f} units")

if total_truck_loads > total_supply:
    print(f"\n🚨 PROBLEM IDENTIFIED:")
    print(f"   Truck loads ({total_truck_loads:,.0f}) exceed available supply ({total_supply:,.0f})")
    print(f"   Excess: {total_truck_loads - total_supply:,.0f} units")
    print(f"   This should be impossible with correct constraints!")

# Check for negative inventory
print(f"\n{'=' * 80}")
print("CHECKING FOR NEGATIVE INVENTORY")
print("=" * 80)

negative_count = 0
min_inv = 0

for d in dates_list:
    for p in products_list:
        if ('6122_Storage', p, d) in model.inventory_ambient_index_set:
            inv = value(pyomo_model.inventory_ambient['6122_Storage', p, d])
            if inv < -0.01:
                negative_count += 1
                min_inv = min(min_inv, inv)
                if negative_count <= 10:  # Show first 10
                    print(f"  {d.strftime('%Y-%m-%d')} Product {p}: {inv:,.2f}")

if negative_count > 0:
    print(f"\n🚨 FOUND {negative_count} instances of negative inventory!")
    print(f"   Minimum value: {min_inv:,.2f}")
    print(f"   This explains the phantom supply!")
else:
    print(f"\n✅ No negative inventory found at 6122_Storage")

print(f"\n{'=' * 80}")
