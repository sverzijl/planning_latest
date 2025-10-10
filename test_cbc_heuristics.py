"""Test CBC aggressive heuristics on 21-day window."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
import time
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization import IntegratedProductionDistributionModel
from pyomo.environ import SolverFactory
from pyomo.opt import TerminationCondition

print("=" * 80)
print("CBC AGGRESSIVE HEURISTICS TEST - 21-DAY WINDOW")
print("=" * 80)
print()

# Load data
print("Loading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# 21-day window
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 22)

forecast_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
test_forecast = Forecast(name='test_21d', entries=forecast_entries, creation_date=full_forecast.creation_date)

print(f"21-day window: {start_date} to {end_date}")
print(f"Demand: {sum(e.quantity for e in test_forecast.entries):,.0f} units")
print()

# Build model
print("Building model...")
model = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
)

pyomo_model = model.build_model()
print(f"Model built: {pyomo_model.nvariables()} vars, {pyomo_model.nconstraints()} constraints")
print()

# Test 1: Default CBC (baseline - 30s timeout)
print("=" * 80)
print("TEST 1: DEFAULT CBC (30s timeout)")
print("=" * 80)

solver_default = SolverFactory('cbc')
solver_default.options['seconds'] = 30

print("Solving with default CBC settings...")
start = time.time()
results_default = solver_default.solve(pyomo_model, tee=False, symbolic_solver_labels=False, load_solutions=False)
time_default = time.time() - start

cost_default = None
if results_default.solver.termination_condition in [TerminationCondition.optimal, TerminationCondition.feasible]:
    pyomo_model.solutions.load_from(results_default)
    from pyomo.environ import value
    cost_default = value(pyomo_model.obj)
    print(f"✅ SOLVED in {time_default:.2f}s")
    print(f"   Cost: ${cost_default:,.2f}")
    print(f"   Status: {results_default.solver.termination_condition}")
else:
    print(f"❌ Failed after {time_default:.2f}s")
    print(f"   Status: {results_default.solver.termination_condition}")

# Rebuild model for second test
print("\nRebuilding model for Test 2...")
pyomo_model = model.build_model()

# Test 2: Aggressive heuristics (120s timeout)
print()
print("=" * 80)
print("TEST 2: AGGRESSIVE HEURISTICS (120s timeout)")
print("=" * 80)
print()

solver_aggressive = SolverFactory('cbc')

# AGGRESSIVE SETTINGS
print("Configuring aggressive heuristic settings:")
print("  - Feasibility Pump: ON")
print("  - RINS (TABU-like): ON")
print("  - Proximity Search (TABU-like): ON")
print("  - Diving Heuristics: ON")
print("  - All cutting planes: ON")
print("  - Auto-tuning: Level 2")
print()

solver_aggressive.options.update({
    # Time and quality
    'seconds': 120,
    'ratio': 0.01,              # Accept 1% gap

    # Preprocessing
    'preprocess': 'sos',
    'passPresolve': 10,

    # Heuristics (THE KEY!)
    'heuristics': 'on',
    'feaspump': 'on',          # Feasibility pump
    'rins': 'on',              # RINS (TABU-like)
    'diving': 'on',            # Diving
    'proximity': 'on',         # Proximity search (TABU-like!)
    'combine': 'on',           # Combine solutions

    # Cuts
    'cuts': 'on',
    'gomory': 'on',
    'knapsack': 'on',
    'probing': 'on',
    'clique': 'on',

    # Strategy
    'strategy': 1,             # Aggressive
    'tune': 2,                 # Maximum auto-tune
})

print("Solving with aggressive heuristics...")
start = time.time()
results_aggressive = solver_aggressive.solve(pyomo_model, tee=False, symbolic_solver_labels=False, load_solutions=False)
time_aggressive = time.time() - start

cost_aggressive = None
if results_aggressive.solver.termination_condition in [TerminationCondition.optimal, TerminationCondition.feasible]:
    pyomo_model.solutions.load_from(results_aggressive)
    from pyomo.environ import value
    cost_aggressive = value(pyomo_model.obj)
    print(f"✅ SOLVED in {time_aggressive:.2f}s")
    print(f"   Cost: ${cost_aggressive:,.2f}")
    print(f"   Status: {results_aggressive.solver.termination_condition}")
else:
    print(f"❌ Failed after {time_aggressive:.2f}s")
    print(f"   Status: {results_aggressive.solver.termination_condition}")

# Results comparison
print()
print("=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)
print()

print(f"Default CBC (30s):        {time_default:>6.2f}s  {'✓ solved' if cost_default else '✗ timeout'}")
print(f"Aggressive Heuristics:    {time_aggressive:>6.2f}s  {'✓ solved' if cost_aggressive else '✗ timeout'}")

if cost_default and cost_aggressive:
    print()
    print("Both methods found solutions:")
    speedup = time_default / time_aggressive
    cost_diff = ((cost_aggressive - cost_default) / cost_default) * 100
    print(f"  Speed: Heuristics {speedup:.1f}x {'faster' if speedup > 1 else 'slower'}")
    print(f"  Cost: {cost_diff:+.2f}% {'worse' if cost_diff > 0 else 'better'}")

elif cost_aggressive and not cost_default:
    print()
    print("🎯 SUCCESS! Aggressive heuristics solved where default failed!")
    print(f"   Time: {time_aggressive:.2f}s")
    print(f"   Cost: ${cost_aggressive:,.2f}")
    print()
    print("✅ CONCLUSION: Aggressive heuristics unlock 21-day windows!")
    print("   → Can now use hierarchical 3-week configurations")
    print("   → Approximate speedup: {:.1f}x faster than default".format(30.0/time_aggressive if time_aggressive > 0 else 0))

elif cost_default and not cost_aggressive:
    print()
    print("⚠ Default solved but heuristics failed")
    print("   → Default is better for this problem")

else:
    print()
    print("❌ Both methods timed out")
    print("   → 21-day windows remain infeasible with CBC")
    print("   → Options: Commercial solver trial or matheuristic decomposition")

print()
print("=" * 80)
