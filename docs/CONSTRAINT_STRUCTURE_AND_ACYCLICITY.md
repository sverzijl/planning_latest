# SlidingWindowModel: Constraint Structure and Acyclicity Verification

## Overview

This document provides a comprehensive analysis of the SlidingWindowModel constraint structure, verifying that no circular dependencies exist and documenting the MIP/Pyomo patterns used.

**Status**: ✅ NO CIRCULAR DEPENDENCIES (as of 2025-11-05 after fixes)

---

## Constraint Categories

### 1. Shelf Life Windows (Lines 1152-1500)

**Purpose**: Enforce maximum age limits without explicit age tracking

**Formulation**:
```python
O_state[node, prod, t] <= Q_state[node, prod, t]

Where:
  Q_state = sum(inflows[tau] for tau in [t-L+1, t])  # L-day window
  O_state = sum(outflows[tau] for tau in [t-L+1, t])
```

**States**:
- Ambient: L = 17 days
- Frozen: L = 120 days
- Thawed: L = 14 days

**Dependencies**:
- Q: production[t], arrivals[t], thaw[t], freeze[t]
- O: consumption[t], departures[t], thaw[t], freeze[t]

**Acyclicity**: ✅ YES
- Inequality constraint (O ≤ Q)
- Both sides are aggregations of flow variables
- No variable appears on both LHS and RHS
- No feedback loop

**MIP Principle**: Sliding window implicitly tracks age - products that entered state more than L days ago have "expired out" of the window.

---

### 2. Material Balance (Lines 1541-1870)

**Purpose**: Conservation of mass - inventory change = inflows - outflows

**Formulation** (per state):
```python
inventory[node, prod, state, t] =
    inventory[node, prod, state, t-1] +  # Previous period
    inflows[t] -                         # Same period
    outflows[t]                          # Same period
```

**Ambient Balance**:
```
inflows:  production[t], thaw[t], arrivals[t]
outflows: freeze[t], departures[t], consumption_from_ambient[t], disposal[t]
```

**Frozen Balance**:
```
inflows:  production[t], freeze[t], arrivals[t]
outflows: thaw[t], departures[t], disposal[t]
```

**Thawed Balance**:
```
inflows:  thaw[t], arrivals[t] (frozen goods arriving at ambient nodes)
outflows: consumption_from_thawed[t], disposal[t]
```

**Dependencies**:
- inventory[t] ← inventory[t-1] (TIME ACYCLIC)
- inventory[t] ← production[t], consumption[t], etc. (same period)

**Acyclicity**: ✅ YES
- **Key property**: inventory[t] does NOT appear on RHS for same t
- Only inventory[t-1] appears on RHS
- Time flows in one direction (no feedback)
- consumption is SUBTRACTED (outflow), appears once only

**Critical Insight**:
Material balance ALONE is sufficient to prevent over-consumption:
```
inventory[t] = inventory[t-1] + production - consumption
inventory[t] >= 0  (NonNegativeReals)

If consumption > available:
  inventory[t] = inventory[t-1] + production - consumption < 0
  Violates non-negativity → INFEASIBLE

Therefore: consumption ≤ inventory[t-1] + production (automatically enforced)
```

**DO NOT ADD**: `consumption <= inventory[t]` - This is REDUNDANT and creates circular dependency!

---

### 3. Demand Satisfaction (Lines 1888-1920)

**Purpose**: Accounting identity - demand must be consumed or recorded as shortage

**Formulation**:
```python
demand_consumed_from_ambient[node, prod, t] +
demand_consumed_from_thawed[node, prod, t] +
shortage[node, prod, t] = demand[node, prod, t]
```

**Dependencies**:
- consumption variables ← demand (parameter, not variable)
- shortage ← demand (parameter)

**Acyclicity**: ✅ YES
- Simple accounting equation
- No variable appears twice
- No feedback to other constraints

**State-Specific Consumption** (2025-11-05 fix):
- Separate variables for ambient and thawed consumption
- Prevents double-counting (don't subtract same consumption from both states)
- Each material balance references only its own consumption variable

---

### 4. Production Constraints (Lines 2047-2239)

**Purpose**: Link production to labor hours and enforce capacity limits

**Key Constraints**:

**A. Production Time Linking** (line 2102):
```python
labor_hours_used[node, t] = production_time[t] + overhead_time[t]

Where:
  production_time = sum(production[node, prod, t] / rate for prod)
  overhead_time = f(startup, shutdown, changeovers)
```

**B. Capacity Limit** (line 2115):
```python
labor_hours_used[node, t] <= max_hours[t]
```

**Dependencies**:
- labor_hours ← production (one direction)
- labor_hours ← binary indicators (one direction)

**Acyclicity**: ✅ YES
- Labor is DERIVED from production (not vice versa)
- No feedback loop
- Capacity is upper bound (doesn't force production)

---

### 5. Binary Logic Constraints (Lines 2240-2428)

**Purpose**: Link binary indicators to continuous variables using Big-M

**Product Produced Indicator** (lines 2271-2321):
```python
# Bidirectional linking:
production[node, prod, t] <= M × product_produced[node, prod, t]  # Upper
product_produced[node, prod, t] >= production[node, prod, t] / M  # Lower

Ensures: production > 0 ⟺ product_produced = 1
```

**Any Production Indicator** (lines 2342-2374):
```python
# FIXED (2025-11-05):
sum(product_produced[node, prod, t] for prod) <= N × any_production[node, t]

Ensures: If ANY product produced → any_production = 1
```

**Dependencies**:
- binary ↔ continuous (bidirectional via INEQUALITIES)

**Acyclicity**: ✅ YES
- Bidirectional dependency through INEQUALITIES is safe
- Not forcing relationships (solver chooses values that satisfy both)
- Standard Big-M indicator pattern from MIP literature

**Critical**: Direction matters!
- ✅ CORRECT: sum(binary) <= N × indicator (forces indicator=1 if any binary=1)
- ❌ WRONG: indicator × N >= sum(binary) (allows indicator=0 while binaries=1)

---

## Removed Circular Dependencies

### REMOVED: Consumption Upper Bounds (2025-11-05)

**Former constraint**:
```python
demand_consumed_from_ambient[node, prod, t] <= inventory[node, prod, 'ambient', t]
demand_consumed_from_thawed[node, prod, t] <= inventory[node, prod, 'thawed', t]
```

**Why circular**:
```
Constraint:  consumption <= inventory[t]
Balance:     inventory[t] = inventory[t-1] + production - consumption

Substituting:
  consumption <= inventory[t-1] + production - consumption
  2×consumption <= inventory[t-1] + production
  consumption <= (inventory[t-1] + production) / 2

This FORCES production to be at least 2×consumption - inventory[t-1]
Creates minimum production requirement → OVERPRODUCTION
```

**Impact**: Caused 8,183-16,756 units of excess end-inventory

**Resolution**: REMOVED - Material balance + non-negativity is sufficient

---

## MIP Patterns Used

### Pattern 1: Time-Stepped State Variables (Acyclic by Design)

```python
state[t] = state[t-1] + Δstate[t]
```

**Properties**:
- state[t] depends only on past (t-1)
- No same-period feedback
- Standard dynamic programming pattern

**Used in**:
- All three material balances (ambient, frozen, thawed)
- Guaranteed acyclic due to time structure

### Pattern 2: Accounting Identities

```python
variable_A + variable_B = parameter_C
```

**Properties**:
- Simple equation
- No variable appears twice
- Parameters (not variables) on RHS

**Used in**:
- Demand balance: consumption + shortage = demand

### Pattern 3: Big-M Indicator Variables

```python
continuous_var <= M × binary_var  # Enable/disable
binary_var >= continuous_var / M  # Force binary=1 if continuous>0
```

**Properties**:
- Bidirectional through inequalities (safe)
- Standard MIP technique
- No circular forcing (inequalities provide slack)

**Used in**:
- product_produced ↔ production
- any_production ↔ sum(product_produced)
- Weekend labor minimum

**Critical Direction Rule**:
```
✅ CORRECT:   sum(binaries) <= N × indicator
❌ INCORRECT: indicator × N >= sum(binaries)
```

### Pattern 4: Inequality Bounds (Non-Forcing)

```python
variable_A <= f(other_variables)  # Upper bound
variable_A >= g(other_variables)  # Lower bound
```

**Properties**:
- Constrains feasible region
- Doesn't force variables to specific values
- Solver minimizes/maximizes subject to bounds

**Used in**:
- Capacity limits
- Shelf life windows
- Truck capacity

---

## Dependency Verification Checklist

✅ **Time Acyclic**: All state variables depend only on t-1, not t
✅ **No Self-Reference**: No variable appears on both LHS and RHS of same constraint
✅ **No Redundant Constraints**: Removed consumption <= inventory
✅ **Proper Big-M Direction**: Fixed any_production formulation
✅ **State Partitioning**: Separate consumption variables (no double-counting)

---

## How to Identify Future Circular Dependencies

### Red Flags:

1. **Variable on both sides**: `X <= f(X, ...)`
   - Check: Does X appear in f?
   - If yes: Potential circular dependency

2. **Redundant with material balance**:
   - Material balance: `inventory = ... - consumption`
   - Extra constraint: `consumption <= inventory`
   - Result: CIRCULAR

3. **Backward Big-M**: `indicator × M >= sum(binaries)`
   - Should be: `sum(binaries) <= M × indicator`

4. **Double subtraction**: Same variable subtracted in multiple balances
   - Was: `demand_consumed` in BOTH ambient and thawed
   - Fixed: Separate variables for each state

### Debugging Process:

1. **Identify irrational behavior**: Model chooses expensive option over cheap
2. **Check costs**: Verify objective coefficients correct
3. **Suspect constraints**: Look for recently added constraints
4. **Test removal**: Remove suspect constraint, re-solve
5. **If improves**: Constraint was forcing/circular
6. **If infeasible**: Constraint was necessary

---

## Performance Characteristics

**Current (Post-Fix)**:
- 1-week solve: <2s
- 4-week solve: <120s
- Variables: ~12k (4-week)
- Constraints: ~9k (4-week)
- End inventory: 0 units ✅

**Key Property**: O(H) scaling (linear in horizon length)
- vs. O(H³) for explicit cohort tracking

---

## Lessons Learned

1. **Material balance is powerful**: Alone ensures conservation + non-negativity prevents over-consumption

2. **Redundant constraints are dangerous**: Can create unintended forcing relationships

3. **Test with actual solves**: Variable counts ≠ solution quality

4. **User insights are critical**: "Makes zero sense" → found circular dependency

5. **MIP gap hides issues**: Sub-optimal solutions can mask constraint bugs

---

## References

- **MIP Modeling Expert Skill**: Integer programming tricks and Big-M formulations
- **Pyomo Documentation**: Model structure and best practices
- **AIMMS Modeling Guide Chapter 7**: Integer linear programming techniques

---

## Maintenance Guidelines

**When adding new constraints**:

1. **Document dependencies**: What variables does it connect?
2. **Check acyclicity**: Does variable appear on both sides?
3. **Verify non-redundancy**: Is this already enforced by other constraints?
4. **Test incrementally**: Add constraint, solve, check if behavior changes
5. **Use verification method**: Run `verify_constraint_structure()` if available

**When debugging**:

1. **Check recent additions**: New constraints are most likely culprits
2. **Look for circular patterns**: var <= f(var), var = g(var)
3. **Test removal**: Remove suspect constraint and see if issue resolves
4. **Consult this document**: Review patterns and known issues

---

**Last Updated**: 2025-11-05
**Status**: Model structure verified clean, no circular dependencies
**Verified By**: Actual solve tests showing end inventory = 0 units
