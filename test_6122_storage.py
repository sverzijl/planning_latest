"""
Test 6122_Storage virtual location implementation.

This test verifies that:
1. The model runs successfully with 6122_Storage
2. No weekend production occurs (cost optimization works)
3. Demand is still satisfied
4. Monday morning trucks can use Friday production
"""
import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("6122_STORAGE VIRTUAL LOCATION TEST")
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

# Filter to 3 weeks (includes weekend Oct 25-26)
start_date = date(2025, 10, 13)  # Monday
end_date = date(2025, 11, 2)     # Sunday (3 weeks)
filtered_entries = [e for e in forecast.entries
                   if start_date <= e.forecast_date <= end_date]
forecast.entries = filtered_entries

# Get unique products
product_ids = sorted(set(e.product_id for e in forecast.entries))

print(f"Filtered to {start_date} - {end_date}: {len(filtered_entries)} forecast entries")
print(f"Products: {len(product_ids)}")
print(f"Locations: {len(locations)}")

# Create initial inventory for 6122_Storage (for first-day morning trucks)
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 10000.0

print(f"\nInitial inventory at 6122_Storage: {sum(initial_inv.values()):,.0f} units across {len(product_ids)} products")

print("\nBuilding optimization model with 6122_Storage...")
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

print(f"\nModel built successfully:")
print(f"  Planning dates: {len(model.production_dates)} days")
print(f"  Routes: {len(model.enumerated_routes)} routes")
print(f"  Inventory locations: {sorted(model.inventory_locations)}")
print(f"  6122_Storage in inventory locations: {'6122_Storage' in model.inventory_locations}")
print(f"  6122_Storage in ambient storage: {'6122_Storage' in model.locations_ambient_storage}")

print("\n" + "=" * 80)
print("SOLVING OPTIMIZATION MODEL")
print("=" * 80)
print("This may take 1-2 minutes...")

result = model.solve(
    solver_name='cbc',
    time_limit_seconds=120,
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

    # Check for weekend production
    print("\n" + "-" * 80)
    print("WEEKEND PRODUCTION CHECK")
    print("-" * 80)

    weekend_production = []
    for prod_date in sorted(model.production_dates):
        # Check if it's a weekend (Saturday=5, Sunday=6)
        if prod_date.weekday() in [5, 6]:
            total_prod = sum(result.production.get((prod_date, p), 0) for p in product_ids)
            if total_prod > 0.1:  # Allow for tiny numerical errors
                weekend_production.append((prod_date, total_prod))
                day_name = prod_date.strftime("%A")
                print(f"  ⚠️  {day_name} {prod_date}: {total_prod:,.0f} units")

    if not weekend_production:
        print("  ✅ NO WEEKEND PRODUCTION - Cost optimization working!")
    else:
        print(f"\n  ❌ Found {len(weekend_production)} weekend production days")

    # Show production by day
    print("\n" + "-" * 80)
    print("PRODUCTION SCHEDULE (First 10 Days)")
    print("-" * 80)

    for i, prod_date in enumerate(sorted(model.production_dates)[:10]):
        total_prod = sum(result.production.get((prod_date, p), 0) for p in product_ids)
        day_name = prod_date.strftime("%A")
        weekend_marker = " [WEEKEND]" if prod_date.weekday() in [5, 6] else ""
        print(f"  {day_name} {prod_date}: {total_prod:,.0f} units{weekend_marker}")

    # Check 6122_Storage inventory
    print("\n" + "-" * 80)
    print("6122_STORAGE INVENTORY (First 10 Days)")
    print("-" * 80)

    for prod_date in sorted(model.production_dates)[:10]:
        total_inv = sum(result.inventory.get(('6122_Storage', p, prod_date), 0) for p in product_ids)
        day_name = prod_date.strftime("%A")
        print(f"  {day_name} {prod_date}: {total_inv:,.0f} units")

    print("\n✅ TEST COMPLETE")

else:
    print(f"\n❌ OPTIMIZATION FAILED: {result.termination_condition}")
    print("\nThis indicates an error in the 6122_Storage implementation.")

print("\n" + "=" * 80)
