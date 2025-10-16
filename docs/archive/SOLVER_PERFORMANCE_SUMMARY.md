# Solver Performance Analysis Summary

## Executive Summary

**The 3-week performance cliff is caused by exponential growth in integer programming difficulty, NOT model size.**

### Key Findings

| Horizon | LP Time | MIP Time | MIP Growth |
|---------|---------|----------|------------|
| 1 week  | 0.20s   | 1.30s    | baseline   |
| 2 weeks | 0.32s   | 1.96s    | 1.51x      |
| 3 weeks | 0.51s   | **11.11s** | **5.67x** |

**Critical Discovery:**
- LP (no integer constraints) solves quickly and scales linearly ✅
- MIP (with integer constraints) grows **exponentially** - averaging **2.92x per week** ❌

## Root Cause Analysis

### Why MIP Explodes While LP Remains Fast

1. **Weak LP Relaxation (242% integrality gap at 2 weeks)**
   - LP bound: $141,238
   - Integer solution: $483,385
   - Gap forces extensive branch-and-bound search

2. **Exponential Search Tree**
   - 300 integer variables at 3 weeks
   - Each binary variable doubles potential search space
   - Theoretical combinations: 2^300 ≈ 10^90

3. **Symmetry Problem**
   - Multiple trucks can serve same destination
   - Many equivalent solutions confuse solver
   - Wasted effort exploring symmetric branches

## Projected Performance

### CBC Solver (current)

| Weeks | Estimated Time |
|-------|---------------|
| 4     | 26 seconds    |
| 6     | 3.7 minutes   |
| 8     | 32 minutes    |
| 10    | 4.5 hours     |
| 29    | **IMPRACTICAL** (exponential blowup) |

**Conclusion:** CBC cannot solve the full 29-week dataset in reasonable time.

## Practical Solutions

### ✅ **RECOMMENDED: Rolling Horizon Approach**

**Strategy:** Optimize 4 weeks at a time, roll forward

- **4-week optimization:** ~26 seconds each
- **Number of runs:** 7-8 (with overlap)
- **Total time:** ~3-4 minutes
- **Benefits:**
  - Fast, predictable solve times
  - Can handle any forecast length
  - Mimics real-world replanning

**Implementation:**
```python
# Pseudo-code
horizon_weeks = 4
overlap_weeks = 1

for start_week in range(0, 29, horizon_weeks - overlap_weeks):
    end_week = min(start_week + horizon_weeks, 29)
    optimize(weeks=range(start_week, end_week))
    # Execute first (horizon - overlap) weeks
    # Keep last week as starting inventory for next iteration
```

### ⚡ **Alternative 1: Relax MIP Gap**

**Current:** 1% gap (very tight)
**Suggested:** 5-10% gap

- Allows solver to stop earlier
- Still finds good solutions (within 5-10% of optimal)
- May reduce solve time by 5-10x

### 💎 **Alternative 2: Commercial Solver**

**Gurobi or CPLEX:**
- 5-10x faster than CBC
- Better cutting planes and heuristics
- May solve 10 weeks in ~30 minutes
- Still likely needs rolling horizon for 29 weeks

### 🔧 **Alternative 3: Model Improvements**

1. **Symmetry Breaking:**
   - Add constraints: if truck[i] not used, truck[i+1] not used
   - Reduces equivalent solutions

2. **Branching Priorities:**
   - Branch on truck assignments first
   - Defer production quantity decisions

3. **Valid Inequalities:**
   - Add cutting planes to strengthen LP relaxation
   - Reduce integrality gap

4. **Fix-and-Optimize Heuristic:**
   - Pre-assign trucks using greedy heuristic
   - Optimize only production quantities
   - 10-100x speedup possible

## Recommendations by Use Case

### For Production Deployment
→ **Use Rolling Horizon (4-6 weeks)** with 1-week overlap
- Fastest, most reliable
- Handles any dataset size
- 3-5 minute total solve time

### For Strategic Planning
→ **Use Commercial Solver + Rolling Horizon**
- Gurobi/CPLEX for better solutions
- 6-8 week windows for longer view
- ~15-30 minute solve time

### For Research/Prototyping
→ **Use CBC with Relaxed Gap (5-10%)**
- Free solver
- Good enough solutions
- 4-6 week windows manageable

## Technical Details

### Exponential Fit
```
MIP Time = 0.357 × exp(1.073 × weeks)
R² = 0.8987
```

This means MIP time roughly **triples every week** beyond week 2.

### Integer Variables Growth
- 1 week: 132 vars
- 2 weeks: 216 vars (+84)
- 3 weeks: 300 vars (+84)
- 29 weeks: ~2,436 vars (extrapolated)

### Why 3 Weeks is the Cliff
- Week 1-2: Solver can enumerate small search tree
- Week 3: Search tree exceeds solver's efficient threshold
- Week 3+: Exponential blowup in branch-and-bound

The jump from 1.96s to 11.11s (5.67x) at week 3 is where the solver's branch-and-bound algorithm can no longer efficiently explore the solution space.

---

## Files Generated

1. `diagnose_3week_timeout.py` - Diagnostic script
2. `performance_analysis_report.py` - Analysis and extrapolation
3. `solver_performance_extrapolation.png` - Visualization
4. `SOLVER_PERFORMANCE_SUMMARY.md` - This document

## Next Steps

1. **Implement rolling horizon optimization** (recommended)
2. Test with 4-week windows on full dataset
3. Measure actual end-to-end time
4. Consider Gurobi trial for comparison
