"""Test the asl:cbc solver interface fix for CBC 2.10.12."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pyomo.environ as pyo
from pyomo.opt import SolverFactory

print("=" * 70)
print("Testing ASL:CBC Solver Interface")
print("=" * 70)

# Create test model
model = pyo.ConcreteModel()
model.x = pyo.Var(within=pyo.NonNegativeReals)
model.obj = pyo.Objective(expr=model.x, sense=pyo.minimize)
model.con = pyo.Constraint(expr=model.x >= 1)

# Test 1: Original cbc (will fail)
print("\nTest 1: Using 'cbc' (original, will fail)...")
try:
    solver = SolverFactory('cbc')
    print(f"  Solver available: {solver.available()}")
    results = solver.solve(model, tee=False, symbolic_solver_labels=False)
    print(f"  ✓ Solved! x = {pyo.value(model.x)}")
except Exception as e:
    print(f"  ✗ Failed: {e}")

# Test 2: ASL:CBC interface (should work!)
print("\nTest 2: Using 'asl:cbc' (AMPL interface)...")
try:
    solver = SolverFactory('asl:cbc')
    print(f"  Solver available: {solver.available()}")
    if solver.available():
        print(f"  Solver executable: {solver.executable()}")
        results = solver.solve(model, tee=False)
        x_val = pyo.value(model.x)
        print(f"  Status: {results.solver.status}")
        print(f"  x = {x_val}")
        if abs(x_val - 1.0) < 1e-5:
            print("  ✓ SUCCESS! ASL:CBC works perfectly!")
        else:
            print(f"  ✗ Wrong answer: expected 1.0, got {x_val}")
    else:
        print("  ✗ ASL:CBC not available")
        print("  Install AMPL solver library:")
        print("    conda install -c conda-forge amplpy")
except Exception as e:
    print(f"  ✗ Failed: {e}")

print("\n" + "=" * 70)
print("If Test 2 succeeded, we can use 'asl:cbc' as the solver!")
print("=" * 70)
