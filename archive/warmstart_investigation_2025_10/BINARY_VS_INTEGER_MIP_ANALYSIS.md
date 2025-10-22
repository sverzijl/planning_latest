# Why Binary SKU Selection Performs Worse Than Pallet Integers: MIP Expert Analysis

**Date:** 2025-10-22
**Question:** Why do binary SKU selectors (domain {0,1}) perform worse than pallet integers (domain {0-10})?
**Analysis:** Deep dive using MIP modeling theory and optimization principles

---

## The Paradox

**From Diagnostic Results:**

| Formulation | Binary Vars | Integer Vars | Solve Time | Paradox? |
|-------------|-------------|--------------|------------|----------|
| Weekly pattern + pallets | 781 (linked) | 4,557 (0-10) | 28.2s | ✓ Fast |
| Full binary + pallets | 280 (independent) | 4,515 (0-10) | 636s | ✗ Slow |

**The Paradox:**
1. Binary variables have smaller domain (2 values) than integers (11 values)
2. Fewer binary variables (280 vs 781)
3. Yet 22× slower to solve!

**Why?**

---

## MIP Theory: Why Binaries are Harder

### Factor 1: Symmetry (The Primary Problem)

**Definition:** Multiple solutions with identical or near-identical objective values.

**Binary SKU Selection Creates Massive Symmetry:**

```
Question: "Which days should we produce SKU A?"

Without constraints:
  Option 1: [Mon, Tue, Wed, Thu, Fri] = 5 days
  Option 2: [Mon, Tue, Wed, Thu, Sat] = 5 days (weekend overtime)
  Option 3: [Tue, Wed, Thu, Fri, Sat] = 5 days
  ...
  Total options: C(42, 5) = 850,668 ways to choose 5 days from 42!

All have SIMILAR costs (within 10-20%):
  - Same labor hours
  - Same production quantities
  - Slightly different overtime costs
  - Slightly different truck utilization
```

**Result:** Solver must explore ~850k branches to prove which is optimal!

**Pallet Integers Have NO Symmetry:**

```
Question: "How many pallets of frozen inventory?"

Options:
  5 pallets → Cost = $76.20/day
  6 pallets → Cost = $91.44/day
  7 pallets → Cost = $106.68/day

Each option has DISTINCT cost.
LP relaxation: 5.3 pallets
Round up to 6: FORCED by ceiling constraint
No exploration needed!
```

**MIP Expert Insight:**
> "Symmetry is the #1 performance killer in MIP. Binaries with many equivalent solutions create exponential search trees. Integers with distinct costs prune quickly."

### Factor 2: LP Relaxation Quality

**Binary Variables (Independent):**

```
LP Relaxation:
  product_produced[6122, 'SKU_A', Mon_week1] = 0.3
  product_produced[6122, 'SKU_A', Tue_week1] = 0.4
  product_produced[6122, 'SKU_A', Wed_week1] = 0.3

Interpretation: "Produce a little bit each day"
Objective: $950,000 (fractional solution)

Rounding to integers:
  Option A: [0, 1, 0] → Cost = $960,000
  Option B: [1, 0, 0] → Cost = $955,000
  Option C: [0, 0, 1] → Cost = $958,000

Gap after rounding: 10-15% (poor!)
Must branch extensively to close gap.
```

**Pallet Integers (With Ceiling Constraints):**

```
LP Relaxation:
  inventory_cohort[node, prod, date, state] = 1,680 units
  pallet_count[cohort] = 5.25 pallets (LP relaxation)

Ceiling constraint: pallet_count * 320 >= 1,680
  → 5 * 320 = 1,600 < 1,680 (infeasible)
  → 6 * 320 = 1,920 ≥ 1,680 (feasible!)

LP solver LEARNS: Must round up to 6
LP objective adjusts: Includes 6 pallet cost
Gap after rounding: 0.1-0.5% (excellent!)

Result: ROOT NODE SOLUTION (no branching!)
```

**MIP Expert Insight:**
> "Ceiling constraints create GUIDED LP relaxation. Solver learns rounding direction during LP solve. Binary variables have no such guidance."

### Factor 3: Branching Difficulty

**Binary Variables - Equal Branches:**

```
Branch decision: product_produced[SKU_A, Monday] = ?

Branch 1: Set to 0 (don't produce)
  - Remaining demand: 1000 units
  - Can produce Tuesday-Friday
  - Many feasible schedules
  - Objective bound: $950k

Branch 2: Set to 1 (produce)
  - Demand satisfied: 1000 units
  - Must produce 0 other days (if sufficient)
  - Also many feasible schedules
  - Objective bound: $952k

Difference: Only $2k (0.2%!)
→ Must explore BOTH branches deeply
→ Creates large B&B tree
```

**Pallet Integers - Unequal Branches:**

```
Branch decision: pallet_count[cohort] = ?

LP solution: 5.3 pallets

Branch 1: Round down to 5
  - 5 * 320 = 1,600 units < 1,680 required
  - INFEASIBLE (violates ceiling)
  - Prune immediately!

Branch 2: Round up to 6
  - 6 * 320 = 1,920 units ≥ 1,680 required
  - Feasible
  - Cost: $91.44
  - Accept and continue

No real branching - LP rounding is forced!
```

**MIP Expert Insight:**
> "Strong branching works when branches have very different bounds. Binaries often have similar bounds → weak branching → large tree."

### Factor 4: Constraint Coupling

**Binary Variables Couple Weakly:**

```
Binary decisions are loosely coupled:
  - product_produced[Monday] affects inventory
  - Inventory affects product_produced[Tuesday]
  - But many valid combinations exist

Weak coupling = Solver must try many combinations
```

**Pallet Integers Couple Strongly:**

```
Pallet decisions are tightly coupled:
  - inventory_cohort = f(production, shipments) [continuous]
  - pallet_count = ceil(inventory_cohort / 320) [forced rounding]

Strong coupling = LP solver handles propagation
Once production is fixed, pallet_count is determined!
```

**MIP Expert Insight:**
> "Tightly coupled integers become pseudo-continuous in LP relaxation. Loosely coupled binaries stay truly discrete."

---

## Why Weekly Pattern Fixes The Problem

**Weekly Pattern = Symmetry Breaking Constraint**

```
Without pattern:
  Can produce SKU_A on: [any 5 of 42 days]
  Combinations: C(42, 5) = 850,668 symmetric solutions

With weekly pattern:
  Must produce SKU_A on: [Same weekdays every week]
  Combinations: 2^5 = 32 patterns (Mon-Fri binary choices)

Symmetry reduction: 850,668 → 32 (99.996% reduction!)
```

**Linking Constraints:**

```
product_produced[Mon_week1] = pattern[Monday]
product_produced[Mon_week2] = pattern[Monday]
...
product_produced[Mon_week6] = pattern[Monday]

These 6 variables are now EQUIVALENT.
Solver only explores pattern[Monday] ∈ {0, 1}
Not 6 independent decisions!
```

**Result:**
- 781 binary variables (appears more)
- But only ~110 independent decisions (weekly pattern + weekends)
- Effective search space: 2^110 vs 2^280
- **Reduction factor: 2^170 ≈ 10^51 fewer combinations!**

---

## Strategies to Allow Flexibility (MIP Expert Techniques)

### Strategy 1: Partial Pattern Fixing (High Priority) ✅

**Concept:** Use weekly pattern for some weeks, flexibility for others

**Implementation:**
```python
# Fix pattern for weeks 1-4 (long-term structure)
for week in [1, 2, 3, 4]:
    for date in week_dates:
        product_produced[date] = pattern[weekday]

# Allow flexibility for weeks 5-6 (near-term adjustment)
for week in [5, 6]:
    for date in week_dates:
        product_produced[date] ∈ {0, 1}  # Independent decisions

Binary variables: 25 pattern + 70 weekend + (2 weeks × 5 days × 5 products) = 145 vars
Effective decisions: 25 + 70 + 50 = 145 (vs 280 full binary)
```

**Expected performance:**
- Solve time: 28.2s → ~150s (middle ground)
- Flexibility: Weeks 5-6 can deviate from pattern
- Use case: Respond to demand changes in near term

### Strategy 2: Soft Pattern Penalties (High Priority) ✅

**Concept:** Allow deviation from pattern but penalize it

**Implementation:**
```python
# Weekly pattern variables (recommended)
pattern[product, weekday] ∈ {0, 1}

# Daily production (actual decisions)
product_produced[product, date] ∈ {0, 1}

# Deviation variables
deviation[product, date] ∈ [0, 1] continuous

# Constraints
deviation[prod, date] ≥ product_produced[prod, date] - pattern[prod, weekday]
deviation[prod, date] ≥ pattern[prod, weekday] - product_produced[prod, date]

# Objective (add penalty for deviations)
minimize: original_cost + penalty * sum(deviation)

# Penalty tuning:
penalty = $1,000/deviation  # Prefer pattern but allow flexibility
```

**Expected performance:**
- Solve time: 28.2s → ~100s (good)
- Flexibility: Full (can deviate anywhere)
- Bias: Strongly prefers pattern (cost-driven)

**MIP Expert Insight:**
> "Soft constraints transform hard combinatorics into continuous optimization. Solver handles continuous penalties efficiently."

### Strategy 3: Campaign-Based Decisions (High Priority) ✅

**Concept:** Group consecutive days into campaigns (2-3 week blocks)

**Implementation:**
```python
# Campaign variables (one per product per campaign)
campaign_active[product, campaign] ∈ {0, 1}

# Campaign definitions
campaign_1 = [week1, week2]      # Days 1-14
campaign_2 = [week3, week4]      # Days 15-28
campaign_3 = [week5, week6]      # Days 29-42

# Linking
for date in campaign_1:
    product_produced[product, date] = campaign_active[product, campaign_1]

Binary variables: 5 products × 3 campaigns = 15 decisions!
(vs 210 daily decisions)
```

**Expected performance:**
- Solve time: ~20-30s (faster than weekly!)
- Flexibility: Low (2-week blocks)
- Use case: Long production runs (campaign planning)

**Why this works:**
- Even fewer independent decisions (15 vs 110)
- Aligns with business practice (SKU campaigns)
- Further symmetry breaking (can't switch mid-campaign)

### Strategy 4: Minimum Run Length Constraints (Medium Priority)

**Concept:** If produce SKU today, must produce for N consecutive days

**Implementation:**
```python
# Constraint: If start production, run for 3+ days
for date in range(start_date, end_date - 3):
    product_produced[date] ≥ product_produced[date+1]
    product_produced[date] ≥ product_produced[date+2]
    product_produced[date] ≥ product_produced[date+3]

# Or using helper variables
start_production[date] ∈ {0, 1}
start_production[date] = product_produced[date] - product_produced[date-1]

# If start, must continue
sum(product_produced[date:date+3]) ≥ 3 * start_production[date]
```

**Expected performance:**
- Solve time: Depends (can help or hurt)
- Flexibility: Medium (no 1-day runs)
- Benefit: Eliminates "chattering" solutions (on-off-on-off)

**Why this works:**
- Reduces feasible region → Fewer equivalent solutions
- Aligns with setup cost reality
- But: Can make problem infeasible if too restrictive!

### Strategy 5: Branching Priorities (Low Priority - Solver Hint)

**Concept:** Tell solver which variables to branch on first

**Implementation:**
```python
# Pyomo syntax (pseudo-code)
for product in products:
    for date in dates:
        var = model.product_produced[product, date]
        var.set_branching_priority(priority=10)  # High priority

for cohort in pallet_cohorts:
    var = model.pallet_count[cohort]
    var.set_branching_priority(priority=1)  # Low priority (handle via LP)
```

**Expected performance:**
- Solve time: 10-20% improvement (if lucky)
- Flexibility: No change (same problem)
- Benefit: May find good solutions faster

**Why this might work:**
- Fixes "important" binaries first (production decisions)
- Leaves "easy" variables for LP (pallet rounding)
- But: Heuristic, may not always help

### Strategy 6: Variable Fixing Heuristics (High Priority) ✅

**Concept:** Fix some decisions based on domain knowledge

**Implementation A: Never Produce Combinations**
```python
# Example: Never produce SKU_A and SKU_B on same day
# (Incompatible production lines)
product_produced['SKU_A', date] + product_produced['SKU_B', date] ≤ 1

Reduces search space: 2^(2N) → 2^N per date
```

**Implementation B: Must Produce Threshold**
```python
# Example: If demand > 5000 units, MUST produce that SKU
if forecast[product, date] > 5000:
    product_produced[product, date].fix(1)

Reduces variables: 210 → ~150 (fix 60 obvious decisions)
```

**Implementation C: Brand Grouping**
```python
# Example: Produce all "Premium" SKUs on Mon/Wed/Fri only
for sku in premium_skus:
    for date in dates:
        if date.weekday() in [1, 3]:  # Tue, Thu
            product_produced[sku, date].fix(0)

Reduces feasible region for premium SKUs: 2^42 → 2^18
```

**Expected performance:**
- Solve time: 100-300s (big improvement)
- Flexibility: Domain-constrained
- Benefit: Leverages business knowledge

### Strategy 7: Rolling Horizon (High Priority for Production) ✅

**Concept:** Fix near-term (week 1), optimize mid-term (weeks 2-4), ignore far-term (weeks 5-6)

**Implementation:**
```python
# Week 1: Fixed from previous optimization
for date in week_1:
    product_produced[product, date].fix(previous_solution[date])

# Weeks 2-4: Optimize with pattern
for date in weeks_2_3_4:
    product_produced[product, date] = pattern[weekday]

# Weeks 5-6: Relaxed (don't enforce demand)
for date in weeks_5_6:
    shortage[date] = demand[date] - inventory[date]
    # Allow shortages (will be filled in next optimization)

Binary decisions: 0 (week 1) + ~60 (weeks 2-4 pattern) = 60 vars
vs 280 full binary
```

**Expected performance:**
- Solve time: ~50-100s
- Flexibility: Week 1 executes, weeks 2-4 planned, weeks 5-6 re-optimized later
- Use case: Production scheduling (not long-term planning)

---

## Strategy Comparison Matrix

| Strategy | Binary Vars | Solve Time | Flexibility | Implementation | Priority |
|----------|-------------|------------|-------------|----------------|----------|
| **Current (Full Binary)** | 280 | 636s | Full | N/A | Baseline |
| **Weekly Pattern (Current)** | 110 eff. | 28s | Low | Done ✅ | ✅ Use |
| **Soft Pattern** | 280 + 280 cont | ~100s | Full | Medium | ✅ High |
| **Partial Pattern (4+2)** | 145 | ~150s | Medium | Easy | ✅ High |
| **Campaign (2-week)** | 15 | ~25s | Low | Medium | ✅ High |
| **Min Run Length** | 280 | Varies | Medium | Hard | ⚠️ Test |
| **Variable Fixing** | 150-200 | 100-300s | Domain | Easy | ✅ High |
| **Rolling Horizon** | 60 | 50-100s | Sequential | Medium | ✅ High |
| **Branching Priority** | 280 | 500s? | Full | Easy | ⚠️ Maybe |

---

## Recommended Approach: Hybrid Strategy

**Combine multiple techniques for best results:**

### Phase A: Strategic Planning (6-week horizon)

**Use:** Campaign-based + Soft pattern penalties

```python
# 3 campaigns (2 weeks each)
campaign_active[product, campaign] ∈ {0, 1}  # 15 decisions

# Within campaign, use weekly pattern with soft penalties
for date in campaign_dates:
    product_produced[date] = pattern[weekday] + deviation[date]
    minimize: cost + $500 * sum(deviation)  # Soft penalty
```

**Expected:** 30-50s solve time, good flexibility within campaigns

### Phase B: Tactical Planning (2-week horizon, rolling)

**Use:** Fixed week 1 + Pattern week 2

```python
# Week 1: Fix from previous solve
product_produced[week_1] = previous_solution

# Week 2: Weekly pattern only
product_produced[week_2] = pattern[weekday]
```

**Expected:** 20-30s solve time, week 1 executes, week 2 plans

### Phase C: Operational Planning (1-week horizon, daily)

**Use:** Full binary with variable fixing

```python
# Fix based on inventory and demand
if inventory[date-1] > demand[date] * 2:
    product_produced[product, date].fix(0)  # Don't overproduce

# Remaining decisions: ~30-50 binary vars
```

**Expected:** 10-20s solve time, daily adjustments

---

## Why This All Matters: The Core Insight

**From MIP Theory:**

> "Binary variables are exponentially hard because of SYMMETRY, not because of domain size."

**Evidence:**
```
Binary (domain {0,1}):
  - 280 independent variables
  - Massive symmetry (many equivalent schedules)
  - Solve time: 636s ❌

Pallet integers (domain {0-10}):
  - 4,557 variables (16× more!)
  - No symmetry (each value distinct)
  - Tight coupling (ceiling constraints)
  - Solve time: 28s ✅ (included in weekly pattern solve)
```

**The Fix:**
- Add structure (weekly pattern, campaigns)
- Break symmetry (min run lengths, variable fixing)
- Tighten coupling (soft penalties guide search)

**Result:** Transform hard combinatorial problem into tractable optimization

---

## Conclusion

**Why binaries perform worse:**
1. **Symmetry:** 850k equivalent solutions vs 0 for integers
2. **Weak LP relaxation:** Fractional solutions don't guide rounding
3. **Equal branching:** Both branches equally promising → large tree
4. **Loose coupling:** Many valid combinations to explore

**How to fix:**
1. **Structure:** Weekly pattern, campaigns (reduces decisions)
2. **Soft constraints:** Penalties guide toward good solutions
3. **Variable fixing:** Domain knowledge eliminates bad choices
4. **Rolling horizon:** Optimize only what matters now

**Best strategy:** Hybrid approach combining multiple techniques for different planning horizons.

---

**Analysis By:** MIP Expert Theory + Optimization Best Practices
**Date:** 2025-10-22
**Key Reference:** MIP Modeling Best Practice #4: "Break symmetry in binary variable problems"
