"""Phase 1: Root Cause Investigation - UI Infeasibility

Following systematic debugging process to determine TRUE root cause.

Evidence gathering:
1. Solve WITHOUT loading solution (to check termination condition)
2. Inspect HiGHS solver status codes
3. Determine if model is infeasible OR if solution loading failed
"""
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from pyomo.contrib.appsi.solvers import Highs

print("=" * 80)
print("PHASE 1: ROOT CAUSE INVESTIGATION - UI Infeasibility")
print("=" * 80)

# Parse data exactly as UI does
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Parse initial inventory
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Use inventory snapshot date + 1 as start (UI pattern)
start_date = inventory_snapshot.snapshot_date + timedelta(days=1)
end_date = start_date + timedelta(days=27)  # 4 weeks

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Convert initial inventory
initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()
else:
    for entry in inventory_snapshot.entries:
        key = (entry.location_id, entry.product_id, 'ambient')
        initial_inv_dict[key] = initial_inv_dict.get(key, 0) + entry.quantity

print(f"\nScenario (EXACT UI CONFIGURATION):")
print(f"  Planning: {start_date} to {end_date}")
print(f"  Initial inventory: {len(initial_inv_dict)} entries")
print(f"  Pallet tracking: True")
print(f"  Truck pallet tracking: True")

# Build model EXACTLY as UI does
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=inventory_snapshot.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

pyomo_model = model.build_model()
print(f"\n✅ Model built")

# ============================================================================
# EVIDENCE 1: Solve WITHOUT loading solution
# ============================================================================
print(f"\n" + "=" * 80)
print("EVIDENCE 1: Solve with load_solution=False")
print("=" * 80)

solver = Highs()
solver.config.load_solution = False  # KEY: Don't load solution automatically
solver.config.time_limit = 120
solver.config.mip_gap = 0.01

print(f"\nSolving (without loading solution)...")
results = solver.solve(pyomo_model)

print(f"\nSolver results:")
print(f"  Termination condition: {results.termination_condition}")
print(f"  Solver status: {results.solver_status if hasattr(results, 'solver_status') else 'N/A'}")
print(f"  Best objective: {results.best_feasible_objective if hasattr(results, 'best_feasible_objective') else 'N/A'}")
print(f"  Best bound: {results.best_objective_bound if hasattr(results, 'best_objective_bound') else 'N/A'}")

# Check if HiGHS found ANY solution
if hasattr(results, 'best_feasible_objective') and results.best_feasible_objective is not None:
    print(f"\n✅ HiGHS FOUND A FEASIBLE SOLUTION")
    print(f"  Objective value: ${results.best_feasible_objective:,.2f}")
    print(f"  Issue is: SOLUTION LOADING failed, not infeasibility")
elif str(results.termination_condition) == 'infeasible':
    print(f"\n❌ HiGHS REPORTS: MODEL IS INFEASIBLE")
    print(f"  No feasible solution exists")
    print(f"  Issue is: MODEL FORMULATION, not loading")
elif str(results.termination_condition) == 'optimal':
    print(f"\n✅ HiGHS REPORTS: OPTIMAL SOLUTION FOUND")
    print(f"  Issue is: SOLUTION LOADING failed (not infeasibility)")
else:
    print(f"\n⚠️  UNCLEAR: {results.termination_condition}")

# ============================================================================
# EVIDENCE 2: Try loading solution manually
# ============================================================================
print(f"\n" + "=" * 80)
print("EVIDENCE 2: Manual Solution Loading")
print("=" * 80)

if str(results.termination_condition) in ['optimal', 'feasible']:
    print(f"\nAttempting to load solution...")
    try:
        solver.load_vars()
        print(f"✅ Solution loaded successfully!")

        # Test accessing a variable
        if hasattr(pyomo_model, 'production'):
            first_prod_var = list(pyomo_model.production)[0]
            from pyomo.core.base import value
            test_val = value(pyomo_model.production[first_prod_var])
            print(f"  Sample variable value: {test_val}")
    except Exception as e:
        print(f"❌ Solution loading failed: {e}")
        print(f"\n  This reveals the TRUE root cause!")

# ============================================================================
# CONCLUSION
# ============================================================================
print(f"\n" + "=" * 80)
print("ROOT CAUSE DETERMINATION")
print("=" * 80)

print(f"""
Based on evidence:

1. Termination condition: {results.termination_condition}
2. Feasible objective exists: {hasattr(results, 'best_feasible_objective') and results.best_feasible_objective is not None}

DIAGNOSIS:
""")

if str(results.termination_condition) == 'infeasible':
    print(f"  MODEL IS TRULY INFEASIBLE")
    print(f"  The refactoring introduced a constraint violation")
    print(f"  Next: Identify which constraint is violated (Phase 2)")
else:
    print(f"  MODEL IS FEASIBLE (or optimal)")
    print(f"  The error is in SOLUTION LOADING, not model formulation")
    print(f"  Next: Fix solution loading mechanism (Phase 2)")
