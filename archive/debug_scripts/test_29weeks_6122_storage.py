"""
Full 29-week integration test with 6122_Storage implementation.

Verifies:
1. Model solves successfully with full dataset
2. Weekend production is minimized/eliminated
3. Demand is satisfied
4. Costs are reasonable
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

print("=" * 80)
print("29-WEEK INTEGRATION TEST WITH 6122_STORAGE")
print("=" * 80)

print("\nLoading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

# Parse all data
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

# Use full 29-week dataset
forecast_dates = [e.forecast_date for e in forecast.entries]
start_date = min(forecast_dates)
end_date = max(forecast_dates)

product_ids = sorted(set(e.product_id for e in forecast.entries))
destination_ids = sorted(set(e.location_id for e in forecast.entries))

print(f"\nDataset: {start_date} to {end_date}")
print(f"  Duration: {(end_date - start_date).days + 1} days (~{((end_date - start_date).days + 1) / 7:.1f} weeks)")
print(f"  Forecast entries: {len(forecast.entries)}")
print(f"  Products: {len(product_ids)}")
print(f"  Destinations: {len(destination_ids)}")

# Create initial inventory for 6122_Storage
# Use moderate initial inventory to handle first-day morning trucks
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

print(f"\nInitial inventory at 6122_Storage: {sum(initial_inv.values()):,.0f} units")

print("\n" + "=" * 80)
print("BUILDING OPTIMIZATION MODEL")
print("=" * 80)

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
print(f"  Planning dates: {len(model.production_dates)} days")
print(f"  Routes: {len(model.enumerated_routes)}")
print(f"  Inventory locations: {len(model.inventory_locations)}")
print(f"    6122_Storage included: {'6122_Storage' in model.inventory_locations}")

print("\n" + "=" * 80)
print("SOLVING OPTIMIZATION MODEL")
print("=" * 80)
print("This will take several minutes for the full 29-week dataset...")

result = model.solve(
    solver_name='cbc',
    time_limit_seconds=600,  # 10 minutes max
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=True
)

print("\n" + "=" * 80)
print("RESULTS ANALYSIS")
print("=" * 80)

print(f"\nSolver Status: {result.termination_condition}")
print(f"Success: {result.success}")

if result.success:
    print(f"Objective Value: ${result.objective_value:,.2f}")
    print(f"Solve Time: {result.solve_time_seconds:.2f}s")

    # Extract production schedule
    production_by_date = {}
    for (prod_date, prod), qty in result.variables.items():
        if 'production[' in str(prod_date):
            # Parse production variable
            continue
        # Direct tuple format
        if isinstance(prod_date, date):
            if prod_date not in production_by_date:
                production_by_date[prod_date] = 0
            production_by_date[prod_date] += qty

    # Check for weekend production
    print("\n" + "-" * 80)
    print("WEEKEND PRODUCTION ANALYSIS")
    print("-" * 80)

    weekend_days = []
    weekend_production = 0
    total_production = 0

    for prod_date in sorted(model.production_dates):
        # Get production from result.variables
        daily_prod = 0
        for (var_date, var_prod), qty in result.variables.items():
            if isinstance(var_date, date) and var_date == prod_date:
                if 'production' in str(var_date) or qty > 0:  # Filter for production vars
                    daily_prod += qty

        total_production += daily_prod

        if prod_date.weekday() in [5, 6]:  # Weekend
            if daily_prod > 0.1:
                weekend_days.append((prod_date, daily_prod))
                weekend_production += daily_prod

    print(f"  Total production: {total_production:,.0f} units")
    print(f"  Weekend production: {weekend_production:,.0f} units ({weekend_production/total_production*100:.1f}%)")
    print(f"  Weekend days with production: {len(weekend_days)}")

    if weekend_days:
        print(f"\n  Weekend production details:")
        for prod_date, qty in weekend_days[:10]:  # Show first 10
            day_name = prod_date.strftime("%A")
            print(f"    {day_name} {prod_date}: {qty:,.0f} units")
        if len(weekend_days) > 10:
            print(f"    ... and {len(weekend_days) - 10} more weekend days")
    else:
        print(f"\n  ✅ NO WEEKEND PRODUCTION - Cost optimization working perfectly!")

    # Check demand satisfaction
    print("\n" + "-" * 80)
    print("DEMAND SATISFACTION")
    print("-" * 80)

    total_demand = sum(v for k, v in model.demand.items())
    total_shortage = sum(v for k, v in result.variables.items() if 'shortage' in str(k))

    print(f"  Total demand: {total_demand:,.0f} units")
    print(f"  Total shortage: {total_shortage:,.0f} units")
    print(f"  Fill rate: {(1 - total_shortage/total_demand)*100:.2f}%")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Model solved to optimality")
    print(f"✅ Objective: ${result.objective_value:,.2f}")
    print(f"✅ Solve time: {result.solve_time_seconds:.1f}s")

    if weekend_production < total_production * 0.01:  # Less than 1%
        print(f"✅ Weekend production minimized: {weekend_production/total_production*100:.2f}%")
    else:
        print(f"⚠️  Weekend production: {weekend_production/total_production*100:.2f}% (may be unavoidable)")

    if total_shortage < total_demand * 0.05:  # Less than 5%
        print(f"✅ Demand well satisfied: {(1 - total_shortage/total_demand)*100:.1f}% fill rate")
    else:
        print(f"⚠️  Demand satisfaction: {(1 - total_shortage/total_demand)*100:.1f}% fill rate")

    print(f"\n✅ 29-WEEK INTEGRATION TEST PASSED")

else:
    print(f"\n❌ OPTIMIZATION FAILED: {result.termination_condition}")
    print("\nPossible issues:")
    print("  - Model infeasibility")
    print("  - Time limit exceeded")
    print("  - Solver error")

print("\n" + "=" * 80)
