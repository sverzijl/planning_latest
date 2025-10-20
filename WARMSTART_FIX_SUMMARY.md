# CBC Warmstart Fix Summary

## Problem

CBC solver was not using warmstart values even when `use_warmstart=True` was passed to `UnifiedNodeModel.solve()`.

**Symptoms:**
- No `-mipstart` flag in CBC command line
- No "MIPStart values read" message
- Warmstart had no performance effect

## Root Cause

**File:** `src/optimization/unified_node_model.py`
**Line:** 1037-1043 (before fix)

The `UnifiedNodeModel.solve()` method was NOT passing the `use_warmstart` parameter to the base class `BaseOptimizationModel.solve()`:

```python
# BEFORE (BROKEN):
return super().solve(
    solver_name=solver_name,
    time_limit_seconds=time_limit_seconds,
    mip_gap=mip_gap,
    tee=tee,
    use_aggressive_heuristics=use_aggressive_heuristics,
    # MISSING: use_warmstart parameter!
)
```

Without `use_warmstart=True` being passed to the base class:
1. `BaseOptimizationModel.solve()` defaults to `use_warmstart=False`
2. Pyomo `solver.solve()` is called with `warmstart=False`
3. Pyomo CBC plugin skips generating the mipstart file
4. CBC never sees the `-mipstart` flag

## The Fix

**File:** `src/optimization/unified_node_model.py`
**Line:** 1043 (after fix)

Added the missing parameter:

```python
# AFTER (FIXED):
return super().solve(
    solver_name=solver_name,
    time_limit_seconds=time_limit_seconds,
    mip_gap=mip_gap,
    tee=tee,
    use_aggressive_heuristics=use_aggressive_heuristics,
    use_warmstart=use_warmstart,  # ← ADDED THIS LINE
)
```

## Verification

Test file: `test_mipstart_flag.py`

**Test 1:** `use_warmstart=True`
```
command line - /usr/bin/cbc ... -mipstart /tmp/tmp....cbc.soln ...
opening mipstart file /tmp/tmp....cbc.soln.
```
✓ `-mipstart` flag IS present

**Test 2:** `use_warmstart=False`
```
command line - /usr/bin/cbc -printingOptions all -import /tmp/tmp....lp -stat=1 -solve ...
```
✓ NO `-mipstart` flag (as expected)

## Investigation Process

### Hypotheses Tested

1. **Hypothesis:** `symbolic_solver_labels=False` breaks warmstart
   **Result:** ✗ False - Parameter does NOT affect warmstart

2. **Hypothesis:** `load_solutions=False` breaks warmstart
   **Result:** ✗ False - Parameter does NOT affect warmstart

3. **Hypothesis:** Variable assignment method (`=` vs `.set_value()`) incorrect
   **Result:** ✗ False - Direct assignment (`model.var = value`) is correct

4. **Hypothesis:** Missing `use_warmstart` parameter in base class call
   **Result:** ✓ TRUE - This was the root cause

### Code Analysis

Examined Pyomo CBC plugin (`venv/lib/python3.11/site-packages/pyomo/solvers/plugins/solvers/CBCplugin.py`):

- Line 414-415: `-mipstart` flag added ONLY when `self._warm_start_solve == True`
- Line 215: `self._warm_start_solve = kwds.pop('warmstart', False)`
- Line 277: Warmstart file written during `_presolve()`

The warmstart flag must flow through this chain:
```
UnifiedNodeModel.solve(use_warmstart=True)
  → BaseOptimizationModel.solve(use_warmstart=True)
    → solver.solve(warmstart=True)
      → CBCSHELL._presolve() extracts warmstart=True
        → CBCSHELL.create_command_line() adds -mipstart flag
```

The chain was broken at the first arrow (UnifiedNodeModel → BaseOptimizationModel).

## Additional Observations

### Warmstart Values Application

The `UnifiedNodeModel._apply_warmstart()` method (line 963-1000) correctly:
- Sets warmstart values using direct assignment: `model.product_produced[...] = hint_value`
- Is called from `build_model()` at line 689 before returning the model
- Uses the `self._warmstart_hints` dict populated in `solve()`

This part was working correctly - values WERE being set. The problem was that Pyomo wasn't being told to USE those values.

### CBC Warmstart Requirements

From Pyomo CBC plugin analysis:
- Only writes **integer/binary** variables with **non-zero values** (line 190-198)
- Warmstart only supported for LP file format (`ProblemFormat.cpxlp`), not NL format (line 171-174)
- Requires CBC version >= 2.8.0 (line 170-174)

All requirements were met in our setup.

## Performance Impact

**Expected improvement:** 10-30% faster solve times for large problems with good warmstart hints.

**Note:** The warmstart effect depends on hint quality:
- Good hints (feasible, near-optimal) → significant speedup
- Poor hints (infeasible, far from optimal) → minimal or negative effect

The campaign-based warmstart generator (`_generate_warmstart()`) produces high-quality hints by:
- Ensuring production only on valid days (respecting fixed hours)
- Spreading production evenly (avoiding spikes)
- Meeting freshness constraints (max 7-day gaps)

## Related Files

- `src/optimization/unified_node_model.py` - Contains the fix (line 1043)
- `src/optimization/base_model.py` - Base class that receives use_warmstart parameter
- `src/optimization/warmstart_generator.py` - Generates warmstart hints
- `test_mipstart_flag.py` - Verification test
- `test_warmstart_minimal.py` - Parameter isolation test

## Pyomo Version

- Version: 6.9.4
- CBC Plugin: `/venv/lib/python3.11/site-packages/pyomo/solvers/plugins/solvers/CBCplugin.py`

## Date

Fixed: 2025-10-19
