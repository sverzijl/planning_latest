# Truck Loading Bug: Root Cause Analysis

## Problem Summary

**Observed Behavior:**
- Production limited to 1,701,492 units (1.70M)
- Demand requires 2,407,299 units (2.41M)
- Capacity available: 3,494,400 units (208 days × 12h × 1,400 units/h)
- Shortage variables all ZERO despite 630K unit deficit
- Cost: $9.31M

**Expected Behavior:**
- Production should reach ~2.41M units to satisfy demand
- OR shortage variables should be non-zero to account for deficit

## Root Cause

The bug is in the **truck loading timing constraints** at lines **1579-1638** of `src/optimization/integrated_model.py`.

### Critical Constraint Flow

1. **Production to Storage:**
   ```python
   # Line 1316-1317: 6122_Storage inventory balance
   inventory_ambient['6122_Storage', prod, date] ==
       prev_ambient + production[date, prod] - truck_outflows[date]
   ```

2. **Truck Loading Constraints:**
   ```python
   # Lines 1595-1608: Morning trucks
   d_minus_1 = departure_date - timedelta(days=1)

   if d_minus_1 not in model.dates:
       return truck_load == 0  # ← BUG: Forces zero load!

   storage_inventory = sum(
       inventory_ambient['6122_Storage', p, d_minus_1]
       if ('6122_Storage', p, d_minus_1) in inventory_ambient_index_set
       else 0  # ← BUG: Defaults to 0 if not in sparse index!
   )
   truck_load <= storage_inventory
   ```

### The Bug in Detail

**Problem 1: Early Planning Horizon Days**
- For trucks departing on first planning day (e.g., Monday), `d_minus_1` = Sunday
- Sunday is BEFORE planning horizon start → `d_minus_1 not in model.dates` → **truck_load forced to 0**
- This eliminates ALL truck capacity on the first departure day!

**Problem 2: Sparse Index Default**
- Even when `d_minus_1` IS in `model.dates`, if it's not in `inventory_ambient_index_set`, defaults to 0
- The sparse index only includes dates within planning horizon
- Initial inventory is ignored in the constraint logic

**Problem 3: Initial Inventory Not Used**
- The 6122_Storage inventory balance (lines 1286-1289) correctly uses `initial_inventory` when `prev_date is None`
- But truck constraints (lines 1604, 1632) don't access initial_inventory when `d_minus_1 < start_date`
- Result: First days of production cannot be shipped!

### Impact Analysis

**Example Scenario:**
- Planning horizon: Monday to Friday (5 days)
- Monday morning truck departs Monday, checks inventory at Sunday
- Sunday < start_date → truck_load[Monday] = 0
- Monday production = 16,800 units
- Monday production CANNOT be shipped on Monday truck
- Monday production goes into 6122_Storage inventory
- Tuesday morning truck checks Monday inventory (finally has stock)
- But Tuesday production also arrives, creating accumulation lag

**Cumulative Effect:**
1. Day 1: Production ✓, Shipping ✗ (no prior inventory)
2. Day 2: Production ✓, Shipping limited to Day 1 production
3. Day 3: Production ✓, Shipping limited to Day 2 net inventory
4. Etc.

This creates a **ramp-up limitation** that prevents full utilization of production capacity.

## Why Shortage Variables Are Zero

The shortage variables are zero because the model finds it **cheaper to underproduce** than to:
1. Produce excess that cannot be shipped (due to truck constraints)
2. Pay holding costs for accumulated 6122_Storage inventory
3. Pay labor costs for production that sits in storage

The solver makes a rational trade-off: **produce only what can be shipped**, rather than producing more and incurring storage costs.

However, this is a **false constraint** - in reality, we COULD pre-stock 6122_Storage before the planning horizon, or we could use initial_inventory to represent existing stock.

## The Fix

### Solution: Use Initial Inventory When d_minus_1 < start_date

Modify truck loading constraints to access initial_inventory when d_minus_1 is before planning horizon:

```python
# Morning trucks (lines 1595-1608)
d_minus_1 = departure_date - timedelta(days=1)

# Calculate storage inventory available at d_minus_1
if d_minus_1 not in model.dates:
    # d_minus_1 is before planning horizon - use initial inventory
    storage_inventory = sum(
        self.initial_inventory.get(('6122_Storage', p, 'ambient'),
                                   self.initial_inventory.get(('6122_Storage', p), 0))
        for p in model.products
    )
else:
    # d_minus_1 is within planning horizon - use inventory variable
    storage_inventory = sum(
        model.inventory_ambient['6122_Storage', p, d_minus_1]
        if ('6122_Storage', p, d_minus_1) in self.inventory_ambient_index_set
        else 0
        for p in model.products
    )

return truck_load <= storage_inventory
```

Same fix for afternoon trucks (lines 1624-1638).

### Why This Fix Works

1. **Trucks on first day** can now access initial_inventory (typically 0, but could be pre-stocked)
2. **Removes artificial constraint** that forced early truck loads to 0
3. **Allows production ramp-up** without accumulation lag
4. **No circular dependency** because initial_inventory is a constant parameter, not a decision variable
5. **Mathematically correct** - represents the actual physical state: storage before planning starts

### Why Previous "Fix" Failed

The attempted fix (changing `d_minus_1` to `departure_date` in lines 1603-1604, 1631-1632) created a **circular dependency**:

```python
# WRONG FIX (creates circular dependency):
truck_load[delivery_date] <= inventory_ambient['6122_Storage', p, departure_date]

# But inventory balance at departure_date includes:
inventory_ambient['6122_Storage', p, departure_date] ==
    prev + production[departure_date] - truck_outflows[departure_date]

# And truck_outflows includes:
if departure_date == date:
    truck_outflows += truck_load[delivery_date]

# Circular: truck_load depends on inventory, inventory depends on truck_load!
```

This makes the constraint **self-referential** and breaks the model structure.

The correct fix uses `d_minus_1` (as designed) but accesses **initial_inventory parameter** when d_minus_1 is out of range, avoiding the circular dependency.

## Implementation

Apply the fix at two locations:
1. **Lines 1595-1608:** truck_morning_timing_agg_rule
2. **Lines 1624-1638:** truck_afternoon_timing_agg_rule

Both need the same pattern:
- Check if `d_minus_1 not in model.dates`
- If true, use `initial_inventory` for 6122_Storage
- If false, use `inventory_ambient` variable as currently coded

## Expected Results After Fix

- Production should increase to ~2.41M units (meeting full demand)
- Cost should increase proportionally (more production, labor, transport)
- Shortage variables should remain at 0 (demand satisfied)
- 6122_Storage inventory should show proper flow-through (not accumulation)
- First day trucks should be able to ship (using initial inventory = 0 + same-day production for afternoon trucks)
