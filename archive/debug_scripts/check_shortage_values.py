"""
Check actual shortage variable values in the solved model.
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
print("SHORTAGE VARIABLE CHECK")
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
print("SHORTAGE ANALYSIS")
print("=" * 80)

# Check if shortage variable exists
if hasattr(pyomo_model, 'shortage'):
    print(f"\n✅ Shortage variable EXISTS")
    print(f"   Number of shortage variables: {len(pyomo_model.shortage)}")

    # Calculate total shortages
    total_shortage = 0
    nonzero_shortages = []

    for (loc, prod, d) in pyomo_model.shortage:
        qty = value(pyomo_model.shortage[loc, prod, d])
        total_shortage += qty
        if qty > 0.01:  # Ignore tiny numerical errors
            nonzero_shortages.append((loc, prod, d, qty))

    print(f"\n   Total shortage quantity: {total_shortage:,.2f} units")
    print(f"   Nonzero shortages: {len(nonzero_shortages)}")

    if nonzero_shortages:
        print(f"\n   Top 10 shortages:")
        for loc, prod, d, qty in sorted(nonzero_shortages, key=lambda x: x[3], reverse=True)[:10]:
            print(f"     {loc}, {prod}, {d}: {qty:,.0f} units")
    else:
        print(f"\n   ⚠️  ALL SHORTAGES ARE ZERO!")
        print(f"      This is unexpected given the 630K unit supply deficit")

else:
    print(f"\n❌ Shortage variable DOES NOT EXIST")
    print(f"   Model was likely built with allow_shortages=False")

print(f"\n{'=' * 80}")
print("SUMMARY")
print("=" * 80)

# Calculate totals
total_production = sum(value(pyomo_model.production[d, p])
                      for d in pyomo_model.dates
                      for p in pyomo_model.products)
total_initial = sum(initial_inv.values())
total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())

print(f"\nProduction: {total_production:,.0f} units")
print(f"Initial inventory: {total_initial:,.0f} units")
print(f"Total supply: {total_production + total_initial:,.0f} units")
print(f"\nTotal demand: {total_demand:,.0f} units")

if hasattr(pyomo_model, 'shortage'):
    print(f"Total shortage: {total_shortage:,.0f} units")
    print(f"Satisfied demand: {total_demand - total_shortage:,.0f} units")

    expected_supply = total_demand - total_shortage
    actual_supply = total_production + total_initial

    print(f"\nBalance check:")
    print(f"  Expected supply (demand - shortage): {expected_supply:,.0f}")
    print(f"  Actual supply (production + initial): {actual_supply:,.0f}")
    print(f"  Difference: {abs(expected_supply - actual_supply):,.0f}")

    if abs(expected_supply - actual_supply) < 1.0:
        print(f"  ✅ Supply equals satisfied demand!")
    else:
        print(f"  ⚠️  Supply mismatch!")

print(f"\n{'=' * 80}")
