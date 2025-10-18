"""
Inspect Pyomo model variables directly to see what solver chose.
"""

from datetime import date, timedelta
from src.optimization.unified_node_model import UnifiedNodeModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from pyomo.environ import value

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
unified_model = UnifiedNodeModel(
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

# Solve (this builds and solves the model)
result = unified_model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01)

# Get the Pyomo model from the instance
pyomo_model = unified_model.model

print("=" * 80)
print("PYOMO VARIABLE INSPECTION")
print("=" * 80)
print(f"Termination: {result.termination_condition}")
print(f"Objective value: ${value(pyomo_model.obj):,.2f}")
print()

# Inspect ALL production variables
print("PRODUCTION VARIABLES:")
for (node, prod, date_val) in pyomo_model.production:
    qty = value(pyomo_model.production[node, prod, date_val])
    if qty > 0.01:
        print(f"  production[{node}, {prod}, {date_val}] = {qty:,.2f}")
print()

# Inspect ALL shipment_cohort variables
print("SHIPMENT COHORT VARIABLES (all > 0.01):")
count = 0
for (origin, dest, prod, prod_date, delivery_date, state) in unified_model.shipment_cohort_index_set:
    qty = value(pyomo_model.shipment_cohort[origin, dest, prod, prod_date, delivery_date, state])
    if qty > 0.01:
        departure_date = delivery_date - timedelta(days=route.transit_days)
        print(f"  shipment_cohort[{origin}, {dest}, {prod}, prod={prod_date}, deliver={delivery_date}, {state}] = {qty:,.2f}")
        print(f"    -> Departs {departure_date}, arrives {delivery_date}, transit={route.transit_days}d")
        count += 1

if count == 0:
    print("  (no shipments with qty > 0.01)")
print()

# Inspect ALL inventory_cohort variables
print("INVENTORY COHORT VARIABLES (all > 0.01):")
for day_offset in range(7):
    curr_date = day_1 + timedelta(days=day_offset)
    print(f"\n  Day {day_offset + 1} ({curr_date}):")

    found_any = False
    for (node, prod, prod_date, inv_date, state) in unified_model.cohort_index_set:
        if inv_date == curr_date:
            qty = value(pyomo_model.inventory_cohort[node, prod, prod_date, inv_date, state])
            if qty > 0.01:
                age = (inv_date - prod_date).days
                print(f"    inventory_cohort[{node}, {prod}, prod={prod_date}, date={inv_date}, {state}] = {qty:,.2f} ({age}d old)")
                found_any = True

    if not found_any:
        print(f"    (no inventory)")

print()

# Inspect demand_from_cohort variables
print("DEMAND FROM COHORT VARIABLES:")
for (node, prod, prod_date, demand_date) in unified_model.demand_cohort_index_set:
    qty = value(pyomo_model.demand_from_cohort[node, prod, prod_date, demand_date])
    if qty > 0.01:
        print(f"  demand_from_cohort[{node}, {prod}, prod={prod_date}, demand={demand_date}] = {qty:,.2f}")
print()

# Check shortage
print("SHORTAGE VARIABLES:")
has_shortage = False
for (node, prod, date_val) in unified_model.demand.keys():
    qty = value(pyomo_model.shortage[node, prod, date_val])
    if qty > 0.01:
        print(f"  shortage[{node}, {prod}, {date_val}] = {qty:,.2f}")
        has_shortage = True

if not has_shortage:
    print("  (no shortages)")
print()

print("=" * 80)
print("BUG ANALYSIS:")
print("=" * 80)

# Calculate total produced
total_produced = sum(value(pyomo_model.production[n, p, d])
                     for (n, p, d) in pyomo_model.production)

# Calculate total shipped
total_shipped = sum(value(pyomo_model.shipment_cohort[o, d, p, pd, dd, s])
                   for (o, d, p, pd, dd, s) in unified_model.shipment_cohort_index_set)

# Calculate total demand satisfied
total_demand_satisfied = sum(value(pyomo_model.demand_from_cohort[n, p, pd, dd])
                            for (n, p, pd, dd) in unified_model.demand_cohort_index_set)

# Calculate end inventory
end_inv = sum(value(pyomo_model.inventory_cohort[n, p, pd, day_7, s])
             for (n, p, pd, cd, s) in unified_model.cohort_index_set
             if cd == day_7)

print(f"Total produced: {total_produced:,.0f} units")
print(f"Total shipped: {total_shipped:,.0f} units")
print(f"Total demand satisfied: {total_demand_satisfied:,.0f} units")
print(f"End inventory: {end_inv:,.0f} units")
print()

if total_produced > 1100:  # Allowing small tolerance
    print("❌ BUG CONFIRMED: Model produced more than needed!")
    print(f"   Expected: ~1,000 units")
    print(f"   Actual: {total_produced:,.0f} units")
    print(f"   Excess: {total_produced - 1000:,.0f} units")
else:
    print("✓ No bug detected - production matches demand")
