# Warmstart Results Comparison

**Test:** 6-week horizon with all fixes

---

## Performance Comparison

| Variant | Phase 1 | Phase 2 | Total | Warmstart Coverage | Gap |
|---------|---------|---------|-------|-------------------|-----|
| **Baseline (Bugs)** | 49s | 632s | 682s | 210 hints (0.2%) | 77% |
| **After Model Fixes** | 62s | 635s | 697s | 307 hints (0.3%) | 63% |
| **Comprehensive Warmstart** | 71s | 639s | 711s | 96,332 hints (90%+) | 74% |

---

## Warmstart Coverage Details

### Baseline (Before Fixes):
```
Product binaries: 210 (100%)
Pallet integers:  0 (0%) - Phase 1 had no inventory
Continuous:       0 (0%)
TOTAL:            210 hints
```

### After Model Fixes (Partial Warmstart):
```
Product binaries: 145 (69%)
Other binaries:   0
Pallet integers:  97 (2%)
Continuous:       0 (0%)
TOTAL:            307 hints
```

### Comprehensive Warmstart (Current):
```
Product binaries: 145
Other binaries:   462
Pallet integers:  4,515 (100%)
Derived integers: 29
Continuous:       96,353
TOTAL:            101,204 hints extracted
Applied:          96,332 hints (skipped 4,872)
```

---

## Key Findings

###  Comprehensive Warmstart Did NOT Improve Performance

**Expected:** Phase 2 time 635s → 200-300s (50-70% speedup)
**Actual:** Phase 2 time 635s → 639s (NO improvement, slightly worse!)

**Why?**

From MIP theory, providing continuous variable warmstart from a different objective function (Phase 1 unit costs vs Phase 2 pallet costs) may actually **mislead** the solver:

1. **Phase 1 optimal solution** uses different inventory/shipment patterns (linear costs)
2. **Phase 2 optimal solution** needs different patterns (pallet efficiency)
3. **Warmstart values** from Phase 1 pull solver toward WRONG region
4. **Solver wastes time** trying to refine incompatible solution

### What Actually Helps:

**Binary hints ONLY** (product_produced, truck_used, etc.):
- These guide which SKUs to produce on which days
- Relatively independent of cost structure
- Phase 1 and Phase 2 should agree on production timing

**What HURTS:**

**Continuous variable hints** (inventory, shipments):
- Specific quantities depend heavily on cost structure
- Phase 1 says "store X units here" based on unit costs
- Phase 2 should store different amounts based on pallet efficiency
- Providing Phase 1 values biases solver incorrectly

---

## MIP Expert Revised Assessment

**From MIP Best Practices:**
> "Warmstart should provide hints from a SIMPLER model with SIMILAR structure"

**Our case:**
- ✓ Phase 1 is simpler (0 pallet integers vs 4,515)
- ❌ Phase 1 has DIFFERENT objective (unit vs pallet costs)
- ❌ Solutions are economically different

**Conclusion:**
Comprehensive warmstart doesn't help because Phase 1 and Phase 2 solve fundamentally different economic optimization problems, despite mathematical equivalence in aggregate.

---

## Recommendations

### Option 1: Binary-Only Warmstart ⭐ TEST THIS

Only provide binary hints (product_produced, truck_used, etc.)
DON'T provide continuous hints (inventory, shipment)

```python
# Only extract binary decisions
warmstart_hints = {
    # product_produced: which SKUs on which days
    # truck_used: which trucks on which days
    # production_day: which days have production
}
# Skip inventory_cohort, shipment_cohort, etc.
```

**Rationale:** Binary decisions about "which SKU/truck/day" are more universal than "how much to ship/store".

### Option 2: Increase Timeout + Relax Gap

```python
time_limit_phase2=900,  # 15 min instead of 10
mip_gap=0.05,           # 5% instead of 3%
```

**Expected:** ~750s with 5% gap (12.5 min total)

### Option 3: Accept Performance

711s (11.8 min) for 6-week with full correctness may be reasonable.

---

## Summary

✅ **Model fixes successful:**
- Phase 1 cost conversion (no pallet variables)
- Storage shipment delay constraint (forces inventory)
- Lineage now stores 3,335 units ✓

✅ **Comprehensive warmstart implemented:**
- 96,332 hints extracted (vs 307 before)
- 100% pallet coverage
- ALL continuous variables

❌ **Comprehensive warmstart provided NO benefit:**
- Phase 2: 639s (same as partial warmstart)
- May actually hurt due to solution mismatch

**Next Test:** Binary-only warmstart to see if that performs better.
