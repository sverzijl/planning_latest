# Eliminating Products of Variables (Linearization)

## Overview

Many optimization problems involve **products of variables** in the objective or constraints. These bilinear or quadratic terms make the problem nonlinear and difficult to solve.

**Goal:** Transform products into linear formulations using integer variables and additional constraints.

**Trade-off:** Adds binary variables and constraints, but enables use of mature MIP solvers.

## Three Cases

1. **Binary × Binary:** Product of two 0-1 variables
2. **Binary × Continuous:** Product of 0-1 variable and continuous variable
3. **Continuous × Continuous:** Product of two continuous variables

Each requires different techniques.

## Case 1: Product of Two Binary Variables

### Problem

Linearize the product:
```
y = x₁x₂    where x₁, x₂ ∈ {0,1}
```

### Truth Table

| x₁ | x₂ | x₁x₂ |
|----|----|----|
| 0  | 0  | 0  |
| 0  | 1  | 0  |
| 1  | 0  | 0  |
| 1  | 1  | 1  |

Product is 1 only when BOTH variables are 1 → this is logical AND.

### Formulation

Introduce new binary variable `y ∈ {0,1}` to represent the product.

**Constraints:**
```
y ≤ x₁
y ≤ x₂
y ≥ x₁ + x₂ - 1
y ∈ {0,1}
```

### Verification

**Case 1:** `x₁=0, x₂=0`
```
y ≤ 0  →  y = 0
y ≤ 0  →  y = 0
y ≥ -1  (not binding)
Result: y = 0 ✓
```

**Case 2:** `x₁=0, x₂=1`
```
y ≤ 0  →  y = 0
y ≤ 1  (not binding)
y ≥ 0  (not binding)
Result: y = 0 ✓
```

**Case 3:** `x₁=1, x₂=0`
```
y ≤ 1  (not binding)
y ≤ 0  →  y = 0
y ≥ 0  (not binding)
Result: y = 0 ✓
```

**Case 4:** `x₁=1, x₂=1`
```
y ≤ 1  (allows y=1)
y ≤ 1  (allows y=1)
y ≥ 1  →  y = 1
Result: y = 1 ✓
```

All cases correct!

### Example: Combined Fixed Costs

Two facilities. Opening facility 1 costs $100k, facility 2 costs $150k. If BOTH are opened, get $50k discount.

```
Variables:
    x₁, x₂ ∈ {0,1}  (facility open indicators)
    y ∈ {0,1}        (both facilities open)

Objective:
    Minimize: 100x₁ + 150x₂ - 50y

Constraints:
    y ≤ x₁
    y ≤ x₂
    y ≥ x₁ + x₂ - 1
```

Scenarios:
- Open neither: `x₁=0, x₂=0, y=0` → cost = $0
- Open facility 1: `x₁=1, x₂=0, y=0` → cost = $100k
- Open facility 2: `x₁=0, x₂=1, y=0` → cost = $150k
- Open both: `x₁=1, x₂=1, y=1` → cost = $100k + $150k - $50k = $200k ✓

### Extension: Product of Multiple Binaries

For `y = x₁x₂x₃` (product of three binaries):

```
y ≤ x₁
y ≤ x₂
y ≤ x₃
y ≥ x₁ + x₂ + x₃ - 2
y ∈ {0,1}
```

General formula for `n` binaries:
```
y ≤ xᵢ               ∀i = 1..n
y ≥ Σᵢ xᵢ - (n-1)
y ∈ {0,1}
```

## Case 2: Product of Binary and Continuous

### Problem

Linearize:
```
y = x₁x₂    where x₁ ∈ {0,1}, 0 ≤ x₂ ≤ u
```

### Key Insight

When `x₁=0`: `y` must be 0
When `x₁=1`: `y` must equal `x₂`

### Formulation

Introduce continuous variable `y ≥ 0` to represent the product.

**Constraints:**
```
y ≤ ux₁
y ≤ x₂
y ≥ x₂ - u(1 - x₁)
y ≥ 0
```

Where `u` is a known upper bound on `x₂`.

### Verification Table

| x₁ | x₂ (range) | Constraints | Implied y |
|----|-----------|-------------|-----------|
| 0  | 0 ≤ w ≤ u | y ≤ 0<br>y ≤ w<br>y ≥ w - u<br>y ≥ 0 | y = 0 ✓ |
| 1  | 0 ≤ w ≤ u | y ≤ u<br>y ≤ w<br>y ≥ w<br>y ≥ 0 | y = w ✓ |

**Explanation for x₁=0:**
- `y ≤ 0` forces `y=0`
- Other constraints are consistent with `y=0`

**Explanation for x₁=1:**
- `y ≤ w` and `y ≥ w` together force `y=w`
- `y ≤ u` is not binding (since `w ≤ u`)

### Example: Variable Production Costs

A factory has:
- Fixed setup cost: $1000 (incurred if `x₁=1`, meaning production occurs)
- Variable cost: $5 per unit produced (`x₂` units)

Total variable cost should be `0` if no production (`x₁=0`), or `5x₂` if producing (`x₁=1`).

```
Variables:
    x₁ ∈ {0,1}    (production indicator)
    x₂ ∈ [0, 500] (units produced)
    y ≥ 0         (variable cost component)

Objective:
    Minimize: 1000x₁ + y

Constraints:
    y ≤ 500x₁        (if not producing, y ≤ 0)
    y ≤ 5x₂           (y can't exceed unit cost × quantity)
    y ≥ 5x₂ - 2500(1-x₁)  (if producing, y ≥ 5x₂)
    x₂ ≤ 500x₁        (can't produce without setup)
```

Using `u = 5×500 = 2500` (max value of `5x₂`).

Scenarios:
- No production: `x₁=0, x₂=0, y=0` → cost = $0 ✓
- Produce 100 units: `x₁=1, x₂=100, y=500` → cost = $1000 + $500 = $1500 ✓

### Choosing Upper Bound u

**Critical:** `u` must be a valid upper bound on the continuous variable `x₂` (or the expression being multiplied).

**Methods:**
1. **Variable bounds:** If `x₂ ≤ u_x₂` given, use that
2. **Coefficient scaling:** If constraint is `c·x₂`, use `u_y = c·u_x₂`
3. **Constraint analysis:** Derive from other constraints

**Impact of u:**
- Too small: May eliminate feasible solutions
- Too large: Weak LP relaxation, poor solver performance

**Best:** As tight as possible while ensuring validity.

## Case 3: Product of Two Continuous Variables

### Problem

Linearize:
```
y = x₁x₂    where l₁ ≤ x₁ ≤ u₁, l₂ ≤ x₂ ≤ u₂
```

This is the hardest case. Two approaches:

### Method 1: Transform to Separable Form

**Key Idea:** Replace product with difference of squares.

**Transformation:**
```
Define:
    z₁ = ½(x₁ + x₂)
    z₂ = ½(x₁ - x₂)

Then:
    x₁ = z₁ + z₂
    x₂ = z₁ - z₂

And:
    x₁x₂ = (z₁+z₂)(z₁-z₂) = z₁² - z₂²
```

**Result:** Product becomes **separable function** `f(z₁, z₂) = z₁² - z₂²`

Now use **piecewise linear approximation** (λ-formulation) for each squared term.

**Bounds on z₁ and z₂:**
```
½(l₁ + l₂) ≤ z₁ ≤ ½(u₁ + u₂)
½(l₁ - u₂) ≤ z₂ ≤ ½(u₁ - l₂)
```

**Advantages:**
- Converts bilinear term to separable quadratic
- Can use standard piecewise linear techniques

**Disadvantages:**
- Requires approximation (not exact)
- Introduces many λ variables
- Functions are non-convex → requires SOS2 and MIP solve

### Method 2: Special Case (One Variable Isolated)

If one variable appears **only** in products (not elsewhere), there's a simpler approach.

**Condition:**
- `l₁, l₂ ≥ 0` (both variables nonnegative)
- `x₁` appears ONLY in products `x₁x₂` (not in other terms)

**Formulation:**

Substitute `z = x₁x₂` and add:
```
l₁x₂ ≤ z ≤ u₁x₂
```

After solving, recover `x₁ = z/x₂` when `x₂ > 0`. When `x₂=0`, `x₁` is undetermined (but `z=0` regardless).

**Verification:**
- Ensures `l₁ ≤ x₁ ≤ u₁` whenever `x₂ > 0`
- Simpler than general case (no new binaries or λ variables)

**Example:** Maximize revenue `R = px` where:
- `p` = price (decision variable)
- `x` = quantity (decision variable, appears elsewhere in model)
- `R` appears only in objective

```
Minimize: -R
Subject to:
    l_p × x ≤ R ≤ u_p × x
    [other constraints on x]
```

This is linear! After solving for `R` and `x`, recover `p = R/x`.

## Comparison of Methods

| Product Type | Variables Added | Constraints Added | Exact? | Solver Type |
|--------------|----------------|-------------------|--------|-------------|
| Binary × Binary | 1 binary | 3 | Yes | MIP |
| Binary × Continuous | 1 continuous | 4 | Yes | MIP |
| Continuous × Continuous (general) | ~20 λ per product | ~10 | No (approx) | MIP |
| Continuous × Continuous (special) | 1 continuous | 2 | Exact | LP or MIP |

## Complete Example: Multi-Period Production

**Problem:** Plan production over 3 periods with:
- Setup cost: $500 per period (if producing)
- Variable cost: $10 per unit
- Quantity discount: 10% off if produce > 100 units in a period

**Variables:**
```
xᵢ ∈ {0,1}    : setup indicator for period i
qᵢ ∈ [0,200]  : quantity produced in period i
yᵢ ≥ 0        : variable cost in period i (= 10qᵢ if xᵢ=1, else 0)
dᵢ ∈ {0,1}    : discount indicator (1 if qᵢ > 100)
sᵢ ≥ 0        : discount savings (= 0.1yᵢ if dᵢ=1, else 0)
```

**Products to linearize:**
1. `yᵢ = xᵢ × (10qᵢ)` → Binary × Continuous
2. `sᵢ = dᵢ × (0.1yᵢ)` → Binary × Continuous

**Formulation:**

```
Objective:
    Minimize: Σᵢ (500xᵢ + yᵢ - sᵢ)

Constraints:
    # Linearize yᵢ = xᵢ × (10qᵢ)
    yᵢ ≤ 2000xᵢ            ∀i  (max cost = 10×200)
    yᵢ ≤ 10qᵢ               ∀i
    yᵢ ≥ 10qᵢ - 2000(1-xᵢ) ∀i

    # Link setup to production
    qᵢ ≤ 200xᵢ              ∀i

    # Discount indicator
    qᵢ ≥ 100dᵢ              ∀i  (if discount, must produce ≥100)
    qᵢ ≤ 100 + 100dᵢ        ∀i  (if no discount, can't exceed 100)

    # Linearize sᵢ = dᵢ × (0.1yᵢ)
    sᵢ ≤ 200dᵢ              ∀i  (max savings = 0.1×2000)
    sᵢ ≤ 0.1yᵢ              ∀i
    sᵢ ≥ 0.1yᵢ - 200(1-dᵢ)  ∀i

    # Demand constraints (example)
    Σᵢ qᵢ ≥ 300             (total demand)
```

## Advanced Techniques

### McCormick Envelopes

For `z = x₁x₂` with bounds `l₁ ≤ x₁ ≤ u₁` and `l₂ ≤ x₂ ≤ u₂`:

**Convex hull (strongest possible linear relaxation):**
```
z ≥ l₁x₂ + l₂x₁ - l₁l₂
z ≥ u₁x₂ + u₂x₁ - u₁u₂
z ≤ l₁x₂ + u₂x₁ - l₁u₂
z ≤ u₁x₂ + l₂x₁ - u₁l₂
```

This gives the tightest possible linear relaxation but does not eliminate the nonlinearity—it just provides bounds. Still need binary variables or piecewise linear for exact linearization.

### Reformulation-Linearization Technique (RLT)

Advanced method that:
1. Multiplies constraints by variables
2. Introduces new variables for products
3. Applies McCormick envelopes

Provides tighter formulations but increases problem size. Best for difficult instances.

## Common Pitfalls

1. **Wrong bounds in binary × continuous**
   - Using bound on `x₂` when you need bound on `c·x₂`
   - Results in incorrect linearization

2. **Forgetting non-negativity**
   - Product variable `y` needs `y ≥ 0` if both original variables are non-negative

3. **Using separable form for non-isolated variables**
   - Method 2 for continuous × continuous requires one variable to appear ONLY in products
   - Otherwise, substitution doesn't work

4. **Too many products**
   - Each product adds variables and constraints
   - Model can become very large
   - Consider: reformulation to reduce products, or nonlinear solver

## Summary

**General Approach:**
1. Identify all product terms in model
2. Classify each: binary×binary, binary×continuous, continuous×continuous
3. Apply appropriate linearization
4. Choose tight bounds
5. Verify formulation on small test cases

**When to Use:**
- Products appear in otherwise linear model
- Want global optimum (not local)
- Have access to good MIP solver

**When NOT to Use:**
- Too many products (model becomes huge)
- Products are deeply nested
- Nonlinear solver might be faster/easier

**Key to Success:** Tight bounds on all variables. Loose bounds → weak formulation → poor performance.
