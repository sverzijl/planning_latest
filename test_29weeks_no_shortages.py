"""
29-week test with NO SHORTAGES ALLOWED.

Tests whether the model can satisfy all demand when shortages are disabled.
This should match the old model behavior with ~$13M cost.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("29-WEEK TEST WITH NO SHORTAGES ALLOWED")
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

# Use full dataset
forecast_dates = [e.forecast_date for e in forecast.entries]
start_date = min(forecast_dates)
end_date = max(forecast_dates)

product_ids = sorted(set(e.product_id for e in forecast.entries))

# Create initial inventory
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

print(f"Dataset: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")

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
    allow_shortages=False,  # ← NO SHORTAGES ALLOWED
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

print(f"\nModel structure:")
print(f"  Planning dates: {len(model.production_dates)}")
print(f"  Network legs: {len(model.leg_keys)}")

print("\nSolving...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=600,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)
print(f"Status: {result.termination_condition}")
print(f"Success: {result.success}")

if result.success:
    print(f"Objective: ${result.objective_value:,.2f}")
    print(f"Solve Time: {result.solve_time_seconds:.1f}s")

    # Calculate demand
    total_demand = sum(v for k, v in model.demand.items())
    print(f"\nTotal Demand: {total_demand:,.0f} units")

    # Calculate production from Pyomo model
    from pyomo.environ import value
    pyomo_model = model.model

    total_production = 0
    for d in pyomo_model.dates:
        for p in pyomo_model.products:
            qty = value(pyomo_model.production[d, p])
            total_production += qty

    print(f"Total Production: {total_production:,.0f} units")
    print(f"Initial Inventory: {sum(initial_inv.values()):,.0f} units")
    print(f"\nSupply: {total_production + sum(initial_inv.values()):,.0f} units")
    print(f"Demand: {total_demand:,.0f} units")

    # Check shortages (should be 0)
    total_shortages = 0
    for dest in model.destinations:
        for p in pyomo_model.products:
            for d in pyomo_model.dates:
                # Shortages should not exist when allow_shortages=False
                if hasattr(pyomo_model, 'shortage'):
                    qty = value(pyomo_model.shortage[dest, p, d])
                    total_shortages += qty

    print(f"Total Shortages: {total_shortages:,.0f} units")

    if total_shortages < 0.1:
        print(f"\n✅ NO SHORTAGES - All demand satisfied!")
    else:
        print(f"\n⚠️  Unexpected shortages: {total_shortages:,.0f} units")

    print(f"\n{'=' * 80}")
    print(f"COMPARISON WITH EXPECTED")
    print(f"{'=' * 80}")
    print(f"Actual cost:    ${result.objective_value:,.2f}")
    print(f"Expected cost:  ~$13,000,000")

    if 12_000_000 <= result.objective_value <= 14_000_000:
        print(f"✅ Cost is in expected range (~$13M)")
    else:
        print(f"⚠️  Cost differs from expected $13M")

else:
    print(f"\n❌ SOLVE FAILED: {result.termination_condition}")

print("\n" + "=" * 80)
