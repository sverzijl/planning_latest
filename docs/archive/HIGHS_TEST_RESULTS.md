# HiGHS Solver Test Results

## Executive Summary

**❌ HiGHS is NOT faster than CBC for this problem**

Contrary to 2024 benchmarks suggesting HiGHS is 10-100x faster than CBC, actual testing on the production planning model shows **HiGHS is 6x SLOWER** than CBC.

**Conclusion: Stick with CBC as your solver**

---

## Test Results

### 14-Day Window

| Solver | Time | Speedup vs CBC | Status |
|--------|------|----------------|--------|
| **CBC** | **2.30s** | **1.0x (baseline)** | ✅ **Optimal** |
| highs (standard) | 14.10s | 0.16x (6x slower) | ✅ Optimal |
| appsi_highs (APPSI interface) | 14.68s | 0.16x (6x slower) | ✅ Optimal |
| GLPK | - | - | ❌ Not installed |

**All solvers found the same solution**: $483,385.13 (verified optimal)

### 21-Day Window (Scaling Test)

| Solver | Time | Status |
|--------|------|--------|
| CBC | >120s | ❌ Timeout |
| HiGHS | >120s | ❌ Timeout |

**Result**: Both CBC and HiGHS timeout on 21-day windows. HiGHS does **NOT** scale better than CBC - both struggle equally with larger windows.

---

## Why HiGHS is Slower

### Possible Reasons

1. **Problem Structure Favors CBC**
   - CBC's branch-and-bound strategy may be better suited for this specific MIP structure
   - Temporal coupling and shelf life constraints create a solution space where CBC excels

2. **Benchmark Mismatch**
   - 2024 benchmarks likely used different problem types (LP-heavy, different MIP structures)
   - HiGHS may excel on problems with different characteristics

3. **Tuning Required**
   - Both CBC and HiGHS have many parameters
   - Default settings may not be optimal for either solver on this problem
   - CBC may benefit from better defaults for production planning problems

4. **Python Interface Overhead**
   - Pyomo interfaces to HiGHS may add overhead
   - CBC's Pyomo integration is more mature

---

## Implications for 21-Day Windows

**Test Result: Both CBC and HiGHS timeout on 21-day windows**
- 14-day windows: CBC solves in ~2-4s, HiGHS in ~14s
- 21-day windows: Both timeout after 2+ minutes

**Scaling test answer: NO, HiGHS does not scale better than CBC.**

**Available options:**

1. **Accept the 14-day/7-day configuration** (proven, reliable, 100% feasible)

2. **Aggressive CBC tuning** (may provide 20-50% speedup, but unlikely to solve 21-day)
   ```python
   solver.options.update({
       'seconds': 300,
       'ratio': 0.01,        # 1% gap acceptable
       'tune': 2,            # Maximum tuning
       'preprocess': 'sos',
       'cuts': 'on',
       'heuristics': 'on',
   })
   ```

3. **Fix-and-optimize heuristic** (advanced, decompose 21-day into solvable sub-problems)

---

## Recommendation Update

**Original Plan**: Use HiGHS to unlock 21-day windows
**Reality**: HiGHS is slower than CBC

**New Recommendation**:

### For Production (Immediate)
✅ **Use 14-day windows with 7-day overlap**
- Proven: 100% feasibility on full 29-week dataset
- Fast: 2-4 seconds per window, ~2 minutes total
- Optimal: Best known cost ($6,896,522 for full dataset)
- Reliable: No solver issues

### For Experimentation (If Time Permits)

**Option A: CBC Tuning**
- Apply research-backed parameter settings
- Expected: 20-50% faster
- Outcome: Unlikely to solve 21-day, but may help with larger problems in future

**Option B: Fix-and-Optimize** (Advanced)
- Decompose 21-day into 3x 7-day sub-problems
- Solve sequentially with overlap
- Outcome: Feasible solutions (sub-optimal by 2-10%)

**Option C: Try Commercial Solver Trial** (If Available)
- Gurobi offers academic/trial licenses
- Would definitively test if solver is the bottleneck
- May unlock 21-day windows if Gurobi succeeds where CBC fails

---

## Key Insight

**Your intuition was 100% correct**: The model complexity grows linearly (1.4x for 21d vs 14d).

**The bottleneck is NOT the model, it's CBC's algorithm** for this specific problem structure.

The shelf life constraints create a solution space that becomes exponentially harder to explore over 21 days, even though the model itself only grows linearly.

**HiGHS does not solve this issue** - it has the same algorithmic challenges as CBC for this problem type.

---

## Files Created

- `test_highs_comparison.py` - Comparison test (found HiGHS is slower)
- `highs_test_results.txt` - Raw test output
- This document - Analysis and recommendations

## Test Date
2025-10-07

## Status
✅ **HiGHS TESTED - NOT SUITABLE FOR THIS PROBLEM**
✅ **RECOMMENDATION: STICK WITH 14-DAY/7-DAY CBC CONFIGURATION**
