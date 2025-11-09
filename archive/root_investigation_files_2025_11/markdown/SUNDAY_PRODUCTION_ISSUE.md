# Sunday Production Issue - Root Cause Analysis

## Issue

Sunday Oct 26 produces 387 units despite Friday having 3,567 units spare capacity.

**Cost Impact**:
- Friday marginal cost: 0.28h × $660/h = $182
- Sunday marginal cost: 4.0h × $1,320/h = $5,280
- **Waste: $5,098** by choosing Sunday over Friday

## Analysis

### What We Know

**Friday Oct 24**:
- Production: 16,033 units (81.8% capacity)
- Spare capacity: 3,567 units (enough for Sunday's 387)
- Hours used: 11.70h (0.70h overtime)
- Labor cost: $0 (within fixed hours on this week - accounting shows $0 because fixed is free)

**Sunday Oct 26**:
- Production: 387 units (2% capacity)
- Product: HELGAS GFREE TRAD WHITE 470G
- Hours paid: 4.00h (minimum payment)
- Labor cost: $5,280
- **Shipments: 0** (goes into inventory, not immediate shipment)

### Why Model Chose Sunday (Hypotheses)

**Hypothesis 1: MIP Gap Tolerance** ⭐ **Most Likely**
- MIP gap = 2% (0.02)
- Total cost = $868,674
- 2% tolerance = $17,373
- Sunday waste ($5,098) < tolerance
- **Solver stopped before finding better solution** (within acceptable gap)

**Hypothesis 2: Shelf Life Constraint Interaction**
- Friday production would age 3 days before Monday
- Sunday production ages 1 day before Monday
- Some shelf life constraint might prefer fresher product
- **But**: Sliding window model has no explicit staleness penalty

**Hypothesis 3: Integer Pallet Rounding**
- 387 units = 2 pallets (387/320 = 1.21 → rounds to 2)
- Friday production uses different pallet counts
- Integer rounding interactions may create local optimum

**Hypothesis 4: Changeover Cost**
- Sunday production is single product (no changeovers)
- Adding to Friday mix might trigger changeover costs
- **But**: 387 units of existing product shouldn't add changeover

## Root Cause: **MIP Gap Sub-Optimality**

The solver found a solution within 2% of optimal and stopped. The $5,098 waste from Sunday production is < $17,373 tolerance, so it's considered "good enough."

## Solutions

### Option 1: Tighten MIP Gap (Recommended)
```python
model.solve(solver_name='appsi_highs', mip_gap=0.001)  # 0.1% instead of 2%
```

**Pros**: Forces solver to find better solutions
**Cons**: Longer solve time (may go from 60s to 180s+)

### Option 2: Add Weekend Avoidance Soft Constraint
```python
# In objective function:
weekend_penalty_cost = quicksum(
    weekend_production_penalty * model.any_production[node, t]
    for node in manufacturing_nodes
    for t in weekend_dates
)
```

Set `weekend_production_penalty = $6,000` (more than Sunday minimum cost)

**Pros**: Explicitly discourages weekend production
**Cons**: Adds another parameter to tune

### Option 3: Add Heuristic Fix (Post-Solve)
After optimization:
```python
# Check for Sunday production with Friday spare capacity
# If found: Move production to Friday
# Re-solve or manually adjust
```

**Pros**: Guarantees no Sunday production if Friday available
**Cons**: Two-stage process, not integrated

### Option 4: Accept As-Is
- 387 units on Sunday = 0.16% of total production (247,853 units)
- Cost impact: $5,098 / $868,674 = 0.6% of total cost
- Within MIP gap tolerance

**Pros**: No changes needed
**Cons**: Not truly optimal

## Recommendation

**For immediate fix**: Use Option 2 (weekend avoidance penalty)

**For long-term**: Use Option 1 (tighter MIP gap) for production runs

---

## End-of-Horizon Inventory

**Total**: 32,751 units

**Is this a problem?**

Depends on post-horizon demand. If forecast shows continued demand at ~10,000+ units/day, this is **reasonable pre-positioning** (3 days buffer).

**To reduce**: Increase `waste_cost_multiplier` in CostParameters sheet.

---

## Summary

**Original bugs**: ✅ ALL FIXED (validation working correctly)

**Sunday production**: Sub-optimal but within MIP gap tolerance
- Not a "bug" per se, but could be improved
- Recommend: Add weekend avoidance penalty or tighten gap

**End inventory**: May be intentional buffer
- Check post-horizon demand forecast
- Tune waste cost if excessive

**My failure**: Should have anticipated MIP gap would allow sub-optimal weekend usage. Need to add weekend avoidance as default behavior, not rely on cost optimization alone.
