"""
Verify consumption extraction - compare Pyomo model values to solution object.

This will show if consumption is being incorrectly extracted or calculated.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Load and solve model
print("Building and solving model...")
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(
        location_id=entry.node_id,
        product_id=entry.product_id,
        forecast_date=entry.demand_date,
        quantity=entry.quantity
    )
    for entry in validated.demand_entries
]
forecast = Forecast(name="Test Forecast", entries=forecast_entries)

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

products_dict = {p.id: p for p in validated.products}

horizon_days = 28
start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=horizon_days-1)).date()

model_builder = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products_dict,
    start_date=start,
    end_date=end,
    truck_schedules=unified_truck_schedules,
    initial_inventory=validated.get_inventory_dict(),
    inventory_snapshot_date=validated.inventory_snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

if not result.success:
    print(f"Solve failed: {result.termination_condition}")
    exit(1)

print(f"Solved!\n")
model = model_builder.model
solution = model_builder.extract_solution(model)

# Extract consumption directly from Pyomo model
print("="*100)
print("CONSUMPTION VERIFICATION - PYOMO MODEL VS SOLUTION OBJECT")
print("="*100)

# Method 1: From Pyomo model (sum of demand_consumed_from_ambient + demand_consumed_from_thawed)
pyomo_consumption_by_node = {}

if hasattr(model, 'demand_consumed_from_ambient') and hasattr(model, 'demand_consumed_from_thawed'):
    for (node_id, prod, t) in model.demand_consumed_from_ambient:
        try:
            amb = value(model.demand_consumed_from_ambient[node_id, prod, t])
            tha = value(model.demand_consumed_from_thawed[node_id, prod, t]) if (node_id, prod, t) in model.demand_consumed_from_thawed else 0
            total = amb + tha

            pyomo_consumption_by_node[node_id] = pyomo_consumption_by_node.get(node_id, 0) + total
        except:
            pass

# Method 2: From solution object
solution_consumption_by_node = {}

if hasattr(solution, 'demand_consumed'):
    for (node_id, prod, t), qty in solution.demand_consumed.items():
        solution_consumption_by_node[node_id] = solution_consumption_by_node.get(node_id, 0) + qty

# Compare
print(f"\n{'Node':<15} {'Pyomo Model':>20} {'Solution Object':>20} {'Difference':>15}")
print("-"*75)

all_nodes = set(pyomo_consumption_by_node.keys()) | set(solution_consumption_by_node.keys())

for node_id in sorted(all_nodes):
    pyomo_val = pyomo_consumption_by_node.get(node_id, 0)
    solution_val = solution_consumption_by_node.get(node_id, 0)
    diff = abs(pyomo_val - solution_val)

    print(f"{node_id:<15} {pyomo_val:>20,.0f} {solution_val:>20,.0f} {diff:>15,.0f}")

print("-"*75)
print(f"{'TOTAL':<15} {sum(pyomo_consumption_by_node.values()):>20,.0f} {sum(solution_consumption_by_node.values()):>20,.0f} {abs(sum(pyomo_consumption_by_node.values()) - sum(solution_consumption_by_node.values())):>15,.0f}")

print(f"\n\n{'='*100}")
if abs(sum(pyomo_consumption_by_node.values()) - sum(solution_consumption_by_node.values())) < 100:
    print(f"✓ Pyomo and Solution match - extraction is correct")
else:
    print(f"❌ MISMATCH - extraction has a bug!")

print(f"{'='*100}")

# Also verify against DEMAND
total_demand = sum(model_builder.demand.values())
total_consumed_pyomo = sum(pyomo_consumption_by_node.values())
total_shortage = solution.total_shortage_units

print(f"\n\nDEMAND EQUATION CHECK:")
print(f"  Total demand:             {total_demand:>15,.0f}")
print(f"  Consumed (from Pyomo):    {total_consumed_pyomo:>15,.0f}")
print(f"  Shortage:                 {total_shortage:>15,.0f}")
print(f"  Consumed + Shortage:      {total_consumed_pyomo + total_shortage:>15,.0f}")
print(f"  ────────────────────────────────────────")
print(f"  Error:                    {abs((total_consumed_pyomo + total_shortage) - total_demand):>15,.0f}")

if abs((total_consumed_pyomo + total_shortage) - total_demand) < 100:
    print(f"\n✓ Demand equation holds")
else:
    print(f"\n❌ Demand equation violated!")

print(f"\n{'='*100}")
