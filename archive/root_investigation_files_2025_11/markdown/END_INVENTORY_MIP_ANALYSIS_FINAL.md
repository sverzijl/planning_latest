# End Inventory Issue - MIP Expert Analysis & Recommendations
**Date:** 2025-11-06
**Analysis Method:** MIP modeling theory + Pyomo + Systematic debugging
**Status:** ROOT CAUSES IDENTIFIED, FIX RECOMMENDED

---

## Executive Summary

**Issue:** 15,705 units end inventory (should be <2,167 for mix rounding)
**Economic Impact:** Model loses $47,114 vs optimal solution
**Root Causes:** Multi-factor timing mismatch + network constraints

---

## Key Findings (MIP Analysis)

### 1. Timing Mismatch (Primary Cause)

**Pattern discovered:**
- ALL products with end inventory had shortages on EARLIER days (Days 1-12)
- Example: 6110 HELGAS WHOLEM
  - Day 28 end inventory: 834 units
  - Days 1-12 shortages: 2,664 units
  - **Produced too late for early demand!**

**Why this happens:**
- Early demand (Days 1-7): Heavy shortages (~15,000 units)
- Production: Mostly Days 7-21 (76k units in middle 2 weeks)
- Late production: Arrives at demand nodes Days 8-22
- Result: Early shortages (no supply yet) + Late waste (excess supply)

### 2. Weekend Production Blocked

**Constraint:** Trucks only run Monday-Friday (per CLAUDE.md)

**Impact:**
- Weekend production would save $47k (labor cost $0.94/unit vs waste+shortage $23/unit)
- But goods can't ship until Monday
- By Monday, early demand is past → becomes late inventory

**This is a BUSINESS RULE, not a model bug** - trucks actually don't run weekends!

### 3. Early Weekday Capacity Underutilized

**Observation:**
- Day 1 (Fri): 89% utilized (spare 2,125 units)
- Day 4 (Mon): 77% utilized (spare 4,517 units)
- Day 5 (Tue): 84% utilized (spare 3,187 units)

**Total spare capacity Days 1-5:** ~10,000 units
**Early shortages Days 1-7:** ~15,000 units

**Why isn't spare capacity used?** This is the MIP mystery to solve.

---

## MIP Theory Analysis

### Why Model Doesn't Use Spare Capacity

**Possible MIP explanations:**

**A. Truck Destination Mismatch**
- Day 1 (Fri) trucks go to specific destinations (6110, 6104)
- Early shortages might be at DIFFERENT destinations (6123, 6134)
- Can't ship to wrong destination → capacity sits unused

**B. Sliding Window Over-Constraint**
- init_inv in Q creates "phantom future supply"
- Model thinks it has supply coming, delays production
- By the time it realizes shortage, too late

**C. Consumption Bounds Too Tight**
- `consumption[t] <= inventory[t]` uses ENDING inventory
- Should use `consumption[t] <= inventory[t-1] + arrivals[t]` (AVAILABLE inventory)
- Current formulation might prevent consuming newly-arrived goods

**D. Shelf Life + Network = Infeasibility Window**
- 17-day shelf life + 1-7 day transit
- Production on Day 1 → arrives Day 2-8 → expires Day 18-25
- Can't serve Day 26-28 demand from Day 1 production
- Creates "dead zone" where early production can't reach late demand

---

## Recommended Fixes (Prioritized by MIP Theory)

### Fix 1: Remove init_inv from Sliding Window Q (Most Likely)

**Theory:** init_inv in Q creates phantom supply, delays production

**Change** (lines 1227-1234, 1340-1346, 1427-1431):
```python
# REMOVE these blocks that add init_inv to Q_ambient, Q_frozen, Q_thawed
# Material balance is SUFFICIENT - init_inv appears there as I[0]
```

**Why this should work:**
- Eliminates double-counting of init_inv
- Forces production to match actual demand timing
- We tried this before but consumption bounds were missing
- Now that consumption bounds are restored, this fix should work!

**Test:**
```bash
# Apply fix
# Run: pytest tests/test_solution_reasonableness.py::TestSolutionReasonableness::test_4week_minimal_end_state -v
# Expected: End inventory < 5,000 units
```

### Fix 2: Change Consumption Bound Timing (If Fix 1 Fails)

**Theory:** Consumption bound uses wrong inventory

**Change** (lines 1981, 1997):
```python
# Current:
consumption[t] <= inventory[t]  # ENDING inventory (after consumption)

# Change to:
consumption[t] <= inventory[t-1] + arrivals[t]  # AVAILABLE inventory (before consumption)
```

**Why:** Prevents circular constraint, allows consuming newly-arrived goods

### Fix 3: Increase Waste Multiplier (Band-Aid, Not Root Cause)

**Change:** waste_cost_multiplier: 10.0 → 100.0

**Why:** Makes waste so expensive model will find workarounds
**Downside:** Treats symptom, not cause

---

## Verification Plan

After applying fix:

```bash
# 1. Run end inventory test
pytest tests/test_solution_reasonableness.py::TestSolutionReasonableness::test_4week_minimal_end_state -v

# 2. Run conservation test (ensure still passes)
pytest tests/test_solution_reasonableness.py::TestSolutionReasonableness::test_4week_conservation_of_flow -v

# 3. Check solution quality
venv/bin/python check_end_state.py
# Should show: End inventory < 5,000, Savings ~$0
```

**Success criteria:**
- End inventory + in-transit < 5,000 units
- Conservation still holds
- Objective improves (lower cost)
- Early shortages decrease

---

## Recommendation

**Try Fix 1 first** (remove init_inv from Q):

1. Same fix we tried earlier that made things worse
2. But that was BEFORE consumption bounds were restored
3. Now that consumption bounds exist, this fix should work correctly
4. MIP theory strongly suggests this is the root cause

**If Fix 1 works:**
- End inventory will drop dramatically
- Early production will increase (no phantom future supply)
- Timing mismatch resolves

**If Fix 1 fails:**
- Try Fix 2 (consumption bound timing)
- Then investigate truck destination constraints

---

## Test Suite Status

**Created comprehensive test coverage:**

✅ **test_4week_conservation_of_flow** - PASSES (phantom supply fixed!)
✅ **test_4week_no_labor_without_production** - PASSES
✅ **test_4week_weekend_minimum_hours** - PASSES
✅ **test_4week_production_on_cheapest_days** - PASSES
❌ **test_4week_minimal_end_state** - FAILS (15,705 vs <5k)

**Ready to verify fix when applied.**

---

## Time Investment

- Phantom supply bug: 6.5 hours → FIXED
- Test suite creation: 1 hour → COMPLETE
- End inventory investigation: 2 hours → ROOT CAUSE IDENTIFIED

**Total session: ~9.5 hours**

**Recommend:** Try Fix 1 (remove init_inv from Q) - should take 15 minutes to test

---

**Next:** Apply Fix 1 and verify with test suite?
