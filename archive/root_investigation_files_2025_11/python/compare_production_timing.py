"""
Compare production timing between natural and constrained solutions.

This will show HOW production changes when we constrain end inventory,
which might explain why init_inv can't be consumed.
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


def solve_and_get_production_schedule(add_constraint=False):
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

    # Extract production by date
    prod_by_date = {}
    for t in model.dates:
        prod_total = sum(value(model.production[n, p, date])
                        for (n, p, date) in model.production if date == t)
        if prod_total > 1:
            prod_by_date[t] = prod_total

    return prod_by_date, model_builder


print("="*100)
print("PRODUCTION TIMING COMPARISON")
print("="*100)

print("\nSolving natural...")
prod_nat, builder_nat = solve_and_get_production_schedule(False)

print("Solving constrained...")
prod_con, builder_con = solve_and_get_production_schedule(True)

# Compare
print("\n\n" + "="*100)
print("PRODUCTION SCHEDULE COMPARISON")
print("="*100)

all_dates = sorted(set(prod_nat.keys()) | set(prod_con.keys()))

print(f"\n{'Date':<12} {'Day#':>4} {'Natural':>15} {'Constrained':>15} {'Difference':>15}")
print("-"*100)

for i, t in enumerate(all_dates, 1):
    nat_prod = prod_nat.get(t, 0)
    con_prod = prod_con.get(t, 0)
    diff = con_prod - nat_prod

    marker = ""
    if abs(diff) > 5000:
        marker = " ← LARGE SHIFT!"
    elif diff != 0:
        marker = " ← Changed"

    print(f"{t} {i:>4} {nat_prod:>15,.0f} {con_prod:>15,.0f} {diff:>15,.0f}{marker}")

print("-"*100)
print(f"{'TOTAL':<17} {sum(prod_nat.values()):>15,.0f} {sum(prod_con.values()):>15,.0f} {sum(prod_con.values()) - sum(prod_nat.values()):>15,.0f}")

# Analysis
print("\n\n" + "="*100)
print("TIMING ANALYSIS:")
print("="*100)

# When is most production?
total_nat = sum(prod_nat.values())
total_con = sum(prod_con.values())

# First week
dates_list = sorted(list(all_dates))
early_nat = sum(prod_nat.get(t, 0) for t in dates_list[:7])
early_con = sum(prod_con.get(t, 0) for t in dates_list[:7])

# Last week
late_nat = sum(prod_nat.get(t, 0) for t in dates_list[-7:])
late_con = sum(prod_con.get(t, 0) for t in dates_list[-7:])

print(f"\nNatural:")
print(f"  First week (Days 1-7):  {early_nat:>10,.0f} ({early_nat/total_nat*100:>5.1f}%)")
print(f"  Last week (Days 22-28): {late_nat:>10,.0f} ({late_nat/total_nat*100:>5.1f}%)")

print(f"\nConstrained:")
print(f"  First week (Days 1-7):  {early_con:>10,.0f} ({early_con/total_con*100:>5.1f}%)")
print(f"  Last week (Days 22-28): {late_con:>10,.0f} ({late_con/total_con*100:>5.1f}%)")

# Check if production shifted
early_shift = early_con - early_nat
late_shift = late_con - late_nat

print(f"\nShift:")
print(f"  Early production: {early_shift:+,.0f} units")
print(f"  Late production: {late_shift:+,.0f} units")

if early_shift < -5000:
    print(f"\n❌ CONSTRAINED PRODUCES LESS EARLY!")
    print(f"   This would explain disposal:")
    print(f"     - Less early production")
    print(f"     - Less early shipments to demand nodes with init_inv")
    print(f"     - init_inv sits unused at those nodes")
    print(f"     - Expires after 17 days")
    print(f"     - Disposal on Days 24+")
elif early_shift > 5000:
    print(f"\n   Constrained produces MORE early")
    print(f"   Doesn't explain disposal - need to investigate further")
else:
    print(f"\n   Production timing similar")
    print(f"   Disposal must be from routing/network changes")

print("\n" + "="*100)
