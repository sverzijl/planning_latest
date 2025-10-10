"""Solve full 29-week horizon in a single monolithic solve."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')
import time

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel

print("="*70)
print("MONOLITHIC SOLVE: Full 29-week horizon (203 days)")
print("="*70)

print("\nLoading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Get planning horizon info
start_date = min(e.forecast_date for e in full_forecast.entries)
end_date = max(e.forecast_date for e in full_forecast.entries)
total_days = (end_date - start_date).days + 1

print(f"\nPlanning horizon: {start_date} to {end_date} ({total_days} days)")
print(f"Forecast entries: {len(full_forecast.entries)}")

# Build the model
print("\nBuilding optimization model...")
build_start = time.time()

model = IntegratedProductionDistributionModel(
    forecast=full_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory={},
)

build_time = time.time() - build_start
print(f"Model built in {build_time:.2f}s")

# Solve the model
print("\nSolving with CBC (aggressive heuristics enabled)...")
print("Time limit: 600 seconds (10 minutes)")
print("MIP gap: 1%")

solve_start = time.time()

result = model.solve(
    solver_name='cbc',
    time_limit_seconds=600,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=True  # Show solver output
)

solve_time = time.time() - solve_start

print("\n" + "="*70)
print("SOLVE COMPLETE")
print("="*70)

print(f"\nSolver status: {result.termination_condition}")
print(f"Feasible: {result.is_feasible()}")
print(f"Optimal: {result.is_optimal()}")
print(f"Solve time: {solve_time:.2f}s")

if result.objective_value is not None:
    print(f"Objective value: ${result.objective_value:,.2f}")

# Extract solution
if result.is_feasible():
    print("\nExtracting solution...")
    solution = model.get_solution()

    if solution:
        print("\n" + "="*70)
        print("SOLUTION SUMMARY")
        print("="*70)

        # Production
        total_production = 0.0
        production_days = 0
        for key, value in solution['production_by_date_product'].items():
            if isinstance(key, tuple):
                # Format: {(date, product): quantity}
                total_production += value
                if value > 0:
                    production_days += 1
            else:
                # Format: {date: {product: quantity}}
                if isinstance(value, dict):
                    total_production += sum(value.values())
                    if sum(value.values()) > 0:
                        production_days += 1
                else:
                    total_production += value
                    if value > 0:
                        production_days += 1

        print(f"\nProduction:")
        print(f"  Total units: {total_production:,.0f}")
        print(f"  Production days: {production_days}")

        # Costs
        print(f"\nCost breakdown:")
        print(f"  Labor:       ${solution['total_labor_cost']:>12,.2f}")
        print(f"  Production:  ${solution['total_production_cost']:>12,.2f}")
        print(f"  Transport:   ${solution['total_transport_cost']:>12,.2f}")
        print(f"  Inventory:   ${solution['total_inventory_cost']:>12,.2f}")
        print(f"  Truck:       ${solution['total_truck_cost']:>12,.2f}")
        print(f"  Shortage:    ${solution['total_shortage_cost']:>12,.2f}")
        print(f"  ------------------------------------------")
        print(f"  TOTAL:       ${solution['total_cost']:>12,.2f}")

        # Shortages
        if solution['total_shortage_units'] > 0:
            print(f"\nShortages:")
            print(f"  Total units: {solution['total_shortage_units']:,.0f}")
            print(f"  Total cost:  ${solution['total_shortage_cost']:,.2f}")

        print("\n" + "="*70)
        print("SUCCESS: Full 29-week horizon solved in single solve!")
        print("="*70)
        print(f"\nTotal time (build + solve): {build_time + solve_time:.2f}s")
    else:
        print("\nERROR: Could not extract solution")
else:
    print("\nINFEASIBLE or ERROR")
    if result.infeasibility_message:
        print(f"Message: {result.infeasibility_message}")
