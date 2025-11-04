#!/usr/bin/env python3
"""
Test script to verify disposal fix prevents zero production.

This script creates a minimal model with initial inventory and demand,
then verifies:
1. Production > 0 (not zero!)
2. Disposal only used for truly expired inventory
3. Demand is satisfied from production + initial inventory
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.optimization.sliding_window_model import SlidingWindowModel
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.unified_route import TransportMode
from src.models.product import Product
from src.models.manufacturing import ManufacturingSite
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure


def test_disposal_fix():
    """Test that disposal fix prevents zero production."""

    print("=" * 80)
    print("DISPOSAL FIX TEST")
    print("=" * 80)

    # Setup: 4-week horizon starting Jan 8, 2025
    start_date = datetime(2025, 1, 8).date()
    end_date = start_date + timedelta(days=27)  # 4 weeks

    print(f"\n1. TEST SETUP")
    print(f"   Planning horizon: {start_date} to {end_date} (28 days)")

    # Create a simple network: Manufacturing -> Hub -> Breadroom
    manufacturing = Location(
        id="MFG",
        name="Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT,
        latitude=0.0,
        longitude=0.0
    )

    hub = Location(
        id="HUB",
        name="Hub",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.AMBIENT,
        latitude=0.0,
        longitude=0.0
    )

    breadroom = Location(
        id="BR1",
        name="Breadroom 1",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
        latitude=0.0,
        longitude=0.0
    )

    locations = {
        "MFG": manufacturing,
        "HUB": hub,
        "BR1": breadroom
    }

    # Routes
    routes = [
        Route(
            id="R1",
            origin_id="MFG",
            destination_id="HUB",
            transit_time_days=1,
            transport_mode=TransportMode.AMBIENT,
            cost=0.10
        ),
        Route(
            id="R2",
            origin_id="HUB",
            destination_id="BR1",
            transit_time_days=1,
            transport_mode=TransportMode.AMBIENT,
            cost=0.10
        )
    ]

    # Products
    products = [
        Product(id="PROD_A", sku="PROD_A", name="Product A", units_per_mix=415)
    ]

    # Manufacturing site with labor
    labor_days = []
    current_date = start_date
    while current_date <= end_date:
        is_weekend = current_date.weekday() >= 5
        labor_days.append(LaborDay(
            date=current_date,
            fixed_hours=0 if is_weekend else 12,
            max_overtime_hours=2 if not is_weekend else 8,
            regular_rate=20.0,
            overtime_rate=30.0,
            non_fixed_rate=40.0
        ))
        current_date += timedelta(days=1)

    labor_calendar = LaborCalendar(name="Test Labor Calendar", labor_days=labor_days)

    mfg_site = ManufacturingSite(
        location_id="MFG",
        production_rate=1400,  # units per hour
        labor_calendar=labor_calendar,
        production_state='ambient'
    )

    # Demand: 500 units per day at BR1 for all 28 days
    demand = {}
    current_date = start_date
    total_demand = 0
    while current_date <= end_date:
        demand[("BR1", "PROD_A", current_date)] = 500
        total_demand += 500
        current_date += timedelta(days=1)

    print(f"   Total demand: {total_demand:,} units (500/day × 28 days)")

    # Initial inventory: Fresh inventory at manufacturing (age = 1 day)
    # Snapshot date = Jan 7, planning starts Jan 8
    # Age on Jan 8 = 1 day (well within 17-day shelf life)
    inventory_snapshot_date = start_date - timedelta(days=1)
    initial_inventory = {
        ("MFG", "PROD_A", "ambient"): 2000  # Fresh inventory
    }

    print(f"   Initial inventory: 2,000 units at MFG (age = 1 day on {start_date})")
    print(f"   Inventory snapshot date: {inventory_snapshot_date}")
    print(f"   Inventory expiration: {inventory_snapshot_date + timedelta(days=17)} (age 17)")
    print(f"   Within planning horizon: {inventory_snapshot_date + timedelta(days=17) <= end_date}")

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=1.30,
        shortage_penalty_per_unit=10000.0,
        storage_cost_ambient_per_unit_day=0.01,
        storage_cost_frozen_per_unit_day=0.02
    )

    # Build model
    print(f"\n2. BUILDING MODEL")
    model_builder = SlidingWindowModel(
        locations=locations,
        routes=routes,
        products=products,
        demand=demand,
        manufacturing_sites={"MFG": mfg_site},
        cost_structure=cost_structure,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        allow_shortages=True,  # Allow shortages to see if model prefers disposal
        use_pallet_tracking=False,  # Simplify for testing
        use_truck_pallet_tracking=False
    )

    model = model_builder.build_model(
        start_date=start_date,
        end_date=end_date
    )

    print(f"   Model built successfully")
    print(f"   Variables: {model.nvariables():,}")
    print(f"   Constraints: {model.nconstraints():,}")

    # Check disposal variables
    if hasattr(model, 'disposal'):
        disposal_count = len(model.disposal)
        print(f"   Disposal variables: {disposal_count}")

        # Check which dates have disposal
        disposal_dates = set()
        for (node_id, prod, state, t) in model.disposal:
            disposal_dates.add(t)

        if disposal_dates:
            min_disposal_date = min(disposal_dates)
            max_disposal_date = max(disposal_dates)
            print(f"   Disposal available from: {min_disposal_date} to {max_disposal_date}")

            # Verify disposal only available AFTER expiration
            expected_expiration = inventory_snapshot_date + timedelta(days=17)
            if min_disposal_date >= expected_expiration:
                print(f"   ✓ Disposal correctly restricted to expired dates (>= {expected_expiration})")
            else:
                print(f"   ✗ ERROR: Disposal available before expiration! (min={min_disposal_date}, expected>={expected_expiration})")
        else:
            print(f"   ✓ No disposal dates (inventory doesn't expire within horizon)")
    else:
        print(f"   No disposal variables (model.disposal not created)")

    # Solve
    print(f"\n3. SOLVING MODEL")

    try:
        solution = model_builder.solve(time_limit_seconds=120)

        print(f"   Solver status: {solution.solver_status}")
        print(f"   Termination: {solution.termination_condition}")
        print(f"   Solve time: {solution.solve_time_seconds:.1f}s")
        print(f"   Total cost: ${solution.total_cost:,.2f}")

        # Extract key metrics
        total_production = solution.total_production
        total_shortage = solution.total_shortage
        total_disposal = sum(
            model_builder.model.disposal[key].value or 0
            for key in model_builder.model.disposal
        ) if hasattr(model_builder.model, 'disposal') else 0

        print(f"\n4. SOLUTION ANALYSIS")
        print(f"   Total demand:      {total_demand:,} units")
        print(f"   Initial inventory: 2,000 units")
        print(f"   Required production: {total_demand - 2000:,} units minimum")
        print(f"   ---")
        print(f"   Actual production: {total_production:,.0f} units")
        print(f"   Shortage:          {total_shortage:,.0f} units")
        print(f"   Disposal:          {total_disposal:,.0f} units")

        # Verify results
        print(f"\n5. VERIFICATION")

        success = True

        # Test 1: Production should be positive
        if total_production > 0:
            print(f"   ✓ TEST 1 PASSED: Production > 0 ({total_production:,.0f} units)")
        else:
            print(f"   ✗ TEST 1 FAILED: Zero production detected!")
            success = False

        # Test 2: Shortage should be zero (we have enough capacity)
        # With 12h/day fixed + 2h overtime = 14h × 1400 units/h = 19,600 units/day
        # Over 28 days, that's 548,800 units capacity (way more than 14,000 demand)
        if total_shortage < 100:  # Allow small numerical tolerance
            print(f"   ✓ TEST 2 PASSED: No significant shortages ({total_shortage:,.0f} units)")
        else:
            print(f"   ⚠ TEST 2 WARNING: Unexpected shortages ({total_shortage:,.0f} units)")

        # Test 3: Disposal should be zero (inventory is fresh, age=1 day on start)
        if total_disposal < 10:  # Allow small numerical tolerance
            print(f"   ✓ TEST 3 PASSED: No disposal of fresh inventory ({total_disposal:,.0f} units)")
        else:
            print(f"   ✗ TEST 3 FAILED: Fresh inventory was disposed! ({total_disposal:,.0f} units)")
            success = False

        # Test 4: Material balance check
        # Total supply = initial + production = 2000 + production
        # Total consumption = demand + shortage = demand - shortage (since shortage is unmet demand)
        # Actually: demand_met + shortage = demand, so demand_met = demand - shortage
        total_supply = 2000 + total_production
        total_consumed = total_demand - total_shortage + total_disposal

        balance_diff = abs(total_supply - total_consumed)
        if balance_diff < 100:  # Allow small numerical tolerance and inventory
            print(f"   ✓ TEST 4 PASSED: Material balance OK (diff={balance_diff:,.0f} units)")
        else:
            print(f"   ⚠ TEST 4 WARNING: Material balance discrepancy ({balance_diff:,.0f} units)")
            print(f"     Supply: {total_supply:,.0f}, Consumed: {total_consumed:,.0f}")

        # Test 5: Production should be approximately demand - initial_inventory
        expected_production = max(0, total_demand - 2000)
        production_diff = abs(total_production - expected_production)
        if production_diff < 500:  # Allow for some buffer inventory
            print(f"   ✓ TEST 5 PASSED: Production matches need (expected ~{expected_production:,}, got {total_production:,.0f})")
        else:
            print(f"   ⚠ TEST 5 WARNING: Production deviation (expected ~{expected_production:,}, got {total_production:,.0f})")

        print(f"\n" + "=" * 80)
        if success:
            print("DISPOSAL FIX TEST: ✓ PASSED")
            print("Zero production bug is FIXED!")
        else:
            print("DISPOSAL FIX TEST: ✗ FAILED")
            print("Zero production bug still present!")
        print("=" * 80)

        return success

    except Exception as e:
        print(f"   ✗ ERROR: Solve failed with exception:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_disposal_fix()
    sys.exit(0 if success else 1)
