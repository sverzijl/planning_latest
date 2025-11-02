"""Test with PLANNING START = 2025-10-16 (not snapshot + 1)"""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("TEST: PLANNING STARTS 2025-10-16 (not snapshot + 1)")

# Parse
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# PLANNING STARTS on Oct 16 (maybe snapshot is Oct 15?)
start_date = date(2025, 10, 16)
end_date = start_date + timedelta(days=27)  # 4 weeks

print(f"Planning: {start_date} to {end_date}")

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Convert inventory
initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()
else:
    for entry in inventory_snapshot.entries:
        key = (entry.location_id, entry.product_id, 'ambient')
        initial_inv_dict[key] = initial_inv_dict.get(key, 0) + entry.quantity

# Build
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params,
    start_date=start_date,  # PLANNING STARTS Oct 16
    end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=date(2025, 10, 15),  # Snapshot day before
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

pyomo_model = model.build_model()

# Solve
from pyomo.contrib.appsi.solvers import Highs
solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 120
solver.config.mip_gap = 0.01

results = solver.solve(pyomo_model)

print(f"\nResult: {results.termination_condition}")

from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC
if results.termination_condition == AppsiTC.infeasible:
    print(f"❌ INFEASIBLE - Issue replicated!")
else:
    print(f"✅ OPTIMAL: ${results.best_feasible_objective:,.2f}")
