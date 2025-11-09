"""Export model details for inspection to identify infeasibility.

RUN THIS ON YOUR WINDOWS MACHINE and share the output.
It will create a detailed diagnostic file showing all model parameters.
"""
import subprocess
import json
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

# Get git commit
result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
commit = result.stdout.strip() if result.returncode == 0 else 'unknown'

diagnostic = {
    'git_commit': commit,
    'git_commit_short': commit[:7] if commit != 'unknown' else 'unknown'
}

# Parse
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

diagnostic['inventory_snapshot_date'] = str(inventory_snapshot.snapshot_date)
diagnostic['inventory_entries'] = len(inventory_snapshot.entries)

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

diagnostic['start_date'] = str(start_date)
diagnostic['end_date'] = str(end_date)
diagnostic['horizon_days'] = (end_date - start_date).days + 1

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

diagnostic['num_products'] = len(products)
diagnostic['num_routes'] = len(unified_routes)
diagnostic['num_nodes'] = len(nodes)

# Route details
diagnostic['routes'] = []
for r in unified_routes:
    diagnostic['routes'].append({
        'origin': r.origin_node_id,
        'dest': r.destination_node_id,
        'transit_days': r.transit_days,
        'mode': str(r.transport_mode)
    })

# Convert inventory
initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()
else:
    for entry in inventory_snapshot.entries:
        key = (entry.location_id, entry.product_id, 'ambient')
        initial_inv_dict[key] = initial_inv_dict.get(key, 0) + entry.quantity

diagnostic['initial_inventory_keys'] = len(initial_inv_dict)
diagnostic['initial_inventory_total'] = sum(initial_inv_dict.values())

# Build model
print(f"\nBuilding model with settings:")
print(f"  allow_shortages: True")
print(f"  use_pallet_tracking: True")
print(f"  use_truck_pallet_tracking: True")

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

# Count variables
from pyomo.environ import Var
in_transit_vars = list(pyomo_model.in_transit) if hasattr(pyomo_model, 'in_transit') else []
departure_dates_set = set(dep for (_, _, _, dep, _) in in_transit_vars)

diagnostic['in_transit_var_count'] = len(in_transit_vars)
if departure_dates_set:
    diagnostic['departure_date_min'] = str(min(departure_dates_set))
    diagnostic['departure_date_max'] = str(max(departure_dates_set))
else:
    diagnostic['departure_date_min'] = None
    diagnostic['departure_date_max'] = None

# Solve
from pyomo.contrib.appsi.solvers import Highs
solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 120
solver.config.mip_gap = 0.01

results = solver.solve(pyomo_model)

diagnostic['termination'] = str(results.termination_condition)
diagnostic['objective'] = results.best_feasible_objective
diagnostic['is_feasible'] = str(results.termination_condition) != 'TerminationCondition.infeasible'

# Write diagnostic file
with open('diagnostic_output.json', 'w') as f:
    json.dump(diagnostic, f, indent=2)

print(f"\n" + "=" * 80)
print("DIAGNOSTIC OUTPUT")
print("=" * 80)
print(json.dumps(diagnostic, indent=2))

print(f"\n" + "=" * 80)
print("RESULT")
print("=" * 80)
print(f"Termination: {results.termination_condition}")
print(f"Feasible: {diagnostic['is_feasible']}")

if diagnostic['is_feasible']:
    print(f"\n✅ Model is FEASIBLE on this system")
    print(f"   If you see INFEASIBLE, compare your diagnostic_output.json with this")
else:
    print(f"\n❌ Model is INFEASIBLE")
    print(f"   Issue successfully replicated!")
    print(f"   diagnostic_output.json saved for analysis")

print(f"\nFiles created:")
print(f"  - diagnostic_output.json (model parameters and result)")
print(f"  - diagnostic_model.lp (full model for inspection)")
