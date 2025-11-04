#!/usr/bin/env python3
"""
Diagnostic script to investigate zero production issue.

This script will:
1. Load the model data
2. Print initial inventory totals
3. Print demand totals
4. Compare initial inventory vs demand
5. Check for any data loading issues
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Don't import models, just use parser directly
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.excel_parser import ExcelParser


def diagnose_zero_production():
    """Diagnose why the model produces zero production."""

    print("=" * 80)
    print("ZERO PRODUCTION DIAGNOSTIC")
    print("=" * 80)

    # Load data files
    forecast_file = "data/examples/Gluten Free Forecast - Latest.xlsm"
    network_file = "data/examples/Network_Config.xlsx"

    print(f"\n1. Loading data files...")
    print(f"   Forecast: {forecast_file}")
    print(f"   Network: {network_file}")

    parser = ExcelParser()

    # Parse forecast
    print(f"\n2. Parsing forecast...")
    products, demand_forecast = parser.parse_forecast(forecast_file)
    print(f"   Products: {len(products)}")
    print(f"   Demand records: {len(demand_forecast)}")

    # Parse network config
    print(f"\n3. Parsing network configuration...")
    result = parser.parse_network_config(network_file)
    locations = result['locations']
    routes = result['routes']
    labor_calendar = result['labor_calendar']
    truck_schedules = result['truck_schedules']
    cost_structure = result['cost_structure']
    initial_inventory_raw = result.get('initial_inventory', {})
    inventory_snapshot_date = result.get('inventory_snapshot_date')

    print(f"   Locations: {len(locations)}")
    print(f"   Routes: {len(routes)}")
    print(f"   Truck schedules: {len(truck_schedules)}")
    print(f"   Inventory snapshot date: {inventory_snapshot_date}")

    # Analyze initial inventory
    print(f"\n4. INITIAL INVENTORY ANALYSIS")
    print(f"   Raw initial inventory records: {len(initial_inventory_raw)}")

    if initial_inventory_raw:
        print(f"\n   Sample initial inventory records:")
        for i, (key, value) in enumerate(list(initial_inventory_raw.items())[:10]):
            print(f"      {key}: {value}")
            if i >= 9:
                break

        # Calculate totals by state
        totals_by_state = {}
        totals_by_node = {}

        for (node_id, prod, state), qty in initial_inventory_raw.items():
            totals_by_state[state] = totals_by_state.get(state, 0) + qty
            totals_by_node[node_id] = totals_by_node.get(node_id, 0) + qty

        print(f"\n   Initial inventory totals by state:")
        for state, total in totals_by_state.items():
            print(f"      {state}: {total:,.0f} units")

        print(f"\n   Initial inventory totals by node:")
        for node_id, total in sorted(totals_by_node.items(), key=lambda x: -x[1]):
            print(f"      {node_id}: {total:,.0f} units")
    else:
        print(f"   ⚠️  NO INITIAL INVENTORY FOUND!")

    # Analyze demand
    print(f"\n5. DEMAND ANALYSIS")

    # Calculate demand totals
    total_demand = sum(qty for qty in demand_forecast.values())

    # Get date range
    demand_dates = sorted(set(date for (node, prod, date) in demand_forecast.keys()))
    if demand_dates:
        min_date = min(demand_dates)
        max_date = max(demand_dates)
        print(f"   Date range: {min_date} to {max_date} ({(max_date - min_date).days + 1} days)")

    print(f"   Total demand (all products, all dates): {total_demand:,.0f} units")

    # Demand by node
    demand_by_node = {}
    for (node_id, prod, date), qty in demand_forecast.items():
        demand_by_node[node_id] = demand_by_node.get(node_id, 0) + qty

    print(f"\n   Demand totals by node:")
    for node_id, total in sorted(demand_by_node.items(), key=lambda x: -x[1]):
        print(f"      {node_id}: {total:,.0f} units")

    # Demand by product
    demand_by_product = {}
    for (node_id, prod, date), qty in demand_forecast.items():
        demand_by_product[prod] = demand_by_product.get(prod, 0) + qty

    print(f"\n   Top 10 products by demand:")
    for i, (prod, total) in enumerate(sorted(demand_by_product.items(), key=lambda x: -x[1])[:10]):
        print(f"      {i+1}. {prod[:50]}: {total:,.0f} units")

    # Compare initial inventory to demand
    print(f"\n6. INITIAL INVENTORY vs DEMAND COMPARISON")

    if initial_inventory_raw:
        total_initial_inv = sum(initial_inventory_raw.values())
        print(f"   Total initial inventory: {total_initial_inv:,.0f} units")
        print(f"   Total demand:           {total_demand:,.0f} units")
        print(f"   Coverage ratio:         {total_initial_inv / total_demand:.1%}")

        if total_initial_inv >= total_demand:
            print(f"\n   ⚠️  CRITICAL: Initial inventory >= total demand!")
            print(f"   This could explain zero production if holding costs are low.")
        else:
            print(f"\n   ✓  Initial inventory < demand (production should be needed)")
    else:
        print(f"   No initial inventory to compare")

    # Check for specific issue: Are there products in initial inventory but not in demand?
    if initial_inventory_raw:
        print(f"\n7. PRODUCT MISMATCH CHECK")

        inv_products = set(prod for (node, prod, state) in initial_inventory_raw.keys())
        demand_products = set(prod for (node, prod, date) in demand_forecast.keys())

        print(f"   Products in initial inventory: {len(inv_products)}")
        print(f"   Products in demand:            {len(demand_products)}")

        inv_only = inv_products - demand_products
        demand_only = demand_products - inv_products

        if inv_only:
            print(f"\n   Products in inventory but NOT in demand ({len(inv_only)}):")
            for prod in list(inv_only)[:5]:
                print(f"      - {prod[:60]}")
                inv_qty = sum(qty for (n, p, s), qty in initial_inventory_raw.items() if p == prod)
                print(f"        Total inventory: {inv_qty:,.0f} units")
            if len(inv_only) > 5:
                print(f"      ... and {len(inv_only) - 5} more")

        if demand_only:
            print(f"\n   Products in demand but NOT in inventory ({len(demand_only)}):")
            for prod in list(demand_only)[:5]:
                print(f"      - {prod[:60]}")
                demand_qty = sum(qty for (n, p, d), qty in demand_forecast.items() if p == prod)
                print(f"        Total demand: {demand_qty:,.0f} units")
            if len(demand_only) > 5:
                print(f"      ... and {len(demand_only) - 5} more")

        if not inv_only and not demand_only:
            print(f"   ✓  All products match between inventory and demand")

    # Check for date mismatch
    print(f"\n8. DATE ALIGNMENT CHECK")
    if inventory_snapshot_date and demand_dates:
        first_demand_date = min(demand_dates)
        print(f"   Inventory snapshot date: {inventory_snapshot_date}")
        print(f"   First demand date:       {first_demand_date}")

        days_diff = (first_demand_date - inventory_snapshot_date).days
        print(f"   Days between:            {days_diff} days")

        if days_diff < 0:
            print(f"   ⚠️  WARNING: Inventory snapshot is AFTER first demand date!")
        elif days_diff > 7:
            print(f"   ⚠️  WARNING: Large gap between inventory snapshot and demand start")
        else:
            print(f"   ✓  Dates are reasonably aligned")

    print(f"\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    diagnose_zero_production()
