# MANDATORY VERIFICATION CHECKLIST

**Purpose:** Prevent claiming success without evidence
**Status:** MANDATORY - Must be followed before ANY completion claim
**Skill Reference:** `superpowers:verification-before-completion`

---

## 🚨 THE IRON LAW

**NO COMPLETION CLAIMS WITHOUT RUNNING VERIFICATION COMMANDS**

This is not optional. This is not flexible. This is mandatory.

---

## ✅ Verification Checklist - UI Changes

**BEFORE claiming "UI works", "Results page complete", "Pull and test", or ANY success statement:**

### **Step 1: Run Integration Test**

**Command:**
```bash
pytest tests/test_ui_integration_complete.py -v
```

**Required output:**
```
1 passed, 10 warnings in ~5-6 seconds
```

**If test FAILS:** Fix the issue, re-run, repeat until passes

**If test PASSES:** Proceed to Step 2

### **Step 2: Verify Test Output**

**Check printed verification:**
```
✅ COMPLETE UI INTEGRATION TEST PASSED
  Production: [number] units
  Cost breakdown: $[number]
  Shipments: [number]
  FEFO batches: [number]
  Daily Snapshot locations: 11
```

**Required:**
- Production > 250,000 units (for 4-week horizon)
- Cost breakdown > $0
- Shipments > 100
- Locations = 11

**If numbers suspicious:** Investigate before claiming success

### **Step 3: Run Manual UI Check** (Optional but Recommended)

**Command:**
```bash
streamlit run ui/app.py
```

**Verify:**
- [ ] Solve completes without errors
- [ ] Results page loads (no ValidationError)
- [ ] Production tab shows all 5 products
- [ ] Daily Snapshot displays
- [ ] Can move date slider

### **Step 4: Commit with Evidence**

**Commit message MUST include test evidence:**
```
fix: [description] (TEST PASSES: 1 passed in 5.4s)

Verification evidence:
  pytest tests/test_ui_integration_complete.py -v
  Result: 1 passed ✅
  Production: 296,310 units
  Cost: $290,493
```

### **Step 5: Report to User with Evidence**

**Format:**
```
✅ [Feature] complete - TEST VERIFIED

Evidence:
  Test: pytest tests/test_ui_integration_complete.py
  Result: 1 passed in 5.4s
  Production: 296,310 units

Pull and verify:
  git pull
  streamlit run ui/app.py
```

**NOT:**
- "Should work now"
- "Pull and test"
- "Everything is complete"

---

## 🚨 Red Flag Phrases - FORBIDDEN Without Evidence

**These phrases are BANNED unless preceded by test evidence:**

- ✅ "Complete"
- ✅ "Working"
- ✅ "Fixed"
- ✅ "Ready"
- ✅ "Pull and test"
- ✅ "All tabs functional"
- ✅ "No errors"

**Required format:**
```
"TEST PASSED (evidence) - [claim]"

Example:
"TEST PASSED (1 passed in 5.4s, Production: 296k) - UI integration complete"
```

---

## 📋 Checklist for Optimization Model Changes

**BEFORE claiming "model works", "optimization complete", "scaling implemented", etc.:**

### **Step 1: Solution Reasonableness Tests (MANDATORY)**
```bash
pytest tests/test_solution_reasonableness.py -v
```

**Required Output:** All tests PASS

**These tests verify:**
- Production meets demand (accounting for initial inventory)
- Fill rate > 95% (no excessive shortages)
- Production spread across sufficient days (not concentrated)
- Conservation of flow (can't consume more than available)
- Cost components have realistic magnitudes

**If ANY test fails:** The solution is economically nonsensical, indicating a formulation bug.

### **Step 2: Integration Test**
```bash
pytest tests/test_integration_ui_workflow.py::test_ui_workflow_4_weeks_sliding_window -v
```

**Required:** `PASSED`

### **Step 3: Unit Tests**
```bash
pytest tests/test_fefo_batch_allocator.py -v
pytest tests/test_pallet_entry_costs.py -v
```

**Required:** All pass

### **Step 4: Manual Solution Inspection (REQUIRED for Major Changes)**

**After solving, verify metrics make sense:**
```python
# Check production quantity
expected_production ≈ total_demand - initial_inventory
actual_production should be within 80-120% of expected

# Check shortage
shortage should be < 5% of demand (unless capacity constrained)

# Check production days
For 4-week horizon: should produce on 15-25 days (not just 2-5 days!)

# Check objective value
For 4-week: should be $400k-$2M (not $50k or $10M)
```

**Red Flags (Indicate Formulation Bugs):**
- Fill rate > 95% but production < 20% of demand → Phantom supply (double-counting)
- Massive shortages despite low shortage cost → Penalty not in objective
- Production only on 2-5 days in 4-week → Constraints blocking production
- Objective suspiciously low → Cost scaling error

### **Step 5: Then and Only Then: Claim Success with Evidence**

**Required Format:**
```
✅ [Feature] complete - ALL TESTS PASS

Verification Evidence:
  pytest tests/test_solution_reasonableness.py: 6 passed ✅
  4-week production: 307,421 units (expected: 306k)
  Fill rate: 99.2%
  Objective: $583,492
```

---

## 🎯 Why This Matters

**From this session:**

**I claimed:** "Daily Snapshot complete"
**Evidence:** None (didn't run UI)
**Result:** User found ValidationError
**Cost:** User's time wasted finding my bugs

**With checklist:**

**Step 1:** Run `pytest tests/test_ui_integration_complete.py`
**Result:** Would have found ValidationError immediately
**Fix:** Before user ever saw it
**Cost:** My time (correct), not user's time

---

## 📚 Architecture References

**This checklist enforces:**
1. `superpowers:verification-before-completion` skill
2. Interface contract: `src/optimization/result_schema.py`
3. Integration test: `tests/test_ui_integration_complete.py`

**All three must be satisfied before completion claims.**

---

## ✅ Quick Reference

**Before claiming anything works:**

```bash
# Run this:
pytest tests/test_ui_integration_complete.py -v

# See this:
1 passed, 10 warnings in 5.40s

# Then say:
"TEST PASSED (1 passed) - [claim] ✅"
```

**Never:**
- Claim without evidence
- Ask user to test unverified code
- Say "should work" instead of "test shows works"

---

## 🔒 Enforcement

**This checklist is MANDATORY.**

**Violation = failure**, not efficiency.

**Future sessions:** Read this file first, follow before ANY claim.

**No exceptions.**
