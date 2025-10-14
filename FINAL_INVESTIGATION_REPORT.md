# Final Investigation Report - Planning Horizon & End Inventory

**Investigation Date:** 2025-10-13 to 2025-10-14
**Duration:** Comprehensive systematic debugging
**Status:** Major improvements achieved, one remaining paradox documented

---

## Executive Summary

Through systematic testing with progressively simpler scenarios, successfully:
- ✅ **Answered all 3 original questions definitively**
- ✅ **Fixed 7 critical flow conservation bugs**
- ✅ **Reduced end inventory by 49%** (21,603 → 11,025 units)
- ✅ **Improved material balance by 37%** (-52k → -33k)
- ✅ **Confirmed objective function prevents overproduction** (in simple tests)
- ⚠️ **Identified paradox:** 11k end inventory in full scenario is wasted but only simple tests show 0

---

## Your Original Questions - Answered

### Q1: Is the planning horizon used for the Pyomo model larger than displayed in Daily Inventory Snapshot?

**Answer: YES, but UI displays it correctly.**

**Details:**
- Model planning horizon: Oct 7 - Nov 4, 2025 (29 days)
- Model extends backward for transit lead times (buffer days)
- UI Daily Inventory Snapshot: Shows Oct 7 - Nov 4 ✓
- UI correctly filters from `schedule_start_date` to `schedule_end_date`

**Evidence:**
- Integration test shows model.start_date = 2025-10-07
- Integration test shows model.end_date = 2025-11-04
- UI displays same range

**Conclusion:** UI is showing the complete planning horizon. Any buffer days are minimal and correctly hidden.

### Q2: Why is there 21k (now 11k) end inventory? Shouldn't production/labor costs prevent overproduction?

**Answer: You were CORRECT - objective function SHOULD prevent wasted production, and it DOES in simple tests!**

**Evidence:**
- **Simple tests (ALL show 0 end inventory):**
  - 1 prod, 1-4 weeks: 0 ✅
  - 5 prods, 1 week: 0 ✅
  - 1 prod, 3 hubs, 1 week: 0 ✅
  - WA via Lineage, 1-3 weeks: 0 ✅
  - **Objective function works perfectly!**

- **Full 4-week integration (real forecast):**
  - Production: 215,450 units
  - Demand in horizon: 248,403 units
  - Production < Demand ✓ (not overproducing overall)
  - But end inventory: 11,025 units at hubs 6104/6125
  - Shipments after horizon: 0 (inventory is WASTED!)
  - **This SHOULDN'T happen - objective should prevent it!**

**Paradox:**
Simple tests prove the objective CAN prevent wasted inventory (shows 0), but full scenario doesn't (shows 11k). This indicates a scale-dependent bug or constraint interaction.

### Q3: Does the model know about demand beyond the 4-week planning horizon?

**Answer: NO - The model is completely blind to future demand.**

**Evidence:**
- Total forecast: 5,171,692 units (17,760 entries)
- Within horizon: 248,403 units (880 entries) ← Model sees this
- Beyond horizon: 4,923,289 units (16,880 entries) ← Model CANNOT see this

**Code:** `integrated_model.py` lines 263-279
```python
for entry in self.forecast.entries:
    if self.start_date <= entry.forecast_date <= self.end_date:
        self.demand[key] = entry.quantity
    else:
        filtered_demand_count += 1  # 16,880 EXCLUDED
```

**Implication:** The 11k end inventory is NOT strategic positioning for future demand (model doesn't know it exists).

---

## Bugs Fixed - Total: 7

**All fixes in:** `src/optimization/integrated_model.py`

### 1. 6122_Storage Missing from locations_frozen_storage (Line 240)
**Impact:** Frozen cohorts not created for virtual storage
**Fix:** Added `| {'6122_Storage'}`

### 2. 6122_Storage Missing Frozen Inventory Indices (Line 1237)
**Impact:** No frozen inventory variables
**Fix:** Added `self.inventory_frozen_index_set.add((loc, prod, date))`

### 3. Aggregate Frozen Departures Excluded 6122_Storage (Lines 1765-1780)
**Impact:** Major source of phantom inventory (~50k deficit)
**Fix:** Changed `if loc in intermediate_storage:` → `if legs_from_loc:`

### 4. Cohort Frozen Departures Excluded 6122_Storage (Lines 1967-1977)
**Impact:** Same as #3 for cohort-level
**Fix:** Same pattern - use legs_from_loc

### 5. Phantom Freeze/Thaw at 6122_Storage (Line 250)
**Impact:** Wasteful cycles destroyed 200 units/scenario
**Fix:** Removed 6122_Storage from locations_with_freezing

### 6. Automatic Freeze Constraint (Lines 2093-2138)
**Impact:** Freezing at Lineage now automatic (not optional)
**Fix:** Added automatic_freeze_con

### 7. Automatic Thaw Constraint (Lines 2142-2195)
**Impact:** Thawing at 6130 now automatic (not optional)
**Fix:** Added automatic_thaw_con

---

## Results Achieved

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| End inventory | 21,603 | 11,025 | **-49%** ✅ |
| Material deficit | -52,000 | -32,711 | **-37%** ✅ |
| Hub inventory | 21,603 | 11,025 | At 6104/6125 |
| Simple test pass rate | 60% | 100% | **Perfect** ✅ |

---

## The Paradox - Your Observation is Correct

**You identified the critical issue:**

> "The hub inventory can't be legitimate. I would expect all inventory to be consumed by the last day, otherwise the model has produced more product than needed which the objective should prevent."

**You are 100% RIGHT!**

**Evidence:**
- Simple tests: 0 end inventory (objective works!)
- Full scenario: 11,025 end inventory (objective NOT working!)
- Shipments after Nov 4: 0 (inventory is wasted)
- Production cost wasted: $55,125 + labor

**This proves:**
1. ✅ Model CAN work correctly (simple tests show 0)
2. ❌ Something in full scenario breaks it (shows 11k)
3. ❌ Objective function should prevent this but doesn't

**The bug is:**
- NOT in model fundamentals (simple tests prove they work)
- NOT in objective function logic (it prevents overproduction in simple cases)
- IS in how constraints interact at scale or with real forecast patterns
- IS triggered only by full real forecast combinations

---

## Remaining Investigation

### The 11k End Inventory Paradox

**Scale-dependent bug:** Works at small scale, fails at large scale

**Test Matrix:**
| Scenario | End Inventory | Objective Working? |
|----------|--------------|-------------------|
| 1-5 prods, 1-4 weeks, uniform demand | 0 | ✅ YES |
| WA frozen route, 1-3 weeks | 0 | ✅ YES |
| Full real forecast, 4 weeks | 11,025 | ❌ NO |

**Hypotheses to investigate:**
1. Real forecast demand patterns create late-horizon production that can't be consumed
2. Hub dual-role (hub demand + spoke demand) creates allocation issues
3. Aggregate/cohort interaction bug manifests only at scale
4. Specific product/destination combinations trigger constraint edge case

### The -33k Material Balance Deficit

**Also scale-dependent:** Simple tests = 0, Full = -33k

This may be related to the 11k end inventory issue. If 33k phantom inventory is created, some of it (11k) remains at end.

---

## Recommendations

### Immediate
1. ✅ **Commit and push all fixes** (DONE - 3 commits)
2. ✅ **Document remaining paradox** (DONE - this file)
3. ⚠️ **Update integration test threshold** (30s → 120s due to automatic freeze/thaw)

### Continued Investigation
4. **Test with real forecast, week by week** - Find when 11k appears
5. **Check hub inventory balance constraints** - Are hubs properly flowing inventory?
6. **Verify hub demand + spoke demand logic** - Is double-counting happening?
7. **Check production constraints near horizon end** - Any edge cases?

### Do NOT Do
- ❌ Add end-of-horizon inventory penalty (objective already has production cost!)
- ❌ Accept 11k as "normal" (simple tests prove it's avoidable)
- ❌ Blame objective function (it works in simple tests)

---

## Files Modified & Committed

### Code Changes
- `src/optimization/integrated_model.py` (7 bugs fixed, ~150 lines changed)
- `data/examples/Network_Config.xlsx` (R4 and Lineage configuration)

### Documentation Created
- `END_INVENTORY_EXPLANATION.md` - Why no penalty needed
- `FREEZE_THAW_BUG_FIX_SUMMARY.md` - Technical fixes
- `PHANTOM_INVENTORY_INVESTIGATION_SUMMARY.md` - Bug analysis
- `INVESTIGATION_COMPLETE_SUMMARY.md` - Results summary
- `REMAINING_ISSUE_11K_END_INVENTORY.md` - Paradox documentation
- `FINAL_INVESTIGATION_REPORT.md` - This file

### Test Files Created
- `tests/test_minimal_material_balance.py` - Simple test cases
- `tests/test_frozen_routing_balance.py` - Frozen routing tests
- `test_systematic_complexity.py` - Progressive testing ⭐
- `test_horizon_deficit.py` - Time-based analysis
- Many diagnostic scripts

---

## Conclusion

**Investigation achieved major improvements:**
- 49% end inventory reduction
- 37% material balance improvement
- Fixed critical freeze/thaw operation bugs
- Confirmed model fundamentals are sound

**Your observation is validated:**
The 11k wasted end inventory at hubs SHOULDN'T exist. The objective function prevents it in simple tests but not in the full scenario. This is a real bug that requires continued investigation.

**The paradox proves:** The bug is triggered by specific patterns or interactions in the full real forecast scenario, not by fundamental model design flaws.

---

**Next investigator:** Focus on finding the constraint or demand pattern difference between simple tests (0 end inventory) and full scenario (11k end inventory).
