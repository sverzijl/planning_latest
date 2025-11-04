# Critical Bug: Truck Schedules Not Enforced

## Issue Summary

**Symptom:** Trucks depart on wrong days (e.g., 6110 truck on Monday when it should only run Tuesday/Thursday)

**Root Cause:** Shipment variables created for all routes on all dates, with no day-of-week enforcement

**Impact:** Invalid shipping schedules, violates operational constraints

**Status:** 🔴 **CRITICAL BUG - INVALID SOLUTIONS**

## Root Cause Analysis

### How in_transit Variables Are Created

Lines 522-536 in sliding_window_model.py:

```python
in_transit_index = []
for route in self.routes:
    for prod in model.products:
        for departure_date in model.dates:  # ❌ ALL DATES
            for state in ['frozen', 'ambient']:
                in_transit_index.append((
                    route.origin_node_id,
                    route.destination_node_id,
                    prod,
                    departure_date,  # No day-of-week restriction!
                    state
                ))
```

**Problem:** Creates shipment variables for EVERY route on EVERY date, regardless of truck schedule

### Truck Capacity Constraint (Lines 1994-2005)

```python
# Check if truck operates on this day of week
if truck.day_of_week.lower() != actual_day_of_week:
    return Constraint.Skip  # Skip constraint on wrong days

# ...capacity constraint...
```

**Problem:** This only SKIPS the capacity constraint on wrong days, it doesn't PREVENT shipments!

**Result:**
- Routes can be used on ANY day (variables exist for all days)
- Truck capacity constraints only apply on correct days
- **No constraint prevents using routes on wrong days**

## Example

### Expected Behavior (Monday):

**Morning truck:**
- Destination: 6125
- Can ship: 6122 → 6125 ✓

**Afternoon truck:**
- Destination: 6104
- Can ship: 6122 → 6104 ✓

**Should NOT ship to:**
- 6110 (only Tuesday/Thursday)

### Actual Behavior (Monday):

Model can ship to ALL destinations:
- 6125 ✓ (correct)
- 6104 ✓ (correct)
- 6110 ✗ (WRONG - no truck on Monday!)

**Why:** The `in_transit[6122, 6110, prod, monday, state]` variable EXISTS and has no constraint preventing it from being used.

## Impact

### Operational Violations

- Shipments scheduled on days with no truck
- Invalid production-distribution plans
- Cannot execute in real operations

### Model Validity

- Solutions are infeasible in practice
- Truck capacity constraints incomplete
- Day-specific routing not enforced

## Solution

### Option A: Restrict in_transit Variable Creation

Only create in_transit variables for route-date combinations where a truck exists:

```python
# Build mapping: (origin, destination) → set of valid departure days
truck_valid_days = {}
for truck in self.truck_schedules:
    route_key = (truck.origin_node_id, truck.destination_node_id)
    if route_key not in truck_valid_days:
        truck_valid_days[route_key] = set()

    if truck.day_of_week:
        truck_valid_days[route_key].add(truck.day_of_week)
    else:
        # Truck runs every day
        truck_valid_days[route_key] = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}

# Create in_transit only for valid days
in_transit_index = []
for route in self.routes:
    route_key = (route.origin_node_id, route.destination_node_id)
    valid_days = truck_valid_days.get(route_key, set())

    for prod in model.products:
        for departure_date in model.dates:
            # Check if truck runs on this day of week
            day_of_week = get_day_of_week_name(departure_date)

            if day_of_week not in valid_days:
                continue  # Skip this date - no truck

            for state in ['frozen', 'ambient']:
                in_transit_index.append((
                    route.origin_node_id,
                    route.destination_node_id,
                    prod,
                    departure_date,
                    state
                ))
```

**Benefits:**
- Prevents shipments on wrong days by construction
- Reduces number of variables (fewer invalid options)
- Makes solutions inherently feasible

### Option B: Add Day-of-Week Constraints

Keep all variables but add constraints to force them to zero on wrong days:

```python
def truck_day_enforcement_rule(model, origin, dest, prod, departure_date, state):
    """Force in_transit = 0 on days when no truck operates."""

    route_key = (origin, dest)
    valid_days = truck_valid_days.get(route_key, set())
    day_of_week = get_day_of_week_name(departure_date)

    if day_of_week not in valid_days:
        return model.in_transit[origin, dest, prod, departure_date, state] == 0

    return Constraint.Skip

model.truck_day_enforcement_con = Constraint(
    model.in_transit.index_set(),
    rule=truck_day_enforcement_rule,
    doc="Force shipments to zero on days with no truck"
)
```

**Benefits:**
- Simpler implementation (doesn't change variable creation)
- Explicit constraints (easier to debug)

**Drawbacks:**
- More variables than necessary
- Weaker LP relaxation

## Recommended Solution

**Use Option A** (restrict variable creation):
- Fewer variables (better performance)
- Infeasibility by construction (can't violate)
- Cleaner model structure

## Implementation Plan

1. Build truck_valid_days mapping from truck_schedules
2. Modify in_transit_index creation to check valid days
3. Handle intermediate stops at same time (expand routes first)
4. Test with Monday solve (should only see 6125 and 6104, not 6110)

## Related Bug

This fix should be combined with intermediate stop expansion to handle both issues together.

## References

- **Code:** src/optimization/sliding_window_model.py lines 522-536
- **Documentation:** MANUFACTURING_SCHEDULE.md (truck schedules)
- **Test:** Verify Monday shipments only to 6125, 6104

## Sign-off

**Identified by:** User observation (trucks on wrong days)
**Analyzed by:** Claude Code (AI Assistant)
**Date:** November 4, 2025
**Severity:** 🔴 CRITICAL - Invalid shipping schedules
**Status:** Documented, ready for fix
