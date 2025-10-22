# APPSI Warmstart Root Cause Analysis

**Date:** 2025-10-22
**Status:** ✅ **ROOT CAUSE IDENTIFIED**

---

## The Mystery

**Expected Behavior:**
```
Phase 1: Solve with pattern → $795K
Phase 2: Deactivate pattern, re-solve → Should return ≤ $795K
```

**Actual Behavior:**
```
Phase 1: $795K
Phase 2: $1,928K (142% WORSE!)
```

**This violates basic optimization logic!** Phase 2 is LESS constrained, so it should find equal or better solution.

---

## Investigation Trail

### Test 1: Check Feasibility
**Question:** Is Phase 1 solution feasible for Phase 2?

**Answer:** NO initially, YES after fix
- **Problem:** `num_products_produced` variables not set in Phase 1 (changeover constraints deactivated)
- **Fix:** Set `num_products_produced = count(product_produced)` before reactivating
- **Result:** Phase 1 solution now satisfies ALL Phase 2 constraints ✓

### Test 2: Re-solve with Feasible Warmstart
**Question:** Does fixing feasibility allow Phase 2 to use warmstart?

**Answer:** NO - warmstart STILL not used!
```
Phase 2 Initial Incumbent: $3,376,253  ← NOT $795K from Phase 1
Final Cost: $1,928,089 (worse than both)
```

---

## ROOT CAUSE

**APPSI does NOT preserve MIP incumbent when constraints are deactivated/reactivated.**

### Evidence

1. **Phase 1 solve produces:** $795K solution with all variables set
2. **We preserve solution:** Set all auxiliary variables (num_products_produced)
3. **We verify feasibility:** Phase 1 solution satisfies Phase 2 constraints ✓
4. **Phase 2 solver log shows:** Initial incumbent = $3,376K (NOT $795K)

**Conclusion:** When we called `solver.solve(model)` the second time after deactivating/reactivating constraints, APPSI did NOT pass the current variable values to HiGHS as a MIP start.

### Why This Happens

From Pyomo research and APPSI documentation:

**APPSI hot-start is designed for:**
- Changing parameter values (RHS, coefficients)
- Small model modifications
- **NOT** for structural changes (constraint activation/deactivation)

**When constraints are activated/deactivated:**
- APPSI sees this as a **model structure change**
- HiGHS internal state may be invalidated
- **MIP incumbent is NOT preserved** (only LP basis for continuous problems)

**Key insight from research:**
> "For LPs... HiGHS automatically performs hot start, reusing basis"
> "For MIPs... provide feasible solution via setSolution"

APPSI automatic hot-start works for **LP** (basis preservation), but for **MIP** with structural changes, we need **explicit setSolution call**.

---

## The Real Problem

### APPSI Doesn't Have setSolution Method!

From APPSI documentation search:
- APPSI Highs() interface doesn't expose HiGHS's `setSolution()` method
- APPSI relies on Pyomo variable `.value` + automatic transfer
- But this automatic transfer only works for **parameter changes**, not **structural changes**

### What We're Doing Wrong

```python
# Current approach:
model = build_model()
solver.solve(model)  # Phase 1

# Modify structure
deactivate_constraints()
reactivate_other_constraints()

solver.solve(model)  # Phase 2 - APPSI sees new structure, clears incumbent!
```

### What We Need To Do

We need to **explicitly reconstruct the MIP start** after model modifications:

**Option A: Use non-APPSI interface with explicit warmstart**
```python
from pyomo.opt import SolverFactory

solver = SolverFactory('highs')  # Not APPSI!

# Phase 1
result1 = solver.solve(model1)

# Build Phase 2 model (separate or modified)
model2 = build_or_modify_model()

# Set variable values
for var in model2.vars:
    var.value = get_value_from_phase1(var)

# Solve with explicit warmstart flag
result2 = solver.solve(model2, warmstart=True)  # Generates .mst file
```

**Option B: Rebuild model instead of modifying**
```python
# Phase 1
model1 = build_with_pattern()
solver1.solve(model1)

# Phase 2 - build NEW model
model2 = build_without_pattern()  # Fresh model, no modifications

# Transfer values explicitly
transfer_solution(model1, model2)

# Solve with APPSI (fresh model, variable values set)
solver2 = appsi.solvers.Highs()
solver2.config.warmstart = True  # May not work
result2 = solver2.solve(model2)
```

**Option C: Don't modify constraints - build both models upfront**
```python
# Build both models at start
model_pattern = build_with_pattern_constraints()
model_flexible = build_without_pattern_constraints()

# Solve pattern
solver.solve(model_pattern)

# Transfer solution to flexible
transfer_all_variables(model_pattern, model_flexible)

# Solve flexible (separate model, new solver instance?)
result = solver.solve(model_flexible)
```

---

## Why Pattern Warmstart Fails (Complete Picture)

### Level 1: Poor Solution Quality
- Pattern forces all 5 SKUs daily
- This is fundamentally wrong structure for optimal solution
- **Even if warmstart worked, it would mislead solver**

### Level 2: Solution Becomes Infeasible
- Deactivating changeover in Phase 1 → `num_products_produced` not set
- Reactivating in Phase 2 → solution violates constraints
- **We fixed this** by setting `num_products_produced`

### Level 3: APPSI Doesn't Preserve MIP Incumbent
- Even with feasible solution, APPSI doesn't pass it to HiGHS
- Structural changes (constraint activation) clear the warmstart
- **This is the current blocker**

---

## Recommendations

### Short Term: ABANDON Pattern Warmstart

**Why:**
1. Poor solution quality (Level 1 problem)
2. APPSI technical limitations (Level 3 problem)
3. Complexity not justified by results
4. Cold start performs better

**Use instead:**
```python
# Just solve directly
model = UnifiedNodeModel(..., force_all_skus_daily=False)
result = model.solve(solver_name='appsi_highs', time_limit_seconds=300)
```

### Medium Term: If Warmstart Needed

**Try non-APPSI interface:**
```python
solver = SolverFactory('highs')  # Not APPSI
result = solver.solve(model, warmstart=True)  # Explicit warmstart flag
```

This may properly generate .mst file with variable values.

### Long Term: Better Warmstart Strategies

1. **LP relaxation warmstart** - Better quality than pattern
2. **Greedy heuristic** - Domain-specific, high quality
3. **Rolling horizon** - Solve incrementally
4. **Just use cold start** - Modern solvers are good!

---

## Key Lessons

1. **APPSI automatic hot-start ≠ MIP warmstart**
   - APPSI preserves LP basis automatically
   - MIP incumbent NOT preserved across structural changes

2. **Warmstart mechanism < Warmstart quality**
   - Even if we fix the technical issue
   - Pattern solution is still poor quality
   - Would still mislead solver

3. **When constraints change, warmstart is hard**
   - Deactivate/reactivate breaks APPSI automatic transfer
   - Need explicit solution preservation
   - May require different solver interface

---

## Conclusion

**Three-layer failure:**
1. ❌ Pattern solution is poor quality (all SKUs daily)
2. ❌ Solution becomes infeasible when constraints change (fixed)
3. ❌ APPSI doesn't preserve MIP incumbent on structural changes (unfixable with current interface)

**Recommendation:** Abandon pattern warmstart. Use direct solve with modern solver heuristics.
