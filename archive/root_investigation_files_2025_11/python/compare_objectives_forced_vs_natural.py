"""
MIP Economic Analysis: Compare objective with natural end inventory vs forced zero.

This will show WHAT the model is avoiding by keeping end inventory.
If forcing zero costs $X more, but waste cost is only $Y, and X >> Y,
then model is making rational choice (avoiding hidden costs).
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


def build_and_solve(force_zero_end_inv=False, waste_mult=10.0):
    """Build and solve model with optional forced zero end inventory."""

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

    # Modify waste multiplier
    cost_structure = cost_structure.model_copy(update={'waste_cost_multiplier': waste_mult})

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

    # Solve normally first
    result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

    if not result.success:
        return None

    model = model_builder.model
    solution = model_builder.extract_solution(model)

    # If forcing zero, resolve with constraint
    if force_zero_end_inv:
        print("  Adding constraint: end_inventory <= 2000...")

        last_date = max(model.dates)
        total_end_inv = sum(
            model.inventory[n, p, s, last_date]
            for (n, p, s, t) in model.inventory
            if t == last_date
        )

        model.force_zero_end_inv_con = Constraint(expr=total_end_inv <= 2000)

        # Re-solve
        from pyomo.opt import SolverFactory
        solver = SolverFactory('appsi_highs')
        result = solver.solve(model)

        solution = model_builder.extract_solution(model)

    return model, solution, model_builder


print("="*100)
print("MIP ECONOMIC ANALYSIS: Natural vs Forced Low End Inventory")
print("="*100)

print("\n\n1. SOLVING WITH NATURAL END INVENTORY (waste_mult=10)...")
print("-"*100)

model_natural, sol_natural, builder_natural = build_and_solve(force_zero_end_inv=False, waste_mult=10.0)

if not sol_natural:
    print("Solve failed!")
    exit(1)

# Extract metrics for natural solution
last_date = max(model_natural.dates)
end_inv_natural = sum(
    value(model_natural.inventory[n, p, s, last_date])
    for (n, p, s, t) in model_natural.inventory
    if t == last_date and value(model_natural.inventory[n, p, s, last_date]) > 0.01
)

print(f"\nNatural solution (waste_mult=10):")
print(f"  Production:     {sol_natural.total_production:>12,.0f} units")
print(f"  End inventory:  {end_inv_natural:>12,.0f} units")
print(f"  Shortage:       {sol_natural.total_shortage_units:>12,.0f} units")
print(f"  Objective:      ${sol_natural.total_cost:>12,.0f}")

# Calculate component costs
waste_cost_natural = end_inv_natural * 10.0 * 1.3
shortage_cost_natural = sol_natural.total_shortage_units * 10.0

print(f"  Waste cost:     ${waste_cost_natural:>12,.0f}")
print(f"  Shortage cost:  ${shortage_cost_natural:>12,.0f}")


print("\n\n2. SOLVING WITH FORCED LOW END INVENTORY...")
print("-"*100)

model_forced, sol_forced, builder_forced = build_and_solve(force_zero_end_inv=True, waste_mult=10.0)

if not sol_forced:
    print("Solve failed with forced constraint!")
    exit(1)

# Extract metrics for forced solution
end_inv_forced = sum(
    value(model_forced.inventory[n, p, s, last_date])
    for (n, p, s, t) in model_forced.inventory
    if t == last_date and value(model_forced.inventory[n, p, s, last_date]) > 0.01
)

print(f"\nForced solution (end_inv <= 2000):")
print(f"  Production:     {sol_forced.total_production:>12,.0f} units")
print(f"  End inventory:  {end_inv_forced:>12,.0f} units")
print(f"  Shortage:       {sol_forced.total_shortage_units:>12,.0f} units")
print(f"  Objective:      ${sol_forced.total_cost:>12,.0f}")

# Calculate component costs
waste_cost_forced = end_inv_forced * 10.0 * 1.3
shortage_cost_forced = sol_forced.total_shortage_units * 10.0

print(f"  Waste cost:     ${waste_cost_forced:>12,.0f}")
print(f"  Shortage cost:  ${shortage_cost_forced:>12,.0f}")


print("\n\n" + "="*100)
print("COMPARISON:")
print("="*100)

objective_diff = sol_forced.total_cost - sol_natural.total_cost
waste_savings = waste_cost_natural - waste_cost_forced
shortage_increase = shortage_cost_forced - shortage_cost_natural

print(f"\nObjective difference:")
print(f"  Natural:  ${sol_natural.total_cost:>12,.0f}")
print(f"  Forced:   ${sol_forced.total_cost:>12,.0f}")
print(f"  Increase: ${objective_diff:>12,.0f}")

print(f"\nWaste cost difference:")
print(f"  Natural:  ${waste_cost_natural:>12,.0f}")
print(f"  Forced:   ${waste_cost_forced:>12,.0f}")
print(f"  Savings:  ${waste_savings:>12,.0f}")

print(f"\nShortage cost difference:")
print(f"  Natural:  ${shortage_cost_natural:>12,.0f}")
print(f"  Forced:   ${shortage_cost_forced:>12,.0f}")
print(f"  Increase: ${shortage_increase:>12,.0f}")

print(f"\n\n" + "="*100)
print(f"MIP THEORY DIAGNOSIS:")
print(f"="*100)

hidden_cost = objective_diff - waste_savings + shortage_increase

print(f"\nAccounting:")
print(f"  Total objective increase:  ${objective_diff:>10,.0f}")
print(f"  Waste savings:             ${waste_savings:>10,.0f}")
print(f"  Shortage increase:         ${shortage_increase:>10,.0f}")
print(f"  Hidden cost:               ${hidden_cost:>10,.0f}")

if hidden_cost > 50000:
    print(f"\n❌ HIDDEN COST FOUND: ${hidden_cost:,.0f}!")
    print(f"\n   Forcing low end inventory increases OTHER costs by ${hidden_cost:,.0f}")
    print(f"   This is WHY model keeps end inventory even with waste penalty:")
    print(f"\n   The hidden costs are likely:")
    print(f"     - Labor cost (more production days, overtime, weekends)")
    print(f"     - Transport cost (more shipments, different routing)")
    print(f"     - Holding cost (inventory held longer during horizon)")
    print(f"     - Changeover cost (more product switches)")
    print(f"\n   Model chooses:")
    print(f"     Pay ${waste_cost_natural:,.0f} waste")
    print(f"     Avoid ${hidden_cost:,.0f} in other costs")
    print(f"     Net: Save ${hidden_cost - waste_cost_natural:,.0f}")
    print(f"\n   THIS IS ECONOMICALLY RATIONAL!")
    print(f"\n   To force low end inventory, waste penalty must exceed hidden costs:")
    print(f"     Required: waste_multiplier > {hidden_cost / (end_inv_natural * 1.3):.1f}")
else:
    print(f"\n   Hidden cost is small (${hidden_cost:,.0f})")
    print(f"   Waste multiplier of 10 should be sufficient")
    print(f"   Something else is wrong")

print(f"\n" + "="*100)
