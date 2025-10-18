#!/usr/bin/env python3
"""Diagnostic script to understand end-of-horizon inventory.

Solves a 4-week model and analyzes inventory on the final day.
"""

from datetime import date, timedelta
from pathlib import Path
from src.parsers.excel_parser import ExcelParser
from src.parsers.unified_data_converter import UnifiedDataConverter
from src.optimization.unified_node_model import UnifiedNodeModel

# Load data
data_dir = Path("data/examples")
forecast_file = data_dir / "Gfree Forecast.xlsm"
network_file = data_dir / "Network_Config.xlsx"

print("Loading data...")
parser = ExcelParser(str(forecast_file), str(network_file))
data = parser.parse()

# Convert to unified format
converter = UnifiedDataConverter()
unified_data = converter.convert(data)

# Set planning horizon (4 weeks from forecast start)
forecast_entries = data['forecast'].entries
forecast_start = min(e.forecast_date for e in forecast_entries)
planning_start = forecast_start
planning_end = planning_start + timedelta(days=27)  # 4 weeks = 28 days (days 0-27)

print(f"\nPlanning Horizon: {planning_start} to {planning_end} (28 days)")

# Create model
model = UnifiedNodeModel(
    nodes=unified_data['nodes'],
    routes=unified_data['routes'],
    forecast=data['forecast'],
    labor_calendar=data['labor_calendar'],
    cost_structure=data['cost_parameters'],
    truck_schedules=unified_data['truck_schedules'],
    start_date=planning_start,
    end_date=planning_end,
    initial_inventory=data.get('initial_inventory', {}),
    inventory_snapshot_date=data.get('inventory_snapshot_date'),
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

# Solve
print("\nSolving model...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=120,
    mip_gap=0.01,
    tee=False
)

print(f"\nSolve Status: {result.status}")
print(f"Solve Time: {result.solve_time:.1f}s")

# Get solution
solution = model.get_solution()

# Extract end-of-horizon inventory
cohort_inventory = solution.get('cohort_inventory', {})

print(f"\n" + "="*80)
print("END-OF-HORIZON INVENTORY ANALYSIS (Day 28: {})".format(planning_end))
print("="*80)

# Filter to last day only
end_day_inventory = {
    (node, prod, prod_date, state): qty
    for (node, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
    if curr_date == planning_end and qty > 0.01
}

if not end_day_inventory:
    print("✓ NO INVENTORY on final day - optimal!")
else:
    total_end_inv = sum(end_day_inventory.values())
    print(f"\n⚠ TOTAL END INVENTORY: {total_end_inv:,.0f} units")

    # Group by location
    by_location = {}
    for (node, prod, prod_date, state), qty in end_day_inventory.items():
        if node not in by_location:
            by_location[node] = 0
        by_location[node] += qty

    print(f"\nInventory by Location:")
    for node_id in sorted(by_location.keys(), key=lambda x: by_location[x], reverse=True):
        qty = by_location[node_id]
        pct = (qty / total_end_inv * 100)
        node_name = next((n.name for n in unified_data['nodes'] if n.id == node_id), node_id)
        print(f"  {node_id} ({node_name}): {qty:,.0f} units ({pct:.1f}%)")

    # Check demand on final day
    demand_on_final_day = sum(
        qty for (loc, prod, d), qty in model.demand.items()
        if d == planning_end
    )
    print(f"\nDemand on final day ({planning_end}): {demand_on_final_day:,.0f} units")

    # Check shipments departing on final day
    shipments_departing = {}
    for (origin, dest, prod, prod_date, delivery_date, state) in model.shipment_cohort_index_set:
        # Calculate departure date
        route = next((r for r in unified_data['routes'] if r.origin_node_id == origin and r.destination_node_id == dest), None)
        if route:
            departure_date = delivery_date - timedelta(days=route.transit_days)
            if departure_date.date() if hasattr(departure_date, 'date') else departure_date == planning_end:
                key = (origin, dest)
                shipments_departing[key] = shipments_departing.get(key, 0) + 1

    if shipments_departing:
        print(f"\nShipment indices departing on final day: {sum(shipments_departing.values())} cohorts")
        for (origin, dest), count in sorted(shipments_departing.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {origin} → {dest}: {count} cohorts")
    else:
        print(f"\nNo shipments departing on final day (due to horizon fix)")

    # Production on final day
    production_on_final_day = sum(
        qty for (d, prod), qty in solution.get('production_by_date_product', {}).items()
        if d == planning_end
    )
    print(f"\nProduction on final day ({planning_end}): {production_on_final_day:,.0f} units")

    # Check if end inventory is at demand nodes or intermediate nodes
    demand_nodes = {n.id for n in unified_data['nodes'] if n.has_demand_capability()}

    inv_at_demand_nodes = sum(qty for (node, prod, pd, state), qty in end_day_inventory.items() if node in demand_nodes)
    inv_at_other_nodes = total_end_inv - inv_at_demand_nodes

    print(f"\nInventory Distribution:")
    print(f"  At demand nodes (breadrooms): {inv_at_demand_nodes:,.0f} units ({inv_at_demand_nodes/total_end_inv*100:.1f}%)")
    print(f"  At hubs/manufacturing: {inv_at_other_nodes:,.0f} units ({inv_at_other_nodes/total_end_inv*100:.1f}%)")

print("\nDiagnostic complete.")
