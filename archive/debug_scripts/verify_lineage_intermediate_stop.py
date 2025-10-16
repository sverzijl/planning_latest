"""Verify that Lineage intermediate stop is working in optimization model.

This diagnostic:
1. Runs a small optimization problem (2-week horizon)
2. Checks if truck_load variables exist for T3 → Lineage
3. Verifies if any frozen product is being sent to Lineage on Wednesdays
4. Traces the flow from 6122 → Lineage → 6130
"""

from datetime import date, timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel


def verify_lineage_routing():
    """Verify Lineage intermediate stop routing in optimization."""

    print("=" * 80)
    print("LINEAGE INTERMEDIATE STOP VERIFICATION")
    print("=" * 80)
    print()

    # Load data
    print("Loading data...")
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    # Find manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            from src.models.manufacturing import ManufacturingSite
            manufacturing_site = ManufacturingSite(
                id=loc.id,
                name=loc.name,
                type=loc.type,
                storage_mode=loc.storage_mode,
                capacity=loc.capacity,
                latitude=loc.latitude,
                longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    if not manufacturing_site:
        print("ERROR: No manufacturing site found")
        return

    # Find T3 truck index
    t3_idx = None
    for i, truck in enumerate(truck_schedules.schedules):
        if truck.id == 'T3':
            t3_idx = i
            break

    if t3_idx is None:
        print("ERROR: Truck T3 not found!")
        return

    print(f"Found T3 at index {t3_idx}")
    print()

    # Run optimization (2 weeks for speed)
    print("Running optimization (2-week horizon)...")
    print("-" * 80)

    # Get date range from forecast
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=13)  # 2 weeks

    model = IntegratedProductionDistributionModel(
        manufacturing_site=manufacturing_site,
        forecast=forecast,
        locations=locations,
        routes=routes,
        start_date=start_date,
        end_date=end_date,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        truck_schedules=truck_schedules,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=60, mip_gap=0.02)

    print(f"Status: {result.termination_condition}")
    print(f"Solve time: {result.solve_time_seconds:.1f}s")
    print()

    if not result.is_optimal() and not result.is_feasible():
        print(f"ERROR: Model not solved successfully")
        return

    # Extract solution
    solution = model.get_solution()
    if not solution:
        print("ERROR: Could not extract solution")
        return

    # Check 1: Does T3 appear in truck destinations?
    print("CHECK 1: TRUCK DESTINATIONS IN MODEL")
    print("-" * 80)

    # Access the model to check truck_destinations
    pyomo_model = model.model
    if hasattr(pyomo_model, 'truck_destinations'):
        destinations = list(pyomo_model.truck_destinations)
        print(f"Truck destinations defined in model: {', '.join(sorted(destinations))}")
        if 'Lineage' in destinations:
            print("✅ Lineage is included in truck_destinations")
        else:
            print("❌ Lineage is NOT in truck_destinations (intermediate stop not working)")
    else:
        print("WARNING: truck_destinations not found in model")
    print()

    # Check 2: Are there truck_load variables for T3 to Lineage?
    print("CHECK 2: TRUCK_LOAD VARIABLES FOR T3")
    print("-" * 80)

    truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})

    t3_loads_to_lineage = {}
    t3_loads_to_6125 = {}

    for (truck_idx, dest, product, date_val), qty in truck_loads.items():
        if truck_idx == t3_idx:
            if qty > 0.01:
                if dest == 'Lineage':
                    t3_loads_to_lineage[(date_val, product)] = qty
                elif dest == '6125':
                    t3_loads_to_6125[(date_val, product)] = qty

    print(f"T3 loads to Lineage: {len(t3_loads_to_lineage)} shipments")
    if t3_loads_to_lineage:
        print("Details:")
        for (date_val, product), qty in sorted(t3_loads_to_lineage.items()):
            print(f"  {date_val} ({date_val.strftime('%A'):9s}): {product} - {qty:,.0f} units")
        print(f"  Total to Lineage: {sum(t3_loads_to_lineage.values()):,.0f} units")
    else:
        print("  ⚠️  No loads to Lineage found in solution")
    print()

    print(f"T3 loads to 6125: {len(t3_loads_to_6125)} shipments")
    if t3_loads_to_6125:
        print("Details:")
        for (date_val, product), qty in sorted(t3_loads_to_6125.items()):
            print(f"  {date_val} ({date_val.strftime('%A'):9s}): {product} - {qty:,.0f} units")
        print(f"  Total to 6125: {sum(t3_loads_to_6125.values()):,.0f} units")
    print()

    # Check 3: Inventory at Lineage
    print("CHECK 3: INVENTORY AT LINEAGE")
    print("-" * 80)

    cohort_inventory = solution.get('cohort_inventory', {})

    lineage_inventory = {}
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
        if loc == 'Lineage' and qty > 0.01:
            if curr_date not in lineage_inventory:
                lineage_inventory[curr_date] = {}
            if state not in lineage_inventory[curr_date]:
                lineage_inventory[curr_date][state] = 0.0
            lineage_inventory[curr_date][state] += qty

    if lineage_inventory:
        print(f"Lineage has inventory on {len(lineage_inventory)} dates:")
        for curr_date in sorted(lineage_inventory.keys()):
            total = sum(lineage_inventory[curr_date].values())
            states = ', '.join(f"{state}: {qty:,.0f}" for state, qty in lineage_inventory[curr_date].items())
            print(f"  {curr_date} ({curr_date.strftime('%A'):9s}): {total:,.0f} units [{states}]")
    else:
        print("⚠️  No inventory found at Lineage in solution")
    print()

    # Check 4: Shipments from Lineage to 6130 (WA)
    print("CHECK 4: SHIPMENTS FROM LINEAGE TO 6130 (WA)")
    print("-" * 80)

    # Check for shipments on the Lineage → 6130 leg
    leg_shipments = solution.get('shipments_by_leg_product_date', {})

    lineage_to_6130 = {}
    # Format: {((origin, dest), product, date): qty}
    for ((origin, dest), product, date_val), qty in leg_shipments.items():
        if origin == 'Lineage' and dest == '6130' and qty > 0.01:
            lineage_to_6130[(date_val, product)] = qty

    if lineage_to_6130:
        print(f"Found {len(lineage_to_6130)} shipments from Lineage to 6130:")
        for (date_val, product), qty in sorted(lineage_to_6130.items()):
            print(f"  {date_val} ({date_val.strftime('%A'):9s}): {product} - {qty:,.0f} units")
        print(f"  Total shipped to WA: {sum(lineage_to_6130.values()):,.0f} units")
    else:
        print("⚠️  No shipments from Lineage to 6130 found")
        print("     (This could mean WA demand is being served via direct frozen route,")
        print("      or there's no WA demand in this 2-week period)")
    print()

    # Check 5: Wednesday T3 capacity allocation
    print("CHECK 5: WEDNESDAY T3 CAPACITY ALLOCATION")
    print("-" * 80)

    wednesdays = [d for d in sorted(set(d for (d, _) in t3_loads_to_lineage.keys()) |
                                     set(d for (d, _) in t3_loads_to_6125.keys()))
                  if d.weekday() == 2]

    if wednesdays:
        for wed_date in wednesdays:
            print(f"{wed_date} (Wednesday):")

            lineage_total = sum(qty for (d, p), qty in t3_loads_to_lineage.items() if d == wed_date)
            hub_total = sum(qty for (d, p), qty in t3_loads_to_6125.items() if d == wed_date)
            grand_total = lineage_total + hub_total

            print(f"  Lineage: {lineage_total:7,.0f} units ({lineage_total/14080*100:5.1f}% of truck capacity)")
            print(f"  6125:    {hub_total:7,.0f} units ({hub_total/14080*100:5.1f}% of truck capacity)")
            print(f"  Total:   {grand_total:7,.0f} units ({grand_total/14080*100:5.1f}% utilization)")

            if grand_total > 14080.01:
                print("  ❌ ERROR: Exceeds truck capacity!")
            elif lineage_total > 0:
                print("  ✅ Split allocation working (sending to both destinations)")
            elif hub_total > 0:
                print("  ⚠️  Only sending to 6125 (no Lineage load)")
            print()
    else:
        print("No Wednesday loads found in this period")
    print()

    # Summary
    print("SUMMARY")
    print("=" * 80)

    issues = []

    if not t3_loads_to_lineage:
        issues.append("No loads to Lineage via T3 (may be economically unnecessary in this period)")
    else:
        print(f"✅ T3 successfully loading to Lineage: {sum(t3_loads_to_lineage.values()):,.0f} units total")

    if not lineage_inventory:
        issues.append("No inventory accumulation at Lineage (intermediate stop may not be working)")
    else:
        print(f"✅ Lineage holding inventory: peak of {max(sum(v.values()) for v in lineage_inventory.values()):,.0f} units")

    if not lineage_to_6130:
        issues.append("No shipments from Lineage to 6130 (WA demand may be served differently)")
    else:
        print(f"✅ Lineage → 6130 flow working: {sum(lineage_to_6130.values()):,.0f} units to WA")

    print()

    if issues:
        print("NOTES:")
        for issue in issues:
            print(f"  ⚠️  {issue}")
        print()
        print("This may be normal if:")
        print("  - WA demand is low in this 2-week period")
        print("  - Direct frozen route is more cost-effective")
        print("  - Existing Lineage inventory is sufficient")
    else:
        print("✅ All Lineage intermediate stop functionality appears to be working!")


if __name__ == "__main__":
    verify_lineage_routing()
