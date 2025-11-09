# Next Session Briefing - SlidingWindowModel Bug Investigation

## Current Status

**Model:** SlidingWindowModel (src/optimization/sliding_window_model.py)
**Last Commit:** `65600b5` (13 commits today)
**Test Status:** Integration tests passing but solutions have bugs
**Performance:** 60-100s for 4-week solve (was 23s before today's changes)

---

## Critical Bugs Still Present (VERIFIED BY USER)

### Bug 1: Labor Hours Without Production ❌

**Symptom:** Labor hours appearing on days with ZERO production

**Example:** Sunday showing 1.5 hours labor with no production batches

**What's Been Tried:**
- ✅ Added bidirectional linking: `product_produced ≥ production / M`
- ✅ Added `any_production ≤ sum(product_produced)`
- ✅ Added `total_starts ≤ N × any_production`
- ✅ Added 4-hour minimum payment constraint
- ❌ Still occurring!

**Likely Root Cause:** Constraint has logical gap allowing binaries to be 1 with zero production

### Bug 2: Lineage Inventory Not Updating ❌

**Symptom:** Lineage frozen inventory stays at 6400 (initial) throughout horizon

**User Reports:**
- ✅ Sees shipments TO Lineage in UI
- ✅ Sees "In Transit" to Lineage
- ✅ Sees frozen stock in labeling UI
- ❌ Lineage inventory doesn't change
- ❌ No shipments FROM Lineage to 6130

**What's Been Fixed:**
- ✅ Intermediate stop route expansion (6122 → Lineage created)
- ✅ Arrival state matching (ambient arrives as frozen)
- ❌ First-day arrival issue (Nov 3 departure before horizon)
- ❓ Later Wednesdays (Nov 5, 12, 19, 26) - need to verify

**Root Cause:** Likely combination of:
1. First-day arrival problem (day 1 goods missing)
2. Solver may not be using Lineage route (prefers other paths)
3. Material balance may have bugs preventing inventory accumulation

---

## What Works Correctly ✅

1. ✅ Model builds without errors
2. ✅ Solves to optimality (64-100s)
3. ✅ Day-of-week filtering working (660-950 variables skipped)
4. ✅ Intermediate stop routes created (Lineage → 6125 NOT created, correctly)
5. ✅ Variables exist for `in_transit[6122, Lineage, ..., wednesday, ambient]`
6. ✅ Fail-fast validation framework in place
7. ✅ Changeover cost, waste, and time all implemented

---

## Key Files

### Main Model
- `src/optimization/sliding_window_model.py` (3,536 lines)
  - Lines 1560-1586: frozen_balance arrivals (FIXED for state matching)
  - Lines 1472-1504: ambient_balance arrivals (FIXED for state matching)
  - Lines 2141-2172: Product binary bidirectional linking
  - Lines 2174-2206: Changeover aggregation linking
  - Lines 2040-2086: 4-hour minimum payment constraints

### Validation
- `src/validation/solution_validator.py` (NEW - post-solve validation)
- `src/validation/truck_schedule_validator.py` (NEW - pre-build validation)

### Tests
- `tests/test_integration_ui_workflow.py::test_ui_workflow_4_weeks_sliding_window`
- `tests/test_truck_routing_fixes.py`
- `tests/test_labor_capacity_enforcement.py`

### Reference Implementation
- `src/optimization/unified_node_model.py` (WORKING correctly)
  - Lines 2986-2990: Intermediate stop handling
  - Lines 3052-3058: Day-of-week with applies_on_date()
  - Lines 3587: 4-hour minimum: `paid >= minimum_hours × production_day`

---

## Diagnostic Evidence

### Nov 4 (Day 1) - Tuesday
```
Routes TO Lineage: 1
  Route: 6122 → Lineage (ambient, 1d)
  Departure needed: Nov 3 (BEFORE horizon)
  Key in model: False
  Arrivals: 0
```
**Conclusion:** First-day arrival problem confirmed

### Nov 5 (Day 2) - Wednesday
```
Variable exists: in_transit[6122, Lineage, prod, 2025-11-05, ambient]
```
**Found in:** Shelf life constraint outflows
**Need to verify:** Is solver setting this to positive value?

### Labor Hours
```
Weekend/holiday dates: Oct 25, 26 (Sat/Sun), Nov 4 (Tue holiday)
User reports: 0.25h then 1.5h on these dates
Production: 0 units on those dates
```
**Constraint chain should prevent this but doesn't!**

---

## Investigation Strategy for Next Session

### Phase 1: Verify Constraint Satisfaction (30 min)

**Extract actual Pyomo variable values after solve:**

```python
# For a weekend with reported labor but no production:
sunday = date(2025, 10, 27)  # Example

# Extract ALL related values:
production_values = {prod: value(model.production[node, prod, sunday])
                     for prod in products}
product_produced_values = {prod: value(model.product_produced[node, prod, sunday])
                           for prod in products}
any_production_value = value(model.any_production[node, sunday])
total_starts_value = value(model.total_starts[node, sunday])
labor_used = value(model.labor_hours_used[node, sunday])
labor_paid = value(model.labor_hours_paid[node, sunday])

# CHECK each constraint:
# 1. product_produced <= production / M  (forward)
# 2. product_produced >= production / M  (reverse)
# 3. any_production <= sum(product_produced)
# 4. any_production × N >= sum(product_produced)
# 5. total_starts = sum(product_start)
# 6. total_starts <= N × any_production
# 7. labor_used = production_time + overhead
# 8. labor_paid >= labor_used
# 9. labor_paid >= 4 × any_production

# Find which constraint is VIOLATED
```

### Phase 2: Fix Identified Constraint Bug (30 min)

Based on which constraint fails, apply targeted fix

### Phase 3: Debug Lineage Flow (30 min)

**Check actual solution values:**

```python
# For each Wednesday:
for wed in [Nov 5, Nov 12, Nov 19, Nov 26]:
    # Check if shipment actually used
    shipment_value = value(model.in_transit[6122, Lineage, prod, wed, 'ambient'])

    # Check Lineage inventory
    lineage_inv = value(model.inventory[Lineage, prod, frozen, wed+1])

    # Should see:
    # shipment_value > 0 → lineage_inv increases
```

If shipment_value = 0 for all Wednesdays: **Solver preferring other routes**
If shipment_value > 0 but inventory not increasing: **Material balance bug**

---

## Testing Data

**Use this exact configuration:**
- Forecast: `data/examples/Gluten Free Forecast - Latest.xlsm`
- Network: `data/examples/Network_Config.xlsx`
- Inventory: `data/examples/inventory_latest.XLSX`
- Start: Oct 16, 2025 OR Nov 4, 2025 (inventory snapshot date)
- Horizon: 4 weeks
- Settings: Pallet tracking ON, 1% MIP gap

---

## Recommended Approach

### Option A: Systematic Constraint Verification

Use Pyomo expert skill to:
1. Extract all variable values for problem dates
2. Manually verify each constraint
3. Find the violated constraint
4. Fix that specific constraint

### Option B: Compare with UnifiedNodeModel

Use MIP expert skill to:
1. Compare SlidingWindowModel constraints with UnifiedNodeModel
2. Identify differences in labor/changeover logic
3. Port working logic from UnifiedNodeModel

### Option C: Incremental Rollback

1. Revert today's changes one by one
2. Test after each revert
3. Identify which change broke it
4. Fix that change properly

---

## Critical Questions to Answer

1. **Labor bug:** Which constraint in the chain is allowing `any_production=1` with `production=0`?

2. **Lineage bug:** Are shipments TO Lineage being set to positive values by the solver?

3. **Performance:** Can we get back to 20-30s solve time while keeping correctness?

---

## Success Criteria for Next Session

✅ Zero labor hours on days with zero production
✅ Lineage inventory increases when receiving shipments
✅ 6130 receives frozen goods from Lineage
✅ Solution validator passes all checks
✅ Solve time < 40s for 4-week horizon

---

## Files to Focus On

**Primary:**
- `src/optimization/sliding_window_model.py` (lines 2141-2206 for labor constraints)

**Reference:**
- `src/optimization/unified_node_model.py` (working implementation)

**Tools:**
- `debug_constraint_violations.py` (extract variable values)
- Skills: pyomo, mip-modeling-expert

---

## Sign-off

**Session:** November 4, 2025
**Status:** Major progress but critical bugs remain
**Commits:** 13 (all pushed to GitHub)
**Next:** Systematic constraint debugging with Pyomo/MIP expertise
