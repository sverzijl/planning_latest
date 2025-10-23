# Either-Or and Conditional Constraints

## Overview

In linear programming, all constraints must hold simultaneously. However, many real-world problems require **logical constraints** where:
- **Either-or:** At least one of several constraints must hold
- **Conditional (If-Then):** If one constraint holds, then another must also hold

These can be modeled using **binary indicator variables** and **Big-M formulations**.

## Technique 1: Either-Or Constraints

### Problem Statement

Given two constraints, **at least one** must be satisfied:

```
Constraint (1): Σⱼ a₁ⱼxⱼ ≤ b₁   OR
Constraint (2): Σⱼ a₂ⱼxⱼ ≤ b₂
```

(At least one must hold, possibly both)

### Applications

1. **Manufacturing Modes**
   - A process can operate in Mode A (with constraint 1) OR Mode B (with constraint 2)
   - Example: Low-temperature operation OR high-pressure operation

2. **Resource Allocation**
   - Budget constraint on labor OR budget constraint on materials must be satisfied

3. **Route Selection**
   - Ship goods via Route 1 (capacity constraint 1) OR Route 2 (capacity constraint 2)

### Mathematical Formulation

Introduce:
- Binary indicator `y ∈ {0,1}`
- **Big-M constants** `M₁` and `M₂`

**Big-M Requirements:**
- `M₁` must be large enough that `Σⱼ a₁ⱼxⱼ ≤ b₁ + M₁` is **always satisfied**
- `M₂` must be large enough that `Σⱼ a₂ⱼxⱼ ≤ b₂ + M₂` is **always satisfied**

**Formulation:**
```
Σⱼ a₁ⱼxⱼ ≤ b₁ + M₁y
Σⱼ a₂ⱼxⱼ ≤ b₂ + M₂(1-y)
y ∈ {0,1}
```

**Logic:**

| y | Effect |
|---|--------|
| 0 | Constraint (1): `Σⱼ a₁ⱼxⱼ ≤ b₁` enforced<br>Constraint (2): `Σⱼ a₂ⱼxⱼ ≤ b₂ + M₂` relaxed (always satisfied) |
| 1 | Constraint (1): `Σⱼ a₁ⱼxⱼ ≤ b₁ + M₁` relaxed (always satisfied)<br>Constraint (2): `Σⱼ a₂ⱼxⱼ ≤ b₂` enforced |

In both cases, at least one constraint is enforced. The other may or may not be satisfied (it's relaxed by adding Big-M).

### Example: Production Modes

A chemical plant can operate in two modes:

- **Mode A:** Temperature ≤ 150°C
- **Mode B:** Pressure ≤ 10 bar

At least one constraint must be satisfied (can't have both high temperature AND high pressure).

```
Variables:
    T ≥ 0   (temperature in °C)
    P ≥ 0   (pressure in bar)
    y ∈ {0,1} (mode indicator)

Constraints:
    T ≤ 150 + 200y      (Mode A enforced when y=0)
    P ≤ 10 + 20(1-y)    (Mode B enforced when y=1)
```

Assuming max temperature is 350°C (`M₁=200`) and max pressure is 30 bar (`M₂=20`):

- `y=0`: `T ≤ 150` (Mode A), `P ≤ 30` (relaxed)
- `y=1`: `T ≤ 350` (relaxed), `P ≤ 10` (Mode B)

### Choosing Big-M Values

**Too Small:** May cut off feasible solutions (model becomes infeasible or wrong)

**Too Large:**
- Weak LP relaxation → poor branch-and-bound performance
- Numerical instability
- Solver may struggle

**Best Practice:**

1. **Derive from problem bounds:**
   ```
   If xⱼ ≤ uⱼ for all j, then:
   M₁ ≥ Σⱼ max(0, a₁ⱼ)·uⱼ - b₁
   ```

2. **Use constraint propagation:**
   - Analyze other constraints to deduce tighter bounds

3. **Start conservative, then tighten:**
   - Use a large value to verify model correctness
   - Then iteratively reduce while maintaining feasibility

**Example Calculation:**

For constraint `2x₁ + 3x₂ ≤ 100` with `x₁ ≤ 30`, `x₂ ≤ 40`:

```
Maximum LHS = 2(30) + 3(40) = 60 + 120 = 180
M = 180 - 100 = 80
```

So `M=80` ensures `2x₁ + 3x₂ ≤ 100 + 80 = 180` is always satisfied.

### Extension: K-out-of-N Constraints

**Problem:** At least `K` out of `N` constraints must hold.

**Solution:** Introduce `N` binary indicators `y₁, y₂, ..., yₙ`:

```
Σⱼ a₁ⱼxⱼ ≤ b₁ + M₁y₁
Σⱼ a₂ⱼxⱼ ≤ b₂ + M₂y₂
...
Σⱼ aₙⱼxⱼ ≤ bₙ + Mₙyₙ

Σᵢ yᵢ ≤ N - K

yᵢ ∈ {0,1}  ∀i
```

The sum `Σᵢ yᵢ ≤ N-K` ensures at most `N-K` constraints are relaxed, so at least `K` are enforced.

**Example:** At least 3 out of 5 budget constraints must be satisfied → `Σᵢ yᵢ ≤ 2`.

## Technique 2: Conditional Constraints (If-Then)

### Problem Statement

**If** constraint (1) is satisfied, **then** constraint (2) must also be satisfied:

```
If    Σⱼ a₁ⱼxⱼ ≤ b₁
Then  Σⱼ a₂ⱼxⱼ ≤ b₂
```

### Logical Equivalence

Using logical notation:
```
A → B   (A implies B)
```

This is equivalent to:
```
¬A ∨ B   (NOT A  OR  B)
```

In words: "Either constraint (1) is violated OR constraint (2) holds."

We can rewrite as an **either-or constraint:**
```
Σⱼ a₁ⱼxⱼ > b₁   OR   Σⱼ a₂ⱼxⱼ ≤ b₂
```

Notice the sign flip on constraint (1)!

### Handling Strict Inequality

Linear programming cannot directly handle strict inequalities (`>`). We approximate using a small tolerance `ε`:

```
Σⱼ a₁ⱼxⱼ > b₁   becomes   Σⱼ a₁ⱼxⱼ ≥ b₁ + ε
```

Choose `ε` based on problem scale (e.g., `ε = 0.01` for currency, `ε = 0.001` for percentages).

### Mathematical Formulation

Introduce:
- Binary indicator `y ∈ {0,1}`
- Big-M upper bound on constraint (2): `M`
- Big-L lower bound on constraint (1): `L`
- Tolerance: `ε`

**Formulation:**
```
Σⱼ a₁ⱼxⱼ ≥ b₁ + ε - Ly
Σⱼ a₂ⱼxⱼ ≤ b₂ + M(1-y)
y ∈ {0,1}
```

**Logic:**

| y | Effect |
|---|--------|
| 0 | Constraint (1): `Σⱼ a₁ⱼxⱼ ≥ b₁ + ε` (violated)<br>Constraint (2): `Σⱼ a₂ⱼxⱼ ≤ b₂ + M` (relaxed) |
| 1 | Constraint (1): `Σⱼ a₁ⱼxⱼ ≥ b₁ + ε - L` (relaxed)<br>Constraint (2): `Σⱼ a₂ⱼxⱼ ≤ b₂` (enforced) |

**Interpretation:**
- If `y=0`: Constraint (1) must be violated, so the "If" part is false → no requirement on constraint (2)
- If `y=1`: Constraint (2) must hold, satisfying the "Then" part

Since we need `(¬A ∨ B)`, this covers both cases:
- `¬A` (constraint 1 violated) when `y=0`
- `B` (constraint 2 holds) when `y=1`

### Applications

1. **Safety Regulations**
   - If production exceeds 1000 units, then quality inspection must be performed
   - If temperature > 200°C, then cooling system must be active

2. **Resource Dependencies**
   - If skilled labor is used, then training budget must be allocated
   - If premium materials are purchased, then premium price must be charged

3. **Operational Rules**
   - If overtime is used, then supervisor must be present
   - If inventory exceeds warehouse capacity, then external storage must be rented

### Example: Production Volume and Quality Control

**Rule:** If production exceeds 1000 units, quality inspectors must be hired (at least 5).

```
Variables:
    x ≥ 0   (production volume)
    q ≥ 0   (number of inspectors)
    y ∈ {0,1}

Constraints:
    x ≥ 1000 + 1 - 10000y     (If x ≥ 1001, then y=1)
    q ≥ 5 - 100(1-y)           (If y=1, then q ≥ 5)
```

Using:
- `ε = 1` (one unit tolerance)
- `L = 10000` (upper bound on production)
- `M = 100` (upper bound on inspectors)

**Scenarios:**
- `x = 500`: Can set `y=0`, then `x ≥ 1001 - 10000 = -8999` ✓, `q ≥ -95` ✓ (no requirements)
- `x = 1500`: Must set `y=1`, then `x ≥ 1001 - 0 = 1001` ✓, `q ≥ 5` ✓ (hiring required)

### Choosing Bounds

**Big-L (Lower Bound on Constraint 1):**
- Should be a valid lower bound on `Σⱼ a₁ⱼxⱼ`
- If all `xⱼ ≥ 0`, then `L = 0` works (but may not be tight)

**Big-M (Upper Bound on Constraint 2):**
- Same principles as either-or constraints

**Tolerance ε:**
- Should be small relative to problem scale
- Too small: may not adequately separate cases due to numerical precision
- Too large: may incorrectly trigger conditional when constraint (1) is borderline

## Comparison: Either-Or vs. Conditional

| Type | Meaning | Formulation |
|------|---------|-------------|
| Either-Or | At least one constraint holds | `C₁ ≤ b₁ + M₁y`<br>`C₂ ≤ b₂ + M₂(1-y)` |
| If-Then | If C₁ holds, then C₂ holds | `C₁ ≥ b₁ + ε - Ly`<br>`C₂ ≤ b₂ + M(1-y)` |

Note the sign changes and the use of tolerance `ε` for conditional constraints.

## Advanced: If-Then-Else

**Problem:** If constraint (1) holds, then constraint (2) must hold; otherwise, constraint (3) must hold.

```
If    Σⱼ a₁ⱼxⱼ ≤ b₁
Then  Σⱼ a₂ⱼxⱼ ≤ b₂
Else  Σⱼ a₃ⱼxⱼ ≤ b₃
```

**Formulation:**

Use indicator `y` where:
- `y=1`: Constraint (1) holds → enforce constraint (2)
- `y=0`: Constraint (1) violated → enforce constraint (3)

```
Σⱼ a₁ⱼxⱼ ≤ b₁ + M₁(1-y)
Σⱼ a₁ⱼxⱼ ≥ b₁ + ε - L₁y
Σⱼ a₂ⱼxⱼ ≤ b₂ + M₂(1-y)
Σⱼ a₃ⱼxⱼ ≤ b₃ + M₃y
```

First two constraints define whether (1) holds. Last two constraints enforce (2) or (3) accordingly.

## Common Pitfalls

1. **Wrong inequality direction**
   - Conditional constraints require reversing the inequality in constraint (1)

2. **Forgetting tolerance ε**
   - Strict inequality `>` must be approximated with `≥ b + ε`

3. **Loose Big-M/Big-L**
   - Results in weak formulation and poor solver performance

4. **Confusing OR with XOR**
   - Either-or means "at least one" (both can hold)
   - Exclusive-or (XOR) means "exactly one" (requires additional constraint: `y₁ + y₂ = 1` for two constraints)

## Summary

| Technique | Binary Vars | Big-M Needed | Use When |
|-----------|-------------|--------------|----------|
| Either-Or | 1 | 2 (one per constraint) | At least one constraint must hold |
| If-Then | 1 | 1 (M) + 1 lower bound (L) | Implication relationship between constraints |

Both techniques transform logical relationships into linear constraints using indicator variables and Big-M formulations.
