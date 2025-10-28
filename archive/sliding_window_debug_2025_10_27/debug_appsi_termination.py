"""Debug APPSI termination condition."""
from pyomo.environ import ConcreteModel, Var, Objective, Constraint, NonNegativeReals, minimize
from pyomo.contrib.appsi.solvers import Highs
from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC

# Create simple MIP model (with integer variables)
from pyomo.environ import Binary
model = ConcreteModel()
model.x = Var(within=NonNegativeReals)
model.y = Var(within=Binary)  # Binary variable to make it MIP
model.z = Var(within=NonNegativeReals)
model.obj = Objective(expr=model.x + 5*model.y + model.z, sense=minimize)
model.con1 = Constraint(expr=model.x + 2*model.z >= 10)
model.con2 = Constraint(expr=model.y >= 0.1)  # Force y to be 1

# Solve with APPSI HiGHS with MIP gap
solver = Highs()
solver.config.mip_gap = 0.10  # 10% gap tolerance
results = solver.solve(model)

print("=" * 80)
print("APPSI HiGHS Termination Condition Debug")
print("=" * 80)
print(f"\nTermination Condition: {results.termination_condition}")
print(f"Type: {type(results.termination_condition)}")
print(f"String repr: '{str(results.termination_condition)}'")

print(f"\nAppsiTC.optimal: {AppsiTC.optimal}")
print(f"Type: {type(AppsiTC.optimal)}")

print(f"\nAre they equal? {results.termination_condition == AppsiTC.optimal}")
print(f"Is 'optimal' in string? {'optimal' in str(results.termination_condition).lower()}")

print(f"\nAvailable AppsiTC values:")
for attr in dir(AppsiTC):
    if not attr.startswith('_'):
        val = getattr(AppsiTC, attr)
        print(f"  {attr}: {val}")
        if results.termination_condition == val:
            print(f"    ^^^ MATCH! ^^^")

print(f"\nBest feasible objective: {results.best_feasible_objective}")
print(f"Best objective bound: {results.best_objective_bound}")

print(f"\nVariable values:")
print(f"  x = {model.x.value}")
print(f"  y = {model.y.value}")
