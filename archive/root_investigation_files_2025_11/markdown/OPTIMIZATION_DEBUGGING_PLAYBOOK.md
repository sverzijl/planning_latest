# Optimization Model Debugging Playbook

**Purpose:** Structured approach for debugging MIP/LP formulation bugs, combining systematic debugging with optimization-specific techniques.

---

## The Game Changer: Constraint Probing

### Technique: Force the Model to Reveal Trade-offs

**Principle:** Add temporary constraints that force the model into specific states, then observe how the objective responds. Irrational cost changes signal formulation bugs.

**How It Works:**
```
1. Add constraint that FORCES a specific behavior
   Example: sum(end_inventory) <= 2000

2. Compare objective before/after constraint

3. Analyze cost breakdown:
   - Which costs increased?
   - Which decreased?
   - Do the changes make economic sense?

4. Irrational trade-offs = FORMULATION BUG
```

### Example: The Disposal Bug

**The Probe:**
```python
# Force low end inventory
model.force_low_end = Constraint(
    expr=sum(model.inventory[n,p,s,last_date]
             for n,p,s in inventory_keys) <= 2000
)
```

**The Response:**
- Objective: $947k → $1,052k (+$105k)
- Production: -$18k (good!)
- Shortage: +$127k (expected)
- Waste: -$115k (good!)
- **Disposal: +$112k (IRRATIONAL!)** ← BUG SIGNAL

**The Insight:**
Model should produce LESS when end_inv is constrained (saves cost).
But disposal INCREASED by $112k - economically impossible!

This irrational response flagged the circular dependency bug.

### When to Use Constraint Probing

**Use when:**
- Model behavior seems economically irrational
- Objective is unexpectedly high/low
- Solution has unexpected patterns (e.g., high waste, strange routing)
- You suspect a formulation bug but don't know where

**How to probe:**
- Constrain end states (end_inventory, end_in_transit)
- Force binary decisions (produce/not produce, use route/don't use)
- Limit specific flows (production, shipments, consumption)
- Fix variables to expected values

**What to look for:**
- Cost increases that don't make sense
- Variables going to unexpected values
- Infeasibility when you expect feasibility
- Feasibility when you expect infeasibility

---

## Complete Debugging Process for Optimization Models

### Phase 0: Load Domain Knowledge (MANDATORY FIRST STEP)

**Before ANY investigation:**

```
1. Load systematic-debugging skill
2. Load optimization-specific skills:
   - mip-modeling-expert (for formulation patterns)
   - pyomo (for Pyomo-specific issues)
3. Load relevant domain skills if available
```

**Why this matters:**
- Skills contain patterns for common bugs
- You'll recognize issues immediately
- Prevents reinventing solved problems

**Time investment:** 30 seconds
**Time saved:** Hours

### Phase 1: Root Cause Investigation

**1A: Create Minimal Test Case (< 20 lines)**

**For optimization models:**
```python
import pyomo.environ as pyo

# MINIMAL: 1 node, 1 product, 1 or 2 time periods
model = pyo.ConcreteModel()

# Add ONLY the suspect constraint
model.x = pyo.Var(domain=pyo.NonNegativeReals)
model.suspect_constraint = pyo.Constraint(expr=...)

# Minimal objective
model.obj = pyo.Objective(expr=..., sense=pyo.minimize)

# Solve
solver = pyo.SolverFactory('appsi_highs')
result = solver.solve(model)

# Check if behavior is wrong
print(f"x = {pyo.value(model.x)}")  # Is this rational?
```

**Critical rules:**
- Start with 1 node, 1 product, 1-2 days
- Add complexity ONLY if bug doesn't reproduce
- If bug doesn't reproduce in minimal case → your hypothesis is wrong

**Time: 5-10 minutes**
**Payoff: Instant proof of root cause**

**1B: Mathematical Analysis**

For constraint bugs, prove algebraically:
```
Given:
  Constraint A: x <= y
  Constraint B: y = z - x

Prove:
  Substituting B into A:
    x <= z - x
    2x <= z
    x <= z/2

  Therefore: Constraint limits x to half of z
```

**Why this matters:**
- Simulation shows WHAT happens
- Math proves WHY it happens
- Can't fix what you don't understand

**Time: 5-15 minutes**
**Payoff: Definitive root cause**

**1C: Constraint Probing (Game Changer!)**

If minimal test doesn't reproduce or cause is unclear:

```python
# Baseline solve
result_baseline = model.solve()
obj_baseline = result_baseline.objective_value

# Add probe constraint
model.probe = Constraint(expr=sum(end_inventory) <= 2000)

# Resolve
result_probed = model.solve()
obj_probed = result_probed.objective_value

# Analyze
cost_increase = obj_probed - obj_baseline
print(f"Cost increase from probe: ${cost_increase:,.0f}")

# Extract cost breakdown
# Which components increased? Which decreased?
# Do the changes make economic sense?
```

**Look for irrational responses:**
- Producing less but cost increases (should save money!)
- Using more expensive route when cheaper exists
- Taking shortages when inventory available
- Disposing inventory that could be consumed

**Irrational response → Formulation bug, not cost bug**

### Phase 2: Pattern Analysis

**2A: Check Against MIP Best Practices**

Common formulation errors (from mip-modeling-expert):

**Circular Dependencies:**
```
BAD:  flow[t] <= state[t], where state[t] = state[t-1] - flow[t]
GOOD: flow[t] <= state[t-1] + inflows
```

**Big-M Too Large:**
```
BAD:  x <= 1000000 * y  (numerical instability)
GOOD: x <= (actual_upper_bound) * y
```

**Wrong Indicator Direction:**
```
BAD:  y * M >= sum(...)  (forces y=1 when sum > 0)
GOOD: sum(...) <= M * y  (allows y=0 or 1)
```

**2B: Check Pyomo-Specific Issues**

- Variable indexing errors
- Constraint.Skip used incorrectly
- Expressions not properly summing over index sets
- Missing parentheses in compound expressions

### Phase 3: Hypothesis Testing

**3A: Test Fix on Minimal Case First**

```python
# Original minimal case (proves bug)
model_broken = create_minimal_case(use_broken_formulation=True)
solver.solve(model_broken)
print(f"Broken: x = {pyo.value(model_broken.x)}")  # Shows bug

# Fixed minimal case
model_fixed = create_minimal_case(use_fixed_formulation=True)
solver.solve(model_fixed)
print(f"Fixed: x = {pyo.value(model_fixed.x)}")  # Should be correct

# If fixed case still shows bug → hypothesis wrong, return to Phase 1
```

**3B: Only Apply to Full Model After Minimal Test Passes**

Never fix the full model directly:
- Too complex to debug if fix is wrong
- Takes too long to solve
- Hard to isolate what changed

### Phase 4: Verification

**4A: Multi-Level Testing**

```
1. Minimal case: ✅ (already done in Phase 3)
2. Full model solve: ✅ (check objective, key metrics)
3. Integration tests: ✅ (no regressions)
4. Constraint probing: ✅ (re-probe to verify fix)
```

**4B: Re-Probe to Confirm Fix**

Add the same probe constraint that exposed the bug:
```python
# After fix, re-add the probe
model.probe = Constraint(expr=sum(end_inventory) <= 2000)
result = model.solve()

# Cost increase should now make sense
# No irrational trade-offs
```

---

## Optimization-Specific Red Flags

### Signs You're Debugging Wrong

**1. Waiting for long solves**
- If waiting > 5 minutes for diagnostic output → WRONG APPROACH
- Create minimal test case instead

**2. Tweaking cost coefficients without understanding**
- "Let me try waste_mult = 50 and see what happens"
- This is random search, not debugging
- Understand WHY current value gives wrong result

**3. Comparing full model solutions**
- "Let me compare production schedules between scenarios"
- This shows symptoms, not cause
- Use minimal case + math instead

**4. Explaining model "choices" anthropomorphically**
- "The model is choosing to dispose because..."
- Model doesn't choose - constraints force behavior
- Irrational behavior = constraint bug

### Signs You're Debugging Right

**1. You have a 10-line test case**
- Reproduces bug in isolation
- Solves in < 1 second
- Can test hypothesis instantly

**2. You can prove it mathematically**
- Algebraic substitution shows the issue
- No simulation needed to understand
- "This constraint implies X, therefore..."

**3. User's hints make sense**
- User said: "Model should use init_inv to save costs"
- You thought: "There's a constraint preventing this"
- Not: "Need to adjust cost parameters"

**4. Fix works on minimal case before full model**
- Test fix in isolation first
- Only one thing changed between broken/fixed
- Clear cause-and-effect

---

## Constraint Probing Patterns

### Pattern 1: Force End State

```python
# Probe: What happens if we minimize end inventory?
model.probe = Constraint(expr=sum(end_inventory) <= target)

# Analyze:
# - Does cost increase make sense?
# - What costs changed?
# - Any irrational trade-offs?
```

**Use for:**
- High end inventory (force it low)
- Waste minimization issues
- Understanding why model holds stock

### Pattern 2: Force Binary Decision

```python
# Probe: What if we produce this product?
model.probe = Constraint(expr=model.production['node', 'product', date] >= 1000)

# Analyze:
# - Does model become infeasible? (reveals dependencies)
# - How much does objective increase? (reveals costs)
# - What else changes? (reveals coupled decisions)
```

**Use for:**
- Product not being produced when expected
- Route selection issues
- Setup/changeover problems

### Pattern 3: Fix Variable to Expected Value

```python
# Probe: Force consumption to use initial inventory
model.probe = Constraint(expr=model.consumption[node, prod, day1] >= init_inv * 0.9)

# Analyze:
# - Is this feasible? (if not → why not?)
# - Does objective improve? (should, since consumption is free!)
# - If objective gets worse → BUG!
```

**Use for:**
- Variables stuck at unexpected values
- Flow variables not utilizing capacity
- Inventory not being consumed

### Pattern 4: Relax Suspect Constraint

```python
# Remove suspect constraint
model.suspect_constraint.deactivate()

# Resolve
result = solver.solve(model)

# Analyze:
# - Does objective improve significantly? (constraint was binding)
# - Does solution become irrational? (constraint was necessary)
# - What variables changed? (reveals what constraint controls)
```

**Use for:**
- Identifying over-constrained models
- Understanding constraint purpose
- Testing if constraint is correct

---

## Quick Reference: Debugging Decision Tree

```
Model behavior is wrong
│
├─ Is it economically irrational?
│  ├─ YES → FORMULATION BUG
│  │   └─ Create minimal test case
│  │       └─ Prove mathematically
│  │           └─ Fix constraint
│  │
│  └─ NO → COST PARAMETER ISSUE
│      └─ Use constraint probing
│          └─ Identify which cost dominates
│              └─ Adjust parameters
│
├─ Is it infeasible when it should be feasible?
│  └─ Check constraint conflicts
│      └─ Relax constraints one by one
│          └─ Find over-constraint
│
├─ Is it feasible when it should be infeasible?
│  └─ Missing constraint
│      └─ Add validation
│          └─ Test with examples
│
└─ Solution looks reasonable but wrong objective?
   └─ Extract cost components
       └─ Compare to hand calculation
           └─ Find missing/double-counted term
```

---

## Tools in Your Debugging Toolkit

### Fast (Use First)
1. **Minimal test case** (10-line Pyomo model)
2. **Mathematical analysis** (algebraic substitution)
3. **Constraint probing** (force states, observe costs)

### Slow (Use Only If Fast Methods Fail)
4. Full model solve comparisons
5. Solution extraction and analysis
6. Detailed diagnostic scripts

### When to Use Each

**Use minimal test case when:**
- You have a hypothesis about ONE constraint
- Bug involves 1-2 variables
- Can reproduce in isolation

**Use mathematical analysis when:**
- Constraint formulation question
- Need to prove a relationship
- Circular dependency suspected

**Use constraint probing when:**
- Model behavior unclear
- Multiple interacting constraints
- Need to understand trade-offs
- Cost breakdown shows irrational changes

**Use full model diagnostics when:**
- Bug doesn't reproduce in minimal case
- Requires specific data patterns
- Network/routing issues
- Multi-period coupling effects

---

## Examples from Disposal Bug

### What Worked (In Order of Effectiveness)

**1. Constraint Probing (The Game Changer!)**
```python
# Force low end inventory
model.force_low_end = Constraint(expr=sum(end_inventory) <= 2000)

# Result:
# - Disposal: +$112k (IRRATIONAL!)
# - This shouldn't happen - flagged the bug
```

**Why this worked:**
- Made the hidden bug visible
- Showed irrational cost increase
- Directed investigation to consumption/disposal interaction

**2. Minimal Test Case (The Proof)**
```python
# 10-line model: 300 units init_inv, 250 demand
# Constraint: consumption <= inventory
# Result: consumption = 150 (exactly 50%!)
# PROOF of circular dependency
```

**Why this worked:**
- Isolated the bug completely
- Proved it in 10 seconds
- No complex data, no network, no multi-period effects

**3. Mathematical Analysis (The Understanding)**
```
consumption <= inventory
inventory = init_inv - consumption

Substituting:
consumption <= init_inv - consumption
2*consumption <= init_inv
consumption <= init_inv / 2
```

**Why this worked:**
- Proved WHY consumption was limited
- No simulation needed
- Definitive understanding

### What Didn't Work

**1. Economic Rationality Theories**
- Spent 30 minutes theorizing about costs
- All theories were wrong
- Should have CHECKED costs in first 60 seconds

**2. Waiting for Complex Comparison Scripts**
- `compare_production_timing.py` ran for 30+ minutes
- Contributed NOTHING to solution
- Minimal test case solved it in 5 minutes

**3. Proposing Fixes Before Root Cause**
- Suggested increasing disposal penalty
- Would have masked bug, not fixed it
- User correctly stopped me

---

## The Systematic Process (Optimized for MIP)

### Step 1: Load Skills & Quick Checks (2 min)
```
- Load systematic-debugging
- Load mip-modeling-expert
- Load pyomo
- Check basic facts (costs, bounds, data)
```

### Step 2: Constraint Probing (10-15 min)
```
- Add constraints to force specific behaviors
- Compare objectives before/after
- Look for irrational cost changes
- Identify suspect constraints
```

### Step 3: Minimal Test Case (10-15 min)
```
- Create 10-20 line Pyomo model
- Test ONLY suspect constraint
- Solve and check values
- Prove bug reproduces
```

### Step 4: Mathematical Proof (5-10 min)
```
- Algebraically manipulate constraints
- Prove why bug occurs
- Show the mechanism
```

### Step 5: Fix & Test (15-20 min)
```
- Fix minimal case
- Verify fix works (values correct)
- Apply to full model
- Run integration tests
```

**Total time: 45-60 minutes for most bugs**

Compare to random approach:
- Guess at fix: 5 min
- Doesn't work: 30 min to realize
- New guess: 5 min
- Doesn't work: 30 min
- Finally investigate: 60 min
- Apply fix: 15 min
**Total: 2-3 hours, much frustration**

---

## Checklist for Future Bugs

### Before Starting Investigation

- [ ] Read all provided evidence completely
- [ ] Load systematic-debugging skill
- [ ] Load domain expert skills (mip, pyomo)
- [ ] Create TodoWrite items for each phase

### Phase 1: Investigation (NO FIXES!)

- [ ] Create minimal test case (< 20 lines)
- [ ] Prove bug reproduces in minimal case
- [ ] Use mathematical analysis (algebra, not simulation)
- [ ] Form hypothesis with PROOF, not reasoning

**IF constraint probing would help:**
- [ ] Add probe constraint to full model
- [ ] Compare objective before/after
- [ ] Look for irrational cost changes
- [ ] Use findings to guide minimal test case

### Phase 2: Hypothesis Testing

- [ ] Create test that could DISPROVE hypothesis
- [ ] If disproven → return to Phase 1
- [ ] If confirmed → proceed to Phase 3

### Phase 3: Fix

- [ ] Test fix on minimal case FIRST
- [ ] Verify fix works in isolation
- [ ] Apply to full model ONLY after minimal test passes
- [ ] Run integration tests

### Phase 4: Verification

- [ ] Minimal case: Fixed values correct
- [ ] Full model: Objective/metrics improved
- [ ] Integration tests: PASSED
- [ ] Constraint probing: Rational responses now

---

## Common MIP Formulation Bugs

### 1. Circular Dependencies

**Pattern:**
```
x <= y
y = z - x
```

**Symptom:** Variable limited to unexpected value (often 50%)

**Fix:** Bound against inputs, not outputs
```
x <= z  (use RHS of y's definition)
y = z - x
```

### 2. Missing/Wrong Big-M Bounds

**Pattern:**
```
x <= M * y
M = 999999  (arbitrary large number)
```

**Symptom:** Numerical instability, weak LP relaxation, slow solve

**Fix:** Calculate tight bound
```
M = known_upper_bound(x)  (problem-specific)
```

### 3. Indicator Wrong Direction

**Pattern:**
```
y * M >= sum(x[i])  (forces y=1 when sum > 0)
```

**Symptom:** Binary variables all forced to 1

**Fix:**
```
sum(x[i]) <= M * y  (allows y=0 or 1)
```

### 4. Over-Consumption Not Prevented

**Pattern:**
```
consumption + shortage = demand
inventory[t] = inventory[t-1] - consumption
# Missing: consumption <= inventory
```

**Symptom:** Phantom supply, negative inventory

**Fix:** Add coupling constraint (but watch for circular dependency!)
```
consumption <= inventory[t-1] + inflows  (use prev_inv, not current!)
```

---

## The Nuclear Option: When Everything Fails

If 3+ fix attempts fail → question the architecture (systematic-debugging Phase 4.5)

**Stop and ask:**
- Is this formulation fundamentally flawed?
- Should we use a different modeling approach?
- Are we sticking with it through inertia?

**Discuss with user before attempting Fix #4**

---

## Key Mantras

1. **Minimal test case is not optional** - It's the fastest path to root cause

2. **Math proves, simulation suggests** - Use algebra for formulation bugs

3. **Constraint probing reveals hidden bugs** - Force model into corners, observe irrationality

4. **Fix minimal case first** - Never touch full model before testing in isolation

5. **Irrational behavior = constraint bug** - Not cost parameters, not solver issues

6. **Trust the process under time pressure** - Systematic debugging is FASTER than guessing

7. **User saying "prove it" = you're guessing** - Return to Phase 1 immediately

---

## This Playbook Going Forward

**Add to this playbook when you:**
- Find a new optimization debugging pattern
- Discover a common formulation error
- Develop a useful probing technique
- Learn a lesson from a difficult bug

**Review this playbook:**
- Before starting ANY optimization debugging
- When stuck on a bug (am I following the process?)
- When user redirects you (which step did you skip?)

**Success criteria:**
- Bugs solved in < 1 hour (not 2-3 hours)
- First hypothesis is correct (not 3rd or 4th)
- No user redirections needed
- Integration tests pass on first try

---

## Credits

**Techniques from:**
- Systematic Debugging skill (superpowers)
- MIP Modeling Expert skill (AIMMS guide)
- Pyomo skill (official docs)

**Constraint probing insight:**
- Discovered during disposal bug investigation
- Recognized by user as "game changer"
- Now formalized in this playbook

**Lessons learned:**
- Disposal bug session (2025-11-08)
- See: LESSONS_LEARNED_DISPOSAL_BUG.md
