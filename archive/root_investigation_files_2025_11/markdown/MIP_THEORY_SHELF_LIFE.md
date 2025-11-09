# MIP Theory: Shelf Life + Material Balance Interaction

**Using MIP Expert + Pyomo Expert Skills**

---

## The Two Constraint Types

### 1. Material Balance (Equality, Conservation of Flow)

**Purpose:** Track actual inventory levels

**Equation:**
```
I[node, product, state, t] = I[t-1] + inflows[t] - outflows[t]

Where:
  I[t-1] = previous inventory (or init_inv on Day 1)
  inflows[t] = production + arrivals + state_transitions_in
  outflows[t] = shipments + consumption + state_transitions_out
```

**Type:** EQUALITY constraint (must hold exactly)

**Enforces:** Physical conservation - can't create or destroy product

---

### 2. Shelf Life Window (Inequality, Freshness Limit)

**Purpose:** Prevent using old inventory (age > L days)

**Equation:**
```
O[window] ≤ Q[window]

Where:
  window = [t-L+1, t-L+2, ..., t]  (last L days)
  Q = sum of inflows in window
  O = sum of outflows in window
```

**Type:** INEQUALITY constraint (≤)

**Enforces:** Can only ship/consume goods that arrived in last L days

---

## How They Should Interact

### Scenario: 30k Initial Inventory on Day 1

**Material Balance says:**
```
Day 1: I[1] = 30k + prod[1] - consumed[1] - shipped[1]
Day 2: I[2] = I[1] + prod[2] - consumed[2] - shipped[2]
Day 3: I[3] = I[2] + prod[3] - consumed[3] - shipped[3]
```

Init_inv enters ONCE on Day 1, then tracked via I[t-1]

**Shelf Life says:**
```
Day 1 window [Day 1]:
  Q = init_inv + prod[1]
  O = consumed[1] + shipped[1]
  Constraint: O ≤ Q

Day 2 window [Day 1-2]:
  Q = init_inv + prod[1] + prod[2]  ← CURRENT CODE
  O = consumed[1] + consumed[2] + shipped[1] + shipped[2]
  Constraint: O ≤ Q

Day 17 window [Day 1-17]:
  Q = init_inv + sum(prod[1:17])  ← CURRENT CODE
  O = sum(consumed[1:17]) + sum(shipped[1:17])
  Constraint: O ≤ Q
```

**The Problem with Current Code:**

Days 1-17 ALL have init_inv in their Q!

This doesn't violate shelf life constraint (init_inv is < 17 days old on those days).

**BUT** it creates a disconnect with material balance:

- Material balance: Init_inv depletes as it's consumed
- Shelf life: Init_inv appears as "fresh supply" on Days 1-17

If I consume 30k on Day 1:
- Material balance: I[1] = 30k - 30k = 0 ✓
- Day 2 shelf life: Q still includes 30k! ✓ (age < 17)
- Day 2 can consume another 30k from "fresh" supply
- But material balance has I[1] = 0!

**This creates the CONFLICT!**

---

## The Correct Formulation

**MIP Principle:** Shelf life window Q should include ONLY **new inflows** in the window period.

**Correct Q for Days 2-17:**
```
Day 2 window [Day 1-2]:
  Q = prod[1] + prod[2] + arrivals[1] + arrivals[2]
  (NO init_inv - it's not a new inflow, it's carried in I[0])

Day 17 window [Day 1-17]:
  Q = sum(prod[1:17]) + sum(arrivals[1:17])
  (NO init_inv - it's starting inventory, not an inflow during window)
```

**Why this is correct:**

- Init_inv is the starting point (I[0])
- Material balance tracks it via I[t-1]
- Shelf life should limit to NEW production/arrivals in last L days
- NOT re-count the starting inventory every day!

**Day 1 is special:**
```
Day 1 window [Day 1]:
  Q = init_inv + prod[1] + arrivals[1]

  Why include init_inv here?
  Because on Day 1, init_inv IS fresh supply (age 0 on snapshot date)
  It's available for immediate use
```

**Days 2+:**
```
Day 2+ windows:
  Q = prod[window] + arrivals[window]

  Why NOT include init_inv?
  It's already accounted for in I[t-1] from material balance
  Adding to Q would double-count it!
```

---

## The Fix

**Change condition from:**
```python
if window_includes_day1:  # True on Days 1-17
    Q += init_inv
```

**To:**
```python
if t == first_date:  # True ONLY on Day 1
    Q += init_inv
```

**This ensures:**
- Day 1: Init_inv in Q (correct - it's fresh on Day 1)
- Days 2-17: Init_inv NOT in Q (correct - material balance handles it)
- Days 18+: Init_inv NOT in Q (correct - expired)

---

## Testing the Fix

**Prediction:**

With fix:
- Day 1: Can consume up to 30k from init_inv
- Day 2+: Can only consume from production + arrivals in window
- Material balance ensures consumption ≤ available inventory
- No phantom supply

Expected Result:
- Production ≈ 276k (as seen in Nov 5 16:52 solve)
- Fill rate ≈ 91%
- Conservation holds

---

**This is the hypothesis I'll test systematically.**
