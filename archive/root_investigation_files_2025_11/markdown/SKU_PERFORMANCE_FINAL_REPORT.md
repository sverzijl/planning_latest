# SKU Performance Investigation - Final Report

## Executive Summary

Investigated performance degradation when allowing binary SKU selection vs forcing all SKUs to produce. Tested multiple optimization strategies and warmstart approaches.

**Bottom line: Single-phase binary SKU optimization remains the best approach (83s, $597,869).**

---

## Problem Statement

Original issue: Model became very slow when varying SKU selection vs. forcing all products every day.

**Observed:**
- All SKUs forced: ~13s
- Binary SKU selection: 120s+ timeout → improved to 83s

---

## Root Cause Analysis (Using Systematic Debugging)

### Phase 1: Evidence Gathering

**Key Findings:**

1. **MIP Complexity Threshold at 50-60 Binary Variables:**
   - 0-40 binary vars: 12-15s (with good pattern)
   - 50-80 binary vars: 48-72s (exponential growth)
   - 140 binary vars: 83s (full problem)

2. **Pattern Quality Matters More Than Count:**
   - Smart pattern (greedy removal): 19 binary vars → 13.5s
   - Arbitrary pattern: 20 binary vars → 57.5s (4× slower!)
   - Greedy patterns are easier for solver to handle

3. **Warmstart Provides Modest Benefit:**
   - Measured: 8% speedup (78.4s → 72.0s)
   - Requires working solution extraction

### Phase 2-3: Hypothesis Testing

**Tested Approaches:**

1. **Tighter Big-M Constraint** ✅
   - Reduced from 33,600 to 19,600 (41.7% tighter)
   - Applied automatically
   - Improves LP relaxation

2. **force_all_skus_daily Parameter** ✅
   - Solves in 13s (10× faster)
   - Perfect for testing/baseline
   - Cost: $774,440 (no SKU optimization)

3. **Two-Phase Solve** ❌
   - Phase 1 (fixed): 13s
   - Phase 2 (binary): 157s
   - Total: 170s vs 83s single-phase
   - **Verdict: Slower than single-phase**

4. **Greedy SKU Reduction (Forcing)** ❌
   - 6 phases of progressive SKU forcing
   - Total: 328s
   - **Verdict: Much slower than single-phase**

5. **Greedy Big-M Relaxation (NEW)** ❌
   - Progressive Big-M tightening + warmstart
   - 3 phases + final: 262s total
   - Cost: $598,506 (similar to single-phase)
   - **Verdict: 3× slower than single-phase**

---

## Final Performance Comparison

### 4-Week Horizon, Real Data (Gfree Forecast.xlsm)

| Method | Time | Cost | Gap | Binary Vars | Warmstart | Winner? |
|--------|------|------|-----|-------------|-----------|---------|
| **force_all_skus_daily** | **13s** | $774,440 | 0.08% | 0 | N/A | ✅ Fastest |
| **Single-phase binary** | **83s** | **$597,869** | **1.48%** | 140 | No | ✅ **BEST** |
| Two-phase | 170s | $598,262 | 1.72% | 140 | Yes | ❌ 2× slower |
| Greedy forcing | 328s | $604,632 | 2.68% | varies | Partial | ❌ 4× slower |
| Greedy Big-M | 262s | $598,506 | 1.73% | 140 | Yes | ❌ 3× slower |

---

## What We Learned

### Why Multi-Phase Approaches Don't Help

**Problem:** Each phase with 50+ binary variables takes 50-70s to solve

**Math:**
- Single-phase: 1 solve × 83s = **83s total**
- Multi-phase: 5-6 solves × 60s + 1 final × 100s = **400s total**

**Conclusion:** Unless each intermediate phase is dramatically faster (<20s), multi-phase is always slower.

### When Force_All_SKUs Actually Helps

**The only time forcing reduces solve time:**
- ALL binary variables become fixed (0 binary vars)
- Solve time: 13s
- But cost increases 29% ($774k vs $598k)

**Partial forcing doesn't help because:**
- Still have 50+ binary vars → still slow (50-80s)
- Adding warmstart saves only 8%
- Overhead of multiple solves dominates

### Why Warmstart Has Limited Impact

**Measured:**
- Cold start: 78.4s
- With warmstart: 72.0s
- **Speedup: 1.09× (only 8%)**

**Reason:** APPSI HiGHS has aggressive presolve that often finds good incumbent quickly. Warmstart provides diminishing returns.

---

## Implementations Delivered

### ✅ Completed Features

1. **Tighter Big-M Constraint**
   - File: `src/optimization/unified_node_model.py:326-370`
   - Automatic (applied to all solves)
   - Improvement: 41.7% tighter bounds

2. **force_all_skus_daily Parameter**
   - File: `src/optimization/unified_node_model.py:97, 141, 617-670`
   - Usage: `UnifiedNodeModel(..., force_all_skus_daily=True)`
   - Benefit: 10× faster for testing

3. **force_sku_pattern Parameter**
   - File: `src/optimization/unified_node_model.py:98, 142, 636-661`
   - Usage: Partial SKU fixing for iterative approaches
   - Format: `{(node, product, date): True/False}`

4. **bigm_overrides Parameter**
   - File: `src/optimization/unified_node_model.py:99, 143, 2295-2297`
   - Usage: Variable-specific Big-M values
   - Format: `{(node, product, date): big_m_value}`

5. **solve_two_phase() Function**
   - File: `src/optimization/unified_node_model.py:2886-3090`
   - With working warmstart extraction using `pyomo.value()`
   - Result: 170s (slower than single-phase)

6. **solve_greedy_sku_reduction() Function**
   - File: `src/optimization/unified_node_model.py:3093-3304`
   - Progressive SKU forcing with cost tracking
   - Result: 328s (much slower than single-phase)

7. **solve_greedy_bigm_relaxation() Function**
   - File: `src/optimization/unified_node_model.py:3880-4137`
   - Progressive Big-M tightening + warmstart
   - Result: 262s (slower than single-phase)

### 📊 Test Files Created

1. `test_sku_performance_improvements.py` - Validates all features
2. `test_warmstart_between_phases.py` - Measures warmstart impact
3. `debug_phase_performance.md` - Investigation notes

---

## Recommendations

### For Development & Testing
**Use:** `force_all_skus_daily=True`
```python
model = UnifiedNodeModel(..., force_all_skus_daily=True)
result = model.solve(solver_name='appsi_highs')
# Solves in 13s, all SKUs produced
```

### For Production Optimization
**Use:** Single-phase binary SKU optimization
```python
model = UnifiedNodeModel(..., force_all_skus_daily=False)
result = model.solve(
    solver_name='appsi_highs',
    time_limit_seconds=180,
    mip_gap=0.03,
)
# Solves in 83s, optimal SKU selection, best cost
```

### Multi-Phase Approaches
**Not recommended** - All tested strategies are 2-4× slower than single-phase due to:
- Multiple full MIP solves required
- Each phase takes similar time (50-80s with 50+ binary vars)
- Warmstart provides only 8% speedup per phase
- Total time dominated by number of solves

---

## Why Single-Phase Is Best

**Key insight:** The problem has only 140 binary variables total (5 products × 28 days). This is **small enough** for modern MIP solvers to handle directly.

**Multi-phase would help if:**
- Problem had 1,000+ binary variables
- Each intermediate phase could be solved in <10s
- Warmstart provided 50%+ speedup
- **None of these are true for this problem**

**APPSI HiGHS is already optimized:**
- Aggressive presolve (60-70% problem reduction)
- Symmetry detection
- Parallel solving
- Good heuristics

**Conclusion:** The single-phase solve is already near-optimal. Adding complexity doesn't help.

---

## Performance Targets Achieved

| Goal | Target | Achieved | Status |
|------|--------|----------|--------|
| Understand slowdown | Root cause | ✅ MIP complexity | ✅ Complete |
| Optimize Big-M | Tighter bounds | ✅ 41.7% reduction | ✅ Complete |
| Fast testing mode | <30s | ✅ 13s | ✅ Complete |
| Multi-phase solve | Faster than single | ❌ 2-4× slower | ⚠️ Not beneficial |

---

## Code Additions

**Lines of code added:** ~1,500
- 3 new solver functions
- Variable-specific Big-M support
- Warmstart extraction fix
- Partial SKU forcing
- Test files and documentation

**Files modified:**
- `src/optimization/unified_node_model.py` (+1,200 lines)

**Files created:**
- `test_sku_performance_improvements.py`
- `test_warmstart_between_phases.py`
- `SKU_PERFORMANCE_INVESTIGATION.md`
- `SKU_PERFORMANCE_IMPROVEMENTS_COMPLETE.md`
- `SKU_PERFORMANCE_FINAL_REPORT.md` (this file)
- `debug_phase_performance.md`

---

## Final Recommendation

**For your use case (okay with longer solve times):**

Use **single-phase binary SKU optimization with APPSI HiGHS:**
- **Time:** 83 seconds
- **Cost:** $597,869 (best)
- **Gap:** 1.48% (excellent)
- **SKU reduction:** Automatic optimization

This is simpler, faster, and achieves better cost than any multi-phase approach.

The `force_all_skus_daily` parameter is valuable for fast development/testing (13s).

The multi-phase strategies are interesting academically but don't provide practical benefit for this problem size.

---

**Investigation Date:** 2025-10-19/20
**Total Investigation Time:** ~4 hours
**Conclusion:** Single-phase is optimal; complexity doesn't help small MIPs
