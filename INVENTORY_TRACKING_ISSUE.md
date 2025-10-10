# Critical Issue: Missing Destination Inventory Tracking

## Problem

The optimization model does **NOT track inventory at destination locations**. This prevents buffer stock from building up and causes unnecessary weekend production to persist across all weeks.

## Current Behavior (WRONG)

**Demand Satisfaction Constraint:**
```python
shipments[delivery_date] >= demand[delivery_date]
```

Each delivery date is satisfied **independently** with no inventory carryover.

**Result:**
- Week 1: Sunday production → Monday delivery ✓
- Week 2: Sunday production → Monday delivery ❌ (should use buffer)
- Week 3: Sunday production → Monday delivery ❌ (should use buffer)
- Week 4: Sunday production → Monday delivery ❌ (should use buffer)

Weekend work pattern **repeats every week** because there's no buffer stock.

## Expected Behavior (CORRECT)

**With Inventory Balance:**
```python
inventory[dest, prod, t-1] + shipments[t] - demand[t] = inventory[dest, prod, t]
```

**Result:**
- Week 1: Build buffer with Sunday/weekday production
- Week 2-4: Use buffer stock, NO weekend production needed

## Evidence

### Test: 4-week scenario, moderate demand (3000 units/week)

**Actual Results:**
```
Week 1: 1,507 units weekend production ✓ (acceptable, no buffer)
Week 2: 694 units weekend production   ❌ (should be 0)
Week 3: 708 units weekend production   ❌ (should be 0)
Week 4: 0 units weekend production     ✓
```

**Expected Results:**
```
Week 1: ~500-1000 units weekend (build buffer)
Week 2: 0 units weekend (use buffer)
Week 3: 0 units weekend (use buffer)
Week 4: 0 units weekend (use buffer)
```

## Root Cause

File: `src/optimization/integrated_model.py`

**Line 927-961:** `demand_satisfaction_con`

The constraint directly links shipments to demand on the exact delivery date:
```python
def demand_satisfaction_rule(model, dest, prod, delivery_date):
    demand_qty = self.demand.get((dest, prod, delivery_date), 0.0)
    total_shipments = sum(
        model.shipment[r, prod, delivery_date]
        for r in route_list
    )
    return total_shipments >= demand_qty  # No inventory buffer!
```

## Required Fix

### 1. Add Inventory Variables

```python
model.inventory = Var(
    model.destinations,
    model.products,
    model.dates,
    within=NonNegativeReals,
    doc="Inventory at destination by product and date"
)
```

### 2. Add Inventory Balance Constraints

```python
def inventory_balance_rule(model, dest, prod, date):
    # Previous inventory + shipments - demand = current inventory
    prev_date = date - timedelta(days=1)

    shipments_in = sum(
        model.shipment[r, prod, date]
        for r in routes_to_destination[dest]
    )

    demand = self.demand.get((dest, prod, date), 0.0)

    if prev_date in model.dates:
        prev_inventory = model.inventory[dest, prod, prev_date]
    else:
        prev_inventory = 0  # Initial inventory

    return (prev_inventory + shipments_in - demand ==
            model.inventory[dest, prod, date])
```

### 3. Add Inventory Holding Costs (optional but recommended)

```python
# In objective function
inventory_cost = sum(
    holding_cost_per_unit * model.inventory[dest, prod, date]
    for dest in destinations
    for prod in products
    for date in dates
)
```

This incentivizes just-in-time delivery while still allowing strategic buffering.

## Impact

**Without this fix:**
- ❌ Weekend work persists unnecessarily
- ❌ Higher labor costs
- ❌ Cannot leverage buffer stock for cost optimization

**With this fix:**
- ✅ Buffer stock builds up naturally
- ✅ Weekend work only when truly needed (week 1)
- ✅ Lower total costs
- ✅ More realistic production planning

## Priority

**HIGH** - This is a fundamental flaw in the model that prevents it from optimizing across time periods. It treats each delivery date as independent when they should be connected through inventory.
