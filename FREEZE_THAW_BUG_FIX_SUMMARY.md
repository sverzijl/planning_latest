# Freeze/Thaw State Transition Bug Fix Summary

**Date:** 2025-10-13
**Issue:** Phantom inventory in frozen routing through Lineage (~50,000 unit material balance deficit)

## Investigation Approach

Used systematic testing with progressively simpler scenarios to isolate the bug:

1. ✅ 1 prod, direct ambient route: Balance = 0
2. ✅ 5 prods, direct ambient: Balance = 0
3. ✅ 1 prod, 4 weeks, ambient: Balance = 0
4. ✅ 1 prod, 3 hubs, ambient: Balance = 0
5. ❌ 1 prod, WA via Lineage frozen: Balance = -700 ← **Bug isolated here!**
6. ❌ 5 prods, all dests, 4 weeks: Balance = -57,300

**Conclusion:** Phantom inventory ONLY occurs with Lineage → 6130 (WA) frozen route.

## Root Cause Identified

**Problem:** 6122_Storage ships frozen inventory to Lineage, but frozen inventory wasn't being tracked or constrained at 6122_Storage.

**Missing Configuration:**
1. 6122_Storage not in `locations_frozen_storage` set
2. Frozen inventory indices not created for 6122_Storage
3. Frozen cohorts not created for 6122_Storage
4. Frozen departures not calculated for 6122_Storage (excluded by `if loc in intermediate_storage`)

**Result:** Frozen shipments from 6122_Storage → Lineage had no inventory source → phantom inventory!

## Fixes Applied

**File:** `src/optimization/integrated_model.py`

### Fix 1: Add 6122_Storage to locations_frozen_storage (Line 240)
```python
self.locations_frozen_storage: Set[str] = {
    loc.id for loc in self.locations
    if loc.storage_mode in [StorageMode.FROZEN, StorageMode.BOTH]
} | {'6122_Storage'}  # Virtual storage also supports frozen inventory
```

**Impact:** Enables frozen cohort creation for 6122_Storage

### Fix 2: Add 6122_Storage to locations_with_freezing (Line 250)
```python
self.locations_with_freezing: Set[str] = {
    loc.id for loc in self.locations
    if loc.storage_mode == StorageMode.BOTH
} | {'6122_Storage'}  # Virtual storage also supports freeze/thaw operations
```

**Impact:** Enables freeze operations at 6122_Storage (ambient → frozen)

### Fix 3: Add frozen inventory indices for 6122_Storage (Line 1237)
```python
if loc == '6122_Storage':
    # 6122_Storage supports BOTH frozen and ambient (via freeze operations)
    for prod in self.products:
        for date in sorted_dates:
            self.inventory_ambient_index_set.add((loc, prod, date))
            self.inventory_frozen_index_set.add((loc, prod, date))  # Add frozen too!
```

**Impact:** Creates frozen inventory variables for 6122_Storage

### Fix 4: Fix aggregate frozen outflows (Lines 1763-1780)
```python
# Before: if loc in self.intermediate_storage
# After: legs_from_loc = self.legs_from_location.get(loc, [])
#        if legs_from_loc:
```

**Impact:** Frozen departures now calculated for 6122_Storage, not just Lineage

### Fix 5: Fix cohort frozen departures (Lines 1967-1977)
```python
# Already had this fix from earlier work
# Uses legs_from_loc pattern instead of intermediate_storage check
```

**Impact:** Cohort frozen departures calculated for all locations with outbound legs

## How Freeze/Thaw State Transitions Work

### Correct Flow for Frozen Routing (6122 → Lineage → 6130):

**Day 1:**
1. Production → 6122_Storage ambient inventory
2. `model.freeze` → converts ambient to frozen at 6122_Storage
   - Subtracts from ambient (via `freeze_output` in ambient balance, line 2077)
   - Adds to frozen (via `freeze_input` in frozen balance, line 1993)
3. Frozen shipment departs from 6122_Storage frozen inventory
   - Subtracts via `frozen_departures` (line 1976 cohort, line 1780 aggregate)

**Day 2:**
4. Frozen shipment arrives at Lineage frozen inventory
   - Adds via `frozen_arrivals` (line 1963 cohort, line 1757 aggregate)

**Day 3:**
5. Frozen shipment departs from Lineage to 6130
   - Subtracts via `frozen_departures` (Lineage is in intermediate_storage)

**Day 5:**
6. Frozen shipment arrives at 6130
   - Arrives as AMBIENT (thaws on arrival, line 742)
   - `model.thaw` operation at 6130 (resets shelf life to 14 days)
   - Satisfies demand from ambient inventory

## Test Results After Fixes

| Test | Before | After | Improvement |
|------|--------|-------|-------------|
| Test 1-4 (Ambient only) | 0 | 0 | ✅ Still perfect |
| Test 5 (WA, 1 week) | -700 | -400 | 43% better |
| Test 6 (Full, 4 weeks) | -57,300 | -51,200 | 11% better |
| 4-week integration | -52,000 | -49,500 | 5% better |

**Status:** PARTIAL FIX - Significant improvement but ~50k deficit remains

## Remaining Issues

The material balance deficit reduced from -57,300 to -51,200 (11% improvement), but a -51k deficit persists. Possible remaining causes:

1. **Aggregate vs cohort constraint interaction** - Both constraint types may have conflicting flow conservation
2. **Thaw operations at 6130** - May not be properly linked to arrivals
3. **Additional missing departures** - Other locations may need similar fixes
4. **Initial inventory edge cases** - First day inventory handling may have issues

## Next Steps

1. Investigate if ambient departures have the same `intermediate_storage` bug
2. Check thaw operations at 6130 (WA thawing destination)
3. Add explicit material balance validation constraint
4. Consider if aggregate constraints are redundant with cohort constraints

## Files Modified

- `src/optimization/integrated_model.py` (5 locations, lines 240, 250, 1237, 1765-1780, 1967-1977)

## Diagnostic Scripts Created

- `test_systematic_complexity.py` - Progressive complexity testing
- `diagnose_lineage_constraints.py` - Lineage-specific flow analysis
- `test_ultra_simple_real_data.py` - Minimal real data test
- `tests/test_minimal_material_balance.py` - Simple test cases
- `tests/test_frozen_routing_balance.py` - Frozen routing tests
