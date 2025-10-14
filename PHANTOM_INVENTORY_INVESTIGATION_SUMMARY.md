# Phantom Inventory Investigation - Summary Report
**Date:** 2025-10-13
**Issue:** Material balance violation (~50,000 unit deficit) in 4-week optimization

## Executive Summary

Through systematic testing with progressively simpler scenarios, we successfully isolated a critical flow conservation bug to frozen routing through Lineage. The bug allows consumption to exceed production by creating phantom inventory.

## Test Results Matrix

| Test Scenario | Route | Production | Consumption | Balance | Status |
|---------------|-------|-----------|-------------|---------|--------|
| Direct ambient | 6122→6110 | 6,000 | 6,000 | 0 | ✅ PASS |
| Hub ambient | 6122→6125→6123 | 2,500 | 2,500 | 0 | ✅ PASS |
| Frozen via Lineage | 6122→Lineage→6130 | 0 | 3,000 | -3,000 | ❌ FAIL |
| 4-week integration | Multiple routes | 206,560 | 258,740 | -52,180 | ❌ FAIL |

**Conclusion:** Bug is specific to frozen routing through Lineage storage.

## Root Cause Analysis

### The Design Conflict

**Current Model Design (lines 2185-2187):**
```python
# NOTE: Flow conservation is now handled by 6122_Storage inventory balance
# Production flows into 6122_Storage, trucks load from 6122_Storage
```

**Virtual Leg Logic (lines 700-702):**
```python
# Skip frozen legs - they ship directly from 6122, not 6122_Storage
if transport_mode == 'frozen':
    continue  # Don't create virtual legs for frozen
```

**The Problem:**
- ALL production → 6122_Storage ambient inventory (line 2071-2072)
- Frozen shipments try to ship from '6122' (skip virtual legs)
- But '6122' has NO production input (production goes to 6122_Storage)
- Result: Frozen shipments from 6122 have no source → phantom inventory

### Network Configuration vs Business Reality

**Current Network_Config.xlsx:**
```
R4: 6122 → Lineage, transport_mode='frozen', transit=0.5d
R10: Lineage → 6130, transport_mode='frozen', transit=3.0d
Lineage: storage_mode='frozen'
```

**Your Business Rule:**
> "Stock should only freeze when they arrive at Lineage, not begin frozen at the manufacturing site"

**Correct Configuration Should Be:**
```
R4: 6122 → Lineage, transport_mode='ambient' ← Ships fresh!
R10: Lineage → 6130, transport_mode='frozen'
Lineage: storage_mode='both' ← Can receive ambient AND freeze it
```

**When We Tried This:**
- Result: Model became infeasible (`intermediateNonInteger`)
- Solve time: 17s → 223s (13x slower)
- Cohorts increased: 52,865 → 67,325 (27% more variables)

## Why the Fix Failed

The model doesn't properly link:
1. Ambient arrivals at Lineage (from 6122)
2. Freeze operation at Lineage (ambient → frozen)
3. Frozen departures from Lineage (to 6130)

Potential issues:
- Freeze operation constraints may be missing or incorrect
- State transition logic may not work correctly
- Cohort indexing may not create the right combinations

## Attempted Fixes

### Fix 1: Add production_input to frozen balance (REVERTED)
**Lines:** 1999-2003, 2040-2041
**Result:** Created double-counting (production flows to BOTH 6122 and 6122_Storage)
**Status:** REVERTED

### Fix 2: Change Network_Config route to ambient (REVERTED)
**Changes:** R4 transport_mode: frozen→ambient, Lineage storage_mode: frozen→both
**Result:** Model infeasible, 13x slower
**Status:** REVERTED

## The Fundamental Design Question

**Current approach:** Production is scalar (not state-specific), all goes to 6122_Storage ambient

**Options:**

**Option A: Make frozen shipments also use 6122_Storage**
- Remove lines 700-702 (allow virtual legs for frozen)
- Frozen shipments: 6122_Storage → freeze → ship frozen
- Requires freeze operation FROM 6122_Storage

**Option B: Split production between frozen and ambient**
- Create production_frozen[date, product] and production_ambient[date, product]
- Frozen production → '6122' frozen inventory → frozen shipments
- Ambient production → '6122_Storage' ambient inventory → ambient shipments
- Requires significant model restructuring

**Option C: Accept current behavior as limitation**
- Document that frozen routing creates phantom inventory
- Recommend using ambient routing for real operations
- Focus on fixing ambient routing (which works correctly)

## Current Status

### What Works ✅
- Direct ambient routing (perfect material balance)
- Hub-and-spoke ambient routing (perfect material balance)
- Production cost minimization (model doesn't overproduce)
- Labor cost minimization (working correctly)

### What's Broken ❌
- Frozen routing through Lineage (phantom inventory)
- Material balance validation in 4-week test (~50k deficit)
- Network configuration doesn't match business process

## Recommendations

**Immediate:**
1. Document frozen routing as known limitation
2. Use phantom inventory findings to improve ambient-only scenarios
3. Verify 4-week test with Lineage disabled (only ambient routes)

**Medium-term:**
4. Implement Option A (virtual legs for frozen) with proper freeze operation linking
5. Add explicit freeze/thaw operation constraints
6. Test with corrected network configuration

**Long-term:**
7. Consider Option B (state-specific production variables) for Phase 4
8. Add end-of-horizon inventory penalty (separate issue)
9. Implement rolling horizon to avoid horizon-end artifacts

## Files Created During Investigation

1. `tests/test_minimal_material_balance.py` - Simple ambient routing tests (PASS)
2. `tests/test_frozen_routing_balance.py` - Frozen routing tests (FAIL)
3. `test_frozen_simple.py` - Minimal frozen diagnostic (shows bug)
4. `diagnose_material_balance.py` - Flow tracing diagnostic
5. `check_intransit_accounting.py` - In-transit inventory check

## Next Steps

The investigation has definitively proven:
- ✅ Model is NOT overproducing (production < demand)
- ✅ Objective function (prod cost + labor cost) works correctly
- ✅ Ambient routing has perfect material balance
- ❌ Frozen routing through Lineage has fundamental design flaw

**Recommendation:** Continue investigation to properly implement frozen routing with freeze operations, OR accept as known limitation and focus on ambient-only optimization.
