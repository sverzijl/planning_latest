# MIP Expert: Reformulation Strategies for Pallet Optimization

**Problem:** 4,515 integer pallet variables → 1 hour to reach 27% gap
**Goal:** Reduce search space or improve warmstart quality

Using MIP modeling techniques to explore creative reformulations.

---

## Current Formulation Analysis

**Variables:**
```
pallet_count[node, prod, prod_date, curr_date, state] ∈ ℤ₊
Bounds: 0 ≤ pallet_count ≤ 61 (max_inventory/320)
Count: 4,515 integer variables
```

**Constraints:**
```
pallet_count * 320 >= inventory_cohort  (ceiling constraint)
```

**Objective:**
```
Cost += ($14.26 + $0.98) * pallet_count  (per pallet costs)
```

**Analysis:** This is standard integer linear formulation. Cost is LINEAR in pallet_count (not true fixed cost with binary indicator).

---

## Strategy 1: Binary + Integer Decomposition ⭐⭐⭐

**MIP Technique:** Discontinuous Variables (Technique #2)

**Current:** `pallet_count ∈ {0, 1, 2, ..., 61}`

**Reformulation:**
```
full_pallets[cohort] ∈ {0, 1, 2, ..., 60}  (integer)
has_partial[cohort] ∈ {0, 1}                (binary)

pallet_count = full_pallets + has_partial

Constraints:
  full_pallets * 320 + has_partial * 160 >= inventory  (tighter bound)
  has_partial ≤ 1  (at most 1 partial pallet)
```

**Benefits:**
- Reduces integer domain: 61 values → 60 values (small)
- Adds 4,515 binary variables (but binary faster than general integer)
- **Key insight:** Most cohorts have 0-2 pallets, rarely >2
- Solver can branch on binary first (faster), then refine integers

**Cost Analysis:**
- +4,515 binary variables
- Same number of integer variables
- **Expected:** 10-20% speedup (binary branching more efficient)

**Verdict:** ⭐⭐⭐ WORTH TESTING - Small change, potential benefit

---

## Strategy 2: Batch-Level Binary in Phase 1 ⭐⭐⭐⭐⭐

**User's insight:** Make Phase 1 cost structure closer to Phase 2

**Current Phase 1:**
```
Cost = unit_cost * inventory  (pure linear, no discreteness)
Result: Minimizes inventory everywhere
```

**Proposed Phase 1:**
```
has_inventory[node, prod, prod_date, curr_date, state] ∈ {0, 1}
inventory >= 0.01 * has_inventory  (force binary when inventory > 0)
Cost = unit_cost * inventory + batch_fee * has_inventory

where:
  batch_fee = $14.26 (one-time cost per batch with inventory)
  unit_cost = $0.98/320 = $0.003/unit-day (variable only)
```

**Benefits:**
- Captures "lumpiness" of pallet costs
- Phase 1 solution prefers consolidated inventory (like Phase 2!)
- Adds only ~10,000 binary variables to Phase 1 (still tractable)
- **Phase 1 and Phase 2 solutions structurally similar!**
- Warmstart quality dramatically improves

**MIP Formulation:**
```
inventory_cohort[cohort] ≤ M * has_inventory_cohort[cohort]
Cost = $0.003 * inventory + $14.26 * has_inventory
```

**Expected Impact:**
- Phase 1: 60s → 120-180s (adds binaries, but manageable)
- Phase 2: Warmstart guides toward pallet-efficient solution
- **Better warmstart → 30-50% Phase 2 speedup possible**

**Verdict:** ⭐⭐⭐⭐⭐ **MOST PROMISING** - Aligns Phase 1 and Phase 2 objectives!

---

## Strategy 3: Piecewise Linear Phase 1 Cost ⭐⭐

**MIP Technique:** Piecewise Linear Approximation (Technique #7)

**Idea:** Approximate pallet cost function in Phase 1

**Formulation:**
```
Breakpoints: 0, 160, 320, 640, 960 units
Costs:       0, $10.50, $21, $42, $63 (pallet costs)

Use SOS2 piecewise linear:
  inventory = Σ λᵢ * breakpoint_i
  cost = Σ λᵢ * cost_i
  Σ λᵢ = 1
  Adjacent λ's only (SOS2)
```

**Benefits:**
- Captures non-linearity of pallet costs
- Phase 1 solution closer to Phase 2
- SOS2 more efficient than general integer

**Drawbacks:**
- Adds complexity to Phase 1
- SOS2 still requires integer branching
- May not be faster than current approach

**Verdict:** ⭐⭐ Interesting but complex, batch-level binary simpler

---

## Strategy 4: Conservative +1 Pallet Heuristic ⭐⭐⭐

**User's idea:** Assume each batch needs 1 extra pallet

**Phase 1 Constraint:**
```
pallet_estimate[cohort] = floor(inventory[cohort] / 320) + 1
Cost = pallet_cost * pallet_estimate
```

**BUT THIS REQUIRES FLOOR which needs integers!**

**Alternative - Conservative Upper Bound:**
```
Phase 1: pallet_upper = ceil(inventory * 1.3 / 320)  (30% buffer)
Use this as WARM START for Phase 2 pallet_count
```

**Benefits:**
- Provides better pallet hints (conservative but directionally correct)
- Doesn't add integers to Phase 1

**Implementation:**
```python
# In warmstart extraction:
for cohort in Phase1.inventory_cohort:
    units = value(inventory_cohort[cohort])
    # Conservative estimate with buffer
    pallets_conservative = ceil(units * 1.3 / 320)
    warmstart_hints[cohort] = pallets_conservative
```

**Verdict:** ⭐⭐⭐ Easy to implement, might help warmstart quality

---

## Strategy 5: Aggregate Pallet Variables ⭐⭐⭐⭐

**MIP Technique:** Variable aggregation (reduce integer count)

**Current:**
```
pallet_count[node, prod, prod_date, curr_date, state]  (4,515 variables)
```

**Proposed:**
```
total_pallets[node, state, curr_date]  (~132 variables instead!)

Sum constraint:
  total_pallets[node, state, date] = Σ pallet_count[..., date, state]

Remove pallet_count integers, use continuous instead
Only integerize the aggregate
```

**Benefits:**
- **Massive reduction:** 4,515 → ~132 integer variables (97% reduction!)
- Much faster MIP solve
- Loses granularity but pallet cost is aggregate anyway

**Drawbacks:**
- Can't track which specific cohorts use pallets
- May over-allocate pallets

**Verdict:** ⭐⭐⭐⭐ **VERY PROMISING** - Huge variable reduction!

---

## Strategy 6: Fix Small Cohorts ⭐⭐⭐⭐

**MIP Technique:** Variable fixing based on heuristic

**From Phase 1 data:**
- Most cohorts have < 640 units (2 pallets)
- Can safely bound: pallet_count ∈ {0, 1, 2}

**Implementation:**
```python
for cohort in pallet_count:
    max_inv_phase1 = phase1_inventory[cohort]

    if max_inv_phase1 < 320:
        # Small cohort - at most 1 pallet
        model.pallet_count[cohort].setub(1)
    elif max_inv_phase1 < 640:
        # Medium cohort - at most 2 pallets
        model.pallet_count[cohort].setub(2)
    elif max_inv_phase1 < 960:
        # Large cohort - at most 3 pallets
        model.pallet_count[cohort].setub(3)
```

**Benefits:**
- Dramatically reduces domain size
- Most variables become {0,1} or {0,1,2}
- **Much smaller search space**

**Current bound tightening** already does this with 1.5× safety factor!
Could make it more aggressive (1.1× safety factor)

**Verdict:** ⭐⭐⭐⭐ Already partially implemented, make more aggressive!

---

## Strategy 7: Lazy Pallet Constraints ⭐⭐

**MIP Technique:** Lazy constraint generation

**Idea:** Only create pallet variables for "significant" cohorts

**Implementation:**
```python
# Only create pallet_count if Phase 1 shows inventory > threshold
pallet_cohort_index = [
    (n, p, pd, cd, s) for (n, p, pd, cd, s) in cohort_index
    if phase1_max_inventory[n, p, s] > 100 units  # Threshold
]
```

**Benefits:**
- Reduces pallet variable count (maybe 4,515 → 1,000)
- Tiny cohorts use continuous approximation

**Drawbacks:**
- Less accurate for small cohorts
- Complex to implement

**Verdict:** ⭐⭐ Interesting but risky

---

## Strategy 8: Phase 1 with Pallet-Packing Incentive ⭐⭐⭐⭐⭐

**User's brilliant insight:** Make Phase 1 prefer full pallets!

**Proposed Phase 1 Cost:**
```python
# Instead of pure unit cost:
unit_cost = $0.003/unit-day

# Use stepped cost that incentivizes 320-unit multiples:
if inventory % 320 close to 0:
    cost = unit_cost * inventory  (cheap - full pallet)
else:
    cost = unit_cost * inventory + $5  (penalty for partial)

# Approximate with:
full_pallet_bonus = -$2 per full pallet
fractional_penalty = +$5 per fractional pallet

# Continuous approximation:
num_full_pallets_approx = floor(inventory / 320)  # Continuous relaxation
fractional_units = inventory - (num_full_pallets_approx * 320)

Cost = unit_cost * inventory + penalty * (fractional_units / 320)
```

**Simpler Version:**
```python
# Phase 1 objective:
Cost = unit_cost * inventory + discrete_penalty * (inventory mod 320)

# Linearize modulo using:
remainder[cohort] ∈ [0, 320]
inventory = 320 * quotient + remainder
Cost += penalty * remainder / 320
```

**Even Simpler - No Integers:**
```python
# Add quadratic penalty for non-multiples (linearize with piecewise):
Cost = unit_cost * inventory + small_penalty * (inventory/320 - floor(inventory/320))

# Continuous approximation:
# Penalize fractional pallets slightly
```

**Best Implementation:**
```python
# Phase 1: Add small per-cohort fee if inventory > 0
has_inventory[cohort] ∈ {0,1}
inventory[cohort] ≤ M * has_inventory[cohort]

Cost = unit_cost * inventory + $7 * has_inventory
```

Where $7 ≈ half the fixed pallet cost, capturing "lumpiness"

**Verdict:** ⭐⭐⭐⭐⭐ **EXCELLENT** - Makes Phase 1 prefer consolidated inventory!

---

## Strategy 9: Two-Tier Integer Variables ⭐⭐⭐

**Idea:** Separate cohorts by size

**Tier 1 (Small cohorts, ≤2 pallets): 90% of cohorts**
```
pallet_count ∈ {0, 1, 2}  (small domain)
```

**Tier 2 (Large cohorts, >2 pallets): 10% of cohorts**
```
pallet_count ∈ {0, 1, ..., 61}  (full domain)
```

**Implementation:**
```python
if max_inv_phase1[cohort] < 640:
    # Small cohort
    model.pallet_count[cohort] = Var(within={0, 1, 2})
else:
    # Large cohort
    model.pallet_count[cohort] = Var(within=NonNegativeIntegers, bounds=(0, 61))
```

**Benefits:**
- Most variables have tiny domain ({0,1,2})
- Solver branches efficiently on small domains

**Verdict:** ⭐⭐⭐ Good, similar to aggressive bound tightening

---

## Strategy 10: Valid Inequality Cuts ⭐⭐⭐⭐

**MIP Technique:** Add valid inequalities based on Phase 1

**From Phase 1 solution:**
```
If product P is rarely stored at node N:
  → Add: Σ pallet_count[N, P, *, *, *] ≤ small_number

If node N has low total inventory:
  → Add: Σ pallet_count[N, *, *, date, *] ≤ capacity_estimate

If certain products never stored frozen:
  → Fix: pallet_count[*, P, *, *, frozen] = 0
```

**Example:**
```python
# If Phase 1 shows SKU_A never uses >320 units at Lineage:
for all cohorts with (Lineage, SKU_A, ...):
    pallet_count <= 1
```

**Benefits:**
- Reduces feasible region
- No new variables
- Just constraints based on Phase 1 insights

**Verdict:** ⭐⭐⭐⭐ Easy to add, likely helps

---

## RANKED RECOMMENDATIONS

### 🥇 **TIER 1: High Impact, Low Risk**

**1A. Batch-Level Binary in Phase 1** (Strategy 8)
```python
# Phase 1 with discrete cost approximation:
has_inventory[cohort] ∈ {0,1}
Cost = $0.003 * inventory + $7 * has_inventory
```

**Expected:**
- Phase 1: 60s → 120-180s (adds ~10k binaries)
- Phase 2: Better warmstart → 30-50% speedup
- **Net: ~400-500s total** (vs current 709s)

**2A. Aggressive Bound Tightening** (Strategy 6 enhancement)
```python
# Tighten bounds more aggressively from Phase 1:
safety_factor = 1.1  # vs current 1.3 or 1.5

if phase1_max < 320:
    pallet_count.setub(1)  # Force binary-like
elif phase1_max < 640:
    pallet_count.setub(2)  # Very small domain
```

**Expected:**
- No Phase 1 change
- Phase 2: Smaller domains → 10-20% speedup
- **Easy to implement**

**3A. Valid Inequalities from Phase 1** (Strategy 10)
```python
# Add cuts based on Phase 1 patterns:
- Product-node aggregates
- Date-wise capacity limits
- Zero-inventory product-state pairs
```

**Expected:**
- Minimal overhead
- 5-15% speedup from tighter LP relaxation

### 🥈 **TIER 2: Moderate Impact**

**1B. Aggregate Pallet Variables** (Strategy 5)
```
total_pallets[node, state, date] instead of per-cohort
4,515 → ~132 integer variables (97% reduction!)
```

**Risk:** Loses cohort-level granularity, might over-allocate

**2B. Binary + Integer Decomposition** (Strategy 1)
**3B. Two-Tier Variables** (Strategy 9)

### 🥉 **TIER 3: Complex, Uncertain Benefit**

**1C. Piecewise Linear Phase 1** (Strategy 2) - Adds complexity
**2C. Lazy Constraints** (Strategy 7) - Implementation risk

---

## CREATIVE COMBINATION STRATEGY ⭐⭐⭐⭐⭐

**Combine Tier 1 strategies:**

### Phase 1 Enhanced:
```python
# Add batch-level binary to capture discreteness:
has_inventory[cohort] ∈ {0,1}
inventory[cohort] ≤ 20,000 * has_inventory[cohort]

# Cost structure:
unit_var_cost = $0.98 / 320 = $0.003/unit-day
batch_fixed_cost = $14.26 * 0.5 = $7 (half of pallet fixed)

Cost_phase1 = Σ (unit_var_cost * inventory + batch_fixed_cost * has_inventory)
```

**Effect:** Phase 1 now prefers to consolidate inventory (like Phase 2), not minimize it!

### Phase 2 Enhanced:
```python
# Use Phase 1 has_inventory as additional warmstart:
for cohort:
    if phase1_has_inventory[cohort] == 0:
        pallet_count[cohort].setub(0)  # Fix to zero
    elif phase1_inventory[cohort] < 320:
        pallet_count[cohort].setub(1)  # Force 0 or 1
    else:
        pallet_count[cohort].setub(ceil(phase1_inv * 1.1 / 320))

# Also warmstart pallet_count:
pallet_warmstart[cohort] = ceil(phase1_inv / 320)
```

**Expected Results:**
- Phase 1: ~150-200s (has_inventory binaries added)
- Phase 2: ~200-300s (much better warmstart + tight bounds)
- **Total: ~350-500s (6-8 minutes!)** ✅ Under 10-minute target!

---

## MY TOP RECOMMENDATION

**Implement Strategy 8 (Batch-Level Binary in Phase 1):**

This makes Phase 1 and Phase 2 solve SIMILAR economic problems:
- Both have discrete costs (batch fee vs pallet cost)
- Both prefer consolidated inventory
- Both avoid tiny scattered inventory

**The warmstart will finally be HIGH QUALITY because solutions are structurally similar!**

---

## Implementation Priority

1. ⭐⭐⭐⭐⭐ **Phase 1 Batch-Level Binary** (Strategy 8)
2. ⭐⭐⭐⭐ **Aggressive Bound Tightening** (Strategy 6)
3. ⭐⭐⭐⭐ **Valid Inequalities** (Strategy 10)
4. ⭐⭐⭐ **Conservative Pallet Hints** (Strategy 4)
5. ⭐⭐⭐ **Binary + Integer Decomp** (Strategy 1)

**Quick wins:** #2, #3, #4 (no Phase 1 changes)
**Game changer:** #1 (aligns objectives)

Would you like me to implement the batch-level binary in Phase 1?
