#!/usr/bin/env python3
"""
Diagnostic script to analyze Daily Inventory Snapshot data from optimization results.

This script helps diagnose why the UI might not be showing:
1. Manufactured products transferring from 6122 to other locations
2. Inventory levels decreasing with demand satisfaction

Run this after an optimization to see what data the Daily Inventory Snapshot actually contains.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.analysis.daily_snapshot import DailySnapshotGenerator


def analyze_snapshot_data(production_schedule, shipments, locations_dict, forecast, start_date, end_date):
    """Analyze daily snapshot data and print diagnostic information."""

    print("=" * 80)
    print("DAILY INVENTORY SNAPSHOT DIAGNOSTIC")
    print("=" * 80)
    print()

    # Generate snapshots
    generator = DailySnapshotGenerator(
        production_schedule=production_schedule,
        shipments=shipments,
        locations_dict=locations_dict,
        forecast=forecast,
        verbose=False  # Set to True for detailed batch tracking
    )

    snapshots = generator.generate_snapshots(start_date, end_date)

    print(f"Generated {len(snapshots)} snapshots from {start_date} to {end_date}")
    print()

    # Analyze each snapshot
    for snapshot_date, snapshot in sorted(snapshots.items()):
        print(f"\n{'=' * 80}")
        print(f"DATE: {snapshot_date.strftime('%Y-%m-%d %A')}")
        print(f"{'=' * 80}")

        # 1. Location Inventory
        print(f"\n📦 LOCATION INVENTORY ({len(snapshot.location_inventory)} locations):")
        print("-" * 80)

        if not snapshot.location_inventory:
            print("  ⚠️  NO LOCATIONS IN SNAPSHOT - This is the bug!")
        else:
            # Sort by total quantity (high to low)
            sorted_locs = sorted(
                snapshot.location_inventory.items(),
                key=lambda x: x[1].total_quantity,
                reverse=True
            )

            for loc_id, loc_inv in sorted_locs:
                if loc_inv.total_quantity > 0:
                    print(f"  {loc_id:20} {loc_inv.total_quantity:10,.0f} units")

                    # Show product breakdown if multiple products
                    if len(loc_inv.by_product) > 1:
                        for prod_id, qty in loc_inv.by_product.items():
                            print(f"    └─ {prod_id}: {qty:,.0f} units")
                else:
                    print(f"  {loc_id:20} {'0':>10} units (empty)")

        # 2. In-Transit Shipments
        print(f"\n🚚 IN-TRANSIT SHIPMENTS ({len(snapshot.in_transit)}):")
        print("-" * 80)

        if not snapshot.in_transit:
            print("  No shipments in transit")
        else:
            for transit in snapshot.in_transit:
                print(f"  {transit.origin_id} → {transit.destination_id}: {transit.quantity:,.0f} units")
                print(f"    Product: {transit.product_id}")
                print(f"    Departed: {transit.departure_date}, Arrives: {transit.expected_arrival_date}")
                print(f"    Days in transit: {transit.days_in_transit}")

        # 3. Production Activity
        print(f"\n🏭 PRODUCTION ACTIVITY ({len(snapshot.production_activity)} batches):")
        print("-" * 80)

        if not snapshot.production_activity:
            print("  No production on this date")
        else:
            for batch in snapshot.production_activity:
                print(f"  Batch {batch.batch_id}: {batch.quantity:,.0f} units of {batch.product_id}")

        # 4. Inflows
        print(f"\n📥 INFLOWS ({len(snapshot.inflows)}):")
        print("-" * 80)

        if not snapshot.inflows:
            print("  No inflows")
        else:
            # Group by type
            by_type = {}
            for flow in snapshot.inflows:
                by_type.setdefault(flow.flow_type, []).append(flow)

            for flow_type, flows in by_type.items():
                print(f"  {flow_type.upper()}:")
                for flow in flows:
                    counterparty = f" from {flow.counterparty}" if flow.counterparty else ""
                    print(f"    {flow.location_id}: {flow.quantity:,.0f} units{counterparty}")

        # 5. Outflows
        print(f"\n📤 OUTFLOWS ({len(snapshot.outflows)}):")
        print("-" * 80)

        if not snapshot.outflows:
            print("  No outflows")
        else:
            # Group by type
            by_type = {}
            for flow in snapshot.outflows:
                by_type.setdefault(flow.flow_type, []).append(flow)

            for flow_type, flows in by_type.items():
                print(f"  {flow_type.upper()}:")
                for flow in flows:
                    counterparty = f" to {flow.counterparty}" if flow.counterparty else ""
                    print(f"    {flow.location_id}: {flow.quantity:,.0f} units{counterparty}")

        # 6. Demand Satisfaction
        print(f"\n📊 DEMAND SATISFACTION ({len(snapshot.demand_satisfied)}):")
        print("-" * 80)

        if not snapshot.demand_satisfied:
            print("  No demand on this date")
        else:
            for demand in snapshot.demand_satisfied:
                fill_rate_pct = demand.fill_rate * 100
                status = "✓ Satisfied" if demand.is_satisfied else "✗ Shortage"

                print(f"  {demand.location_id} - {demand.product_id}:")
                print(f"    Demand: {demand.demand_quantity:,.0f} units")
                print(f"    Supplied: {demand.supplied_quantity:,.0f} units")
                print(f"    Shortage: {demand.shortage_quantity:,.0f} units")
                print(f"    Fill rate: {fill_rate_pct:.1f}% {status}")

        # 7. Summary Statistics
        print(f"\n📈 SUMMARY:")
        print("-" * 80)
        print(f"  Total inventory (on-hand): {snapshot.total_system_inventory:,.0f} units")
        print(f"  Total in-transit: {snapshot.total_in_transit:,.0f} units")
        print(f"  Combined total: {snapshot.total_system_inventory + snapshot.total_in_transit:,.0f} units")

    # Final Summary
    print(f"\n{'=' * 80}")
    print("OVERALL SUMMARY")
    print(f"{'=' * 80}")

    # Count unique locations across all snapshots
    all_locations = set()
    for snapshot in snapshots.values():
        all_locations.update(snapshot.location_inventory.keys())

    print(f"\nTotal unique locations tracked: {len(all_locations)}")
    print(f"Locations: {sorted(all_locations)}")

    # Total production
    total_production = sum(
        batch.quantity
        for snapshot in snapshots.values()
        for batch in snapshot.production_activity
    )
    print(f"\nTotal production across all days: {total_production:,.0f} units")

    # Total demand
    total_demand = sum(
        demand.demand_quantity
        for snapshot in snapshots.values()
        for demand in snapshot.demand_satisfied
    )
    total_supplied = sum(
        demand.supplied_quantity
        for snapshot in snapshots.values()
        for demand in snapshot.demand_satisfied
    )
    total_shortage = sum(
        demand.shortage_quantity
        for snapshot in snapshots.values()
        for demand in snapshot.demand_satisfied
    )

    print(f"\nTotal demand across all days: {total_demand:,.0f} units")
    print(f"Total supplied: {total_supplied:,.0f} units")
    print(f"Total shortage: {total_shortage:,.0f} units")

    if total_demand > 0:
        overall_fill_rate = (total_supplied / total_demand) * 100
        print(f"Overall fill rate: {overall_fill_rate:.1f}%")

    print()


def main():
    """Main entry point for standalone execution."""
    print("\n" + "=" * 80)
    print("DAILY INVENTORY SNAPSHOT DIAGNOSTIC TOOL")
    print("=" * 80)
    print()
    print("This script analyzes Daily Inventory Snapshot data to diagnose UI issues.")
    print()
    print("Usage:")
    print("  1. Load your optimization results in the Streamlit UI")
    print("  2. In the Python console, get the production_schedule, shipments, etc.")
    print("  3. Call: analyze_snapshot_data(production_schedule, shipments, ...)")
    print()
    print("Or integrate this into your UI code to print diagnostics.")
    print()
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
