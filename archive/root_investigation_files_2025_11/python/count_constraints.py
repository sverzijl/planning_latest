"""
Count how many material balance constraints SHOULD exist vs how many ACTUALLY exist.

If some are missing, that's the bug!
"""

from datetime import datetime, timedelta
from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Load data
print("Loading data...")
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

# Count constraints
print("="*100)
print("MATERIAL BALANCE CONSTRAINT COUNT")
print("="*100)

# Expected count
num_nodes = len(model.nodes)
num_products = len(model.products)
num_dates = len(model.dates)

print(f"\nModel dimensions:")
print(f"  Nodes: {num_nodes}")
print(f"  Products: {num_products}")
print(f"  Dates: {num_dates}")
print(f"  Maximum possible constraints: {num_nodes} × {num_products} × {num_dates} = {num_nodes * num_products * num_dates}")

# Actual count
ambient_count = len(model.ambient_balance_con) if hasattr(model, 'ambient_balance_con') else 0
frozen_count = len(model.frozen_balance_con) if hasattr(model, 'frozen_balance_con') else 0
thawed_count = len(model.thawed_balance_con) if hasattr(model, 'thawed_balance_con') else 0

total_balance_constraints = ambient_count + frozen_count + thawed_count

print(f"\nActual material balance constraints:")
print(f"  Ambient: {ambient_count}")
print(f"  Frozen: {frozen_count}")
print(f"  Thawed: {thawed_count}")
print(f"  TOTAL: {total_balance_constraints}")

# Check inventory variables (these determine how many constraints SHOULD exist)
inventory_vars = len(model.inventory) if hasattr(model, 'inventory') else 0
print(f"\nInventory variables: {inventory_vars}")
print(f"  (One material balance constraint per inventory variable)")

if total_balance_constraints < inventory_vars:
    print(f"\n❌ MISSING CONSTRAINTS!")
    print(f"   Expected: {inventory_vars} (one per inventory variable)")
    print(f"   Actual: {total_balance_constraints}")
    print(f"   Missing: {inventory_vars - total_balance_constraints}")
elif total_balance_constraints == inventory_vars:
    print(f"\n✓ All expected constraints exist")
else:
    print(f"\n⚠️  More constraints than inventory variables?")

# Check for skipped constraints
print(f"\n\nCHECKING FOR SKIPPED CONSTRAINTS:")
print(f"Examining constraint index to see if any (node, prod, date) combinations are missing...")

# Build expected index
expected_keys = set()
for node_id in model.nodes:
    node = model_builder.nodes[node_id]
    if node.supports_ambient_storage():
        for prod in model.products:
            for t in model.dates:
                if (node_id, prod, 'ambient', t) in model.inventory:
                    expected_keys.add(('ambient', node_id, prod, t))

# Check actual
actual_keys = set(model.ambient_balance_con.keys()) if hasattr(model, 'ambient_balance_con') else set()

missing_keys = expected_keys - actual_keys

if len(missing_keys) > 0:
    print(f"\n❌ FOUND {len(missing_keys)} MISSING CONSTRAINTS!")
    print(f"First 10 missing:")
    for key in list(missing_keys)[:10]:
        print(f"  {key}")
else:
    print(f"\n✓ No missing ambient constraints")

print(f"\n{'='*100}")
