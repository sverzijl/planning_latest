# Changeover Overhead Time - MIP Optimization

## Performance Issue

**Symptom:** 4-week solve time increased from 23.5s to 41.5s (+76%) after adding changeover overhead

**Root Cause:** Inefficient MIP formulation with inline sums of binary variables

## Problem Analysis

### Current Implementation (Lines 1729-1754)

```python
# Count product starts (sum of N binaries)
num_starts = sum(
    model.product_start[node_id, prod, t]
    for prod in model.products
)

# Count if producing (sum of N binaries)
producing = sum(
    model.product_produced[node_id, prod, t]
    for prod in model.products
)

# Complex expression with 2N binary variables
overhead_time = (startup + shutdown) * producing + changeover * (num_starts - producing)
```

**Issues:**
1. **2N binary variables per constraint** (N = 5 products → 10 binaries)
2. **Inline sums in constraints** (Pyomo must expand at constraint build time)
3. **Redundant computation** (`producing` and `num_starts` are correlated)
4. **Complex expression** makes LP relaxation weaker

### Why This Is Slow

From MIP Modeling Expert skill:

- Each binary variable in a constraint **doubles the potential branch-and-bound nodes**
- Inline sums create **implicit products** of binaries with continuous variables
- Complex constraints have **weaker LP relaxations** (more B&B iterations needed)

**Impact:**
- 4-week: 29 dates × 2N binaries = 290 complex constraints
- Each constraint has 10 binary variables
- Total: ~2,900 binary variable occurrences in overhead constraints

## Optimized Solution

### Strategy 1: Pre-Aggregate Binary Sums ⭐ RECOMMENDED

Create auxiliary variables for the sums, computed once per (node, date):

```python
# NEW VARIABLES (add to _add_variables)
model.total_starts = Var(
    [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
    within=NonNegativeIntegers,
    bounds=(0, len(model.products)),  # At most N products can start
    doc="Total number of product starts on this date"
)

model.any_production = Var(
    [(node.id, t) for node in self.manufacturing_nodes for t in model.dates],
    within=Binary,
    doc="1 if any production occurs on this date"
)

# NEW CONSTRAINTS (add to _add_changeover_detection or new method)
def total_starts_rule(model, node_id, t):
    """Link total_starts to sum of product_start binaries."""
    return model.total_starts[node_id, t] == sum(
        model.product_start[node_id, prod, t]
        for prod in model.products
        if (node_id, prod, t) in model.product_start
    )

def any_production_upper_rule(model, node_id, t):
    """If any product is produced, any_production = 1."""
    return model.any_production[node_id, t] >= sum(
        model.product_produced[node_id, prod, t]
        for prod in model.products
        if (node_id, prod, t) in model.product_produced
    ) / len(model.products)

def any_production_lower_rule(model, node_id, t):
    """If any_production = 0, no products produced."""
    # This ensures: any_production = 0 → all product_produced = 0
    for prod in model.products:
        if (node_id, prod, t) in model.product_produced:
            model.product_binary_linking_con[node_id, prod, t].set_value(
                model.production[node_id, prod, t] <=
                model.any_production[node_id, t] * max_production
            )

# SIMPLIFIED OVERHEAD CALCULATION (in production_time_link_rule)
overhead_time = (
    (startup_hours + shutdown_hours) * model.any_production[node_id, t] +
    changeover_hours * (model.total_starts[node_id, t] - model.any_production[node_id, t])
)
```

**Benefits:**
- **From 2N binaries to 1 binary + 1 integer** per constraint
- **Simpler constraint structure** → stronger LP relaxation
- **Pre-computed sums** → faster constraint evaluation

**Trade-off:**
- Adds 29 binary variables + 29 integer variables (for 4-week)
- But simplifies 29 constraints that each had 10 binaries
- Net effect: Fewer complex expressions, likely faster

---

### Strategy 2: Simplified Overhead Formula ⭐ SIMPLEST FIX

Use a simpler approximation that avoids the complex formula:

```python
# SIMPLIFIED: Assume changeover time is negligible compared to startup/shutdown
# Or: Count changeovers directly from production patterns

# Option A: Startup/shutdown only (ignore changeover)
overhead_time = (startup_hours + shutdown_hours) * model.any_production[node_id, t]

# Option B: Use total_starts directly (approximation)
overhead_time = startup_hours * model.any_production[node_id, t] + \
                changeover_hours * model.total_starts[node_id, t]
```

**Note:** This is mathematically different from the correct formula but may be "good enough" for practical purposes.

**Correct formula:** `startup + shutdown + (N-1) × changeover`
**Approximation:** `startup + N × changeover`

Difference is `(shutdown + changeover)` per day, typically ~0.75h vs actual overhead.

---

### Strategy 3: Use SOS1 for Exclusive Products (If Applicable)

**Only applicable if:** Each day produces exactly ONE product (not your case)

If you had mutual exclusivity, mark `product_produced` as SOS1:

```python
model.product_produced_sos = SOSConstraint(
    var=model.product_produced,
    sos=1  # At most one nonzero
)
```

This enables specialized branching, but **doesn't apply** to your multi-product scenario.

---

### Strategy 4: Remove Overhead Entirely for Long Horizons

For horizons > 8 weeks, overhead time may be negligible:

```python
# In _add_production_constraints
horizon_days = (self.end_date - self.start_date).days

if horizon_days > 56:  # > 8 weeks
    print("    Skipping overhead time for long horizon (tractability)")
    overhead_time = 0
else:
    # Use Strategy 1 or 2
    overhead_time = ...
```

**Rationale:** For strategic planning (12 weeks), exact overhead is less critical than capacity trends.

---

## Recommended Implementation

**For 4-8 week horizons:** Use **Strategy 1** (pre-aggregate binary sums)

**For 8+ week horizons:** Use **Strategy 2** or **Strategy 4** (simplify or disable)

---

## Implementation Code

### Add Pre-Aggregated Variables

```python
# In _add_variables method, after product_start definition:

# Aggregate changeover variables (for efficient overhead calculation)
changeover_index = [(node.id, t) for node in self.manufacturing_nodes for t in model.dates]

model.total_starts = Var(
    changeover_index,
    within=NonNegativeIntegers,
    bounds=(0, len(model.products)),
    doc="Total product starts on date (sum of product_start)"
)

model.any_production = Var(
    changeover_index,
    within=Binary,
    doc="1 if any production on date"
)

print(f"  Changeover aggregation variables: {len(changeover_index) * 2}")
```

### Add Linking Constraints

```python
# In _add_changeover_detection method, after start_detection_con:

def total_starts_link_rule(model, node_id, t):
    """Sum of product starts equals total_starts variable."""
    return model.total_starts[node_id, t] == sum(
        model.product_start[node_id, prod, t]
        for prod in model.products
        if (node_id, prod, t) in model.product_start
    )

model.total_starts_link_con = Constraint(
    changeover_index,
    rule=total_starts_link_rule,
    doc="Link total_starts to sum of product_start"
)

def any_production_link_rule(model, node_id, t):
    """If ANY product is produced, any_production = 1."""
    # Using Big-M approach
    num_products = len(model.products)
    return model.any_production[node_id, t] * num_products >= sum(
        model.product_produced[node_id, prod, t]
        for prod in model.products
        if (node_id, prod, t) in model.product_produced
    )

model.any_production_link_con = Constraint(
    changeover_index,
    rule=any_production_link_rule,
    doc="Link any_production to existence of product_produced"
)

print(f"    Changeover aggregation linking constraints added")
```

### Simplified Overhead Calculation

```python
# In production_time_link_rule (line 1720-1754), REPLACE with:

# Calculate overhead time (startup + shutdown + changeover)
overhead_time = 0
if hasattr(model, 'total_starts') and (node_id, t) in model.total_starts:
    # Get overhead parameters
    startup_hours = node.capabilities.daily_startup_hours or 0.5
    shutdown_hours = node.capabilities.daily_shutdown_hours or 0.25
    changeover_hours = node.capabilities.default_changeover_hours or 0.5

    # OPTIMIZED: Use pre-computed aggregates
    # Overhead = (startup + shutdown) * any_production +
    #            changeover * (total_starts - any_production)
    overhead_time = (
        (startup_hours + shutdown_hours) * model.any_production[node_id, t] +
        changeover_hours * (model.total_starts[node_id, t] - model.any_production[node_id, t])
    )
```

---

## Expected Performance Improvement

**Before optimization:**
- Constraint complexity: 2N binary variables per constraint
- 4-week solve: 41.5s

**After optimization:**
- Constraint complexity: 1 binary + 1 integer per constraint
- Additional: 2N linking constraints (but simpler structure)
- **Expected 4-week solve: 30-35s** (15-25% faster)
- **Expected 12-week solve: May now be feasible** (was OOM)

---

## Alternative: Disable Overhead for Validation

To test if overhead is causing the slowdown:

```python
# Quick test: Set overhead to 0
overhead_time = 0  # TEMPORARY: Disable overhead
```

If solve time returns to 23.5s, confirms overhead is the bottleneck.

---

## Summary

**Root cause:** Inline sums of binary variables create complex constraints

**Best fix:** Pre-aggregate binary sums into auxiliary variables (Strategy 1)

**Quick fix:** Simplify overhead formula (Strategy 2)

**Long horizons:** Disable overhead entirely (Strategy 4)

**Expected impact:** 15-30% solve time reduction

---

## Sign-off

**Created by:** Claude Code (AI Assistant)
**Date:** November 4, 2025
**Skills Used:** MIP Modeling Expert + Pyomo Expert
**Status:** Ready for implementation
