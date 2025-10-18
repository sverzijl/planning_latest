"""
Diagnostic script to trace the minimal case bug.
Extracts detailed solution data to understand why 2x production occurs.
"""

from datetime import date, timedelta
from src.optimization.unified_node_model import UnifiedNodeModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
# Setup minimal case
day_1 = date(2025, 1, 1)
day_7 = date(2025, 1, 7)

manufacturing = UnifiedNode(
    id='MFG',
    name='Manufacturing Site',
    capabilities=NodeCapabilities(
        can_manufacture=True,
        has_demand=False,
        can_store=True,
        requires_trucks=False,
        storage_mode=StorageMode.AMBIENT,
        production_rate_per_hour=1400.0,
    ),
)

breadroom = UnifiedNode(
    id='BR1',
    name='Breadroom 1',
    capabilities=NodeCapabilities(
        can_manufacture=False,
        has_demand=True,
        can_store=True,
        requires_trucks=False,
        storage_mode=StorageMode.AMBIENT,
        production_rate_per_hour=None,
    ),
)

route = UnifiedRoute(
    id='MFG-BR1',
    origin_node_id='MFG',
    destination_node_id='BR1',
    transit_days=1.0,
    cost_per_unit=1.0,
    transport_mode=TransportMode.AMBIENT,
)

forecast = Forecast(
    name='Minimal Test',
    entries=[
        ForecastEntry(
            location_id='BR1',
            product_id='PROD1',
            forecast_date=day_7,
            quantity=1000.0
        )
    ]
)

labor_days = []
for day_offset in range(7):
    curr_date = day_1 + timedelta(days=day_offset)
    labor_days.append(LaborDay(
        date=curr_date,
        is_fixed_day=True,
        fixed_hours=12.0,
        overtime_hours=2.0,
        minimum_hours=4.0,
        regular_rate=25.0,
        overtime_rate=37.50,
        non_fixed_rate=50.0,
    ))

labor_calendar = LaborCalendar(name='Test Calendar', days=labor_days)

cost_structure = CostStructure(
    production_cost_per_unit=5.0,
    shortage_penalty_per_unit=10000.0,
)

# Create model
model = UnifiedNodeModel(
    nodes=[manufacturing, breadroom],
    routes=[route],
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=day_1,
    end_date=day_7,
    truck_schedules=None,
    initial_inventory=None,
    allow_shortages=True,
    enforce_shelf_life=True,
    use_batch_tracking=True,
)

# Solve
result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01)
solution = model.get_solution()

print("=" * 80)
print("MINIMAL CASE DIAGNOSTIC")
print("=" * 80)
print(f"Status: {result.termination_condition}")
print(f"Solve time: {result.solve_time_seconds:.2f}s")
print(f"Total cost: ${solution['total_cost']:,.2f}")
print()

# Extract production
print("PRODUCTION:")
prod_by_date = solution.get('production_by_date_product', {})
for (prod_date, product), qty in sorted(prod_by_date.items()):
    if qty > 0.01:
        print(f"  {prod_date} ({product}): {qty:,.0f} units")
print()

# Extract shipments - check multiple possible keys
print("SHIPMENTS:")
batch_shipments = solution.get('batch_shipments', [])
shipments_by_route = solution.get('shipments_by_route_product_date', {})

if batch_shipments:
    print("  Batch shipments:")
    for shipment in batch_shipments:
        print(f"    {shipment}")

if shipments_by_route:
    print("  Shipments by route/product/date:")
    for key, qty in sorted(shipments_by_route.items()):
        if qty > 0.01:
            print(f"    {key}: {qty:,.0f} units")

if not batch_shipments and not shipments_by_route:
    print("  WARNING: No shipments found in solution")
    print(f"  Available solution keys: {sorted(solution.keys())}")
print()

# Extract inventory at each node by date
print("INVENTORY BY NODE AND DATE (All nodes, all dates):")
cohort_inventory = solution.get('cohort_inventory', {})

# Group by node and date
inv_by_node_date = {}
for (node, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
    if qty > 0.01:
        key = (node, curr_date)
        if key not in inv_by_node_date:
            inv_by_node_date[key] = []
        inv_by_node_date[key].append({
            'production_date': prod_date,
            'current_date': curr_date,
            'state': state,
            'quantity': qty,
            'product': prod
        })

if not inv_by_node_date:
    print("  WARNING: No inventory found!")
else:
    for (node, curr_date) in sorted(inv_by_node_date.keys()):
        total = sum(inv['quantity'] for inv in inv_by_node_date[(node, curr_date)])
        print(f"  {node} on {curr_date}: {total:,.0f} units")
        for inv in inv_by_node_date[(node, curr_date)]:
            age_days = (inv['current_date'] - inv['production_date']).days
            print(f"    - Produced {inv['production_date']} ({age_days}d old, {inv['state']}): {inv['quantity']:,.0f}")
print()

# Check specifically for MFG inventory
print("MFG INVENTORY CHECK:")
mfg_inv = {k: v for k, v in cohort_inventory.items() if k[0] == 'MFG' and v > 0.01}
if mfg_inv:
    print("  MFG has inventory:")
    for (node, prod, prod_date, curr_date, state), qty in sorted(mfg_inv.items()):
        print(f"    {curr_date}: {qty:,.0f} units (produced {prod_date}, {state})")
else:
    print("  MFG has NO inventory (all production immediately shipped)")
print()

# Extract demand allocation
print("DEMAND ALLOCATION:")
demand_consumption = solution.get('cohort_demand_consumption', {})
for (node, prod, prod_date, demand_date), qty in sorted(demand_consumption.items()):
    if qty > 0.01:
        print(f"  {node} on {demand_date}")
        print(f"    From cohort produced {prod_date}: {qty:,.0f} units")
print()

# Check demand satisfaction
total_demand = sum(entry.quantity for entry in forecast.entries)
total_satisfied = sum(demand_consumption.values())
total_shortage = solution.get('total_shortage_units', 0)

print("DEMAND SUMMARY:")
print(f"  Total forecast: {total_demand:,.0f} units")
print(f"  Total satisfied: {total_satisfied:,.0f} units")
print(f"  Total shortage: {total_shortage:,.0f} units")
print()

# End inventory
end_inv = sum(qty for (n, p, pd, cd, s), qty in cohort_inventory.items()
              if cd == day_7 and qty > 0.01)

print("END STATE:")
print(f"  End-of-horizon inventory (day 7): {end_inv:,.0f} units")
print(f"  Expected (with perfect foresight): ~0 units")
print(f"  Excess: {end_inv:,.0f} units")
print(f"  Wasted cost: ${end_inv * 5:,.0f}")
print()

# Cost breakdown
print("COST BREAKDOWN:")
for key, value in sorted(solution.items()):
    if 'cost' in key.lower() and isinstance(value, (int, float)):
        print(f"  {key}: ${value:,.2f}")
