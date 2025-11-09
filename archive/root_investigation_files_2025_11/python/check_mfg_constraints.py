"""
Check if material balance constraints exist for manufacturing node.

If they're being skipped, that explains the violation!
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
print("Building model...")
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

print(f"Model solved!\n")
model = model_builder.model

# Check for manufacturing constraints
print("="*80)
print("CHECKING MATERIAL BALANCE CONSTRAINTS FOR MANUFACTURING (6122)")
print("="*80)

mfg_node = '6122'

# Check ambient_balance_con
if hasattr(model, 'ambient_balance_con'):
    ambient_constraints = []
    for key in model.ambient_balance_con:
        if key[0] == mfg_node:  # node_id is first element
            ambient_constraints.append(key)

    print(f"\nAmbient balance constraints for {mfg_node}:")
    print(f"  Found: {len(ambient_constraints)} constraints")

    if len(ambient_constraints) > 0:
        print(f"  Expected: {len(list(model.products)) * len(list(model.dates))} (5 products × 28 dates = 140)")

        if len(ambient_constraints) < len(list(model.products)) * len(list(model.dates)):
            print(f"  ❌ MISSING CONSTRAINTS! Only {len(ambient_constraints)} out of 140 expected")
        else:
            print(f"  ✓ All constraints present")

        # Check if any are skipped/deactivated
        active_count = sum(1 for key in ambient_constraints if model.ambient_balance_con[key].active)
        print(f"  Active: {active_count}/{len(ambient_constraints)}")

        if active_count < len(ambient_constraints):
            print(f"  ⚠️ Some constraints are DEACTIVATED!")

        # Show a sample constraint
        if len(ambient_constraints) > 0:
            sample_key = ambient_constraints[0]
            print(f"\n  Sample constraint: {sample_key}")
            try:
                constraint = model.ambient_balance_con[sample_key]
                print(f"    Active: {constraint.active}")
                print(f"    Expression: {constraint.expr}")
            except Exception as e:
                print(f"    Error accessing: {e}")
    else:
        print(f"  ❌ NO CONSTRAINTS FOUND FOR {mfg_node}!")
        print(f"  This means material balance is NOT enforced at manufacturing!")
else:
    print(f"  ❌ ambient_balance_con DOES NOT EXIST!")

# Check if manufacturing node supports ambient storage
print(f"\n\nCHECKING NODE CAPABILITIES:")
if mfg_node in model_builder.nodes:
    node = model_builder.nodes[mfg_node]
    print(f"  Node type: {node.node_type}")
    print(f"  Can store: {node.capabilities.can_store}")
    print(f"  Supports ambient: {node.supports_ambient_storage()}")
    print(f"  Supports frozen: {node.supports_frozen_storage()}")
    print(f"  Can produce: {node.can_produce()}")

    if not node.supports_ambient_storage():
        print(f"\n  ❌ NODE DOES NOT SUPPORT AMBIENT STORAGE!")
        print(f"  Material balance constraint would be SKIPPED (line 1598-1599 in model)")
        print(f"  This is the BUG - manufacturing should support storage!")

print("\n" + "="*80)
