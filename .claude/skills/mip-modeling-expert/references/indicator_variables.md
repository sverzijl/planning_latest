# Indicator Variables: Discontinuous Variables and Fixed Costs

## Overview

**Indicator variables** are binary (0-1) variables that indicate whether a certain state or condition holds in an optimization model. They are the fundamental building block for most MIP modeling tricks.

## Concept

An indicator variable `y ∈ {0,1}` links to another variable or constraint to represent mutually exclusive states:

```
y = 0  →  State A (e.g., facility closed, machine off, variable is zero)
y = 1  →  State B (e.g., facility open, machine on, variable is positive)
```

## Technique 1: Discontinuous Variables

### Problem Statement

A variable `x` must be either **exactly zero** OR within bounds **[l, u]**:

```
x = 0   OR   l ≤ x ≤ u
```

Graphically:
```
    ●----------●=============●------>  x
    0          l             u

    Allowed:  x = 0  or  l ≤ x ≤ u
    Forbidden: 0 < x < l
```

This **cannot** be formulated as a linear program because LP can only model simultaneous constraints, not "either-or" situations.

### Applications

1. **Batch Size Restrictions**
   - Supplier requires minimum order quantity
   - Example: "Either order nothing, or order between 100 and 500 units"

2. **Setup Costs**
   - A fixed cost is incurred when production begins
   - If no production, no cost

3. **Equipment Operation**
   - Equipment must run at minimum capacity or not at all
   - Safety or engineering constraints

### Mathematical Formulation

Introduce binary indicator variable `y`:

```
y = { 0  if x = 0
    { 1  if l ≤ x ≤ u
```

**Constraints:**
```
x ≤ uy
x ≥ ly
y ∈ {0,1}
```

**Verification:**

| y | Constraints Imply | Result |
|---|-------------------|--------|
| 0 | x ≤ 0 and x ≥ 0 | x = 0 ✓ |
| 1 | x ≤ u and x ≥ l | l ≤ x ≤ u ✓ |

**Critical:** The upper bound `u` must be a valid upper bound for `x` in your problem. If `u` is too small, you may eliminate feasible solutions.

### Example: Supplier Order Quantity

A supplier requires orders to be either 0 or between 100 and 500 units.

```
Variables:
    x ≥ 0    (order quantity)
    y ∈ {0,1}  (order indicator)

Constraints:
    x ≤ 500y
    x ≥ 100y
```

Solutions:
- `y=0`: Forces `x=0` (no order)
- `y=1`: Allows `100 ≤ x ≤ 500` (valid order)

**Invalid:** `x=50` because this would require `y=0` (from upper bound) but violate `x ≥ 100y=0`.

## Technique 2: Fixed Costs

### Problem Statement

A cost function with a **discontinuous jump** at x=0:

```
C(x) = { 0        if x = 0
       { k + cx   if x > 0
```

Where:
- `k` = fixed cost (setup cost, activation fee, etc.)
- `c` = variable cost per unit

Graphically:
```
C(x)
  ↑
  |         /
  |        /
  |       / slope = c
k |●- - -/
  |     /
  |    /
0 |●  /
  └──────────> x
    0
```

There's a discontinuous jump of size `k` at `x=0`.

### Applications

1. **Manufacturing Setup Costs**
   - Must set up machinery before production
   - Setup cost incurred once, then variable costs per unit

2. **Facility Opening Costs**
   - Fixed cost to open a warehouse
   - Variable costs for operations

3. **Transportation**
   - Fixed cost to dispatch a truck
   - Variable fuel costs per mile

### Mathematical Formulation

Introduce:
- Binary indicator `y`
- Upper bound `u` on `x`

Define modified cost function:
```
C*(x, y) = ky + cx
```

This matches the original cost function except when `x > 0` and `y = 0`. We prevent this case by adding:

```
x ≤ uy
```

**Complete Formulation:**

```
Minimize:  ky + cx

Subject to:
    x ≤ uy
    [other constraints involving x]
    x ≥ 0
    y ∈ {0,1}
```

**Verification:**

| y | x bound | Cost |
|---|---------|------|
| 0 | x ≤ 0 → x=0 | k·0 + c·0 = 0 ✓ |
| 1 | x ≤ u | k·1 + cx = k + cx ✓ |

### Example: Production with Setup Cost

A factory produces widgets. There's a $500 setup cost if any widgets are produced, plus $3 per widget.

```
Parameters:
    k = 500   (setup cost)
    c = 3     (cost per widget)
    u = 1000  (maximum production capacity)

Variables:
    x ≥ 0     (widgets produced)
    y ∈ {0,1}   (production indicator)

Objective:
    Minimize: 500y + 3x

Constraints:
    x ≤ 1000y
    [demand constraints, capacity constraints, etc.]
```

Scenarios:
- **No production:** `y=0`, `x=0`, cost = $0
- **Produce 100 widgets:** `y=1`, `x=100`, cost = $500 + $300 = $800
- **Produce 1000 widgets:** `y=1`, `x=1000`, cost = $500 + $3000 = $3500

## General Form with Multiple Constraints

When the main problem has multiple constraints:

```
Minimize:  ky + cx + Σⱼ cⱼwⱼ

Subject to:
    aᵢx + Σⱼ aᵢⱼwⱼ ≷ bᵢ    ∀i ∈ I
    x ≤ uy
    x ≥ 0
    wⱼ ≥ 0    ∀j ∈ J
    y ∈ {0,1}
```

Where "≷" means the constraint could be ≤, =, or ≥.

## Choosing the Upper Bound u

The value of `u` is **critical**:

### Too Small
- May eliminate feasible solutions
- Model becomes infeasible or suboptimal

### Too Large
- **Weak LP relaxation:** In the LP relaxation (where `y` is continuous `0 ≤ y ≤ 1`), large `u` allows fractional `y` values with `x` far from integer
- Poor solver performance
- Numerical instability

### Best Practice
Choose `u` as **tight as possible** while ensuring all feasible values of `x` satisfy `x ≤ u`.

**Methods to determine u:**
1. **Problem-specific bounds:** Use physical limits (capacity, demand, budget)
2. **Constraint analysis:** Derive from other constraints in the model
3. **Preprocessing:** Use constraint propagation techniques

**Example:**
If you have constraint `x + 2y ≤ 100` and `y ≥ 0`, then `x ≤ 100` is a valid bound.

## Common Pitfalls

1. **Forgetting the binary constraint**
   - Result: `y` becomes continuous, model no longer enforces the discontinuity

2. **Using the same indicator for multiple variables**
   - If you need `x₁` and `x₂` to each be discontinuous, you generally need separate indicators `y₁` and `y₂`

3. **Big-M too large**
   - Causes numerical issues
   - Weakens LP relaxation → poor branch-and-bound performance

4. **Not validating bounds**
   - If actual optimal `x` exceeds your bound `u`, you get wrong answer

## Extensions

### Multiple Ranges

If `x` can be in one of several disjoint ranges:
```
x ∈ {0} ∪ [10,20] ∪ [30,40]
```

Use multiple indicators:
```
x = 0·y₀ + x₁·y₁ + x₂·y₂
10y₁ ≤ x₁ ≤ 20y₁
30y₂ ≤ x₂ ≤ 40y₂
y₀ + y₁ + y₂ = 1
```

This is also known as a **SOS1 (Special Ordered Set Type 1)** formulation.

## Summary Table

| Technique | Variables Added | Constraints Added | When to Use |
|-----------|----------------|-------------------|-------------|
| Discontinuous Variable | 1 binary | 2 | Variable must be 0 or in [l,u] |
| Fixed Cost | 1 binary | 1 | Cost has jump discontinuity at 0 |

**Key Insight:** Both techniques use the same fundamental pattern:
```
x ≤ uy  (forces x=0 when y=0)
```

The difference is whether you also need a lower bound `x ≥ ly`.
