"""
Test inventory-based truck loading to verify no irrational Sunday production.
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
print("INVENTORY-BASED TRUCK LOADING TEST")
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

# Filter to 3 weeks around the problematic weekend
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

# Create initial inventory at manufacturing site for first-day morning trucks
# Set to 10,000 units per product (enough for ~1 truck load per product)
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122', pid, 'ambient')] = 10000.0

print(f"\nInitial inventory at 6122: {sum(initial_inv.values()):,.0f} units across {len(product_ids)} products")

print("\nBuilding optimization model...")
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

print(f"Model built successfully")
print(f"  Planning dates: {len(model.production_dates)} days")
print(f"  Routes: {len(model.enumerated_routes)} routes")

print("\n" + "=" * 80)
print("SOLVING OPTIMIZATION MODEL")
print("=" * 80)
print("This may take 1-2 minutes...\n")

result = model.solve(
    solver_name='cbc',
    time_limit_seconds=120,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=True  # Show solver output
)

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

print(f"\nSuccess: {result.success}")
print(f"Termination: {result.termination_condition}")
print(f"Solve Time: {result.solve_time_seconds:.2f}s")

if not result.success:
    print(f"\n❌ INFEASIBLE: {result.infeasibility_message}")
    print("\nThis indicates an error in the inventory-based truck loading implementation.")
    print("The model constraints are over-constrained or incorrectly formulated.")
    sys.exit(1)

print(f"Total Cost: ${result.objective_value:,.2f}")

# Focus on the problematic weekend
print("\n" + "=" * 80)
print("PRODUCTION SCHEDULE (Oct 24-27: Fri-Mon)")
print("=" * 80)
print(f"{'Date':<12} {'Day':<10} {'Production':>12} {'Labor Hrs':>12} {'Labor Cost':>12}")
print("-" * 80)

oct24 = date(2025, 10, 24)  # Friday
weekend_production = 0
weekday_production = 0

for i in range(7):  # Show full week
    d = oct24 + timedelta(days=i)
    if d not in model.production_dates:
        continue
    
    day_name = d.strftime("%A")
    
    # Get total production
    production = sum(result.production.get((d, pid), 0)
                    for pid in product_ids)

    # Get labor
    labor_hours = result.labor_hours.get(d, 0)
    labor_cost = result.labor_cost_by_date.get(d, 0)
    
    # Track weekend vs weekday
    if d.weekday() >= 5:  # Sat/Sun
        weekend_production += production
    else:
        weekday_production += production
    
    print(f"{d} {day_name:<10} {production:>12,.0f} {labor_hours:>10.2f}h ${labor_cost:>11.2f}")

print("-" * 80)
print(f"\nWeekday production (Fri+Mon): {weekday_production:,.0f} units")
print(f"Weekend production (Sat+Sun): {weekend_production:,.0f} units")

# Verification
print("\n" + "=" * 80)
print("VERIFICATION")
print("=" * 80)

if weekend_production == 0:
    print("\n✅ SUCCESS: No weekend production!")
    print("   Model correctly uses weekday capacity before expensive weekend labor")
elif weekend_production < 1000:
    print(f"\n⚠️  MINIMAL: Only {weekend_production:,.0f} units on weekend")
    print("   May be justified by capacity or timing constraints")
else:
    print(f"\n❌ ISSUE: {weekend_production:,.0f} units on weekend")
    print(f"   Weekday production: {weekday_production:,.0f}")
    
# Check for idle weekend costs
print("\n" + "=" * 80)
print("WEEKEND LABOR COSTS CHECK")
print("=" * 80)

for i in range(2, 4):  # Saturday, Sunday
    d = oct24 + timedelta(days=i)
    if d not in model.production_dates:
        continue

    production = sum(result.production.get((d, pid), 0)
                    for pid in product_ids)
    labor_cost = result.labor_cost_by_date.get(d, 0)
    
    if labor_cost > 0 and production == 0:
        print(f"❌ {d} ({d.strftime('%A')}): ${labor_cost:.2f} labor cost with zero production")
    elif labor_cost > 0 and production > 0:
        print(f"✓ {d} ({d.strftime('%A')}): ${labor_cost:.2f} labor cost with {production:,.0f} units")
    else:
        print(f"✅ {d} ({d.strftime('%A')}): No labor cost, no production (optimal)")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
