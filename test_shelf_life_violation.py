"""Test if initial inventory violates shelf life windows.

Hypothesis: 17-day ambient shelf life window constraint may be violated
by initial inventory that's too old or too large.
"""
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

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# EXACT UI scenario
start_date = date(2025, 10, 17)
end_date = date(2025, 11, 13)
snapshot_date = date(2025, 10, 16)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Get initial inventory
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    inv_2tuple = inventory_snapshot.to_optimization_dict()
    initial_inv_dict = {}
    for (location, product), quantity in inv_2tuple.items():
        initial_inv_dict[(location, product, 'ambient')] = quantity
else:
    initial_inv_dict = {}

print(f"Scenario:")
print(f"  Snapshot: {snapshot_date}")
print(f"  Planning: {start_date} to {end_date}")
print(f"  Inventory age on {start_date}: {(start_date - snapshot_date).days} day(s)")
print(f"  Initial inventory: {len(initial_inv_dict)} entries, {sum(initial_inv_dict.values()):,.0f} units")

# Test WITHOUT pallet tracking first
print(f"\n" + "=" * 80)
print("TEST 1: WITHOUT pallet tracking")
print("=" * 80)

m1 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=False,  # Disable pallets
    use_truck_pallet_tracking=False
)

pm1 = m1.build_model()

from pyomo.contrib.appsi.solvers import Highs
solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 60
solver.config.mip_gap = 0.05

r1 = solver.solve(pm1)
print(f"Result: {r1.termination_condition}")

# Test WITH pallet tracking
print(f"\n" + "=" * 80)
print("TEST 2: WITH pallet tracking")
print("=" * 80)

m2 = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,  # Enable pallets
    use_truck_pallet_tracking=True
)

pm2 = m2.build_model()
r2 = solver.solve(pm2)
print(f"Result: {r2.termination_condition}")

print(f"\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC

if r1.termination_condition == AppsiTC.optimal and r2.termination_condition == AppsiTC.infeasible:
    print(f"\nINFEASIBILITY ISOLATED:")
    print(f"  Without pallets: OPTIMAL")
    print(f"  With pallets: INFEASIBLE")
    print(f"\n  Issue is in PALLET CONSTRAINTS")
    print(f"  Likely: Storage pallet ceiling or pallet entry detection")
elif r1.termination_condition == AppsiTC.infeasible:
    print(f"\nINFEASIBILITY in base model (no pallets):")
    print(f"  Issue is in CORE constraints")
    print(f"  Likely: Shelf life or material balance")
else:
    print(f"\nBoth tests OPTIMAL - cannot replicate")
