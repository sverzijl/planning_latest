# Special Ordered Sets (SOS)

## Overview

**Special Ordered Sets (SOS)** are constraints with special structure that MIP solvers can exploit for dramatic performance improvements. SOS constraints were introduced by Beale and Tomlin (1969) and are now standard features in modern solvers.

**Key Insight:** While SOS constraints can always be modeled with binary variables, declaring them explicitly as SOS allows solvers to use specialized branching strategies that reduce the branch-and-bound search tree.

## Types of SOS Constraints

### SOS Type 1 (SOS1)

**Definition:** At most **one** variable in the set can be nonzero.

**Basic Form:**
```
Σᵢ yᵢ ≤ 1    where yᵢ ∈ {0,1}
```

**General Form:**
For continuous variables `0 ≤ xᵢ ≤ uᵢ`:
```
Σᵢ aᵢxᵢ ≤ b    with at most one xᵢ nonzero
```

**Applications:**
- Selecting exactly one option from a set of alternatives
- Mutually exclusive decisions
- Discrete choice variables

### SOS Type 2 (SOS2)

**Definition:** At most **two** variables in the set can be nonzero, and they must be **adjacent** in a specified ordering.

**Form:**
```
Σᵢ λᵢ = 1
λᵢ ≥ 0
```
With the adjacency requirement: If `λᵢ > 0` and `λⱼ > 0` with `i ≠ j`, then `|i-j| = 1`.

**Applications:**
- Piecewise linear approximations (λ-formulation)
- Interpolation between adjacent breakpoints

## SOS1: At Most One Nonzero

### Example: Warehouse Size Selection

A company must choose exactly one warehouse size:

| Option | Size (sq ft) | Annual Cost |
|--------|-------------|-------------|
| 1 | 10,000 | $100,000 |
| 2 | 20,000 | $180,000 |
| 3 | 40,000 | $320,000 |
| 4 | 50,000 | $380,000 |

**Variables:**
```
x₁, x₂, x₃, x₄ ∈ {0,1}
```

**Constraints:**
```
x₁ + x₂ + x₃ + x₄ = 1    (SOS1 constraint)
size = 10000x₁ + 20000x₂ + 40000x₃ + 50000x₄
cost = 100000x₁ + 180000x₂ + 320000x₃ + 380000x₄
```

### Binary Variable Equivalence

A SOS1 constraint with binary variables can be reformulated using standard binary constraints:

```
SOS1: Σᵢ yᵢ ≤ 1

Equivalent to: Σᵢ yᵢ ≤ 1 (standard linear constraint)
```

**Why declare as SOS1?**
- Solvers use smarter branching strategies (see below)
- Reduces search tree size
- **Only beneficial when variables have natural ordering**

### SOS1 Branching Strategy

Standard binary branching creates two nodes:
```
Node 1: yᵢ = 0
Node 2: yᵢ = 1
```

SOS1 branching uses **weighted average** to split the set:

**Example:** Warehouse selection with LP relaxation solution:
```
x₁ = 0.1, x₂ = 0, x₃ = 0, x₄ = 0.9
```

Calculate weighted average:
```
avg = (0.1 × 10000 + 0.9 × 50000) / (0.1 + 0.9)
    = (1000 + 45000) / 1.0
    = 46000 sq ft
```

This falls between option 3 (40,000) and option 4 (50,000), so split the set:

```
Node 1: x₄ = 0        (nonzero element must be in {x₁, x₂, x₃})
Node 2: x₁ = x₂ = x₃ = 0   (must choose x₄)
```

This creates only **2 nodes** instead of branching on each variable individually (which would create many more nodes).

### When to Use SOS1

**Use SOS1 when:**
- Variables have a **natural ordering** (sizes, time periods, distances, etc.)
- You have many mutually exclusive options

**Don't use SOS1 when:**
- No natural ordering exists (unrelated categories)
- Only 2-3 options (no performance benefit)

**Example of bad SOS1 usage:**
```
Choosing between: {truck transport, rail transport, ship transport}
```
These have no natural ordering → SOS1 provides no benefit → use standard binaries.

## SOS2: At Most Two Adjacent Nonzero

### Definition and Purpose

SOS2 is specifically designed for **piecewise linear approximations** using the λ-formulation.

**Constraint:**
```
Σᵢ λᵢ = 1
λᵢ ≥ 0
At most two adjacent λᵢ can be nonzero
```

### Example: Piecewise Linear Function

Approximate `f(x) = ½x²` on [0, 4] with breakpoints at `{0, 1, 2, 4}`:

```
Breakpoints:   x₁=0   x₂=1   x₃=2   x₄=4
Function values: f₁=0   f₂=0.5 f₃=2   f₄=8
```

**Variables:**
```
λ₁, λ₂, λ₃, λ₄ ≥ 0
```

**Constraints:**
```
x = 0λ₁ + 1λ₂ + 2λ₃ + 4λ₄
f̃(x) = 0λ₁ + 0.5λ₂ + 2λ₃ + 8λ₄
λ₁ + λ₂ + λ₃ + λ₄ = 1    (SOS2)
```

**Adjacency requirement:** Only adjacent pairs can be nonzero:
- `{λ₁, λ₂}` or `{λ₂, λ₃}` or `{λ₃, λ₄}`

**Example:** To evaluate `x=3`:
```
x=3 lies between breakpoints x₃=2 and x₄=4

λ₃ = (4-3)/(4-2) = 0.5
λ₄ = (3-2)/(4-2) = 0.5

Check: x = 0 + 0 + 2(0.5) + 4(0.5) = 1 + 2 = 3 ✓
       f̃(3) = 0 + 0 + 2(0.5) + 8(0.5) = 1 + 4 = 5

Actual: f(3) = ½(3²) = 4.5
Error: 5 - 4.5 = 0.5
```

### When Adjacency is Redundant

**Important:** For certain problem types, the adjacency requirement is automatically satisfied by the LP solution → **no MIP solve needed!**

#### Convex Minimization

If you **minimize** a separable function where all component functions `fⱼ(xⱼ)` are **convex**:

```
Minimize: Σⱼ fⱼ(xⱼ)
```

Then the LP relaxation (treating λᵢ as continuous) automatically produces at most two adjacent nonzero λ values.

**Why?** Convex functions have non-decreasing slopes. If non-adjacent λ's were positive, you could reduce the objective by shifting weight to adjacent breakpoints.

**Result:** Solve as **LP**, not MIP. Much faster!

#### Concave Maximization

If you **maximize** a separable function where all `fⱼ(xⱼ)` are **concave**:

```
Maximize: Σⱼ fⱼ(xⱼ)
```

Again, adjacency is automatic → solve as LP.

### When MIP is Required (Non-Convex)

For **non-convex** functions, adjacency must be explicitly enforced.

**Example:** `f(x) = x² - 4x + 3` on [0,4] is non-convex (U-shaped).

Without SOS2, the LP might select:
```
λ₁ = 0.5 (x=0)
λ₄ = 0.5 (x=4)
→ x = 0(0.5) + 4(0.5) = 2
```

But this skips the interior where the function is lowest, giving incorrect approximation.

**Solution:** Declare SOS2 property → solver enforces adjacency via branch-and-bound.

### SOS2 Branching Strategy

Similar to SOS1, but splits on weighted average:

**Example:** LP solution: `λ₂ = 0.3, λ₄ = 0.7`

Weighted average:
```
avg = (0.3 × 1 + 0.7 × 4) / 1.0 = 3.1
```

This falls between `x₃=2` and `x₄=4`, so create nodes:

```
Node 1: λ₄ = 0       (nonzero λ's must be in {λ₁, λ₂, λ₃})
Node 2: λ₁ = λ₂ = λ₃ = 0  (must use λ₄)
```

### Convexity and Concavity

A function is:

**Convex:** Slopes are non-decreasing
```
   f(x)
    ↑
    |     ___/
    |   _/
    | _/
    |/
    └────────> x
```
Examples: `x²`, `eˣ`, `|x|`

**Concave:** Slopes are non-increasing
```
   f(x)
    ↑
    |\___
    |    \___
    |        \___
    |
    └────────────> x
```
Examples: `log(x)`, `√x`, `-x²`

**Visual Test:** If you can draw a straight line between any two points on the curve and it stays above (convex) or below (concave) the curve, it has that property.

## Implementation in Modeling Languages

### AIMMS
```
Constraint ConvexityConstraint {
    Definition: λ₁ + λ₂ + λ₃ + λ₄ = 1;
    Property: SOS2;
}
```

### AMPL
```ampl
var lambda {1..4} >= 0;
subject to convexity: sum {i in 1..4} lambda[i] = 1;
# Suffix for SOS
suffix sosno IN;
suffix ref IN;
let convexity.sosno := 1;
let {i in 1..4} lambda[i].ref := i;
```

### Pyomo
```python
model.lambda_vars = Var([1,2,3,4], domain=NonNegativeReals)
model.sos_constraint = SOSConstraint(var=model.lambda_vars, sos=2)
```

### GAMS
```gams
SOS2 Variable lambda(i);
Equation convexity;
convexity.. sum(i, lambda(i)) =e= 1;
```

## Performance Comparison

**Example:** 100-variable SOS1 set

| Method | Nodes Explored | Solve Time |
|--------|---------------|------------|
| Standard binary branching | ~2^100 worst case | Hours to days |
| SOS1 branching | ~100-200 nodes | Seconds to minutes |

**Speedup:** Orders of magnitude for large SOS sets with natural ordering.

## SOS Priorities

For models with **multiple SOS sets**, you can specify **priorities** to guide branching order:

```
Priority 1: Branch on warehouse size SOS1 first
Priority 2: Then branch on production level SOS2
```

This focuses the search on the most important decisions first.

## Common Pitfalls

1. **Using SOS without natural ordering**
   - SOS exploits ordering → no order = no benefit
   - May even hurt performance

2. **Forgetting to check convexity**
   - Convex minimization/concave maximization don't need SOS2 enforcement
   - Solving as MIP wastes time

3. **Not declaring SOS explicitly**
   - Solvers can't use specialized branching
   - Loses performance advantage

4. **Wrong SOS type**
   - SOS1 for piecewise linear (should be SOS2)
   - SOS2 for discrete choice (should be SOS1)

## Decision Tree: Which SOS Type?

```
Do you need piecewise linear approximation?
├─ Yes → SOS2
│   └─ Is the function convex (min) or concave (max)?
│       ├─ Yes → No need for SOS2, solve as LP
│       └─ No → Use SOS2 (solver enforces adjacency)
│
└─ No → Are you choosing one option from many?
    ├─ Yes → SOS1 (if natural ordering exists)
    └─ No → Standard binary variables
```

## Summary Table

| Feature | SOS1 | SOS2 |
|---------|------|------|
| **Max nonzero** | 1 | 2 |
| **Adjacency required?** | No | Yes |
| **Typical use** | Discrete choice | Piecewise linear |
| **Natural ordering needed?** | Recommended | Required |
| **LP sufficient when?** | Never | Convex min / Concave max |
| **Performance benefit** | Large for many variables | Large for many breakpoints |

**Key Takeaway:** SOS constraints are powerful when used correctly (natural ordering, appropriate problem structure) but provide no benefit or may even hurt performance when misapplied.
