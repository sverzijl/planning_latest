"""Test CBC directly with different Pyomo options."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("Direct CBC Test")
print("=" * 70)

# Test 1: Basic Pyomo setup
print("\nTest 1: Creating simple model...")
try:
    import pyomo.environ as pyo
    from pyomo.opt import SolverFactory

    model = pyo.ConcreteModel()
    model.x = pyo.Var(within=pyo.NonNegativeReals)
    model.obj = pyo.Objective(expr=model.x, sense=pyo.minimize)
    model.con = pyo.Constraint(expr=model.x >= 1)
    print("  ✓ Model created")
except Exception as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)

# Test 2: Check CBC availability
print("\nTest 2: Checking CBC availability...")
try:
    solver = SolverFactory('cbc')
    is_available = solver.available()
    print(f"  Available: {is_available}")
    if is_available:
        print(f"  Executable: {solver.executable()}")
    else:
        print("  ✗ CBC not available!")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)

# Test 3: Try solving with symbolic_solver_labels=False
print("\nTest 3: Solving with symbolic_solver_labels=False...")
try:
    solver = SolverFactory('cbc')
    results = solver.solve(model, tee=True, symbolic_solver_labels=False)
    print(f"  Status: {results.solver.status}")
    print(f"  Termination: {results.solver.termination_condition}")
    print(f"  x = {pyo.value(model.x)}")
    if abs(pyo.value(model.x) - 1.0) < 1e-5:
        print("  ✓ Test 3 PASSED!")
    else:
        print(f"  ✗ Test 3 FAILED - expected x=1.0, got {pyo.value(model.x)}")
except Exception as e:
    print(f"  ✗ Test 3 FAILED with error: {e}")

# Test 4: Try with keepfiles=False and other options
print("\nTest 4: Solving with additional options...")
try:
    model2 = pyo.ConcreteModel()
    model2.x = pyo.Var(within=pyo.NonNegativeReals)
    model2.obj = pyo.Objective(expr=model2.x, sense=pyo.minimize)
    model2.con = pyo.Constraint(expr=model2.x >= 1)

    solver = SolverFactory('cbc')
    results = solver.solve(
        model2,
        tee=False,
        symbolic_solver_labels=False,
        keepfiles=False,
    )
    print(f"  Status: {results.solver.status}")
    print(f"  x = {pyo.value(model2.x)}")
    if abs(pyo.value(model2.x) - 1.0) < 1e-5:
        print("  ✓ Test 4 PASSED!")
    else:
        print(f"  ✗ Test 4 FAILED")
except Exception as e:
    print(f"  ✗ Test 4 FAILED with error: {e}")

# Test 5: Check Pyomo version
print("\nTest 5: Checking Pyomo version...")
try:
    import pyomo
    print(f"  Pyomo version: {pyomo.__version__}")

    # Check if this is a version that might have issues
    version_parts = pyomo.__version__.split('.')
    major = int(version_parts[0])
    minor = int(version_parts[1]) if len(version_parts) > 1 else 0

    if major < 6:
        print(f"  ⚠ Warning: Pyomo {pyomo.__version__} is old. Consider upgrading:")
        print(f"     pip install --upgrade pyomo")
    else:
        print(f"  ✓ Pyomo version is recent")
except Exception as e:
    print(f"  Version check error: {e}")

print("\n" + "=" * 70)
print("If Test 3 or Test 4 passed, CBC is working correctly!")
print("=" * 70)
