# MIP Expert Review: Comprehensive Warmstart Results

**Date:** 2025-10-21
**Subject:** Analysis of comprehensive warmstart performance
**Methodology:** MIP theory and solver behavior analysis

---

## Experimental Results

| Warmstart Type | Hints | Phase 2 Time | Gap | Cost |
|----------------|-------|--------------|-----|------|
| Partial | 307 | 635s | 63% | $1.2M-2.1M |
| **Comprehensive** | **96,332** | **639s** | **74%** | **$3.0M** |
| **Difference** | **+96,025** | **+4s** | **+11%** | **Worse** |

**Observation:** Providing 96,000+ additional hints resulted in:
- ❌ NO performance improvement (+4s worse)
- ❌ WORSE solution quality (74% gap vs 63%)
- ❌ HIGHER cost ($3.0M vs $1.2M-2.1M)

---

## MIP Theory Analysis

### Expected Behavior of Warmstart

**From MIP Best Practice #5: Preprocessing**
> "Tighten variable bounds - Improves solver performance"

**From MIP Warmstart Theory:**
1. **Good warmstart** provides feasible solution near optimum → Reduces search space
2. **Poor warmstart** provides feasible solution far from optimum → Wastes time refining bad solution
3. **Misleading warmstart** biases branching toward wrong region → WORSE than cold start

### What Happened: Misleading Warmstart

**Phase 1 Solution** (unit costs):
```
Objective: Minimize Σ(unit_cost × inventory)
Optimal strategy: Minimize inventory everywhere (linear cost)
Result: Small, distributed inventory
```

**Phase 2 Solution** (pallet costs):
```
Objective: Minimize Σ(fixed_cost × pallet_indicator + var_cost × pallet_count)
Optimal strategy: Pack efficiently into full pallets (discontinuous cost)
Result: Larger, consolidated inventory in full pallets
```

**Warmstart Effect:**
- Provided Phase 1's "small distributed inventory" as starting point
- Phase 2 starts from solution optimal for WRONG objective
- Solver explores neighborhood of Phase 1 solution
- **This neighborhood doesn't contain Phase 2's optimum!**

### Why Gap Got Worse (63% → 74%)

**MIP Branching Strategy:**

Solvers use the incumbent solution to guide branching decisions:
1. **Good incumbent** → Prune branches with worse bounds → Faster convergence
2. **Poor incumbent** → Keep exploring bad branches → Slower convergence

**What Happened:**
- Comprehensive warmstart gave solver a $744k "incumbent" based on Phase 1
- Solver tried to improve from this starting point
- But Phase 2's true optimum is in a DIFFERENT region (pallet-packed strategy)
- Solver spent time exploring Phase 1's neighborhood
- Hit timeout before finding better solution → 74% gap

**Partial warmstart (binary only):**
- Only guided SKU selection, not quantities
- Solver had more freedom to explore inventory strategies
- Found better incumbent → 63% gap

---

## Detailed Analysis: Variable-by-Variable

### Variables That Help:

**1. Binary Production Decisions (product_produced)**
- ✓ Guides which SKUs to produce on which days
- ✓ Relatively independent of cost structure
- ✓ Phase 1 and Phase 2 should agree on production timing

**2. Binary Truck Decisions (truck_used)**
- ✓ Guides truck scheduling
- ✓ Logistics-driven, not cost-structure-dependent
- ✓ Safe to warmstart

**3. Production Day Indicators (production_day)**
- ✓ Which days to run production
- ✓ Should be similar across formulations
- ✓ Safe to warmstart

### Variables That HURT:

**1. Continuous Inventory (inventory_cohort)** ❌
```
Phase 1: Minimizes inventory (linear costs favor less storage)
Phase 2: Optimizes pallet packing (fixed costs favor full pallets)
Conflict: Phase 1 inventory levels wrong for Phase 2
```

**2. Continuous Shipments (shipment_cohort)** ❌
```
Phase 1: Ships minimal quantities to avoid storage
Phase 2: Ships in pallet-sized batches for efficiency
Conflict: Shipment sizes fundamentally different
```

**3. Integer Pallet Counts (pallet_count)** ❌
```
Phase 1 derived: ceil(Phase1_inventory / 320)
Phase 2 optimal: Different based on pallet economics
Conflict: Derived values not optimal for Phase 2
```

Example:
```
Phase 1: 160 units → 1 pallet (ceil(160/320))
Phase 2: Prefers 320 units → 1 pallet (full utilization)
Warmstart locks solver toward 160-unit solution
```

---

## Why This Violates MIP Theory

### MIP Warmstart Requirements (From Literature):

**1. Solution Proximity**
- Warmstart should be "close" to target problem's optimum
- Measured by objective function distance
- **Our case:** Phase 1 cost $744k vs Phase 2 cost $2-3M (3-4× difference!)
- **Violation:** Solutions not close

**2. Formulation Similarity**
- Warmstart from relaxation (LP → MIP) works well
- Warmstart from different objective is risky
- **Our case:** Different cost structures (unit vs pallet)
- **Violation:** Economic objectives differ

**3. Incumbent Quality**
- Poor incumbent is worse than no incumbent
- Solver wastes time trying to improve bad solution
- **Our case:** Phase 1 incumbent is $744k, Phase 2 needs $2-3M solution
- **Violation:** Incumbent quality poor for Phase 2

---

## Theoretical Explanation: Why Continuous Hints Hurt

### MIP Solver Algorithm (Simplified):

```
1. Solve LP relaxation → Get lower bound
2. If integer solution → Done
3. Branch on fractional integer variable:
   - Create two subproblems
   - Use incumbent to prune branches
4. Repeat until gap < tolerance or timeout
```

### With Bad Warmstart:

```
1. Load warmstart as incumbent ($744k from Phase 1)
2. Solve LP relaxation → Lower bound
3. Gap = |incumbent - bound| / incumbent
   - If incumbent is far from true optimum, gap is LARGE
   - Solver can't prune many branches
4. Explore neighborhood of warmstart
   - But warmstart is in wrong region!
   - True optimum is elsewhere
5. Timeout with poor gap (74%)
```

### Without Warmstart or Binary-Only:

```
1. No incumbent initially (or just binary hints)
2. Solve LP relaxation → Lower bound
3. Branch-and-bound explores freely
4. Finds better incumbent naturally
5. Better gap (63%)
```

---

## Recommendation: Binary-Only Warmstart

**Extract from Phase 1:**
- ✓ product_produced (which SKUs)
- ✓ truck_used (which trucks)
- ✓ production_day (which days)
- ✓ uses_overtime (overtime decisions)

**Do NOT extract:**
- ❌ inventory_cohort (wrong quantities)
- ❌ shipment_cohort (wrong flows)
- ❌ pallet_count (derived from wrong inventory)
- ❌ production quantities (wrong levels)

**Expected Result:**
- Phase 2 gets guidance on **decisions** (which/when)
- Phase 2 optimizes **quantities** (how much) independently
- Better than comprehensive warmstart (doesn't mislead on quantities)

---

## Alternative: Disable Warmstart for 6-Week

**Given that:**
- Partial warmstart: 635s, 63% gap
- Comprehensive warmstart: 639s, 74% gap (worse!)
- Warmstart adds 62-71s Phase 1 overhead

**Test:** Solve Phase 2 directly without warmstart
```python
# Just solve Phase 2 (no Phase 1)
result = model_phase2.solve(
    solver_name='appsi_highs',
    time_limit_seconds=700,
    mip_gap=0.05,  # Relaxed
    use_warmstart=False,
)
```

**Expected:**
- No Phase 1 overhead (-71s)
- Phase 2 explores freely without bias
- Total: ~550-600s if it performs similarly to warmstart Phase 2

---

## Conclusion

**From MIP Expert Perspective:**

The comprehensive warmstart experiment validates a fundamental MIP principle:

> **"Warmstart from a different objective function can be counter-productive"**

**Providing 96,000 hints didn't help because those hints encoded Phase 1's optimal strategy (unit costs), which conflicts with Phase 2's optimal strategy (pallet costs).**

**This is a textbook example of why warmstart quality matters more than warmstart coverage.**

---

## Next Steps

1. **Test binary-only warmstart** (remove continuous hints)
2. **Test no warmstart** (solve Phase 2 directly with more time)
3. **Compare all strategies** and pick best

**Hypothesis:** Binary-only or no warmstart will outperform comprehensive warmstart.
