# Infeasibility Investigation - Session Handoff

**Date:** 2025-11-02
**Session Duration:** ~8 hours
**Status:** ROOT CAUSE IDENTIFIED, FIX NEEDED

---

## Executive Summary

**Original Problem:** ✅ **SOLVED**
- Excess end-of-horizon inventory due to asymmetric constraint scope
- Pipeline inventory tracking refactor successfully eliminated this issue
- End-of-horizon inventory: **0 units** (verified)

**New Problem Discovered:** ❌ **BLOCKING**
- Model is **infeasible** when initial inventory is properly loaded with alias resolver
- Works WITHOUT initial inventory (takes shortages)
- Fails WITH initial inventory (presolve infeasible)

---

## What Works vs What Fails

### ✅ Works (OPTIMAL)

| Scenario | Inventory | Product Matching | Result |
|----------|-----------|------------------|--------|
| No initial inventory | None | N/A | OPTIMAL |
| Initial inventory WITHOUT alias resolver | Present but not matched | Product IDs don't match | OPTIMAL (treats as zero inv) |
| Script with zero inventory | Zero | Matched | OPTIMAL |

### ❌ Fails (INFEASIBLE)

| Scenario | Inventory | Product Matching | Result |
|----------|-----------|------------------|--------|
| Initial inventory WITH alias resolver | 49,581 units, 34 entries | Products matched (5/5) | INFEASIBLE at presolve |
| UI with Oct 16 snapshot | 49,581 units | Products matched (5/5) | INFEASIBLE at presolve |

---

## Root Cause Analysis

### The Discovery Process

1. **Initial confusion:** All diagnostic scripts showed OPTIMAL
   - **Why:** Scripts used wrong product IDs, so inventory wasn't actually loaded
   - **User insight:** "Your diagnostics haven't been using initial inventory correctly"

2. **Breakthrough:** Added alias resolver to simulation script
   - **Result:** Now replicates infeasibility!
   - **Script:** `EXACT_UI_WORKFLOW_SIMULATION.py` with alias resolver

3. **Constraint analysis:** HiGHS reports "Presolve: Infeasible"
   - Infeasible constraints identified:
     - `ambient_shelf_life_con` (multiple)
     - `product_binary_linking_con` (multiple)
   - All for product: 'WONDER GFREE WHOLEM 500G'

### The Architectural Issue

**Hypothesis:** Shelf life constraints + initial inventory create over-constraint

**Evidence from LP file:**
```
ambient_shelf_life_con['6122',HELGAS GFREE MIXED GRAIN 500G,2025-10-17]
inventory[t] - (2240.0 + production + ... - departures) <= 0
```

The `2240.0` is initial inventory being added to inflows in the shelf life constraint.

**Potential conflict:**
1. **Material balance** on day 1: `inventory[day1] = initial_inv + production - departures - demand`
2. **Shelf life** on day 1: `inventory[day1] <= initial_inv + production - departures`
3. **Constraint interaction:** May be creating contradiction

---

## Configuration That Triggers Issue

**Files:**
- Forecast: `Gluten Free Forecast - Latest.xlsm`
- Network: `Network_Config.xlsx`
- Inventory: `inventory_latest.XLSX`

**Settings:**
- Inventory snapshot date: 2025-10-16
- Planning horizon: 2025-10-17 to 2025-11-13 (4 weeks)
- allow_shortages: True
- use_pallet_tracking: True or False (fails either way)
- use_truck_pallet_tracking: True or False (fails either way)

**Critical:** Must use `ProductAliasResolver` from Network_Config.xlsx to match product IDs between inventory and forecast.

---

## Key Findings

### 1. Product ID/Name Mismatch
- **Inventory file has:** Numeric product IDs ('168846', '184223', etc.)
- **Forecast file has:** Product names ('HELGAS GFREE MIXED GRAIN 500G', etc.)
- **Alias resolver:** Converts numeric IDs to canonical names
- **Without alias resolver:** Products don't match → inventory ignored → model solves (with shortages)
- **With alias resolver:** Products match → inventory used → **INFEASIBLE**

### 2. Initial Inventory in Shelf Life Constraints
**Current implementation** (lines 628-633):
```python
# Include initial inventory if planning start is in window
first_date = min(model.dates)
if first_date in window_dates:
    Q_ambient += self.initial_inventory.get((node_id, prod, 'ambient'), 0)
```

**Also in:** Frozen shelf life (line 711) and Thawed shelf life (line 759)

**Hypothesis:** This may cause double-accounting or over-constraint when combined with material balance.

### 3. HiGHS Presolve Detection
- Fails at **presolve** (before branch-and-bound)
- Indicates **structural infeasibility**, not numeric issues
- Likely: Contradictory constraints or impossible bounds

---

## Diagnostic Tools Created

All tools are committed and pushed to GitHub:

1. **`EXACT_UI_WORKFLOW_SIMULATION.py`** ⭐ **PRIMARY REPRODUCER**
   - Replicates exact UI workflow
   - NOW SHOWS INFEASIBLE (with alias resolver fix)
   - Use this to test fixes

2. **`ANALYZE_INFEASIBILITY_WITH_INVENTORY.py`**
   - Runs Pyomo infeasibility analysis
   - Shows which constraints fail
   - Logs initial inventory lookups

3. **`FIND_INFEASIBILITY.py`**
   - Windows-compatible diagnostic
   - Writes infeasibility_report.txt

4. **`CHECK_DEMAND_FILTERING.py`**
   - Verifies demand is filtered to planning horizon
   - Confirmed: working correctly

5. **`CHECK_PALLET_BOUNDS.py`**
   - Checks if inventory exceeds pallet storage limits
   - Confirmed: all within bounds

6. **Comprehensive logging added to:**
   - `src/workflows/base_workflow.py` - Shows all workflow parameters
   - `src/optimization/base_model.py` - Shows APPSI solver results
   - `src/optimization/sliding_window_model.py` - Shows initial inventory lookups

---

## What to Investigate Next

### Priority 1: Shelf Life + Initial Inventory Interaction

**Question:** Why does including initial inventory in shelf life constraints cause infeasibility?

**Investigation steps:**
1. Review shelf life constraint formula (line 691):
   ```python
   inventory[t] <= Q_ambient - O_ambient
   ```
   Where `Q_ambient` includes initial inventory

2. Review material balance on day 1 (line 874):
   ```python
   prev_inv = self.initial_inventory.get((node_id, prod, 'ambient'), 0)
   ```

3. **Check for double-accounting:**
   - Is initial inventory counted in BOTH shelf life inflows AND material balance prev_inv?
   - If yes, this creates contradiction

4. **Test hypothesis:**
   - Remove initial inventory from shelf life constraints (lines 628-633, 711, 759)
   - Keep it ONLY in material balance
   - See if model becomes feasible

### Priority 2: First-Day Arrivals

**Question:** Are first-day arrivals being handled correctly with initial inventory?

**Check:**
- Line 880: `if (departure_date := t - timedelta(days=route.transit_days)) in model.dates`
- On day 1 (Oct 17), departure Oct 16 is NOT in model.dates
- Result: First-day arrivals = 0 (correct for planning model)
- But: If inventory includes "in-transit" goods, they should arrive on day 1

### Priority 3: Constraint Redundancy

**Question:** Do shelf life and material balance constraints conflict?

**Consider:**
- Shelf life says: `inventory[t] <= sum(inflows) - sum(outflows)`
- Material balance says: `inventory[t] = prev_inv + inflows - outflows`
- With initial inventory in BOTH, these might contradict

---

## Commits Made This Session

Pipeline refactoring (original goal):
- `7f14ac1` - Merge pipeline inventory tracking refactor (11 commits)
- `a8b8e04` - Remove pre-horizon in-transit variables
- `ceb0c0c` - Use inventory snapshot date for planning start
- `1a30da6` - Convert initial inventory to 3-tuple format
- Multiple diagnostic and logging commits

**Current HEAD:** `f2c945c` (with comprehensive diagnostics)

---

## Files to Review

**Model implementation:**
- `src/optimization/sliding_window_model.py` - Lines 620-700 (shelf life constraints)
- `src/optimization/sliding_window_model.py` - Lines 855-910 (material balance)

**Test that reproduces issue:**
- `EXACT_UI_WORKFLOW_SIMULATION.py` - Run this to see infeasibility

**LP file for inspection:**
- `workflow_model_debug.lp` (91,819 lines) - The exact infeasible model

---

## Current State of Code

**On GitHub (commit f2c945c):**
- Pipeline refactoring: ✅ Complete
- End-of-horizon fix: ✅ Working (0 units)
- Initial inventory: ❌ Causes infeasibility when properly loaded
- Git commit hash: ✅ In all error messages
- Windows compatibility: ✅ No emojis in output
- Comprehensive diagnostics: ✅ All tools working

---

## Recommended Next Steps

### Immediate (Next Session)

1. **Remove initial inventory from shelf life inflows** (architectural fix)
   - Lines to modify: 628-633, 711, 759
   - Hypothesis: Initial inventory should ONLY be in material balance, not shelf life
   - Test with `EXACT_UI_WORKFLOW_SIMULATION.py`

2. **If still infeasible:** Investigate material balance on day 1
   - Check if prev_inv calculation is correct
   - Verify no double-accounting between constraints

3. **If still infeasible:** Check if production/inventory variables for initial inventory products are being created correctly

### Medium Term

- Refactor shelf life constraints to be clearer about initial vs new inventory
- Add architectural tests for initial inventory scenarios
- Document shelf life constraint semantics

### Long Term

- Consider if sliding window approach is compatible with initial inventory
- May need different constraint formulation when starting with inventory
- Might need "first day special case" handling

---

## Open Questions

1. **Why does the cohort model (UnifiedNodeModel) work with initial inventory but sliding window doesn't?**
   - Answer might reveal the architectural difference needed

2. **Should initial inventory be in shelf life window at all?**
   - Material balance handles it as starting state
   - Shelf life should track age of NEW inflows
   - Including initial inventory in shelf life might be conceptually wrong

3. **Is there a bug in how window_dates are calculated on early days?**
   - Day 1 window: only [Oct 17]
   - Day 2 window: [Oct 17, Oct 18]
   - etc.
   - Is initial inventory being added to all these windows correctly?

---

## Prompt for Next Session

```
I need to fix the infeasibility issue in the SlidingWindowModel when initial inventory is used with the alias resolver.

CONTEXT:
- Pipeline inventory tracking refactor works perfectly for the original problem (zero end-of-horizon inventory)
- But introduced infeasibility when initial inventory is properly loaded
- Can reproduce with: python EXACT_UI_WORKFLOW_SIMULATION.py
- Model fails at HiGHS presolve (structural infeasibility)

FILES TO INVESTIGATE:
- src/optimization/sliding_window_model.py lines 620-700 (shelf life constraints)
- src/optimization/sliding_window_model.py lines 855-910 (material balance)

HYPOTHESIS:
Initial inventory is being added to shelf life constraint inflows (lines 628-633, 711, 759)
AND being used as prev_inv in material balance (line 874).
This may cause double-accounting or over-constraint.

FIRST FIX TO TRY:
Remove initial inventory from shelf life inflows - it should ONLY be in material balance as starting state.
Shelf life windows should track NEW inflows (production, arrivals, thaw), not starting inventory.

TEST WITH:
python EXACT_UI_WORKFLOW_SIMULATION.py  # Should show INFEASIBLE before fix, OPTIMAL after

GOAL:
Make SlidingWindowModel work with initial inventory while maintaining zero end-of-horizon inventory.
```

---

## Files Created This Session

**Diagnostic scripts:**
- EXACT_UI_WORKFLOW_SIMULATION.py ⭐ Primary reproducer
- ANALYZE_INFEASIBILITY_WITH_INVENTORY.py
- FIND_INFEASIBILITY.py
- CHECK_DEMAND_FILTERING.py
- CHECK_PALLET_BOUNDS.py
- EXPORT_MODEL_WINDOWS.py
- And ~10 other test scripts

**Outputs:**
- workflow_model_debug.lp (91K lines - the infeasible model)
- infeasibility_report.txt
- diagnostic_output_windows.json

**All committed to GitHub for reference.**
