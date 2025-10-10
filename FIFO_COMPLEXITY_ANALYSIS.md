# FIFO Inventory Management: Would It Reduce Solver Complexity?

## Question

If we enforce FIFO (First-In-First-Out) inventory management - requiring older inventory to be consumed before newer inventory - would this reduce the solver complexity and eliminate the performance cliff?

## TL;DR Answer

**Potentially YES for the right implementation** - but with important caveats.

**Best approach:** Age-weighted holding costs (simple implementation, moderate symmetry breaking, no model size increase)

**Expected impact:** 2-3x speedup on tight capacity problems (Week 3 cliff: >60s → 20-30s estimated)

**Not a silver bullet:** Still need rolling horizon for full 29-week dataset

---

## Current Model Behavior

### Inventory Tracking (No Age Tracking)

**Current model:** `inventory[destination, product, date]`

This is an **aggregated quantity** with no tracking of production date or age:

```python
inventory[dest, prod, June_10] = 5000 units
```

**This could be:**
- 5000 units produced June 5
- 5000 units produced June 9
- 2000 from June 5 + 3000 from June 9
- **The model doesn't care**

### Inventory Balance

```python
inventory[t] = inventory[t-1] + arrivals[t] - demand[t]
```

**No constraint on consumption order** - the model can freely mix old and new inventory.

### Current Holding Cost

**Location:** `src/optimization/integrated_model.py` line 1464

```python
inventory_cost += holding_cost_per_unit_day * model.inventory[dest, prod, date]
```

**This is flat** - doesn't increase with age:
- 1-day-old inventory: $0.01/unit/day
- 10-day-old inventory: $0.01/unit/day (same cost!)

**Problem:** No incentive to consume old inventory first

---

## How This Creates Temporal Symmetry

### Example: Week 2 Bottleneck Problem

**Scenario:**
- Week 2 demand: 82,893 units
- Week 2 capacity: 78,400 units
- Shortage: 4,493 units must come from other weeks

**Strategy A: Produce Early**
```
Week 1: Produce 87,635 units (extra 4,493)
        → Hold 4,493 units inventory
Week 2: Produce 78,400 units (max capacity)
        → Consume inventory from Week 1
Week 3: Produce 83,401 units (normal)

Cost: Extra production cost Week 1 + holding cost
```

**Strategy B: Produce Late**
```
Week 1: Produce 83,142 units (normal)
Week 2: Produce 78,400 units (max capacity)
        → 4,493 unit shortage
Week 3: Produce 87,894 units (extra 4,493)
        → "Backfill" some Week 2 demand if timing allows

Cost: Extra production cost Week 3 + potential expediting
```

**Current Model:** If holding costs are low, these strategies have **similar total costs**.

**Result:** Solver explores both branches → temporal symmetry → exponential search tree

---

## How FIFO Would Break Symmetry

### FIFO Rule

**Definition:** Inventory produced/arriving earlier MUST be consumed before inventory produced/arriving later.

### Impact on Strategy Symmetry

**With FIFO enforced:**

**Strategy A: Produce Early**
```
Week 1: Produce 87,635 units
Week 2: MUST consume Week 1 inventory first (FIFO rule)
        → Week 1 inventory = 4,493 units at start of Week 2
        → Week 2 production can only fill remaining demand
Week 3: Normal production

FIFO compatible: ✅
```

**Strategy B: Produce Late**
```
Week 1: Produce 83,142 units
Week 2: Consume all Week 1 production
        → No Week 1 inventory left
        → Shortage of 4,493 units
Week 3: Produce 87,894 units
        → Try to "backfill" Week 2 demand

FIFO violation: ❌
Week 3 production is NEWER than Week 2 demand date
Cannot go back in time to satisfy earlier demand
```

**Conclusion:** Strategy B becomes infeasible with FIFO!

**Impact:** Eliminates temporal symmetry → reduces search tree → faster solve

---

## Implementation Options

### Option A: Age-Stratified Inventory (Accurate but Complex)

**Approach:** Track inventory by production date

```python
inventory[dest, prod, delivery_date, production_date] >= 0
```

**FIFO Constraint:**
```python
# For each date, consume oldest inventory first
# If inventory from production_date_1 > 0, then
# inventory from production_date_2 must be 0 for production_date_2 > production_date_1

for prod_date_old in dates:
    for prod_date_new in dates:
        if prod_date_new > prod_date_old:
            # If old inventory exists, new inventory must be zero
            inventory[dest, prod, date, prod_date_new] <= M * (1 - has_old_inventory)
```

**Pros:**
- Exact FIFO enforcement
- Can track exact age for shelf life

**Cons:**
- ❌ **Massive variable explosion:** O(dates^2) inventory variables
- ❌ **Many new constraints:** O(dates^2) FIFO constraints
- ❌ **Likely slower overall** despite symmetry breaking

**Verdict:** Too complex, **not recommended**

---

### Option B: Age-Weighted Holding Costs (Simple Approximation)

**Approach:** Make holding cost increase with inventory age

**Current:**
```python
inventory_cost = holding_cost * inventory[dest, prod, date]
```

**Modified:**
```python
# Track weighted inventory age
inventory_age[dest, prod, date] = (
    (inventory_age[dest, prod, date-1] * inventory[dest, prod, date-1] + 1 * arrivals[date])
    / (inventory[dest, prod, date] + eps)
)

inventory_cost = holding_cost * inventory[dest, prod, date] * inventory_age[dest, prod, date]
```

**Or simpler - progressive cost:**
```python
# Holding cost increases with time
inventory_cost = holding_cost * inventory[dest, prod, date] * (date - start_date).days
```

**FIFO Incentive:**
- Old inventory costs more to hold
- Model naturally prefers to consume old inventory first
- Not strict FIFO, but approximate

**Pros:**
- ✅ **Simple implementation:** Just change objective function
- ✅ **No new variables:** Reuse existing inventory variables
- ✅ **No new constraints**
- ✅ **Breaks temporal symmetry** (produce early is now cheaper than late due to cumulative holding)

**Cons:**
- ⚠️ Not strict FIFO (can violate in pathological cases)
- ⚠️ Nonlinear objective (age tracking) - but can approximate linearly

**Verdict:** **Best option** - good symmetry breaking with minimal complexity

---

### Option C: Explicit FIFO Constraints (Moderate Complexity)

**Approach:** Add constraints forcing consumption before production

```python
# Simplified FIFO rule: If inventory > 0, then new production is held
# (Consumed inventory must come from stock before using new production)

for date in dates:
    if inventory[dest, prod, date-1] > 0:
        # Demand on date must be satisfied from inventory first
        demand_from_inventory[dest, prod, date] >= min(demand[dest, prod, date], inventory[dest, prod, date-1])

        # New arrivals go to inventory
        inventory[dest, prod, date] = inventory[dest, prod, date-1] + arrivals[date] - demand_from_inventory[date]
```

**Pros:**
- ✅ Stricter FIFO than Option B
- ✅ Moderate complexity

**Cons:**
- ⚠️ New variables: `demand_from_inventory[dest, prod, date]`
- ⚠️ New constraints: O(destinations × products × dates)
- ⚠️ May create infeasibility in edge cases

**Verdict:** Possible but more complex than Option B

---

## Expected Performance Impact

### Symmetry Reduction Analysis

**Current (No FIFO):**
- Week 2 bottleneck creates ~2-4 equivalent strategies
- Each strategy has different production timing
- Solver explores all branches

**With FIFO (Option B - Age-weighted costs):**
- Only 1-2 viable strategies (produce early strongly favored)
- "Produce late" becomes expensive due to higher cumulative holding
- Reduces branching by ~50-75%

### Estimated Impact on Fractional Binaries

**Hypothesis:** FIFO constraints tighten LP relaxation

**Current (Week 3):**
- Estimated 60-90 fractional binaries in LP relaxation
- Creates search tree: 2^60 to 2^90 nodes

**With FIFO:**
- Estimated 40-60 fractional binaries (33% reduction)
- Creates search tree: 2^40 to 2^60 nodes
- **Reduction:** 2^20 to 2^30 fewer nodes (1 million to 1 billion reduction!)

### Expected Solve Time Improvement

**Week 3 Problem:**
- Current: >60s timeout
- With FIFO Option B: **20-30s** (estimated 2-3x speedup)
- With FIFO Option A: **Slower** (added complexity dominates)

**Week 3 @ 60% Utilization:**
- Current: 7.15s
- With FIFO: **3-4s** (estimated 2x speedup)

**Why not more improvement?**
- FIFO only breaks temporal symmetry
- Truck assignment symmetry still exists (5 trucks to same destination)
- Binary variable count unchanged (300 binaries)
- Planning horizon length still dominant factor

---

## Practical Considerations

### Alignment with Real Operations

**Real warehouses use FIFO for perishable goods:**
- Bread has limited shelf life (10-14 days ambient)
- Older product sold first for freshness
- Regulatory compliance (food safety)

**Model should reflect reality:**
- Current model allows unrealistic mixing
- FIFO makes model more accurate

### Shelf Life Management

**Current model:**
- Filters routes with transit > 10 days
- But doesn't track inventory age at destinations

**With age tracking (Option B):**
- Can add shelf life constraints: `age[dest, prod, date] <= max_age`
- More realistic spoilage modeling
- Better inventory planning

### Implementation Simplicity

**Option B is straightforward:**

```python
# Modified objective (simplified linear version)
# Instead of: inventory_cost = cost * inventory[d,p,t]
# Use: inventory_cost = cost * inventory[d,p,t] * t

# This makes holding inventory longer more expensive
# Naturally incentivizes FIFO without strict constraints
```

**Estimated implementation:** 10-20 lines of code, minimal testing needed

---

## Recommendation

### ✅ IMPLEMENT Option B: Age-Weighted Holding Costs

**Rationale:**
1. **Simple implementation** - Modify objective function only
2. **No model size increase** - No new variables or constraints
3. **Moderate symmetry breaking** - Expected 2-3x speedup on tight problems
4. **More realistic** - Aligns with actual warehouse operations
5. **Low risk** - Easy to test and revert if ineffective

### Implementation Approach

**Step 1: Modify objective function**

```python
# Current (line 1464):
inventory_cost += holding_cost_per_unit_day * model.inventory[dest, prod, date]

# Modified:
days_held = (date - self.start_date).days
inventory_cost += holding_cost_per_unit_day * model.inventory[dest, prod, date] * days_held
```

**Step 2: Tune holding cost**

Current: `holding_cost = $0.01/unit/day` (estimate)

With age weighting, this becomes:
- Day 1: $0.01 × 1 = $0.01/unit
- Day 10: $0.01 × 10 = $0.10/unit
- Day 20: $0.01 × 20 = $0.20/unit

**May need to reduce base rate** to avoid over-penalizing inventory:
- New base: `holding_cost = $0.001 - $0.005/unit/day`
- This maintains reasonable total holding costs

**Step 3: Test on Week 3 problem**

Run `test_no_bottleneck.py` with modified objective:
- Expected: 20-30s instead of >60s
- If faster: Success! ✅
- If slower or similar: Revert change

### Expected Timeline

- Implementation: 30 minutes
- Testing: 1 hour
- **Total effort:** ~2 hours

---

## Alternative: Combine with Other Optimizations

FIFO alone won't solve the 29-week problem. **Combine strategies:**

### Recommended Stack:

1. ✅ **Sparse indexing** (already implemented) - 72.7% variable reduction
2. ✅ **Age-weighted holding costs** (FIFO approximation) - 2-3x speedup
3. ⏳ **Lexicographic truck ordering** (break truck symmetry) - 3-5x speedup
4. ⏳ **Rolling horizon** (4-6 weeks) - Necessary for full dataset

**Combined effect (estimated):**
```
Sparse indexing:        1.3x speedup
Age-weighted costs:     2.5x speedup
Truck ordering:         4x speedup
Combined:               1.3 × 2.5 × 4 = 13x speedup total

Week 3: >60s → ~5s (feasible)
Week 6: Could be ~30-60s (feasible with commercial solver)
Full 29 weeks: Still need rolling horizon
```

---

## Potential Concerns

### Concern 1: "Won't age weighting make the objective nonlinear?"

**Answer:** The formulation above is LINEAR:
```python
inventory_cost = sum(cost * inventory[d,p,t] * t for all d,p,t)
```
`t` is a constant (date index), not a variable. This is a linear expression.

### Concern 2: "What if the increased holding costs make solutions infeasible?"

**Answer:**
- Inventory is still allowed (not forced to zero)
- Just more expensive to hold long-term
- Can tune `holding_cost` parameter to balance
- If infeasibility occurs, reduce holding cost rate

### Concern 3: "Will this help with the public holiday bottleneck?"

**Answer:** **Yes, specifically!**

The Week 2 bottleneck forces inter-week production shifting. Age-weighted costs make:
- "Produce Week 1 + hold → Week 2": Moderate cost (2-day hold)
- "Produce Week 3 + backfill → Week 2": High cost (negative days? infeasible)

This breaks the symmetry between early and late production strategies.

---

## Conclusion

### Summary

**FIFO enforcement via age-weighted holding costs:**
- ✅ **Simple to implement** (modify objective only)
- ✅ **Breaks temporal symmetry** (2-3x speedup expected)
- ✅ **More realistic** (aligns with operations)
- ✅ **Low risk** (easy to test/revert)
- ⚠️ **Not a complete solution** (still need rolling horizon for full dataset)

### Final Recommendation

**Implement Option B (Age-Weighted Holding Costs) as part of optimization stack:**

1. Test on Week 3 problem first
2. If successful (20-30s solve time), proceed to lexicographic truck ordering
3. Combine all optimizations for Week 6 testing
4. Use rolling horizon for production deployment

**This is a high-value, low-effort optimization** that addresses one of the root causes (temporal symmetry) we identified in the performance cliff analysis.

---

## Code Sketch

```python
# In integrated_model.py, modify objective function (line ~1456-1464):

def objective_rule(model):
    # ... labor, production, transport costs (unchanged) ...

    # Inventory cost - AGE-WEIGHTED for FIFO incentive
    inventory_cost = 0.0
    holding_cost_base = self.cost_structure.storage_cost_ambient_per_unit_day or 0.0

    # Reduce base rate since we're multiplying by days
    holding_cost_base = holding_cost_base * 0.1  # Tune this factor

    for dest in model.destinations:
        for prod in model.products:
            for date in model.dates:
                if (dest, prod, date) in self.inventory_index_set:
                    # Days held = days since planning start
                    days_held = (date - self.start_date).days + 1  # +1 to avoid zero

                    # Cost increases with age - incentivizes FIFO
                    inventory_cost += (holding_cost_base *
                                      model.inventory[dest, prod, date] *
                                      days_held)

    # ... truck, shortage costs (unchanged) ...

    return labor_cost + production_cost + transport_cost + inventory_cost + truck_cost + shortage_cost
```

This simple change could yield significant performance improvements on the Week 3 cliff problem.
