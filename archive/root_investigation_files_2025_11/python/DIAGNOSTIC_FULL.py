"""Complete diagnostic - outputs model file and all parameters for inspection.

This will help identify EXACTLY why the model is infeasible on your system.
"""
import subprocess
from datetime import timedelta, date
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("COMPLETE DIAGNOSTIC FOR INFEASIBILITY")
print("=" * 80)

# Git commit
result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
commit = result.stdout.strip()
print(f"\nGit commit: {commit}")
print(f"Short hash: {commit[:7]}")

# Parse
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

print(f"\nData Summary:")
print(f"  Forecast entries: {len(forecast.entries)}")
print(f"  Locations: {len(locations)}")
print(f"  Routes: {len(routes)}")
print(f"  Truck schedules: {len(truck_schedules)}")
print(f"  Inventory snapshot date: {inventory_snapshot.snapshot_date}")
print(f"  Inventory entries: {len(inventory_snapshot.entries)}")

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Dates
start_date = inventory_snapshot.snapshot_date + timedelta(days=1)
end_date = start_date + timedelta(days=27)

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

print(f"\nModel Parameters:")
print(f"  start_date: {start_date}")
print(f"  end_date: {end_date}")
print(f"  Days: {(end_date - start_date).days + 1}")
print(f"  initial_inventory entries: {len(initial_inv_dict)}")
print(f"  Total initial inv: {sum(initial_inv_dict.values()):,.0f} units")
print(f"  allow_shortages: True")
print(f"  use_pallet_tracking: True")
print(f"  use_truck_pallet_tracking: True")

# Build model
print(f"\nBuilding model...")
model = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    products=products,
    labor_calendar=labor_calendar,
    cost_structure=cost_params,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=inventory_snapshot.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

pyomo_model = model.build_model()

# Output model to file for inspection
print(f"\nWriting Pyomo model to file...")
pyomo_model.write('diagnostic_model.lp', format='lp')
print(f"  Model written to: diagnostic_model.lp")
print(f"  (You can inspect this file to see all constraints)")

# Check model statistics
print(f"\nModel Statistics:")
from pyomo.environ import Var, Constraint
var_count = sum(1 for _ in pyomo_model.component_data_objects(Var))
con_count = sum(1 for _ in pyomo_model.component_data_objects(Constraint, active=True))
print(f"  Total variables: {var_count}")
print(f"  Total constraints: {con_count}")

# Solve and capture detailed output
print(f"\nSolving...")
from pyomo.contrib.appsi.solvers import Highs

solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 120
solver.config.mip_gap = 0.01

results = solver.solve(pyomo_model)

print(f"\n" + "=" * 80)
print("RESULT")
print("=" * 80)
print(f"Termination: {results.termination_condition}")
print(f"Best objective: {results.best_feasible_objective}")
print(f"Best bound: {results.best_objective_bound if hasattr(results, 'best_objective_bound') else 'N/A'}")

from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC

if results.termination_condition == AppsiTC.infeasible:
    print(f"\n❌ INFEASIBLE - Issue replicated!")
    print(f"\n   Check diagnostic_model.lp for constraint details")
    print(f"   Commit: {commit[:7]}")
elif results.termination_condition == AppsiTC.optimal:
    print(f"\n✅ OPTIMAL - Cannot replicate issue")
    print(f"   Objective: ${results.best_feasible_objective:,.2f}")
    print(f"   Commit: {commit[:7]}")
else:
    print(f"\n⚠️  {results.termination_condition}")
