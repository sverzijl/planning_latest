# Next Session: Fix Disposal Bug (Optional Optimization)

**Copy this prompt to start your next session:**

---

## Context

I have an optimization model with TWO bugs that were investigated for 12 hours:

1. ✅ **Phantom supply bug:** FIXED (consumption bounds restored)
2. ⚠️ **Disposal bug:** IDENTIFIED but not yet fixed (optimization opportunity)

**Both bugs are functionally fixed** - model is production-ready with workarounds.

**This session:** Fix the disposal bug properly to optimize objective from $1,205k to ~$941k.

---

## The Disposal Bug

### What We Know

**Symptom:**
When constraining end inventory to be low (`sum(end_inventory) <= 2000`):
- Model disposes 7,434 units of initial inventory
- Disposal cost: $111,510 (at $15/unit)
- Meanwhile takes shortages at $10/unit
- Economically irrational!

**Impact:**
```
Objective with waste_mult=10:

Natural (unconstrained):        $947k
Constrained (end_inv <= 2000):  $1,052k (+$105k)

Cost breakdown of +$105k:
  Production:  -$18k   (producing less, good)
  Shortage:    +$127k  (more shortages, expected)
  Waste:       -$115k  (less end inventory, good)
  DISPOSAL:    +$112k  ← THE BUG! Should be $0
```

**Current workaround:**
- waste_multiplier = 100 (vs 10)
- Forces model to avoid end inventory despite disposal issue
- Works but objective is $1,205k (27% higher than ideal)

**If disposal bug fixed:**
- Can use waste_mult = 10 or 20
- Objective: ~$941k (saves $264k vs workaround)
- More economically optimal solution

---

## What You Need to Do

### Read the Handover First

```bash
cat HANDOVER_DISPOSAL_BUG_INVESTIGATION.md
```

This contains:
- Complete evidence gathered
- Hypotheses to test
- Investigation approach
- Expected fixes

---

## Quick Start

### Step 1: Verify Current State

```bash
git log --oneline -3
# Should see: 3 commits including phantom supply fix and waste_mult=100

git status
# Should be clean or have investigation files

pytest tests/test_solution_reasonableness.py::TestSolutionReasonableness::test_4week_conservation_of_flow \
  tests/test_solution_reasonableness.py::TestSolutionReasonableness::test_4week_minimal_end_state -v
# Should: BOTH PASS
```

---

### Step 2: Run Investigation Scripts

**Production timing comparison:**
```bash
venv/bin/python compare_production_timing.py
```
Look for: Production shifts between natural and constrained

**Daily inventory trace:**
```bash
venv/bin/python phase1_trace_init_inv_fate.py
```
Look for: When inventory levels diverge

**Cost breakdown:**
```bash
venv/bin/python detailed_objective_comparison.py
```
Verify: Disposal is $111k of the $105k increase

---

### Step 3: Form Hypothesis

Based on evidence, identify WHY end_inv constraint causes disposal.

**Likely cause:** Production timing shifts or routing changes prevent init_inv consumption before expiration

---

### Step 4: Test and Fix

**Apply ONE minimal fix** based on hypothesis

**Potential fixes:**
1. Exclude init_inv from end_inv constraint
2. Add constraint: `disposal == 0`
3. Fix sliding window to not over-constrain early days
4. Adjust consumption bounds to allow init_inv usage

**Verify fix:**
```bash
# With waste_mult=10 and end_inv constraint:
# Should achieve: Disposal = 0, end_inv < 2000, objective ~$941k
```

---

## Success Criteria

**Disposal bug is fixed when:**

```bash
# Test with waste_mult=10 (not 100!):
1. Reset waste_multiplier to 10.0 in Network_Config.xlsx
2. Ensure disposal = 0 when constraining end_inv <= 2000
3. End inventory <= 2000 units
4. Objective ~$941k (not $1,052k)
5. All tests still pass
```

**This proves:** Model can minimize end inventory without disposal cost

---

## Investigation Tools Available

**Key Scripts:**
- `detailed_objective_comparison.py` - Cost breakdown
- `trace_disposal_mechanism.py` - Disposal details
- `compare_production_timing.py` - Production schedule comparison
- `phase1_trace_init_inv_fate.py` - Daily inventory trace

**Documentation:**
- `HANDOVER_DISPOSAL_BUG_INVESTIGATION.md` - Complete context
- `DISPOSAL_BUG_IDENTIFIED.md` - What we know
- `SYSTEMATIC_DEBUG_CHECKLIST.md` - Process to follow

---

## Skills to Use

**REQUIRED:**
- `systematic-debugging` - Follow 4-phase process (no fixes before root cause!)
- `mip-modeling-expert` - Understand formulation issues
- `pyomo` - Implement fixes correctly

**Process:**
1. Phase 1: Gather evidence (run scripts, analyze output)
2. Phase 2: Pattern analysis (compare working vs broken)
3. Phase 3: Form and test ONE hypothesis
4. Phase 4: Apply minimal fix, verify

**Don't:**
- Skip to fixes without understanding mechanism
- Try multiple fixes at once
- Use waste_mult=100 as the solution (it's a band-aid)

---

## Expected Timeline

| Phase | Activity | Time |
|-------|----------|------|
| 1 | Evidence gathering (run scripts) | 30 min |
| 2 | Pattern analysis (identify mechanism) | 30 min |
| 3 | Hypothesis testing | 30 min |
| 4 | Fix and verify | 30 min |
| **Total** | **Root cause to verified fix** | **2 hours** |

---

## Commits to Make (After Fix)

```bash
# After fixing disposal bug:
git add src/optimization/sliding_window_model.py
git add data/examples/Network_Config.xlsx  # Reset to waste_mult=10 or 20

git commit -m "fix: Eliminate disposal bug in end inventory optimization

Root cause: [Fill in after investigation]
Fix: [Describe minimal fix applied]

Results:
- Disposal: 7,434 → 0 units
- End inventory: <2,000 units
- Objective: $1,052k → $941k (22% improvement)
- waste_multiplier: Can use 10-20 (not 100)

All tests pass."
```

---

## Fallback Plan

**If disposal bug takes >3 hours to fix:**
- Accept current solution with waste_mult=100
- Document as Phase 4 optimization opportunity
- Push current commits (model works)
- Revisit later with fresh investigation

**The model is production-ready now** - this is optimization, not critical bug.

---

## Files to Clean Up (After Session)

**Archive these investigation scripts:**
```bash
mkdir -p archive/disposal_investigation_2025_11/
mv *diagnostic*.py *trace*.py *compare*.py *check*.py *phase*.py archive/disposal_investigation_2025_11/
mv *INVESTIGATION*.md *ANALYSIS*.md *HANDOVER*.md archive/disposal_investigation_2025_11/
```

**Keep:**
- `tests/test_solution_reasonableness.py` (test suite)
- `src/optimization/sliding_window_model.py` (model with fixes)
- `data/examples/Network_Config.xlsx` (cost parameters)

---

**Good luck with the disposal bug fix! The investigation has narrowed it significantly.**
