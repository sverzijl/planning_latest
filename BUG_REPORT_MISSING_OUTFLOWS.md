# Critical Bug Report: Missing Outflow Term in Ambient Inventory Balance

## Summary

**Bug:** The ambient inventory balance constraint for standard locations (non-6122, non-intermediate-storage) does not include an outflow term for leg-based shipments departing from the location.

**Impact:** Flow conservation is violated at hub locations (6104, 6125) that both consume demand AND forward units to spoke locations.

**Severity:** CRITICAL - Produces incorrect solutions with artificially low production and costs

## Root Cause Analysis

### Current Implementation (src/optimization/integrated_model.py:1354-1356)

```python
# Standard inventory balance for other locations
return model.inventory_ambient[loc, prod, date] == (
    prev_ambient + ambient_arrivals - demand_qty - shortage_qty
)
```

This constraint is **MISSING the outflow term** for locations that have outgoing legs.

### Expected Implementation

```python
# Calculate ambient outflows (shipments departing from this location)
ambient_outflows = 0
legs_from_loc = self.legs_from_location.get(loc, [])
for (origin, dest) in legs_from_loc:
    if self.leg_arrival_state.get((origin, dest)) == 'ambient':
        # Shipments depart on date and arrive after transit_days
        ambient_outflows += model.shipment_leg[(origin, dest), prod, date]

return model.inventory_ambient[loc, prod, date] == (
    prev_ambient + ambient_arrivals - demand_qty - shortage_qty - ambient_outflows
)
```

## Evidence of Bug

### Test Case: 29-Week Full Dataset

**Forecast Demand:**
- Total: 2,407,299 units
  - Hub demand (6104 + 6125): 691,334 units (29%)
  - Spoke demand: 1,715,965 units (71%)

**Model Results (INCORRECT):**
- Production: 1,059,895 units
- Initial inventory: 75,000 units
- **Total supply: 1,134,895 units**
- **Total demand: 2,407,299 units**
- **Deficit: 1,272,404 units**
- Reported shortages: **0 units** ← IMPOSSIBLE!
- Cost: **$5.8M** (expected ~$13M)

### Hub Flow Analysis

**Hub 6104:**
- Demand at 6104: 432,595 units
- Inflow to 6104: 432,595 units (exactly matches demand)
- Outflow from 6104: 417,246 units (to spokes 6103 + 6105)
- **Net balance: 432,595 - 432,595 - 417,246 = -417,246** ← NEGATIVE INVENTORY!

**Hub 6125:**
- Demand at 6125: 258,739 units
- Inflow to 6125: 258,739 units (exactly matches demand)
- Outflow from 6125: 645,257 units (to spokes 6123 + 6134 + 6120)
- **Net balance: 258,739 - 258,739 - 645,257 = -645,257** ← NEGATIVE INVENTORY!

The hubs are receiving just enough to satisfy their own demand, but then ALSO forwarding units to spokes without accounting for those outflows in the inventory balance.

### Why The Old Model Cost ~$13M

The "old model" likely:
1. Used route-based (not leg-based) routing, OR
2. Didn't have hub demand in the forecast, OR
3. Had the outflow term correctly implemented

With proper flow conservation, the model would need to produce:
- Spoke demand: 1,715,965 units
- Hub consumption: 691,334 units
- **Total production required: ~2.4M units** (minus initial inventory)
- Expected cost: ~$13M

## Comparison of Inventory Balance Implementations

| Location Type | Inflows | Outflows | Demand | Implementation Status |
|--------------|---------|----------|--------|----------------------|
| 6122_Storage | Production | Truck loads | 0 | ✅ Correct (line 1297-1313) |
| Intermediate storage (Lineage) | Frozen legs | Frozen legs | 0 | ✅ Correct (line 1213-1229) |
| **Hub locations (6104, 6125)** | **Ambient legs** | **Ambient legs** | **Non-zero** | **❌ MISSING OUTFLOWS (line 1354-1356)** |
| Final destinations (6103, 6105, etc.) | Ambient legs | 0 | Non-zero | ✅ Correct (no outflows) |

## Fix Required

### File: `src/optimization/integrated_model.py`

### Location: Lines 1316-1356 (ambient inventory balance for standard locations)

### Change Required:

**Before:**
```python
# Standard inventory balance for other locations
...
return model.inventory_ambient[loc, prod, date] == (
    prev_ambient + ambient_arrivals - demand_qty - shortage_qty
)
```

**After:**
```python
# Standard inventory balance for other locations
...

# LEG-BASED ROUTING: Calculate ambient outflows from this location
ambient_outflows = 0
legs_from_loc = self.legs_from_location.get(loc, [])
for (origin, dest) in legs_from_loc:
    if self.leg_arrival_state.get((origin, dest)) == 'ambient':
        # Units shipped on this leg must come from inventory on this date
        ambient_outflows += model.shipment_leg[(origin, dest), prod, date]

return model.inventory_ambient[loc, prod, date] == (
    prev_ambient + ambient_arrivals - demand_qty - shortage_qty - ambient_outflows
)
```

## Expected Impact of Fix

After fixing, the model should:
1. ✅ Correctly enforce flow conservation at all locations
2. ✅ Produce ~2.4M units to satisfy total demand (hubs + spokes)
3. ✅ Report cost of ~$13M (matching old model)
4. ✅ Show zero shortages (if `allow_shortages=False`)
5. ✅ Have positive inventory at all hubs throughout planning horizon

## Testing Plan

1. Apply fix to `integrated_model.py`
2. Run `test_29weeks_no_shortages.py`:
   - Expect: Production ~2.4M units
   - Expect: Cost ~$13M
   - Expect: Zero shortages
   - Expect: All demand satisfied
3. Run `trace_unit_flow.py`:
   - Expect: Hub inflows = hub demand + hub outflows
   - Expect: No negative inventory balances
4. Run `diagnose_shortages.py`:
   - Expect: Zero shortages
5. Run `check_hub_demand.py`:
   - Confirm: 6104 and 6125 are valid breadroom+hub locations

## Related Files

**Created during investigation:**
- `diagnose_shortages.py` - Shortage analysis
- `trace_unit_flow.py` - Flow conservation check
- `check_hub_demand.py` - Forecast demand analysis

**Affected model files:**
- `src/optimization/integrated_model.py` (lines 1316-1356)

**Migration documentation:**
- `LEG_BASED_ROUTING_MIGRATION.md` - Documents Phase 1 & 2 of leg-based routing migration

## Lessons Learned

1. **Flow conservation is critical:** Every inflow must have a matching outflow or storage term
2. **Hub-and-spoke networks are complex:** Locations that both consume AND forward require careful accounting
3. **Test with multiple location types:** Manufacturing, intermediate storage, hubs with demand, final destinations
4. **Mass balance verification is essential:** Always verify supply = demand + storage + losses

## Date Identified

2025-01-[date from current investigation]

## Status

**IDENTIFIED - AWAITING FIX**
