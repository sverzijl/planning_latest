"""Test various workarounds for CBC 2.10.12 + Pyomo 6.9.4 compatibility."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pyomo.environ as pyo
from pyomo.opt import SolverFactory

print("=" * 70)
print("CBC 2.10.12 Compatibility Workarounds")
print("=" * 70)

# Create test model
def create_model():
    model = pyo.ConcreteModel()
    model.x = pyo.Var(within=pyo.NonNegativeReals)
    model.obj = pyo.Objective(expr=model.x, sense=pyo.minimize)
    model.con = pyo.Constraint(expr=model.x >= 1)
    return model

# Workaround 1: Try io_options
print("\nWorkaround 1: Using io_options={'symbolic_solver_labels': False}...")
try:
    model = create_model()
    solver = SolverFactory('cbc')
    results = solver.solve(
        model,
        tee=False,
        io_options={'symbolic_solver_labels': False}
    )
    x_val = pyo.value(model.x)
    print(f"  Status: {results.solver.status}")
    print(f"  x = {x_val}")
    if abs(x_val - 1.0) < 1e-5:
        print("  ✓ Workaround 1 WORKS!")
    else:
        print(f"  ✗ Workaround 1 FAILED")
except Exception as e:
    print(f"  ✗ Workaround 1 FAILED: {e}")

# Workaround 2: Try load_solutions=False
print("\nWorkaround 2: Using load_solutions=False...")
try:
    model = create_model()
    solver = SolverFactory('cbc')
    results = solver.solve(
        model,
        tee=False,
        symbolic_solver_labels=False,
        load_solutions=False
    )
    model.solutions.load_from(results)
    x_val = pyo.value(model.x)
    print(f"  Status: {results.solver.status}")
    print(f"  x = {x_val}")
    if abs(x_val - 1.0) < 1e-5:
        print("  ✓ Workaround 2 WORKS!")
    else:
        print(f"  ✗ Workaround 2 FAILED")
except Exception as e:
    print(f"  ✗ Workaround 2 FAILED: {e}")

# Workaround 3: Try using warmstart=True
print("\nWorkaround 3: Using warmstart=True...")
try:
    model = create_model()
    solver = SolverFactory('cbc')
    results = solver.solve(
        model,
        tee=False,
        symbolic_solver_labels=False,
        warmstart=True
    )
    x_val = pyo.value(model.x)
    print(f"  Status: {results.solver.status}")
    print(f"  x = {x_val}")
    if abs(x_val - 1.0) < 1e-5:
        print("  ✓ Workaround 3 WORKS!")
    else:
        print(f"  ✗ Workaround 3 FAILED")
except Exception as e:
    print(f"  ✗ Workaround 3 FAILED: {e}")

# Workaround 4: Try using suffixes=[]
print("\nWorkaround 4: Using suffixes=[]...")
try:
    model = create_model()
    solver = SolverFactory('cbc')
    results = solver.solve(
        model,
        tee=False,
        symbolic_solver_labels=False,
        suffixes=[]
    )
    x_val = pyo.value(model.x)
    print(f"  Status: {results.solver.status}")
    print(f"  x = {x_val}")
    if abs(x_val - 1.0) < 1e-5:
        print("  ✓ Workaround 4 WORKS!")
    else:
        print(f"  ✗ Workaround 4 FAILED")
except Exception as e:
    print(f"  ✗ Workaround 4 FAILED: {e}")

# Workaround 5: Set solver options to suppress output
print("\nWorkaround 5: Using solver.options['printingOptions'] = 'none'...")
try:
    model = create_model()
    solver = SolverFactory('cbc')
    # Try setting the option explicitly to prevent Pyomo from passing it
    solver.options['printingOptions'] = 'none'
    results = solver.solve(
        model,
        tee=False,
        symbolic_solver_labels=False,
    )
    x_val = pyo.value(model.x)
    print(f"  Status: {results.solver.status}")
    print(f"  x = {x_val}")
    if abs(x_val - 1.0) < 1e-5:
        print("  ✓ Workaround 5 WORKS!")
    else:
        print(f"  ✗ Workaround 5 FAILED")
except Exception as e:
    print(f"  ✗ Workaround 5 FAILED: {e}")

# Workaround 6: Try using keepfiles=True and debug mode
print("\nWorkaround 6: Checking generated command line...")
try:
    model = create_model()
    solver = SolverFactory('cbc')

    # Enable keepfiles to see what command is being run
    import tempfile
    import os
    tmpdir = tempfile.mkdtemp()

    results = solver.solve(
        model,
        tee=True,
        symbolic_solver_labels=False,
        keepfiles=True,
        tmpdir=tmpdir
    )

    print(f"\n  Temporary files in: {tmpdir}")
    print(f"  Files created: {os.listdir(tmpdir)}")

    # Look for .log file to see actual command
    for fname in os.listdir(tmpdir):
        if fname.endswith('.log'):
            logpath = os.path.join(tmpdir, fname)
            with open(logpath, 'r') as f:
                print(f"\n  Log content:\n{f.read()[:500]}")

except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 70)
print("Summary: If any workaround succeeded, we can use that!")
print("=" * 70)
