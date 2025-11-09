"""Export model details for inspection (Windows compatible - no git).

RUN THIS ON YOUR WINDOWS MACHINE and share the output.
"""
import json
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

diagnostic = {
    'note': 'Run from Windows system - no git available'
}

print("=" * 80)
print("DIAGNOSTIC - Windows Compatible")
print("=" * 80)

# Parse
print("\nParsing data...")
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

diagnostic['inventory_snapshot_date'] = str(inventory_snapshot.snapshot_date)
diagnostic['inventory_entries'] = len(inventory_snapshot.entries)

print(f"Snapshot date: {inventory_snapshot.snapshot_date}")

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

# Check max transit days
max_transit = max(r.transit_days for r in unified_routes)
diagnostic['max_transit_days'] = max_transit

# Convert inventory
initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()
else:
    for entry in inventory_snapshot.entries:
        key = (entry.location_id, entry.product_id, 'ambient')
        initial_inv_dict[key] = initial_inv_dict.get(key, 0) + entry.quantity

diagnostic['initial_inventory_total'] = float(sum(initial_inv_dict.values()))

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

# Check in_transit variables
if hasattr(pyomo_model, 'in_transit'):
    in_transit_vars = list(pyomo_model.in_transit)
    departure_dates = set(dep for (_, _, _, dep, _) in in_transit_vars)

    diagnostic['in_transit_var_count'] = len(in_transit_vars)
    diagnostic['departure_date_min'] = str(min(departure_dates))
    diagnostic['departure_date_max'] = str(max(departure_dates))
    diagnostic['pre_horizon_days'] = (start_date - min(departure_dates)).days

# Solve
print(f"Solving...")
from pyomo.contrib.appsi.solvers import Highs

solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 120
solver.config.mip_gap = 0.01

results = solver.solve(pyomo_model)

diagnostic['termination'] = str(results.termination_condition)
diagnostic['objective'] = float(results.best_feasible_objective) if results.best_feasible_objective else None
diagnostic['is_feasible'] = 'infeasible' not in str(results.termination_condition).lower()

# Write output
with open('diagnostic_output_windows.json', 'w') as f:
    json.dump(diagnostic, f, indent=2)

print(f"\n" + "=" * 80)
print("RESULT")
print("=" * 80)
print(f"Termination: {results.termination_condition}")
print(f"Feasible: {diagnostic['is_feasible']}")

if diagnostic['is_feasible']:
    print(f"✅ FEASIBLE - Objective: ${diagnostic['objective']:,.2f}")
else:
    print(f"❌ INFEASIBLE - Issue replicated!")

print(f"\n" + "=" * 80)
print("DIAGNOSTIC OUTPUT")
print("=" * 80)
print(json.dumps(diagnostic, indent=2))

print(f"\nFile saved: diagnostic_output_windows.json")
print(f"Share this JSON to help identify the difference")
