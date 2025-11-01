"""Now that we can replicate, analyze the actual infeasibility."""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Use alias resolver to make inventory match
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_snapshot = inv_parser.parse()

# Override snapshot to Oct 16
inventory_snapshot.snapshot_date = date(2025, 10, 16)

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start_date = date(2025, 10, 17)
end_date = date(2025, 11, 13)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Get inventory
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    inv_2tuple = inventory_snapshot.to_optimization_dict()
    initial_inv_dict = {}
    for (location, product), quantity in inv_2tuple.items():
        initial_inv_dict[(location, product, 'ambient')] = quantity
else:
    initial_inv_dict = {}

print(f"Configuration that causes infeasibility:")
print(f"  Products: {list(products.keys())[:3]}")
print(f"  Inventory products: {list(set(p for (l,p,s) in initial_inv_dict.keys()))[:3]}")
print(f"  Inventory total: {sum(initial_inv_dict.values()):,.0f} units")
print(f"  Planning: {start_date} to {end_date}")

# Build model
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=date(2025, 10, 16),
    allow_shortages=True,
    use_pallet_tracking=False,
    use_truck_pallet_tracking=False
)

pyomo_model = model.build_model()

print(f"\nSolving to check if infeasible...")
from pyomo.contrib.appsi.solvers import Highs

solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 60
solver.config.mip_gap = 0.01

results = solver.solve(pyomo_model)

print(f"\nResult: {results.termination_condition}")
from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC

if results.termination_condition == AppsiTC.infeasible:
    print(f"INFEASIBLE - Now analyzing constraints...")
    import logging
    logging.basicConfig(level=logging.INFO)
    from pyomo.util.infeasible import log_infeasible_constraints
    log_infeasible_constraints(pyomo_model, log_expression=True, log_variables=True)
else:
    print(f"OPTIMAL - Objective: ${results.best_feasible_objective:,.2f}")
