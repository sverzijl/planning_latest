# Changeover Formulations: Counting vs Start Tracking

**Date:** October 2025
**Status:** Start tracking is now the default formulation

---

## Overview

Changeover tracking in production scheduling captures the time and cost associated with switching between products. Two formulations were evaluated:

1. **Counting constraint (OLD):** Counts simultaneous products
2. **Start tracking (NEW, RECOMMENDED):** Tracks product startups (0→1 transitions)

---

## Counting Constraint Formulation (Deprecated)

### Variables

```python
product_produced[i,t] ∈ {0,1}      # Is product i running on day t?
num_products_produced[t] ∈ {0..5}  # How many products on day t?
```

### Constraints

```python
# Counting equality constraint
num_products_produced[t] = sum(product_produced[i,t] for i in products)
```

### Overhead Calculation

```python
overhead_time = (startup + shutdown - changeover) * production_day +
                changeover * num_products_produced[t]
```

### Issues

1. **Equality constraint:** Strong coupling between all product binaries
2. **Integer variable:** 28 integer variables (one per day)
3. **Activation requirement:** Must deactivate when using pattern constraints
4. **Performance impact:** 15× slower when active alongside pattern constraints

**Performance:**
- Pattern (counting deactivated): $779K in 8s
- Pattern (counting active): $1,957K in 124s

### When It Made Sense

This formulation accurately models overhead when products run simultaneously:
- Overhead = startup + shutdown + (N-1) changeovers
- Where N = number of products running that day

But it introduced unnecessary complexity and poor performance.

---

## Start Tracking Formulation (Current)

### Variables

```python
product_produced[i,t] ∈ {0,1}  # Is product i running on day t?
product_start[i,t] ∈ {0,1}     # Does product i START on day t?
```

### Constraints

```python
# Start detection (inequality)
product_start[i,t] ≥ product_produced[i,t] - product_produced[i,t-1]
```

### Logic

| Transition | product_produced[t-1] | product_produced[t] | start ≥ | start = |
|------------|----------------------|-------------------|---------|---------|
| Start (0→1) | 0 | 1 | 1 | 1 ✓ (changeover!) |
| Continue (1→1) | 1 | 1 | 0 | 0 ✓ (no changeover) |
| Stop (1→0) | 1 | 0 | -1 | 0 ✓ (no changeover) |
| Off (0→0) | 0 | 0 | 0 | 0 ✓ (no changeover) |

**Only 0→1 transitions create a start!**

### Overhead Calculation

```python
num_starts = sum(product_start[i,t] for i in products)
overhead_time = (startup + shutdown) * production_day + changeover * num_starts
```

### Benefits

1. ✅ **Inequality constraints:** Weak coupling, solver has more freedom
2. ✅ **Binary only:** No integer variables, better for MIP solvers
3. ✅ **Always active:** No activation/deactivation needed
4. ✅ **Direct semantics:** Tracks actual changeovers (what we care about)
5. ✅ **Better performance:** 2% better cost, 19% faster

**Performance:**
- Pattern with start tracking: $764K in 6.5s
- Flexible with start tracking: $764K in 6.5s

---

## Mathematical Formulation Details

### Full Model with Start Tracking

**Decision Variables:**
```
x[i,t]           # Production quantity of product i on day t (continuous)
b[i,t] ∈ {0,1}   # Binary: Is product i running on day t?
y[i,t] ∈ {0,1}   # Binary: Does product i START on day t?
```

**Changeover Detection:**
```
y[i,t] ≥ b[i,t] - b[i,t-1]    ∀ i,t (with b[i,0] = 0)
```

**Production Linking (BigM):**
```
x[i,t] ≤ max_production[i,t] * b[i,t]
x[i,t] ≥ 0
```

**Capacity Constraint:**
```
sum_i(x[i,t] / production_rate) +
  (startup + shutdown) * any_production[t] +
  changeover * sum_i(y[i,t])
≤ available_hours[t]
```

**Objective (includes changeover cost):**
```
minimize: labor_cost + production_cost + transport_cost + holding_cost +
          changeover_cost_per_start * sum_{i,t}(y[i,t])
```

---

## Performance Comparison

| Metric | Counting Constraint | Start Tracking | Improvement |
|--------|---------------------|----------------|-------------|
| **Pattern Cost** | $779,471 | $763,813 | -$15,658 (-2.0%) |
| **Pattern Time** | 8.0s | 6.5s | -1.5s (-18.8%) |
| **Flexible Cost** | Unknown | $763,828 | - |
| **Flexible Time** | Unknown | 9.3s | - |
| **Binary Variables** | 504 + 25 pattern | 644 + 140 starts | +140 more but performs better |
| **Integer Variables** | 2,058 + 28 counting | 2,058 | -28 (-1.3%) |
| **Warmstart Works?** | ❌ NO | ✅ YES | Fixed! |

---

## Implementation Guide

### Pyomo Code Pattern

```python
import pyomo.environ as pyo

# Create model
model = pyo.ConcreteModel()

# Existing variables
model.product_produced = pyo.Var(products_dates, within=pyo.Binary)

# NEW: Add start tracking variables
model.product_start = pyo.Var(
    products_dates,
    within=pyo.Binary,
    doc="1 if product starts (changeover) on this date"
)

# NEW: Start detection constraints
model.start_detection = pyo.ConstraintList()

for product in products:
    prev_date = None
    for date in sorted(dates):
        if prev_date is None:
            # First period - start if producing
            model.start_detection.add(
                model.product_start[product, date] >=
                model.product_produced[product, date]
            )
        else:
            # Detect 0→1 transition
            model.start_detection.add(
                model.product_start[product, date] >=
                model.product_produced[product, date] -
                model.product_produced[product, prev_date]
            )
        prev_date = date

# Use in capacity constraint
changeover_time = changeover_hours * sum(model.product_start[p,t] for p in products)
```

---

## When to Use Each Formulation

### Use Start Tracking (Default)
- ✅ General production scheduling
- ✅ When warmstart may be needed
- ✅ When performance is critical
- ✅ Sequence-independent changeovers

### Use Counting Constraint (Rare)
- If you truly need to count simultaneous products
- Sequence-dependent changeovers with full transition matrix
- Legacy code compatibility

---

## Related Formulations

### Sequence-Dependent Changeovers

If changeover time depends on from→to product pairs:

```python
# Variables
z[i,j,t] ∈ {0,1}  # Changeover from product i to product j on day t

# Constraints
sum_j(z[i,j,t]) = b[i,t-1]  # If i ran yesterday, must transition
sum_i(z[i,j,t]) = b[j,t]    # If j runs today, must transition from something

# Capacity
changeover_time = sum_{i,j,t}(changeover_time[i,j] * z[i,j,t])
```

**Note:** Much more complex (N² binary variables per day). Only use if changeover times truly depend on product sequence.

---

## References

- Warmstart investigation: `docs/lessons_learned/warmstart_investigation_2025_10.md`
- Implementation: `src/optimization/unified_node_model.py:_add_changeover_tracking_constraints()`
- Test validation: `test_start_tracking_formulation.py`
- AIMMS Modeling Guide, Chapter 7: Integer Linear Programming Tricks
