# State Tracking Implementation Plan

## Overview
Implement frozen/ambient state tracking for inventory with automatic state transitions based on transport mode and destination storage capabilities.

## Key Changes Required

### 1. Inventory Variables
**Current:** Single `inventory[dest, prod, date]` variable

**New:** State-specific variables
- `inventory_frozen[loc, prod, date]` - Frozen inventory at each location
- `inventory_ambient[loc, prod, date]` - Ambient/thawed inventory at each location

**Locations requiring inventory:**
- All breadrooms with demand (existing)
- Lineage frozen storage (NEW)
- Any other intermediate storage locations

### 2. State Transition Rules

**Arrival state based on route and destination:**

| Route Transport Mode | Destination Storage | Arrival State |
|---------------------|---------------------|---------------|
| frozen              | frozen only         | frozen        |
| frozen              | ambient only        | ambient (thawed) |
| frozen              | both                | ambient (thawed) |
| ambient             | any                 | ambient       |

**Special Cases:**
- 6130: Frozen arrivals thaw automatically, shelf life resets to 14 days
- Lineage: Only receives frozen, stores frozen (120-day shelf life)
- Most breadrooms: Ambient only, can only receive ambient product

### 3. Inventory Balance Constraints

**Frozen Inventory:**
```
inventory_frozen[loc, prod, t] =
    inventory_frozen[loc, prod, t-1]
    + arrivals_frozen[loc, prod, t]
    - outflows_frozen[loc, prod, t]
```

**Ambient Inventory:**
```
inventory_ambient[loc, prod, t] =
    inventory_ambient[loc, prod, t-1]
    + arrivals_ambient[loc, prod, t]
    + arrivals_from_frozen_thawed[loc, prod, t]  # State transition
    - demand[loc, prod, t]
    - shortage[loc, prod, t]
```

**Key Rules:**
- Frozen inventory only decreases via outbound shipments (no demand from frozen)
- Ambient inventory satisfies demand
- When frozen product arrives at ambient/both location → automatic thaw → ambient inventory

### 4. Shelf Life Constraints

**Frozen Inventory:**
- No shelf life decay (or 120-day limit)
- Can be stored indefinitely at Lineage

**Ambient Inventory:**
- 17-day shelf life from production date
- Tracks age of inventory
- Must have ≥7 days remaining when delivered to breadroom

**Special: 6130 Thawed Inventory:**
- 14-day shelf life from thaw date (arrival date)
- Shelf life resets when product thaws at 6130
- Must have ≥7 days remaining for demand satisfaction

### 5. Implementation Steps

1. **Identify all locations needing inventory variables** (not just demand locations)
2. **Create state-specific inventory variables** (frozen + ambient)
3. **Determine arrival state for each route** based on transport mode and destination
4. **Update inventory balance constraints** to handle state transitions
5. **Add shelf life decay constraints** for ambient inventory
6. **Handle 6130 special thawing** shelf life reset
7. **Update demand satisfaction** to only use ambient inventory
8. **Update solution extraction** to report state-specific inventory

### 6. Route Analysis for State Transitions

**Routes to Lineage:**
- 6122 → Lineage: frozen mode → arrives frozen at Lineage ✓

**Routes from Lineage:**
- Lineage → 6130: frozen mode → 6130 has "both" storage → **arrives as AMBIENT (thawed)**
- This is the key state transition!

**Routes to other locations:**
- Most routes are ambient mode → arrive ambient
- 6104, 6125 are breadrooms (ambient only) → must receive ambient

### 7. Data Structures Needed

```python
# Location categorization
locations_by_storage_mode = {
    'frozen': ['Lineage'],
    'ambient': ['6103', '6104', '6105', '6110', '6123', '6125', '6134'],
    'both': ['6120', '6130']
}

# Route arrival states
route_arrival_state = {}  # route_index -> 'frozen' or 'ambient'

# For each route:
#   if route.transport_mode == 'frozen' and dest.storage_mode == 'frozen':
#       arrival_state = 'frozen'
#   else:
#       arrival_state = 'ambient'  # Thaws if frozen transport to non-frozen dest
```

## Testing Strategy

1. **Test frozen route:** 6122 → Lineage → 6130
   - Verify product arrives frozen at Lineage
   - Verify product thaws when leaving Lineage for 6130
   - Verify 14-day shelf life at 6130

2. **Test ambient routes:** 6122 → 6125 → other breadrooms
   - Verify ambient state maintained throughout
   - Verify 17-day shelf life applies

3. **Compare with existing model:**
   - Should produce same/better results
   - Should have same or lower cost
   - Should properly account for frozen buffer value

## Backward Compatibility

- If all routes are ambient, model behaves like current implementation
- Frozen routes are an enhancement, not a breaking change
- Existing tests should still pass (or produce better results)
