"""
PHASE 1: Check if sliding window constraint blocks consumption on Day 28

From MIP theory: If O <= Q is TIGHT and consumption is in O,
the constraint may be preventing additional consumption even though inventory exists.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Solve model
print("Solving 4-week model...")
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(
        location_id=e.node_id,
        product_id=e.product_id,
        forecast_date=e.demand_date,
        quantity=e.quantity
    )
    for e in validated.demand_entries
]
forecast = Forecast(name="Test", entries=forecast_entries)

parser = MultiFileParser('data/examples/Gluten Free Forecast - Latest.xlsm',
                        'data/examples/Network_Config.xlsx',
                        'data/examples/inventory_latest.XLSX')
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)
products_dict = {p.id: p for p in validated.products}

start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=27)).date()

model_builder = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
if not result.success:
    print("Solve failed!")
    exit(1)

print("Solved!\n")
model = model_builder.model

# Check Day 28 sliding window for one node/product
print("="*100)
print("PHASE 1: SLIDING WINDOW CONSTRAINT CHECK - DAY 28")
print("="*100)

# Pick node with high end inventory
check_node = '6110'  # Has 3,349 end inventory
check_prod = 'HELGAS GFREE MIXED GRAIN 500G'
last_date = max(model.dates)

print(f"\nChecking: Node {check_node}, Product {check_prod[:35]}, Date {last_date}")
print(f"Day of week: {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][last_date.weekday()]}")

# Get constraint if it exists
constraint_key = (check_node, check_prod, last_date)

if hasattr(model, 'ambient_shelf_life_con') and constraint_key in model.ambient_shelf_life_con:
    constraint = model.ambient_shelf_life_con[constraint_key]

    print(f"\n✓ Sliding window constraint exists")
    print(f"  Constraint: O_ambient <= Q_ambient")

    # Try to evaluate Q and O
    try:
        # The constraint expression is: O <= Q
        # So constraint.body = O and constraint.upper = Q (or vice versa)
        expr = constraint.expr

        print(f"\n  Constraint expression: {expr}")

        # Try to get bounds
        if hasattr(constraint, 'lower'):
            print(f"  Lower bound: {constraint.lower}")
        if hasattr(constraint, 'upper'):
            print(f"  Upper bound: {constraint.upper}")

    except Exception as e:
        print(f"  Error examining constraint: {e}")

    # Check if constraint is tight (slack ≈ 0)
    try:
        # Get constraint slack (how much "room" is left)
        # Slack = Upper - Body (for <= constraints)
        # If slack ≈ 0, constraint is TIGHT (active, preventing more)
        # If slack > 0, constraint has room (not blocking)

        # For Pyomo, need to evaluate the expression
        print(f"\n  Attempting to extract slack...")

        # This is complex - just check if we can access duals
        if hasattr(model, 'dual'):
            dual_value = model.dual.get(constraint)
            if dual_value and abs(dual_value) > 0.01:
                print(f"  Dual value: {dual_value:.4f}")
                print(f"  → Constraint is ACTIVE (dual != 0)")
                print(f"  → This constraint is BINDING and may be blocking consumption!")
            else:
                print(f"  Dual value: ~0")
                print(f"  → Constraint is INACTIVE (has slack)")
        else:
            print(f"  Duals not available (need to resolve with dual import)")

    except Exception as e:
        print(f"  Could not check slack: {e}")

else:
    print(f"\n❌ No sliding window constraint for this node/product/date!")

# Now check actual values
print(f"\n\n{'='*100}")
print(f"ACTUAL VALUES ON DAY 28:")
print(f"{'='*100}")

# Demand
demand_day28 = model_builder.demand.get((check_node, check_prod, last_date), 0)
print(f"\nDemand[{check_node}, {check_prod[:35]}, {last_date}]: {demand_day28:,.0f} units")

# Inventory
inv_day28 = 0
if (check_node, check_prod, 'ambient', last_date) in model.inventory:
    try:
        inv_day28 = value(model.inventory[check_node, check_prod, 'ambient', last_date])
    except:
        pass
print(f"Inventory[{check_node}, ambient, {last_date}]: {inv_day28:,.0f} units")

# Consumption
cons_day28 = 0
if (check_node, check_prod, last_date) in model.demand_consumed_from_ambient:
    try:
        cons_day28 = value(model.demand_consumed_from_ambient[check_node, check_prod, last_date])
    except:
        pass
print(f"Consumption[{check_node}, {last_date}]: {cons_day28:,.0f} units")

# Shortage
shortage_day28 = 0
if hasattr(model, 'shortage') and (check_node, check_prod, last_date) in model.shortage:
    try:
        shortage_day28 = value(model.shortage[check_node, check_prod, last_date])
    except:
        pass
print(f"Shortage[{check_node}, {last_date}]: {shortage_day28:,.0f} units")

# Check consumption bound
print(f"\n\n{'='*100}")
print(f"CONSUMPTION BOUND CHECK:")
print(f"{'='*100}")

print(f"\nConsumption bound: consumption <= inventory[t]")
print(f"  consumption[Day 28]: {cons_day28:,.0f}")
print(f"  inventory[Day 28]:   {inv_day28:,.0f}")
print(f"  Slack:               {inv_day28 - cons_day28:,.0f}")

if cons_day28 >= inv_day28 - 0.01:
    print(f"\n  ⚠️  Consumption bound is TIGHT!")
    print(f"  This constraint is preventing MORE consumption")
else:
    print(f"\n  ✓ Consumption bound has slack (not blocking)")

# Demand satisfaction
print(f"\n\nDEMAND SATISFACTION:")
print(f"  Demand:              {demand_day28:,.0f}")
print(f"  Consumption:         {cons_day28:,.0f}")
print(f"  Shortage:            {shortage_day28:,.0f}")
print(f"  Cons + Shortage:     {cons_day28 + shortage_day28:,.0f}")
print(f"  (Should equal demand)")

if abs((cons_day28 + shortage_day28) - demand_day28) < 1:
    print(f"  ✓ Demand equation holds")

# Key question
print(f"\n\n{'='*100}")
print(f"KEY QUESTION (MIP Analysis):")
print(f"{'='*100}")

print(f"\nInventory exists: {inv_day28:,.0f} units")
print(f"Demand exists: {demand_day28:,.0f} units")
print(f"But consumption: {cons_day28:,.0f} units (not consuming all available!)")
print(f"Taking shortage: {shortage_day28:,.0f} units instead")

if inv_day28 > cons_day28 + 100 and shortage_day28 > 100:
    print(f"\n❌ IRRATIONAL: Has {inv_day28:,.0f} inventory but takes {shortage_day28:,.0f} shortage!")
    print(f"\nWHICH CONSTRAINT prevents consuming the available inventory?")
    print(f"Options:")
    print(f"  1. Sliding window (O <= Q is tight)")
    print(f"  2. Shelf life (inventory too old)")
    print(f"  3. Consumption bound (though it has slack)")
    print(f"  4. Some other constraint")

print(f"\n{'='*100}")
