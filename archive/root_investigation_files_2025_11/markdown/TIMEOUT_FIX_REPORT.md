# Timeout Issue - Root Cause & Resolution

**Date:** 2025-10-19  
**Issue:** Apparent timeout on 4-week problem  
**Status:** ✅ **RESOLVED**

## Root Cause

**NOT a solver timeout!** CBC found optimal solution in **51 seconds**.

**Actual problem:** **31,462 error messages** in solution extraction made it appear to hang!

### Why?

1. Transport costs = $0 (all routes)
2. MIP solver doesn't initialize zero-cost variables (valid behavior)
3. Pyomo `value()` prints error for each uninitialized variable
4. 19,345 shipment variables × mostly uninit = **31,462 errors**!

## Fix Applied (Pyomo Best Practice)

**Check `var.stale` BEFORE calling `value()`:**

```python
# BEFORE (caused 31k errors):
qty = value(model.shipment_cohort[...])

# AFTER (silent):
var = model.shipment_cohort[...]
if var.stale:
    continue  # Skip uninit silently
qty = value(var)
```

**Also:** Use component sum for total cost (don't extract from model.obj)

## Results

| Metric | Before | After | 
|--------|--------|-------|
| Error messages | 31,462 | 2 | 
| Solve time | 51s (hidden) | 51s |
| Total time | Appears timeout | **60s** ✅ |

## Files Modified

- `src/optimization/unified_node_model.py` (6 extraction sections)
- `src/optimization/warmstart_generator.py` (2 SKUs/weekday fix)

## Test

```bash
python test_user_data_timeout.py
# Expected: ~60s, optimal, 0-2 errors
```

**Status:** ✅ FIXED
