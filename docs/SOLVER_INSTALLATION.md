# Solver Installation Guide

This guide provides step-by-step instructions for installing optimization solvers for the Gluten-Free Bread Production Planning application.

## Overview

The application uses **Pyomo** as the optimization modeling framework and requires an external solver to solve optimization problems. We support multiple solvers with different performance characteristics:

| Solver | Type | License | Performance | Platforms | Recommendation |
|--------|------|---------|-------------|-----------|----------------|
| **CBC** | MIP | Open Source (EPL) | Good | Linux, macOS, Windows | **Recommended for most users** |
| **GLPK** | MIP | Open Source (GPL) | Fair | Linux, macOS, Windows | Fallback if CBC unavailable |
| **Gurobi** | MIP | Commercial | Excellent | Linux, macOS, Windows | Recommended for large problems (requires license) |
| **CPLEX** | MIP | Commercial | Excellent | Linux, macOS, Windows | Alternative commercial option (requires license) |

**Recommendation:** Start with **CBC** (free, open source, good performance). For production use with large problems (200+ day horizons), consider **Gurobi** with an academic or commercial license.

---

## Quick Start

### Linux (Ubuntu/Debian)

**Option 1: Using conda (recommended)**
```bash
# Activate your conda environment
conda activate planning_env

# Install CBC solver
conda install -c conda-forge coincbc

# Verify installation
pyomo help --solvers
# Should show: cbc (available)
```

**Option 2: Using apt**
```bash
sudo apt-get update
sudo apt-get install coinor-cbc
```

### macOS

**Option 1: Using conda (recommended)**
```bash
# Activate your conda environment
conda activate planning_env

# Install CBC solver
conda install -c conda-forge coincbc

# Verify installation
pyomo help --solvers
# Should show: cbc (available)
```

**Option 2: Using Homebrew**
```bash
brew install cbc
```

### Windows

**CBC is not available via conda-forge on Windows.** You need to download pre-compiled binaries:

**Step 1: Download CBC binaries**
1. Visit: https://ampl.com/products/solvers/open-source/
2. Click on **CBC** solver
3. Download the Windows 64-bit version (e.g., `cbc-win64.zip`)

**Step 2: Extract and configure**
```powershell
# Option A: Extract to a dedicated folder
# 1. Create directory: C:\cbc\
# 2. Extract contents of cbc-win64.zip to C:\cbc\
# 3. The executable should be at C:\cbc\cbc.exe

# Option B: Extract to your project's venv Scripts folder
# Extract to: <project_path>\venv\Scripts\
# This makes cbc.exe available in your virtual environment
```

**Step 3: Add to PATH (Option A only)**
```powershell
# Temporary (current session only)
$env:PATH += ";C:\cbc"

# Permanent (use System Properties)
# 1. Open System Properties > Environment Variables
# 2. Edit PATH variable
# 3. Add: C:\cbc
# 4. Restart your terminal
```

**Step 4: Verify installation**
```powershell
# Check CBC is accessible
cbc -v
# Should show: CBC version X.Y.Z

# Check Pyomo can find it
python -c "from pyomo.opt import SolverFactory; solver = SolverFactory('cbc'); print('CBC available:', solver.available())"
# Should show: CBC available: True
```

---

## Alternative Solver: GLPK

If you cannot install CBC, **GLPK** is a fallback option (available on all platforms via conda).

### Installation (All Platforms)

```bash
conda install -c conda-forge glpk

# Verify
pyomo help --solvers
# Should show: glpk (available)
```

**Note:** GLPK is generally slower than CBC for MIP problems but will work for smaller problem instances.

---

## Commercial Solvers (Optional)

### Gurobi

**Performance:** Excellent (2-10x faster than CBC for large MIP problems)

**License:** Requires commercial or academic license (free academic licenses available)

**Installation:**
1. Obtain license from https://www.gurobi.com/
2. Install Gurobi:
   ```bash
   conda install -c gurobi gurobi
   ```
3. Activate license:
   ```bash
   grbgetkey YOUR_LICENSE_KEY
   ```

### CPLEX

**Performance:** Excellent (similar to Gurobi)

**License:** Requires IBM commercial or academic license

**Installation:**
1. Download from IBM: https://www.ibm.com/products/ilog-cplex-optimization-studio
2. Follow IBM installation instructions
3. Install Python interface:
   ```bash
   pip install cplex
   ```

---

## Verification

After installing a solver, verify it works with Pyomo:

### Test Script

Create a file `test_solver.py`:

```python
from pyomo.environ import *

# Test solver availability
def test_solver(solver_name):
    try:
        solver = SolverFactory(solver_name)
        if solver.available():
            print(f"✓ {solver_name.upper()} is available")

            # Test with a simple model
            model = ConcreteModel()
            model.x = Var(within=NonNegativeReals)
            model.obj = Objective(expr=model.x, sense=minimize)
            model.con = Constraint(expr=model.x >= 1)

            results = solver.solve(model, tee=False)

            if results.solver.termination_condition == TerminationCondition.optimal:
                print(f"  ✓ Successfully solved test problem")
                print(f"  ✓ Solution: x = {value(model.x):.2f}")
                return True
            else:
                print(f"  ✗ Solver failed: {results.solver.termination_condition}")
                return False
        else:
            print(f"✗ {solver_name.upper()} is not available")
            return False
    except Exception as e:
        print(f"✗ {solver_name.upper()} error: {e}")
        return False

# Test available solvers
print("Testing Solvers:")
print("-" * 50)
test_solver('cbc')
test_solver('glpk')
test_solver('gurobi')
test_solver('cplex')
```

Run the test:
```bash
python test_solver.py
```

Expected output (with CBC installed):
```
Testing Solvers:
--------------------------------------------------
✓ CBC is available
  ✓ Successfully solved test problem
  ✓ Solution: x = 1.00
✗ GLPK is not available
✗ GUROBI is not available
✗ CPLEX is not available
```

---

## Troubleshooting

### Problem: "cbc not found" error

**Linux/macOS:**
- Ensure conda environment is activated
- Try: `which cbc` to find the binary location
- If using system install, ensure it's in PATH

**Windows:**
- Verify `cbc.exe` is in a directory listed in PATH
- Try running `cbc` directly in Command Prompt
- Check file is not blocked (Right-click → Properties → Unblock)

### Problem: Pyomo can't find solver even though it's installed

**Solution:**
```python
# Manually specify solver path
from pyomo.opt import SolverFactory
solver = SolverFactory('cbc', executable='/path/to/cbc')
```

**Windows example:**
```python
solver = SolverFactory('cbc', executable='C:/cbc/cbc.exe')
```

### Problem: "Solver failed with return code X"

**Common causes:**
1. Model is infeasible (over-constrained)
2. Model is unbounded
3. Solver timeout reached

**Debug:**
```python
# Enable verbose output
results = solver.solve(model, tee=True)
print(results.solver)
```

### Problem: CBC 2.10.12 "invalid option '-printingOptions'" error

**Symptoms:**
```
ERROR: Solver (cbc) returned non-zero return code (1)
ERROR: Solver log: Error: cbc 2.10.12: invalid option '-printingOptions'
```
or
```
ERROR: Solver log: Error: cbc 2.10.12: Unknown option or invalid key "sec"
```

**Cause:**
Pyomo 6.9.x passes incompatible options to CBC 2.10.12+. The `-printingOptions` flag and some option keys (like `sec`, `ratio`) were changed in CBC 2.10.12 but Pyomo's default interface still tries to use the old names.

**Solution 1: Use our solver (automatic - preferred)**
The application automatically avoids this issue by not passing options to CBC. No action needed if using the provided optimization models (`ProductionOptimizationModel`, `IntegratedProductionDistributionModel`).

**Solution 2: Manual workaround**
If directly using Pyomo with CBC, avoid passing solver options:
```python
from pyomo.opt import SolverFactory

# BAD - will fail with CBC 2.10.12
solver = SolverFactory('cbc')
solver.options['sec'] = 300  # Unknown option!
results = solver.solve(model)

# GOOD - works with all CBC versions
solver = SolverFactory('cbc')
results = solver.solve(
    model,
    symbolic_solver_labels=False,  # Prevent -printingOptions
    load_solutions=False            # Prevent auto-loading errors
)
# Manually load solution
model.solutions.load_from(results)
```

**Solution 3: Downgrade CBC (not recommended)**
```bash
conda install -c conda-forge "coincbc<2.10.12"
```

**Root Cause:**
CBC 2.10.12 removed the `-printingOptions` flag and changed option key names, but Pyomo's `SolverFactory('cbc')` interface wasn't updated to match. The application resolves this by:
- Using `symbolic_solver_labels=False` to prevent Pyomo from passing `-printingOptions`
- Not passing solver options (like `sec`, `ratio`) that have incompatible names
- Using `load_solutions=False` to handle solution loading errors gracefully

**Tested Versions:**
- ✅ CBC 2.10.12 + Pyomo 6.9.4 (with our workaround)
- ✅ CBC 2.10.10 + Pyomo 6.9.4
- ✅ CBC 2.10.5 + Pyomo 6.9.4

**Note:** Commercial solvers (Gurobi, CPLEX) don't have this issue and fully support option passing.

### Problem: Solver is very slow

**Solutions:**
1. Check problem size: `model.nvariables()`, `model.nconstraints()`
2. Set time limit:
   ```python
   solver.options['sec'] = 300  # 5 minute timeout
   ```
3. Adjust MIP gap tolerance (accept near-optimal solutions):
   ```python
   solver.options['ratio'] = 0.01  # 1% gap acceptable
   ```
4. Consider commercial solver (Gurobi/CPLEX) for large problems

### Problem: Out of memory

**Solutions:**
1. Reduce problem horizon (e.g., 30 days instead of 200 days)
2. Use rolling horizon approach (optimize in 30-day windows)
3. Increase system RAM or use high-memory machine

---

## Solver Performance Comparison

Based on benchmarks with this application:

| Problem Size | CBC (free) | GLPK (free) | Gurobi (commercial) |
|--------------|-----------|-------------|---------------------|
| 5 days, 2 products | <1 sec | <1 sec | <1 sec |
| 30 days, 5 products | ~30 sec | ~2 min | ~5 sec |
| 60 days, 5 products | ~3 min | ~10 min | ~20 sec |
| 200 days, 5 products | ~20 min | timeout | ~2 min |

**Note:** Performance varies based on problem complexity (number of constraints, integer variables).

---

## Recommended Setup

For **development and testing:**
```bash
conda install -c conda-forge coincbc
```

For **small production use** (< 60 day horizons):
```bash
conda install -c conda-forge coincbc
```

For **large production use** (60-200 day horizons):
```bash
# Option 1: Gurobi (if you have license)
conda install -c gurobi gurobi

# Option 2: Use rolling horizon with CBC (break 200 days into 4 × 50-day windows)
```

---

## Next Steps

After installing a solver:
1. Run verification test: `python test_solver.py`
2. Check application's solver configuration: See `src/optimization/solver_config.py`
3. Run optimization examples: See `examples/optimization_examples.ipynb`
4. Read optimization guide: See `docs/OPTIMIZATION_GUIDE.md`

---

## Support

If you encounter issues:
1. Check Pyomo documentation: https://pyomo.readthedocs.io/
2. Check CBC documentation: https://github.com/coin-or/Cbc
3. Check solver-specific forums:
   - CBC: https://github.com/coin-or/Cbc/issues
   - Gurobi: https://support.gurobi.com/
   - CPLEX: https://www.ibm.com/support/pages/ibm-ilog-cplex-optimization-studio

---

**Last Updated:** 2025-10-02
