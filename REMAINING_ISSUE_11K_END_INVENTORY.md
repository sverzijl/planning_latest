# Remaining Issue: 11k Wasted End Inventory

## Problem Statement

**Issue:** Full 4-week integration test shows 11,025 units of end inventory at hubs (6125: 8,249, 6104: 2,742) that serves NO purpose.

**Evidence:**
- End inventory: 11,025 units
- Shipments after horizon: 0 units
- Inventory is NOT used for any post-horizon deliveries
- **This is wasted production** - Objective function should prevent it!

## Why This is a Bug

**The objective function includes:**
- Production cost: $5/unit × 11,025 = $55,125 wasted
- Labor cost: Additional hours to produce the excess
- Inventory holding: $8,890 total

**The model should minimize cost** → Should NOT produce 11,025 unnecessary units!

## Paradox: Simple Tests Work, Full Scenario Doesn't

**All simple tests show 0 end inventory:**
- ✅ 1 prod, 1-4 weeks: 0
- ✅ 5 prods, 1 week: 0
- ✅ 1 prod, 3 dests, 1 week: 0
- ✅ WA via Lineage, 1-3 weeks: 0
- ✅ 2 prods, 2 dests, 2 weeks: 0

**Full 4-week integration shows 11k end inventory:**
- ❌ 5 prods, 8 dests, 4 weeks: 11,025 units

**Key Differences:**
1. Simple tests: Uniform synthetic demand (100 units/day)
2. Full scenario: Real forecast with variable daily demand patterns
3. Simple tests: Use batch tracking with automatic freeze/thaw
4. Full scenario: Same constraints but at much larger scale

## Hypotheses for Investigation

### Hypothesis 1: Packaging/Batching Constraints
- Production in 10-unit cases might create rounding excess
- 11,025 units = 1,102.5 cases (half-case excess?)
- But simple tests also have packaging constraints and show 0...

### Hypothesis 2: Truck Loading Patterns
- Truck schedules force specific loading patterns
- May create batching that leaves residual inventory
- Simple tests have truck schedules too...

### Hypothesis 3: Real Forecast Demand Pattern
- Spiky demand in real data vs uniform in tests
- Late-horizon demand may trigger production that isn't fully consumed
- Need to check demand distribution near Nov 4

### Hypothesis 4: Production Smoothing
- Model may smooth production across days
- Could create inventory buffer that isn't fully depleted
- Check if smoothing constraints are active

### Hypothesis 5: Hub Flow Conservation Bug
- Hubs receive inventory from manufacturing
- Hub demand + spoke demand should deplete hub inventory
- Maybe hub outbound flow is undercounted?

## Material Balance Breakdown

```
Production: 215,450 units
Consumption: 237,136 units
End inventory: 11,025 units
Total usage: 248,161 units

Deficit: 215,450 - 248,161 = -32,711 units
```

**Two separate issues:**
1. **-33k material balance deficit** (phantom consumption of 33k units)
2. **+11k wasted end inventory** (unnecessary production)

These might be related: If 33k phantom inventory is created, part of it (11k) remains at end.

## Investigation Status

**Progress:**
- ✅ Reduced end inventory from 21k → 11k (-49%)
- ✅ All simple tests have perfect balance and 0 end inventory
- ✅ Confirmed objective function works (production < demand)
- ❌ Full scenario still has 11k wasted inventory

**Remaining Work:**
- Identify constraint/pattern that creates 11k excess ONLY in full scenario
- Check if it's hub-specific (inventory at 6104/6125)
- Verify if late-horizon demand patterns trigger the bug

## Recommended Next Steps

1. **Test with real forecast, 1 week only** - Does 1 week real data show end inventory?
2. **Progressive weeks with real forecast** - At what week does end inventory appear?
3. **Check hub demand vs spoke demand split** - Is hub inventory from dual role?
4. **Examine last 3 days of horizon** - Is late demand creating the excess?
5. **Disable packaging constraints temporarily** - Is 10-unit rounding the culprit?

The paradox (simple = 0, full = 11k) suggests the bug is scale-dependent or triggered by specific real forecast patterns.

---

**Status:** Documented as remaining investigation item. Simple tests prove model fundamentals are sound. Issue is isolated to full-scale real forecast scenarios.
