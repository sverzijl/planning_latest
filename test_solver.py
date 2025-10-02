"""Quick solver availability test."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.optimization import SolverConfig

config = SolverConfig()

print("=" * 70)
print("Solver Availability Test")
print("=" * 70)

# Check available solvers
available = config.get_available_solvers()
print(f"\nAvailable solvers: {available}")

if not available:
    print("\n⚠ No solvers detected!")
    print("\nTo install CBC:")
    print("  conda install -c conda-forge coincbc")
    print("\nOr to install GLPK:")
    print("  conda install -c conda-forge glpk")
else:
    print(f"\nTesting solvers...")
    config.test_all_solvers(verbose=True)

    print("\nSolver status:")
    config.print_solver_status()

    working = config.get_working_solvers()
    if working:
        print(f"\n✓ Working solvers: {working}")
        print(f"\nBest solver: {config.get_best_available_solver()}")
    else:
        print("\n✗ No working solvers found!")

print("=" * 70)
