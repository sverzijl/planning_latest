# Root Cause Analysis: 6-Week Warmstart Timeout

**Date:** 2025-10-20
**Issue:** 6-week horizon with warmstart times out after 10+ minutes
**Methodology:** Systematic debugging with MIP/Pyomo expertise

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:** Phase 1 of the warmstart has 4,557 integer variables when it should have ZERO.

The warmstart was designed to use a simplified Phase 1 model (no pallet tracking) to generate hints for Phase 2 (with pallet tracking). However, Phase 1 is using the **same cost structure** as Phase 2, which triggers pallet tracking creation in Phase 1, defeating the entire purpose of the two-phase approach.

**Impact:**
- Phase 1: Should be ~20-40s → Actually >10 minutes (timeout)
- Total solve: Should be ~5 minutes → Exceeds 10-minute timeout
- Warmstart: Provides no benefit because Phase 1 is as hard as Phase 2

---

## Evidence Gathered

### Phase 1 Model Structure (ACTUAL)

```
Variable Counts:
  Binary:     781
  Integer:    4,557  ← ❌ SHOULD BE ZERO
  Continuous: 100,868

Key Integer Variables:
  num_products_produced:     42 vars
  pallet_count:           4,515 vars ← ❌ ROOT CAUSE
```

### Phase 1 Model Structure (EXPECTED per documentation)

```
Variable Counts:
  Binary:     ~110 (25 pattern + ~85 weekend)
  Integer:       0  ← NO PALLET TRACKING
  Continuous: ~100,000
```

### Cost Structure Configuration

```
Pallet-Based Storage Costs:
  Fixed frozen:  $14.26 per pallet   ← CONFIGURED
  Daily frozen:  $0.98 per pallet-day ← CONFIGURED

Unit-Based Storage Costs:
  Frozen:  $0.00 per unit-day  ← NOT CONFIGURED
  Ambient: $0.00 per unit-day  ← NOT CONFIGURED
```

**Conclusion:** Cost structure is pallet-based, which triggers `pallet_count` variable creation in UnifiedNodeModel.

---

## Code Analysis

### Location: `src/optimization/unified_node_model.py`, line 4340-4345

```python
# PHASE 1: Weekly Pattern (No Pallet Tracking)
model_phase1_obj = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,  # ❌ SAME as Phase 2!
    ...
)
```

### Location: `src/optimization/unified_node_model.py`, line 4514-4519

```python
# PHASE 2: Full Binary Optimization (With Pallet Tracking)
model_phase2 = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,  # ✓ Original cost structure
    ...
)
```

**Problem:** Both phases use the **identical cost_structure** object.

### UnifiedNodeModel Pallet Variable Creation Logic

When `UnifiedNodeModel.__init__()` receives a cost_structure with:
- `storage_cost_fixed_per_pallet_frozen > 0`, OR
- `storage_cost_fixed_per_pallet_ambient > 0`, OR
- `storage_cost_per_pallet_day_frozen > 0`, OR
- `storage_cost_per_pallet_day_ambient > 0`

It creates integer `pallet_count` variables for storage cost tracking.

**Result:** Phase 1 gets 4,515 integer variables it shouldn't have.

---

## Impact Analysis

### Complexity Comparison

| Metric | Phase 1 (EXPECTED) | Phase 1 (ACTUAL) | Phase 2 | Impact |
|--------|-------------------|------------------|---------|---------|
| Binary vars | ~110 | 781 | ~280 | 7× worse |
| Integer vars | 0 | 4,557 | ~4,500 | ∞ worse |
| Solve time | 20-40s | >600s | ~300s | 15-30× slower |

### Why This Causes Timeout

1. **MIP Complexity:** Each integer variable roughly doubles the search space for branch-and-bound
2. **4,515 integer variables** in Phase 1 makes it as hard to solve as Phase 2
3. **Weekly pattern constraints** add minimal benefit when model is already this complex
4. **Warmstart becomes useless:** Phase 1 solution is just as hard to find as final solution

### MIP Expert Analysis

From MIP modeling best practices:
- **Binary variables:** Each roughly doubles potential search nodes
- **Integer variables:** Even worse than binary (larger domains)
- **Warmstart quality:** Must be from a substantially simpler/faster model to provide value

**Phase 1 is NOT simpler** → Warmstart provides zero benefit.

---

## Validation Against User Observations

### User Observation 1: "Initial inventory made it worse"
❌ **Incorrect theory** (initial inventory reduces constraints, doesn't add them)
✅ **Actual cause:** Pallet tracking in Phase 1

### User Observation 2: "Phase 1 solution too far from Phase 2 optimum"
❌ **Incorrect theory** (distance from optimum doesn't make MIP harder, just different starting point)
✅ **Actual cause:** Phase 1 IS Phase 2 (same complexity)

### User Observation 3: "Pallet tracking only in Lineage"
✅ **Partially correct:** Pallet tracking IS only for Lineage frozen storage
❌ **But:** Even 4,515 pallet variables just for Lineage is enough to kill performance

---

## Root Cause Chain

```
Cost Structure (from UI/Excel)
    ↓ has pallet_fixed_frozen = $14.26
    ↓ has pallet_daily_frozen = $0.98
    ↓
solve_weekly_pattern_warmstart()
    ↓ passes cost_structure to Phase 1 (line 4345)
    ↓
UnifiedNodeModel.__init__() [Phase 1]
    ↓ detects pallet costs in cost_structure
    ↓ creates pallet_count integer variables
    ↓ 4,515 integer vars created for Lineage frozen storage
    ↓
Phase 1 Solve
    ❌ Takes >10 minutes (timeout)
    ❌ No warmstart benefit
    ❌ Total time exceeds limit
```

---

## Solution Design

### Option 1: Create Unit-Based Cost Structure for Phase 1 (RECOMMENDED)

**Approach:**
1. In `solve_weekly_pattern_warmstart()`, create a modified cost structure for Phase 1
2. Convert pallet costs to equivalent unit costs
3. Set all pallet costs to 0.0
4. Pass modified cost_structure to Phase 1, original to Phase 2

**Conversion Formula:**
```python
# Frozen storage cost conversion (Lineage only)
pallet_cost_per_day = cost_structure.storage_cost_per_pallet_day_frozen
pallet_fixed_cost = cost_structure.storage_cost_fixed_per_pallet_frozen
units_per_pallet = 320.0

# Equivalent unit cost (amortize fixed cost over typical pallet life ~7 days)
unit_cost_per_day = (pallet_cost_per_day + pallet_fixed_cost / 7.0) / units_per_pallet
# = (0.98 + 14.26/7) / 320 = 0.00944 per unit-day

# Phase 1 cost structure
phase1_costs = copy.copy(cost_structure)
phase1_costs.storage_cost_frozen_per_unit_day = unit_cost_per_day
phase1_costs.storage_cost_per_pallet_day_frozen = 0.0
phase1_costs.storage_cost_fixed_per_pallet_frozen = 0.0
```

**Benefits:**
- Phase 1 will have ZERO integer variables (only binary)
- Same economic objective (costs are equivalent)
- Solver can optimize quickly (~20-40s)
- Warmstart will actually provide value

**Risks:**
- Unit-based costs may lead to slightly different Phase 1 solution
- Need to ensure warmstart hints are still valid for Phase 2

### Option 2: Disable Pallet Tracking Explicitly in Phase 1

**Approach:**
- Add `force_unit_based_storage=True` parameter to UnifiedNodeModel
- Skip pallet variable creation when this flag is set
- Use unit costs even if pallet costs exist

**Benefits:**
- Clean separation of concern
- More explicit control

**Risks:**
- Requires modifying UnifiedNodeModel interface
- Need to ensure costs are set appropriately

---

## Recommended Fix (Option 1 Implementation)

### Code Changes Required

**File:** `src/optimization/unified_node_model.py`
**Function:** `solve_weekly_pattern_warmstart()`
**Location:** Before Phase 1 model creation (around line 4340)

```python
# Create Phase 1 cost structure with unit-based storage (no pallet tracking)
import copy

phase1_cost_structure = copy.copy(cost_structure)

# Convert pallet costs to equivalent unit costs for Phase 1
if (cost_structure.storage_cost_per_pallet_day_frozen > 0 or
    cost_structure.storage_cost_fixed_per_pallet_frozen > 0):

    # Calculate equivalent unit cost (amortize fixed over ~7 days)
    pallet_var_cost = cost_structure.storage_cost_per_pallet_day_frozen
    pallet_fixed_cost = cost_structure.storage_cost_fixed_per_pallet_frozen
    amortization_days = 7.0  # Typical pallet retention in Lineage

    equivalent_unit_cost_frozen = (
        pallet_var_cost + pallet_fixed_cost / amortization_days
    ) / 320.0  # units per pallet

    phase1_cost_structure.storage_cost_frozen_per_unit_day = equivalent_unit_cost_frozen
    phase1_cost_structure.storage_cost_per_pallet_day_frozen = 0.0
    phase1_cost_structure.storage_cost_fixed_per_pallet_frozen = 0.0

    print(f"  Phase 1: Using unit-based storage cost (${equivalent_unit_cost_frozen:.6f}/unit-day)")
    print(f"  Equivalent to pallet cost (${pallet_var_cost:.4f}/pallet-day + ${pallet_fixed_cost:.2f} fixed)")

# Similarly for ambient if needed
if (cost_structure.storage_cost_per_pallet_day_ambient > 0 or
    cost_structure.storage_cost_fixed_per_pallet_ambient > 0):

    pallet_var_cost = cost_structure.storage_cost_per_pallet_day_ambient
    pallet_fixed_cost = cost_structure.storage_cost_fixed_per_pallet_ambient
    amortization_days = 7.0

    equivalent_unit_cost_ambient = (
        pallet_var_cost + pallet_fixed_cost / amortization_days
    ) / 320.0

    phase1_cost_structure.storage_cost_ambient_per_unit_day = equivalent_unit_cost_ambient
    phase1_cost_structure.storage_cost_per_pallet_day_ambient = 0.0
    phase1_cost_structure.storage_cost_fixed_per_pallet_ambient = 0.0

# Now use phase1_cost_structure for Phase 1
model_phase1_obj = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=phase1_cost_structure,  # ✅ MODIFIED for Phase 1
    ...
)
```

### Expected Results After Fix

**Phase 1:**
- Binary vars: ~110
- Integer vars: 42 (only `num_products_produced`)
- Solve time: 20-40 seconds

**Phase 2:**
- Binary vars: ~280
- Integer vars: ~4,500 (with pallet tracking)
- Solve time: ~250-300 seconds (with warmstart)

**Total time:** ~5-6 minutes (UNDER 10-minute limit)

---

## Testing Plan

1. **Unit Test:** Verify cost conversion formula
2. **Integration Test:** Run 6-week warmstart with fix
3. **Regression Test:** Verify 4-week still works
4. **Cost Validation:** Ensure Phase 1 and Phase 2 objectives are economically equivalent

---

## Lessons Learned

1. ✅ **Used MIP expertise:** Understood how integer variables affect solve complexity
2. ✅ **Used systematic debugging:** Evidence gathering before proposing fixes
3. ✅ **Validated against code:** Read actual implementation, not just documentation
4. ❌ **Previous attempts:** Made incorrect theories about warmstart distance/initial inventory

**Key Insight:** When documentation says "no pallet tracking" but code uses same cost_structure, documentation is WRONG (or implementation is incomplete).

---

## Appendix: Diagnostic Output

See `diagnostic_phase1_structure.py` for full analysis.

**Key Finding:**
```
EXPECTED Phase 1: Binary: ~110, Integer: 0
ACTUAL Phase 1:   Binary: 781, Integer: 4,557

❌ MISMATCH: Phase 1 has 4,557 integer variables
→ This explains the timeout!
```
