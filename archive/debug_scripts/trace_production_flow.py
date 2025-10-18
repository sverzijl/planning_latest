"""Trace production flow in the actual model solution.

This script runs the model and extracts detailed solution data to answer:
1. What is the total demand by node?
2. What is the total shortage by node?
3. What is the total production?
4. Where is inventory accumulating?
5. What shipments are actually created near the end of horizon?
"""

import sys
from datetime import date as Date, timedelta
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.excel_parser import ExcelParser
from src.optimization.unified_node_model import UnifiedNodeModel

def run_and_trace():
    """Run model and extract detailed solution."""

    # Parse input files (matching integration test)
    forecast_path = Path('data/examples/Gfree Forecast.xlsm')
    network_path = Path('data/examples/Network_Config.xlsx')

    print("Parsing input files...")
    parser = ExcelParser(str(forecast_path))
    network_parser = ExcelParser(str(network_path))

    forecast = parser.parse_forecast()
    locations = parser.parse_locations()
    products = parser.parse_products()

    nodes = network_parser.parse_unified_nodes()
    routes = network_parser.parse_unified_routes()
    truck_schedules = network_parser.parse_unified_truck_schedules()
    labor_calendar = network_parser.parse_labor_calendar()
    cost_structure = network_parser.parse_cost_structure()

    # Planning horizon (4 weeks from start date)
    start_date = Date(2025, 10, 16)
    end_date = Date(2025, 11, 13)  # 29 days total

    print(f"\nPlanning Horizon: {start_date} to {end_date}")
    print(f"Total days: {(end_date - start_date).days + 1}")

    # Build model
    print("\nBuilding model...")
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=None,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Extract demand before solving
    print("\n=== DEMAND SUMMARY ===")
    demand_by_node = defaultdict(float)
    demand_by_node_date = defaultdict(lambda: defaultdict(float))
    for (node_id, prod, demand_date), qty in model.demand.items():
        demand_by_node[node_id] += qty
        demand_by_node_date[node_id][demand_date] += qty

    total_demand = sum(demand_by_node.values())
    print(f"\nTotal Demand: {total_demand:,.0f} units")
    print(f"\nDemand by Node:")
    for node_id in sorted(demand_by_node.keys()):
        print(f"  {node_id}: {demand_by_node[node_id]:,.0f} units")

    # Solve
    print("\n\nSolving model...")
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=120,
        mip_gap=0.01,
        tee=False,
    )

    print(f"\nSolve Status: {result.status}")
    print(f"Solve Time: {result.solve_time:.2f}s")

    if result.status not in ['optimal', 'feasible']:
        print("Model did not solve successfully!")
        return

    # Extract solution
    solution = model.solution
    production_by_date_product = solution.get('production_by_date_product', {})
    shortages_by_dest_product_date = solution.get('shortages_by_dest_product_date', {})
    cohort_inventory = solution.get('cohort_inventory', {})
    shipments_by_route = solution.get('shipments_by_route_product_date', {})

    # Calculate production totals
    print("\n\n=== PRODUCTION SUMMARY ===")
    total_production = sum(production_by_date_product.values())
    print(f"\nTotal Production: {total_production:,.0f} units")

    # Production by date
    production_by_date = defaultdict(float)
    for (date_val, prod), qty in production_by_date_product.items():
        production_by_date[date_val] += qty

    print(f"\nProduction by Date:")
    for date_val in sorted(production_by_date.keys())[:10]:  # First 10 days
        print(f"  {date_val}: {production_by_date[date_val]:,.0f} units")
    if len(production_by_date) > 10:
        print(f"  ... ({len(production_by_date) - 10} more dates)")

    # Calculate shortages
    print("\n\n=== SHORTAGE SUMMARY ===")
    shortage_by_node = defaultdict(float)
    shortage_by_node_date = defaultdict(lambda: defaultdict(float))
    for (node_id, prod, demand_date), qty in shortages_by_dest_product_date.items():
        shortage_by_node[node_id] += qty
        shortage_by_node_date[node_id][demand_date] += qty

    total_shortage = sum(shortage_by_node.values())
    print(f"\nTotal Shortage: {total_shortage:,.0f} units")
    print(f"Fill Rate: {100 * (1 - total_shortage / total_demand):.1f}%")

    print(f"\nShortage by Node:")
    for node_id in sorted(shortage_by_node.keys()):
        node_demand = demand_by_node[node_id]
        node_shortage = shortage_by_node[node_id]
        node_fill_rate = 100 * (1 - node_shortage / node_demand) if node_demand > 0 else 100
        print(f"  {node_id}: {node_shortage:,.0f} / {node_demand:,.0f} ({node_fill_rate:.1f}% fill)")

    # Check shortage timing
    print("\n\nShortage Timing (first/last dates with shortages):")
    for node_id in sorted(shortage_by_node_date.keys()):
        dates_with_shortage = sorted([d for d, qty in shortage_by_node_date[node_id].items() if qty > 0])
        if dates_with_shortage:
            first_date = dates_with_shortage[0]
            last_date = dates_with_shortage[-1]
            print(f"  {node_id}: {first_date} to {last_date} ({len(dates_with_shortage)} dates)")

    # Calculate inventory
    print("\n\n=== INVENTORY SUMMARY ===")
    inventory_by_node = defaultdict(float)
    inventory_by_node_date = defaultdict(lambda: defaultdict(float))
    for (node_id, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
        inventory_by_node[node_id] += qty
        inventory_by_node_date[node_id][curr_date] += qty

    total_inventory = sum(inventory_by_node.values())
    print(f"\nTotal Inventory (across all dates and nodes): {total_inventory:,.0f} units")

    print(f"\nInventory by Node:")
    for node_id in sorted(inventory_by_node.keys()):
        print(f"  {node_id}: {inventory_by_node[node_id]:,.0f} units")

    # End-of-horizon inventory (last 3 days)
    last_3_days = [end_date - timedelta(days=i) for i in range(3)]
    eoh_inventory_by_node = defaultdict(float)
    for (node_id, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
        if curr_date in last_3_days:
            eoh_inventory_by_node[node_id] += qty

    total_eoh_inventory = sum(eoh_inventory_by_node.values())
    print(f"\nEnd-of-Horizon Inventory (last 3 days): {total_eoh_inventory:,.0f} units")
    for node_id in sorted(eoh_inventory_by_node.keys()):
        if eoh_inventory_by_node[node_id] > 0:
            print(f"  {node_id}: {eoh_inventory_by_node[node_id]:,.0f} units")

    # Calculate shipments
    print("\n\n=== SHIPMENT SUMMARY ===")
    shipment_by_origin = defaultdict(float)
    shipment_by_dest = defaultdict(float)
    for (origin, dest, prod, delivery_date), qty in shipments_by_route.items():
        shipment_by_origin[origin] += qty
        shipment_by_dest[dest] += qty

    total_shipments = sum(shipment_by_origin.values())
    print(f"\nTotal Shipments: {total_shipments:,.0f} units")

    print(f"\nShipments by Origin:")
    for origin in sorted(shipment_by_origin.keys()):
        print(f"  {origin}: {shipment_by_origin[origin]:,.0f} units")

    print(f"\nShipments by Destination:")
    for dest in sorted(shipment_by_dest.keys()):
        print(f"  {dest}: {shipment_by_dest[dest]:,.0f} units")

    # Material balance check
    print("\n\n=== MATERIAL BALANCE CHECK ===")
    print(f"Production: {total_production:,.0f}")
    print(f"Demand Satisfied: {total_demand - total_shortage:,.0f}")
    print(f"Shortage: {total_shortage:,.0f}")
    print(f"End-of-Horizon Inventory: {total_eoh_inventory:,.0f}")
    print(f"\nBalance Check:")
    print(f"  Production = Demand Satisfied + EOH Inventory")
    print(f"  {total_production:,.0f} = {total_demand - total_shortage:,.0f} + {total_eoh_inventory:,.0f}")
    print(f"  {total_production:,.0f} = {(total_demand - total_shortage) + total_eoh_inventory:,.0f}")
    balance_diff = total_production - ((total_demand - total_shortage) + total_eoh_inventory)
    print(f"  Difference: {balance_diff:,.0f} (should be ~0 or waste/in-transit)")

    # CRITICAL ANALYSIS
    print("\n\n=== CRITICAL ANALYSIS ===")
    print(f"\n1. Expected Production (based on reachable demand): ~185,000 units")
    print(f"   Actual Production: {total_production:,.0f} units")
    print(f"   Excess Production: {total_production - 185000:,.0f} units")

    print(f"\n2. Expected Shortage (unreachable demand): ~18,000 units")
    print(f"   Actual Shortage: {total_shortage:,.0f} units")
    print(f"   Difference: {total_shortage - 18000:,.0f} units")

    print(f"\n3. End-of-Horizon Inventory: {total_eoh_inventory:,.0f} units")
    print(f"   This inventory CANNOT be used (planning horizon ended)")
    print(f"   It represents wasted production")

    if total_production > 185000:
        print(f"\n⚠️  MODEL IS OVERPRODUCING!")
        print(f"   Producing {total_production - 185000:,.0f} units beyond reachable demand")
        print(f"   Possible causes:")
        print(f"   - Shipments created that violate latest_safe_departure restriction")
        print(f"   - Inventory building at intermediate nodes without demand satisfaction")
        print(f"   - Model has alternate routes not considered in diagnostic")

    if total_eoh_inventory > 10000:
        print(f"\n⚠️  LARGE END-OF-HORIZON INVENTORY!")
        print(f"   {total_eoh_inventory:,.0f} units trapped at end of planning horizon")
        print(f"   Confirms shipment restriction is CREATING waste, not preventing it")

if __name__ == '__main__':
    run_and_trace()
