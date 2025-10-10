#!/usr/bin/env python3
"""
Diagnose Daily Inventory Snapshot using real example data.

This script loads the actual Gfree Forecast.xlsm file and runs a small
optimization to diagnose what's happening with inventory tracking.
"""

import sys
from pathlib import Path
from datetime import date, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.analysis.daily_snapshot import DailySnapshotGenerator


def main():
    print("=" * 80)
    print("DAILY INVENTORY SNAPSHOT DIAGNOSIS WITH REAL DATA")
    print("=" * 80)
    print()

    # Load example data
    excel_file = "data/examples/Gfree Forecast.xlsm"

    print(f"Loading data from: {excel_file}")

    try:
        parser = ExcelParser(excel_file)
        forecast = parser.parse_forecast()
        locations = parser.parse_locations()
        routes = parser.parse_routes()
        labor_calendar = parser.parse_labor_calendar()
        truck_schedules = parser.parse_truck_schedules()
        cost_params = parser.parse_cost_parameters()

        print(f"✓ Loaded {len(forecast.entries)} forecast entries")
        print(f"✓ Loaded {len(locations)} locations")
        print(f"✓ Loaded {len(routes)} routes")
        print(f"✓ Loaded {len(labor_calendar.days)} labor calendar days")
        print(f"✓ Loaded {len(truck_schedules)} truck schedules")
        print()

    except FileNotFoundError:
        print(f"ERROR: Could not find {excel_file}")
        print("Please ensure the example file exists in data/examples/")
        return
    except Exception as e:
        print(f"ERROR loading data: {e}")
        return

    # Use a small date range for testing (7 days)
    start_date = date(2025, 10, 13)  # Monday
    end_date = start_date + timedelta(days=6)  # Sunday

    print(f"Running optimization for {start_date} to {end_date} (7 days)")
    print()

    # Create locations dict
    locations_dict = {loc.id: loc for loc in locations}

    # Find manufacturing site
    manufacturing_site = next(
        (loc for loc in locations if loc.id == "6122"),
        None
    )

    if not manufacturing_site:
        print("ERROR: Could not find manufacturing site (6122)")
        return

    # Filter forecast to date range
    filtered_entries = [
        entry for entry in forecast.entries
        if start_date <= entry.date <= end_date
    ]

    print(f"Forecast entries in range: {len(filtered_entries)}")

    if not filtered_entries:
        print("WARNING: No forecast entries in date range")
        # Add some dummy demand for testing
        from src.models.forecast import ForecastEntry
        filtered_entries = [
            ForecastEntry(
                location_id="6104",
                product_id="176283",
                date=start_date + timedelta(days=2),
                quantity=500.0
            ),
            ForecastEntry(
                location_id="6103",
                product_id="176283",
                date=start_date + timedelta(days=4),
                quantity=300.0
            ),
        ]
        print(f"Added {len(filtered_entries)} dummy forecast entries")

    print()

    # Create model
    print("Creating optimization model...")

    try:
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            manufacturing_site=manufacturing_site,
            locations=locations,
            routes=routes,
            labor_calendar=labor_calendar,
            truck_schedules=truck_schedules,
            cost_structure=cost_params,
            start_date=start_date,
            end_date=end_date,
            allow_shortages=True,  # Allow shortages for feasibility
            shortage_penalty=10000.0
        )

        print("✓ Model created")
        print()

    except Exception as e:
        print(f"ERROR creating model: {e}")
        import traceback
        traceback.print_exc()
        return

    # Solve model
    print("Solving optimization model...")
    print("(This may take 1-2 minutes for 7 days)")
    print()

    try:
        result = model.solve(
            solver_name='cbc',
            time_limit=120,  # 2 minute limit
            verbose=False
        )

        print(f"✓ Solver status: {result.status}")
        print(f"✓ Objective value: ${result.objective_value:,.2f}")
        print()

        if not result.is_optimal():
            print(f"WARNING: Solution is not optimal (status: {result.status})")
            if not result.is_feasible():
                print("ERROR: Solution is not feasible")
                return

    except Exception as e:
        print(f"ERROR solving model: {e}")
        import traceback
        traceback.print_exc()
        return

    # Get shipment plan
    print("Extracting shipment plan from solution...")

    try:
        shipments = model.get_shipment_plan()

        if not shipments:
            print("⚠️  WARNING: No shipments created!")
            print("This could explain why you're not seeing transfers.")
            print()
            print("Possible reasons:")
            print("  - All demand satisfied from initial inventory")
            print("  - Optimization found it cheaper to have shortages")
            print("  - Model constraints prevented shipments")
            print()
        else:
            print(f"✓ Found {len(shipments)} shipments")
            print()

            # Show first few shipments
            print("Sample shipments:")
            for i, ship in enumerate(shipments[:5], 1):
                print(f"  {i}. {ship.origin_id} → {ship.destination_id}")
                print(f"     Product: {ship.product_id}, Quantity: {ship.quantity:,.0f} units")
                print(f"     Delivery: {ship.delivery_date}")
                if ship.route and len(ship.route) > 2:
                    print(f"     Route: {' → '.join(ship.route)}")
                print()

    except Exception as e:
        print(f"ERROR extracting shipments: {e}")
        import traceback
        traceback.print_exc()
        return

    # Get production schedule
    print("Extracting production schedule...")

    try:
        from ui.utils.result_adapter import adapt_optimization_results

        adapted_results = adapt_optimization_results(model, result)
        production_schedule = adapted_results['production_schedule']

        print(f"✓ Production schedule: {len(production_schedule.batches)} batches")

        # Show first few batches
        if production_schedule.batches:
            print()
            print("Sample production batches:")
            for i, batch in enumerate(production_schedule.batches[:3], 1):
                print(f"  {i}. Batch {batch.id}: {batch.quantity:,.0f} units of {batch.product_id}")
                print(f"     Produced: {batch.production_date}")
                print()

    except Exception as e:
        print(f"ERROR extracting production schedule: {e}")
        import traceback
        traceback.print_exc()
        return

    # Generate daily snapshots
    print("=" * 80)
    print("GENERATING DAILY SNAPSHOTS")
    print("=" * 80)
    print()

    try:
        # Use shipments from adapted results if available
        shipments_to_use = adapted_results.get('shipments', shipments or [])

        generator = DailySnapshotGenerator(
            production_schedule=production_schedule,
            shipments=shipments_to_use,
            locations_dict=locations_dict,
            forecast=forecast,
            verbose=False
        )

        snapshots = generator.generate_snapshots(start_date, end_date)

        print(f"✓ Generated {len(snapshots)} daily snapshots")
        print()

    except Exception as e:
        print(f"ERROR generating snapshots: {e}")
        import traceback
        traceback.print_exc()
        return

    # Analyze snapshots
    print("=" * 80)
    print("SNAPSHOT ANALYSIS")
    print("=" * 80)
    print()

    for snapshot_date, snapshot in sorted(snapshots.items()):
        print(f"\n{'='*80}")
        print(f"DATE: {snapshot_date.strftime('%Y-%m-%d %A')}")
        print(f"{'='*80}")

        # Summary
        print(f"\nSummary:")
        print(f"  Total inventory: {snapshot.total_system_inventory:,.0f} units")
        print(f"  In transit: {snapshot.total_in_transit:,.0f} units")
        print(f"  Production today: {len(snapshot.production_activity)} batches")
        print(f"  Demand records: {len(snapshot.demand_satisfied)}")

        # Location inventory (top 5 by quantity)
        print(f"\nLocation Inventory (showing top 5):")
        sorted_locs = sorted(
            snapshot.location_inventory.items(),
            key=lambda x: x[1].total_quantity,
            reverse=True
        )[:5]

        if not sorted_locs:
            print("  ⚠️  NO LOCATIONS - This is the problem!")
        else:
            for loc_id, loc_inv in sorted_locs:
                print(f"  {loc_id}: {loc_inv.total_quantity:,.0f} units")

        # In-transit
        if snapshot.in_transit:
            print(f"\nIn-transit shipments:")
            for transit in snapshot.in_transit[:3]:  # Show first 3
                print(f"  {transit.origin_id} → {transit.destination_id}: {transit.quantity:,.0f} units")

        # Demand
        if snapshot.demand_satisfied:
            print(f"\nDemand satisfaction:")
            for demand in snapshot.demand_satisfied[:3]:  # Show first 3
                fill_pct = demand.fill_rate * 100
                print(f"  {demand.location_id}: {demand.supplied_quantity:,.0f}/{demand.demand_quantity:,.0f} ({fill_pct:.0f}%)")

    # Final diagnosis
    print()
    print("=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    print()

    # Check what we found
    total_shipments = len(shipments_to_use) if shipments_to_use else 0
    total_batches = len(production_schedule.batches) if production_schedule.batches else 0
    total_locations_with_inventory = sum(
        1 for snapshot in snapshots.values()
        for loc_inv in snapshot.location_inventory.values()
        if loc_inv.total_quantity > 0
    )

    print(f"Total shipments created: {total_shipments}")
    print(f"Total production batches: {total_batches}")
    print(f"Location-days with inventory: {total_locations_with_inventory}")
    print()

    if total_shipments == 0:
        print("❌ PROBLEM IDENTIFIED: No shipments were created")
        print()
        print("This explains why you're not seeing transfers between locations.")
        print()
        print("Possible causes:")
        print("  1. Demand is very low relative to initial inventory")
        print("  2. All demand locations have sufficient initial inventory")
        print("  3. Optimization parameters favor not shipping")
        print("  4. Issue with how shipments are extracted from model")
        print()
        print("Recommendation: Check initial_inventory and demand quantities")

    elif total_locations_with_inventory == 0:
        print("❌ PROBLEM IDENTIFIED: No locations have inventory in snapshots")
        print()
        print("This is a data processing issue. Shipments exist but aren't")
        print("being tracked properly in the snapshot generation.")

    else:
        print("✓ System appears to be working")
        print()
        print(f"  - {total_shipments} shipments created")
        print(f"  - {total_batches} production batches")
        print(f"  - Inventory tracked at multiple locations")
        print()
        print("If you're still not seeing this in the UI, the issue might be:")
        print("  1. Wrong date range selected")
        print("  2. UI filtering settings")
        print("  3. Looking at wrong location IDs")


if __name__ == "__main__":
    main()
