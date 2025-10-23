# Complete Worked Examples

## Example 1: Production Planning with Setup Costs

### Problem Description

A factory produces three products (A, B, C) over a 4-week planning horizon. Each product has:
- **Setup cost:** Fixed cost incurred if any amount is produced that week
- **Variable cost:** Cost per unit produced
- **Minimum batch size:** If producing, must produce at least this amount
- **Maximum capacity:** Can't produce more than this per week

### Data

| Product | Setup Cost | Variable Cost | Min Batch | Max Capacity |
|---------|-----------|---------------|-----------|--------------|
| A | $500 | $10/unit | 50 units | 200 units |
| B | $800 | $15/unit | 30 units | 150 units |
| C | $600 | $12/unit | 40 units | 180 units |

**Demand:**
- Week 1: 100 A, 80 B, 60 C
- Week 2: 150 A, 40 B, 90 C
- Week 3: 80 A, 120 B, 50 C
- Week 4: 120 A, 60 B, 100 C

**Inventory:**
- Can hold up to 100 units of each product
- Inventory cost: $2/unit/week
- Start with 0 inventory

### Formulation

**Indices:**
- `i ∈ {A,B,C}` : products
- `t ∈ {1,2,3,4}` : weeks

**Parameters:**
- `k_i` : setup cost for product i
- `c_i` : variable cost for product i
- `l_i` : minimum batch size for product i
- `u_i` : maximum capacity for product i
- `d_{it}` : demand for product i in week t
- `h` : inventory holding cost ($2/unit/week)
- `cap_inv` : inventory capacity (100 units)

**Decision Variables:**
- `x_{it} ≥ 0` : units of product i produced in week t
- `y_{it} ∈ {0,1}` : 1 if product i is produced in week t, 0 otherwise
- `inv_{it} ≥ 0` : inventory of product i at end of week t

**Objective:**
```
Minimize: ΣᵢΣₜ (k_i y_{it} + c_i x_{it}) + h ΣᵢΣₜ inv_{it}
```

**Constraints:**

1. **Discontinuous variable (batch size):**
   ```
   l_i y_{it} ≤ x_{it} ≤ u_i y_{it}    ∀i,t
   ```

2. **Inventory balance:**
   ```
   inv_{i,t-1} + x_{it} = d_{it} + inv_{it}    ∀i,t
   inv_{i,0} = 0    ∀i   (initial inventory)
   ```

3. **Inventory capacity:**
   ```
   inv_{it} ≤ cap_inv    ∀i,t
   ```

### AIMMS Code

```aimms
Set Products {
    Index: i;
    Definition: {'A', 'B', 'C'};
}

Set Weeks {
    Index: t;
    Definition: {1..4};
}

Parameter SetupCost {
    IndexDomain: i;
    Definition: data { A: 500, B: 800, C: 600 };
}

Parameter VarCost {
    IndexDomain: i;
    Definition: data { A: 10, B: 15, C: 12 };
}

Parameter MinBatch {
    IndexDomain: i;
    Definition: data { A: 50, B: 30, C: 40 };
}

Parameter MaxCap {
    IndexDomain: i;
    Definition: data { A: 200, B: 150, C: 180 };
}

Parameter Demand {
    IndexDomain: (i,t);
    Definition: data table;
}

Variable Production {
    IndexDomain: (i,t);
    Range: nonnegative;
}

Variable SetupIndicator {
    IndexDomain: (i,t);
    Range: binary;
}

Variable Inventory {
    IndexDomain: (i,t);
    Range: [0, 100];
}

Variable TotalCost {
    Range: free;
    Definition: sum((i,t), SetupCost(i)*SetupIndicator(i,t) +
                           VarCost(i)*Production(i,t) +
                           2*Inventory(i,t));
}

Constraint BatchLowerBound {
    IndexDomain: (i,t);
    Definition: Production(i,t) >= MinBatch(i) * SetupIndicator(i,t);
}

Constraint BatchUpperBound {
    IndexDomain: (i,t);
    Definition: Production(i,t) <= MaxCap(i) * SetupIndicator(i,t);
}

Constraint InventoryBalance {
    IndexDomain: (i,t);
    Definition: Inventory(i,t-1) + Production(i,t) =
                Demand(i,t) + Inventory(i,t);
}

MathematicalProgram ProductionPlan {
    Objective: TotalCost;
    Direction: minimize;
    Type: MIP;
}
```

### Solution Interpretation

Optimal solution might be:
- Week 1: Produce 200 A (to cover weeks 1-2), 110 B, 100 C
- Week 2: Produce 0 A (use inventory), 0 B, 50 C
- Week 3: Produce 120 A, 150 B, 0 C
- Week 4: Produce 120 A, 0 B, 100 C

**Key insights:**
- Setup costs incentivize larger batches less frequently
- Inventory costs limit how much to overproduce
- Trade-off between setup costs and holding costs

## Example 2: Facility Location with Either-Or Constraints

### Problem Description

A company needs to decide whether to build warehouses to serve 5 customer zones. Two warehouse locations are under consideration: City A and City B.

**Rules:**
- **At least one warehouse must be built** (can build both)
- Each warehouse has a fixed opening cost
- Each warehouse has a maximum capacity
- Shipping costs vary by warehouse-customer pair

### Data

**Warehouse costs and capacities:**
| Warehouse | Fixed Cost | Capacity (tons/month) |
|-----------|-----------|---------------------|
| A | $500,000 | 1000 |
| B | $600,000 | 1200 |

**Demand (tons/month):**
| Customer | Demand |
|----------|--------|
| 1 | 200 |
| 2 | 300 |
| 3 | 250 |
| 4 | 350 |
| 5 | 400 |

**Shipping costs ($/ton):**
|  | Customer 1 | Customer 2 | Customer 3 | Customer 4 | Customer 5 |
|--|-----|-----|-----|-----|-----|
| Warehouse A | 10 | 8 | 12 | 15 | 20 |
| Warehouse B | 15 | 10 | 8 | 10 | 12 |

### Formulation

**Indices:**
- `w ∈ {A,B}` : warehouses
- `c ∈ {1,2,3,4,5}` : customers

**Decision Variables:**
- `y_w ∈ {0,1}` : 1 if warehouse w is opened
- `x_{wc} ≥ 0` : tons shipped from warehouse w to customer c

**Objective:**
```
Minimize: Σ_w FC_w y_w + Σ_w Σ_c SC_{wc} x_{wc}
```
Where `FC_w` = fixed cost, `SC_{wc}` = shipping cost

**Constraints:**

1. **At least one warehouse:**
   ```
   y_A + y_B ≥ 1
   ```

2. **Demand satisfaction:**
   ```
   Σ_w x_{wc} = D_c    ∀c
   ```

3. **Capacity constraints (with indicator):**
   ```
   Σ_c x_{wc} ≤ Cap_w y_w    ∀w
   ```

This ensures warehouse can only ship if it's open.

### Alternative: Conditional Constraint Version

**Rule change:** "If we serve more than 600 tons total, we MUST open warehouse B"

**Formulation:**
```
Let z = total tonnage served = Σ_c D_c = 1500

If Σ_c Σ_w x_{wc} > 600, then y_B = 1
```

Convert to either-or:
```
Σ_c Σ_w x_{wc} ≤ 600 + M·z
y_B ≥ 1 - M·(1-z)

z ∈ {0,1}
```

Where `M = 1500` (total possible tonnage).

## Example 3: Piecewise Linear Cost Function

### Problem Description

An energy company operates a power plant with nonlinear fuel costs. The cost per MWh increases as production increases (decreasing efficiency at high output).

**Fuel cost function:**
```
C(x) = 100x + 0.5x²    (in $, where x is MWh)
```

Domain: 0 ≤ x ≤ 500 MWh

### Piecewise Linear Approximation

**Step 1: Choose breakpoints**

Use 6 breakpoints:
```
x₁ = 0, x₂ = 100, x₃ = 200, x₄ = 300, x₅ = 400, x₆ = 500
```

**Step 2: Calculate function values**

| Breakpoint | x | C(x) = 100x + 0.5x² |
|------------|---|---------------------|
| 1 | 0 | 0 |
| 2 | 100 | 10,000 + 5,000 = 15,000 |
| 3 | 200 | 20,000 + 20,000 = 40,000 |
| 4 | 300 | 30,000 + 45,000 = 75,000 |
| 5 | 400 | 40,000 + 80,000 = 120,000 |
| 6 | 500 | 50,000 + 125,000 = 175,000 |

**Step 3: λ-formulation**

```
Variables:
    λ₁, λ₂, λ₃, λ₄, λ₅, λ₆ ≥ 0

Constraints:
    x = 0λ₁ + 100λ₂ + 200λ₃ + 300λ₄ + 400λ₅ + 500λ₆
    C̃(x) = 0λ₁ + 15000λ₂ + 40000λ₃ + 75000λ₄ + 120000λ₅ + 175000λ₆
    λ₁ + λ₂ + λ₃ + λ₄ + λ₅ + λ₆ = 1   (SOS2)
```

**Step 4: Check convexity**

```
C'(x) = 100 + x     (first derivative)
C''(x) = 1 > 0      (second derivative)
```

Function is **convex**.

**Step 5: Optimization type**

If **minimizing** cost (convex function) → **LP relaxation is exact** → No need for SOS2 enforcement!

```
Minimize: C̃(x)
Subject to:
    [demand constraints, etc.]
    λ₁ + λ₂ + λ₃ + λ₄ + λ₅ + λ₆ = 1
    λᵢ ≥ 0    ∀i
```

Solve as **LP** (not MIP).

### Complete Model with Demand

**Scenario:** Must produce to meet demand of 350 MWh, minimize cost.

```
Minimize: Σᵢ C_i λᵢ

Subject to:
    x = Σᵢ x_i λᵢ
    λ₁ + ... + λ₆ = 1
    x ≥ 350        (demand)
    λᵢ ≥ 0
```

**Optimal solution:**
```
x = 350 lies between x₄=300 and x₅=400

λ₄ = (400-350)/(400-300) = 0.5
λ₅ = (350-300)/(400-300) = 0.5

C̃(350) = 75000(0.5) + 120000(0.5) = 37500 + 60000 = $97,500

Actual C(350) = 100(350) + 0.5(350²) = 35000 + 61250 = $96,250
Error = $1,250 (1.3%)
```

With more breakpoints, error decreases.

## Example 4: Product Linearization in Advertising Budget

### Problem Description

A marketing team allocates budget across 3 channels: TV, Radio, Online.

**Revenue model:**
```
Revenue = effectiveness × budget × reach

For channel i:
R_i = e_i × b_i × r_i

Where:
    b_i ∈ {0,1} : whether to use channel i (minimum commitment required)
    r_i ∈ [0, M_i] : reach (thousands of people)
```

**Data:**
| Channel | Effectiveness ($/person) | Min Reach | Max Reach |
|---------|-------------------------|-----------|-----------|
| TV | 2.0 | 100 | 500 |
| Radio | 1.5 | 50 | 300 |
| Online | 1.8 | 80 | 400 |

**Budget:** Total spend on reach ≤ $50,000
**Cost per reach:** TV: $100/1000, Radio: $80/1000, Online: $90/1000

### Formulation

**Problem:** Linearize `R_i = e_i × b_i × r_i`

This is **constant × binary × continuous** → simplify to **binary × continuous**

Let `v_i = e_i × r_i` (effectiveness times reach). Then:
```
R_i = b_i × v_i
```

**Linearization:**

Introduce `R_i ≥ 0` to represent revenue from channel i.

```
R_i ≤ e_i M_i b_i           (if not using channel, R_i = 0)
R_i ≤ e_i r_i               (R_i ≤ effectiveness × reach)
R_i ≥ e_i r_i - e_i M_i (1-b_i)  (if using channel, R_i = effectiveness × reach)
```

**Complete model:**

```
Variables:
    b_i ∈ {0,1}    : use channel i
    r_i ≥ 0        : reach in channel i (thousands)
    R_i ≥ 0        : revenue from channel i

Maximize: R_TV + R_Radio + R_Online

Subject to:
    # Linearization of R_i = e_i × b_i × r_i
    R_TV ≤ 2.0 × 500 × b_TV = 1000 b_TV
    R_TV ≤ 2.0 × r_TV
    R_TV ≥ 2.0 × r_TV - 1000(1 - b_TV)

    R_Radio ≤ 1.5 × 300 × b_Radio = 450 b_Radio
    R_Radio ≤ 1.5 × r_Radio
    R_Radio ≥ 1.5 × r_Radio - 450(1 - b_Radio)

    R_Online ≤ 1.8 × 400 × b_Online = 720 b_Online
    R_Online ≤ 1.8 × r_Online
    R_Online ≥ 1.8 × r_Online - 720(1 - b_Online)

    # Minimum reach if using channel
    r_TV ≥ 100 b_TV
    r_TV ≤ 500 b_TV

    r_Radio ≥ 50 b_Radio
    r_Radio ≤ 300 b_Radio

    r_Online ≥ 80 b_Online
    r_Online ≤ 400 b_Online

    # Budget constraint
    100 r_TV + 80 r_Radio + 90 r_Online ≤ 50000

    # Non-negativity
    r_i ≥ 0, R_i ≥ 0
```

### Solution Approach

This is a MIP with 3 binary variables and several continuous variables. Modern solvers (CPLEX, Gurobi) solve this quickly.

**Possible optimal solution:**
- Use TV: yes, reach = 300 → cost = $30,000, revenue = 2.0 × 300 = $600
- Use Radio: yes, reach = 250 → cost = $20,000, revenue = 1.5 × 250 = $375
- Use Online: no
- Total cost: $50,000, Total revenue: $975

## Example 5: Warehouse Size Selection (SOS1)

### Problem Description

Select exactly one warehouse size from discrete options.

### Data

| Size Option | Area (sq ft) | Annual Cost | Capacity (units) |
|-------------|-------------|-------------|------------------|
| Small | 5,000 | $100,000 | 500 |
| Medium | 10,000 | $180,000 | 1,200 |
| Large | 20,000 | $300,000 | 2,500 |
| X-Large | 30,000 | $400,000 | 4,000 |

**Demand:** Uncertain, but must handle at least 800 units

### Formulation

```
Variables:
    x_Small, x_Medium, x_Large, x_XLarge ∈ {0,1}

Minimize: 100000 x_Small + 180000 x_Medium + 300000 x_Large + 400000 x_XLarge

Subject to:
    x_Small + x_Medium + x_Large + x_XLarge = 1   (SOS1: exactly one)
    500 x_Small + 1200 x_Medium + 2500 x_Large + 4000 x_XLarge ≥ 800  (capacity)
```

**Solution:**
- Small is infeasible (capacity 500 < 800)
- Medium is feasible and cheapest: cost = $180,000 ✓

**Why use SOS1?**
- Variables have natural ordering (by size)
- Solver uses SOS1 branching for efficiency
- For this small example, not critical, but for hundreds of options, significant speedup

## Summary

These examples demonstrate:

1. **Fixed costs and discontinuous variables** (Production planning)
2. **Either-or and conditional constraints** (Facility location)
3. **Piecewise linear approximation** (Energy costs)
4. **Product linearization** (Marketing budget)
5. **SOS1 discrete choice** (Warehouse sizing)

**Common patterns:**
- Indicator variables link binary decisions to continuous variables
- Big-M formulations enable logical constraints
- Piecewise linear converts nonlinear to linear/MIP
- Product linearization enables bilinear term handling

**Tools needed:**
- MIP solver (CPLEX, Gurobi, AIMMS, GAMS, etc.)
- Good bounds for Big-M values
- Understanding of problem structure (convexity, separability, etc.)
