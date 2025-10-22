# Hybrid Flexible-Pattern Strategy Analysis

**Date:** 2025-10-22
**Strategy:** First 2 weeks completely flexible, weeks 3-6 with weekly pattern
**Status:** Theoretical analysis with performance prediction

---

## Executive Summary

**Strategy Configuration:**
- **Weeks 1-2:** Full binary flexibility (no pattern constraints)
- **Weeks 3-6:** Weekly pattern constraints (forced repetition)

**Expected Performance:** ~100-300s (3-10× slower than full pattern, but 2-6× faster than no pattern)

**Business Value:** High - provides operational flexibility where it matters most (near-term) while maintaining tractability

**Recommendation:** ✅ **HIGHLY RECOMMENDED** for 6-week planning horizon

---

## Strategy Design

### Configuration Details

**Horizon:** 6 weeks (42 days, typically ~30 production days Mon-Fri)

**Binary Variables:**

**Weeks 1-2 (Flexible):**
- 5 products × ~10 production days = **50 independent binary variables**
- No pattern constraints
- Full flexibility to respond to:
  - Urgent demand changes
  - Production issues
  - Inventory corrections
  - Operational constraints

**Weeks 3-6 (Pattern):**
- 5 products × 5 weekday patterns = **25 pattern binary variables**
- Weekly repetition enforced: Mon week 3 = Mon week 4 = Mon week 5 = Mon week 6
- Long-term consistency with limited flexibility need

**Total Binary Decisions:** 50 (flexible) + 25 (pattern) = **75 binary decisions**

### Comparison to Other Approaches

| Strategy | Binary Decisions | Search Space | Expected Time | Flexibility |
|----------|------------------|--------------|---------------|-------------|
| **Full pattern (baseline)** | 25 | 2^25 ≈ 3.4×10^7 | 28s | 0% (rigid) |
| **Hybrid (proposed)** | 75 | 2^75 ≈ 3.8×10^22 | **100-300s** | **100% weeks 1-2, 0% weeks 3-6** |
| **No pattern** | 280 | 2^280 ≈ 10^84 | 636s | 100% (full) |

**Key observation:** Hybrid is 10^15 times more complex than full pattern, but 10^62 times simpler than no pattern.

---

## Performance Analysis

### MIP Complexity Assessment

#### Search Space Reduction

**Full flexibility (no pattern):**
```
6 weeks × 5 weekdays × 5 products = 150 production decisions
BUT: 280 independent binary variables due to weeks
Search space: 2^280 ≈ 10^84 combinations
```

**Hybrid approach:**
```
Weeks 1-2: 2 weeks × 5 weekdays × 5 products = 50 binaries
Weeks 3-6: 4 weeks × 5 patterns = 20 pattern-linked binaries
          + 5 pattern definitions = 25 pattern binaries
Search space: 2^50 × 2^25 = 2^75 ≈ 3.8×10^22 combinations
```

**Reduction from no pattern:** 2^280 / 2^75 = 2^205 ≈ 10^62 times fewer combinations!

#### Why This Works

**Key insight:** Weeks 3-6 pattern creates "backbone" structure that guides search

1. **Pattern weeks constrain solution space:**
   - Once week 3 Monday pattern decided → Weeks 4-6 Monday determined
   - Reduces temporal symmetry by 75% (4 weeks → 1 pattern)
   - Creates "anchor points" for optimization

2. **Flexible weeks have implicit constraints:**
   - Must satisfy near-term demand (less flexibility than it appears)
   - Must respect inventory continuity with weeks 3-6
   - Labor capacity limits reduce feasible combinations

3. **Solver can use pattern as warmstart:**
   - Solve weeks 3-6 pattern first (fast, ~20s)
   - Use that structure to guide weeks 1-2 decisions
   - Progressive refinement strategy

### Performance Prediction

**Method:** Extrapolate from diagnostic results using MIP theory

**Data points:**
- Full pattern (2^25): 28.2s
- No pattern (2^280): 636s
- Hybrid (2^75): ?

**MIP scaling relationship:**
```
Time ≈ Base_Time × (Binaries / Base_Binaries)^α

Where α = empirical scaling factor
From data: 636 / 28.2 = 22.5× for 280 / 25 = 11.2× binary increase
α ≈ log(22.5) / log(11.2) ≈ 1.3

Predicted time for hybrid:
Time ≈ 28.2 × (75 / 25)^1.3
     ≈ 28.2 × 3^1.3
     ≈ 28.2 × 4.2
     ≈ 118s
```

**Confidence intervals:**
- **Optimistic (α=1.0):** 28.2 × 3 = 85s
- **Expected (α=1.3):** 28.2 × 4.2 = 118s
- **Conservative (α=1.5):** 28.2 × 5.2 = 147s
- **Pessimistic (α=2.0):** 28.2 × 9 = 254s

**Most likely range:** 100-150s (3-5× slower than full pattern)

**Why not worse:**
- 50 flexible binaries partially constrained by demand/capacity
- Pattern in weeks 3-6 provides search guidance
- Solver can exploit temporal structure (early decisions affect later ones)

---

## Implementation

### Pyomo Model Construction

```python
def build_hybrid_flexible_pattern_model(
    model_obj,
    products,
    dates,
    weekday_dates,
    manufacturing_nodes,
    flexible_weeks=2
):
    """Build model with flexible near-term + pattern long-term.

    Args:
        model_obj: UnifiedNodeModel instance
        products: List of product IDs
        dates: List of all dates in horizon
        weekday_dates: Dict mapping weekday index → list of dates
        manufacturing_nodes: List of manufacturing node IDs
        flexible_weeks: Number of weeks to leave flexible (default: 2)
    """
    # Build base model
    model = model_obj.build_model()

    # Determine flexible vs pattern dates
    start_date = min(dates)
    flexible_end_date = start_date + timedelta(days=flexible_weeks * 7 - 1)

    flexible_dates = [d for d in dates if d <= flexible_end_date]
    pattern_dates = [d for d in dates if d > flexible_end_date]

    print(f"Flexible dates (weeks 1-{flexible_weeks}): {len(flexible_dates)} days")
    print(f"Pattern dates (weeks {flexible_weeks+1}+): {len(pattern_dates)} days")

    # Create pattern variables for long-term weeks ONLY
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = Var(
        pattern_index,
        within=Binary,
        doc="Weekly production pattern for weeks 3+"
    )

    # Add linking constraints ONLY for pattern dates
    model.weekly_pattern_linking = ConstraintList()

    for node_id in manufacturing_nodes:
        for product in products:
            for weekday_idx in range(5):
                # Only link dates in pattern weeks (weeks 3-6)
                pattern_week_dates = [
                    d for d in weekday_dates[weekday_idx]
                    if d in pattern_dates
                ]

                for date_val in pattern_week_dates:
                    if (node_id, product, date_val) in model.product_produced:
                        # Link to pattern
                        model.weekly_pattern_linking.add(
                            model.product_produced[node_id, product, date_val] ==
                            model.product_weekday_pattern[product, weekday_idx]
                        )

    # Deactivate conflicting constraints (CRITICAL!)
    # Only for pattern dates (flexible dates keep changeover tracking)
    if hasattr(model, 'num_products_counting_con'):
        for node_id, date_val in model.manufacturing_node_date_set:
            if date_val in pattern_dates:
                if (node_id, date_val) in model.num_products_counting_con:
                    model.num_products_counting_con[node_id, date_val].deactivate()

    print(f"\nHybrid model configuration:")
    print(f"  Flexible binary variables (weeks 1-{flexible_weeks}): ~{len(flexible_dates) * len(products)}")
    print(f"  Pattern binary variables (weeks {flexible_weeks+1}+): {len(pattern_index)}")
    print(f"  Total binary decisions: ~{len(flexible_dates) * len(products) + len(pattern_index)}")

    return model
```

### Usage Example

```python
# Build hybrid model
model_obj = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    # ... other params ...
    start_date=date(2025, 10, 20),
    end_date=date(2025, 11, 30),  # 6 weeks
)

# Build with 2-week flexible + 4-week pattern
model = build_hybrid_flexible_pattern_model(
    model_obj=model_obj,
    products=products,
    dates=dates,
    weekday_dates=weekday_dates,
    manufacturing_nodes=manufacturing_nodes,
    flexible_weeks=2  # First 2 weeks fully flexible
)

# Solve
solver = appsi.solvers.Highs()
solver.config.time_limit = 600  # 10 minutes
solver.config.mip_gap = 0.03   # 3%
result = solver.solve(model)
```

---

## Business Value Assessment

### Flexibility Where It Matters

**Weeks 1-2 (Flexible):**

**Business scenarios enabled:**
1. **Demand surges:** Respond to unexpected orders
2. **Production issues:** Adjust for equipment failures or quality problems
3. **Inventory corrections:** Fix discrepancies or use up aging stock
4. **Changeover optimization:** Find truly optimal SKU sequence for first 2 weeks
5. **Campaign starts:** Launch new production campaigns with custom timing

**Value:** High - operational decisions have immediate impact

**Weeks 3-6 (Pattern):**

**Business rationale for pattern:**
1. **Long-term forecast uncertainty:** Less value in optimizing distant weeks
2. **Planning stability:** Consistent pattern easier for workforce planning
3. **Procurement:** Repeating pattern simplifies ingredient ordering
4. **Computational tractability:** Pattern enables solver to find good solution

**Value:** Medium - consistency and stability valuable, flexibility less critical

### Cost-Benefit Analysis

**Flexibility gain:**
- Weeks 1-2: 100% flexible (10 production days)
- Weeks 3-6: 0% flexible but likely "close enough" (20 production days)
- **Overall: 33% of horizon fully flexible, 67% pattern-constrained**

**Performance cost:**
- Expected solve time: 100-150s (vs 28s full pattern)
- **Slowdown: 3-5× (acceptable for planning context)**

**Trade-off analysis:**

| Metric | Full Pattern | Hybrid | No Pattern |
|--------|--------------|--------|------------|
| Solve time | 28s ✓ | 100-150s ✓ | 636s ✗ |
| Week 1-2 flexibility | 0% ✗ | 100% ✓ | 100% ✓ |
| Week 3-6 flexibility | 0% ✗ | 0% ✗ | 100% ✓ |
| Business value | Low | **High** | Very High |
| Computational feasibility | ✓ | ✓ | ✗ |

**Winner:** Hybrid approach (best balance of flexibility and performance)

---

## Sensitivity Analysis

### Variable Configurations

**Question:** How does flexible window size affect performance?

| Flexible Weeks | Binary Decisions | Search Space | Predicted Time | Flexibility |
|----------------|------------------|--------------|----------------|-------------|
| 0 weeks (full pattern) | 25 | 2^25 | 28s | 0% |
| **1 week** | **50** | **2^50** | **50-80s** | **17%** |
| **2 weeks (proposed)** | **75** | **2^75** | **100-150s** | **33%** |
| **3 weeks** | **100** | **2^100** | **180-300s** | **50%** |
| 4 weeks | 125 | 2^125 | 300-500s | 67% |
| 6 weeks (no pattern) | 280 | 2^280 | 636s | 100% |

**Sweet spot:** 1-2 weeks flexible provides good flexibility-performance balance

### Horizon Length Sensitivity

**For 4-week horizon (20 production days):**
- 1 week flexible: 25 flexible + 15 pattern = 40 binaries → ~40-60s
- 2 weeks flexible: 50 flexible + 0 pattern = 50 binaries → ~60-100s
- **Observation:** Full flexibility becomes feasible for 4-week horizon!

**For 8-week horizon (40 production days):**
- 2 weeks flexible: 50 flexible + 40 pattern = 65 binaries → ~80-120s
- 3 weeks flexible: 75 flexible + 40 pattern = 90 binaries → ~150-250s
- **Observation:** Hybrid essential for 8+ week horizons

### Solver Behavior Prediction

**Expected solver progression:**

**Phase 1 (0-30s):** Find initial feasible solution
- Pattern weeks (3-6) solved quickly using LP relaxation
- Flexible weeks (1-2) use pattern as heuristic starting point
- Likely achieves 5-10% gap

**Phase 2 (30-100s):** Improve flexible weeks
- Pattern weeks remain fixed (already optimal in their constrained space)
- Solver focuses on weeks 1-2 optimization
- Gap reduces to 3-5%

**Phase 3 (100-150s):** Final refinement
- Fine-tune weeks 1-2 decisions
- Achieve <3% gap (target)
- Return best solution found

---

## Comparison to Other Strategies

### vs Campaign-Based (2-week blocks)

**Campaign approach:**
- 3 campaigns × 5 products = 15 binary decisions
- Faster: ~25-35s
- Less flexible: Can only change every 2 weeks

**Hybrid approach:**
- 75 binary decisions
- Slower: ~100-150s
- More flexible: Daily decisions in weeks 1-2

**Winner:** Depends on changeover cost
- High changeover cost → Campaign (minimize changes)
- Low changeover cost → Hybrid (maximize flexibility)

### vs Soft Penalties

**Soft penalties:**
- ~140 deviation variables + penalty in objective
- Expected: ~60-120s (if implemented correctly)
- 100% flexibility with cost trade-off

**Hybrid approach:**
- No deviation variables
- Expected: ~100-150s
- Partial flexibility (33% fully flexible)

**Winner:** Depends on planning context
- Tactical (2-4 weeks) → Soft penalties (full flexibility)
- Strategic (6+ weeks) → Hybrid (computational feasibility)

### vs Rolling Horizon

**Rolling horizon:**
- Weekly replanning: Fix week 1, optimize weeks 2-4, relax weeks 5-6
- Per-cycle: ~50-100s
- 100% flexibility through sequential optimization

**Hybrid approach:**
- Single optimization run
- One-time: ~100-150s
- Partial flexibility (weeks 1-2)

**Winner:** Depends on operational cadence
- Weekly replanning → Rolling horizon (always fresh week 1)
- Bi-weekly/monthly planning → Hybrid (stable long-term plan)

---

## Recommended Use Cases

### Ideal Scenarios for Hybrid Approach

1. **6-8 week planning horizon**
   - Too long for full flexibility (636s timeout risk)
   - Pattern weeks provide structure without excessive rigidity

2. **High demand variability in near-term**
   - Weeks 1-2 flexibility handles forecast volatility
   - Weeks 3-6 pattern acceptable (low forecast confidence anyway)

3. **Monthly planning cycle**
   - Plan once per month for 6 weeks ahead
   - 2-minute solve time acceptable for monthly cadence
   - Weeks 1-2 flexibility enables responsive operations

4. **Moderate changeover costs**
   - High enough to avoid daily changes (campaign better)
   - Low enough to benefit from daily optimization (not just campaign blocks)

5. **Stable long-term demand patterns**
   - Weeks 3-6 demand patterns known (seasonal, contractual)
   - Weekly repetition in weeks 3-6 matches business reality

### When to Use Alternatives

**Use full pattern instead (25 binaries, ~28s):**
- Planning horizon ≤ 4 weeks
- Need fast solve times (<1 minute)
- Demand patterns very stable

**Use campaign-based instead (15 binaries, ~25-35s):**
- High changeover costs (minimize SKU switches)
- Workforce prefers 2-week production blocks
- Simplicity valued over fine-grained optimization

**Use soft penalties instead (~60-120s):**
- Need full flexibility across all weeks
- Willing to pay computational cost
- Have good "suggested" pattern to deviate from

**Use rolling horizon instead (50-100s per cycle):**
- Weekly replanning cadence
- Always need fresh near-term optimization
- Can afford sequential optimization cycles

---

## Implementation Roadmap

### Phase 1: Prototype and Validate (1-2 weeks)

**Tasks:**
1. Implement `build_hybrid_flexible_pattern_model()` function
2. Test on 6-week horizon with real data
3. Measure actual solve time (validate 100-150s prediction)
4. Compare solution cost to full pattern baseline

**Success criteria:**
- Solve time < 5 minutes (300s)
- Solution quality within 5% of full pattern cost
- Weeks 1-2 show different decisions than pattern would enforce

### Phase 2: Production Integration (2-3 weeks)

**Tasks:**
1. Add UI configuration option (flexible_weeks parameter)
2. Integrate with existing warmstart workflow
3. Add progress monitoring (report gap at 30s, 60s, 90s intervals)
4. Create result visualization comparing flexible vs pattern weeks

**Success criteria:**
- Planner can select 1, 2, or 3 flexible weeks
- Solver progress visible during optimization
- Results clearly show which weeks are flexible vs constrained

### Phase 3: Business Validation (2-4 weeks)

**Tasks:**
1. Run parallel with current planning process
2. Collect planner feedback on flexibility value
3. Measure cost savings from flexible weeks 1-2
4. Tune flexible_weeks parameter based on business value

**Success criteria:**
- Planners prefer hybrid results over full pattern
- Measurable cost reduction (e.g., better inventory utilization)
- Acceptable solve time for planning cadence

---

## Conclusion

**Strategy:** 2 weeks flexible + 4 weeks pattern

**Expected Performance:** 100-150s (3-5× slower than full pattern, but 4-6× faster than no pattern)

**Business Value:** High
- 33% of horizon fully flexible (where it matters most)
- 67% pattern-constrained (acceptable for long-term)
- Computational tractability maintained

**Recommendation:** ✅ **STRONGLY RECOMMENDED**

**Why this works:**
1. **Practical flexibility:** Near-term decisions most valuable to optimize
2. **Computational feasibility:** 75 binary decisions manageable for modern solvers
3. **Search space reduction:** 2^75 is middle ground between 2^25 and 2^280
4. **Business alignment:** Long-term pattern matches planning reality

**Implementation priority:** High
- Simple to implement (minor modification of weekly pattern approach)
- High business value (operational flexibility)
- Acceptable performance (2-minute solve time)

**Next steps:**
1. Implement and test on real 6-week scenario
2. Validate 100-150s performance prediction
3. Collect business feedback on flexibility value
4. Deploy as primary 6-week planning approach

---

**Analysis Date:** 2025-10-22
**Confidence:** High (based on MIP scaling theory + diagnostic empirical data)
**Status:** Recommended for implementation and testing
