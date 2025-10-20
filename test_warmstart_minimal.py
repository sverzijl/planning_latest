"""Minimal test to debug CBC warmstart issue.

This script tests different solver.solve() parameter combinations to identify
which parameter prevents the -mipstart flag from being generated.
"""

from pyomo.environ import (
    ConcreteModel, Var, Objective, Constraint,
    Binary, minimize, SolverFactory, value
)


def create_simple_mip():
    """Create a simple MIP model for testing."""
    model = ConcreteModel()

    # Variables
    model.x1 = Var(within=Binary)
    model.x2 = Var(within=Binary)
    model.x3 = Var(within=Binary)

    # Objective
    model.obj = Objective(expr=model.x1 + 2*model.x2 + 3*model.x3, sense=minimize)

    # Constraint
    model.con1 = Constraint(expr=model.x1 + model.x2 + model.x3 >= 1)

    return model


def test_warmstart_config(symbolic_labels=None, load_solutions=None):
    """Test warmstart with specific configuration."""
    print("\n" + "="*80)
    print(f"Testing: symbolic_solver_labels={symbolic_labels}, load_solutions={load_solutions}")
    print("="*80)

    # Create model
    model = create_simple_mip()

    # Set warmstart values (like Stack Exchange example)
    model.x1 = 1
    model.x2 = 0
    model.x3 = 0

    print(f"Warmstart values set: x1={model.x1.value}, x2={model.x2.value}, x3={model.x3.value}")

    # Create solver
    solver = SolverFactory('cbc')

    # Build solve() kwargs
    solve_kwargs = {
        'warmstart': True,
        'tee': True,
    }

    # Add optional parameters
    if symbolic_labels is not None:
        solve_kwargs['symbolic_solver_labels'] = symbolic_labels

    if load_solutions is not None:
        solve_kwargs['load_solutions'] = load_solutions

    print(f"\nCalling solver.solve() with: {solve_kwargs}")
    print("\nCBC command line output:")
    print("-" * 80)

    # Solve
    results = solver.solve(model, **solve_kwargs)

    print("-" * 80)
    print(f"\nSolver status: {results.solver.status}")
    print(f"Termination: {results.solver.termination_condition}")

    # Load solution if not auto-loaded
    if load_solutions is False:
        model.solutions.load_from(results)

    print(f"Solution: x1={value(model.x1)}, x2={value(model.x2)}, x3={value(model.x3)}")
    print(f"Objective: {value(model.obj)}")


if __name__ == "__main__":
    print("\n" + "#"*80)
    print("# CBC WARMSTART INVESTIGATION")
    print("#"*80)

    # Test 1: Exactly like Stack Exchange (no extra parameters)
    print("\n### TEST 1: Stack Exchange style (no symbolic_solver_labels, no load_solutions)")
    test_warmstart_config(symbolic_labels=None, load_solutions=None)

    # Test 2: With symbolic_solver_labels=False (our current code)
    print("\n### TEST 2: With symbolic_solver_labels=False")
    test_warmstart_config(symbolic_labels=False, load_solutions=None)

    # Test 3: With load_solutions=False (our current code)
    print("\n### TEST 3: With load_solutions=False")
    test_warmstart_config(symbolic_labels=None, load_solutions=False)

    # Test 4: Both parameters (our current code)
    print("\n### TEST 4: Both symbolic_solver_labels=False AND load_solutions=False")
    test_warmstart_config(symbolic_labels=False, load_solutions=False)

    print("\n" + "#"*80)
    print("# INVESTIGATION COMPLETE")
    print("#"*80)
    print("\nLook for '-mipstart' flag in CBC command line output above.")
    print("If missing in any test, that parameter combination breaks warmstart.")
