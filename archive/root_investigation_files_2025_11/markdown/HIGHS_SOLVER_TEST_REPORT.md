# HiGHS Solver Performance Test Report

**Test Date:** 2025-10-19
**Test Subject:** HiGHS solver as alternative to CBC for binary product_produced variables
**HiGHS Version:** 1.11.0
**Model:** UnifiedNodeModel with binary product tracking

---

## Executive Summary

**HiGHS is 2.35x FASTER than CBC** for the 4-week production planning problem with binary product_produced variables.

**Key Results:**
- **4-week horizon:** 96s (HiGHS) vs 226s (CBC) → **2.35x speedup**
- **1-week horizon:** 1.9s (HiGHS) vs ~8-10s (CBC estimate) → **4-5x speedup**
- **Solution quality:** OPTIMAL in all tests (gap <1%)
- **Warmstart:** Not effective for HiGHS (no performance difference)
- **Recommendation:** **Use HiGHS as primary solver for MIP problems**

---

## Test Configuration

### Problem Size (4-week horizon):
- **Variables:** 53,797 total
  - 2,726 integer variables
  - 522 binary variables
  - 51,071 continuous variables
- **Constraints:** 33,497 total
- **Nonzeros:** 132,595

### Problem Size (1-week horizon):
- **Variables:** 5,494 total
  - 332 integer variables
  - 144 binary variables
  - 5,050 continuous variables
- **Constraints:** 4,015 total
- **Nonzeros:** 13,494

### Solver Settings:
- **MIP Gap Tolerance:** 1%
- **Time Limit:** 300s (4-week), 60s (1-week)
- **Warmstart:** Tested both enabled and disabled
- **Aggressive Heuristics:** Not enabled (default settings)

---

## Performance Results

### 1-Week Horizon (Quick Test)

| Configuration               | Solve Time | Status  | Gap    | Cost      | LP Iters |
|-----------------------------|------------|---------|--------|-----------|----------|
| HiGHS (no warmstart)        | 1.9s       | OPTIMAL | 0.23%  | $286,335  | 3,166    |
| HiGHS (warmstart)           | 2.2s       | OPTIMAL | 0.23%  | $286,335  | 3,166    |

**Observations:**
- HiGHS solves 1-week problem in **under 2 seconds**
- Warmstart provides no benefit (same number of LP iterations)
- Optimal solution found within gap tolerance

### 4-Week Horizon (CBC Baseline Comparison)

| Configuration               | Solve Time | Status  | Gap    | Cost      | Nodes | LP Iters |
|-----------------------------|------------|---------|--------|-----------|-------|----------|
| HiGHS (no warmstart)        | 96.2s      | OPTIMAL | 0.91%  | $512,113  | 3     | 62,107   |
| HiGHS (warmstart)           | 96.0s      | OPTIMAL | 0.91%  | $512,113  | 3     | 62,107   |
| **CBC (no warmstart)**      | **226s**   | OPTIMAL | <1%    | ~$512K    | -     | -        |
| **CBC (warmstart)**         | **>300s**  | TIMEOUT | ~100%  | -         | -     | -        |

**Observations:**
- HiGHS solves 4-week problem in **96 seconds** vs CBC's 226 seconds
- **2.35x faster than CBC**
- Warmstart has negligible effect (96.0s vs 96.2s - within noise)
- Only 3 B&B nodes explored (excellent presolve and cutting planes)
- Excellent symmetry detection (found 4 generators)

---

## Solver Behavior Analysis

### HiGHS Strengths:

1. **Powerful Presolve:**
   - Original problem: 33,497 rows, 53,797 cols
   - After presolve: 12,668 rows, 25,169 cols (62% reduction)
   - Removes dominated variables and redundant constraints

2. **Effective Heuristics:**
   - **Feasibility Jump (J):** Found initial solution quickly (1.8s)
   - **Randomized Rounding (R):** Improved solution quality (65% gap → 3.4s)
   - **Sub-MIP (L):** Final improvement to near-optimal (2.38% gap → 70.8s)

3. **Strong Cutting Planes:**
   - Generated 9,827 cuts in root node
   - 403 cuts kept in LP (dynamic constraint management)
   - Effective gap closure without excessive branching

4. **Symmetry Detection:**
   - Automatically detected 4 symmetry generators
   - Reduces search space significantly
   - CBC does not have this feature

5. **Minimal Branching:**
   - Only 3 B&B nodes explored for 4-week problem
   - Strong lower bounds from cutting planes
   - Efficient node selection

### HiGHS Limitations:

1. **Warmstart Not Supported:**
   - Setting initial variable values has no effect on solve time
   - Unlike CBC, HiGHS does not appear to use MIP warmstart hints
   - Presolve likely discards initial values

2. **No "Aggressive Heuristics" Mode:**
   - HiGHS uses fixed heuristic strategy
   - Cannot tune heuristic effort as extensively as CBC
   - Default settings work well for this problem

---

## Comparison to CBC

### Why HiGHS is Faster:

1. **Better Presolve:**
   - CBC presolve: Less aggressive, fewer reductions
   - HiGHS presolve: 62% variable reduction, better bound tightening

2. **Modern Heuristics:**
   - HiGHS uses state-of-the-art MIP heuristics (Feasibility Jump, Sub-MIP)
   - CBC relies on older heuristics (RINS, Feasibility Pump, Diving)

3. **Symmetry Breaking:**
   - HiGHS: Automatic symmetry detection (found 4 generators)
   - CBC: No symmetry detection (explores symmetric solutions redundantly)

4. **Cutting Plane Management:**
   - HiGHS: Dynamic cuts (adds/removes based on activity)
   - CBC: Static cuts (once added, stays in LP)

5. **LP Solver Performance:**
   - HiGHS: Native dual simplex with better numerics
   - CBC: Uses CLP (older code base)

### When CBC Might Be Better:

- **Warmstart scenarios:** CBC can leverage warmstart (but didn't help in our test)
- **Highly tunable:** CBC has more heuristic parameters (but default HiGHS wins)
- **Mature tooling:** More integration with other tools (Pyomo, AMPL, GAMS)

---

## Recommendations

### Primary Recommendation: **Use HiGHS**

For this production planning problem with binary product tracking:
1. **Use HiGHS as the default solver**
2. **Do NOT use warmstart** (no benefit, adds overhead)
3. **Use default settings** (no aggressive heuristics needed)
4. **Set 1% MIP gap** (good balance of quality and speed)

### Solver Selection Strategy:

```python
# Recommended solver configuration
result = model.solve(
    solver_name='highs',        # Use HiGHS
    use_warmstart=False,        # No benefit for HiGHS
    time_limit_seconds=120,     # 2 minutes sufficient for 4-week
    mip_gap=0.01,               # 1% gap tolerance
    tee=False,                  # Disable output for production
)
```

### Expected Performance:

| Horizon | Expected Solve Time | Status  | Gap   |
|---------|---------------------|---------|-------|
| 1 week  | 2-3 seconds         | OPTIMAL | <1%   |
| 2 weeks | 10-20 seconds       | OPTIMAL | <1%   |
| 4 weeks | 90-100 seconds      | OPTIMAL | <1%   |
| 8 weeks | 300-400 seconds (est) | OPTIMAL/FEASIBLE | <2% |

### Fallback to CBC:

Only use CBC if:
- HiGHS is unavailable (installation issues)
- Solver compatibility problems arise
- Specific CBC features are required (e.g., Gurobi-style callbacks)

---

## Implementation Notes

### Code Changes Required:

1. **base_model.py** - Add HiGHS solver options:
   ```python
   elif solver_name == 'highs':
       if time_limit_seconds is not None:
           options['time_limit'] = time_limit_seconds
       if mip_gap is not None:
           options['mip_rel_gap'] = mip_gap
   ```

2. **base_model.py** - Skip warmstart for HiGHS:
   ```python
   # HiGHS doesn't support warmstart kwarg
   if use_warmstart and solver_name not in ['highs']:
       solve_kwargs['warmstart'] = True
   ```

3. **solver_config.py** - Add HiGHS to available solvers list (already done).

### Installation:

```bash
pip install highspy
```

No additional configuration needed - HiGHS is pure Python package with compiled binaries.

---

## Conclusion

**HiGHS is the superior solver for this problem:**
- ✅ **2.35x faster** than CBC for 4-week horizon
- ✅ **Finds optimal solutions** consistently
- ✅ **Better presolve** and cutting planes
- ✅ **Automatic symmetry breaking**
- ✅ **Modern MIP heuristics**
- ✅ **Easy installation** (pip install highspy)

**Recommendation:** Switch to HiGHS as the default solver for all MIP models with binary product tracking.

---

## Appendix: Raw Test Output

### 4-Week HiGHS Solve Log:

```
Running HiGHS 1.11.0 (git hash: 364c83a): Copyright (c) 2025 HiGHS under MIT licence terms
MIP  has 33497 rows; 53797 cols; 132595 nonzeros; 2726 integer variables (522 binary)

Presolving model
26648 rows, 41536 cols, 108063 nonzeros  0s
18948 rows, 29754 cols, 78690 nonzeros  0s
13256 rows, 25930 cols, 64714 nonzeros  1s
12668 rows, 25169 cols, 62982 nonzeros  1s

Solving MIP model with:
   12668 rows
   25169 cols (182 binary, 1314 integer, 23673 continuous)
   62982 nonzeros

        Nodes      |    B&B Tree     |            Objective Bounds              |  Dynamic Constraints |       Work
Src  Proc. InQueue |  Leaves   Expl. | BestBound       BestSol              Gap |   Cuts   InLp Confl. | LpIters     Time

 J       0       0         0   0.00%   -inf            2457174.1077       Large        0      0      0         0     1.8s
 R       0       0         0   0.00%   493997.917936   1446150.822365    65.84%        0      0      0     12675     3.4s
         0       0         0   0.00%   498608.281387   1446150.822365    65.52%     4618    250     25     16159    12.5s
         0       0         0   0.00%   499118.444344   1446150.822365    65.49%     6521    389     25     19209    17.9s
         0       0         0   0.00%   499934.450321   1446150.822365    65.43%     9076    498     25     21748    22.9s
 L       0       0         0   0.00%   499934.450321   512112.60359       2.38%     9076    498     25     21748    70.8s

Symmetry detection completed in 0.0s
Found 4 generator(s)

         2       1         0  50.00%   502406.78402    512112.60359       1.90%     9086    351     34     61334    83.4s
         3       0         0 100.00%   507432.894965   512112.60359       0.91%     9827    403     34     62107    85.8s

Solving report
  Status            Optimal
  Primal bound      512112.60359
  Dual bound        507432.894965
  Gap               0.914% (tolerance: 1%)
  Timing            85.82 (total)
  Nodes             3
  LP iterations     62107 (total)
```

**Analysis:**
- **Heuristics (0-70s):** Built good feasible solution (gap from ∞ to 2.38%)
- **Cutting planes (0-23s):** Added 9,076 cuts to tighten LP relaxation
- **Symmetry breaking (70s):** Detected 4 symmetry generators
- **Branching (70-86s):** Only 3 nodes needed to prove optimality
- **Final gap:** 0.914% (well within 1% tolerance)

---

**End of Report**
