# Systematic Debugging Findings: Underproduction Bug

**Date:** 2025-11-06
**Approach:** Following systematic-debugging skill after 3+ failed fix attempts

---

## Phase 1: Root Cause Investigation - COMPLETED

### Evidence Gathered

**Timeline:**
- Nov 4 17:36 (before consumption bound removal): 966k production (OVERPRODUCTION)
- Nov 5 16:52 (after removal, before scaling): 276k production ✅ **WORKING**
- Nov 5 17:25 (after my scaling commit 8f2e4df): 0 production ❌ **BROKEN**
- Nov 6 11:19 (user's solve): 44k production in 5 days ❌ **STILL BROKEN**

**Conclusion:** Bug introduced BY my coefficient scaling (commit 8f2e4df), not pre-existing.

### Conservation Violation Confirmed

**Test evidence:**
```
Available supply: 47,255 units (30,823 init_inv + 16,432 production)
Actual consumed:  330,237 units
PHANTOM SUPPLY:   282,982 units (6× overconsumption!)
```

**Per-node analysis:**
- ALL 9 demand nodes consume 4-10× their available supply
- Example: Node 6104 consumes 59k with only 9.8k supply
- Material balance equality constraint violated by 283k units

### What Changed in Scaling Commit (8f2e4df)

**In `__init__`:**
- `self.demand` ÷ 1000 (now in thousands)
- `self.initial_inventory` ÷ 1000 (now in thousands)

**In `_add_variables`:**
- Added `bounds=(0, X)` to all flow variables
- All variables documented as "in thousands"

**In constraints:**
- Production constraints updated to handle thousands
- Big-M values scaled

**In objective:**
- All flow costs × FLOW_SCALE_FACTOR

**NOT changed:**
- Material balance equation structure (lines 1625-1952)
- Demand balance equation (line 1988)
- Shelf life constraints (lines 1230-1520)

---

## Phase 2: Diagnostic Instrumentation - IN PROGRESS

### Instruments Added

**Material Balance Logging (Line 1745-1758):**
Logs all equation components for sample nodes on Day 3.

**Output shows:**
- Equation structure correct (all components present)
- Values are Pyomo expressions (can't see numeric values during build)

**Post-Solve Diagnostic Created:**
- `diagnose_material_balance_values.py` - Extracts actual numeric values
- Result: Trivial solutions (all zeros) - not helpful for diagnosis

---

## Phase 3: Hypotheses (Not Yet Tested)

### Hypothesis A: Scaled Initial Inventory But Diagnostic Still Checks > 100

**Line 1294:**
```python
if node_id == '6122' and t == list(model.dates)[5] and init_inv > 100:
```

**Issue:** `init_inv` is now in thousands (e.g., 1.28), so `> 100` never triggers!

**Impact:** Diagnostic doesn't print, but shouldn't affect constraint logic.

**Likelihood:** Low (diagnostic issue, not formulation bug)

### Hypothesis B: Bounds Too Tight for Inventory Variables

**Line 745:**
```python
model.inventory = Var(..., bounds=(0, 100))  # Max 100 thousands = 100k units
```

**Issue:** If a hub stores 17 days × 6k/day = 102k units, bound of 100k is violated!

**Test:** Check if any inventory variables hit upper bound of 100.

**Likelihood:** Medium (could force underproduction)

### Hypothesis C: Material Balance Missing for Demand Nodes

**Lines 1767, 1968:**
```python
if node.supports_ambient_storage() or node.has_demand_capability()
```

**My fixes added** `or node.has_demand_capability()`

**But:** Rule function (line 1657) has:
```python
if not node.supports_ambient_storage() and not node.has_demand_capability():
    return Constraint.Skip
```

**Combined logic:** Node included if `supports_ambient_storage() OR has_demand`

**But then skipped if:** `NOT supports_ambient AND NOT has_demand`

**This is correct!** Skip only if BOTH are false.

**Likelihood:** Low (logic is correct)

### Hypothesis D: Arrivals Calculation Has Bug

**Observation from diagnostic:**
```
DEBUG arrivals for 6104, HELGAS GFREE TRAD WHITE 470G, 2025-11-07:
  Key in model.in_transit: False  ← Arrivals = 0!
```

**Issue:** If `in_transit` variables aren't being created or valued correctly, arrivals = 0, so demand nodes can't be replenished!

**Result:**
- Day 1: Use init_inv (30k total)
- Day 2-28: No arrivals, init_inv depleted
- Model forced to take shortages OR... phantom consumption?

**Likelihood:** HIGH - This could explain everything!

---

## Recommended Next Steps (Systematic Debugging Phase 3)

### Test Hypothesis D (Arrivals Bug)

**1. Query in_transit variables after solve:**
```python
# How many in_transit variables have value > 0?
active_shipments = sum(1 for key in model.in_transit
                      if value(model.in_transit[key]) > 0.01)

# Expected: ~100+ active shipments for 4-week
# If << 100: Shipments aren't happening!
```

**2. Check why `Key in model.in_transit: False`:**
- Are variables being created?
- Are solver assigning values?
- Is key format wrong?

**3. If arrivals are broken:**
- Demand nodes can't be replenished
- They consume init_inv on Day 1-2
- Then have nothing left
- Model creates phantom consumption via shelf life constraints?

---

## Recommendation

**Given 6+ hours of failed attempts:**

1. **STOP trying fixes** (systematic debugging says question architecture after 3+ failures)

2. **Test Hypothesis D thoroughly** (arrivals = 0 explains underproduction)

3. **If Hypothesis D confirmed:** Check if `in_transit` variable creation or valuation changed in scaling

4. **If Hypothesis D false:** Consider **reverting coefficient scaling** and re-approaching with smaller incremental changes

---

**Estimated time to resolution:** 2-4 hours if Hypothesis D is correct

**My confidence:** 60% that arrivals/shipments are the issue

**Fallback:** Revert scaling, fix underproduction separately, re-apply scaling incrementally with tests at each step
