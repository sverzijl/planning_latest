# Critical Findings: Warmstart Solution Mismatch

**Date:** 2025-10-21
**Issue:** Warmstart enhancements investigation
**Status:** 🚨 **FUNDAMENTAL PROBLEM DISCOVERED**

---

## Executive Summary

**The warmstart approach has a fatal flaw:** Phase 1 and Phase 2 are solving fundamentally different economic problems.

- **Phase 1** (unit costs): Avoids frozen storage entirely → $740,345 cost
- **Phase 2** (pallet costs): Requires frozen storage (Lineage) → $1.2M-3.4M cost

**Result:** Warmstart provides ZERO benefit because solutions are too different.

---

## Evidence

### Phase 1 Solution Analysis

```
Frozen inventory cohorts: 4,515 total
Frozen inventory with units > 0: 0
Lineage frozen usage: 0 units
```

**Phase 1 uses NO frozen storage at all.**

### Cost Comparison

| Metric | Phase 1 | Phase 2 | Ratio |
|--------|---------|---------|-------|
| Cost | $740,345 | $1,200,860 - $3,387,691 | 1.6× - 4.6× |
| Frozen inventory | 0 units | Required for pallets | N/A |
| MIP gap | 0% (optimal) | 30-77% | Large |
| Solve time | 49s | 634s (timeout) | 13× |

### Why This Happens

**Unit-Based Costs (Phase 1):**
- Frozen storage: $0.009429/unit-day (linear, continuous)
- Ambient storage: $0.00/unit-day (free!)
- **Optimal strategy:** Use ambient everywhere, avoid frozen

**Pallet-Based Costs (Phase 2):**
- Frozen storage: $14.26 fixed + $0.98/pallet-day (discontinuous, integer)
- Ambient storage: $0.00/pallet-day (free!)
- **Optimal strategy:** Pack efficiently into pallets at Lineage (frozen buffer)

**The problem:** These are economically DIFFERENT objectives!

---

## Why Enhancements Failed

### High Priority: Pallet Warmstart Hints

**Result:** ❌ Cannot extract pallet hints from Phase 1

**Reason:** Phase 1 has zero frozen inventory, so there are no pallet values to extract for Lineage.

### Medium Priority: Bound Tightening

**Result:** ⚠️ Applied 30,765 + 4,515 bounds, but minimal benefit

**Reason:** Phase 1 max inventory patterns don't reflect Phase 2's optimal frozen buffer strategy.

---

## Root Cause: Cost Conversion Error

The cost conversion formula is mathematically correct but economically flawed:

**Current Conversion:**
```
Frozen unit cost = ($0.98 + $14.26/7) / 320 = $0.009429/unit-day
Ambient unit cost = $0.00/unit-day
```

**Problem:** This makes frozen storage 0.009429× more expensive than ambient on a per-unit basis. Phase 1 will NEVER use frozen storage when ambient is free!

**Phase 2 Reality:** The fixed cost ($14.26/pallet) means:
- Storing 320 units costs $21.12 (7 days)
- Storing 160 units ALSO costs $21.12 (same fixed cost!)
- Phase 2 prefers packing efficiently into full pallets

---

## MIP Expert Analysis

From MIP warmstart theory:

**Warmstart Requirement:** Phase 1 must be:
1. ✓ Simpler (fewer integer variables) - ACHIEVED
2. ❌ Similar solution structure - NOT ACHIEVED
3. ❌ Economic equivalence - VIOLATED

**Current Status:**
- Phase 1 is simpler (0 vs 4,515 pallet integers)
- BUT solutions are completely different
- Warmstart hints guide solver to wrong region

**Conclusion:** This warmstart is **anti-helpful** - it starts Phase 2 in a region far from the optimum.

---

## Options Forward

### Option 1: Abandon Warmstart (RECOMMENDED)

**Just solve Phase 2 directly without warmstart.**

**Rationale:**
- Phase 1 warmstart is misleading (wrong solution structure)
- Phase 2 cold start might be better than wrong warmstart
- Saves 49s of Phase 1 time

**Test:**
```python
# Solve Phase 2 directly (no warmstart)
result = model_phase2.solve(
    solver_name='appsi_highs',
    time_limit_seconds=700,  # Give it the full time
    mip_gap=0.03,
    use_warmstart=False,  # Disable warmstart
)
```

**Expected:** Might actually perform better than with warmstart!

### Option 2: Fix Cost Conversion (COMPLEX)

Make Phase 1 unit costs reflect the pallet packing advantage:

**Idea:** Frozen unit costs should be CHEAPER than ambient for quantities near pallet multiples.

```python
# Make frozen competitive for pallet-sized quantities
# This encourages Phase 1 to use frozen buffer like Phase 2 would
frozen_unit_cost = $0.003/unit-day  # Lower than current $0.009429
```

**Problem:** This loses economic equivalence and is essentially "gaming" Phase 1.

### Option 3: Increase Phase 2 Time Limit (SIMPLE)

**Just give Phase 2 more time:**

```python
time_limit_phase2=900,  # 15 minutes instead of 10
```

**With warmstart total:** ~950s (15.8 min)
**Without warmstart:** ~900s (15 min)

**Might be acceptable for 6-week planning horizon.**

### Option 4: Relax MIP Gap (PRAGMATIC)

```python
mip_gap=0.05,  # 5% instead of 3%
```

**Result:** Solver terminates earlier with acceptable solution.

---

## Recommendation

**OPTION 1 + OPTION 4 Combined:**

1. **Disable warmstart** for 6-week horizons (it's counterproductive)
2. **Relax MIP gap** to 5%
3. **Give Phase 2 full 10 minutes** (no Phase 1 overhead)

**Expected Performance:**
- Time: ~600s (10 min)
- Gap: ~5% (acceptable)
- Cost: Better than current (no warm start leading astray)

**Alternative for shorter horizons:**
- Keep warmstart for 4-week (works well there)
- Disable for 6+ weeks (solution mismatch issue)

---

## Files Modified (Enhancement Attempt)

1. `src/optimization/unified_node_model.py` - Added pallet hints + bound tightening
2. `tests/test_warmstart_baseline.py` - Baseline capture
3. `tests/test_warmstart_enhancements.py` - Validation tests

**These enhancements can be kept** (they don't hurt), but they provide minimal benefit for this specific problem where Phase 1 and Phase 2 solutions diverge.

---

## Next Steps

**User Decision Required:**

1. Keep warmstart enhancements (minimal benefit, no harm)?
2. Try Option 1 (no warmstart, just solve Phase 2)?
3. Increase Phase 2 timeout + relax gap?
4. Accept 11-minute solve time as reasonable for 6-week planning?

---

## Lessons Learned

✅ Systematic debugging revealed the real issue
✅ MIP expertise identified warmstart requirements
❌ Cost conversion created economically different problems
❌ Warmstart can be counter-productive if solutions diverge

**Key Insight:** Economic equivalence in aggregate ($21.12 total) doesn't guarantee similar solution structures. The SHAPE of the cost function matters!
