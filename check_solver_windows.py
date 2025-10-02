"""Check solver installation on Windows."""

import sys
from pathlib import Path
import subprocess
import shutil

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("Windows Solver Detection")
print("=" * 70)

# Check if CBC is in PATH
print("\n1. Checking for CBC executable in PATH...")
cbc_path = shutil.which("cbc")
if cbc_path:
    print(f"   ✓ CBC found at: {cbc_path}")

    # Try to run CBC to get version
    try:
        result = subprocess.run(
            ["cbc", "-?"],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"   Version info: {result.stdout[:100] if result.stdout else 'Unknown'}")
    except Exception as e:
        print(f"   ⚠ Could not run CBC: {e}")
else:
    print("   ✗ CBC not found in PATH")

# Check for GLPK
print("\n2. Checking for GLPK executable in PATH...")
glpk_path = shutil.which("glpsol")
if glpk_path:
    print(f"   ✓ GLPK found at: {glpk_path}")
else:
    print("   ✗ GLPK not found in PATH")

# Try Pyomo solver detection
print("\n3. Testing Pyomo solver detection...")
try:
    from pyomo.opt import SolverFactory

    for solver_name in ['cbc', 'glpk', 'gurobi', 'cplex']:
        print(f"\n   Testing {solver_name.upper()}:")
        try:
            solver = SolverFactory(solver_name)
            is_available = solver.available()
            print(f"     Available: {is_available}")

            if is_available:
                print(f"     Executable: {solver.executable()}")
        except Exception as e:
            print(f"     Error: {e}")

except ImportError as e:
    print(f"   ✗ Pyomo not installed: {e}")

# Check conda environment
print("\n4. Checking conda environment...")
try:
    result = subprocess.run(
        ["conda", "list", "coincbc"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0 and result.stdout:
        print("   Conda packages:")
        print("   " + "\n   ".join(result.stdout.strip().split('\n')))
    else:
        print("   ✗ coincbc not found in conda environment")
except FileNotFoundError:
    print("   ⚠ conda command not found")
except Exception as e:
    print(f"   ⚠ Error checking conda: {e}")

print("\n" + "=" * 70)
print("Installation Instructions for Windows:")
print("=" * 70)
print("""
If CBC is not installed, you have two options:

Option 1: Install via conda (recommended):
  conda install -c conda-forge coincbc

Option 2: Download CBC binaries manually:
  1. Download from: https://github.com/coin-or/Cbc/releases
  2. Extract the ZIP file
  3. Add the bin/ directory to your PATH
  4. Restart your terminal/IDE

After installation, restart your Python session and try again.
""")
print("=" * 70)
