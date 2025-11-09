# Objective Function Refactor Plan

## Problem Statement

**Current Objective:**
```
Minimize: Production Cost + Labor + Transport + Storage + Shortage + Staleness + Changeover
        = $354,367     + $43,566 + $0 + $0 + $236,382 + $256,570 + $538
        = $891,422
```

**Issues:**
1. **Production cost ($354k) is 40% of objective** - but it's essentially a pass-through (sunk cost)
2. **Labor savings ($15k) seem tiny** at 1.8% - solver stops with 2% gap before finding them
3. **Staleness penalty ($5/unit) is 3.8× production cost** - way too aggressive
4. **No waste tracking** - expired inventory and end-of-horizon stock aren't costed
5. **Doesn't reflect incremental decisions** - includes fixed costs that don't vary

## Proposed New Objective

**Incremental Cost Focus:**
```
Minimize: Labor + Transport + Storage + Shortage + Freshness + Changeover
        + Waste (expired inventory)
        + End-of-Horizon Waste (unsold inventory)
```

### Changes:

1. **REMOVE: Production Cost** ($354k)
   - It's a pass-through - every unit produced costs $1.30 regardless
   - With shortage penalties, production quantity is determined by demand/capacity
   - No decision optimization needed

2. **ADD: Waste Cost** (NEW)
   - Track inventory that expires before use
   - Cost = `waste_cost_multiplier × production_cost_per_unit × waste_units`
   - Cost = `1.5 × $1.30 × waste_units = $1.95/unit waste`

3. **ADD: End-of-Horizon Inventory Waste** (NEW)
   - All inventory remaining at end of planning horizon
   - Treated as waste (discarded, not sold)
   - Cost = `1.5 × $1.30 × end_inventory = $1.95/unit`
   - Prevents stockpiling

4. **REDUCE: Staleness/Freshness Penalty**
   - Current: $5/unit/age_ratio (3.8× production cost)
   - Proposed: $0.05 - $0.50/unit/age_ratio (0.04× - 0.4× production cost)
   - Recommendation: **$0.13/unit/age_ratio** (0.1× production cost)
   - This provides mild FIFO preference without dominating other costs

## Implementation Details

### 1. Waste Tracking (Currently Missing)

**Add Variables:**
```python
# Waste from expired inventory (inventory that ages beyond shelf life)
model.waste_from_expiry = Var(
    waste_expiry_index,  # (node, product, expiry_date)
    domain=NonNegativeReals
)

# End-of-horizon inventory (treated as waste)
model.end_horizon_inventory = Var(
    end_inventory_index,  # (node, product, state)
    domain=NonNegativeReals
)
```

**Add Constraints:**
```python
# Link waste to inventory that can't be used due to shelf life
# (Inventory older than 17 days ambient, 120 days frozen, 14 days thawed)

# Link end-horizon inventory to actual inventory on last date
for (node, prod, state) in end_inventory_index:
    model.end_horizon_inventory[node, prod, state] == sum(
        model.inventory_cohort[node, prod, prod_date, last_date, state]
        for all prod_dates
    )
```

**Add to Objective:**
```python
waste_cost = (
    # Expired inventory waste
    sum(waste_cost_multiplier * production_cost_per_unit * model.waste_from_expiry[...]) +
    # End-of-horizon waste
    sum(waste_cost_multiplier * production_cost_per_unit * model.end_horizon_inventory[...])
)
```

### 2. Update Objective Function

**Remove:**
```python
production_cost = sum(...)  # DELETE
```

**Add:**
```python
waste_cost = sum(...)  # As above
```

**New Total:**
```python
total_cost = (
    labor_cost +
    transport_cost +
    holding_cost +
    shortage_cost +
    freshness_cost +  # Reduced weight
    changeover_cost +
    waste_cost  # NEW
)
```

### 3. Update Staleness Weight

**In Network_Config.xlsx CostParameters:**
```
freshness_incentive_weight: $5.00 → $0.13
```

Or provide as config option with explanation:
- $0.05: Very mild FIFO preference
- $0.13: Moderate FIFO (0.1× production cost) ← Recommended
- $0.50: Strong FIFO preference
- $5.00: Extremely aggressive (current, too high)

## Expected Results

**New Objective (Estimated):**
```
Labor:             $43,566
Transport:         $0
Storage:           $0
Shortage:          $236,382
Freshness:         $6,664    (was $256k at $5, now ~$6k at $0.13)
Changeover:        $538
Waste (new):       ~$5,000   (estimated - need to calculate from actual waste)
End Inventory:     ~$10,000  (estimated)
─────────────────────────────
Total:             ~$302,150 (vs $891k currently)
```

**Impact on Labor Savings:**
- $15,840 savings ÷ $302k objective = **5.2%** of total
- With 2% gap: $302k × 2% = $6,040 tolerance
- $15,840 > $6,040 ✅ **Solver WILL find it!**

## Testing Plan

1. Add waste tracking variables and constraints
2. Update objective function
3. Reduce freshness_incentive_weight to $0.13
4. Run 4-week solve with 2% gap
5. Verify:
   - Weekend consolidation happens automatically
   - No end-of-horizon stockpiling
   - Waste is tracked and costed
   - Total objective matches sum of components

## Risks & Considerations

1. **Waste calculation complexity** - Need to properly track expired inventory
   - Could be complex with multi-state inventory (frozen/ambient/thawed)
   - May increase solve time due to additional variables

2. **End-of-horizon behavior** - Treating end inventory as waste might:
   - Create artificial scarcity at horizon end
   - Underserve demand in final week
   - **Mitigation:** This is actually correct behavior - forces realistic planning

3. **Backward compatibility** - Changing objective affects all existing solves
   - Results won't be comparable to previous runs
   - **Mitigation:** This is Phase A, fresh start is fine

## Alternative: Quick Test First

**Before full refactor, test MIP gap hypothesis:**

1. Rerun exact same 4-week solve with **0.1% gap** (instead of 2%)
2. See if weekend consolidation happens automatically
3. If YES: We can just recommend tighter gaps (simpler)
4. If NO: Proceed with full objective refactor (necessary)

**Estimated time:**
- Quick test: 30 minutes (just rerun with 0.1% gap)
- Full refactor: 4-6 hours (implement waste tracking, test, verify)

## Recommendation

1. **Quick test first** (0.1% gap) - 30 min
2. **If that doesn't work** → Full refactor - 4-6 hours
3. **Either way**: Reduce staleness from $5 to $0.13

What's your preference?
