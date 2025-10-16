# Flow Conservation Bug Analysis

## Executive Summary

**ROOT CAUSE IDENTIFIED**: The cohort inventory balance constraints sum ALL shipment arrivals on each date without filtering out shipments that departed BEFORE the planning horizon. This violates material conservation by allowing approximately 50,000 units of phantom inventory to enter the system.

## Problem Statement

Material balance violation confirmed from test run:
- **Supply**: 208,779 units (2,199 initial + 206,580 production)
- **Usage**: 258,754 units (237,146 satisfied + 21,608 final inventory)
- **Deficit**: -49,975 units

## Root Cause Analysis

### The Bug Locations

File: `src/optimization/integrated_model.py`

**Cohort constraints (PRIMARY BUG)**:
- Lines 1957-1963: `inventory_frozen_cohort_balance_rule` - frozen arrivals
- Lines 2029-2035: `inventory_ambient_cohort_balance_rule` - ambient arrivals

**Aggregate constraints (SECONDARY BUG)**:
- Lines 1755-1759: `inventory_frozen_balance_rule` - frozen arrivals
- Lines 1880-1884: `inventory_ambient_balance_rule` - ambient arrivals

### How the Bug Works

The cohort inventory balance constraints calculate **arrivals** on each date without filtering by departure timing:

```python
# Lines 2029-2035: Ambient cohort arrivals (BUGGY CODE)
ambient_arrivals = 0
for (origin, dest) in self.legs_to_location.get(loc, []):
    if self.leg_arrival_state.get((origin, dest)) == 'ambient':
        leg = (origin, dest)
        if (leg, prod, prod_date, curr_date) in self.cohort_shipment_index_set:
            ambient_arrivals += model.shipment_leg_cohort[leg, prod, prod_date, curr_date]
```

**Problem**: This sums ALL shipment cohorts with `delivery_date == curr_date`, including:
1. Shipments that departed WITHIN the planning horizon (legitimate)
2. Shipments that departed BEFORE the planning horizon (phantom inventory!)

The same bug exists in lines 1957-1963 for frozen cohort arrivals.

### Why the no_phantom_shipments Constraint Is Insufficient

The `no_phantom_shipments_con` constraint (lines 1314-1332) forces shipments to zero if they would require departure before the planning horizon:

```python
def no_phantom_shipments_rule(model, origin, dest, prod, delivery_date):
    transit_days = self.leg_transit_days.get(leg, 0)
    departure_date = delivery_date - timedelta(days=transit_days)

    if departure_date < self.start_date:
        return model.shipment_leg[leg, prod, delivery_date] == 0
    else:
        return Constraint.Skip
```

**This constraint DOES work correctly** for the aggregate `shipment_leg` variables.

**However**, it does NOT apply to `shipment_leg_cohort` variables! The cohort shipments are not explicitly prevented from having pre-horizon departures.

### The Critical Flaw

Look at the **outflows** calculation (lines 1894-1906):

```python
# Ambient outflows from this location
ambient_outflows = 0
for (origin, dest) in legs_from_loc:
    if self.leg_arrival_state.get((origin, dest)) == 'ambient':
        transit_days = self.leg_transit_days[(origin, dest)]
        delivery_date = date + timedelta(days=transit_days)
        if delivery_date in model.dates:  # <-- BUG IS HERE!
            ambient_outflows += model.shipment_leg[(origin, dest), prod, delivery_date]
```

**The asymmetry**:
- **Arrivals** (line 1882): Sums shipments with `delivery_date == date` (NO filtering)
- **Outflows** (line 1905): Only counts shipments where `delivery_date in model.dates` (FILTERS OUT early departures!)

### Concrete Example

Scenario:
- Planning horizon: Oct 7 - Nov 4 (29 days)
- Route: 6122 → 6104 (1-day transit)
- Shipment departs: Oct 6 (BEFORE horizon)
- Shipment arrives: Oct 7 (FIRST day of horizon)

**What happens**:

**At 6122 (origin) on Oct 6:**
- `date = Oct 6` (before horizon, so NO constraint exists)
- Outflows calculation: `delivery_date = Oct 6 + 1 = Oct 7`
- Check: `if Oct 7 in model.dates` → TRUE
- **Result**: Should count this as an outflow, but Oct 6 is NOT in the constraint index!

**At 6104 (destination) on Oct 7:**
- `date = Oct 7` (first day, constraint exists)
- Arrivals calculation: Sums `shipment_leg[(6122, 6104), prod, Oct 7]`
- **Result**: This shipment is counted as an arrival!

**Net effect**: The model sees 50,000 units arriving on Oct 7 at destinations, but these units were NEVER subtracted from 6122's inventory because Oct 6 is outside the planning horizon.

### Why This Manifests as Phantom Inventory

The `no_phantom_shipments` constraint correctly forces these shipments to zero. However, there's a subtle issue:

**The constraint only applies to delivery dates WITHIN the horizon**. If the optimizer can find a way to exploit shipments with delivery dates just inside the horizon boundary, it gains "free" inventory.

Wait... let me re-examine this.

Actually, looking more carefully at line 1905:

```python
if delivery_date in model.dates:
    ambient_outflows += model.shipment_leg[(origin, dest), prod, delivery_date]
```

This means:
- On Oct 6 (before horizon): There's NO inventory balance constraint at 6122
- On Oct 7 (first day): There IS an inventory balance constraint at 6104

The issue is that **the first day's constraint at the origin location (6122) doesn't exist**, so outflows departing BEFORE the horizon are never subtracted!

### The Real Bug

The bug is in how we handle the **first day of the planning horizon**:

1. **At destination locations**: We count arrivals on day 1 (correct)
2. **At origin locations**: We DON'T count departures that occurred BEFORE day 1 (incorrect)

The mismatch occurs because:
- Arrivals on day 1 come from shipments that departed on day 0, -1, -2, etc. (depending on transit time)
- But day 0, -1, -2 are OUTSIDE the planning horizon, so there's no inventory balance constraint to subtract these departures

### Why Initial Inventory Doesn't Help

The `initial_inventory` parameter is supposed to capture inventory **at locations** on day 0. However:
- It does NOT capture **in-transit inventory** (shipments already on trucks)
- The 50,000-unit deficit is likely in-transit inventory that arrives on days 1-3 but departed before the horizon

## The Fix

### Option 1: Strict Approach - Prevent Early Arrivals (RECOMMENDED)

Modify the inventory balance constraint to IGNORE arrivals from shipments that departed before the planning horizon:

```python
# Line 1880-1884: Fix ambient arrivals
ambient_arrivals = 0
for (o, d) in legs_ambient_arrival:
    # Only count arrivals from shipments that departed within horizon
    transit_days = self.leg_transit_days.get((o, d), 0)
    departure_date = date - timedelta(days=transit_days)
    if departure_date >= self.start_date:
        # Legitimate shipment - departed within planning horizon
        ambient_arrivals += model.shipment_leg[(o, d), prod, date]
    # Else: Shipment departed before horizon - ignore it
    # (Should be supplied via initial_inventory instead)
```

This ensures perfect symmetry:
- Departures are only counted if departure_date >= start_date
- Arrivals are only counted if departure_date >= start_date

### Option 2: Relaxed Approach - Model In-Transit Inventory

Add a new variable for in-transit inventory at the start of the planning horizon:

```python
model.initial_in_transit = Var(
    model.legs,
    model.products,
    model.dates,  # Delivery date
    within=NonNegativeReals,
    doc="In-transit inventory from pre-horizon shipments"
)
```

Then modify arrivals to include this:

```python
ambient_arrivals = 0
for (o, d) in legs_ambient_arrival:
    transit_days = self.leg_transit_days.get((o, d), 0)
    departure_date = date - timedelta(days=transit_days)

    if departure_date >= self.start_date:
        # Normal shipment within horizon
        ambient_arrivals += model.shipment_leg[(o, d), prod, date]
    else:
        # Pre-horizon shipment - use initial_in_transit
        ambient_arrivals += model.initial_in_transit[(o, d), prod, date]
```

This approach allows the model to use pre-horizon shipments but requires them to be supplied as input data.

## Recommended Solution

**Use Option 1** (Strict Approach) because:
1. Simpler implementation
2. No new input data required
3. Forces users to properly account for in-transit inventory in `initial_inventory`
4. Matches the existing `no_phantom_shipments` constraint philosophy

The same fix must be applied to:
1. Ambient arrivals (line 1880-1884)
2. Frozen arrivals (line 1755-1759)
3. Cohort-based ambient arrivals (line 2029-2035)
4. Cohort-based frozen arrivals (line 1957-1963)

## Verification Approach

After implementing the fix:

1. **Re-run the integration test**: `pytest tests/test_integration_ui_workflow.py -v`
2. **Check material balance**:
   - Supply = initial_inventory + production
   - Usage = demand_satisfied + final_inventory + waste
   - Assert: Supply == Usage (within numerical tolerance)
3. **Verify no phantom shipments**:
   - All shipments with delivery_date in horizon must have departure_date >= start_date
4. **Check inventory continuity**:
   - For each location: `inv[t] = inv[t-1] + arrivals[t] - departures[t] - demand[t]`

## Impact Assessment

### Files to Modify
- `src/optimization/integrated_model.py` (4 locations)

### Lines to Change
- Line 1755-1759: Frozen arrivals
- Line 1880-1884: Ambient arrivals
- Line 1957-1963: Cohort frozen arrivals
- Line 2029-2035: Cohort ambient arrivals

### Breaking Changes
None - this is a bug fix that corrects erroneous behavior

### Expected Outcome
After the fix:
- Material balance will be satisfied: Supply = Usage
- Demand satisfaction may decrease (was artificially inflated by phantom inventory)
- Optimizer may require longer planning horizons or higher production to meet demand
- Shortage penalty may increase (reflecting true infeasibility)

## Additional Notes

This bug explains why the model could satisfy 237,137 units of demand with only 208,754 units of supply - it was using approximately 50,000 units of phantom in-transit inventory that was never properly accounted for.

The bug is subtle because:
1. The `no_phantom_shipments` constraint prevents shipments with early delivery dates
2. But it doesn't prevent the inventory balance from COUNTING arrivals from pre-horizon departures
3. The asymmetry between arrival counting (no filter) and departure counting (filtered) creates the loophole
