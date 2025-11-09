"""
Check Day 1 inventory to see if initial inventory is consumed or sitting unused.

This will show if end_inv constraint blocks using initial inventory.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value
from pyomo.environ import Constraint

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


def solve_and_check(add_constraint=False):
    coordinator = DataCoordinator(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    validated = coordinator.load_and_validate()

    forecast_entries = [
        ForecastEntry(location_id=e.node_id, product_id=e.product_id,
                     forecast_date=e.demand_date, quantity=e.quantity)
        for e in validated.demand_entries
    ]
    forecast = Forecast(name="Test", entries=forecast_entries)

    parser = MultiFileParser(
        'data/examples/Gluten Free Forecast - Latest.xlsm',
        'data/examples/Network_Config.xlsx',
        'data/examples/inventory_latest.XLSX'
    )
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
    model = model_builder.model

    if add_constraint:
        last_date = max(model.dates)
        total_end_inv = sum(
            model.inventory[n, p, s, last_date]
            for (n, p, s, t) in model.inventory
            if t == last_date
        )
        model.force_low_end_inv = Constraint(expr=total_end_inv <= 2000)

        from pyomo.opt import SolverFactory
        solver = SolverFactory('appsi_highs')
        result = solver.solve(model, tee=False)

    # Check inventory levels across first week
    init_inv_total = sum(model_builder.initial_inventory.values())
    dates = sorted(list(model.dates))

    inv_by_day = []
    for t in dates[:7]:  # First week
        inv_total = sum(
            value(model.inventory[n, p, s, t])
            for (n, p, s, date) in model.inventory
            if date == t and value(model.inventory[n, p, s, t]) > 0.01
        )
        inv_by_day.append((t, inv_total))

    return init_inv_total, inv_by_day, model_builder


print("="*100)
print("DAY 1 INVENTORY USAGE CHECK")
print("="*100)

print("\n1. Natural solution...")
init_inv, inv_nat, builder_nat = solve_and_check(False)

print("\n2. Constrained solution...")
_, inv_con, builder_con = solve_and_check(True)

# Compare
print("\n\n" + "="*100)
print("INVENTORY LEVELS - FIRST WEEK")
print("="*100)

print(f"\nInitial inventory: {init_inv:,.0f} units")

print(f"\n{'Date':<12} {'Day#':>4} {'Natural Inv':>15} {'Constrained Inv':>15} {'Difference':>15}")
print("-"*100)

for i in range(7):
    t_nat, inv_val_nat = inv_nat[i]
    t_con, inv_val_con = inv_con[i]

    diff = inv_val_con - inv_val_nat

    marker = ""
    if diff > 2000:
        marker = " ← CONSTRAINED HOLDS MORE!"

    print(f"{t_nat} {i+1:>4} {inv_val_nat:>15,.0f} {inv_val_con:>15,.0f} {diff:>15,.0f}{marker}")

print("\n\n" + "="*100)
print("CRITICAL INSIGHT:")
print("="*100)

# Check if constrained holds more inventory early
avg_inv_nat = sum(inv for _, inv in inv_nat) / len(inv_nat)
avg_inv_con = sum(inv for _, inv in inv_con) / len(inv_con)

if avg_inv_con > avg_inv_nat + 2000:
    print(f"\n❌ CONSTRAINED SOLUTION HOLDS MORE INVENTORY EARLY!")
    print(f"   Average Days 1-7:")
    print(f"     Natural: {avg_inv_nat:,.0f} units")
    print(f"     Constrained: {avg_inv_con:,.0f} units")
    print(f"     Difference: {avg_inv_con - avg_inv_nat:,.0f} units MORE in constrained")
    print(f"\n   This is the opposite of what should happen!")
    print(f"   Constraining LOW end inventory causes HIGH early inventory!")
    print(f"\n   ROOT CAUSE: end_inv constraint creates perverse incentive:")
    print(f"     - Forces model to 'get rid of' inventory by end")
    print(f"     - But can't consume it (some constraint blocking)")
    print(f"     - So holds it early, lets it expire, disposes it")
    print(f"\n   This is a FORMULATION BUG in how end_inv constraint interacts")
    print(f"   with the rest of the model!")
else:
    print(f"\n   Inventory levels similar in early days")
    print(f"   Need to investigate later in horizon")

print("\n" + "="*100)
