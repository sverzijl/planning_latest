# Underproduction Bug: Systematic Debugging Report

**Date:** 2025-11-06
**Approach:** systematic-debugging skill (after 3+ failed fix attempts)
**Status:** ROOT CAUSE IDENTIFIED, FIX REQUIRES DEEPER INVESTIGATION

---

## Executive Summary

**Bug:** 4-week solve produces only 44k units in 5 days (need 307k units in 20+ days)

**Root Cause:** Coefficient scaling implementation (commit 8f2e4df) broke material balance

**Evidence:** Conservation of flow violated by 283k units (6× overconsumption)

**My Failed Attempts:** 3 fixes tried, none worked → Systematic debugging required

---

## Phase 1: Root Cause Investigation (COMPLETED)

### Timeline Analysis

| Date/Time | Commit | Production | Days | Status |
|-----------|--------|------------|------|--------|
| Nov 4 17:36 | Before 3a71197 | 966k | 65 | OVERPRODUCTION |
| Nov 5 16:52 | After 3a71197, before scaling | 276k | 20 | ✅ **WORKING** |
| Nov 5 17:25 | After scaling (8f2e4df) | 0 | 0 | ❌ **BROKEN** |
| Nov 6 11:19 | User's solve (75d4659) | 44k | 5 | ❌ **BROKEN** |

**Conclusion:** Coefficient scaling (8f2e4df) introduced the bug.

### Conservation Violation Confirmed

```
Test: test_4week_conservation_of_flow

Supply:    47,255 units (init_inv 30,823 + production 16,432)
Consumed: 330,237 units
PHANTOM:  282,982 units (598% overconsumption!)

Result: FAILED ❌
```

**This violates material balance equality constraint** - mathematically impossible unless:
1. Constraint doesn't exist (verified it DOES)
2. Constraint has wrong equation (investigating)
3. Extraction calculates consumed wrong (verified extraction is correct)

### Key Finding: Impossible Shipment Ratio

```
Test: test_hypothesis_arrivals.py

Production:  16,432 units
Shipments:  350,643 units
Ratio: 2,134% (shipping 21× more than produced!)

Result: PHYSICALLY IMPOSSIBLE ❌
```

**This proves either:**
- Shipment extraction is wrong (inflating numbers), OR
- My conservation test calculation is wrong (using wrong shipment data)

---

## Phase 2: What Changed in Scaling (8f2e4df)

### Changed:
1. ✅ `self.demand` ÷ 1000 (now in thousands)
2. ✅ `self.initial_inventory` ÷ 1000 (now in thousands)
3. ✅ Variable bounds added (0, X)
4. ✅ Constraint coefficients scaled
5. ✅ Objective costs × FLOW_SCALE_FACTOR
6. ✅ Extraction × FLOW_SCALE_FACTOR

### NOT Changed:
- Material balance equation structure
- Demand balance equation
- Shelf life constraints

### Verified Working:
- ✅ Extraction scaling correct (verified line-by-line)
- ✅ Coefficient range improved [0.05, 19.6]
- ✅ Waste cost scaled (fixed in commit 2977245)
- ✅ All cost components scaled correctly

---

## Phase 3: Hypotheses Tested

### ❌ Hypothesis A: Init_inv in Shelf Life Q (WRONG - made worse)
**Test:** Removed init_inv from Q
**Result:** Phantom increased 283k → 291k
**Conclusion:** False, reverted

### ❌ Hypothesis B: Demand Nodes Missing Material Balance (WRONG - already had it)
**Test:** Added demand nodes to constraint index
**Result:** No change, phantom still 283k
**Conclusion:** Nodes already had constraints

### ❌ Hypothesis C: Skip Conditions Wrong (WRONG - no effect)
**Test:** Fixed Skip logic
**Result:** No change, phantom still 283k
**Conclusion:** Logic was already correct

### ✅ Hypothesis D: Shipments/Arrivals Broken (CONFIRMED PARTIALLY)
**Test:** Queried in_transit variables
**Evidence:**
- 1,020 / 2,160 variables uninitialized (47% unused!)
- Active shipments: 174
- **Total shipped: 350k units (21× production!) ← IMPOSSIBLE**

**Conclusion:** Something wrong with shipments, but unclear what

---

## Phase 4: Current Status (BLOCKED)

### What I Know:
1. Bug introduced by scaling (8f2e4df)
2. Conservation violated by 283k units
3. Material balance constraints exist but don't prevent overconsumption
4. Extraction reports shipping 21× more than produced

### What I Don't Know:
1. **WHY** material balance allows 6× overconsumption
2. **WHERE** the 350k "phantom shipments" come from
3. **WHICH** specific scaling change broke it

### Systematic Debugging Says:
"After 3+ failed fixes, question the architecture"

**I've tried 3 fixes, all failed. Time to step back.**

---

## Recommended Path Forward

### Option A: Detailed Component Tracing (4-6 hours)

**Following root-cause-tracing skill:**

1. **Instrument EVERY variable in material balance**
   - Log prev_inv, arrivals, departures, consumption
   - Print actual numeric values post-solve
   - Identify which component is 1000× wrong

2. **Trace that component backward**
   - Where does it get its value?
   - Is it scaled correctly?
   - Does extraction match model?

3. **Fix at source**

**Confidence:** 70% we find it
**Time:** 4-6 hours
**Risk:** May find architectural issue requiring major changes

### Option B: Revert and Re-apply Incrementally (2-3 hours)

**Safest approach:**

1. **Revert scaling** (back to c1188f3 working state)
2. **Apply scaling in 5 small commits:**
   - Commit 1: Scale demand only
   - Commit 2: Scale initial_inventory only
   - Commit 3: Scale variable bounds
   - Commit 4: Scale constraints
   - Commit 5: Scale objective

3. **Test after EACH commit** with `test_solution_reasonableness.py`
4. **Identify which specific change breaks it**
5. **Fix that one thing**

**Confidence:** 95% we isolate the issue
**Time:** 2-3 hours
**Risk:** Low (incremental = safe)

### Option C: Ask for Expert Help

**Given:**
- 6+ hours invested
- 3+ failed fix attempts
- Violation of fundamental MIP constraint (impossible!)
- Systematic debugging says "question architecture"

**Consider:**
- Posting issue on Pyomo forums
- Reviewing with MIP expert colleague
- Pair programming session

---

## My Recommendation

**Option B: Revert and re-apply incrementally**

**Why:**
1. We KNOW c1188f3 works (276k production, 20 days)
2. We KNOW 8f2e4df breaks (44k production, 5 days)
3. Incremental commits will show EXACTLY which change breaks
4. Lower risk than continued random attempts
5. Follows systematic debugging: "Test minimally, one variable at a time"

**Steps:**
1. `git revert 8f2e4df 2977245` (revert both scaling commits)
2. Verify working state restored (276k production)
3. Re-apply scaling changes ONE AT A TIME
4. Test after each
5. When it breaks, we have the exact change that causes it

---

## Lessons Learned (Process Failures)

**What I did wrong:**
1. ❌ Didn't run solution reasonableness tests before pushing
2. ❌ Trusted "optimal" status without checking solution makes sense
3. ❌ Made 3+ fix attempts without understanding root cause
4. ❌ Claimed "production-ready" without multi-horizon validation

**What I should have done:**
1. ✅ Create `test_solution_reasonableness.py` FIRST
2. ✅ Run it BEFORE pushing
3. ✅ When it failed, use systematic debugging (not random fixes)
4. ✅ Apply scaling incrementally with tests at each step

**Process improvements implemented:**
- Created `test_solution_reasonableness.py` (catches this bug)
- Updated `MANDATORY_VERIFICATION_CHECKLIST.md` (requires testing)
- Created `verify_before_push.py` (automated gate)

---

## Decision Point

**I need your direction:**

**A.** Continue debugging (Option A - 4-6 hours, uncertain outcome)
**B.** Revert and re-apply incrementally (Option B - 2-3 hours, high confidence)
**C.** Something else?

I recommend **Option B** based on systematic debugging principles: "Test one variable at a time" and "After 3+ failures, question approach."

**What would you like me to do?**
