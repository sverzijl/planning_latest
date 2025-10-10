"""
Test model with allow_shortages=FALSE to force meeting all demand.
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
print("TEST: allow_shortages=FALSE")
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

initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

print("\nBuilding model with allow_shortages=FALSE...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=5,
    allow_shortages=False,  # FORCE meeting all demand
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

print("\nSolving (10 minute timeout)...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=600,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=True  # Show solver output
)

print(f"\n{'=' * 80}")
print("RESULT")
print("=" * 80)

if result.success:
    print(f"\n✅ SOLVED in {result.solve_time_seconds:.1f}s")
    print(f"   Objective: ${result.objective_value:,.2f}")

    pyomo_model = model.model

    total_production = sum(value(pyomo_model.production[d, p])
                          for d in pyomo_model.dates
                          for p in pyomo_model.products)
    total_initial = sum(initial_inv.values())
    total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())

    print(f"\n  Production: {total_production:,.0f} units")
    print(f"  Initial inventory: {total_initial:,.0f} units")
    print(f"  Total supply: {total_production + total_initial:,.0f} units")
    print(f"  Total demand: {total_demand:,.0f} units")
    print(f"  Deficit: {total_demand - (total_production + total_initial):,.0f} units")

    if abs(total_production - 2_400_000) < 100_000:
        print(f"\n  ✅ Production matches expected ~2.4M units!")
    else:
        print(f"\n  ⚠️  Production {total_production:,.0f} != expected ~2,400,000")

else:
    print(f"\n❌ SOLVE FAILED")
    print(f"   Status: {result.status}")
    print(f"   Termination: {result.termination_condition}")
    print(f"   Message: {result.message}")

    if "infeasible" in str(result.termination_condition).lower():
        print(f"\n   Model is INFEASIBLE - cannot meet all demand with given constraints")
        print(f"   This suggests there IS a capacity or routing constraint preventing")
        print(f"   the model from producing 2.4M units.")

print(f"\n{'=' * 80}")
