#!/usr/bin/env python3
"""Diagnostic: Analyze end-of-horizon inventory for shelf life stranding.

This script tests the hypothesis that the 14,387 units of end-of-horizon inventory
are stranded because they've aged beyond the 14-day shelf life limit.

Hypothesis:
- Production from early in horizon (days 1-14) creates inventory
- Some isn't fully consumed by early demand
- By day 28, it's aged 14-28 days
- Shelf life limit = 14 days (min of AMBIENT_SHELF_LIFE and THAWED_SHELF_LIFE)
- Age > shelf life → can't be used for demand → becomes waste
"""

from datetime import date as Date, timedelta
from typing import Dict, Tuple

from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


def analyze_shelf_life_stranding():
    """Analyze end-of-horizon inventory to identify shelf-life-stranded units."""

    print("=" * 80)
    print("SHELF LIFE STRANDING ANALYSIS")
    print("=" * 80)

    # Parse input data
    print("\n1. Loading data...")
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Find manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    assert manufacturing_site is not None, "No manufacturing site found"

    # Setup 4-week planning horizon
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=27)  # 4 weeks = 28 days

    print(f"   Planning horizon: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")

    # Convert legacy data to unified format
    print("\n2. Converting to unified format...")
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Build and solve model
    print("\n3. Building and solving UnifiedNodeModel...")
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory={},
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(solver_name='cbc', mip_gap=0.01, time_limit_seconds=120, tee=False)

    if not result.is_optimal() and not result.is_feasible():
        print(f"   ERROR: Model solve failed with termination: {result.termination_condition}")
        return

    print(f"   Solve status: {result.termination_condition}")
    print(f"   Solve time: {result.solve_time_seconds:.2f}s")

    # Get solution
    solution = model.get_solution()
    cohort_inventory = solution.get('cohort_inventory', {})

    print(f"\n4. Analyzing end-of-horizon inventory...")

    # Extract inventory on last day
    end_inv = {k: v for k, v in cohort_inventory.items() if k[3] == end_date and v > 0.01}

    total_end_inv = sum(end_inv.values())
    print(f"   Total end-of-horizon inventory: {total_end_inv:,.0f} units")

    # CRITICAL: Analyze by production date and age
    print(f"\n5. Analyzing by production date and age...")

    by_prod_date = {}
    by_age_bucket = {}

    for (node, prod, prod_date, curr_date, state), qty in end_inv.items():
        age = (curr_date - prod_date).days

        # By production date
        by_prod_date[prod_date] = by_prod_date.get(prod_date, 0) + qty

        # By age bucket
        if age <= 7:
            bucket = "0-7 days"
        elif age <= 14:
            bucket = "8-14 days"
        elif age <= 21:
            bucket = "15-21 days"
        else:
            bucket = "22+ days"

        by_age_bucket[bucket] = by_age_bucket.get(bucket, 0) + qty

    # Print production date distribution
    print("\n   Inventory by production date:")
    print("   " + "-" * 60)
    print(f"   {'Production Date':<20} {'Age (days)':<15} {'Quantity':<15}")
    print("   " + "-" * 60)

    for pd in sorted(by_prod_date.keys()):
        age = (end_date - pd).days
        qty = by_prod_date[pd]
        stale_marker = " ** STALE **" if age > 14 else ""
        print(f"   {pd.strftime('%Y-%m-%d'):<20} {age:<15} {qty:>12,.0f}{stale_marker}")

    # Print age bucket distribution
    print("\n   Inventory by age bucket:")
    print("   " + "-" * 60)
    print(f"   {'Age Bucket':<20} {'Quantity':<15} {'% of Total':<15}")
    print("   " + "-" * 60)

    for bucket in ["0-7 days", "8-14 days", "15-21 days", "22+ days"]:
        qty = by_age_bucket.get(bucket, 0)
        pct = (qty / total_end_inv * 100) if total_end_inv > 0 else 0
        print(f"   {bucket:<20} {qty:>12,.0f} {pct:>12.1f}%")

    # CRITICAL CALCULATION: Identify dead inventory (age > 14 days)
    print(f"\n6. Calculating dead inventory (age > 14 days)...")

    dead_inventory = sum(
        qty for (node, prod, pd, cd, state), qty in end_inv.items()
        if (cd - pd).days > 14  # Aged beyond shelf life
    )

    usable_inventory = total_end_inv - dead_inventory

    print(f"   Dead inventory (age > 14 days):   {dead_inventory:>12,.0f} units ({dead_inventory / total_end_inv * 100:.1f}%)")
    print(f"   Usable inventory (age <= 14 days): {usable_inventory:>12,.0f} units ({usable_inventory / total_end_inv * 100:.1f}%)")

    # WHY MODEL PRODUCES UNITS IT KNOWS WILL EXPIRE
    print(f"\n7. Explaining why model produces units that expire...")
    print("   " + "-" * 76)

    # Extract demand over horizon
    total_demand = sum(model.demand.values())
    total_production = sum(solution.get('production_by_date_product', {}).values())

    print(f"   Total demand over horizon:      {total_demand:>12,.0f} units")
    print(f"   Total production over horizon:  {total_production:>12,.0f} units")
    print(f"   Overproduction:                 {total_production - total_demand:>12,.0f} units")

    # Check if dead inventory matches hypothesis
    print(f"\n8. HYPOTHESIS VALIDATION:")
    print("   " + "-" * 76)

    hypothesis_match = abs(dead_inventory - 14387) < 100  # Within 100 units

    if hypothesis_match:
        print("   HYPOTHESIS CONFIRMED: Dead inventory (~14,387 units) is aged > 14 days")
        print("   ")
        print("   ROOT CAUSE:")
        print("   - Model produces on days 1-13 to satisfy early demand (days 1-20)")
        print("   - Some inventory remains unused (slight overproduction or positioning)")
        print("   - By day 28, this inventory is 15-28 days old")
        print("   - TOO OLD to consume (not in demand_cohort_index_set)")
        print("   - Can't be disposed (no waste variable/constraint)")
        print("   - Sits as end-of-horizon waste")
    else:
        print(f"   HYPOTHESIS REJECTED: Dead inventory ({dead_inventory:,.0f}) != 14,387 units")
        print("   Need to investigate other causes for end-of-horizon inventory")

    # Additional insights: Production date of dead inventory
    print(f"\n9. Dead inventory by production date:")
    print("   " + "-" * 60)

    dead_by_prod_date = {}
    for (node, prod, pd, cd, state), qty in end_inv.items():
        age = (cd - pd).days
        if age > 14:
            dead_by_prod_date[pd] = dead_by_prod_date.get(pd, 0) + qty

    if dead_by_prod_date:
        print(f"   {'Production Date':<20} {'Age (days)':<15} {'Quantity':<15}")
        print("   " + "-" * 60)
        for pd in sorted(dead_by_prod_date.keys()):
            age = (end_date - pd).days
            qty = dead_by_prod_date[pd]
            print(f"   {pd.strftime('%Y-%m-%d'):<20} {age:<15} {qty:>12,.0f}")
    else:
        print("   No dead inventory found!")

    # CRITICAL INSIGHT: Check demand cohort index cutoff
    print(f"\n10. Verifying demand cohort index cutoff...")
    print("   " + "-" * 76)

    # For demand on day 28, what's the oldest production date allowed?
    shelf_life = min(17, 14)  # min(AMBIENT_SHELF_LIFE, THAWED_SHELF_LIFE)
    oldest_prod_date_for_day_28 = end_date - timedelta(days=shelf_life)

    print(f"   Shelf life limit: {shelf_life} days")
    print(f"   Demand date: {end_date.strftime('%Y-%m-%d')}")
    print(f"   Oldest production date allowed: {oldest_prod_date_for_day_28.strftime('%Y-%m-%d')}")
    print(f"   ")
    print(f"   Production from {start_date.strftime('%Y-%m-%d')} to {(oldest_prod_date_for_day_28 - timedelta(days=1)).strftime('%Y-%m-%d')}")
    print(f"   CANNOT satisfy demand on {end_date.strftime('%Y-%m-%d')} (too old)")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    analyze_shelf_life_stranding()
