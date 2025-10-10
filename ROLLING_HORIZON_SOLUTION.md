# Rolling Horizon Solution Summary

## Executive Summary

**Problem Solved**: 41% infeasibility rate with 7-day windows eliminated entirely by doubling window size to 14 days.

**Root Cause**: Myopic planning - 7-day windows couldn't "see" far enough ahead to make inventory buildup decisions.

**Solution**: 14-day windows with 7-day overlap (uniform daily granularity).

## Results Comparison

### Configuration A: 7-Day Windows (BASELINE)
```
Window size: 7 days
Overlap: 3 days
Committed: 4 days per window
```

**Results:**
- Windows: 51
- ✅ Feasible: 30 (59%)
- ❌ Infeasible: 21 (41%)
- Avg time: 0.75s/window
- Total time: 38s

### Configuration B: 14-Day Windows (SOLUTION)
```
Window size: 14 days
Overlap: 7 days
Committed: 7 days per window
```

**Results:**
- Windows: 30
- ✅ Feasible: 30 (100%) ← **ALL FEASIBLE!**
- ❌ Infeasible: 0 (0%)
- Avg time: 3.80s/window
- Total time: 114s
- Total cost: $6,896,522

**Improvement: 21 fewer infeasible windows (100% reduction in infeasibility)**

## Why This Works

### The Problem with 7-Day Windows

**Window 2 (Jun 6-12, committed Jun 6-9):**
- Optimizer sees: Jun 6-12 demand
- Cannot see: Jun 10+ demand surge
- Decision: Minimize cost → zero ending inventory at Jun 9
- Result: Ships everything just-in-time

**Window 3 (Jun 10-16, committed Jun 10-13):**
- Starts with: Zero inventory from Window 2
- Must satisfy: Jun 10-13 demand immediately
- Problem: Cannot produce enough in window due to:
  - D-1 production lead time (needs Jun 9 production)
  - Limited capacity in short window
  - Zero starting inventory
- Result: **INFEASIBLE**

### The Solution with 14-Day Windows

**Window 1 (Jun 2-15, committed Jun 2-8):**
- Optimizer sees: Full 2 weeks of demand (Jun 2-15)
- Can see: Jun 10+ demand spike coming
- Decision: Build inventory in Jun 2-8 to prepare for Jun 10+
- Result: Ends with inventory buffer at Jun 8

**Window 2 (Jun 9-22, committed Jun 9-15):**
- Starts with: Inventory buffer from Window 1
- Can satisfy: Jun 9-15 demand using starting inventory + new production
- Result: **FEASIBLE**

## Trade-offs

### Pros ✅
1. **Zero infeasibility** - all 30 windows solve successfully
2. **Proven capacity** - confirms there IS enough capacity
3. **No code changes** - just configuration parameter
4. **Better decisions** - solver makes inventory buildup when needed
5. **Fewer windows** - 30 vs 51 (simpler to manage)

### Cons ❌
1. **Longer per-window time** - 3.80s vs 0.75s (5x slower)
2. **Longer total time** - 114s vs 38s (3x slower)
3. **More memory per window** - 14 days vs 7 days of variables

## Recommendation

**✅ ADOPT 14-day windows as the standard configuration**

**Rationale:**
- 114s total time is still **highly acceptable** for a 29-week planning problem
- 100% feasibility vs 59% feasibility is **mission-critical**
- No implementation risk - zero code changes
- Can still see per-window progress (user requirement)

## Future Enhancements (Optional)

If 14-day window solve times become problematic (>10s per window), consider:

### Phase 2: Hierarchical Granularity (User's Original Proposal)
- Week 1 (days 1-7): Daily, full constraints → COMMITTED
- Week 2 (days 8-14): 3-day buckets, relaxed constraints → LOOKAHEAD

**Expected Benefits:**
- Reduce to ~11 time periods vs 14 days
- Maintain lookahead visibility
- Faster per-window solve time

**Estimated Effort:** 2-3 days implementation
**Risk:** Medium (requires model changes)

**Current Recommendation:** Not needed - 14-day daily granularity performs well enough.

## Implementation

### Update Default Configuration

File: `src/optimization/rolling_horizon_solver.py:91-92`

```python
# BEFORE:
window_size_days: int = 28,
overlap_days: int = 7,

# AFTER:
window_size_days: int = 14,  # Changed from 28 to 14
overlap_days: int = 7,       # Kept at 7
```

### Test Scripts

- **Baseline (7-day)**: `test_rolling_horizon_29weeks_7day.py`
- **Solution (14-day)**: `test_rolling_horizon_14day.py`
- **Output**: `rolling_horizon_14day_output.txt`

## Conclusion

The 14-day window configuration **completely solves** the infeasibility problem with minimal trade-offs. The 3x increase in total solve time (38s → 114s) is acceptable for the benefit of 100% feasibility.

**Your intuition was correct** - the solver needed lookahead visibility to make inventory decisions. The simpler uniform daily granularity works perfectly without needing hierarchical bucketing (though that remains a valid future optimization if needed).

---

**Status**: ✅ **SOLVED**
**Next Step**: Update default rolling horizon configuration to 14-day windows
**Date**: 2025-10-06
