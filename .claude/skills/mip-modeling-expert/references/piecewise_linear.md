# Piecewise Linear Approximations

## Overview

Many practical optimization problems involve **nonlinear** objective functions or constraints. While general nonlinear programming is difficult and may not guarantee global optima, **separable** nonlinear functions can be approximated using **piecewise linear functions**, enabling solution via LP or MIP.

**Key Advantage:** Transform nonlinear problems into linear ones that modern solvers can handle efficiently.

## Separable Functions

### Definition

A function is **separable** if it can be written as a sum of functions of individual variables:

```
F(x₁, x₂, ..., xₙ) = f₁(x₁) + f₂(x₂) + ... + fₙ(xₙ)
```

Each `fᵢ` depends only on one variable.

### Examples of Separable Functions

**Separable:**
```
x₁² + 1/x₂ - 2x₃        = f₁(x₁) + f₂(x₂) + f₃(x₃)
x₁² + 5x₁ - x₂          = g₁(x₁) + g₂(x₂)
100x₁⁰·⁵ + 10log(x₂)    = h₁(x₁) + h₂(x₂)
```

**NOT Separable:**
```
x₁x₂ + 3x₂ + x₂²        Cannot split x₁x₂ term
1/(x₁ + x₂) + x₃        Cannot split 1/(x₁+x₂)
sin(x₁ + x₂)            Argument involves multiple variables
```

### Why Separability Matters

For separable functions:
- Each nonlinear term `fᵢ(xᵢ)` can be approximated independently
- Approximations combine linearly → overall function remains linear
- Can use λ-formulation (see below)

For non-separable functions, piecewise linear approximation is much more complex.

## Piecewise Linear Approximation Concept

**Goal:** Replace smooth curve `f(x)` with connected straight line segments.

```
   f(x)
    ↑
  8 |                       ●  x₄
    |                    _/´
    |                _/´´
  2 |           ●/´´         x₃
    |        _/´
 0.5|    ●/´                 x₂
    | _/´
  0 |●________________________> x
    0   1   2   3   4
       x₁ x₂  x₃   x₄

Approximation of f(x) = ½x²
```

**Breakpoints:** Points where slope changes: `(x₁,f₁), (x₂,f₂), (x₃,f₃), (x₄,f₄)`

**Segments:** Linear pieces connecting consecutive breakpoints

## The λ-Formulation

The **λ-formulation** expresses any point as a weighted combination of breakpoints.

### Setup

Given:
- `n` breakpoints: `x₁, x₂, ..., xₙ`
- Function values: `f₁ = f(x₁), f₂ = f(x₂), ..., fₙ = f(xₙ)`

Introduce:
- **Weight variables:** `λ₁, λ₂, ..., λₙ ≥ 0`

### Formulation

```
x = Σᵢ λᵢxᵢ              (x is weighted combination of breakpoints)
f̃(x) = Σᵢ λᵢfᵢ            (approximated function value)
Σᵢ λᵢ = 1                (weights sum to 1)
λᵢ ≥ 0                   (non-negative weights)
```

**Plus adjacency requirement:** At most two λᵢ can be nonzero, and they must be adjacent.

This adjacency constraint is a **SOS2** (Special Ordered Set Type 2).

### Why Adjacency is Needed

Without adjacency, the formulation might select non-adjacent breakpoints, creating a poor approximation.

**Example:** For `f(x) = ½x²` with breakpoints at 0, 1, 2, 4:

Without adjacency, could have:
```
λ₁ = 0.5 (x₁=0, f₁=0)
λ₄ = 0.5 (x₄=4, f₄=8)

→ x = 0(0.5) + 4(0.5) = 2
→ f̃(2) = 0(0.5) + 8(0.5) = 4

But actual f(2) = ½(4) = 2
Error: 4 - 2 = 2 (huge!)
```

With adjacency (use `λ₃` and `λ₄`):
```
λ₃ = 0.5 (x₃=2, f₃=2)
λ₄ = 0.5 (x₄=4, f₄=8)

→ x = 2(0.5) + 4(0.5) = 3
→ f̃(3) = 2(0.5) + 8(0.5) = 5

Actual f(3) = ½(9) = 4.5
Error: 5 - 4.5 = 0.5 (small)
```

## Detailed Example: Quadratic Function

Approximate `f(x) = ½x²` on domain [0, 4].

### Step 1: Choose Breakpoints

More breakpoints → better approximation, but more variables.

Choose 4 breakpoints: `x₁=0, x₂=1, x₃=2, x₄=4`

### Step 2: Evaluate Function

```
x₁ = 0  →  f₁ = ½(0)² = 0
x₂ = 1  →  f₂ = ½(1)² = 0.5
x₃ = 2  →  f₃ = ½(2)² = 2
x₄ = 4  →  f₄ = ½(4)² = 8
```

### Step 3: λ-Formulation

```
Variables:
    λ₁, λ₂, λ₃, λ₄ ≥ 0

Constraints:
    x = 0λ₁ + 1λ₂ + 2λ₃ + 4λ₄
    f̃ = 0λ₁ + 0.5λ₂ + 2λ₃ + 8λ₄
    λ₁ + λ₂ + λ₃ + λ₄ = 1   (SOS2)
```

### Step 4: Example Calculations

**Evaluate at x=1.5:**

Falls between x₂=1 and x₃=2, so use λ₂ and λ₃:

```
1.5 = 1λ₂ + 2λ₃
λ₂ + λ₃ = 1

Solving:
λ₃ = (1.5 - 1)/(2 - 1) = 0.5
λ₂ = 1 - 0.5 = 0.5

f̃(1.5) = 0.5(0.5) + 2(0.5) = 0.25 + 1 = 1.25
Actual f(1.5) = ½(1.5)² = 1.125
Error = 0.125 (11% relative error)
```

**Evaluate at x=3:**

Falls between x₃=2 and x₄=4:

```
λ₄ = (3-2)/(4-2) = 0.5
λ₃ = 0.5

f̃(3) = 2(0.5) + 8(0.5) = 1 + 4 = 5
Actual f(3) = ½(9) = 4.5
Error = 0.5 (11% relative error)
```

### Step 5: Improving Accuracy

Add more breakpoints in regions of high curvature:

```
Breakpoints: 0, 0.5, 1, 1.5, 2, 3, 4 (7 breakpoints)

→ Smaller segments
→ Better approximation
→ More variables (7 λ's instead of 4)
```

Trade-off between accuracy and model size.

## When is Adjacency Automatic? (No MIP Needed!)

For certain problem structures, the LP relaxation automatically ensures adjacency → **solve as LP, not MIP**.

### Convex Minimization

If:
1. Objective is to **minimize**
2. All functions `fⱼ(xⱼ)` are **convex**

Then: LP solution automatically satisfies adjacency.

**Why?** Convex functions have non-decreasing slopes. Selecting non-adjacent λ's would increase the objective → LP naturally avoids this.

**Result:** Solve as **pure LP**. Fast!

**Example:**
```
Minimize: ½x₁² + x₂² + 2x₃²
Subject to: [linear constraints]
```

All terms are convex → use piecewise linear approximation → solve as LP.

### Concave Maximization

If:
1. Objective is to **maximize**
2. All functions `fⱼ(xⱼ)` are **concave**

Then: LP solution automatically satisfies adjacency.

**Why?** By symmetry with convex minimization.

**Example:**
```
Maximize: √x₁ + log(x₂)
Subject to: [linear constraints]
```

Both terms are concave → piecewise linear → solve as LP.

### Non-Convex Cases (MIP Required)

For:
- Convex **maximization**
- Concave **minimization**
- Mixed convex/concave
- Non-convex, non-concave functions

The LP may violate adjacency → must enforce with **SOS2** → requires MIP solve.

**Example:**
```
Minimize: x₁² - 4x₁ + 3    (non-convex on domain)
```

Must use SOS2 and solve as MIP.

## Choosing Breakpoints

### Uniform Spacing

**Simple approach:** Evenly spaced points

```
For [0, 10] with 5 breakpoints:
x = 0, 2.5, 5, 7.5, 10
```

**Pros:** Easy to generate
**Cons:** May waste points in flat regions, too few in curved regions

### Adaptive Spacing

**Smart approach:** More points where function curves more

**Heuristic:** Place points where second derivative `|f''(x)|` is large.

**Example:** For `f(x) = x²`:
```
f'(x) = 2x
f''(x) = 2 (constant)

Curvature is constant → uniform spacing is fine
```

For `f(x) = e^x`:
```
f''(x) = e^x (grows rapidly)

→ Use denser spacing for larger x values
```

### Rule of Thumb

- **5-10 breakpoints:** Reasonable for most applications
- **More breakpoints:** If high accuracy needed or high curvature
- **Fewer breakpoints:** If problem is large (many variables) and modest accuracy acceptable

## Multi-Dimensional Piecewise Linear

For non-separable functions `f(x₁, x₂)`, piecewise linear approximation is much more complex:

- Requires 2D grid of breakpoints
- Many more λ variables (m×n for m×n grid)
- Adjacency involves triangulation or simplicial complex

**Recommendation:** If possible, reformulate to make separable. If not, consider:
1. Using nonlinear solver instead
2. Fixing one variable, approximating in the other
3. Advanced MIP techniques (beyond scope of this reference)

## Complete Model Template

For minimizing a convex separable function:

```
Given:
    n variables: x₁, ..., xₙ
    Function fⱼ(xⱼ) with breakpoints xⱼ₁, xⱼ₂, ..., xⱼₘ

Decision Variables:
    λⱼᵢ ≥ 0  for j=1..n, i=1..m

Objective:
    Minimize: ΣⱼΣᵢ λⱼᵢfⱼ(xⱼᵢ)

Constraints:
    xⱼ = Σᵢ λⱼᵢxⱼᵢ              ∀j (define variable values)
    Σᵢ λⱼᵢ = 1                  ∀j (convexity constraint - SOS2 if needed)
    [problem-specific constraints on x₁, ..., xₙ]

Properties:
    If all fⱼ are convex: Solve as LP
    Otherwise: Mark each convexity constraint as SOS2, solve as MIP
```

## Applications

### 1. Quantity Discounts

**Problem:** Unit cost decreases with quantity

```
Cost per unit:
    0-100 units: $10/unit
    101-500 units: $8/unit
    501+ units: $6/unit
```

**Formulation:**

This is piecewise linear, but NOT smooth (has kinks). Still works with λ-formulation:

```
Breakpoints: x₁=0, x₂=100, x₃=500, x₄=1000
Total costs:  f₁=0, f₂=1000, f₃=1000+400×8=4200, f₄=4200+500×6=7200

x = quantity ordered
TC(x) = total cost

TC = Σᵢ λᵢfᵢ
x = Σᵢ λᵢxᵢ
Σᵢ λᵢ = 1 (SOS2)
```

This is concave (economies of scale) → for maximizing profit, need SOS2. For minimizing cost subject to demand, may need MIP.

### 2. Nonlinear Production Costs

**Problem:** Energy cost is quadratic in production rate

```
Energy cost = 0.5x² (convex)
```

Use piecewise linear approximation → solve as LP if minimizing cost.

### 3. Portfolio Optimization

**Problem:** Risk is quadratic in investment (for uncorrelated assets)

```
Risk of asset j: σⱼ²xⱼ²
```

If all risk terms are separable (no covariance), can approximate each as piecewise linear.

For minimizing risk: convex objective → LP.

### 4. Efficiency Curves

**Problem:** Generator efficiency varies nonlinearly with output

```
Fuel consumption: f(output) (non-convex U-shaped curve)
```

Minimum consumption at mid-range output. Use piecewise linear + SOS2.

## Accuracy vs. Complexity Trade-off

| Breakpoints | Variables Added | Constraints Added | Typical Max Error |
|-------------|----------------|-------------------|-------------------|
| 3 | 3n | 2n | 10-20% |
| 5 | 5n | 2n | 5-10% |
| 10 | 10n | 2n | 1-5% |
| 20 | 20n | 2n | 0.5-2% |

For `n` variables with `m` breakpoints each:
- Add `m×n` λ variables
- Add `2n` constraints (value + convexity)
- If non-convex: add `n` SOS2 sets

## Common Pitfalls

1. **Using for non-separable functions**
   - Standard λ-formulation only works for separable functions
   - Need advanced techniques for `f(x₁, x₂)`

2. **Forgetting adjacency in non-convex cases**
   - LP relaxation gives wrong answer
   - Must declare SOS2

3. **Too few breakpoints**
   - Poor approximation quality
   - Solution may be far from optimal

4. **Too many breakpoints**
   - Excessive variables slow down solver
   - Diminishing returns on accuracy

5. **Not checking convexity**
   - Solving convex minimization as MIP wastes time
   - Test: compute `f''(x)` or plot function

## Summary

**When to Use Piecewise Linear:**
- Separable nonlinear objective or constraints
- Want global optimum (not just local)
- Have modern LP/MIP solver

**Key Steps:**
1. Verify separability
2. Choose breakpoints
3. Set up λ-formulation
4. Check convexity/concavity
5. Solve as LP (if convex min/concave max) or MIP (with SOS2 otherwise)

**Main Advantage:** Transforms difficult nonlinear problems into tractable linear or mixed-integer problems with proven global optimality.
