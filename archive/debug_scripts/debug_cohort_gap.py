#!/usr/bin/env python3
"""
Debug script to find cohorts with inventory that aren't in demand_cohort_index_set.

This script investigates the 355-unit mismatch where:
- demand_from_cohort = 8,556 units (what demand satisfaction allocated)
- inventory consumed = 8,201 units (what inventory balance deducted)
- GAP = 355 units

Root cause: Some cohorts have inventory but aren't in demand_cohort_index_set,
so they don't deduct demand_consumption in inventory balance equation.
"""

import sys
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.unified_node import UnifiedNode, StorageMode, NodeCapabilities
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel


def create_test_data():
    """Create minimal test data to reproduce the bug."""

    # Nodes
    mfg_node = UnifiedNode(
        id="6122",
        name="Manufacturing",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            has_demand=False,
            can_store=True,
            production_rate_per_hour=1400,
            storage_mode=StorageMode.AMBIENT,
            requires_trucks=True
        )
    )

    # CRITICAL: Test node with BOTH storage modes!
    demand_node = UnifiedNode(
        id="6104",
        name="NSW Hub (BOTH modes + Demand)",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            has_demand=True,
            can_store=True,
            storage_mode=StorageMode.BOTH,  # BOTH ambient and frozen!
            requires_trucks=False
        )
    )

    nodes = [mfg_node, demand_node]

    # Route
    route = UnifiedRoute(
        id="6122_to_6104",
        origin_node_id="6122",
        destination_node_id="6104",
        transport_mode=TransportMode.AMBIENT,
        transit_days=1,
        cost_per_unit=0.5
    )

    routes = [route]

    # Forecast - demand on day 28
    forecast = Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="6104",
                product_id="GFSL",
                forecast_date=date(2025, 2, 1) + timedelta(days=27),  # Day 28
                quantity=8556  # Matches the validation test
            )
        ]
    )

    # Labor calendar - simple setup
    labor_days = []
    for i in range(30):
        d = date(2025, 2, 1) + timedelta(days=i)
        labor_days.append(LaborDay(
            date=d,
            is_fixed_day=True,
            fixed_hours=12,
            overtime_hours=2,
            regular_rate=25,
            overtime_rate=37.5,
            non_fixed_rate=50,
            minimum_hours=4
        ))

    labor_calendar = LaborCalendar(name="Test Calendar", labor_days=labor_days)

    # Costs
    cost_structure = CostStructure(
        production_cost_per_unit=1.0,
        shortage_penalty_per_unit=10.0
    )

    return nodes, routes, forecast, labor_calendar, cost_structure


def analyze_cohort_gap():
    """Analyze which cohorts have inventory but aren't in demand_cohort_index."""

    print("=" * 80)
    print("COHORT GAP ANALYSIS")
    print("=" * 80)

    nodes, routes, forecast, labor_calendar, cost_structure = create_test_data()

    # Create model
    model_instance = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=date(2025, 2, 1),
        end_date=date(2025, 2, 28),
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True
    )

    # Build Pyomo model to generate indices
    print("\nBuilding model to generate indices...")
    pyomo_model = model_instance.build_model()

    # Extract day 28
    day_28 = date(2025, 2, 28)

    print(f"\n{'='*80}")
    print(f"ANALYZING DAY 28: {day_28}")
    print(f"{'='*80}")

    # Find all cohorts for 6104 GFSL on day 28
    cohorts_on_day_28 = set()
    for (node_id, prod, prod_date, curr_date, state) in model_instance.cohort_index_set:
        if node_id == "6104" and prod == "GFSL" and curr_date == day_28:
            cohorts_on_day_28.add((node_id, prod, prod_date, curr_date, state))

    print(f"\n1. COHORTS IN cohort_index_set for 6104/GFSL/day_28:")
    print(f"   Total: {len(cohorts_on_day_28)}")
    for cohort in sorted(cohorts_on_day_28):
        node_id, prod, prod_date, curr_date, state = cohort
        age = (curr_date - prod_date).days
        print(f"   - Prod: {prod_date}, Age: {age}d, State: {state}")

    # Find cohorts in demand_cohort_index for 6104 GFSL day 28
    demand_cohorts_day_28 = set()
    for (node_id, prod, prod_date, demand_date) in model_instance.demand_cohort_index_set:
        if node_id == "6104" and prod == "GFSL" and demand_date == day_28:
            demand_cohorts_day_28.add((node_id, prod, prod_date))

    print(f"\n2. COHORTS IN demand_cohort_index_set for 6104/GFSL/day_28:")
    print(f"   Total: {len(demand_cohorts_day_28)}")
    for (node_id, prod, prod_date) in sorted(demand_cohorts_day_28):
        age = (day_28 - prod_date).days
        print(f"   - Prod: {prod_date}, Age: {age}d")

    # Find the GAP: cohorts in cohort_index but NOT in demand_cohort_index
    # Need to extract (node, prod, prod_date) from cohort tuples
    cohort_prod_dates = set(
        (node_id, prod, prod_date)
        for (node_id, prod, prod_date, curr_date, state) in cohorts_on_day_28
    )

    gap_cohorts = cohort_prod_dates - demand_cohorts_day_28

    print(f"\n3. GAP COHORTS (in cohort_index but NOT in demand_cohort_index):")
    print(f"   Total: {len(gap_cohorts)}")
    for (node_id, prod, prod_date) in sorted(gap_cohorts):
        age = (day_28 - prod_date).days
        print(f"   - Prod: {prod_date}, Age: {age}d")

        # Check which states this cohort has
        states_for_this_cohort = [
            state for (n, p, pd, cd, state) in cohorts_on_day_28
            if n == node_id and p == prod and pd == prod_date
        ]
        print(f"     States: {states_for_this_cohort}")

    # Analyze shelf life rules
    print(f"\n4. SHELF LIFE ANALYSIS:")
    print(f"   Shelf life constants:")
    print(f"   - FROZEN_SHELF_LIFE = {model_instance.FROZEN_SHELF_LIFE} days")
    print(f"   - AMBIENT_SHELF_LIFE = {model_instance.AMBIENT_SHELF_LIFE} days")
    print(f"   - THAWED_SHELF_LIFE = {model_instance.THAWED_SHELF_LIFE} days")

    # Check node 6104 storage mode
    node_6104 = model_instance.nodes["6104"]
    print(f"\n   Node 6104 storage capabilities:")
    print(f"   - Supports ambient: {node_6104.supports_ambient_storage()}")
    print(f"   - Supports frozen: {node_6104.supports_frozen_storage()}")
    print(f"   - Supports both: {node_6104.supports_both_storage_modes()}")

    # Determine shelf life used for demand_cohort_index
    if node_6104.supports_ambient_storage():
        shelf_life_for_demand = min(
            model_instance.AMBIENT_SHELF_LIFE,
            model_instance.THAWED_SHELF_LIFE
        )
        print(f"\n   Shelf life for demand_cohort_index (min of ambient/thawed): {shelf_life_for_demand} days")

    # Determine shelf life used for cohort_index (ambient state)
    shelf_life_for_cohort = min(
        model_instance.AMBIENT_SHELF_LIFE,
        model_instance.THAWED_SHELF_LIFE
    )
    print(f"   Shelf life for cohort_index (ambient state): {shelf_life_for_cohort} days")

    # Check each gap cohort's age
    print(f"\n5. GAP COHORT AGE CHECK:")
    for (node_id, prod, prod_date) in sorted(gap_cohorts):
        age = (day_28 - prod_date).days
        exceeds_demand_shelf_life = age > shelf_life_for_demand
        within_cohort_shelf_life = age <= shelf_life_for_cohort

        print(f"   Prod: {prod_date}, Age: {age}d")
        print(f"     - Exceeds demand shelf life ({shelf_life_for_demand}d): {exceeds_demand_shelf_life}")
        print(f"     - Within cohort shelf life ({shelf_life_for_cohort}d): {within_cohort_shelf_life}")
        print(f"     - MISMATCH: {within_cohort_shelf_life and exceeds_demand_shelf_life}")

    # Final diagnosis
    print(f"\n{'='*80}")
    print("DIAGNOSIS:")
    print(f"{'='*80}")

    if len(gap_cohorts) > 0:
        print(f"\n❌ BUG CONFIRMED: {len(gap_cohorts)} cohorts have inventory but can't satisfy demand!")
        print("\nRoot Cause:")
        print("  Both cohort_index_set and demand_cohort_index_set use the SAME shelf life")
        print(f"  (min of {model_instance.AMBIENT_SHELF_LIFE}d and {model_instance.THAWED_SHELF_LIFE}d = {shelf_life_for_demand}d)")
        print("\n  But there's a subtle difference:")
        print("  - cohort_index_set: Checks 'age_days <= shelf_life' (lines 441-496)")
        print("  - demand_cohort_index_set: Checks 'age_days <= shelf_life' (lines 600-621)")
        print("\n  WAIT - these SHOULD be identical!")
        print("\n  Need to check if there's a difference in HOW these sets are built...")

        # Check the exact logic difference
        print("\n  Checking construction logic...")
        print("\n  cohort_index (_build_cohort_indices, lines 441-496):")
        print("    - Includes initial inventory production dates (before planning horizon)")
        print("    - Uses 'all_prod_dates' which includes dates from initial_inventory")
        print("\n  demand_cohort_index (_build_demand_cohort_indices, lines 579-622):")
        print("    - Also includes initial inventory production dates")
        print("    - Uses 'all_prod_dates' which includes dates from initial_inventory")
        print("\n  Both should include the same production dates...")

        print("\n  HYPOTHESIS: The bug may be in a subtle difference in how")
        print("  all_prod_dates is constructed between the two methods!")

    else:
        print("\n✅ No gap cohorts found - sets are consistent")


if __name__ == "__main__":
    analyze_cohort_gap()
