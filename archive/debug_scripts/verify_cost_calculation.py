"""
Comprehensive cost verification for 29-week model.

Verifies:
1. All cost components are calculated correctly
2. Demand satisfaction (production vs forecast)
3. Transport quantities match production
4. Cost breakdown matches objective value
"""
import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value

print("=" * 80)
print("COST VERIFICATION - 29 WEEK MODEL")
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
    allow_shortages=True,
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
print("SOLUTION STATUS")
print("=" * 80)
print(f"Status: {result.termination_condition}")
print(f"Success: {result.success}")
print(f"Objective Value: ${result.objective_value:,.2f}")
print(f"Solve Time: {result.solve_time_seconds:.1f}s")

if not result.success:
    print("\n❌ Solve failed - cannot verify costs")
    sys.exit(1)

# Access Pyomo model for detailed extraction
pyomo_model = model.model

print("\n" + "=" * 80)
print("DEMAND VERIFICATION")
print("=" * 80)

# Calculate total demand
total_demand = 0
for (dest, prod, d), qty in model.demand.items():
    total_demand += qty

print(f"Total Demand: {total_demand:,.0f} units")

# Calculate total production
total_production = 0
for d in pyomo_model.dates:
    for p in pyomo_model.products:
        qty = value(pyomo_model.production[d, p])
        total_production += qty

print(f"Total Production: {total_production:,.0f} units")

# Calculate total initial inventory
total_initial_inv = sum(initial_inv.values())
print(f"Initial Inventory: {total_initial_inv:,.0f} units")

# Calculate supply vs demand
print(f"\nSupply (Production + Initial): {total_production + total_initial_inv:,.0f} units")
print(f"Demand: {total_demand:,.0f} units")
print(f"Surplus/Deficit: {(total_production + total_initial_inv - total_demand):,.0f} units")

print("\n" + "=" * 80)
print("DETAILED COST BREAKDOWN")
print("=" * 80)

# Extract costs from solution metadata
if hasattr(result, 'metadata') and 'solution' in result.metadata:
    solution = result.metadata['solution']

    print(f"\nLabor Cost:         ${solution.get('total_labor_cost', 0):>15,.2f}")
    print(f"Production Cost:    ${solution.get('total_production_cost', 0):>15,.2f}")
    print(f"Transport Cost:     ${solution.get('total_transport_cost', 0):>15,.2f}")
    print(f"Inventory Cost:     ${solution.get('total_inventory_cost', 0):>15,.2f}")
    print(f"Truck Cost:         ${solution.get('total_truck_cost', 0):>15,.2f}")
    print(f"Shortage Cost:      ${solution.get('total_shortage_cost', 0):>15,.2f}")
    print(f"{'-' * 80}")
    print(f"Total Cost:         ${solution.get('total_cost', 0):>15,.2f}")

    # Compare with objective
    calc_total = (
        solution.get('total_labor_cost', 0) +
        solution.get('total_production_cost', 0) +
        solution.get('total_transport_cost', 0) +
        solution.get('total_inventory_cost', 0) +
        solution.get('total_truck_cost', 0) +
        solution.get('total_shortage_cost', 0)
    )

    print(f"\nCalculated Total:   ${calc_total:>15,.2f}")
    print(f"Objective Value:    ${result.objective_value:>15,.2f}")

    diff = abs(calc_total - result.objective_value)
    if diff < 0.01:
        print(f"✅ Cost breakdown matches objective")
    else:
        print(f"⚠️  Difference: ${diff:,.2f}")

else:
    print("\n⚠️  Solution metadata not available - extracting costs manually...")

    # Manual extraction
    from pyomo.environ import value

    # Labor cost
    total_labor_cost = 0
    labor_hours_by_date = {}
    for d in pyomo_model.dates:
        hours = value(pyomo_model.labor_hours[d])
        labor_hours_by_date[d] = hours

        # Get cost for this day
        labor_day = model.labor_calendar.get_day(d)
        if labor_day and hours > 0:
            day_cost = model.manufacturing_site.calculate_labor_cost(hours, labor_day)
            total_labor_cost += day_cost

    # Transport cost (LEG-BASED)
    total_transport_cost = 0
    for (origin, dest) in pyomo_model.legs:
        leg_cost_value = model.leg_cost.get((origin, dest), 0.0)
        for p in pyomo_model.products:
            for d in pyomo_model.dates:
                qty = value(pyomo_model.shipment_leg[(origin, dest), p, d])
                total_transport_cost += leg_cost_value * qty

    # Shortage cost
    total_shortage_cost = 0
    for dest in model.destinations:
        for p in pyomo_model.products:
            for d in pyomo_model.dates:
                qty = value(pyomo_model.shortage[dest, p, d])
                total_shortage_cost += model.cost_structure.shortage_penalty_per_unit * qty

    # Production cost
    total_production_cost = 0
    for d in pyomo_model.dates:
        for p in pyomo_model.products:
            qty = value(pyomo_model.production[d, p])
            total_production_cost += model.cost_structure.production_cost_per_unit * qty

    # Inventory cost
    total_inventory_cost = 0
    for loc in model.inventory_locations:
        for p in pyomo_model.products:
            for d in pyomo_model.dates:
                if hasattr(pyomo_model, 'inventory_ambient') and (loc, p, d) in pyomo_model.inventory_ambient:
                    qty = value(pyomo_model.inventory_ambient[loc, p, d])
                    total_inventory_cost += model.cost_structure.inventory_holding_cost_per_unit_day * qty

                if hasattr(pyomo_model, 'inventory_frozen') and (loc, p, d) in pyomo_model.inventory_frozen:
                    qty = value(pyomo_model.inventory_frozen[loc, p, d])
                    total_inventory_cost += model.cost_structure.inventory_holding_cost_per_unit_day * qty

    # Truck cost
    total_truck_cost = 0
    if hasattr(pyomo_model, 'truck_used'):
        for t, dest, d in pyomo_model.truck_used:
            is_used = value(pyomo_model.truck_used[t, dest, d])
            if is_used > 0.5:  # Binary variable
                truck_schedule = model.truck_schedule_collection.get_schedule_by_id(t)
                if truck_schedule:
                    total_truck_cost += truck_schedule.fixed_cost_per_trip

    print(f"\nLabor Cost:         ${total_labor_cost:>15,.2f}")
    print(f"Production Cost:    ${total_production_cost:>15,.2f}")
    print(f"Transport Cost:     ${total_transport_cost:>15,.2f}")
    print(f"Inventory Cost:     ${total_inventory_cost:>15,.2f}")
    print(f"Truck Cost:         ${total_truck_cost:>15,.2f}")
    print(f"Shortage Cost:      ${total_shortage_cost:>15,.2f}")
    print(f"{'-' * 80}")

    calc_total = (
        total_labor_cost +
        total_production_cost +
        total_transport_cost +
        total_inventory_cost +
        total_truck_cost +
        total_shortage_cost
    )

    print(f"Calculated Total:   ${calc_total:>15,.2f}")
    print(f"Objective Value:    ${result.objective_value:>15,.2f}")

    diff = abs(calc_total - result.objective_value)
    if diff < 0.01:
        print(f"✅ Cost breakdown matches objective")
    else:
        print(f"⚠️  Difference: ${diff:,.2f}")

print("\n" + "=" * 80)
print("SHIPMENT VERIFICATION")
print("=" * 80)

# Calculate total shipments via legs
total_leg_shipments = 0
for (origin, dest) in pyomo_model.legs:
    for p in pyomo_model.products:
        for d in pyomo_model.dates:
            qty = value(pyomo_model.shipment_leg[(origin, dest), p, d])
            total_leg_shipments += qty

print(f"Total Leg Shipments: {total_leg_shipments:,.0f} units")

# Calculate shortages
total_shortages = 0
for dest in model.destinations:
    for p in pyomo_model.products:
        for d in pyomo_model.dates:
            qty = value(pyomo_model.shortage[dest, p, d])
            total_shortages += qty

print(f"Total Shortages:     {total_shortages:,.0f} units")

# Final inventory
final_inventory = 0
final_date = max(pyomo_model.dates)
for loc in model.inventory_locations:
    for p in pyomo_model.products:
        if hasattr(pyomo_model, 'inventory_ambient') and (loc, p, final_date) in pyomo_model.inventory_ambient:
            qty = value(pyomo_model.inventory_ambient[loc, p, final_date])
            final_inventory += qty

        if hasattr(pyomo_model, 'inventory_frozen') and (loc, p, final_date) in pyomo_model.inventory_frozen:
            qty = value(pyomo_model.inventory_frozen[loc, p, final_date])
            final_inventory += qty

print(f"Final Inventory:     {final_inventory:,.0f} units")

print("\n" + "=" * 80)
print("MASS BALANCE VERIFICATION")
print("=" * 80)

# Mass balance: Initial + Production = Shipments + Shortages + Final Inventory
supply = total_initial_inv + total_production
usage = total_leg_shipments + total_shortages + final_inventory

print(f"Supply (Initial + Production):                {supply:,.0f} units")
print(f"Usage (Shipments + Shortages + Final Inv):   {usage:,.0f} units")
print(f"Difference:                                   {abs(supply - usage):,.0f} units")

if abs(supply - usage) < 1.0:
    print(f"✅ Mass balance verified")
else:
    print(f"⚠️  Mass balance discrepancy detected")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"\n✅ Model solved successfully")
print(f"✅ Objective: ${result.objective_value:,.2f}")
print(f"✅ Demand: {total_demand:,.0f} units")
print(f"✅ Production: {total_production:,.0f} units")
print(f"✅ Shortages: {total_shortages:,.0f} units ({100*total_shortages/total_demand:.2f}%)")

print("\n" + "=" * 80)
