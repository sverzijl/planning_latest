"""
MIP Experiment: Force end inventory to be low and see if feasible.

If model can find a solution with low end inventory, current high end inventory
is due to objective/cost issue, not infeasibility.

If model becomes infeasible, constraints truly prevent low end inventory.
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
print("MIP EXPERIMENT: Force Low End Inventory")
print("="*100)

# Build model
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

# Build the model but don't solve yet
print("\nBuilding model...")
model = model_builder._build_model()

# Add constraint: Force end inventory to be small
last_date = max(model.dates)
max_end_inv_target = 5000  # Mix rounding allowance

print(f"\nAdding constraint: Total end inventory <= {max_end_inv_target} units")

# Create constraint that sums all end inventory
total_end_inv_expr = sum(
    model.inventory[n, p, s, last_date]
    for (n, p, s, t) in model.inventory
    if t == last_date
)

model.force_low_end_inv = Constraint(
    expr=total_end_inv_expr <= max_end_inv_target
)

print("Constraint added.")

# Solve with forced constraint
print(f"\nSolving with forced low end inventory constraint...")
result = model_builder._solve_model(model, solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

print(f"\n\n{'='*100}")
print(f"RESULT:")
print(f"{'='*100}")

if not result.success:
    print(f"\n❌ INFEASIBLE with end inventory <= {max_end_inv_target}!")
    print(f"   Termination: {result.termination_condition}")
    print(f"\n   This means constraints FORCE end inventory to be >5k")
    print(f"   The 15k end inventory is unavoidable given model structure")
    print(f"\n   Constraints preventing low end inventory:")
    print(f"     - Shelf life (17 days)")
    print(f"     - Network transit times")
    print(f"     - Production timing")
    print(f"     - Truck schedules")
else:
    solution = model_builder.extract_solution(model)

    end_inv_actual = sum(
        value(model.inventory[n, p, s, last_date])
        for (n, p, s, t) in model.inventory
        if t == last_date and value(model.inventory[n, p, s, last_date]) > 0.01
    )

    print(f"\n✅ FEASIBLE with end inventory <= {max_end_inv_target}!")
    print(f"   Actual end inventory: {end_inv_actual:,.0f} units")
    print(f"   Production: {solution.total_production:,.0f} units")
    print(f"   Shortage: {solution.total_shortage_units:,.0f} units")
    print(f"   Objective: ${solution.total_cost:,.0f}")
    print(f"\n   → Low end inventory IS achievable!")
    print(f"   → Current high end inventory is due to OBJECTIVE/COST issue")
    print(f"   → NOT due to infeasibility")
    print(f"\n   This means:")
    print(f"     - Waste cost coefficient too low, OR")
    print(f"     - Waste cost not actually in objective, OR")
    print(f"     - Some other cost is dominating and forcing overproduction")

print(f"\n{'='*100}")
