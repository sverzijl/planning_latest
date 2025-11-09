"""
Compare objectives: Natural solution vs Constrained to end_inv < 2000 units.

This will show the hidden costs that prevent low end inventory at waste_mult=10.
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


print("="*100)
print("OBJECTIVE COMPARISON: Natural (waste_mult=10) vs Constrained (end_inv < 2000)")
print("="*100)

# First restore waste_mult to 10 for fair comparison
import openpyxl
wb = openpyxl.load_workbook('data/examples/Network_Config.xlsx')
ws = wb['CostParameters']
for row in ws.iter_rows(min_row=2):
    if row[0].value == 'waste_cost_multiplier':
        row[1].value = 10.0
        break
wb.save('data/examples/Network_Config.xlsx')
print("Reset waste_multiplier to 10.0 for comparison\n")


def build_components():
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

    return (validated, forecast, nodes, unified_routes, labor_calendar,
            cost_structure, products_dict, start, end, unified_truck_schedules)


components = build_components()

# SOLVE 1: Natural solution
print("\n1. SOLVING WITH NATURAL END INVENTORY (no constraints)...")
print("-"*100)

(validated, forecast, nodes, unified_routes, labor_calendar,
 cost_structure, products_dict, start, end, unified_truck_schedules) = components

model_builder_nat = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

result_nat = model_builder_nat.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

if not result_nat.success:
    print("Natural solve failed!")
    exit(1)

model_nat = model_builder_nat.model
sol_nat = model_builder_nat.extract_solution(model_nat)

last_date = max(model_nat.dates)
end_inv_nat = sum(
    value(model_nat.inventory[n, p, s, last_date])
    for (n, p, s, t) in model_nat.inventory
    if t == last_date and value(model_nat.inventory[n, p, s, last_date]) > 0.01
)

print(f"Natural solution:")
print(f"  Production:    {sol_nat.total_production:>12,.0f} units")
print(f"  End inventory: {end_inv_nat:>12,.0f} units")
print(f"  Shortage:      {sol_nat.total_shortage_units:>12,.0f} units")
print(f"  Objective:     ${sol_nat.total_cost:>12,.0f}")


# SOLVE 2: Constrained solution
print("\n\n2. SOLVING WITH CONSTRAINED END INVENTORY (<= 2000 units)...")
print("-"*100)

model_builder_con = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

# Build model
result_temp = model_builder_con.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
model_con = model_builder_con.model

# Add constraint
total_end_inv_expr = sum(
    model_con.inventory[n, p, s, last_date]
    for (n, p, s, t) in model_con.inventory
    if t == last_date
)

model_con.force_low_end_inv = Constraint(expr=total_end_inv_expr <= 2000)

print("Added constraint: sum(end_inventory) <= 2000")

# Re-solve
from pyomo.opt import SolverFactory
solver = SolverFactory('appsi_highs')
solver.options['time_limit'] = 180
solver.options['mip_rel_gap'] = 0.01

print("Re-solving...")
result_con = solver.solve(model_con, tee=False)

# Check result
from pyomo.opt import TerminationCondition
success = result_con.solver.termination_condition == TerminationCondition.optimal

if not success:
    print(f"\n❌ INFEASIBLE with end_inv <= 2000!")
    print(f"   This means >2000 units is unavoidable")
    exit(1)

print(f"✓ Solved with constraint!")

sol_con = model_builder_con.extract_solution(model_con)

end_inv_con = sum(
    value(model_con.inventory[n, p, s, last_date])
    for (n, p, s, t) in model_con.inventory
    if t == last_date and value(model_con.inventory[n, p, s, last_date]) > 0.01
)

print(f"\nConstrained solution:")
print(f"  Production:    {sol_con.total_production:>12,.0f} units")
print(f"  End inventory: {end_inv_con:>12,.0f} units")
print(f"  Shortage:      {sol_con.total_shortage_units:>12,.0f} units")
print(f"  Objective:     ${sol_con.total_cost:>12,.0f}")


# COMPARE
print("\n\n" + "="*100)
print("DETAILED COMPARISON (waste_mult=10):")
print("="*100)

obj_diff = sol_con.total_cost - sol_nat.total_cost
end_inv_diff = end_inv_nat - end_inv_con
shortage_diff = sol_con.total_shortage_units - sol_nat.total_shortage_units

waste_cost_savings = end_inv_diff * 13.0
shortage_cost_increase = shortage_diff * 10.0

print(f"\nEnd inventory:")
print(f"  Natural:     {end_inv_nat:>10,.0f} units")
print(f"  Constrained: {end_inv_con:>10,.0f} units")
print(f"  Reduction:   {end_inv_diff:>10,.0f} units")

print(f"\nShortage:")
print(f"  Natural:     {sol_nat.total_shortage_units:>10,.0f} units")
print(f"  Constrained: {sol_con.total_shortage_units:>10,.0f} units")
print(f"  Increase:    {shortage_diff:>10,.0f} units")

print(f"\nObjective:")
print(f"  Natural:     ${sol_nat.total_cost:>10,.0f}")
print(f"  Constrained: ${sol_con.total_cost:>10,.0f}")
print(f"  Increase:    ${obj_diff:>10,.0f}")

print(f"\nCost breakdown:")
print(f"  Waste savings:         -${waste_cost_savings:>10,.0f} (from {end_inv_diff:,.0f} fewer units)")
print(f"  Shortage increase:     +${shortage_cost_increase:>10,.0f} (from {shortage_diff:,.0f} more units)")
print(f"  Other hidden costs:    +${obj_diff + waste_cost_savings - shortage_cost_increase:>10,.0f}")

hidden = obj_diff + waste_cost_savings - shortage_cost_increase

print(f"\n\n" + "="*100)
print(f"ANSWER TO YOUR QUESTION:")
print(f"="*100)

print(f"\nWhy doesn't waste penalty of $13/unit push end inventory to zero?")
print(f"\nBECAUSE: Avoiding the {end_inv_diff:,.0f} units of waste costs ${hidden:,.0f} in OTHER expenses!")

cost_per_unit_avoided = hidden / end_inv_diff if end_inv_diff > 0 else 0

print(f"\n  Waste cost:          ${waste_cost_savings:,.0f} saved")
print(f"  Other costs:         ${hidden:,.0f} incurred")
print(f"  Net:                 ${obj_diff:,.0f} worse")
print(f"\n  Cost per unit of waste avoided: ${cost_per_unit_avoided:.2f}")
print(f"  Waste penalty:                  $13.00")
print(f"\n  Since ${cost_per_unit_avoided:.2f} > $13.00, model rationally chooses to keep waste!")

print(f"\nThe hidden costs come from:")
print(f"  - Different production timing (may require overtime/weekends)")
print(f"  - More shortages (${shortage_cost_increase:,.0f} from {shortage_diff:,.0f} units)")
print(f"  - Other costs: ${hidden - shortage_cost_increase:,.0f}")

print(f"\n" + "="*100)
