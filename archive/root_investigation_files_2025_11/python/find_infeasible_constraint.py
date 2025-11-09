"""Use Pyomo's infeasibility tools to identify conflicting constraints.

This will compute an Irreducible Infeasible Subsystem (IIS) or compute infeasibility.
"""
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from pyomo.util.infeasible import log_infeasible_constraints
import logging

# Set up logging to see infeasible constraints
logging.basicConfig(level=logging.INFO)

print("=" * 80)
print("INFEASIBLE CONSTRAINT IDENTIFICATION")
print("=" * 80)

# Parse (EXACT UI config)
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

start_date = inventory_snapshot.snapshot_date + timedelta(days=1)
end_date = start_date + timedelta(days=27)

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()

print(f"\nConfiguration:")
print(f"  Snapshot date: {inventory_snapshot.snapshot_date}")
print(f"  Planning: {start_date} to {end_date}")
print(f"  Initial inv: {len(initial_inv_dict)} entries")

# Build model
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=inventory_snapshot.snapshot_date,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=True
)

pyomo_model = model.build_model()

# Solve WITHOUT exception handling to see raw HiGHS output
print(f"\nSolving...")
from pyomo.contrib.appsi.solvers import Highs

solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 60
solver.config.mip_gap = 0.05

results = solver.solve(pyomo_model)

print(f"\n" + "=" * 80)
print("SOLVE RESULT")
print("=" * 80)
print(f"Termination: {results.termination_condition}")

from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC

if results.termination_condition == AppsiTC.infeasible:
    print(f"\n❌ MODEL IS INFEASIBLE")
    print(f"\nUsing Pyomo's infeasibility analysis tool...")
    print(f"\n" + "=" * 80)
    print("INFEASIBLE CONSTRAINTS (if any with tol violation)")
    print("=" * 80)

    # This will print constraints that are violated
    log_infeasible_constraints(pyomo_model)

    print(f"\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print(f"Review the constraints listed above.")
    print(f"Look for patterns in:")
    print(f"  - Material balance constraints on first day")
    print(f"  - Pallet ceiling constraints")
    print(f"  - Arrival calculations with in_transit variables")
else:
    print(f"\n✅ MODEL IS FEASIBLE")
    print(f"  Objective: ${results.best_feasible_objective:,.2f}")
    print(f"\n  The model is NOT infeasible!")
    print(f"  If you're seeing errors, it's a different issue (not infeasibility)")
