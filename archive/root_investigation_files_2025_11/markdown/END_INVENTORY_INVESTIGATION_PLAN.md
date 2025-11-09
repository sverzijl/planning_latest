# Systematic Investigation Plan: End Inventory Issue
**Using:** MIP-modeling-expert + Pyomo skills
**Approach:** Systematic debugging (hypothesis → test → conclude)

---

## Problem Statement

**Observation:**
- End inventory: 15,705 units (at demand nodes)
- Shortage: 36,118 units (at SAME nodes, SAME products!)
- ALL 5 products have both waste and shortage
- Economic loss: $47,114 (should take shortage instead of waste)

**From MIP Theory:**
If model pays $204k waste when $157k shortage would be cheaper, something is PREVENTING the better solution. Need to identify WHICH constraint(s).

---

## Investigation Plan

### Phase 1: Verify Constraint Soundness (30 min)

**Hypothesis:** Restored consumption bounds might be over-constraining

**Tests:**
1. **Check consumption bound direction:**
   - Current: `consumption[t] <= inventory[t]`
   - Question: Is inventory[t] BEFORE or AFTER consumption in the equation?
   - Material balance: `inventory[t] = inventory[t-1] + inflows - consumption`
   - This means inventory[t] is ENDING inventory (after consumption)
   - Is the bound using the right timing?

2. **Check for circular constraints:**
   - consumption <= inventory[t]
   - inventory[t] = ... - consumption
   - Substitute: consumption <= ... - consumption
   - Does this create forced behavior?

3. **Verify consumption can actually happen:**
   - Pick Day 28, node 6110 (has 3,349 end inventory)
   - Check demand[6110, Day 28]
   - Check inventory[6110, ambient, Day 28]
   - If demand < inventory, why wasn't it consumed?

**Tools:** Manual constraint analysis, Pyomo expr examination

---

### Phase 2: Test Constraint Relaxation (45 min)

**Hypothesis:** One of the restored constraints is over-tight

**Experiment 1: Relax consumption bounds**
```python
# Change from:
consumption <= inventory[t]

# To:
consumption <= inventory[t-1] + production + arrivals
# (Use available supply BEFORE consumption, not after)
```

**Experiment 2: Temporarily remove sliding window**
- Comment out shelf life constraints
- Solve with just material balance + consumption bounds
- If end inventory drops to ~0, sliding window is the culprit
- If still high, consumption bounds or material balance is the issue

**Experiment 3: Force zero end inventory**
```python
# Add constraint:
for all nodes, products, states:
    inventory[last_date] == 0
```
- If infeasible, identify which constraint conflicts
- If feasible but higher cost, verify cost increase matches waste savings

**Tools:** Model modification, re-solve, compare objectives

---

### Phase 3: Trace One Specific Product (30 min)

**Hypothesis:** Network/timing prevents late consumption

**Focus:** HELGAS GFREE MIXED GRAIN (largest end inv: 3,863 units)

**Trace:**
1. **Production timing:** When is this product produced?
2. **Shipment timing:** When does it arrive at demand nodes?
3. **Consumption timing:** When is it consumed vs when does demand occur?
4. **Expiration:** What age is the end inventory? Too old to consume?

**Specific checks:**
- Day 28 demand for this product at each node
- Day 28 inventory for this product at each node
- Why wasn't inventory consumed to meet demand?

**Tools:** Pyomo variable value extraction, temporal analysis

---

### Phase 4: Check Sliding Window Formulation (30 min)

**Hypothesis:** Sliding window prevents consuming inventory

**From lines 1211-1290:**
```python
O_ambient <= Q_ambient

where:
O = shipments + consumption (in window)
Q = init_inv + production + arrivals (in window)
```

**Question:** Does init_inv in Q allow "borrowing" that creates end inventory?

**Test:**
- On Day 28, what is the sliding window?
  - Window = Days 12-28 (17-day window)
  - Q includes: init_inv (if Day 1 in window = NO!) + production[Days 12-28] + arrivals[Days 12-28]
  - O includes: shipments[Days 12-28] + consumption[Days 12-28]

**Check:** Is O > Q on Day 28?
- If yes: Sliding window PREVENTS more consumption
- If no: Sliding window is not the blocker

**Tools:** Extract Q and O values on Day 28, compare

---

### Phase 5: Check Network/Transit Constraints (30 min)

**Hypothesis:** Goods can't reach demand nodes in time

**Check:**
1. **Last production date:** Dec 2 (Day 26)
2. **Transit times:** 1-7 days depending on route
3. **Question:** Can Day 26 production reach all nodes before Day 28?

**Specific check:**
- Production on Day 26: Which destinations can it reach by Day 28?
- 6110 (direct, 1-day transit): Can arrive Day 27 ✓
- 6130 (via Lineage, 8-day transit): Can arrive Dec 10 ✗ (beyond horizon!)

**Theory:** Model produces for near-destinations (6110) but not far-destinations (6130) because goods can't arrive in time. Result: misallocated inventory.

**Tools:** Route analysis, transit time checking

---

### Phase 6: Test Alternative Formulations (if needed) (1 hour)

**If above phases don't reveal root cause:**

**Option A: Check if it's a MINLP artifact**
- Do binaries for product_produced interact badly with consumption bounds?
- Test: Fix binaries to 1, resolve as LP

**Option B: Check disposal interaction**
- Are disposal variables "stealing" inventory that should be consumed?
- Test: Force disposal = 0, resolve

**Option C: Examine LP file**
- Extract actual constraints for Day 28, node 6110
- Manually verify with solved values
- See if constraint is tight (preventing more consumption)

---

## Investigation Order (Prioritized by Likelihood)

1. **Phase 4 first** (sliding window most likely culprit)
2. **Phase 3 second** (trace one product to understand mechanism)
3. **Phase 2 third** (test constraint relaxation if cause unclear)
4. **Phase 5 fourth** (network constraints if timing issue)
5. **Phase 1 last** (theoretical analysis to understand)
6. **Phase 6 only if desperate** (alternative formulations)

---

## Success Criteria

**Investigation complete when:**
- Identified WHICH constraint prevents zero end inventory
- Understand MIP mechanism causing the issue
- Have targeted fix (not just parameter tuning)

**Fix verified when:**
- test_4week_minimal_end_state PASSES
- End inventory + in-transit < 5,000 units
- Shortage decreases or stays same
- Objective improves (lower cost)

---

## Time Estimate

- Phase 4: 30 min
- Phase 3: 30 min
- Phase 2: 45 min (if needed)
- **Total:** 1-2 hours to root cause

---

**Ready to execute systematically. Start with Phase 4 (sliding window)?**
