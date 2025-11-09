# Handover: Disposal Bug Investigation
**Date:** 2025-11-06
**Status:** Bug identified, mechanism partially understood, fix NOT yet attempted
**For Next Session:** Option B - Fix disposal bug to optimize objective

---

## Current State

### ✅ What's FIXED and Ready to Push

**Commits ready:**
- `1df30b1` - Phantom supply fix (consumption bounds) + comprehensive test suite
- `e5a0f0c` - End inventory fix (waste_multiplier 10 → 100)

**Test results:**
```bash
pytest tests/test_solution_reasonableness.py (critical tests)
# Result: 5/5 critical tests PASSING ✅
```

**Model works correctly** - can be deployed as-is!

---

## The Disposal Bug (Optimization Opportunity)

### Problem Statement

**When forcing low end inventory with current formulation:**

Using waste_mult=10 and constraining `sum(end_inventory) <= 2000`:
- Model disposes 7,434 units of initial inventory
- Disposal cost: $111,510 (at $15/unit)
- Meanwhile takes shortages at $10/unit
- **Economically irrational!**

**Impact on objective:**
```
Natural (no constraint):     $947k
Constrained (end_inv<=2000): $1,052k (+$105k)

Breakdown of $105k increase:
  Production:  -$18k   (producing less, good)
  Shortage:    +$127k  (more shortages, expected)
  Waste:       -$115k  (less end inventory, good)
  DISPOSAL:    +$112k  ← THE BUG!
```

**Current workaround:** waste_mult=100 forces model to avoid waste, achieving:
- End inventory: 620 units ✅
- Objective: $1,205k (27% higher than ideal)

**Potential if bug fixed:**
- End inventory: <2,000 units
- Disposal: 0 units
- Objective: ~$941k (saves $264k vs current workaround!)

---

## Root Cause Analysis (What We Know)

### Evidence Gathered

**1. Disposal is VALID (not a constraint bug):**
- All 7,434 disposed units are actually expired (age >= 17 days)
- Disposal happens Days 24-28
- Disposal variables only exist for dates >= expiration_date ✓
- Formulation is correct on disposal logic

**2. Disposal locations:**
- Nodes: 6110, 6123, 6120, 6130
- These are demand nodes that HAD initial inventory
- Initial inventory sits unused at these nodes until expiration

**3. Cost breakdown proves disposal is the mystery:**
```
Expected cost change: -$18k (prod) +$127k (shortage) -$115k (waste) = -$6k
Actual cost change: +$105k
Difference: $111k ← Exactly matches disposal cost!
```

**4. Production quantities:**
- Natural: 285,886 units
- Constrained: 271,756 units (-14,130 units, 5% less)
- Producing LESS should save money, not cost more!

**5. Initial inventory fate:**
- Natural: 30,823 units initial inventory, 0 disposal (consumed before expiration)
- Constrained: 30,823 units initial inventory, 7,434 disposal (expires unused)
- **7,434 units not consumed in constrained solution!**

---

## Hypotheses (Not Yet Tested)

### Hypothesis A: Production Timing Shift
**Theory:** end_inv constraint forces production to shift later, preventing early consumption of init_inv

**Evidence needed:**
- Compare production schedules (when does each produce?)
- Check if constrained produces LESS on Days 1-10
- If yes: Fewer shipments to demand nodes → init_inv sits unused

**Test:** Compare production day-by-day

---

### Hypothesis B: Sliding Window Over-Constraint
**Theory:** end_inv constraint + sliding window create impossible situation on early days

**Evidence needed:**
- Check sliding window slack on Days 1-10
- See if consumption is blocked by O <= Q being tight

**Test:** Extract Q and O values for early days in both solutions

---

### Hypothesis C: Network Routing Changes
**Theory:** Constrained solution uses different routes, stranding init_inv at nodes without demand

**Evidence needed:**
- Compare shipment patterns
- Check if constrained ships less TO nodes with init_inv
- Check if init_inv at wrong nodes for demand pattern

**Test:** Compare shipments by route in both solutions

---

### Hypothesis D: Consumption Bound Becomes Too Tight
**Theory:** With end_inv constraint, consumption bound prevents using init_inv

**Evidence needed:**
- Check if consumption[t] < inventory[t] has slack
- Compare slack in natural vs constrained
- If tight in constrained but not natural → this is the blocker

**Test:** Extract consumption and inventory values, check slack

---

## Investigation Assets

### Key Diagnostic Scripts (Keep These)
1. **detailed_objective_comparison.py** - Reveals disposal cost is the $111k
2. **trace_disposal_mechanism.py** - Shows disposal is valid (actually expired)
3. **compare_production_timing.py** - Production schedule comparison
4. **phase1_trace_init_inv_fate.py** - Daily inventory trace

### Investigation Documentation
1. **DISPOSAL_BUG_IDENTIFIED.md** - What we know
2. **FINDINGS_SUMMARY_DISPOSAL_BUG.md** - Cost analysis
3. **SYSTEMATIC_DEBUG_CHECKLIST.md** - Process followed

### Other Files (Can Archive)
- 15+ other diagnostic scripts from phantom supply investigation
- Various investigation markdown files

---

## Recommended Investigation Approach

### Phase 1: Complete Root Cause (30-60 min)

**Use scripts created:**

1. **Run production timing comparison:**
   ```bash
   venv/bin/python compare_production_timing.py
   ```
   Look for: Production shifts between solutions

2. **Run daily inventory trace:**
   ```bash
   venv/bin/python phase1_trace_init_inv_fate.py
   ```
   Look for: When/where inventory diverges

3. **Identify divergence point:**
   - Which day do solutions start differing?
   - What happens on that day in constrained that doesn't in natural?

---

### Phase 2: Test Hypothesis (30-45 min)

**Based on Phase 1 evidence, form ONE hypothesis**

**Example:** "Constrained produces less on Day 7, causing init_inv at node 6123 to not be consumed before expiration"

**Test minimally:**
- Check production on Day 7 in both solutions
- Check shipments TO node 6123 in both solutions
- Check consumption at 6123 in both solutions
- Verify hypothesis

---

### Phase 3: Fix Formulation (30-60 min)

**Once mechanism identified, potential fixes:**

**Fix Option 1:** Exclude init_inv from end_inv constraint
```python
# Only constrain NEW inventory (from production), not initial
end_inventory_from_production = sum(
    inventory[n, p, s, last_date]
    for (n, p, s) not in initial_inventory.keys()
)
end_inventory_from_production <= 2000
```

**Fix Option 2:** Add consumption bound that includes init_inv on Day 1
```python
# Current: consumption[t] <= inventory[t]
# Fix: consumption[1] <= init_inv[node] + inventory[1]  # Explicitly allow consuming init_inv
```

**Fix Option 3:** Force disposal = 0
```python
sum(disposal[...]) == 0
```
Then see if model can still minimize end_inv

---

### Phase 4: Verification (15-30 min)

**After fix applied:**

```bash
# Test with waste_mult=10 (not 100)
# Constrain end_inv <= 2000
# Verify:
pytest tests/test_solution_reasonableness.py::TestSolutionReasonableness::test_4week_minimal_end_state -v

# Check costs:
# - Disposal should be 0
# - Objective should be ~$941k (not $1,052k)
# - End inventory <= 2000
# - Conservation still holds
```

**Success criteria:**
- Disposal: 0 units
- End inventory: <2,000 units
- Objective: <$950k
- No new bugs introduced

---

## Expected Outcome

**If disposal bug fixed properly:**
- Can use waste_mult=10 or 20 (not 100)
- End inventory minimized naturally
- Objective: ~$941k (vs $1,205k with band-aid)
- **Savings: $264k** (22% improvement)

**Time estimate:** 2-3 hours total

---

## Git Status

```bash
git status
# On branch master
# Ahead by 3 commits (ready to push):
#   94dfd45 - Consumption bounds (partial)
#   1df30b1 - Complete phantom supply fix + tests
#   e5a0f0c - waste_multiplier = 100
```

**Can push these now** - model works!

**Or wait** - fix disposal bug first, then push everything together

---

## For Next Session

**Start with:**
1. Read this handover
2. Run production timing comparison
3. Run daily inventory trace
4. Identify divergence mechanism
5. Apply minimal fix
6. Verify

**Don't:**
- Skip Phase 1 (need root cause first!)
- Try multiple fixes at once
- Guess at solutions

**Use skills:**
- systematic-debugging (process)
- mip-modeling-expert (theory)
- pyomo (implementation)

---

**Good luck! The bug is nearly solved - just need to find the mechanism.**
