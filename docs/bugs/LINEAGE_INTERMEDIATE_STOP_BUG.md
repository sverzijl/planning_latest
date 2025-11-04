# Critical Bug: Lineage Intermediate Stop Not Working

## Issue Summary

**Symptom:** Lineage receives no shipments, only has initial inventory (6400 units), causing shortages at 6130 (WA)

**Root Cause:** SlidingWindowModel does not handle intermediate truck stops

**Impact:** WA route (6122 → Lineage → 6130) completely broken

**Status:** 🔴 **CRITICAL BUG - BLOCKING WA DELIVERIES**

## Background

### WA Route Design

**Complete path:** 6122 (Manufacturing) → Lineage (Frozen Buffer) → 6130 (WA Breadroom)

**Why Lineage exists:**
- WA is remote, requires frozen shipment
- Lineage serves as frozen buffer/staging area
- Goods arrive ambient from 6122, get frozen at Lineage
- Ship frozen to 6130 (7-day transit)
- Thaw on arrival at 6130 (resets to 14-day shelf life)

### Truck Schedule

**Wednesday Morning Truck:**
- Route: 6122 → Lineage → 6125
- Intermediate stop: Lineage
- Purpose: Drop frozen goods at Lineage for WA, continue to 6125

### Routes in Data

1. **6122 → Lineage** (ambient, 1 day, cost=0)
2. **Lineage → 6130** (frozen, 7 days, cost=0)

Both routes exist in Network_Config.xlsx and parse correctly.

## Root Cause Analysis

### What's Missing

SlidingWindowModel has **NO intermediate stop handling**:

1. **Truck constraints** (line 2010): Only look at routes to final destination
   ```python
   routes_to_dest = [r for r in self.routes if r.destination_node_id == truck_dest]
   # truck_dest = 6125 (final destination)
   # Misses: 6122 → Lineage (intermediate)
   ```

2. **No intermediate shipment creation:** Model doesn't create in_transit variables for intermediate legs

3. **No freeze operation at Lineage:** Goods should arrive ambient, freeze, then ship frozen

### What Happens Instead

**Wednesday truck (6122 → Lineage → 6125):**
- Model sees: truck.destination_node_id = "6125"
- Creates shipments: 6122 → 6125 (direct)
- **Ignores:** 6122 → Lineage leg
- **Ignores:** Lineage → 6125 continuation
- **Result:** Lineage gets nothing

**Lineage inventory:**
- Initial: 6400 units frozen
- Inflows: 0 (no shipments from 6122)
- Outflows: Can ship to 6130, but limited by initial stock
- **Result:** 6130 shortages

## Expected Behavior

### Intermediate Stop Handling

When truck has intermediate_stops = ['Lineage']:

1. **Create shipment for first leg:** 6122 → Lineage
   - Mode: ambient (as per route definition)
   - Departs: Wednesday (truck departure)
   - Arrives: Thursday (1-day transit)

2. **Freeze operation at Lineage:** ambient → frozen
   - Create freeze flow variable
   - Link arrival to freeze to maintain material balance

3. **Create shipment for continuation:** Lineage → 6125
   - Mode: (per route from Lineage to 6125, if exists)
   - Same truck continues
   - Additional transit time

4. **Separate path to 6130:** Lineage → 6130
   - Mode: frozen (7-day transit)
   - Independent of 6125 route
   - Satisfies WA demand

## Impact

### Current State

- **6130 (WA):** Cannot receive goods → shortages
- **Lineage:** Unused frozen buffer → wasted capacity
- **Network:** 2-echelon routing broken for WA
- **Labeling:** Shows infeasible flow (demand exists but can't route)

### Business Impact

- WA customers not served
- Frozen buffer strategy ineffective
- Model doesn't match actual operations
- Planning results invalid for WA region

## Comparison: UnifiedNodeModel

Does UnifiedNodeModel handle intermediate stops?

Let me check...

*[To be investigated]*

## Solutions

### Option 1: Expand Routes for Intermediate Stops (Preprocessing)

Before building model, expand truck routes with intermediate stops into explicit route segments:

```python
def expand_intermediate_stops(truck_schedules, routes):
    """Expand trucks with intermediate stops into multi-leg routes."""

    expanded_routes = routes.copy()

    for truck in truck_schedules:
        if not truck.intermediate_stops:
            continue

        # Build path: origin → stop1 → stop2 → ... → destination
        path = [truck.origin_node_id] + truck.intermediate_stops + [truck.destination_node_id]

        # Find routes for each leg
        for i in range(len(path) - 1):
            origin = path[i]
            dest = path[i + 1]

            # Find existing route for this leg
            route = find_route(routes, origin, dest)
            if not route:
                print(f"WARNING: No route found for {origin} → {dest} (intermediate leg)")
                # Could create virtual route here

    return expanded_routes
```

### Option 2: Model Intermediate Stops Explicitly

Modify SlidingWindowModel to create variables/constraints for intermediate stops:

```python
# In _add_truck_constraints:
for truck in self.truck_schedules:
    if truck.intermediate_stops:
        # Create shipment variables for each leg
        current_origin = truck.origin_node_id

        for stop in truck.intermediate_stops:
            # Create in_transit for: current_origin → stop
            # Add to truck capacity
            current_origin = stop

        # Final leg: last_stop → destination
        # Create in_transit for: current_origin → truck.destination_node_id
```

### Option 3: Treat Intermediate Stops as Mandatory Routes

Force shipments through intermediate stops:

```python
# For Wednesday truck: 6122 → Lineage → 6125
# Add constraint: shipment_6122_to_Lineage_wednesday > 0 (if demand exists for WA)
```

## Recommended Fix

**Option 1** (Preprocessing) is cleanest:
- Expand intermediate stops into explicit routes BEFORE building model
- Ensures all route variables exist
- Handles freeze/thaw at intermediate nodes
- No changes to core model logic needed

**Implementation Plan:**
1. Add `expand_intermediate_stops()` function to converter
2. Call before passing routes to model
3. Document expanded routes clearly
4. Test with Wednesday truck → Lineage → 6125

## Testing Strategy

1. **Unit test:** Verify intermediate stop expansion
2. **Integration test:** Solve with Lineage route, check inventory
3. **Validate 6130:** Ensure WA demand is satisfied
4. **Check freeze flow:** Verify goods freeze at Lineage

## References

- **Truck Schedule:** Morning 6125 (Wed via Lineage)
- **Routes:** 6122 → Lineage, Lineage → 6130
- **Documentation:** NETWORK_ROUTES.md, MANUFACTURING_SCHEDULE.md
- **Code:** src/optimization/sliding_window_model.py (truck constraints)

## Sign-off

**Identified by:** User observation (Lineage not receiving goods)
**Analyzed by:** Claude Code (AI Assistant)
**Date:** November 4, 2025
**Severity:** 🔴 CRITICAL - Blocks WA deliveries
**Status:** Documented, awaiting fix implementation
