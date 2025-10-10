"""
Diagnose shortage quantities and costs.

This script extracts actual shortage values from the Pyomo model
to understand why the cost is only $5.8M when there appears to be
a 1.27M unit deficit.
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
print("SHORTAGE DIAGNOSTIC")
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

print(f"\n{'=' * 80}")
print("SOLUTION OVERVIEW")
print("=" * 80)
print(f"Status: {result.termination_condition}")
print(f"Objective: ${result.objective_value:,.2f}")
print(f"Solve Time: {result.solve_time_seconds:.1f}s")

# Access Pyomo model
pyomo_model = model.model

# Calculate totals
total_demand = sum(v for k, v in model.demand.items())
total_production = sum(value(pyomo_model.production[d, p]) for d in pyomo_model.dates for p in pyomo_model.products)
total_initial = sum(initial_inv.values())

print(f"\nTotal Demand:      {total_demand:>15,.0f} units")
print(f"Total Production:  {total_production:>15,.0f} units")
print(f"Initial Inventory: {total_initial:>15,.0f} units")
print(f"Supply:            {(total_production + total_initial):>15,.0f} units")
print(f"Deficit:           {(total_demand - total_production - total_initial):>15,.0f} units")

print(f"\n{'=' * 80}")
print("SHORTAGE ANALYSIS")
print("=" * 80)

# Extract shortages - only iterate over shortage variable indices that exist
total_shortages = 0
shortage_by_dest = {}
shortage_details = []

# Iterate only over valid indices in the shortage variable
for idx in pyomo_model.shortage:
    qty = value(pyomo_model.shortage[idx])
    if qty > 0.01:  # Ignore tiny numerical errors
        dest, p, d = idx
        total_shortages += qty
        shortage_details.append((dest, p, d, qty))

        if dest not in shortage_by_dest:
            shortage_by_dest[dest] = 0
        shortage_by_dest[dest] += qty

print(f"\nTotal Shortages: {total_shortages:,.0f} units")

if total_shortages > 0:
    print(f"\nShortages by Destination:")
    for dest in sorted(shortage_by_dest.keys(), key=lambda x: shortage_by_dest[x], reverse=True):
        qty = shortage_by_dest[dest]
        pct = 100 * qty / total_demand
        print(f"  {dest}: {qty:>12,.0f} units ({pct:>5.1f}%)")

    print(f"\nSample Shortage Details (first 20):")
    for dest, p, d, qty in sorted(shortage_details, key=lambda x: x[3], reverse=True)[:20]:
        print(f"  {dest}, {p}, {d}: {qty:>10,.0f} units")
else:
    print("  ✅ No shortages!")

# Calculate shortage cost
shortage_cost = total_shortages * model.cost_structure.shortage_penalty_per_unit
print(f"\n{'=' * 80}")
print("COST BREAKDOWN")
print("=" * 80)
print(f"Shortage Cost:         ${shortage_cost:>15,.2f} ({model.cost_structure.shortage_penalty_per_unit}/unit)")
print(f"Production Cost:       ${total_production * model.cost_structure.production_cost_per_unit:>15,.2f} ({model.cost_structure.production_cost_per_unit}/unit)")
print(f"Other Costs (approx):  ${(result.objective_value - shortage_cost - total_production * model.cost_structure.production_cost_per_unit):>15,.2f}")
print(f"{'-' * 80}")
print(f"Total Objective:       ${result.objective_value:>15,.2f}")

# Check if shortage cost matches
expected_with_shortages = shortage_cost + total_production * model.cost_structure.production_cost_per_unit
print(f"\n{'=' * 80}")
print("VERIFICATION")
print("=" * 80)
print(f"Expected cost (production + shortages): ${expected_with_shortages:,.2f}")
print(f"Actual objective:                       ${result.objective_value:,.2f}")
print(f"Difference (labor+transport+inventory): ${(result.objective_value - expected_with_shortages):,.2f}")

print(f"\n{'=' * 80}")
print("MASS BALANCE CHECK")
print("=" * 80)

# Calculate actual deliveries to breadrooms
leg_deliveries_by_dest = {}
for (origin, dest) in model.leg_keys:
    # Only count legs that deliver to final destinations (not hubs)
    if dest in model.destinations:  # This includes all breadrooms
        dest_total = 0
        for p in pyomo_model.products:
            for d in pyomo_model.dates:
                qty = value(pyomo_model.shipment_leg[(origin, dest), p, d])
                dest_total += qty

        if dest_total > 0:
            leg_deliveries_by_dest[dest] = dest_total

total_deliveries = sum(leg_deliveries_by_dest.values())
print(f"\nTotal Leg Deliveries: {total_deliveries:,.0f} units")
print(f"Total Shortages:      {total_shortages:,.0f} units")
print(f"Total Demand:         {total_demand:,.0f} units")
print(f"\nDeliveries + Shortages: {(total_deliveries + total_shortages):,.0f} units")

balance_diff = abs(total_demand - total_deliveries - total_shortages)
if balance_diff < 1.0:
    print(f"✅ Mass balance verified (Deliveries + Shortages = Demand)")
else:
    print(f"⚠️  Mass balance error: {balance_diff:,.0f} units")

print(f"\n{'=' * 80}")
print("SUMMARY")
print("=" * 80)

if total_shortages > 1000:
    shortage_pct = 100 * total_shortages / total_demand
    print(f"\n⚠️  Model has significant shortages:")
    print(f"  {total_shortages:,.0f} units short ({shortage_pct:.1f}% of demand)")
    print(f"  This is expected because supply ({total_production + total_initial:,.0f}) < demand ({total_demand:,.0f})")
    print(f"  Shortage penalty: ${model.cost_structure.shortage_penalty_per_unit}/unit")
    print(f"  Total shortage cost: ${shortage_cost:,.2f}")
elif total_shortages > 0:
    print(f"\n✅ Minor shortages: {total_shortages:,.0f} units ({100*total_shortages/total_demand:.2f}%)")
else:
    print(f"\n✅ All demand satisfied with no shortages!")

print(f"\n{'=' * 80}")
