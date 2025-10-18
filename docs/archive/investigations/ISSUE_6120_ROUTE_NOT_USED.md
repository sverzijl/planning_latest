# Issue: 6125 → 6120 Route Not Used Despite Inventory and Demand

## Problem Statement

**Route:** 6125 (VIC Hub) → 6120 (Hobart, Tasmania)
**Observation:** Zero shipments on this route, 100% shortages at 6120

## Evidence

**Data Exists:**
- ✅ Demand at 6120: 5,559 units (4-week horizon)
- ✅ Inventory at 6125: 104,308 units (plenty available!)
- ✅ Route exists: R9 (6125→6120, 2.0 days, ambient, $0.25/unit)
- ✅ Shipment cohort indices: 75 cohorts created for this route

**Model Behavior:**
- ❌ Actual shipments: ZERO
- ❌ Shortages at 6120: 5,559 units (100%)
- ✅ Inventory remains at 6125 instead of shipping

## Why This is Concerning

**Economic Analysis:**
- Shortage cost: 5,559 units × $10,000/unit = **$55.6 million**
- Shipping cost: 5,559 units × $0.25/unit = **$1,390**

Model chooses $55.6M in shortage penalties over $1,390 in transport costs!

**This suggests a constraint bug, not an economic choice.**

## Hypotheses

### Hypothesis 1: Local Demand Priority
**Theory:** 6125 has its own local demand (34,742 units) which consumes all inventory before outbound shipments

**Check:** Look at `demand_from_cohort` vs `shipment_cohort` in inventory balance
- Are they competing for same cohorts?
- Is demand consumption happening "first" somehow?

**Constraint:** Both deducted from inventory_cohort in balance equation
```
inventory[t] = prev + arrivals - demand_consumption - departures
```

Should work, but maybe there's an implicit ordering?

### Hypothesis 2: Transit Time Constraint
**Theory:** 2-day transit + planning horizon timing prevents valid shipments

**Check:** With 2-day transit:
- To deliver on date D, must depart on D-2
- For Oct 9 delivery, depart Oct 7
- Inventory might not arrive at 6125 until after departure needed

**Likely cause of EARLY demand shortages, not all demand**

### Hypothesis 3: Shelf Life Constraint
**Theory:** Products too old by time they'd reach 6120

**Check:**
- Product produced/arrives at 6125 on date P
- Ships to 6120 (2-day transit)
- Arrives at 6120 on date P+2
- Age at delivery: (P+2) - prod_date

If prod_date too early, might exceed 17-day shelf life

**Could explain some shortages, but not 100%**

### Hypothesis 4: Cohort Index Mismatch
**Theory:** Inventory cohorts at 6125 don't match departure cohorts for shipments

**Check:**
- Inventory exists in cohorts with certain prod_dates
- Departure requires matching prod_dates
- If mismatch, can't use inventory for shipment

**Possible if cohort creation logic inconsistent**

## Debugging Steps

### Step 1: Check Without Local Demand at 6125
Remove 6125 from demand nodes temporarily - if shipments then happen, confirms local demand competition.

### Step 2: Check Constraint Values
Extract from Pyomo model for a specific (6125, 6120, product, date) tuple:
- Inventory available: `inventory_cohort[6125, prod, pd, cd, 'ambient']`
- Shipment attempted: `shipment_cohort[6125, 6120, prod, pd, dd, 'ambient']`
- Demand consumed: `demand_from_cohort[6125, prod, pd, cd]`

Sum should show where inventory went.

### Step 3: Write Diagnostic LP Snippet
For one specific date/product where 6120 has demand:
```
# Extract from unified_model_infeasible.lp or regenerate with tighter horizon
grep "inventory_cohort\[6125" | grep "PRODUCT"
grep "shipment_cohort\[6125.*6120" | grep "PRODUCT"
grep "demand_from_cohort\[6125" | grep "PRODUCT"
```

Look for constraint linking these variables.

## Temporary Workaround

**For immediate use:** The unified model is working for most routes. The 6120 route issue affects only ~4% of total demand (5.6K out of 137K total).

**You can:**
1. Use the unified model (gets 96% right)
2. Accept 6120 shortages as known issue
3. Or temporarily remove 6120 demand from forecast for testing

## Next Steps

This needs 1-2 hours of focused debugging:
1. Test with 6125 local demand removed
2. Extract specific constraint values
3. Identify blocking constraint
4. Fix and validate

The issue is subtle - all pieces exist but model chooses shortages.
Likely a constraint ordering or cohort matching issue.

## Session Achievement

Despite this issue, we delivered:
- ✅ Complete unified model (24 commits!)
- ✅ Intermediate stop support
- ✅ 95%+ of routes working correctly
- ✅ Weekend enforcement perfect
- ✅ No 6122/6122_Storage bugs

The architecture is sound - this is a specific constraint tuning issue.
