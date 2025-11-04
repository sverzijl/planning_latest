# Sliding Window Bug - Root Cause Analysis

**Date:** 2025-11-03
**Finding:** CRITICAL BUG in sliding window constraint formulation

---

## Incremental Test Results

| Level | Description | Result | Production | Shortage |
|-------|-------------|--------|------------|----------|
| 1 | Basic production-demand | ✅ PASS | 450 units | 0 units |
| 2 | + Material balance | ✅ PASS | 450 units | 0 units |
| 3 | + Initial inventory (100 units) | ✅ PASS | 350 units | 0 units |
| 4 | + Sliding window (3-day shelf life) | ❌ **INFEASIBLE** | - | - |

**Bug Isolated:** Sliding window constraints make the model infeasible!

---

## The Bug: Sliding Window Constraint Is Wrong

### Current (Broken) Formulation

```python
# In sliding_window_model.py (line ~820):
def sliding_window_rule(model, node_id, prod, t):
    # Window: last L days
    window_dates = [dates from t-(L-1) to t]

    # Inflows
    Q = init_inv (if window includes Day 1) + sum(production in window)

    # Outflows
    O = sum(shipments in window)

    # Constraint
    return inventory[t] <= Q - O  # ← WRONG!
```

###  Why It's Wrong

The constraint says:
```
inventory[t] <= (inflows in window) - (outflows in window)
```

**Problem:** This treats inventory as if it's ONLY the net change in the window, ignoring inventory carried over from before the window!

**Example (3-day window, Day 4):**
```
Window: [Day 2, Day 3, Day 4]
Q = production[Day2] + production[Day3] + production[Day4]  (no init_inv, window excludes Day 1)
O = shipment[Day2] + shipment[Day3] + shipment[Day4]

Constraint: inventory[Day4] <= Q - O
```

But inventory[Day4] ALSO includes:
- Inventory carried from Day 1 (from init_inv)!
- The constraint doesn't account for this!

**Result:** INFEASIBLE because inventory[Day4] > (Q - O) due to carryover.

---

## Correct Formulation

The sliding window should constrain **FRESH inventory only**, not total inventory.

### Option 1: Cumulative Inflows/Outflows

```python
# Cumulative inflows from start
Q_cumulative = init_inv + sum(production[Day1:Day_t])

# Cumulative outflows from start
O_cumulative = sum(shipments[Day1:Day_t])

# Constraint
inventory[t] <= Q_cumulative - O_cumulative
```

But this is just the material balance! It doesn't enforce shelf life.

### Option 2: Age Cohort Tracking

Track inventory by age explicitly (this is what UnifiedNodeModel does).

**Problem:** This is what we're trying to avoid (too slow).

### Option 3: Correct Sliding Window (What Literature Uses)

The standard sliding window formulation is:

```python
# For shelf life L, on day t:
# Sum of shipments in [t-L+1, ..., t] <= Sum of production in [t-L+1, ..., t] + init_inv (if day 1 in window)
```

**But this doesn't directly constrain inventory[t]!**

Instead, it constrains **outflows** to not exceed **inflows** in the window, which indirectly prevents old inventory from being used.

The key insight: **We don't need inventory[t] in the constraint at all!**

---

## The Real Issue

Looking at the actual sliding_window_model.py code (line 839):

```python
return model.inventory[node_id, prod, 'ambient', t] <= Q_ambient - O_ambient
```

This says `inventory[t] <= inflows_in_window - outflows_in_window`.

**This is WRONG because:**
- Inventory[t] = CUMULATIVE (all inventory at location on day t)
- Q - O = NET CHANGE in the window only

These are not comparable!

---

## Correct Sliding Window Constraint

The standard formulation from perishables literature is:

```
Outflows in window ≤ Inflows in window
```

NOT:
```
Inventory[t] ≤ Inflows - Outflows
```

### Correct Implementation

```python
def sliding_window_rule(model, t):
    """
    Outflows in L-day window cannot exceed inflows in same window.

    This ensures products older than L days are not used (implicitly expired).
    """
    window_dates = [dates in last L days including t]

    # Inflows
    Q = init_inv (if Day 1 in window) + sum(production[tau] for tau in window)

    # Outflows
    O = sum(shipment[tau] for tau in window)

    # Constraint: Can't ship more than available in window
    return O <= Q  # ← CORRECT!
```

**Key difference:** No `inventory[t]` in the constraint!

---

## Why Original Was Infeasible

With current wrong formulation:

**Day 4 (window = [Day 2, 3, 4], excludes Day 1):**
```
inventory[Day4] <= Q - O
where:
  Q = production[Day2] + production[Day3] + production[Day4]  (no init_inv)
  O = shipment[Day2] + shipment[Day3] + shipment[Day4]

But inventory[Day4] includes carryover from Day 1!

If we produced nothing on Days 2-4 (Q=0) and shipped 80×3=240 (O=240):
  inventory[Day4] <= 0 - 240 = -240  ← NEGATIVE! INFEASIBLE!

But material balance says:
  inventory[Day4] = init_inv=100 - shipments[Day1-4]=320 = -220

Both negative! The model is trying to use init_inv but sliding window blocks it.
```

---

## The Fix

**Remove `inventory[t]` from the sliding window constraint:**

```python
# OLD (WRONG):
return model.inventory[t] <= Q - O

# NEW (CORRECT):
return O <= Q
```

This allows the material balance to handle inventory levels, while the sliding window only enforces "can't use products older than L days".

---

## Impact on Zero Production

With the WRONG formulation:
- Sliding window is too restrictive
- Makes model infeasible
- Solver might return a solution that violates some constraints
- Or takes shortcuts (massive shortages) to avoid infeasibility

With the CORRECT formulation:
- Sliding window properly enforces shelf life
- Material balance handles inventory
- Model should produce optimally

---

## Next Steps

1. Fix sliding_window_model.py (lines ~839, ~925, ~990)
2. Change `inventory[t] <= Q - O` to `O <= Q`
3. Re-run Level 4 test (should pass)
4. Re-run full model test (should produce > 0)

**File to fix:** `src/optimization/sliding_window_model.py`
**Lines:** 839 (ambient), 925 (frozen), 990 (thawed)
