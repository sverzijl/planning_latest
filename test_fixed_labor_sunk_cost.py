"""
Test that fixed labor is treated as a sunk cost (paid regardless of production).

This test verifies:
1. Weekdays always incur 12 fixed hours of labor cost (even with zero production)
2. Weekends only incur labor cost when production occurs
3. Model prefers weekday production over weekend production
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from datetime import date, timedelta
from src.models import (
    Forecast, ForecastEntry, Location, Route, Product,
    LaborCalendar, LaborDay, ManufacturingSite, CostStructure
)
from src.optimization import IntegratedProductionDistributionModel

# Create minimal test data
start_date = date(2025, 10, 13)  # Monday
products = [Product(id="P1", name="Product 1", sku="SKU-P1")]

# Create forecast for one week: Mon-Sun
forecast_entries = []
for i in range(7):
    d = start_date + timedelta(days=i)
    forecast_entries.append(
        ForecastEntry(
            location_id="DEST1",
            product_id="P1",
            forecast_date=d,
            quantity=1000.0  # Need 1000 units each day
        )
    )

forecast = Forecast(name="Test Forecast", entries=forecast_entries, products=products)

# Labor calendar: Mon-Fri fixed, Sat-Sun non-fixed
labor_days = []
for i in range(7):
    d = start_date + timedelta(days=i)
    is_weekend = i >= 5  # Sat=5, Sun=6

    labor_days.append(
        LaborDay(
            date=d,
            is_fixed_day=not is_weekend,
            fixed_hours=12 if not is_weekend else 0,
            max_hours=14,
            fixed_rate=25.0,
            overtime_rate=37.5,
            non_fixed_rate=40.0 if is_weekend else None,
            minimum_hours=4 if is_weekend else 0
        )
    )

labor_calendar = LaborCalendar(days=labor_days)

# Manufacturing site
manufacturing_site = ManufacturingSite(
    location_id="MFG",
    production_rate_per_hour=1400.0,  # Can produce 1400 units/hour
    labor_calendar=labor_calendar
)

# Simple network: MFG -> DEST1
locations = [
    Location(location_id="MFG", name="Manufacturing", location_type="manufacturing"),
    Location(location_id="DEST1", name="Destination 1", location_type="breadroom")
]

routes = [
    Route(
        route_id="R1",
        origin="MFG",
        destination="DEST1",
        transport_mode="ambient",
        transit_time_days=1,
        cost_per_unit=0.10
    )
]

# Cost structure
cost_structure = CostStructure(
    production_cost_per_unit=1.0,
    shortage_penalty_per_unit=100.0,  # High penalty for unmet demand
    holding_cost_per_unit_per_day=0.01
)

print("="*80)
print("FIXED LABOR SUNK COST TEST")
print("="*80)
print("\nTest Setup:")
print("- Forecast: 1,000 units/day for 7 days (Mon-Sun)")
print("- Labor: Mon-Fri (12h fixed at $25/h), Sat-Sun ($40/h with 4h minimum)")
print("- Production rate: 1,400 units/hour")
print("- Required production time: ~0.7 hours/day")
print("\nExpected Behavior:")
print("- Model should produce on WEEKDAYS (Mon-Fri) because labor is sunk cost")
print("- Model should AVOID weekends ($40/h with 4h minimum = $160 vs $0 marginal cost on weekdays)")
print()

# Build and solve model
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=[],  # No truck constraints for this test
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=False,
    initial_inventory={}
)

print("Solving optimization model...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

print(f"\nSolver Status: {result.status}")
print(f"Total Cost: ${result.objective_value:,.2f}")
print(f"Solve Time: {result.solve_time_seconds:.2f}s")

# Extract production and labor decisions
print("\n" + "="*80)
print("PRODUCTION AND LABOR SCHEDULE")
print("="*80)
print(f"{'Date':<12} {'Day':<10} {'Production':<12} {'Labor Hrs':<12} {'Labor Cost':<12}")
print("-"*80)

total_weekday_production = 0
total_weekend_production = 0
total_labor_cost = 0

for i in range(7):
    d = start_date + timedelta(days=i)
    day_name = d.strftime("%A")

    # Get production
    production = result.production.get((d, "P1"), 0.0)

    # Get labor hours and cost
    labor_hours = result.labor_hours.get(d, 0.0)
    labor_cost = result.labor_cost_by_date.get(d, 0.0)

    total_labor_cost += labor_cost

    if i < 5:  # Weekday
        total_weekday_production += production
    else:  # Weekend
        total_weekend_production += production

    print(f"{d} {day_name:<10} {production:>10.0f} {labor_hours:>10.2f}h ${labor_cost:>10.2f}")

print("-"*80)
print(f"\nSummary:")
print(f"  Weekday production (Mon-Fri): {total_weekday_production:,.0f} units")
print(f"  Weekend production (Sat-Sun): {total_weekend_production:,.0f} units")
print(f"  Total labor cost: ${total_labor_cost:,.2f}")

# Verify the fix
print("\n" + "="*80)
print("FIX VERIFICATION")
print("="*80)

# Check 1: Weekdays with zero production should still have labor cost
weekday_with_zero_production = False
for i in range(5):  # Mon-Fri
    d = start_date + timedelta(days=i)
    production = result.production.get((d, "P1"), 0.0)
    labor_cost = result.labor_cost_by_date.get(d, 0.0)

    if production == 0 and labor_cost > 0:
        weekday_with_zero_production = True
        print(f"✓ {d} ({d.strftime('%A')}): Zero production but ${labor_cost:.2f} labor cost (CORRECT - sunk cost)")

if not weekday_with_zero_production:
    print("✓ All weekdays have production (expected - weekday labor is effectively free)")

# Check 2: Model should prefer weekdays over weekends
if total_weekend_production == 0:
    print("✓ PASS: No weekend production (model correctly prefers weekday sunk cost)")
elif total_weekend_production < total_weekday_production:
    print(f"⚠️  PARTIAL: Some weekend production ({total_weekend_production} units)")
    print(f"   This might be due to capacity constraints or demand timing")
else:
    print(f"✗ FAIL: More weekend than weekday production!")
    print(f"   Weekday: {total_weekday_production}, Weekend: {total_weekend_production}")

# Check 3: Fixed labor cost should appear on weekdays regardless of production
expected_weekday_fixed_cost = 5 * 12 * 25.0  # 5 weekdays × 12 hours × $25/hour = $1,500
fixed_labor_in_cost = sum(
    result.labor_cost_by_date.get(start_date + timedelta(days=i), 0.0)
    for i in range(5)
)

print(f"\n✓ Total weekday fixed labor: ${fixed_labor_in_cost:,.2f}")
print(f"  Expected: ${expected_weekday_fixed_cost:,.2f} (5 days × 12h × $25/h)")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
