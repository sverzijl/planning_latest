"""
Analyze consumption and demand by node to understand the discrepancy.
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

print(f"Solved successfully!\n")
model = model_builder.model
solution = model_builder.extract_solution(model)

# Analyze by node
print("="*80)
print("CONSUMPTION AND DEMAND BY NODE")
print("="*80)

# Get demand by node
demand_by_node = {}
for (node_id, prod, t) in model_builder.demand.keys():
    demand_by_node[node_id] = demand_by_node.get(node_id, 0) + model_builder.demand[(node_id, prod, t)]

# Get consumed by node
consumed_by_node = {}
for (node_id, prod, t), qty in solution.demand_consumed.items():
    consumed_by_node[node_id] = consumed_by_node.get(node_id, 0) + qty

# Get initial inventory by node
init_inv_by_node = {}
for (node_id, prod, state) in model_builder.initial_inventory.keys():
    init_inv_by_node[node_id] = init_inv_by_node.get(node_id, 0) + model_builder.initial_inventory[(node_id, prod, state)]

print(f"\n{'Node':<10} {'Type':>8} {'Init Inv':>12} {'Demand':>12} {'Consumed':>12} {'Production':>12}")
print("-"*80)

# Get all nodes (including manufacturing)
all_nodes = set(demand_by_node.keys()) | set(init_inv_by_node.keys()) | set(['6122'])

# Get production by node
production_by_node = {}
if hasattr(solution, 'production_batches') and solution.production_batches:
    for batch in solution.production_batches:
        node_id = batch.node if hasattr(batch, 'node') else (batch.location_id if hasattr(batch, 'location_id') else None)
        qty = batch.quantity if hasattr(batch, 'quantity') else 0
        if node_id and qty:
            production_by_node[node_id] = production_by_node.get(node_id, 0) + qty

for node_id in sorted(all_nodes):
    node_type = 'MFG' if node_id == '6122' else 'DEMAND'
    init_inv = init_inv_by_node.get(node_id, 0)
    demand = demand_by_node.get(node_id, 0)
    consumed = consumed_by_node.get(node_id, 0)
    production = production_by_node.get(node_id, 0)

    print(f"{node_id:<10} {node_type:>8} {init_inv:>12,.0f} {demand:>12,.0f} {consumed:>12,.0f} {production:>12,.0f}")

print("-"*60)
print(f"{'TOTAL':<10} {sum(init_inv_by_node.values()):>12,.0f} {sum(demand_by_node.values()):>12,.0f} {sum(consumed_by_node.values()):>12,.0f}")

print("\n" + "="*80)
print("KEY OBSERVATION:")
print("="*80)
print(f"\nIf consumed > init_inv for a node, where did the extra goods come from?")
print(f"Options:")
print(f"  1. Production at that node (but only 6122 can produce)")
print(f"  2. Shipments arriving from other nodes")
print(f"  3. BUG: Phantom supply (material balance violation)")

print("\n" + "="*80)
