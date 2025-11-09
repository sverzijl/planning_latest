# Prompt for Next Session: Underproduction Bug

**Copy this prompt to start the new session:**

---

## Context

I have an optimization model (SlidingWindowModel) that's producing unrealistic solutions for 4-week horizons.

**The bug:**
- 4-week solve produces only 44,000 units in 5 days
- Should produce ~307,000 units across 20+ days
- Fill rate shows 98% but this is impossible with available supply
- Conservation of flow is violated (consuming 6× available supply)

**Previous session:**
- 10+ hours of investigation  
- 5 attempted fixes (all failed or made it worse)
- Comprehensive test suite created to detect the bug
- Need fresh systematic approach

**Read the complete context:**
```
cat SESSION_HANDOVER_UNDERPRODUCTION_BUG.md
```

---

## Your Task

**Fix the underproduction bug using systematic debugging.**

**DO NOT:**
- ❌ Jump straight to proposing fixes
- ❌ Guess at solutions without evidence
- ❌ Try multiple fixes at once
- ❌ Make more than 2 fix attempts without re-evaluating

**DO:**
- ✅ Read SESSION_HANDOVER_UNDERPRODUCTION_BUG.md completely first
- ✅ Use systematic-debugging skill (mandatory!)
- ✅ Use mip-modeling-expert skill for formulation theory
- ✅ Use pyomo skill for implementation details
- ✅ Gather evidence before proposing solutions

---

## Recommended Starting Approach

### Step 1: Verify Baseline
The handover doc says Nov 5 16:52 solve produced 276k units (working), but current code produces 7-16k (broken). Find out why.

### Step 2: Question the Test Logic
Maybe the conservation test is wrong, not the model. Check if it accounts for in-transit goods properly.

### Step 3: Add Minimal Instrumentation
One diagnostic that prints actual Pyomo variable values for ONE material balance equation.

### Step 4: Form ONE Hypothesis and Test It

---

## Success Criteria

```bash
pytest tests/test_solution_reasonableness.py -v
# ALL tests PASS

4-week production: 250k-320k units
Production days: 15-25
Conservation holds
```

---

## Starting Command

```bash
cat SESSION_HANDOVER_UNDERPRODUCTION_BUG.md
git status
pytest tests/test_solution_reasonableness.py -v
```

**Good luck! Evidence first, fixes second.**
