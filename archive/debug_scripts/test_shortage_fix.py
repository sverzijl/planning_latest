"""
Test if the shortage sign fix resolves the 630K unit gap.

This script will:
1. Run the model with the corrected shortage sign
2. Verify production levels (~2.4M expected)
3. Verify total cost (~$13M expected)
4. Check shortage reporting
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
print("SHORTAGE FIX VERIFICATION")
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
    print(f"   Status: {result.status}")
    print(f"   Message: {result.message}")
    sys.exit(1)

pyomo_model = model.model

print(f"\n{'=' * 80}")
print("SOLUTION SUMMARY")
print("=" * 80)

# Calculate production
total_production = sum(value(pyomo_model.production[d, p])
                      for d in pyomo_model.dates
                      for p in pyomo_model.products)

# Calculate initial inventory
total_initial = sum(v for v in model.initial_inventory.values())

# Calculate demand
total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())

# Calculate shortages
total_shortages = 0
if hasattr(pyomo_model, 'shortage'):
    for (loc, prod, d) in pyomo_model.shortage:
        total_shortages += value(pyomo_model.shortage[loc, prod, d])

# Calculate final inventory
final_date = max(pyomo_model.dates)
total_final_inv = 0
for loc in model.inventory_locations:
    for p in pyomo_model.products:
        if (loc, p, final_date) in model.inventory_ambient_index_set:
            total_final_inv += value(pyomo_model.inventory_ambient[loc, p, final_date])

# Calculate total cost from result
total_cost = result.total_cost

print(f"\nProduction Summary:")
print(f"  Total production:      {total_production:>12,.0f} units")
print(f"  Initial inventory:     {total_initial:>12,.0f} units")
print(f"  Total supply:          {total_production + total_initial:>12,.0f} units")
print(f"\nDemand Summary:")
print(f"  Total demand:          {total_demand:>12,.0f} units")
print(f"  Shortages:             {total_shortages:>12,.0f} units")
print(f"  Satisfied:             {total_demand - total_shortages:>12,.0f} units")
print(f"\nInventory:")
print(f"  Final inventory:       {total_final_inv:>12,.0f} units")
print(f"\nCost:")
print(f"  Total cost:            ${total_cost:>12,.2f}")

# Check mass balance
supply = total_production + total_initial
usage = (total_demand - total_shortages) + total_final_inv
balance_diff = abs(supply - usage)

print(f"\n{'=' * 80}")
print("MASS BALANCE CHECK")
print("=" * 80)
print(f"\nSupply = Production + Initial")
print(f"       = {total_production:,.0f} + {total_initial:,.0f}")
print(f"       = {supply:,.0f} units")
print(f"\nUsage = Demand Satisfied + Final Inventory")
print(f"      = {total_demand - total_shortages:,.0f} + {total_final_inv:,.0f}")
print(f"      = {usage:,.0f} units")
print(f"\nDifference: {balance_diff:,.0f} units")

if balance_diff < 1.0:
    print(f"✅ Mass balance verified!")
else:
    print(f"⚠️  Mass balance error: {balance_diff:,.0f} units")

# Check against expectations
print(f"\n{'=' * 80}")
print("COMPARISON TO EXPECTED VALUES")
print("=" * 80)

expected_production = 2_400_000
expected_cost = 13_000_000

production_diff = abs(total_production - expected_production)
cost_diff = abs(total_cost - expected_cost)

print(f"\nProduction:")
print(f"  Expected: ~{expected_production:,.0f} units")
print(f"  Actual:    {total_production:,.0f} units")
print(f"  Difference: {production_diff:,.0f} units ({production_diff/expected_production*100:.1f}%)")

print(f"\nCost:")
print(f"  Expected: ~${expected_cost:,.0f}")
print(f"  Actual:   ${total_cost:,.2f}")
print(f"  Difference: ${cost_diff:,.2f} ({cost_diff/expected_cost*100:.1f}%)")

# Verdict
print(f"\n{'=' * 80}")
print("VERDICT")
print("=" * 80)

if production_diff < 100_000 and cost_diff < 1_000_000:
    print("\n✅ FIX SUCCESSFUL!")
    print("   Production and cost are within expected ranges")
elif total_shortages > 0:
    print(f"\n⚠️  Model found infeasibility")
    print(f"   Shortages: {total_shortages:,.0f} units")
    print(f"   This suggests the problem may be infeasible with current constraints")
else:
    print(f"\n❌ Issue persists")
    print(f"   Production still low: {total_production:,.0f} vs expected {expected_production:,.0f}")
    print(f"   Cost still low: ${total_cost:,.2f} vs expected ${expected_cost:,.2f}")
    print(f"   No shortages reported despite production deficit")

print(f"\n{'=' * 80}")
