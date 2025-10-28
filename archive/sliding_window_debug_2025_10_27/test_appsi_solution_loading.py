"""Test if APPSI HiGHS automatically loads solutions."""
import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs

# Create simple model
model = pyo.ConcreteModel()
model.x = pyo.Var(within=pyo.NonNegativeReals)
model.y = pyo.Var(within=pyo.NonNegativeReals)
model.obj = pyo.Objective(expr=model.x + model.y, sense=pyo.minimize)
model.con = pyo.Constraint(expr=model.x + 2*model.y >= 10)

# Solve with APPSI HiGHS
solver = Highs()
results = solver.solve(model)

print("=" * 80)
print("APPSI Solution Loading Test")
print("=" * 80)

print(f"\nTermination condition: {results.termination_condition}")
print(f"Best objective: {results.best_feasible_objective}")

print(f"\nVariable values AFTER solve:")
try:
    x_val = pyo.value(model.x)
    y_val = pyo.value(model.y)
    print(f"  x = {x_val}")
    print(f"  y = {y_val}")
    print(f"\n✅ Solution WAS automatically loaded!")
except ValueError as e:
    print(f"  ❌ ERROR: {e}")
    print(f"\n❌ Solution was NOT automatically loaded!")

    # Try explicitly loading
    print(f"\nTrying to load variables explicitly...")
    print(f"  Available results attributes: {dir(results)}")

    # Check if we need to call load_vars()
    if hasattr(results, 'solution_loader'):
        print(f"  Has solution_loader: YES")

    # Check what APPSI provides
    print(f"\n  APPSI Results type: {type(results)}")
