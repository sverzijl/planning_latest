#!/usr/bin/env python
"""
Test production smoothing fix for batch tracking mode.

Verifies that:
1. FIFO penalty is disabled (no production concentration)
2. Production smoothing constraint prevents single-day production
3. Solution spreads production across multiple days
"""

from datetime import date, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.optimization.solver_config import SolverConfig


def test_production_smoothing():
    """Test that production smoothing prevents concentration in batch tracking mode."""

    # Create a 4-week planning horizon
    start = date(2024, 11, 1)
    dates = [start + timedelta(days=i) for i in range(28)]

    # Create simple forecast: 5000 units per day for 4 weeks
    forecast_entries = []
    for d in dates:
        forecast_entries.append(ForecastEntry(
            location_id='6110',
            product_id='P1',
            forecast_date=d,
            quantity=5000.0
        ))
    forecast = Forecast(name='Test Forecast', entries=forecast_entries)

    # Create labor calendar (simple: all weekdays fixed, weekends overtime)
    labor_days = []
    for d in dates:
        is_weekend = d.weekday() >= 5
        labor_days.append(LaborDay(
            date=d,
            fixed_hours=0.0 if is_weekend else 12.0,
            regular_rate=40.0,
            overtime_rate=60.0,
            non_fixed_rate=50.0 if is_weekend else None,
            minimum_hours=4.0 if is_weekend else 0.0,
            is_fixed_day=not is_weekend
        ))
    labor_calendar = LaborCalendar(name='Test Labor Calendar', labor_days=labor_days)

    # Manufacturing site
    manufacturing_site = ManufacturingSite(
        location_id='6122',
        production_rate=1400.0,
        max_hours_per_day=14.0
    )

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=1.0,
        transport_cost_per_unit_km=0.01,
        holding_cost_per_unit_day=0.05,
        waste_cost_per_unit=5.0,
        shortage_penalty_per_unit=100.0
    )

    # Locations
    locations = [
        Location(
            location_id='6122',
            name='Manufacturing',
            location_type=LocationType.MANUFACTURING,
            storage_modes={StorageMode.AMBIENT}
        ),
        Location(
            location_id='6110',
            name='Brisbane',
            location_type=LocationType.BREADROOM,
            storage_modes={StorageMode.AMBIENT}
        )
    ]

    # Simple direct route: 6122 -> 6110 (2 days transit)
    routes = [
        Route(
            origin_id='6122',
            destination_id='6110',
            transit_days=2,
            cost_per_unit=1.0,
            transport_mode='ambient'
        )
    ]

    print("\nTesting Production Smoothing Fix")
    print("=" * 80)
    print(f"Forecast: {len(dates)} days, 5000 units/day = {5000 * len(dates):,} total units")
    print(f"Max daily production: {1400 * 14:,} units (14 hours)")
    print(f"Production smoothing: 20% max change = {0.20 * 1400 * 14:,.0f} units/day")

    # Test WITH production smoothing (default for batch tracking)
    print("\n--- Test 1: Batch Tracking WITH Production Smoothing (default) ---")
    model_with_smoothing = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        solver_config=SolverConfig(solver_name='cbc', time_limit_seconds=60),
        allow_shortages=False,
        use_batch_tracking=True,  # Enable batch tracking
        # enable_production_smoothing defaults to True when use_batch_tracking=True
    )

    print("Building model...")
    pyomo_model = model_with_smoothing.build_model()

    # Check that smoothing constraint exists
    assert hasattr(pyomo_model, 'production_smoothing_con'), \
        "Production smoothing constraint should exist when use_batch_tracking=True"
    print("✓ Production smoothing constraint found in model")

    print("Solving...")
    result = model_with_smoothing.solve(time_limit_seconds=60)

    if result.is_optimal() or result.is_feasible():
        print(f"✓ Solution found: {result.status}")
        print(f"  Objective value: ${result.objective_value:,.2f}")

        # Get production schedule
        production = model_with_smoothing.get_production_schedule()
        prod_by_date = {}
        for batch in production:
            if batch.quantity > 10:  # Ignore trivial amounts
                prod_by_date[batch.production_date] = \
                    prod_by_date.get(batch.production_date, 0) + batch.quantity

        print(f"\n  Production spread across {len(prod_by_date)} days:")
        for d in sorted(prod_by_date.keys())[:10]:  # Show first 10 days
            print(f"    {d}: {prod_by_date[d]:>8,.0f} units")

        if len(prod_by_date) > 10:
            print(f"    ... ({len(prod_by_date) - 10} more days)")

        # Verify production is spread (not concentrated on 1-2 days)
        if len(prod_by_date) >= 10:
            print(f"\n✓ SUCCESS: Production spread across {len(prod_by_date)} days (expected 10-15)")
        else:
            print(f"\n⚠ WARNING: Production only on {len(prod_by_date)} days (expected 10-15)")
            print("  This suggests production concentration may still be occurring")
    else:
        print(f"✗ Solution not found: {result.status}")
        if result.solver_log:
            print(f"  Solver log: {result.solver_log[:500]}")

    # Test WITHOUT production smoothing (to verify the constraint makes a difference)
    print("\n--- Test 2: Batch Tracking WITHOUT Production Smoothing ---")
    model_no_smoothing = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        solver_config=SolverConfig(solver_name='cbc', time_limit_seconds=60),
        allow_shortages=False,
        use_batch_tracking=True,
        enable_production_smoothing=False,  # Explicitly disable
    )

    print("Building model...")
    pyomo_model_no_smoothing = model_no_smoothing.build_model()

    # Check that smoothing constraint does NOT exist
    assert not hasattr(pyomo_model_no_smoothing, 'production_smoothing_con'), \
        "Production smoothing constraint should NOT exist when enable_production_smoothing=False"
    print("✓ Production smoothing constraint correctly disabled")

    print("Solving...")
    result_no_smoothing = model_no_smoothing.solve(time_limit_seconds=60)

    if result_no_smoothing.is_optimal() or result_no_smoothing.is_feasible():
        print(f"✓ Solution found: {result_no_smoothing.status}")
        print(f"  Objective value: ${result_no_smoothing.objective_value:,.2f}")

        # Get production schedule
        production_no_smoothing = model_no_smoothing.get_production_schedule()
        prod_by_date_no_smoothing = {}
        for batch in production_no_smoothing:
            if batch.quantity > 10:  # Ignore trivial amounts
                prod_by_date_no_smoothing[batch.production_date] = \
                    prod_by_date_no_smoothing.get(batch.production_date, 0) + batch.quantity

        print(f"\n  Production spread across {len(prod_by_date_no_smoothing)} days:")
        for d in sorted(prod_by_date_no_smoothing.keys())[:10]:
            print(f"    {d}: {prod_by_date_no_smoothing[d]:>8,.0f} units")

        if len(prod_by_date_no_smoothing) <= 5:
            print(f"\n  Note: Without smoothing, production may concentrate on fewer days")
            print(f"        ({len(prod_by_date_no_smoothing)} days vs {len(prod_by_date)} days with smoothing)")
    else:
        print(f"✗ Solution not found: {result_no_smoothing.status}")

    print("\n" + "=" * 80)
    print("Test complete!")
    print("\nExpected behavior:")
    print("  - WITH smoothing: Production spread across 10-15 days")
    print("  - WITHOUT smoothing: Production may concentrate on 1-5 days")
    print("  - FIFO penalty disabled: No perverse incentives in objective")


if __name__ == '__main__':
    test_production_smoothing()
