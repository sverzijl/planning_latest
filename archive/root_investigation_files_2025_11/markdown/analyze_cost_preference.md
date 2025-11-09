# Cost Preference Analysis: Why Model Chooses Shortage Over Production

## Observed Behavior

Model chooses:
- Production: 0 units
- Shortage: 346,687 units @ $10/unit = **$3,466,870**
- Total cost: $3,833,220

## Economic Comparison

### Option A: Produce 100 units
```
Production: 100 units × $1.30 = $130
Labor: ~0.07 hours × $20/hour = $1.40
Transport: 100 units × $0.10 = $10
Holding: minimal
Total: ~$141.40 for 100 units = $1.41/unit delivered
```

### Option B: Take Shortage
```
Shortage: 100 units × $10 = $1,000
Total: $1,000 for 100 units = $10/unit
```

**Option A is 7× cheaper!** Model should prefer production.

##  Hypotheses

### Hypothesis 1: Production Variables Not Linked to Demand Reduction

**Issue:** Maybe producing inventory doesn't actually reduce shortages?

**Test:** Check if production → inventory → demand_consumed chain is complete

### Hypothesis 2: Initial Inventory Blocking Production

**Issue:** Maybe initial inventory is still being mishandled, creating "infinite supply"

**Test:** Check sliding window constraints on Day 18+ (should exclude init_inv)

### Hypothesis 3: Demand_Consumed Not Constrained

**Issue:** Maybe demand_consumed can be > inventory (ghost consumption)

**Test:** Check if material balance actually limits demand_consumed

### Hypothesis 4: Shortage Variables Unbounded

**Issue:** Maybe shortage penalty not actually in objective?

**Evidence:** We see shortage_cost in objective (line 1841-1844), so this is ruled out

### Hypothesis 5: Production Cost Misrepresented

**Issue:** Maybe production cost is multiplied by wrong coefficient?

**Evidence:** LP file shows "+1.3 x2" which suggests $1.30/unit, correct

## Most Likely Root Cause

Given your statement "it may be how you've represented them in the model", I suspect:

**The demand_consumed variable is not properly constrained by available inventory.**

Currently, the material balance is:
```
inventory[t] = prev_inv + production + inflows - outflows - demand_consumed
```

With:
```
inventory[t] >= 0
```

This should prevent `demand_consumed > available`, but maybe there's a numerical issue or the constraint isn't tight enough.

## Next Steps

1. Check if demand_consumed values in solution are reasonable
2. Check if inventory ever goes negative (constraint violation)
3. Add explicit constraint: `demand_consumed[node,prod,t] <= inventory[node,prod,state,t]`

The third option would make the constraint explicit rather than implicit via material balance.
