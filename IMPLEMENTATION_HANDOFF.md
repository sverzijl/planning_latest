# Implementation Handoff: Start Tracking Changeover

**Date:** 2025-10-22
**Status:** Investigation COMPLETE ✅ | Ready for Implementation
**Estimated Implementation Time:** 12-18 hours

---

## What Was Accomplished

### Investigation Results ✅

**Problem Solved:**
- ✅ Identified why pattern warmstart failed (counting constraint + APPSI limitation)
- ✅ Found solution: Start tracking changeover formulation
- ✅ Tested 6 different approaches comprehensively
- ✅ Proved start tracking enables warmstart
- ✅ Discovered warmstart unnecessary for 4-week (pattern = optimal)

**Performance Improvements Proven:**
- Cost: $764K vs $779K baseline (-2%)
- Time: 6.5s vs 8s baseline (-19%)
- Warmstart: Works (Phase 2 matches Phase 1 exactly)

### Documentation Created ✅

**Core Documentation:**
1. `docs/lessons_learned/warmstart_investigation_2025_10.md` - APPSI warmstart behavior, complete lessons
2. `docs/optimization/changeover_formulations.md` - Counting vs start tracking comparison
3. `WARMSTART_INVESTIGATION_COMPLETE_SUMMARY.md` - Roadmap with code snippets
4. `FINAL_WARMSTART_RECOMMENDATION.md` - Comprehensive findings
5. `START_TRACKING_SUCCESS.md` - Proof that solution works

**Updated:**
- `CLAUDE.md` - Added start tracking to key design decisions

### Proof of Concept Code ✅

**Working test files:**
- `test_start_tracking_formulation.py` - Proves formulation works (pattern + flexible + warmstart)
- `test_pattern_vs_flexible_analysis.py` - Proves warmstart unnecessary for 4-week

**Results validated:**
- Start tracking solves correctly
- Better performance than counting
- Warmstart preserved (Phase 2 = Phase 1)
- Pattern and flexible give identical solutions for 4-week

---

## What Needs Implementation

### Phase 2: Core Model Changes (6-8 hours)

**File:** `src/optimization/unified_node_model.py`

**Changes required:**

1. **Replace counting constraint with start tracking** (~lines 691-696, 2640-2747)
   - Remove `num_products_produced` integer variable
   - Remove `num_products_counting_con` equality constraint
   - Remove `production_day_lower_con` and `production_day_upper_con`
   - Add `product_start` binary variables
   - Add start detection constraints: `y[i,t] ≥ b[i,t] - b[i,t-1]`
   - Update overhead calculation to use `sum(product_start)` instead of `num_products`

2. **Add changeover cost to objective** (~line 3800)
   - Add changeover cost term: `cost_per_start * sum(product_start)`
   - Make conditional on `changeover_cost_per_start > 0`

3. **Scale freshness penalty** (~line 3600)
   - Get shelf life per state: {frozen: 120, ambient: 17, thawed: 14}
   - Normalize: `age_ratio = age_days / shelf_life`
   - Use in penalty: `weight * age_ratio * demand`

**File:** `src/models/cost_structure.py`

4. **Add changeover cost parameter**
   ```python
   changeover_cost_per_start: float = 0.0
   ```

**File:** `src/parsers/cost_parser.py`

5. **Parse changeover cost from Excel**
   - Read `changeover_cost_per_start` row
   - Default to 0.0 if not present

**File:** `data/examples/Network_Config.xlsx`

6. **Add changeover cost row to CostParameters sheet**
   - Row: "changeover_cost_per_start"
   - Value: 50.0 (example)
   - Description: "Cost per product changeover/startup ($)"

### Phase 3: UI Updates (2-3 hours)

**File:** `ui/pages/2_Planning.py`

7. **Simplify solver configuration** (~lines 78-156)
   - Remove solver dropdown
   - Keep only APPSI HiGHS
   - Update text: "Using APPSI HiGHS (high-performance MIP solver)"

8. **Remove weekly warmstart section** (~lines 305-330)
   - Delete entire "Solve Strategy" section
   - Pattern warmstart now unnecessary for 4-week

9. **Add changeover statistics** (results display section)
   - Extract `sum(product_start > 0.5)`
   - Display: "Total Changeovers: X"
   - Display: "Changeover Cost: $Y" if cost > 0

### Phase 4: Testing (4-6 hours)

**Create new test files:**

10. **`tests/test_start_tracking_integration.py`**
    - Test start tracking variables exist
    - Test start detection logic (0→1 = 1, else = 0)
    - Test overhead calculation correct
    - Compare cost to baseline (should be ≤ $779K)

11. **`tests/test_scenario_validation.py`**
    - Test non-production day 4-hour minimum
    - Test overtime before weekend logic
    - Test pallet ceiling rounding
    - Test changeover cost in objective

12. **`tests/test_ui_workflow.py`**
    - Test UI loads without errors
    - Test optimization runs
    - Test results display

13. **Update `tests/test_integration_ui_workflow.py`**
    - Verify start tracking in result
    - Update expected variable counts
    - Add changeover assertions

14. **Run full test suite**
    ```bash
    pytest tests/ -v
    ```

### Phase 5: Cleanup (1-2 hours)

15. **Archive investigation files**
    ```bash
    mkdir -p archive/warmstart_investigation_2025_10
    mv test_approach*.py archive/warmstart_investigation_2025_10/
    mv diagnostic_*.py archive/warmstart_investigation_2025_10/
    mv *_output.txt archive/warmstart_investigation_2025_10/
    # Move ~30 test files
    ```

16. **Consolidate markdown docs**
    ```bash
    mv WARMSTART_*.md archive/warmstart_investigation_2025_10/
    mv MIP_*.md archive/warmstart_investigation_2025_10/
    mv DIAGNOSTIC_*.md archive/warmstart_investigation_2025_10/
    # Keep only summary in root, move rest to docs/ or archive
    ```

### Phase 6: GitHub (1 hour)

17. **Commit changes**
    - Commit 1: Core model (start tracking)
    - Commit 2: Changeover cost + freshness scaling
    - Commit 3: UI simplification
    - Commit 4: Tests
    - Commit 5: Documentation and cleanup

---

## Code Snippets (Ready to Use)

### Start Tracking Variable Declaration

```python
# In build_model(), replace num_products_produced with:

model.product_start = Var(
    product_produced_index,
    within=Binary,
    doc="Binary: 1 if product starts (changeover) in this period"
)

print(f"  Start tracking: {len(product_produced_index):,} start indicators (binary)")
```

### Start Detection Constraints

```python
# In _add_changeover_tracking_constraints(), replace counting section with:

model.start_detection_con = ConstraintList()

for node_id in self.manufacturing_nodes:
    for product in model.products:
        # Get dates for this node in order
        relevant_dates = sorted([d for d in model.dates])

        prev_date = None
        for date in relevant_dates:
            if (node_id, product, date) not in model.product_produced:
                continue

            if prev_date is None or prev_date not in model.dates:
                # First period - start if producing (assume b[i,0] = 0)
                model.start_detection_con.add(
                    model.product_start[node_id, product, date] >=
                    model.product_produced[node_id, product, date]
                )
            else:
                # Detect 0→1 transition: y[t] ≥ b[t] - b[t-1]
                model.start_detection_con.add(
                    model.product_start[node_id, product, date] >=
                    model.product_produced[node_id, product, date] -
                    model.product_produced[node_id, product, prev_date]
                )

            prev_date = date

print(f"  Start detection: {len(model.start_detection_con)} constraints")
```

### Production Day Linking (Simplified)

```python
# Replace production_day_lower_con and production_day_upper_con with:

def production_day_linking_rule(model, node_id, date):
    """Link production_day to any product being produced."""
    # production_day = 1 if any product runs, 0 otherwise
    # Use: production_day >= product_produced[i] for any i
    #      production_day <= sum(product_produced[i]) for all i

    # Upper bound: if no products, production_day must be 0
    return model.production_day[node_id, date] <= sum(
        model.product_produced[node_id, prod, date]
        for prod in model.products
        if (node_id, prod, date) in model.product_produced
    )

model.production_day_linking_con = Constraint(
    production_day_index,
    rule=production_day_linking_rule
)

# Lower bound handled by production linking (if production > 0, product_produced = 1)
```

### Updated Overhead Calculation

```python
# In production_capacity_rule and labor_hours_linking_rule:

# OLD:
overhead_time = (
    (startup_hours + shutdown_hours - changeover_hours) * model.production_day[node_id, date] +
    changeover_hours * model.num_products_produced[node_id, date]
)

# NEW:
num_starts = sum(
    model.product_start[node_id, prod, date]
    for prod in model.products
    if (node_id, prod, date) in model.product_start
)

overhead_time = (
    (startup_hours + shutdown_hours) * model.production_day[node_id, date] +
    changeover_hours * num_starts
)
```

### Changeover Cost in Objective

```python
# In _create_objective(), add after other cost components:

# Changeover cost
changeover_cost = 0
if hasattr(model, 'product_start'):
    if self.cost_structure.changeover_cost_per_start > 0:
        changeover_cost = self.cost_structure.changeover_cost_per_start * sum(
            model.product_start[idx] for idx in model.product_start
        )

# Update objective
model.obj = Objective(
    expr=total_labor_cost + total_production_cost + total_transport_cost +
         total_holding_cost + total_shortage_penalty + total_staleness_penalty +
         changeover_cost,
    sense=minimize
)
```

### Scaled Freshness Penalty

```python
# In staleness penalty calculation:

SHELF_LIFE_DAYS = {
    'frozen': 120,
    'ambient': 17,
    'thawed': 14
}

staleness_penalty_expr = 0
for cohort in demand_cohort_indices:
    node_id, product, prod_date, demand_date, state = cohort
    age_days = (demand_date - prod_date).days
    shelf_life = SHELF_LIFE_DAYS.get(state, 17)

    # Normalize age by shelf life (0-1 scale)
    age_ratio = min(age_days / shelf_life, 1.0)

    staleness_penalty_expr += (
        self.cost_structure.freshness_incentive_weight *
        age_ratio *
        model.demand_from_cohort[cohort]
    )
```

---

## Success Criteria

Before considering implementation complete:

- [ ] All tests pass (including `test_integration_ui_workflow.py`)
- [ ] 4-week solve time < 30s
- [ ] Solution cost ≤ $779K (baseline)
- [ ] UI loads without errors
- [ ] Changeover statistics displayed
- [ ] No regressions in solution quality
- [ ] Documentation complete and organized
- [ ] Cleanup complete (<20 files in root directory)

---

## Files to Keep in Root

After cleanup, root should only have:
- `test_start_tracking_formulation.py` - Reference implementation
- `test_pattern_vs_flexible_analysis.py` - Analysis tool
- `WARMSTART_INVESTIGATION_COMPLETE_SUMMARY.md` - Quick reference
- `IMPLEMENTATION_HANDOFF.md` - This file

Everything else moves to `archive/` or `docs/`.

---

## Next Session Checklist

When starting implementation:

1. Read `IMPLEMENTATION_HANDOFF.md` (this file)
2. Read code snippets section
3. Start with `src/optimization/unified_node_model.py`
4. Work through phases 2-6 systematically
5. Run tests frequently
6. Commit incrementally

**All preparation is complete. Implementation can begin immediately.**

---

## Contact Points for Implementation

**Key files to modify:**
- `src/optimization/unified_node_model.py` (primary changes)
- `src/models/cost_structure.py` (1 field addition)
- `src/parsers/cost_parser.py` (parse 1 new parameter)
- `ui/pages/2_Planning.py` (simplification + display)
- `data/examples/Network_Config.xlsx` (1 row addition)

**Key tests to create:**
- `tests/test_start_tracking_integration.py` (new)
- `tests/test_scenario_validation.py` (new)
- `tests/test_ui_workflow.py` (new)

**Key cleanup tasks:**
- Archive ~30 test files from investigation
- Consolidate ~20 markdown documents
- Simplify root directory

---

**Ready for implementation in fresh session.**
