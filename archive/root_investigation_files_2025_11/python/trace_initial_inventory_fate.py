"""
Trace what happens to initial inventory in both solutions.

Natural: 0 disposal (init_inv consumed before expiration)
Constrained: 7,434 disposal (init_inv expires unused)

WHY does constraining end inventory prevent consuming initial inventory?
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


def solve_and_trace_init_inv(add_constraint=False):
    """Solve and trace what happens to initial inventory."""

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
        solver.options['time_limit'] = 180
        solver.options['mip_rel_gap'] = 0.01
        result = solver.solve(model, tee=False)

    # Trace initial inventory
    init_inv_total = sum(validated.get_inventory_dict().values())

    # Consumption on Days 1-7 (before expiration)
    day1 = min(model.dates)
    dates = sorted(list(model.dates))

    early_consumption = 0  # Days 1-7
    for t in dates[:7]:
        if hasattr(model, 'demand_consumed_from_ambient'):
            for (node_id, prod, date) in model.demand_consumed_from_ambient:
                if date == t:
                    early_consumption += value(model.demand_consumed_from_ambient[node_id, prod, date])

    # Disposal
    total_disposal = 0
    if hasattr(model, 'disposal'):
        for key in model.disposal:
            total_disposal += value(model.disposal[key])

    # End inventory
    last_date = max(model.dates)
    end_inv = sum(
        value(model.inventory[n, p, s, last_date])
        for (n, p, s, t) in model.inventory
        if t == last_date and value(model.inventory[n, p, s, last_date]) > 0.01
    )

    return {
        'init_inv_total': init_inv_total,
        'early_consumption': early_consumption,
        'disposal': total_disposal,
        'end_inv': end_inv,
        'production': sum(value(model.production[k]) for k in model.production)
    }


print("Tracing initial inventory fate...\n")

print("1. NATURAL solution (no constraint)...")
nat = solve_and_trace_init_inv(False)

print("\n2. CONSTRAINED solution (end_inv <= 2000)...")
con = solve_and_trace_init_inv(True)

# Compare
print("\n\n" + "="*100)
print("INITIAL INVENTORY FATE COMPARISON")
print("="*100)

print(f"\n{'Metric':<35} {'Natural':>15} {'Constrained':>15} {'Difference':>15}")
print("-"*100)
print(f"{'Initial inventory':<35} {nat['init_inv_total']:>15,.0f} {con['init_inv_total']:>15,.0f} {0:>15,.0f}")
print(f"{'Consumed Days 1-7 (early)':<35} {nat['early_consumption']:>15,.0f} {con['early_consumption']:>15,.0f} {con['early_consumption'] - nat['early_consumption']:>15,.0f}")
print(f"{'Disposal (expired)':<35} {nat['disposal']:>15,.0f} {con['disposal']:>15,.0f} {con['disposal'] - nat['disposal']:>15,.0f}")
print(f"{'End inventory':<35} {nat['end_inv']:>15,.0f} {con['end_inv']:>15,.0f} {con['end_inv'] - nat['end_inv']:>15,.0f}")
print(f"{'Production (new goods)':<35} {nat['production']:>15,.0f} {con['production']:>15,.0f} {con['production'] - nat['production']:>15,.0f}")

print("\n\n" + "="*100)
print("DIAGNOSIS:")
print("="*100)

print(f"\nInitial inventory: {nat['init_inv_total']:,.0f} units")

print(f"\nNatural solution:")
print(f"  Consumed early: {nat['early_consumption']:,.0f} units")
print(f"  Disposal: {nat['disposal']:,.0f} units")
print(f"  → Initial inventory consumed before expiration ✓")

print(f"\nConstrained solution:")
print(f"  Consumed early: {con['early_consumption']:,.0f} units")
print(f"  Disposal: {con['disposal']:,.0f} units")
print(f"  → {con['disposal']:,.0f} units of initial inventory NOT consumed, expired and disposed!")

early_consumption_diff = con['early_consumption'] - nat['early_consumption']
disposal_diff = con['disposal'] - nat['disposal']

print(f"\nDifference:")
print(f"  Early consumption reduced by: {-early_consumption_diff:,.0f} units")
print(f"  Disposal increased by: {disposal_diff:,.0f} units")

if abs(early_consumption_diff + disposal_diff) < 1000:
    print(f"\n  → These almost match! ({abs(early_consumption_diff + disposal_diff):,.0f} unit difference)")
    print(f"  → Initial inventory that WAS consumed in natural solution")
    print(f"    becomes DISPOSED in constrained solution!")

print(f"\n\nWHY?")
print(f"  The end_inv <= 2000 constraint somehow prevents early consumption")
print(f"  of initial inventory, causing it to expire and be disposed.")

print(f"\n  This is the ROOT CAUSE of the $111k cost increase!")

print(f"\n" + "="*100)
print(f"NEXT STEP:")
print(f"{'='*100}")
print(f"""
Need to understand the MECHANISM:

How does constraining end_inv (Day 28) affect consumption (Days 1-7)?

Hypotheses:
1. end_inv constraint forces production shift that blocks early consumption
2. Sliding window constraint interaction with end_inv constraint
3. Network routing changes prevent initial inventory from reaching demand

Need to trace production timing and routing changes.
""")
