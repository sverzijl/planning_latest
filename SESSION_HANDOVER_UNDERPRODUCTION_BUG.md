# Session Handover: Underproduction Bug Investigation

**Date:** 2025-11-06
**Status:** UNSOLVED after 10+ hours, 5 failed fix attempts
**Recommendation:** Fresh session with systematic approach

---

## Problem Statement

**4-week optimization solve produces only 44,000 units in 5 days when it should produce ~307,000 units across 20+ days.**

**Symptoms:**
- Production: 44,000 units (14% of needed)
- Production days: 5 (should be 20+)
- Fill rate: 98-99% (impossible with only 74k supply!)
- Objective: Unexpectedly low

**Evidence of Bug:**
- Total demand: 336,982 units
- Initial inventory: 30,823 units
- Production: 7,000-44,000 units (varies by test)
- **Consumed: 330,000+ units (from 47k supply!) ← IMPOSSIBLE**
- Phantom supply: ~283,000 units (6× overconsumption)

---

## Timeline - When Did Bug Start?

| Date/Time | Commit | Production | Days | Status |
|-----------|--------|------------|------|--------|
| Nov 4 17:36 | Before 3a71197 | 966k | 65 | OVERPRODUCTION |
| **Nov 5 16:52** | **After 3a71197** | **276k** | **20** | **✅ WORKING** |
| Nov 5 17:25 | After 8f2e4df (scaling) | 0-44k | 0-5 | ❌ BROKEN |
| Nov 6 (current) | After reverting scaling | 7-16k | varies | ❌ STILL BROKEN |

**Critical Insight:** Reverting coefficient scaling did NOT fix the bug!

**This means:**
1. Bug exists at commit 3a71197 (remove consumption bounds)
2. User's Nov 5 16:52 solve with 276k production used DIFFERENT code or data
3. Current code at 3a71197 (after reverting) shows 7-16k production

**Possible explanations:**
- User's 16:52 solve used different data files
- User's 16:52 solve used different parameters
- Git history is confusing us about what commit was actually used
- Test harness uses different setup than UI

---

## Conservation Violation Confirmed

**Test:** `tests/test_solution_reasonableness.py::test_4week_conservation_of_flow`

```
Result: FAILED

Available supply:    47,255 units (30,823 init + 16,432 prod)
Total consumed:     330,237 units
PHANTOM SUPPLY:     282,982 units

Violation: Consuming 7× more than available!
```

**This violates fundamental material balance** - should be mathematically impossible.

**Per-node analysis shows:**
- ALL 9 demand nodes have negative balances
- Example: Node 6104 consumes 59k with only 9.8k supply
- Even accounting for shipments, balances are massively negative

---

## Test Infrastructure Created (What Works)

✅ **`tests/test_solution_reasonableness.py`**
- `test_4week_production_meets_demand` - Checks production ≈ 306k units
- `test_4week_conservation_of_flow` - Checks consumed ≤ available
- `test_4week_cost_components_reasonable` - Checks cost magnitudes
- **All currently FAIL** - catching the bug correctly

✅ **`MANDATORY_VERIFICATION_CHECKLIST.md`** - Updated with solution validation requirements

✅ **`verify_before_push.py`** - Automated pre-push gate

✅ **Documentation:**
- `UNDERPRODUCTION_ROOT_CAUSE_REPORT.md` - Failed debugging attempts
- `SYSTEMATIC_DEBUG_FINDINGS.md` - Evidence gathered
- `MIP_THEORY_SHELF_LIFE.md` - MIP theory for correct formulation

---

## Failed Fix Attempts (Learn from These)

### Attempt #1: Remove init_inv from shelf life Q entirely
- **Theory:** Init_inv being double-counted in Q and material balance
- **Result:** Phantom INCREASED 283k → 291k
- **Conclusion:** Wrong - made it worse

### Attempt #2: Add demand nodes to material balance index
- **Theory:** Demand nodes missing material balance constraints
- **Result:** No change (they already had constraints)
- **Conclusion:** Diagnosis was wrong

### Attempt #3: Fix Skip conditions in balance rules
- **Theory:** Skip logic preventing constraints from being created
- **Result:** No change (constraints already existed)
- **Conclusion:** Logic was already correct

### Attempt #4: Change to `t == first_date` (Day 1 only)
- **Theory:** Init_inv should be in Q only on Day 1, not Days 2-17
- **Result:** Production WORSE (16k → 7k), objective increased
- **Conclusion:** Made problem worse

### Attempt #5: (same as #4 after revert)
- **Result:** Same as #4
- **Conclusion:** Repeatedly making same mistake

**Pattern:** Every fix either has no effect or makes it worse

**Systematic Debugging Verdict:** "After 3+ failures, question the architecture"

---

## Current Code State

**Git status:**
- HEAD: commit 1d0aa23 (reverted coefficient scaling)
- Modified files:
  - `src/validation/data_coordinator.py` - Fixed Products loading from network file
  - `src/validation/planning_data_schema.py` - Added units_per_mix to ProductID
  - `tests/test_solution_reasonableness.py` - Fixed to handle scaled/unscaled
  - `src/optimization/sliding_window_model.py` - Has latest failed fix (revert this!)

**Uncommitted changes:** Need to decide what to keep

**Diagnostic files:** All removed (clean slate)

---

## Key Evidence Files

**User's Solve Data:**
- `solves/2025/wk45/initial_20251106_1119.json` - Latest 4-week solve (44k prod, 5 days)
- `solves/2025/wk45/initial_20251105_1652.json` - Nov 5 16:52 (276k prod, 20 days) ✅ WORKING

**Model Output:**
- `workflow_model_debug.lp` - LP file from last solve (can inspect actual constraints)

**Code Files:**
- `src/optimization/sliding_window_model.py` - Lines 1211-1450 (shelf life constraints)
- `src/optimization/sliding_window_model.py` - Lines 1582-1952 (material balance)

---

## Hypotheses to Investigate (Next Session)

### Hypothesis A: Test Calculation is Wrong
**Theory:** Model is correct, but my conservation test calculates "consumed" wrong

**Evidence for:**
- Material balance is an EQUALITY constraint (Pyomo enforces it)
- Solver reports "optimal" and "feasible"
- Violating equality constraint should be impossible

**Evidence against:**
- Per-node analysis shows all demand nodes with negative balances
- Shipments = 21× production (extraction bug?)

**Test:** Manually verify ONE material balance equation holds in solved model

### Hypothesis B: Shipment Extraction is Wrong
**Theory:** Extraction calculates shipments incorrectly, inflating consumption

**Evidence for:**
- `test_hypothesis_arrivals.py` showed shipments = 350k vs production = 16k
- 21× ratio is physically impossible

**Evidence against:**
- Checked extraction code line-by-line, looks correct
- Unscaling verified

**Test:** Compare extracted shipments to actual in_transit variable values

### Hypothesis C: Material Balance Missing Shipments in Arrivals
**Theory:** Material balance arrivals calculation has bug, nodes don't get replenished

**Evidence for:**
- Diagnostic showed "Key in model.in_transit: False" for some routes
- If arrivals = 0, nodes can't be replenished

**Evidence against:**
- in_transit variables exist (2160 created)
- Some have non-zero values (174 active)

**Test:** Add instrumentation to material balance arrivals calculation

---

## Data to Check (Next Session)

**Compare Nov 5 16:52 solve (working) vs current:**

1. **What commit was 16:52 solve run from?**
   - Check git log timestamps
   - Might not be 3a71197

2. **What data files were used?**
   - Check metadata in JSON
   - planning_start_date, planning_end_date
   - num_forecast_entries

3. **What solver parameters?**
   - MIP gap
   - Time limit
   - Warm start used?

4. **What model parameters?**
   - use_pallet_tracking
   - use_truck_pallet_tracking
   - allow_shortages

---

## Recommended Approach for Next Session

**Following systematic-debugging skill:**

### Phase 1: Verify Baseline (30 min)

1. **Checkout commit 3a71197 exactly**
   ```bash
   git checkout 3a71197
   ```

2. **Run 4-week solve with SAME parameters as user's 16:52 solve**
   - Check JSON metadata for exact config
   - Use same data files
   - See if you get 276k production

3. **If you get 276k:** Code works, bug is in test/scaling
   **If you get 16k:** Code is broken, proceed to Phase 2

### Phase 2: Instrument Material Balance (1 hour)

**Don't try more fixes - GATHER EVIDENCE first!**

1. **Add logging to ONE material balance equation:**
   ```python
   # For node 6104, product 0, Day 5:
   print all components with actual numeric values
   ```

2. **Verify equation holds:** `I[5] == I[4] + arrivals - consumed`

3. **If holds:** Model is correct, test is wrong
   **If doesn't hold:** Impossible - Pyomo bug or misunderstanding

### Phase 3: Check Test Logic (30 min)

**My conservation test might be wrong for network models!**

**Current test assumes:**
```
Global: init_inv + production = consumed + end_inv
```

**But in a NETWORK:**
```
Manufacturing: prod = shipments_out
Demand nodes: shipments_in = consumed
Total system: init_inv + prod = consumed + end_inv + in_transit
```

**The test doesn't account for in-transit goods!**

Test if: `init_inv + prod = consumed + end_inv + end_in_transit`

---

## Key Files for Next Session

**Code:**
- `src/optimization/sliding_window_model.py` (main model)

**Tests:**
- `tests/test_solution_reasonableness.py` (may need fixing!)

**Data:**
- `solves/2025/wk45/initial_20251105_1652.json` (working solve)
- `solves/2025/wk45/initial_20251106_1119.json` (broken solve)

**Theory:**
- `MIP_THEORY_SHELF_LIFE.md` (how it should work)

---

## What NOT to Do (Lessons Learned)

❌ **Don't:** Try fixes without understanding root cause
❌ **Don't:** Make 3+ attempts without changing approach
❌ **Don't:** Trust "optimal" status without checking solution makes sense
❌ **Don't:** Push code without running solution validation tests

✅ **Do:** Gather evidence systematically
✅ **Do:** Test hypotheses one at a time
✅ **Do:** Question test logic if model seems impossible
✅ **Do:** Compare working vs broken commits directly

---

## Git Commands for Next Session

```bash
# Start fresh
git checkout master
git pull

# Check current state
git log --oneline -5

# Revert the failed init_inv fix if still there
git checkout src/optimization/sliding_window_model.py

# Compare working vs current
git diff 3a71197 HEAD -- src/optimization/sliding_window_model.py

# Or checkout exact working commit
git checkout 3a71197
```

---

## Success Criteria

**You'll know the bug is fixed when:**

```bash
pytest tests/test_solution_reasonableness.py -v
# ALL tests PASS

4-week solve shows:
  Production: 250k-320k units
  Production days: 15-25
  Fill rate: 85-95%
  Shortage: < 30k units
  Conservation: init_inv + prod ≈ consumed + end_inv (within 5%)
```

---

## Final Notes

**Process improvements created this session:**
- Comprehensive test suite that catches this bug
- Verification checklist for future changes
- MIP theory documentation

**These ensure this type of bug is caught before push in future.**

**The actual model bug remains unsolved** - needs fresh eyes and systematic approach.

---

**Good luck to next session! Start with Phase 1: Verify Baseline.**
