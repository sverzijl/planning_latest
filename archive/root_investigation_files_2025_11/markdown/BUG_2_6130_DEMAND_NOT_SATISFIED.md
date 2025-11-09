# CRITICAL BUG #2: 6130 Demand Not Being Satisfied

## Status: IDENTIFIED - Root Cause Analysis Needed

## Problem Summary

Location 6130 (WA) has significant demand in the forecast but the optimization model is:
- ✅ Shipping goods TO 6130 (6,627 units received)
- ❌ NOT consuming inventory to satisfy demand (0 units consumed)
- ❌ Recording 100% shortage (14,154 units short)
- ❌ Leaving inventory static (937 units initial inventory unused)

## Evidence

### Forecast Data
```
Total 6130 demand in forecast: 235,111 units (full horizon)
6130 demand in planning horizon: 14,154 units (22 days)
Date range: 2025-10-17 to 2025-11-07
Products: All 5 gluten-free SKUs
```

### Solution Data (initial_20251105_1528.json)
```
Demand consumed at 6130: 0 units
Shortages at 6130: 14,154 units (100% shortage!)
Shipments TO 6130: 6,627 units
Initial inventory at 6130: 937 units (static, never consumed)
Inventory state at 6130: 26,236 units total (ambient)
```

### Comparison with Other Locations
```
Locations WITH demand satisfied: ['6103', '6104', '6105', '6110', '6120', '6123', '6125', '6134']
Location WITHOUT demand satisfied: ['6130']  ← ONLY 6130 affected!
```

## Root Cause Hypotheses

### Hypothesis 1: Thaw Flow Constraint Issue
6130 is the ONLY location that receives **thawed** product (frozen → thawed reset to 14 days).

**Possible Issues:**
1. Thaw flow variables not created for 6130
2. Thaw operation not allowed/constrained
3. State transition logic broken for thawed inventory

**Evidence:**
- Shipments TO 6130 show `state: 'thawed'` (6,627 units)
- Inventory at 6130 shows `state: 'ambient'` (26,236 units)
- **Mismatch**: Received thawed but inventory shows ambient?

### Hypothesis 2: Demand Satisfaction Constraint Missing 6130
The demand satisfaction constraints may not be applied to 6130.

**Check:**
- Does `model.demand_satisfaction_con` include 6130?
- Are shortage variables created for 6130?
- Is 6130 categorized incorrectly (as hub instead of destination)?

### Hypothesis 3: Shelf Life Constraint Too Restrictive
Thawed product arriving at 6130 may be failing shelf life checks.

**Business Rule**: Breadrooms discard stock with <7 days remaining
**Thawed shelf life**: 14 days

**Possible Issue:**
- Transit time + thaw time + age = >7 days remaining?
- Shelf life window constraint excluding thawed inventory?

### Hypothesis 4: Node Type Classification Error
6130 may be incorrectly classified in the node setup.

**Check:**
- Is 6130 a `destination` node or classified as `storage`/`hub`?
- Do demand satisfaction constraints only apply to `destination` nodes?

## Investigation Steps

1. **Check thaw flow variables**:
   ```python
   # In sliding_window_model.py
   # Search for thaw flow variable creation
   # Verify 6130 is included in thaw_index
   ```

2. **Check demand satisfaction constraints**:
   ```python
   # Look for demand_satisfaction_con
   # Verify 6130 is in the constraint index
   ```

3. **Check node classification**:
   ```python
   # In unified_node.py or converter
   # Verify 6130.node_type == 'destination'
   # Verify 6130.can_satisfy_demand() returns True
   ```

4. **Check shelf life logic for thawed**:
   ```python
   # In sliding_window_model.py
   # Check if thawed_shelf_life constraints apply to 6130
   ```

## Impact

**Critical**: 6130 (WA) is receiving NO service despite having demand and receiving shipments.
- Business impact: 100% shortage at major destination
- Cost impact: Shipping goods that can't be used
- Inventory waste: 937 + 6,627 = 7,564 units unusable

## Next Steps

1. Add diagnostic logging to identify which constraint is blocking demand satisfaction
2. Check node setup for 6130 in converter and model
3. Verify thaw flow variables exist for 6130
4. Test with simplified scenario (6130 demand only)

## Validation Enhancement Needed

Add validator to catch this automatically:

```python
def _validate_demand_nodes_receive_service(self):
    """Check all nodes with demand either satisfy it or have shortages."""

    # Get all nodes with demand
    nodes_with_demand = set(...)

    # Get nodes with ANY consumption OR shortage
    nodes_serviced = set(demand_consumed.keys()) | set(shortages.keys())

    # Find nodes with demand but NO service
    unserviced = nodes_with_demand - nodes_serviced

    if unserviced:
        errors.append(f"Nodes {unserviced} have demand but zero consumption and zero shortages!")
```

## Priority: HIGH

This is a critical bug affecting demand satisfaction at a major destination.
