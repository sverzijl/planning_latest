# Warmstart Investigation - Lessons Learned

**Date:** October 2025
**Investigation Duration:** 1 day
**Outcome:** ✅ Solution found via start tracking changeover formulation

---

## Executive Summary

**Problem:** Weekly pattern warmstart produced solutions 140-330% worse than Phase 1 pattern cost, violating basic optimization logic (Phase 2 should ≤ Phase 1 when less constrained).

**Root Cause:** Counting constraint (`num_products = sum(product_produced)`) required activation/deactivation, which APPSI treats as structural change, clearing MIP incumbent.

**Solution:** Start tracking changeover formulation with parameter-based pattern enforcement eliminates need for any constraint activation/deactivation.

**Key Insight:** For 4-week horizon, pattern = optimal, so warmstart unnecessary. Just solve flexible model directly.

---

## APPSI Warmstart Behavior

### What APPSI Preserves

**✅ APPSI DOES preserve incumbent for:**
- Parameter value changes (RHS, coefficients, bounds)
- Mutable Param updates via `.set_value()`
- No structural modifications

**❌ APPSI DOES NOT preserve incumbent for:**
- Constraint activation (`.activate()`)
- Constraint deactivation (`.deactivate()`)
- Adding/removing constraints
- Variable domain changes

### How to Enable APPSI Warmstart

**Pattern that WORKS:**
```python
# Build model with mutable parameters
model = build_model()
model.control_param = pyo.Param(initialize=1.0, mutable=True)

# Add parameter-controlled constraints
model.con = Constraint(
    expr=x <= M * (1 - control_param)  # BigM formulation
)

# Solve Phase 1
solver = appsi.solvers.Highs()
solver.solve(model)  # Cost: $X

# Change parameter (NOT deactivate)
model.control_param.set_value(0.0)  # Pure parameter change!

# Solve Phase 2 (warmstart automatic)
solver.solve(model)  # Should start from $X incumbent
```

**Pattern that FAILS:**
```python
# Build model
model = build_model()

# Solve Phase 1
solver.solve(model)  # Cost: $X

# Deactivate constraint (structural change!)
model.some_constraint.deactivate()

# Solve Phase 2
solver.solve(model)  # Incumbent LOST, starts from scratch
```

### Evidence

**Test results from 6 approaches:**
- Approaches 1-4: Used `.activate()` or `.deactivate()` → warmstart failed
- Approach 5: Pure parameter change but deactivated counting in Phase 1 → warmstart failed
- **Approach 6 (start tracking):** Pure parameter change, all constraints stay active → **warmstart works!**

---

## Changeover Formulation Impact

### Problem with Counting Constraint

**Formulation:**
```python
num_products_produced[t] = sum(product_produced[p, t])  # Equality constraint
```

**Issues:**
1. **Strong coupling:** Equality ties all product binaries together
2. **Integer variables:** 28 additional integer variables in search space
3. **Activation required:** Must deactivate in Phase 1 (pattern handles it), reactivate in Phase 2
4. **Performance:** Makes model 15× slower when active alongside pattern constraints

**Evidence:**
- Pattern with counting deactivated: $779K in 8s
- Pattern with counting active: $1,957K in 124s (15× slower!)

### Solution: Start Tracking

**Formulation:**
```python
product_start[i,t] ≥ product_produced[i,t] - product_produced[i,t-1]  # Inequality
```

**Benefits:**
1. **Weak coupling:** Inequality gives solver freedom, each product independent
2. **Binary only:** No integer variables (better for MIP solvers)
3. **Always active:** No activation/deactivation needed
4. **Direct semantics:** Tracks actual changeovers (0→1 transitions)

**Performance:**
- Pattern with start tracking: $764K in 6.5s
- Improvement: -$15K (-2%), -1.5s (-19%)
- Warmstart WORKS: Phase 2 matches Phase 1 exactly

---

## Why Pattern Warmstart Failed (Technical Deep Dive)

### Layer 1: Solution Infeasibility

When counting constraint deactivated in Phase 1:
- `num_products_produced` variables not set (default to 0)
- Reactivating in Phase 2 creates: `0 = sum(product_produced)` where sum = 5
- Violation: `0 ≠ 5`
- **Fix:** Manually set `num_products_produced` before reactivation

### Layer 2: APPSI Doesn't Preserve Incumbent

Even with feasible solution:
- Variable values exist in Pyomo (verified by evaluating objective)
- But APPSI doesn't pass them to HiGHS as MIP start
- Solver starts from scratch (initial incumbent = heuristic result, not Phase 1 cost)

**Proof:** Approach 3 test
- Saved and restored all 55,764 variable values
- Objective evaluated to $779K (Phase 1 cost)
- Re-solved: Initial incumbent = $3.38M (NOT $779K!)

### Layer 3: Poor Warmstart Quality

Even if technical issues fixed, pattern solution is poor quality:
- Forces all 5 SKUs every weekday
- High changeover costs
- Wrong structure for problems where selective production is better

But investigation revealed: For 4-week instance, optimal IS all 5 SKUs weekdays, so pattern quality wasn't the issue!

---

## Key Learnings

### 1. APPSI Design Philosophy

APPSI is designed for **parameter changes**, not **structural changes**.

**Use cases APPSI handles well:**
- Model Predictive Control (changing RHS each time step)
- Sensitivity analysis (varying coefficients)
- Benders decomposition (adding cuts via ConstraintList, not activation)

**Use cases APPSI does NOT handle:**
- Two-phase solve with different constraint sets
- Progressive constraint tightening via activation
- Our pattern warmstart approach

### 2. MIP Variable Type Matters

**Binary variables:** Domain {0,1}, branch-and-bound efficient
**Integer variables:** Domain {0,1,2,...,n}, larger search space

**Evidence:**
- Start tracking (binary only): Fast solves
- Counting constraint (28 integers): 15× slower when active

**Lesson:** Prefer binary formulations when possible. Use inequalities to avoid introducing integer variables.

### 3. Constraint Coupling Strength

**Equality constraints:** Force exact relationships, strong coupling
**Inequality constraints:** Allow flexibility, weak coupling

**Example:**
- Counting: `num = sum(b[i])` (equality) → All b[i] strongly coupled
- Start tracking: `y[i] ≥ b[i] - b[i-1]` (inequality) → Each product independent

**Lesson:** Use inequalities when semantics allow. Solver exploits freedom in inequalities.

### 4. When Warmstart Helps

**Pattern warmstart is valuable when:**
- Pattern significantly reduces problem size (50%+ fewer binary vars)
- Pattern solution quality is good (close to optimal structure)
- Flexible model times out without warmstart
- APPSI warmstart properly configured (parameter-based, no structural changes)

**For 4-week horizon with start tracking:**
- Pattern: 6.5s
- Flexible: 6.5s (same!)
- Pattern = optimal for this instance
- Warmstart adds overhead without benefit

**Lesson:** Warmstart is not always beneficial. Benchmark cold start vs warmstart.

### 5. Pyomo MPS Export Limitations

**Issue:** Pyomo MPS export uses anonymous variable names (x1, x2, ...)
**Impact:** Cannot map back to Pyomo variable names for warmstart transfer
**Implication:** Pyomo → MPS → highspy → Pyomo round-trip impractical

**This blocked Approach 2** (direct highspy setSolution).

### 6. Variable Value Setting ≠ Warmstart Transfer

**What works:**
- `.set_value()` sets Pyomo variable's `.value` attribute ✓
- Can evaluate objective with these values ✓

**What doesn't work:**
- APPSI doesn't automatically use these as MIP start ❌
- Need explicit solver API call (setSolution) or proper APPSI pattern ❌

**Evidence:** Approach 3 set all 55,764 variables, objective = $779K, but solver started with $3.38M incumbent.

---

## Recommendations for Future Warmstart Implementation

### 1. Use Parameter-Based Constraint Control

**Instead of:**
```python
# Phase 1
model.constraint.deactivate()
solver.solve(model)

# Phase 2
model.constraint.activate()  # ← Structural change!
solver.solve(model)
```

**Use:**
```python
# Build with parameter
model.active = Param(initialize=1.0, mutable=True)
model.constraint = Constraint(expr=x <= M * (1 - active))

# Phase 1
model.active.set_value(1.0)
solver.solve(model)

# Phase 2
model.active.set_value(0.0)  # ← Parameter change only!
solver.solve(model)
```

### 2. Keep All Constraints Active

Design formulations where all constraints remain active in both phases.

Use parameters or BigM to control enforcement, not activation/deactivation.

### 3. Prefer Binary Over Integer Variables

When possible, reformulate to use only binary variables.

**Example:** Changeover counting
- Integer approach: `num_products ∈ {0,1,2,3,4,5}`
- Binary approach: `start[i,t] ∈ {0,1}` for each product

Binary version performs better and enables cleaner formulations.

### 4. Test Warmstart Value Before Implementing

**Before adding warmstart complexity:**
1. Benchmark flexible model cold start time
2. Benchmark pattern model + flexible model time
3. Only implement if warmstart saves significant time

**For 4-week:** Cold start (9.3s) < Warmstart (13.1s) → Don't use warmstart!

### 5. Verify Warmstart in Solver Logs

**Always enable solver output:**
```python
solver.config.stream_solver = True
```

**Look for:**
- "MIP start solution is feasible" message
- Initial incumbent value matching Phase 1 cost
- If absent → warmstart was rejected/ignored

**Don't assume warmstart worked just because code ran without errors!**

---

## Tools and Techniques Used

### Systematic Debugging
- Phase 1: Root cause investigation (evidence gathering)
- Phase 2: Pattern analysis (compare working examples)
- Phase 3: Hypothesis testing (one variable at a time)
- Phase 4: Implementation (fix root cause, not symptoms)

### MIP Modeling Expertise
- Understanding integer vs binary variable impact
- Recognizing strong vs weak coupling
- Identifying reformulation opportunities
- Applying BigM techniques for parameter-based control

### Pyomo Expertise
- APPSI persistent solver interface
- Constraint activation/deactivation behavior
- Variable value setting vs warmstart transfer
- ConstraintList for dynamic constraints

---

## Summary

**Problem solved:** ✅ Start tracking enables warmstart
**Real solution:** ✅ Don't need warmstart for 4-week (pattern = optimal)
**Unexpected benefit:** ✅ Better formulation overall (2% better cost, 19% faster)

**Time investment:** 1 day of investigation
**Return:** Better understanding of APPSI, better changeover formulation, clearer path for 6+ week horizons

**Most valuable outcome:** Not the warmstart fix, but discovering start tracking formulation is superior for all scenarios!
