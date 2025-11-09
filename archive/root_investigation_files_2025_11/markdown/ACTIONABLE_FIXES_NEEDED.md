# Actionable Fixes Needed - November 5, 2025

## Issues Confirmed

✅ Bugs #1, #2, #3: ALL FIXED (working correctly)
❌ **New Issue 1**: Sunday production when Friday has capacity (sub-optimal)
❌ **New Issue 2**: Excessive end-of-horizon inventory with no post-horizon demand knowledge

---

## Issue 1: Sunday Production (Sub-Optimal)

### Problem
- Friday: 3,567 units spare capacity, marginal cost = $182
- Sunday: 387 units produced, cost = $5,280
- **Waste: $5,098** (model should prefer Friday)

### Root Cause
MIP gap tolerance (2%) allows sub-optimal solutions within $17,373 of optimal.

### Fix Options

**Option A: Add Weekend Avoidance Penalty** (Recommended)

Add to objective function:
```python
# Penalize weekend production heavily to force weekday usage
weekend_avoidance_cost = quicksum(
    6000.0 * model.any_production[node_id, t]  # $6k per weekend day used
    for node_id in manufacturing_nodes
    for t in model.dates
    if is_weekend(t)
)
```

**Option B: Tighten MIP Gap**
```python
result = model.solve(solver_name='appsi_highs', mip_gap=0.001)  # 0.1% vs 2%
```

**Trade-off**: Longer solve time (60s → possibly 300s+)

**Recommendation**: Use Option A (explicit weekend avoidance)

---

## Issue 2: End-of-Horizon Inventory (32,751 units)

### Problem
Model has **no demand data beyond planning horizon**, yet builds large inventory at end.

**Why this is wrong**:
- Unknown demand → inventory likely wasted
- Ages during storage
- May expire before any known use
- Ties up working capital

### Current Objective (Line 2748-2774)

```python
waste_cost = waste_multiplier * production_cost * (end_inventory + end_in_transit)
```

**Current parameter values** (check CostParameters sheet):
- `waste_cost_multiplier`: Likely 1.0 or 10.0
- `production_cost_per_unit`: $1.30
- **Effective penalty**: ~$13-$130 per unit

**For 32,751 units**:
- If multiplier=1: Cost = $42,577
- If multiplier=10: Cost = $425,770

The fact that model chose to pay this suggests **other costs dominate**.

### Root Cause Analysis

**Hypothesis 1: Shortage Penalty Too High**
- Shortage penalty: $10/unit (from analysis)
- Model prefers: Overproduce and waste vs risk shortage
- Even though there's no known demand post-horizon!

**Hypothesis 2: Truck Utilization Forcing Overproduction**
- Trucks have 14,080 capacity (44 pallets)
- Model may fill trucks even without near-term demand
- Partial truck loads waste capacity

**Hypothesis 3: Shelf Life Constraints Forcing Early Production**
- 17-day shelf life for ambient
- Model might produce early to avoid violating shelf life on late-horizon demand
- Leftover inventory accumulates at end

### Recommended Fix

**Increase End-Inventory Waste Multiplier**:

In `data/examples/Network_Config.xlsx`, CostParameters sheet:
```
waste_cost_multiplier: 50  (try 50× instead of 1× or 10×)
```

This makes end-inventory extremely expensive:
- 32,751 units × 50 × $1.30 = $2.1M penalty
- Will force model to minimize end inventory

**Alternative: Add Hard Constraint**:
```python
# In _add_constraints:
def max_end_inventory_rule(model):
    """Limit total end inventory to reasonable buffer."""
    last_date = max(model.dates)

    total_end_inv = sum(
        model.inventory[node_id, prod, state, last_date]
        for (node_id, prod, state, t) in model.inventory
        if t == last_date
    )

    # Allow max 2 days of average demand as buffer
    avg_daily_demand = sum(self.demand.values()) / len(model.dates)
    max_buffer = 2.0 * avg_daily_demand

    return total_end_inv <= max_buffer

model.max_end_inventory_con = Constraint(rule=max_end_inventory_rule)
```

---

## Implementation Plan

### Fix 1: Weekend Avoidance (30 min)

**File**: `src/optimization/sliding_window_model.py`

1. Add weekend avoidance parameter to CostStructure
2. Add penalty term to objective (after line 2802)
3. Test: Sunday production should drop to 0 if Friday has capacity

### Fix 2: End-Inventory Control (20 min)

**Option A**: Update Excel parameter
- Increase `waste_cost_multiplier` to 50 in Network_Config.xlsx
- Test: End inventory should drop significantly

**Option B**: Add hard constraint
- Implement `max_end_inventory_con` in model
- Set reasonable buffer (e.g., 2× daily demand)

---

## Verification Criteria

✅ Sunday Oct 26: 0 units production (shifted to Friday)
✅ Friday Oct 24: Production increases by 387 units (still within capacity)
✅ End-of-horizon inventory: <5,000 units (minimal buffer)
✅ No increase in shortages
✅ Total cost decreases (eliminating Sunday waste)

---

## Priority

**High**: These are real optimization quality issues
- Sunday production: $5k waste per solve
- End inventory: Potentially $400k+ of unusable inventory

**My Apology**: I should have caught these in verification. The bugs (#1, #2, #3) are fixed, but the optimization isn't truly optimal due to:
1. MIP gap allowing sub-optimal weekend usage
2. Insufficient end-inventory penalty

Would you like me to implement the weekend avoidance penalty and end-inventory constraint?
