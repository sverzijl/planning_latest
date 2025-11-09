"""Diagnostic test to isolate labor capacity constraint violation.

ROOT CAUSE HYPOTHESIS:
Line 1721 in sliding_window_model.py:
    return model.labor_hours_used[node_id, t] == production_time

This is an EQUALITY constraint, not a capacity constraint.
It sets labor_hours_used = production_time, but doesn't enforce upper bound!

The labor_hours_used variable (line 703) has:
    within=NonNegativeReals

But NO UPPER BOUND! So labor can grow unbounded.

Expected constraint should be:
    return production_time <= max_hours

Or if using labor_hours_used:
    Add separate constraint: labor_hours_used <= max_hours
"""

from datetime import datetime, timedelta
from pathlib import Path
from src.optimization.sliding_window_model import SlidingWindowModel
from src.parsers.multi_file_parser import MultiFileParser
from src.validation.data_validator import DataValidator

def test_labor_capacity_violation():
    """Test for labor capacity violation in sliding window model."""

    print("=" * 80)
    print("LABOR CAPACITY BUG DIAGNOSTIC TEST")
    print("=" * 80)

    # Parse data
    print("\n1. Parsing data files...")
    forecast_file = Path("data/examples/Gluten Free Forecast - Latest.xlsm")
    network_file = Path("data/examples/Network_Config.xlsx")

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file
    )
    forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
    products = forecast.get_products()  # Extract products from forecast

    print("✅ Data parsed successfully")

    # Set planning horizon (1 week to keep small)
    start_date = datetime(2025, 1, 6)
    end_date = start_date + timedelta(days=6)

    print(f"\n3. Building model (horizon: {start_date.date()} to {end_date.date()})...")

    # Build model
    model_builder = SlidingWindowModel(
        nodes=locations,
        routes=routes,
        products=products,
        demand=forecast,
        initial_inventory={},  # No initial inventory for this test
        labor_calendar=labor_calendar,
        truck_schedules=truck_schedules,
        cost_params=cost_params,
        start_date=start_date,
        end_date=end_date,
        mipgap=0.01,
        timelimit=300,
        use_pallet_tracking=True,
        use_mix_based_production=True,
        use_truck_pallet_tracking=False
    )

    model = model_builder.build_model()

    print("\n4. Checking labor_hours_used variable bounds...")

    # Check if labor_hours_used has upper bounds
    labor_vars_checked = 0
    unbounded_count = 0

    for node_id, date in model.labor_hours_used:
        labor_vars_checked += 1
        var = model.labor_hours_used[node_id, date]

        # Check bounds
        if var.bounds[1] is None:  # Upper bound is None
            unbounded_count += 1
            if unbounded_count <= 3:  # Show first 3
                print(f"  ⚠️  labor_hours_used[{node_id}, {date.date()}] has NO UPPER BOUND")

    print(f"\n  Total labor_hours_used variables: {labor_vars_checked}")
    print(f"  Variables with no upper bound: {unbounded_count}")

    if unbounded_count > 0:
        print(f"\n  ❌ BUG CONFIRMED: {unbounded_count} labor variables have no upper bound!")
    else:
        print(f"\n  ✅ All labor variables have upper bounds")

    print("\n5. Checking production_capacity_con constraints...")

    # Check what the production capacity constraints actually enforce
    constraints_checked = 0
    equality_constraints = 0
    inequality_constraints = 0

    for node_id, date in model.production_capacity_con:
        constraints_checked += 1
        con = model.production_capacity_con[node_id, date]

        # Get constraint body and bounds
        if hasattr(con, 'equality') and con.equality:
            equality_constraints += 1
            if equality_constraints <= 3:  # Show first 3
                print(f"  ⚠️  production_capacity_con[{node_id}, {date.date()}] is EQUALITY (not capacity limit)")
        elif hasattr(con, 'upper') and con.upper is not None:
            inequality_constraints += 1
        else:
            if constraints_checked <= 3:
                print(f"  ⚠️  production_capacity_con[{node_id}, {date.date()}] type unclear")

    print(f"\n  Total production_capacity_con: {constraints_checked}")
    print(f"  Equality constraints (=): {equality_constraints}")
    print(f"  Inequality constraints (≤): {inequality_constraints}")

    if equality_constraints > 0:
        print(f"\n  ❌ BUG CONFIRMED: {equality_constraints} constraints are equalities, not capacity limits!")
        print(f"     These set labor_hours_used = production_time")
        print(f"     But don't enforce production_time <= max_hours")

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)

    if unbounded_count > 0 or equality_constraints > 0:
        print("\n❌ ROOT CAUSE IDENTIFIED:")
        print("   1. labor_hours_used has no upper bound (line 703)")
        print("   2. production_capacity_con sets labor_hours_used = production_time (line 1721)")
        print("   3. No constraint enforces production_time <= max_hours")
        print("\n   RESULT: Labor hours can grow unbounded (35 hours observed)")

        print("\n✅ FIX:")
        print("   Change line 1721 from:")
        print("       return model.labor_hours_used[node_id, t] == production_time")
        print("   To:")
        print("       labor_hours_var = model.labor_hours_used[node_id, t]")
        print("       model.production_capacity_con.add(labor_hours_var == production_time)")
        print("       return labor_hours_var <= max_hours")
        print("\n   OR simpler:")
        print("       return production_time <= max_hours")
        print("       # And add separate constraint: labor_hours_used == production_time")
    else:
        print("\n✅ No issues found in labor capacity constraints")

if __name__ == "__main__":
    test_labor_capacity_violation()
