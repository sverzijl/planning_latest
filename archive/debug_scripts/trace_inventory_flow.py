"""
Trace inventory flow day-by-day to find the bug.
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
print("DAY-BY-DAY INVENTORY FLOW TRACE")
print("=" * 80)
print(f"Total cost: ${solution['total_cost']:,.2f}")
print()

cohort_inventory = solution.get('cohort_inventory', {})
shipments = solution.get('shipments_by_route_product_date', {})
production = solution.get('production_by_date_product', {})
demand = solution.get('cohort_demand_consumption', {})

# Trace through each day
for day_offset in range(7):
    curr_date = day_1 + timedelta(days=day_offset)
    print(f"DAY {day_offset + 1}: {curr_date}")
    print("-" * 40)

    # Production on this day
    prod_today = sum(qty for (prod_date, product), qty in production.items()
                     if prod_date == curr_date)
    if prod_today > 0:
        print(f"  PRODUCTION: {prod_today:,.0f} units")

    # Shipments departing this day (delivery_date - transit_days = departure_date)
    shipments_departing = []
    for (origin, dest, product, delivery_date), qty in shipments.items():
        # Route has 1-day transit
        departure_date = delivery_date - timedelta(days=1)
        if departure_date == curr_date and qty > 0.01:
            shipments_departing.append((origin, dest, delivery_date, qty))

    if shipments_departing:
        print(f"  SHIPMENTS DEPARTING:")
        for origin, dest, delivery_date, qty in shipments_departing:
            print(f"    {origin} → {dest}: {qty:,.0f} units (arrives {delivery_date})")

    # Shipments arriving this day
    shipments_arriving = []
    for (origin, dest, product, delivery_date), qty in shipments.items():
        if delivery_date == curr_date and qty > 0.01:
            shipments_arriving.append((origin, dest, qty))

    if shipments_arriving:
        print(f"  SHIPMENTS ARRIVING:")
        for origin, dest, qty in shipments_arriving:
            print(f"    {origin} → {dest}: {qty:,.0f} units")

    # Demand on this day
    demand_today = sum(qty for (node, product, prod_date, demand_date), qty in demand.items()
                       if demand_date == curr_date)
    if demand_today > 0:
        print(f"  DEMAND CONSUMED: {demand_today:,.0f} units")

    # Inventory at end of day
    print(f"  END-OF-DAY INVENTORY:")
    mfg_inv = sum(qty for (node, product, prod_date, inv_date, state), qty in cohort_inventory.items()
                  if node == 'MFG' and inv_date == curr_date and qty > 0.01)
    br1_inv = sum(qty for (node, product, prod_date, inv_date, state), qty in cohort_inventory.items()
                  if node == 'BR1' and inv_date == curr_date and qty > 0.01)

    if mfg_inv > 0:
        print(f"    MFG: {mfg_inv:,.0f} units")
    if br1_inv > 0:
        print(f"    BR1: {br1_inv:,.0f} units")
    if mfg_inv == 0 and br1_inv == 0:
        print(f"    (empty)")

    print()

print("=" * 80)
print("ANALYSIS:")
print(f"Total production: {sum(production.values()):,.0f} units")
print(f"Total demand: {sum(demand.values()):,.0f} units")
print(f"End inventory: {sum(qty for (n,p,pd,cd,s), qty in cohort_inventory.items() if cd == day_7):,.0f} units")
print(f"Waste: {sum(qty for (n,p,pd,cd,s), qty in cohort_inventory.items() if cd == day_7):,.0f} units × $5 = ${sum(qty for (n,p,pd,cd,s), qty in cohort_inventory.items() if cd == day_7) * 5:,.0f}")
