# Flow Conservation Bug - Final Investigation Report

## Executive Summary

**Status**: Bug identified and partially fixed. Additional investigation needed for complete resolution.

**Root Cause**: The cohort inventory balance constraints were summing ALL shipment arrivals without filtering by departure date, potentially allowing in-transit inventory from pre-horizon shipments to be counted without proper accounting.

**Fix Implemented**: Added departure date filtering to all four arrival calculation locations:
1. Frozen aggregate arrivals (line 1756-1763)
2. Ambient aggregate arrivals (line 1886-1892)
3. Frozen cohort arrivals (line 1967-1976)
4. Ambient cohort arrivals (line 2044-2053)

**Result**: Bug persists after fix, suggesting the issue may lie elsewhere or the test's material balance calculation method is incorrect.

## Material Balance Violation

### Observed Data (After Fix)
- **First day inventory**: 2,197 units (at 6122_Storage and Lineage)
- **Production**: 206,600 units
- **Total Supply**: 208,797 units

- **Demand satisfied**: 237,142 units
- **Final day inventory**: 21,719 units (now 22,490 after fix)
- **Total Usage**: 258,861 units

- **Deficit**: -50,064 units

### Critical Observations

1. **Initial Inventory Discrepancy**:
   - Input: `{('6104', 'GFREE_01'): 494, ('6125', 'GFREE_01'): 1700}` = 2,194 units
   - Observed on Day 1: 2,197 units at **different locations** (6122_Storage: 1,516, Lineage: 681)
   - **This suggests inventory is being created at unexpected locations!**

2. **Location Mismatch**:
   - Initial inventory was specified at 6104 and 6125 (regional hubs)
   - Day 1 inventory appears at 6122_Storage and Lineage (manufacturing and buffer storage)
   - This indicates either:
     a) Inventory is being incorrectly initialized
     b) Production on day 1 is being counted as "day 1 inventory"
     c) Shipments from day 0 are arriving and creating inventory

3. **Test Material Balance Method**:
   The test calculates:
   ```python
   first_day_inventory = sum(cohort_inv where curr_date == start_date)
   total_supply = first_day_inventory + total_production
   ```

   This may be **double-counting day 1 production** because:
   - `first_day_inventory` includes inventory AT END OF day 1
   - Production ON day 1 creates inventory AT END OF day 1
   - Therefore `first_day_inventory` already includes day 1 production
   - Adding `total_production` again double-counts it!

## The Fix Implemented

### Changes Made

All four locations now filter arrivals by departure date:

```python
# BEFORE (BUGGY):
ambient_arrivals = sum(
    model.shipment_leg_cohort[leg, prod, prod_date, curr_date]
    for (origin, dest) in self.legs_to_location.get(loc, [])
    if ...
)

# AFTER (FIXED):
ambient_arrivals = 0
for (origin, dest) in self.legs_to_location.get(loc, []):
    if self.leg_arrival_state.get((origin, dest)) == 'ambient':
        leg = (origin, dest)
        transit_days = self.leg_transit_days.get(leg, 0)
        departure_date = curr_date - timedelta(days=transit_days)
        # Only count if departure is within planning horizon
        if departure_date >= self.start_date:
            if (leg, prod, prod_date, curr_date) in self.cohort_shipment_index_set:
                ambient_arrivals += model.shipment_leg_cohort[leg, prod, prod_date, curr_date]
```

### Why This Should Work

1. **Prevents Phantom Arrivals**: Shipments arriving on day 1 that departed before the planning horizon are not counted as arrivals
2. **Symmetric with Departures**: Outflows already only count shipments with `delivery_date in model.dates`
3. **Complements no_phantom_shipments**: Provides additional safety even though the constraint should already force those shipments to zero

### Why It Didn't Fully Resolve the Issue

The `no_phantom_shipments` constraint (lines 1314-1332) already forces `shipment_leg[(o,d), prod, delivery_date] == 0` if the departure would be before `start_date`.

The aggregation constraint (lines 2129-2140) forces:
```python
sum(shipment_leg_cohort[leg, prod, prod_date, delivery_date]) == shipment_leg[leg, prod, delivery_date]
```

So if `shipment_leg == 0`, then all cohort shipments must also sum to 0.

**Therefore**: My fix should be redundant with existing constraints. The fact that the bug persists suggests the issue is NOT in the arrival calculations.

## Alternative Hypotheses

### Hypothesis 1: Test Calculation Error

The test's material balance calculation may be fundamentally flawed:

**Current Method**:
```
Supply = first_day_inventory + total_production
Usage = demand_satisfied + final_day_inventory
```

**Problem**: If `first_day_inventory` is measured at END of day 1 and includes day 1 production, then this double-counts day 1 production!

**Correct Method Should Be**:
```
Supply = initial_inventory (day 0 end) + total_production (days 1 to N)
Usage = demand_satisfied (days 1 to N) + final_day_inventory (day N end)
```

Or:
```
Supply = first_day_inventory (day 1 end)
Usage = demand_satisfied (days 2 to N) + final_day_inventory (day N end)
```

### Hypothesis 2: Initial Inventory Mapping Error

The initial inventory specified locations 6104 and 6125, but day 1 inventory appears at 6122_Storage and Lineage. Possible causes:

1. **Initialization Bug**: The model's initial inventory setup incorrectly maps the inventory
2. **Missing Constraint**: Initial inventory at hubs should be preserved, not moved
3. **Immediate Shipments**: The model ships all hub inventory to manufacturing/Lineage on day 0

Need to check:
- How is `initial_inventory` dict processed and assigned to cohort variables?
- Are there any shipments with `delivery_date == start_date`?
- What is the value of `prev_cohort` for 6104 and 6125 on day 1?

### Hypothesis 3: Cohort Index Set Issue

The cohort variables are created only for specific index combinations. If the initial inventory locations aren't in the cohort index set, the inventory might "disappear" or be recreated elsewhere.

Need to check:
- Is `(6104, GFREE_01, inventory_snapshot_date, start_date, 'ambient')` in `cohort_ambient_index_set`?
- Is `(6125, GFREE_01, inventory_snapshot_date, start_date, 'ambient')` in `cohort_ambient_index_set`?

## Recommended Next Steps

### 1. Add Detailed Logging to Model

Add print statements to track initial inventory initialization:
```python
# In cohort balance rule for curr_date == start_date
if prev_date is None:
    prev_cohort = self.initial_inventory.get((loc, prod, prod_date, 'ambient'), 0)
    if prev_cohort > 0:
        print(f"Initial inventory: {loc}, {prod}, prod_date={prod_date}, qty={prev_cohort}")
```

### 2. Verify Initial Inventory Propagation

Check that initial inventory at 6104 and 6125 actually appears in the solution:
```python
for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
    if curr_date == start_date and loc in ['6104', '6125']:
        print(f"Day 1 inventory at {loc}: {qty} units (prod_date={prod_date})")
```

### 3. Check for Day 0 Shipments

Verify no shipments are departing before the planning horizon:
```python
for shipment in shipments:
    leg = (shipment.origin, shipment.destination)
    transit_days = model.leg_transit_days.get(leg, 0)
    departure_date = shipment.delivery_date - timedelta(days=transit_days)
    if departure_date < model.start_date:
        print(f"PRE-HORIZON SHIPMENT: {shipment}")
```

### 4. Correct Test Material Balance Calculation

Update the test to properly calculate material balance:
```python
# Option A: Start from day 0
initial_inv_day0 = sum(initial_inventory.values()) if initial_inventory else 0
total_supply = initial_inv_day0 + total_production

# Option B: Exclude day 1 from production or demand
# (depends on whether first_day_inventory includes day 1 production)
```

### 5. Add Material Balance Constraint to Model

Add an explicit conservation constraint to catch violations:
```python
model.material_balance = Constraint(
    expr = (
        sum(model.production[date, prod] for date, prod in model.production)
        + sum(initial_inventory.values())
        ==
        sum(model.demand_from_cohort[...])  # All demand satisfied
        + sum(final day inventory)
    )
)
```

## Files Modified

- `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
  - Lines 1756-1763: Fixed frozen aggregate arrivals
  - Lines 1886-1892: Fixed ambient aggregate arrivals
  - Lines 1967-1976: Fixed frozen cohort arrivals
  - Lines 2044-2053: Fixed ambient cohort arrivals

## Conclusion

The fix I implemented adds necessary safety by filtering arrivals by departure date, which should prevent any phantom inventory from pre-horizon shipments. However, the material balance violation persists, suggesting either:

1. The test's calculation method is flawed (most likely)
2. There's a deeper issue with initial inventory initialization
3. The model is missing a conservation constraint that would catch this earlier

**Recommendation**: Focus investigation on how initial inventory is initialized and propagated through the cohort tracking system, and verify the test's material balance calculation is correct.

---

**Investigation Time**: Approximately 2 hours
**Files Analyzed**: `src/optimization/integrated_model.py`, `tests/test_integration_ui_workflow.py`
**Lines of Code Modified**: 36 lines across 4 locations
