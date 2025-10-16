#!/usr/bin/env python3
"""
Test whether production spreads naturally with batch tracking
after disabling the broken FIFO penalty.

This test validates the hypothesis that natural constraints (labor costs,
shelf life, transport capacity) should spread production without needing
an explicit smoothing constraint.
"""

from datetime import date, timedelta
from src.models.forecast import Forecast
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.optimization.integrated_model import IntegratedProductionDistributionModel

def create_test_data():
    """Create 4-week test scenario with realistic demand."""

    # Date range: 4 weeks
    start = date(2025, 10, 13)  # Monday
    end = start + timedelta(days=27)  # 4 weeks

    # Locations
    mfg = Location(
        id="6122",
        name="Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH
    )
    dest1 = Location(
        id="6104",
        name="Destination 1",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT
    )

    # Routes: Direct route, 2-day transit
    routes = [
        Route(
            origin_id="6122",
            destination_id="6104",
            transport_mode="ambient",
            transit_days=2,
            cost_per_unit=0.50
        )
    ]

    # Forecast: Spread demand across 4 weeks (500 units/day = 14,000 total)
    forecast_data = []
    current = start + timedelta(days=2)  # Start demand after transit
    for i in range(26):  # 26 days of demand
        forecast_data.append({
            'location_id': '6104',
            'product_id': 'P1',
            'date': current + timedelta(days=i),
            'quantity': 500
        })

    forecast = Forecast(forecast_data)

    # Labor calendar: Weekdays with fixed hours
    labor_days = []
    current = start
    for i in range(28):
        day = current + timedelta(days=i)
        is_weekday = day.weekday() < 5
        labor_days.append(LaborDay(
            date=day,
            fixed_hours=12 if is_weekday else 0,
            max_overtime_hours=2 if is_weekday else 4,
            fixed_labor_cost=600 if is_weekday else 0,
            overtime_hourly_rate=50 if is_weekday else 100,
            min_hours_if_used=0 if is_weekday else 4
        ))

    labor_calendar = LaborCalendar(labor_days)

    # Manufacturing site
    mfg_site = ManufacturingSite(
        location=mfg,
        products=['P1'],
        production_rate_per_hour=1400,
        storage_capacity_frozen=50000,
        storage_capacity_ambient=10000
    )

    # Cost structure
    costs = CostStructure(
        production_cost_per_unit=2.0,
        transport_cost_per_unit_km=0.01,
        storage_cost_frozen_per_unit_day=0.01,
        storage_cost_ambient_per_unit_day=0.005,
        shortage_penalty_per_unit=20.0
    )

    return {
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'manufacturing_site': mfg_site,
        'cost_structure': costs,
        'locations': [mfg, dest1],
        'routes': routes,
        'start_date': start,
        'end_date': end
    }

def analyze_production_spread(production_schedule):
    """Analyze how production is distributed across days."""

    production_by_date = {}
    for batch in production_schedule:
        prod_date = batch.production_date
        if prod_date not in production_by_date:
            production_by_date[prod_date] = 0
        production_by_date[prod_date] += batch.quantity

    # Sort by date
    sorted_dates = sorted(production_by_date.keys())

    print("\n=== PRODUCTION DISTRIBUTION ===")
    print(f"Total production days: {len(sorted_dates)}")
    print(f"Total quantity: {sum(production_by_date.values()):,}")
    print("\nProduction by date:")

    for d in sorted_dates:
        qty = production_by_date[d]
        day_name = d.strftime("%A")
        print(f"  {d} ({day_name}): {qty:,} units")

    # Check concentration
    if len(sorted_dates) == 1:
        print("\n⚠️  WARNING: All production concentrated on ONE day!")
        return False
    elif len(sorted_dates) <= 3:
        print(f"\n⚠️  WARNING: Production concentrated on only {len(sorted_dates)} days")
        return False
    else:
        print(f"\n✅ Production spread across {len(sorted_dates)} days")
        return True

def main():
    """Run the test."""

    print("=" * 70)
    print("TESTING: Natural Production Spreading with Batch Tracking")
    print("=" * 70)
    print("\nHypothesis: Production should spread naturally across multiple days")
    print("due to labor costs, shelf life, and transport constraints.")
    print("\nTest setup:")
    print("  - 4-week planning horizon (28 days)")
    print("  - Demand: 500 units/day for 26 days = 13,000 units total")
    print("  - Daily capacity: 16,800 units (regular), 19,600 (with OT)")
    print("  - Labor: Weekdays cheaper than weekends")
    print("  - Batch tracking: ENABLED")
    print("  - FIFO penalty: DISABLED (the bug fix)")
    print("  - Production smoothing: DISABLED (testing natural constraints)")

    # Create test data
    data = create_test_data()

    # Build model WITH batch tracking, WITHOUT smoothing
    print("\n" + "=" * 70)
    print("Building optimization model...")
    print("=" * 70)

    model = IntegratedProductionDistributionModel(
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        manufacturing_site=data['manufacturing_site'],
        cost_structure=data['cost_structure'],
        locations=data['locations'],
        routes=data['routes'],
        max_routes_per_destination=3,
        allow_shortages=False,
        enforce_shelf_life=True,
        start_date=data['start_date'],
        end_date=data['end_date'],
        use_batch_tracking=True,           # ✅ Batch tracking enabled
        enable_production_smoothing=False  # ❌ No smoothing - test natural constraints
    )

    print(f"\nModel configuration:")
    print(f"  - Batch tracking: {model.use_batch_tracking}")
    print(f"  - Production smoothing: {model.enable_production_smoothing}")

    # Solve
    print("\n" + "=" * 70)
    print("Solving optimization model...")
    print("=" * 70)

    result = model.solve(time_limit_seconds=300)

    if result['status'] != 'optimal' and result['status'] != 'feasible':
        print(f"\n❌ Solve failed: {result['status']}")
        return

    print(f"\n✅ Solve completed: {result['status']}")
    print(f"   Total cost: ${result['total_cost']:,.2f}")

    # Analyze production distribution
    production_schedule = result.get('production_batch_objects', result.get('production', []))

    is_spread = analyze_production_spread(production_schedule)

    # Print conclusion
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    if is_spread:
        print("\n✅ SUCCESS: Production spreads naturally without smoothing constraint!")
        print("   Natural constraints (labor, shelf life, transport) are sufficient.")
        print("   The FIFO penalty fix alone resolved the concentration bug.")
    else:
        print("\n❌ ISSUE: Production still concentrated despite natural constraints.")
        print("   This suggests missing cost components (e.g., holding costs).")
        print("   OR: The current cost structure doesn't penalize concentration enough.")
        print("\n   Next steps:")
        print("   1. Investigate which cost components are missing")
        print("   2. Check if holding costs are properly modeled")
        print("   3. Consider if labor cost structure correctly reflects reality")

if __name__ == "__main__":
    main()
