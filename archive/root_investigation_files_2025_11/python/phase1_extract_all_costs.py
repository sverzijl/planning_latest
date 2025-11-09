"""
PHASE 1: Extract complete cost breakdown from both solutions.

This will identify EXACTLY which cost(s) account for the $156k "other costs".
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


def solve_and_extract_costs(add_end_inv_constraint=False):
    """Solve and extract ALL cost components."""

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

    # Solve
    result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

    if not result.success:
        return None

    model = model_builder.model

    # If adding constraint, do it now and resolve
    if add_end_inv_constraint:
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

    solution = model_builder.extract_solution(model)

    # Extract costs from solution.costs (Pydantic validated breakdown)
    costs = {
        'production': solution.costs.production.total,
        'labor': solution.costs.labor.total,
        'transport': solution.costs.transport.total,
        'holding': solution.costs.holding.total,
        'shortage': solution.costs.waste.shortage_penalty,  # Shortage in waste breakdown
        'waste': solution.costs.waste.expiration_waste,  # End inventory waste
        'total': solution.total_cost
    }

    # Calculate waste cost manually
    last_date = max(model.dates)
    end_inv = sum(
        value(model.inventory[n, p, s, last_date])
        for (n, p, s, t) in model.inventory
        if t == last_date and value(model.inventory[n, p, s, last_date]) > 0.01
    )

    waste_mult = cost_structure.waste_cost_multiplier
    prod_cost = cost_structure.production_cost_per_unit
    costs['waste'] = end_inv * waste_mult * prod_cost
    costs['end_inventory_units'] = end_inv

    # Extract production and shortage units
    costs['production_units'] = solution.total_production
    costs['shortage_units'] = solution.total_shortage_units

    return costs, model, solution, model_builder


print("="*120)
print("PHASE 1: COMPLETE COST BREAKDOWN COMPARISON")
print("="*120)

print("\n\nSolving NATURAL solution (no constraints)...")
costs_nat, model_nat, sol_nat, builder_nat = solve_and_extract_costs(add_end_inv_constraint=False)

print("\n\nSolving CONSTRAINED solution (end_inv <= 2000)...")
costs_con, model_con, sol_con, builder_con = solve_and_extract_costs(add_end_inv_constraint=True)

# Display comparison
print("\n\n" + "="*120)
print("COST COMPONENT COMPARISON")
print("="*120)

print(f"\n{'Component':<20} {'Natural':>15} {'Constrained':>15} {'Difference':>15} {'% Change':>10} {'Expected?':<15}")
print("-"*120)

components = ['production', 'labor', 'transport', 'holding', 'shortage', 'waste', 'changeover']

for comp in components:
    nat_val = costs_nat.get(comp, 0)
    con_val = costs_con.get(comp, 0)
    diff = con_val - nat_val
    pct = (diff / nat_val * 100) if nat_val > 0 else 0

    # Determine if change is expected
    expected = "?"
    if comp == 'production' and diff < 0:
        expected = "✓ Less prod"
    elif comp == 'shortage' and diff > 0:
        expected = "✓ More shortage"
    elif comp == 'waste' and diff < 0:
        expected = "✓ Less waste"
    elif comp in ['labor', 'transport'] and diff > 0:
        expected = "❌ SUSPICIOUS!"
    elif comp == 'holding' and diff > 0:
        expected = "⚠️ Investigate"

    print(f"{comp:<20} ${nat_val:>14,.0f} ${con_val:>14,.0f} ${diff:>14,.0f} {pct:>9.1f}% {expected:<15}")

print("-"*120)

# Verify total
sum_nat = sum(costs_nat.get(c, 0) for c in components)
sum_con = sum(costs_con.get(c, 0) for c in components)

print(f"{'SUM (components)':<20} ${sum_nat:>14,.0f} ${sum_con:>14,.0f} ${sum_con - sum_nat:>14,.0f}")
print(f"{'TOTAL (reported)':<20} ${costs_nat['total']:>14,.0f} ${costs_con['total']:>14,.0f} ${costs_con['total'] - costs_nat['total']:>14,.0f}")

discrepancy_nat = costs_nat['total'] - sum_nat
discrepancy_con = costs_con['total'] - sum_con

if abs(discrepancy_nat) > 1000 or abs(discrepancy_con) > 1000:
    print(f"\n⚠️  DISCREPANCY FOUND!")
    print(f"   Natural: reported ${costs_nat['total']:,.0f} vs sum ${sum_nat:,.0f} (diff: ${discrepancy_nat:,.0f})")
    print(f"   Constrained: reported ${costs_con['total']:,.0f} vs sum ${sum_con:,.0f} (diff: ${discrepancy_con:,.0f})")
    print(f"   → Some cost component is missing from extraction!")

# Production quantities
print("\n\nProduction quantities:")
print(f"  Natural:     {costs_nat['production_units']:,.0f} units")
print(f"  Constrained: {costs_con['production_units']:,.0f} units")
print(f"  Difference:  {costs_con['production_units'] - costs_nat['production_units']:,.0f} units")

# Identify the culprit
print("\n\n" + "="*120)
print("PRIMARY COST DRIVER:")
print("="*120)

# Find largest cost increase
increases = {}
for comp in components:
    diff = costs_con.get(comp, 0) - costs_nat.get(comp, 0)
    if diff > 10000:  # Significant increase
        increases[comp] = diff

if len(increases) > 0:
    sorted_increases = sorted(increases.items(), key=lambda x: -x[1])
    print(f"\nCosts that increased significantly:")
    for comp, amount in sorted_increases:
        print(f"  {comp:<15}: +${amount:>12,.0f}")

    largest_comp, largest_amt = sorted_increases[0]
    print(f"\n→ PRIMARY DRIVER: {largest_comp.upper()} increased by ${largest_amt:,.0f}")
    print(f"  This accounts for {largest_amt / (costs_con['total'] - costs_nat['total']) * 100:.0f}% of objective increase")
else:
    print("\nNo single large increase found - must be distributed across components")

print("\n" + "="*120)
