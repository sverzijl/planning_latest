"""Debug constraint creation."""
from datetime import date, timedelta
from pyomo.core.base import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

# Parse
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=1)  # Just 2 days for simplicity

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Build
pyomo_model = model.build_model()

# Check constraints
print("=" * 80)
print("CONSTRAINT INSPECTION")
print("=" * 80)

print(f"\n1. Ambient balance constraints:")
if hasattr(pyomo_model, 'ambient_balance_con'):
    num_cons = len(list(pyomo_model.ambient_balance_con))
    print(f"   Total: {num_cons}")

    # Show constraints for DEMAND NODES (not manufacturing)
    demand_node_ids = set(n for (n, p, t) in model.demand.keys())
    first_demand_node = list(demand_node_ids)[0]
    print(f"\n   Constraints for DEMAND node {first_demand_node}:")
    for idx in list(pyomo_model.ambient_balance_con):
        if idx[0] == first_demand_node:
            con = pyomo_model.ambient_balance_con[idx]
            print(f"   ambient_balance{idx}")
            print(f"     Expression: {con.expr}")
            break  # Just show one

else:
    print(f"   NOT FOUND!")

print(f"\n2. Demand balance constraints:")
if hasattr(pyomo_model, 'demand_balance_con'):
    num_cons = len(list(pyomo_model.demand_balance_con))
    print(f"   Total: {num_cons}")

    # Sample first few
    for idx in list(pyomo_model.demand_balance_con)[:3]:
        con = pyomo_model.demand_balance_con[idx]
        print(f"   demand_balance{idx}")
        print(f"     Expression: {con.expr}")
else:
    print(f"   NOT FOUND!")

print(f"\n3. Production variables for manufacturing node:")
mfg_node_id = '6122'
prod_vars = [(n, p, t) for (n, p, t) in pyomo_model.production if n == mfg_node_id]
print(f"   Production variables for {mfg_node_id}: {len(prod_vars)}")
if prod_vars:
    print(f"   Sample: {prod_vars[:3]}")

print(f"\n4. Demand at first date:")
first_date = start
demand_at_first = [(n, p, t) for (n, p, t) in model.demand.keys() if t == first_date]
print(f"   Demand entries on {first_date}: {len(demand_at_first)}")
total_demand_first = sum(model.demand[k] for k in demand_at_first)
print(f"   Total demand on {first_date}: {total_demand_first:,.0f} units")

print(f"\n5. Check if demand nodes have ambient_balance constraints:")
demand_node_ids = set(n for (n, p, t) in model.demand.keys())
for node_id in list(demand_node_ids)[:3]:
    has_ambient = any(idx[0] == node_id for idx in pyomo_model.ambient_balance_con)
    print(f"   Node {node_id}: ambient_balance = {has_ambient}")

    # Check if node supports ambient
    node = nodes_dict = {n.id: n for n in nodes}
    if node_id in nodes_dict:
        node_obj = nodes_dict[node_id]
        print(f"     supports_ambient: {node_obj.supports_ambient_storage()}")
        print(f"     has_demand: {node_obj.has_demand_capability()}")
