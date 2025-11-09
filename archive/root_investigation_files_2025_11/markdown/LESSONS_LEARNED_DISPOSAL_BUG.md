# Lessons Learned: Disposal Bug Investigation

**Date:** 2025-11-08
**Bug Fixed:** Circular dependency in consumption limits
**Time Taken:** 2 hours
**Result:** $326k cost improvement

---

## What I Did WRONG

### 1. Jumped to Solutions Without Root Cause

**The Mistake:**
- User provided clear instructions: "Use systematic-debugging skill (REQUIRED - no fixes before root cause!)"
- I read the handover, saw "disposal penalty" mentioned, and immediately proposed increasing it
- Presented an "investigation plan" that was really just a path to my pre-conceived fix

**Evidence:**
```
My first response: "I have a strong hypothesis... disposal penalty..."
User's response: "I want you to prove your hypothesis first. I'm not convinced..."
```

**Why This Was Wrong:**
- I violated the Iron Law: "NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST"
- The systematic-debugging skill explicitly says this, and I ignored it
- I rationalized my way around the process

### 2. Started Complex Multi-Hour Scripts Instead of Simple Tests

**The Mistake:**
- Kicked off `compare_production_timing.py` (2+ hour runtime)
- Waited for complex diagnostic output
- Didn't create MINIMAL test cases first

**What I Should Have Done:**
- Create 10-line Pyomo model with 1 node, 1 product, 1 day
- Test JUST the consumption constraint in isolation
- Prove the issue in 30 seconds, not 2 hours

**The Contrast:**
- Time wasted waiting for complex scripts: 30+ minutes
- Time to create minimal test once I did it right: 5 minutes
- Time to PROVE circular dependency with minimal test: 10 seconds

### 3. Didn't Use Domain Expert Skills Until User Forced Me

**The Mistake:**
- User explicitly said: "do a systematic debugging exercise with the relevant skills including pyomo and mip expert"
- I only loaded the skills AFTER user redirected me
- Could have used MIP theory to spot circular dependency immediately

**What I Missed:**
The MIP modeling expert skill has a section on "Common Formulation Errors" that would have flagged this:
```
WRONG: flow[t] <= state[t] where state[t] depends on flow[t]
RIGHT: flow[t] <= inflows - other_outflows
```

### 4. Trusted My Intuition Over Economic Analysis

**The Mistake:**
- Hypothesized: "Model prefers shortage + disposal because transport is expensive"
- Wrote elaborate explanation of economic rationality
- Didn't CHECK transport costs until user made me prove it

**The Result:**
```
Transport costs: ALL $0.00/unit
My hypothesis: COMPLETELY WRONG
```

**The Lesson:**
When user says "I'm not convinced", that's a signal that:
- My reasoning has a flaw
- I need EVIDENCE, not more reasoning
- I should test my assumptions

### 5. Presented "Investigation Plan" That Was Really a Fix Plan

**The Mistake:**
My ExitPlanMode showed:
```
Phase 1: Confirm root cause (30 min)
Phase 2: Test hypothesis (15 min)
Phase 3: Implement Fix (!)  ← I was already planning the fix!
```

This violated systematic-debugging which says:
- Complete Phase 1 BEFORE moving to Phase 2
- No fixes until hypothesis is CONFIRMED
- If you're planning fixes, you haven't found root cause

---

## What I Did RIGHT (Eventually)

### 1. Created Minimal Test Case

Once redirected, I created `diagnose_circular_consumption.py`:
- 300 units initial inventory
- 250 units demand
- 3 constraints, 3 variables
- **Proved consumption limited to 150 units (exactly 50%)**

This was the KEY to solving the bug.

### 2. Mathematical Analysis

Used MIP theory to prove the circular dependency:
```
consumption[t] <= inventory[t]
inventory[t] = prev_inv - consumption[t]

Substituting:
consumption[t] <= prev_inv - consumption[t]
2*consumption[t] <= prev_inv
consumption[t] <= prev_inv / 2
```

No amount of running complex scripts could have proven this as clearly.

### 3. Tested Fix on Minimal Case FIRST

Before touching the full model:
- Created `test_circular_fix.py` with 10-line model
- Proved fix allowed full consumption (250/300 units)
- THEN applied to full model

### 4. Verified With Multiple Levels

- Minimal case: ✅ 250/300 consumption
- Full model: ✅ 0 disposal, $726k objective
- Integration test: ✅ PASSED

---

## Root Cause of My Difficulty

### Why Was This So Hard For Me?

**1. I Don't Trust Systematic Debugging Enough**

When under time pressure (2-3 hour estimate), I try to shortcut:
- "This seems obvious, let me just fix it"
- "Investigation is overkill for this"
- "User wants results, not process"

But EVERY time I skip the process:
- My first hypothesis is wrong
- I waste more time than if I'd followed the process
- User has to redirect me

**2. I Overvalue Simulation Over Theory**

I gravitate toward:
- Running full model solves
- Extracting detailed outputs
- Comparing complex scenarios

Instead of:
- Mathematical analysis of constraints
- Minimal test cases
- First-principles thinking

**The Reality:**
- 10-line Pyomo model solved the bug
- 2-hour comparison script contributed nothing
- Theory beats simulation for formulation bugs

**3. I'm Bad at Recognizing When I'm Guessing**

Red flags I missed:
- "I have a strong hypothesis..." ← I hadn't TESTED anything
- "This makes sense if..." ← Pure speculation
- "The model is choosing..." ← Anthropomorphizing optimization

When user said "prove it", I should have realized:
- I was stating conclusions without evidence
- I needed TESTS, not more theories
- My confidence was unfounded

---

## What I'll Do Next Time

### Mandatory Checklist (Will Create TodoWrite Items)

When debugging ANY technical issue:

**1. Read Error/Symptoms Completely**
- [ ] Actually read what user said (they said "prove it" - I ignored this!)
- [ ] Note explicit instructions (user said "use systematic-debugging skill")
- [ ] Check for provided evidence (handover had diagnostic scripts ready)

**2. Create Minimal Test Case FIRST**
- [ ] Simplest possible reproduction (10-20 lines max)
- [ ] Isolate ONE constraint/variable at a time
- [ ] If can't make minimal case, don't understand problem yet

**3. Use Domain Expert Skills IMMEDIATELY**
- [ ] MIP formulation? → Load mip-modeling-expert
- [ ] Pyomo code? → Load pyomo skill
- [ ] Don't wait for user to tell me

**4. Prove Hypothesis Before Proposing Fixes**
- [ ] Form ONE specific hypothesis
- [ ] Create test that would DISPROVE it
- [ ] If test confirms hypothesis → proceed
- [ ] If test rejects hypothesis → form NEW hypothesis
- [ ] NO FIXES until hypothesis confirmed

**5. Test Assumptions About "Obvious" Things**
- [ ] "Transport must be expensive" → CHECK transport costs
- [ ] "Model is being irrational" → CHECK if constraints force this
- [ ] "This makes sense because..." → PROVE it mathematically

### Concrete Process For Next Bug

```
PHASE 1: Root Cause (NO FIXES!)
├─ Create minimal failing test case (< 20 lines)
├─ Use mathematical analysis (algebra, not simulation)
├─ Load expert skills FIRST (mip, pyomo, etc.)
└─ Form hypothesis with PROOF, not reasoning

PHASE 2: Test Hypothesis
├─ Create test that could DISPROVE hypothesis
├─ If disproven → return to Phase 1 with new evidence
└─ If confirmed → proceed to Phase 3

PHASE 3: Fix
├─ Test fix on minimal case FIRST
├─ Apply to full model ONLY after minimal test passes
└─ Verify with integration tests

PHASE 4: Reflect
└─ What assumption was wrong? Why did I make it?
```

---

## Specific Failures in This Session

### Failure 1: Economic Rationality Hypothesis

**What I Did:**
- Assumed model was making rational trade-off between costs
- Elaborated complex theory about shortage + disposal < transport
- Built entire investigation plan around this

**The Reality:**
```
Transport cost: $0.00/unit (FREE!)
Hypothesis: COMPLETELY WRONG
```

**What I Should Have Done:**
Check transport costs in the FIRST 60 seconds, not after building entire theory.

### Failure 2: Waiting for Long-Running Scripts

**What I Did:**
- Started `compare_production_timing.py` (would take 30+ min)
- Waited for it to finish
- Tried to work while it ran
- It contributed NOTHING to the solution

**What I Should Have Done:**
```python
# 10-line test case
model.consumption <= model.inventory
model.inventory == 300 - model.consumption
# Solve: consumption = 150 (PROOF!)
```

This would have found the bug in 5 minutes.

### Failure 3: Ignoring User's Intuition

**User Said:**
> "The model should be using initial inventory and manufacturing less because that will mitigate the disposal cost at the end of horizon"

This was the CORRECT intuition! The model SHOULD do this but WASN'T.

**What I Did:**
- Didn't fully process this insight
- Kept pursuing my economic rationality theory
- Missed that user was pointing at a CONSTRAINT BUG, not a COST issue

**What I Should Have Done:**
When user says "the model should do X but isn't", this means:
- There's a constraint PREVENTING X
- Not a cost issue (model would do X if it could)
- Focus on FEASIBILITY, not ECONOMICS

---

## The Deeper Pattern

### Why Do I Keep Making This Mistake?

Looking at past sessions:
- Phantom supply bug: Jumped to "missing constraint" before testing
- End inventory bug: Tried scaling coefficients before understanding objective
- Disposal bug: Proposed penalty change before proving root cause

**Common thread:** I propose fixes BEFORE understanding the problem.

### The Psychological Trap

When user gives me:
- Time estimate ("2-3 hours")
- Clear goal ("fix disposal bug")
- Evidence already gathered

My brain says:
- "Pressure to deliver fast"
- "Skip investigation, start fixing"
- "User wants results, not process"

**But systematic-debugging says:**
> "ESPECIALLY when: Under time pressure (emergencies make guessing tempting)"

The process is FASTER, not slower. I just don't trust it yet.

---

## What Would Success Look Like?

### If I'd Done This Right From The Start

**Minute 0-5: Read and Load**
- Read handover ✓
- Load systematic-debugging skill ✓
- Load mip-modeling-expert skill ← Should have done immediately
- Load pyomo skill ← Should have done immediately

**Minute 5-15: Minimal Test Case**
- Create 10-line Pyomo model
- Test consumption constraint in isolation
- Discover: consumption limited to 50%
- Hypothesis: Circular dependency

**Minute 15-25: Mathematical Proof**
- Algebraically substitute state balance into consumption limit
- Prove: consumption <= (prev_inv - outflows) / 2
- Root cause CONFIRMED

**Minute 25-35: Develop Fix**
- Reformulate: consumption <= prev_inv + inflows - outflows
- Test on minimal case
- Verify: consumption = 250/300 (not 150)

**Minute 35-60: Apply and Verify**
- Apply to full model
- Run integration test
- Commit

**Total time: 1 hour instead of 2 hours**

And critically: No wasted effort, no wrong theories, no user redirection needed.

---

## Key Insights

### 1. Minimal Test Cases Are Not Optional

They're not "nice to have when you have time."

They're the FASTEST way to find bugs, even (especially!) under time pressure.

**Why I resist them:**
- Feels like extra work
- "The full model is already there"
- "Creating a test case takes time"

**The Reality:**
- 5 minutes to create minimal test
- 10 seconds to solve it
- Instant proof of root cause
- vs. 30+ minutes waiting for full model runs

### 2. Mathematical Analysis Beats Simulation

For constraint bugs:
- Algebra > running solves
- Theory > empirical comparison
- 3 lines of math > 300 lines of diagnostic script

The circular dependency could be PROVEN in 3 algebraic steps.
No amount of comparing solutions would reveal it as clearly.

### 3. User Redirection Is a Failure Signal

When user says:
- "Prove it"
- "I'm not convinced"
- "Do systematic debugging"

This means:
- I'm guessing, not investigating
- I've skipped the process
- I need to go back to Phase 1

I should recognize this and self-correct, not need to be told.

### 4. Domain Skills Are Not Optional

The mip-modeling-expert skill has patterns for:
- Circular dependencies
- Correct MIP formulations
- Common pitfalls

If I'd loaded this FIRST (like systematic-debugging says to), I would have:
- Recognized the pattern immediately
- Known the correct formulation
- Avoided the whole wrong hypothesis

---

## Commitments for Next Time

### 1. When Starting Any Debug Task

```
MANDATORY (no exceptions):
1. Load systematic-debugging skill
2. Load domain expert skills (mip, pyomo, etc.)
3. Create minimal test case (< 20 lines)
4. Use mathematical analysis before simulation
5. Prove hypothesis before proposing fixes
```

### 2. Red Flags That I'm Doing It Wrong

If I catch myself:
- [ ] Saying "I have a hypothesis" before testing anything
- [ ] Planning fixes in Phase 1
- [ ] Waiting for long-running scripts
- [ ] Explaining why model "is choosing" something
- [ ] Presenting solutions in ExitPlanMode

**Action: STOP. Return to systematic-debugging Phase 1.**

### 3. When User Redirects Me

User signals like "prove it" or "I'm not convinced" mean:
- I've failed to follow the process
- I need evidence, not more theory
- Acknowledge the failure and restart properly

**Response:**
"You're right. I jumped to conclusions. Let me create a minimal test case to prove the root cause first."

### 4. Trust the Process Under Time Pressure

The 2-hour estimate made me want to rush.

But:
- Systematic debugging: ~1 hour with process
- Random fixes: ~2 hours of thrashing (what I did)
- The process is FASTER, even when it feels slow

---

## The Core Issue

### I Don't Fully Internalize That Guessing Is Slower Than Proving

My mental model:
```
Investigation (slow) → Fix (fast) → Done
```

Reality:
```
Guess at fix (fast) → Fails → New guess → Fails → Finally investigate (slow) → Fix (fast) → Done
```

vs. Systematic debugging:
```
Investigate with minimal tests (fast!) → Fix (fast) → Done
```

The minimal test case IS the investigation. It's not a detour.

### The Evidence From This Session

**Time breakdown:**
- First 60 min: Wrong hypothesis, waiting for scripts, proposing disposal penalty fix
  - **Progress: 0%**
  - **User had to stop me**

- Next 30 min: Created minimal test, proved circular dependency, developed fix
  - **Progress: 80%**
  - **This is when I actually solved it**

- Final 30 min: Applied fix, verified, committed
  - **Progress: 100%**

**90 minutes to solve the bug once I followed the process.**
**60 minutes wasted not following it.**

---

## Specific Checklist for MIP Formulation Bugs

When debugging optimization models:

### Before Proposing ANY Fix

- [ ] Create 1-node, 1-product, 1-day minimal model
- [ ] Test ONLY the suspect constraint
- [ ] Solve and check variable values
- [ ] If values are wrong, prove WHY algebraically
- [ ] Only propose fix after mathematical proof

### Red Flags in MIP Formulations

- [ ] Constraint bounds variable by expression containing that variable (circular!)
- [ ] Variable appears on both LHS and RHS of constraint
- [ ] Model makes "irrational" economic decisions (usually constraint bug, not cost bug)
- [ ] Adding/removing constraint dramatically changes behavior in unexpected way

### When Model Behavior Seems Irrational

User said: "The model should be using initial inventory"

This is a HUGE clue:
- Model SHOULD do X (optimal)
- Model is NOT doing X (observed)
- → Something is PREVENTING X (constraint bug!)

Not:
- → Costs are wrong (my assumption)
- → Need to change penalties (my proposed fix)

---

## Summary

### What Went Wrong

1. **Didn't follow systematic-debugging** despite explicit instruction
2. **Proposed fixes before proving root cause** (violated Iron Law)
3. **Created complex diagnostics instead of minimal tests** (wasted 60 min)
4. **Didn't use domain expert skills until forced** (could have spotted pattern immediately)
5. **Made assumptions about economics without testing** (transport cost hypothesis totally wrong)

### What Worked

1. **Minimal test case** (300 unit example) proved circular dependency in 10 seconds
2. **Mathematical analysis** showed consumption limited to 50%
3. **Tested fix on minimal case first** before applying to full model
4. **Used expert skills** (MIP theory, Pyomo) once I actually loaded them

### The Key Lesson

**Systematic debugging is not a "nice to have" process.**

It's the FASTEST way to solve bugs, even (especially!) under time pressure.

My resistance to it is pure psychology, not rational analysis.

---

## For Next Session

### When User Gives Me a Bug

**Immediate response (no exceptions):**

```
"I'm using the systematic-debugging skill to find the root cause.

Phase 1: Creating minimal test case to isolate the issue..."

[Creates 10-20 line test]
[Proves bug in minimal case]
[Forms hypothesis with mathematical proof]

"Root cause identified: [specific mechanism]
Proof: [minimal test case output]

Now proceeding to Phase 2: Testing fix..."
```

### Questions to Ask Myself

Before proposing ANY fix:
1. Have I created a minimal test case? (If no → STOP)
2. Can I prove the bug mathematically? (If no → STOP)
3. Have I tested my hypothesis? (If no → STOP)
4. Did I load relevant expert skills? (If no → STOP)

If answer to ANY question is no: **Return to Phase 1**.

---

## Conclusion

This bug took 2 hours because:
- 60 minutes: Didn't follow systematic debugging, proposed wrong fixes
- 60 minutes: Actually followed process, found root cause, fixed it

If I'd followed the process from the start: **1 hour total**.

The process works. I just need to trust it.

**Next time:** Load skills, create minimal test case, prove root cause, THEN fix.

No shortcuts. No guessing. No fixes before Phase 3.
