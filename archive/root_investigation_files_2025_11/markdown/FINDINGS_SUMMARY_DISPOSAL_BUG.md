# Summary: Disposal Bug Investigation
**Status:** Bug mechanism being traced
**Your insight was correct:** It's a bug, not a real cost

---

## What We've Proven

### ✅ The $111k "Hidden Cost" is Disposal

**Objective breakdown (waste_mult=10, end_inv <= 2000):**
```
Production unit cost:  -$18k   (producing less, saves money) ✓
Shortage cost:         +$127k  (more shortages, makes sense) ✓
Waste cost:            -$115k  (less end inventory, saves money) ✓
DISPOSAL COST:         +$112k  (disposing init_inv, BUG!) ❌
Labor/Transport/Other: +$28    (negligible)
────────────────────────────────────────────────────────
NET:                   +$105k  (should be -$6k!)
```

**The bug:** When we constrain end inventory to be low:
- 7,434 units of initial inventory don't get consumed
- Sit unused for 17+ days
- Expire
- Model disposes them at $15/unit = $112k
- Meanwhile takes shortages at $10/unit!

**This is economically irrational and proves formulation bug.**

---

## What We're Currently Investigating

**Two background processes running:**

1. **check_day1_inventory_usage.py**
   - Checking if init_inv sits unused from Day 1
   - Or if it gets consumed but disposed later

2. **compare_production_timing.py**
   - Comparing when production happens in each solution
   - Seeing if timing shift prevents init_inv consumption

**Goal:** Identify WHICH constraint interaction prevents consuming init_inv

---

## Hypotheses

### Hypothesis A: Production Shifted Away from Early Days
**Theory:** end_inv constraint forces production to different days, creating gaps where init_inv can't be consumed

**Test:** Compare production schedules
- If constrained produces LESS on Days 1-7
- Then fewer shipments to demand nodes with init_inv
- init_inv sits there, expires, disposed

### Hypothesis B: Sliding Window Over-Constraint
**Theory:** end_inv constraint + sliding window create impossible situation

**Test:** Check sliding window slack on early days
- If tight, may be preventing consumption
- If slack, not the issue

### Hypothesis C: The end_inv Constraint Itself is Broken
**Theory:** Summing inventory across all nodes/products/states creates perverse interaction

**Test:** Try constraining end_inv for ONLY manufactured goods (exclude init_inv locations)
- See if disposal still happens
- If not, proves constraint scope is wrong

---

## Recommended Fix Approaches (After Mechanism Identified)

### Option 1: Exclude Initial Inventory from end_inv Constraint
```python
# Instead of:
sum(inventory[n, p, s, last_date] for all n, p, s) <= 2000

# Use:
sum(inventory[n, p, s, last_date]
    for n, p, s
    if (n, p, s) NOT in initial_inventory.keys()) <= 2000
```

**Rationale:** Don't penalize for init_inv that couldn't be consumed due to demand timing

### Option 2: Force Disposal to Zero
```python
# Add constraint:
sum(disposal[n, p, s, t] for all keys) == 0
```

**Then see if end_inv can still be minimized without disposal**

### Option 3: Fix Root Constraint
Once we identify which constraint prevents init_inv consumption, fix THAT constraint rather than working around it.

---

## Current Status

**Commits made:**
1. ✅ Phantom supply fix (consumption bounds)
2. ✅ waste_mult = 100 (treats symptom, not cause)

**What we know:**
- Disposal bug is the root cause ($111k of $105k)
- waste_mult=100 works but is a band-aid
- Real fix is to eliminate disposal in constrained solution

**What we're finding:**
- Mechanism that prevents init_inv consumption
- Then can apply targeted fix

**Expected outcome:**
- Fix formulation bug
- Constrained solution: 0 disposal, low end_inv, $941k objective
- Can reduce waste_mult back to 10 (or reasonable value)

---

**Waiting for background processes to complete with timing analysis...**
