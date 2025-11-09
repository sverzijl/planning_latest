# Investigation Summary: Underproduction Bug
**Date:** 2025-11-06
**Investigator:** Claude (Fresh Session)
**Status:** ROOT CAUSE IDENTIFIED, MECHANISM UNDER INVESTIGATION

---

## Executive Summary

**Initial Hypothesis:** Test logic error - forgot to account for `end_in_transit` goods
**Status:** **REJECTED** - Conservation violation is REAL, not a test artifact

**Current Finding:** Model allows demand nodes to consume **282,982 phantom units** beyond available supply

---

## Key Findings

### 1. Conservation Violation is Real

**Supply Side:**
- Initial inventory: 30,823 units
- Production: 16,432 units
- **Total supply: 47,255 units**

**Usage Side:**
- Consumed: 330,237 units
- End inventory: 658 units
- End in-transit: 4,535 units
- **Total usage: 335,431 units**

**Phantom Supply: 288,176 units** (609% of available supply!)

### 2. Model Constraints are Enforced Correctly

✅ Material balance holds locally (verified for node 6104, day 2)
✅ No negative inventory (checked all variables)
✅ Demand equation holds: `consumed + shortage = demand` (perfect match)
✅ Pyomo reports "optimal" and "feasible"

**This creates a paradox:** All local constraints hold, but global conservation fails!

### 3. Breakdown by Node Reveals the Issue

**Manufacturing Node (6122):**
- Initial inventory: 6,400 units
- Production: 16,432 units
- **Can supply: 22,832 units maximum**

**Demand Nodes (Combined):**
- Initial inventory: 24,423 units (excluding 6122)
- Consumed: 330,237 units
- **Need from manufacturing: 305,814 units**

**GAP: 305,814 - 22,832 = 282,982 units**

This exactly matches the phantom supply! Demand nodes are consuming goods that manufacturing never produced or shipped.

---

## Hypotheses Tested

### ❌ Hypothesis A: Test Missing `end_in_transit`
**Result:** REJECTED
**Evidence:** Even accounting for end_in_transit (4,535 units), conservation still violated by 283k units

### ❌ Hypothesis B: Negative Inventory
**Result:** REJECTED
**Evidence:** All 1,680 inventory variables are >= 0

### ❌ Hypothesis C: Scaling Factor
**Result:** REJECTED
**Evidence:** No scaling factors found in current code (FLOW_SCALE_FACTOR was reverted)

### ⚠️ Hypothesis D: First-Day Arrivals
**Status:** PARTIAL
**Evidence:** Lineage has zero initial inventory but receives first-day arrivals from pre-horizon shipments
**Impact:** Small (only affects Lineage route), cannot explain 283k phantom units

---

## Current Theory

**The model's material balance is correct**, but something is allowing **arrival flows** to exceed **departure flows** from manufacturing.

Possibilities:
1. **In-transit extraction bug:** Arrivals counted multiple times or departures under-counted
2. **Material balance scope:** Some nodes missing material balance constraints
3. **Arrival calculation:** First-day arrivals from pre-horizon creating infinite supply
4. **Constraint skip logic:** Material balance being skipped for some nodes/dates

---

## Evidence for Theory

**From node analysis:**
- Manufacturing: 22,832 units available (init_inv + prod)
- Demand nodes: consume 305,814 beyond their own init_inv
- **Shortfall: 282,982 units**

**Where could these 283k units come from?**
- NOT from production (only 16k produced)
- NOT from init_inv (only 31k total across all nodes)
- NOT from negative inventory (verified all >= 0)
- **Must be from inflated arrivals or missing constraints**

---

## Next Steps (Recommended)

### Immediate (30 min)
1. **Manually trace material balance for node 6104** across all 28 days
   - Extract actual Pyomo variable values
   - Verify: `I[t] = I[t-1] + arrivals - departures - consumed`
   - Check if arrivals match departures from upstream nodes

2. **Sum all shipment flows from 6122** (manufacturing departures)
   - Extract: `sum(in_transit[6122, dest, prod, t, state])` for all t
   - Compare to: production + init_inv - end_inv
   - Should match within rounding

### Deep Dive (1 hour)
3. **Check constraint creation counts**
   - How many material balance constraints created vs expected?
   - Any being skipped due to `Constraint.Skip` logic?

4. **Audit arrival calculation** in material balance
   - For each demand node on each date
   - Sum arrivals: `in_transit[origin, node, prod, t-transit, state]`
   - Verify these in_transit variables exist and have correct values

### Root Cause (2 hours)
5. **Identify the mechanism** allowing phantom supply
   - Once found, propose minimal fix
   - Verify fix doesn't break working solves

---

## Files Created During Investigation

1. `diagnostic_conservation_with_intransit.py` - Main diagnostic
2. `check_negative_inventory.py` - Verified no negative inventory
3. `check_first_day_arrivals.py` - Found Lineage issue (minor)
4. `analyze_consumption_by_node.py` - Breakdown by node (KEY FINDING)

---

## Time Spent

- Phase 1 (Hypothesis Testing): 2 hours
- Evidence Gathering: 1 hour
- **Total: 3 hours**

---

## Recommendation

**DO NOT attempt fixes yet.** The mechanism is not fully understood. Need to:
1. Trace one complete node's material balance manually
2. Identify WHERE the phantom supply enters
3. THEN propose targeted fix

Attempting fixes without understanding will likely fail (as previous session's 5 attempts demonstrated).

---

## For Next Session

If you continue this investigation:
1. Start with "Next Steps - Immediate"
2. Use the analysis scripts created (`analyze_consumption_by_node.py`)
3. Focus on: "How do 305k units flow from 6122 when it only has 23k?"

The answer to that question IS the bug.
