"""
Simple test to verify fixed labor is treated as sunk cost.
Tests that weekday fixed labor is charged regardless of production.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from datetime import date, timedelta
from src.parsers import ExcelParser

# Use existing test data
parser = ExcelParser("data/examples/Gfree Forecast.xlsm")
data = {
    'forecast': parser.forecast,
    'labor_calendar': parser.labor_calendar,
    'manufacturing_site': parser.manufacturing_site,
    'cost_structure': parser.cost_structure,
    'locations': parser.locations,
    'routes': parser.routes,
    'truck_schedules': parser.truck_schedules,
}

print("="*80)
print("LABOR COST SUNK COST VERIFICATION")
print("="*80)

# Build optimization model
from src.optimization import IntegratedProductionDistributionModel

print("\nBuilding optimization model...")
print(f"Forecast: {len(data['forecast'].entries)} entries")
print(f"Labor days: {len(data['labor_calendar'].days)} days")
print(f"Products: {len(data['forecast'].products)}")

# Use only first 7 days for quick test
start_date = data['forecast'].start_date
end_date = start_date + timedelta(days=6)  # 1 week

# Filter forecast for first week
filtered_entries = [e for e in data['forecast'].entries if e.forecast_date <= end_date]
data['forecast'].entries = filtered_entries

print(f"\nFiltered to first week: {start_date} to {end_date}")
print(f"Forecast entries: {len(filtered_entries)}")

model = IntegratedProductionDistributionModel(
    forecast=data['forecast'],
    labor_calendar=data['labor_calendar'],
    manufacturing_site=data['manufacturing_site'],
    cost_structure=data['cost_structure'],
    locations=data['locations'],
    routes=data['routes'],
    truck_schedules=data['truck_schedules'],
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=False,
    initial_inventory={}
)

print(f"\nModel built:")
print(f"  Planning dates: {len(model.production_dates)} days")
print(f"  Routes: {len(model.enumerated_routes)} routes")

print("\nSolving...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=120,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

print(f"\nSolver Status: {result.status}")
print(f"Success: {result.success}")
print(f"Termination: {result.termination_condition}")
print(f"Solve Time: {result.solve_time_seconds:.2f}s")

if not result.success:
    print(f"\nError: {result.infeasibility_message}")
    sys.exit(1)

print(f"\nTotal Cost: ${result.objective_value:,.2f}")

# Analyze labor costs by day
print("\n" + "="*80)
print("LABOR COST ANALYSIS")
print("="*80)
print(f"{'Date':<12} {'Day':<10} {'Fixed?':<8} {'Production':<12} {'Labor Cost':<12}")
print("-"*80)

weekday_labor_costs = []
weekend_labor_costs = []
weekend_production = 0
weekday_production = 0

for d in sorted(model.production_dates):
    if d > end_date:
        continue

    day_name = d.strftime("%A")
    labor_day = data['labor_calendar'].get_day_for_date(d)
    is_fixed = labor_day.is_fixed_day if labor_day else False

    # Get production
    production = sum(result.production.get((d, p.id), 0.0) for p in data['forecast'].products)

    # Get labor cost
    labor_cost = result.labor_cost_by_date.get(d, 0.0)

    if is_fixed:
        weekday_labor_costs.append(labor_cost)
        weekday_production += production
    else:
        weekend_labor_costs.append(labor_cost)
        weekend_production += production

    print(f"{d} {day_name:<10} {str(is_fixed):<8} {production:>10.0f} ${labor_cost:>10.2f}")

print("-"*80)

# Verification checks
print("\n" + "="*80)
print("VERIFICATION CHECKS")
print("="*80)

# Check 1: Weekday fixed labor should be consistent
if weekday_labor_costs:
    expected_fixed_cost = 12 * 25.0  # 12 hours × $25/h = $300
    avg_weekday_cost = sum(weekday_labor_costs) / len(weekday_labor_costs)

    print(f"\n1. Weekday Fixed Labor (Sunk Cost):")
    print(f"   Average weekday labor cost: ${avg_weekday_cost:.2f}")
    print(f"   Expected fixed cost: ${expected_fixed_cost:.2f}")

    # Allow for some variation due to overtime
    if all(cost >= expected_fixed_cost * 0.95 for cost in weekday_labor_costs):
        print(f"   ✓ PASS: All weekdays have at least fixed labor cost")
    else:
        min_cost = min(weekday_labor_costs)
        print(f"   ✗ FAIL: Some weekdays have less than fixed cost (min: ${min_cost:.2f})")

# Check 2: Weekend production should be minimized
print(f"\n2. Weekend Production (Should be minimized):")
print(f"   Weekday production: {weekday_production:,.0f} units")
print(f"   Weekend production: {weekend_production:,.0f} units")

if weekend_production == 0:
    print(f"   ✓ PASS: No weekend production (optimal)")
elif weekend_production < weekday_production * 0.1:  # Less than 10% on weekends
    print(f"   ⚠️  PARTIAL: Some weekend production but minimal ({weekend_production/weekday_production*100:.1f}%)")
else:
    print(f"   ✗ FAIL: Significant weekend production ({weekend_production/weekday_production*100:.1f}%)")

# Check 3: Weekend labor cost should only appear if there's production
if weekend_labor_costs:
    print(f"\n3. Weekend Labor Costs:")
    for i, (cost, prod) in enumerate(zip(weekend_labor_costs, [weekend_production])):
        if cost > 0 and prod == 0:
            print(f"   ✗ FAIL: Weekend has labor cost (${cost:.2f}) but no production")
        elif cost > 0:
            print(f"   ✓ OK: Weekend has labor cost (${cost:.2f}) with production ({prod:.0f} units)")
        else:
            print(f"   ✓ PASS: Weekend has no labor cost and no production")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
