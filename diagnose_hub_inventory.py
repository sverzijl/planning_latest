"""Diagnose hub inventory in optimization solutions.

Investigates why daily snapshot shows no inventory at hub locations like 6104, 6110.
"""

from datetime import date, timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel


def diagnose_hub_inventory():
    """Check hub inventory in optimization model and daily snapshot."""

    print("=" * 80)
    print("HUB INVENTORY DIAGNOSTIC")
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

    # Identify hub locations
    hub_locations = ['6104', '6125']  # NSW/ACT and VIC/TAS/SA hubs
    print(f"Hub locations: {', '.join(hub_locations)}")
    print()

    # Run optimization (2 weeks for speed)
    print("Running optimization (2-week horizon)...")
    print("-" * 80)

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

    print("CHECK 1: HUB INVENTORY IN MODEL SOLUTION")
    print("-" * 80)

    # Check cohort inventory at hubs
    cohort_inventory = solution.get('cohort_inventory', {})

    hub_inventory_by_date = {}
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
        if loc in hub_locations and qty > 0.01:
            if (loc, curr_date) not in hub_inventory_by_date:
                hub_inventory_by_date[(loc, curr_date)] = {'total': 0.0, 'by_state': {}, 'by_product': {}}
            hub_inventory_by_date[(loc, curr_date)]['total'] += qty
            hub_inventory_by_date[(loc, curr_date)]['by_state'][state] = \
                hub_inventory_by_date[(loc, curr_date)]['by_state'].get(state, 0.0) + qty
            hub_inventory_by_date[(loc, curr_date)]['by_product'][prod] = \
                hub_inventory_by_date[(loc, curr_date)]['by_product'].get(prod, 0.0) + qty

    if hub_inventory_by_date:
        print(f"✅ Found hub inventory on {len(hub_inventory_by_date)} location-date combinations:")
        print()

        for loc in hub_locations:
            loc_dates = [(l, d) for (l, d) in hub_inventory_by_date.keys() if l == loc]
            if loc_dates:
                print(f"Hub {loc}:")
                for (l, curr_date) in sorted(loc_dates, key=lambda x: x[1]):
                    inv_data = hub_inventory_by_date[(l, curr_date)]
                    states = ', '.join(f"{s}: {q:,.0f}" for s, q in inv_data['by_state'].items())
                    products = ', '.join(f"{p}: {q:,.0f}" for p, q in inv_data['by_product'].items())
                    print(f"  {curr_date} ({curr_date.strftime('%A'):9s}): {inv_data['total']:7,.0f} units")
                    print(f"    States: {states}")
                    print(f"    Products: {products}")
                print()
    else:
        print("❌ NO hub inventory found in model solution!")
        print("   This suggests the model is not buffering inventory at hubs.")
        print()

    # Check flows into/out of hubs
    print("CHECK 2: SHIPMENT FLOWS THROUGH HUBS")
    print("-" * 80)

    leg_shipments = solution.get('shipments_by_leg_product_date', {})

    # Inbound to hubs (from manufacturing)
    print("Inbound to hubs (from 6122):")
    for loc in hub_locations:
        inbound = {}
        for ((origin, dest), product, date_val), qty in leg_shipments.items():
            if dest == loc and origin == '6122' and qty > 0.01:
                if date_val not in inbound:
                    inbound[date_val] = 0.0
                inbound[date_val] += qty

        if inbound:
            print(f"  {loc}:")
            for date_val in sorted(inbound.keys()):
                print(f"    {date_val} ({date_val.strftime('%A'):9s}): {inbound[date_val]:7,.0f} units")
        else:
            print(f"  {loc}: No inbound shipments")
    print()

    # Outbound from hubs (to spokes)
    print("Outbound from hubs (to spokes):")
    for loc in hub_locations:
        outbound = {}
        for ((origin, dest), product, date_val), qty in leg_shipments.items():
            if origin == loc and dest != '6122' and qty > 0.01:
                if (date_val, dest) not in outbound:
                    outbound[(date_val, dest)] = 0.0
                outbound[(date_val, dest)] += qty

        if outbound:
            print(f"  {loc}:")
            for (date_val, dest) in sorted(outbound.keys()):
                print(f"    {date_val} ({date_val.strftime('%A'):9s}) → {dest}: {outbound[(date_val, dest)]:7,.0f} units")
        else:
            print(f"  {loc}: No outbound shipments")
    print()

    # Check if model has inventory variables for hubs
    print("CHECK 3: INVENTORY VARIABLES FOR HUBS")
    print("-" * 80)

    inventory_ambient = solution.get('inventory_ambient_by_loc_product_date', {})
    inventory_frozen = solution.get('inventory_frozen_by_loc_product_date', {})

    for loc in hub_locations:
        ambient_dates = [d for (l, p, d), qty in inventory_ambient.items() if l == loc and qty > 0.01]
        frozen_dates = [d for (l, p, d), qty in inventory_frozen.items() if l == loc and qty > 0.01]

        print(f"Hub {loc}:")
        if ambient_dates:
            print(f"  Ambient inventory on {len(set(ambient_dates))} dates")
            for d in sorted(set(ambient_dates)):
                total = sum(qty for (l, p, dt), qty in inventory_ambient.items() if l == loc and dt == d)
                print(f"    {d} ({d.strftime('%A'):9s}): {total:7,.0f} units")
        else:
            print(f"  No ambient inventory")

        if frozen_dates:
            print(f"  Frozen inventory on {len(set(frozen_dates))} dates")
            for d in sorted(set(frozen_dates)):
                total = sum(qty for (l, p, dt), qty in inventory_frozen.items() if l == loc and dt == d)
                print(f"    {d} ({d.strftime('%A'):9s}): {total:7,.0f} units")
        else:
            print(f"  No frozen inventory")
        print()

    # Check daily snapshot extraction
    print("CHECK 4: DAILY SNAPSHOT EXTRACTION")
    print("-" * 80)

    from src.analysis.daily_snapshot import DailySnapshotGenerator

    # Convert locations to dict
    locations_dict = {loc.id: loc for loc in locations}

    # Create shipments
    shipments = model.extract_shipments()

    # Create production schedule
    production_schedule = model.extract_production_schedule()

    # Create snapshot generator with model solution
    generator = DailySnapshotGenerator(
        production_schedule=production_schedule,
        shipments=shipments,
        locations_dict=locations_dict,
        forecast=forecast,
        model_solution=solution
    )

    # Check snapshots for a few dates
    test_dates = sorted(set(d for (l, d) in hub_inventory_by_date.keys()))[:5]

    if test_dates:
        print(f"Testing daily snapshot for {len(test_dates)} dates with hub inventory:")
        print()

        for test_date in test_dates:
            snapshot = generator._generate_single_snapshot(test_date)

            print(f"Date: {test_date} ({test_date.strftime('%A')})")
            for loc in hub_locations:
                if loc in snapshot.location_inventory:
                    inv = snapshot.location_inventory[loc]
                    if inv.total_quantity > 0.01:
                        print(f"  {loc}: {inv.total_quantity:7,.0f} units ({len(inv.batches)} batches)")
                    else:
                        print(f"  {loc}: 0 units (EMPTY)")
                else:
                    print(f"  {loc}: NOT IN SNAPSHOT")
            print()
    else:
        print("No dates with hub inventory found to test")

    # Summary
    print("SUMMARY")
    print("=" * 80)

    if hub_inventory_by_date:
        print(f"✅ Model DOES create hub inventory")
        print(f"   Found inventory at hubs on {len(set(d for (l, d) in hub_inventory_by_date.keys()))} dates")
    else:
        print(f"❌ Model does NOT create hub inventory")
        print(f"   Product flows through hubs without buffering (same-day transit)")

    print()
    print("Possible issues:")
    print("  1. Model may be optimizing for same-day transit through hubs")
    print("  2. Hub inventory may be zero at end-of-day (all shipped out)")
    print("  3. Daily snapshot may not be extracting hub inventory correctly")
    print("  4. Batch tracking cohort logic may have bugs for hub locations")


if __name__ == "__main__":
    diagnose_hub_inventory()
