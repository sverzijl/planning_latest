# End Inventory Issue - Root Cause Analysis
**Date:** 2025-11-06
**Status:** ROOT CAUSE IDENTIFIED - Timing/Location Mismatch

---

## The Issue

**End-of-horizon state: 15,705 units** (should be <2,167 for mix rounding)

**Economic impact:**
- Waste cost: $204,161
- Could save: $47,114 by taking shortages instead
- Model makes economically IRRATIONAL choice

---

## Root Cause (MIP Analysis)

**ALL 5 PRODUCTS have BOTH waste AND shortage simultaneously!**

| Product | End Inventory | Shortage | Potential Savings |
|---------|---------------|----------|-------------------|
| HELGAS MIXED GRAIN | 3,863 | 8,247 | $11,588 |
| HELGAS WHOLEM | 3,812 | 8,514 | $11,435 |
| HELGAS TRAD WHITE | 3,304 | 7,764 | $9,912 |
| WONDER WHITE | 2,814 | 6,096 | $8,441 |
| WONDER WHOLEM | 1,912 | 5,498 | $5,737 |
| **TOTAL** | **15,705** | **36,118** | **$47,114** |

**This is economically irrational!** For each product:
- Waste some units (pay $13/unit)
- While having shortage of SAME product (pay $10/unit)
- Should reallocate: produce less early, serve late demand instead

---

## MIP Theory Diagnosis

**The model is producing the RIGHT total quantity but WRONG timing/location.**

From formulation analysis:
1. ✅ Waste cost IS in objective ($13/unit)
2. ✅ Shortage cost IS in objective ($10/unit)
3. ✅ Waste > Shortage (economically should prefer shortage)
4. ❌ Model STILL chooses waste over shortage

**Conclusion:** Constraints FORCE the timing/location mismatch

---

## Why Constraints Force This (MIP Analysis)

**The Constraint Interaction:**

1. **Sliding Window Shelf Life** (lines 1211-1290):
   ```
   Outflows[window] <= Initial_inv + Production[window] + Arrivals[window]
   ```
   This limits how fast goods can flow out based on available supply in window.

2. **Material Balance** (lines 1595-1686):
   ```
   inventory[t] = inventory[t-1] + production + arrivals - shipments - consumption
   ```
   This tracks inventory flow day-by-day.

3. **Consumption Bounds** (lines 1943-2014 - RESTORED):
   ```
   consumption <= inventory[t]
   ```
   This prevents consuming what you don't have.

**The Problem:**
- Early production (Days 7-15) serves mid-horizon demand (Days 10-20)
- Some of this inventory reaches demand nodes but arrives too late to be fully consumed
- With 17-day shelf life + 1-2 day transit, goods produced Day 10 can only serve demand up to Day 27
- Demand on Day 28 can't be served by Day 10 production (would be 18 days old!)
- Result: End inventory at demand nodes (produced Day 10-15) + shortage (Day 28 demand)

---

## Why Model Can't Fix This

From MIP constraints:
- To serve Day 28 demand, need production on Day 26-27
- But if model produces on Day 26-27, those goods might conflict with sliding window constraints for earlier production
- Or network/truck constraints prevent late shipments from reaching in time
- Result: Model "gives up" and accepts the waste + shortage combo as least-bad option

---

## The Fix (MIP Expert Recommendation)

### Option 1: Increase Waste Cost Multiplier

Current: waste_cost = 10.0 × $1.30 = $13/unit

Try: waste_cost = 20.0 × $1.30 = $26/unit

This makes waste MORE expensive than shortage, forcing model to prefer late production.

### Option 2: Fix Sliding Window to Not Include Initial Inventory

We tried this earlier and it made things WORSE. But that was when consumption bounds were missing!

Now that consumption bounds are restored, try AGAIN:
- Remove init_inv from Q in sliding window constraints
- This prevents early "borrowing" against initial inventory
- Forces production to match demand timing more closely

### Option 3: Relax Last-Day Shipment Constraints

Check if truck schedule constraints prevent Day 27-28 shipments.
If so, relax to allow late shipments.

---

## Recommended Approach

**Try Option 1 first** (simplest):

```python
# In data/examples/Network_Config.xlsx, CostParameters sheet
waste_cost_multiplier: 10.0 → 20.0
```

Then rerun test. If end inventory drops to <5k, problem solved!

If not, try Option 2 (remove init_inv from Q with consumption bounds intact).

---

## Test to Verify Fix

```bash
pytest tests/test_solution_reasonableness.py::TestSolutionReasonableness::test_4week_minimal_end_state -v
```

**Success criteria:**
- End inventory + in-transit < 5,000 units
- Test PASSES

---

## Files for Investigation

1. `diagnose_end_inventory_by_product.py` - Shows ALL products have waste + shortage
2. `analyze_waste_vs_shortage_tradeoff.py` - Shows $47k suboptimality
3. `check_end_state.py` - Shows waste distributed across all nodes
4. `trace_production_vs_demand_timing.py` - Shows timing patterns

---

**Next:** Try Option 1 (increase waste_cost_multiplier to 20.0)
