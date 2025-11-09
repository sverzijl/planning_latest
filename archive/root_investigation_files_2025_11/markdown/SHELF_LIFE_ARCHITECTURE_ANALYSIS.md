# Shelf Life Architecture - First Principles Analysis

## The Fundamental Problem

**User Expectation:** Zero inventory on last day (waste penalty should drive this)

**Reality:** 17,520 units remain, with 11,820 units EXPIRED (>17 days old)

**This reveals:** Shelf life constraints are not working.

---

## Current Constraint Formulation (WRONG)

```python
def ambient_shelf_life_rule(model, node_id, prod, t):
    # Window: last 17 days [t-16, t]
    Q_ambient = sum(inflows in window)  # Production + thaw + arrivals
    O_ambient = sum(outflows in window)  # Shipments + freeze
    # MISSING: + demand_consumed

    return O_ambient <= Q_ambient  # ← WRONG!
```

### Why This Is Wrong

**This constraint says:** "Outflows ≤ Inflows" (material conservation)

**This does NOT say:** "Inventory older than 17 days cannot exist"

**Example Bug:**
- Day 0: Produce 1000 units
- Days 0-16: Consume 500 units
- Day 17: Check constraint for window [0, 17]
  - Q = 1000 (production)
  - O = 500 (consumption)
  - Constraint: 500 ≤ 1000 ✓ PASSES
  - But inventory = 500 units FROM DAY 0 still exists!
- Day 27: Window [10, 27] doesn't see day 0 production
  - Day 0 inventory is "invisible" to this constraint
  - Can persist indefinitely!

---

## Correct Formulation (SHOULD BE)

```python
def ambient_shelf_life_rule(model, node_id, prod, t):
    # Inventory on date t can ONLY come from inflows in last 17 days
    # Anything from before t-16 must have left the system

    Q_ambient = sum(inflows in [t-16, t])
    O_ambient = sum(outflows in [t-16, t])

    # DIRECT constraint on inventory variable
    return model.inventory[node_id, prod, 'ambient', t] <= Q_ambient - O_ambient
```

### Why This Works

**This directly limits inventory based on the window:**
- Inventory[t] ≤ Net inflows in last 17 days
- If production was on day 0, by day 17 it's outside window
- Q won't include day 0 production
- Inventory must be ≤ Q - O (which excludes old production)
- Forces inventory from day 0 to be 0 by day 17!

---

## Why My Previous Fix Failed

I added `demand_consumed` to outflows:
```python
O_ambient += model.demand_consumed[...]
```

But kept the WRONG constraint form:
```python
return O_ambient <= Q_ambient  # Still wrong!
```

This made outflows LARGER, making the constraint say "you consumed a lot" but still didn't LINK to the inventory variable!

Result: Tighter outflow constraint without inventory linkage → infeasible/worse solution

---

## The Correct Fix (Two Parts)

### Part 1: Include Demand in Outflows
```python
O_ambient += model.demand_consumed[node_id, prod, tau]
```

### Part 2: Link Inventory to Window (CRITICAL)
```python
# Change from:
return O_ambient <= Q_ambient

# To:
return model.inventory[node_id, prod, 'ambient', t] <= Q_ambient - O_ambient
```

---

## Why Unified Model Didn't Have This Bug

**Unified Model:** Explicit age tracking
- inventory_cohort[(node, prod, prod_date, curr_date, state)]
- Age = curr_date - prod_date
- If age > 17: Variable doesn't exist!
- IMPOSSIBLE to have expired inventory

**Sliding Window Model:** Implicit age via constraints
- inventory[(node, prod, state, date)] ← No age dimension!
- Relies on constraint to prevent old inventory
- Current constraint is WRONG → expired inventory possible

---

## The Architectural Lesson

**Aggregate models trade granularity for speed:**
- Lose explicit age tracking
- Gain 60× faster solves
- But MUST have correct constraints to enforce implicit properties

**When aggregation loses information, constraints must compensate.**

Current bug: Constraint doesn't compensate for lost age dimension.

---

## The Fix

Change BOTH:
1. Include demand in outflows (so consumption counts)
2. Link inventory variable to window (so old inventory is constrained)

```python
def ambient_shelf_life_rule(model, node_id, prod, t):
    window_start = max(0, list(model.dates).index(t) - 16)
    window_dates = list(model.dates)[window_start:list(model.dates).index(t)+1]

    # Inflows to ambient in window
    Q_ambient = sum(production + thaw + arrivals in window_dates)

    # Outflows from ambient in window
    O_ambient = sum(shipments + freeze + DEMAND_CONSUMED in window_dates)

    # CRITICAL: Directly constrain inventory variable
    return model.inventory[node_id, prod, 'ambient', t] <= Q_ambient - O_ambient
```

This makes expired inventory **structurally impossible**.

---

## Testing Plan

1. Apply both parts of fix
2. Solve and check: production outside 17-day window
3. Should be ZERO (or model infeasible if demand can't be met)
4. If infeasible: Shortage variables will absorb unmet demand
5. End result: No expired inventory, potentially more shortage

Expected outcome: Zero inventory older than 17 days.
