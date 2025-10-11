# Packaging Constraints Code Review & Integration Summary

## Executive Summary

**Status:** Packaging constraints are NOT currently implemented in the Pyomo optimization model.

**Current State:**
- ✅ Domain knowledge exists (`ProductionFeasibilityChecker`, `PackagingAnalysis`)
- ✅ Constants defined (UNITS_PER_CASE=10, CASES_PER_PALLET=32, etc.)
- ✅ Validation methods available for post-processing
- ❌ Optimization model uses continuous variables (no integer enforcement)
- ❌ No pallet space accounting in truck loading
- ❌ No case multiple constraints in production

**Required Action:** Implement integer programming constraints as detailed in `PACKAGING_CONSTRAINTS_IMPLEMENTATION.md`

---

## Code Review Findings

### 1. Model Structure (integrated_model.py)

#### ✅ Strengths
- Well-organized model with clear separation of concerns
- Extensive documentation and type hints
- Modular constraint structure (easy to add new constraints)
- Robust solution extraction with comprehensive data

#### ⚠️ Gaps for Packaging Constraints
- **Line 1273-1278:** Production variables are `NonNegativeReals` (should link to integer cases)
- **Line 1349-1356:** `truck_load` is continuous (no pallet space accounting)
- **No import of `NonNegativeIntegers`** from Pyomo (needed for integer variables)
- **No ceiling division constraints** for pallet calculations

#### 🔧 Required Changes

```python
# BEFORE (Line 36-45):
from pyomo.environ import (
    ConcreteModel,
    Var,
    Constraint,
    Objective,
    NonNegativeReals,
    Binary,
    minimize,
    value,
)

# AFTER:
from pyomo.environ import (
    ConcreteModel,
    Var,
    Constraint,
    Objective,
    NonNegativeReals,
    NonNegativeIntegers,  # ADD THIS
    Binary,
    minimize,
    value,
)
```

### 2. Solution Extraction (extract_solution method)

#### ✅ Strengths
- Comprehensive extraction of all decision variables
- Good separation of cost components
- Batch tracking support for traceability

#### ⚠️ Missing Packaging Data
- **Line 2650-2656:** Production extracted but no case validation
- **No extraction of integer variable values** (production_cases, pallets_loaded)
- **No packaging efficiency metrics** in solution dictionary

#### 🔧 Required Additions

Add after line 2656:

```python
# Extract production quantities
production_by_date_product: Dict[Tuple[Date, str], float] = {}
production_cases_by_date_product: Dict[Tuple[Date, str], int] = {}  # NEW

for d in model.dates:
    for p in model.products:
        qty = value(model.production[d, p])
        if qty > 1e-6:
            production_by_date_product[(d, p)] = qty

            # Validate case multiple (should be exact if constraints enforced)
            if qty % self.UNITS_PER_CASE != 0:
                warnings.warn(
                    f"Production {qty} on {d} for {p} is not a case multiple. "
                    f"Rounding to nearest case."
                )

            cases = int(round(qty / self.UNITS_PER_CASE))
            production_cases_by_date_product[(d, p)] = cases
```

### 3. Feasibility Validation (Production Module)

#### ✅ Excellent Domain Logic
- `ProductionFeasibilityChecker` has all packaging constants
- `PackagingAnalysis` dataclass provides rich diagnostics
- `check_packaging_constraints()` validates case multiples
- `analyze_packaging()` calculates efficiency metrics

#### 💡 Opportunity: Integrate with Optimization
- Currently used for heuristic planning only
- Should be used for **post-solve validation** of optimization results
- Can provide warnings for low pallet efficiency

#### 🔧 Recommended Integration

In `IntegratedProductionDistributionModel`, add validation method:

```python
def validate_packaging_constraints(self) -> Dict[str, Any]:
    """
    Validate solution against packaging constraints.

    Uses ProductionFeasibilityChecker logic for consistency.
    """
    from src.production.feasibility import ProductionFeasibilityChecker, PackagingAnalysis

    checker = ProductionFeasibilityChecker(
        self.manufacturing_site,
        self.labor_calendar
    )

    issues = []
    analyses = []

    for (date, product), qty in self.solution['production_by_date_product'].items():
        # Check case alignment
        result = checker.check_packaging_constraints(qty)
        if not result.is_feasible:
            issues.append(f"{date} {product}: {result.reason}")

        # Get detailed analysis
        analysis = checker.analyze_packaging(qty)
        if analysis.partial_pallet_warning:
            analyses.append(analysis)

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'partial_pallet_warnings': analyses
    }
```

### 4. UI Integration (Planning Page)

#### ✅ Good Foundation
- Tab-based organization (Heuristic, Optimization, Scenarios)
- Comprehensive result display with metrics
- Cost breakdown visualization

#### ⚠️ Missing Packaging Metrics
- **No pallet efficiency display** after optimization
- **No case/pallet breakdown** in production summary
- **No truck utilization percentage** (pallets used / 44 capacity)

#### 🔧 Recommended UI Components

Add to optimization results tab:

```python
# Packaging Efficiency Card
st.subheader("📦 Packaging Efficiency")

validation = model.validate_packaging_constraints()
metrics = validation['metrics']

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Cases",
        f"{metrics['total_cases']:,}",
        help="Production in 10-unit cases"
    )

with col2:
    st.metric(
        "Total Pallets",
        f"{metrics['total_pallets']:,}",
        delta=f"{metrics['partial_pallets']} partial",
        delta_color="inverse" if metrics['partial_pallets'] > 0 else "off"
    )

with col3:
    efficiency = metrics['pallet_efficiency']
    st.metric(
        "Pallet Efficiency",
        f"{efficiency:.1f}%",
        delta="Optimal" if efficiency > 95 else "Suboptimal",
        delta_color="normal" if efficiency > 95 else "inverse"
    )

with col4:
    # Average truck utilization
    avg_truck_util = (metrics['total_pallets'] / metrics['total_trucks'] / 44 * 100) if metrics['total_trucks'] > 0 else 0
    st.metric(
        "Avg Truck Utilization",
        f"{avg_truck_util:.1f}%",
        help="Average pallets per truck / 44 capacity"
    )

# Warnings for inefficient loads
if validation['warnings']:
    with st.expander("⚠️ Packaging Warnings", expanded=len(validation['warnings']) <= 3):
        for warning in validation['warnings']:
            st.warning(warning, icon="⚠️")
```

---

## Edge Cases & Potential Issues

### 1. **Rounding Errors in Continuous-to-Integer Conversion**

**Issue:** If production variable is continuous and linked to integer cases:
```python
model.production[d, p] == model.production_cases[d, p] * 10
```

With floating-point arithmetic, solver might return `production_cases = 149.9999` instead of `150`.

**Solution:** Use rounding with tolerance in extraction:
```python
cases = value(model.production_cases[d, p])
cases_int = int(round(cases))

# Validate rounding error is small
if abs(cases - cases_int) > 1e-3:
    warnings.warn(f"Large rounding error: {cases} → {cases_int}")

production_cases_by_date_product[(d, p)] = cases_int
```

### 2. **Infeasibility from Integer Constraints**

**Issue:** Adding integer constraints can make previously feasible problems infeasible.

**Example:** Demand = 9,995 units, but must produce in 10-unit multiples → must produce 10,000

**Solution 1:** Allow shortages (already implemented)
```python
model = IntegratedProductionDistributionModel(
    ...,
    allow_shortages=True  # Prevents infeasibility
)
```

**Solution 2:** Round up demand internally
```python
def _round_demand_to_cases(self):
    """Round all demand up to nearest case multiple."""
    for key, qty in self.demand.items():
        rounded = math.ceil(qty / self.UNITS_PER_CASE) * self.UNITS_PER_CASE
        if rounded != qty:
            self.demand[key] = rounded
            # Track rounding for reporting
```

### 3. **Partial Pallet Inefficiency**

**Issue:** Demand = 10,010 units → 1,001 cases → 32 pallets (31 full + 1 with 1 case)

Last pallet: 1 case / 32 cases = 3.1% utilization (wastes 96.9% of pallet space)

**Detection:**
```python
cases_on_last_pallet = cases % 32
if cases_on_last_pallet > 0 and cases_on_last_pallet < 5:  # Less than 5 cases
    efficiency = (cases_on_last_pallet / 32) * 100
    warnings.append(f"Very low pallet efficiency: {efficiency:.1f}% on last pallet")
```

**Optimization Strategy:** Add soft constraint to penalize partial pallets
```python
# Penalty for partial pallets
model.partial_pallet_penalty = Var(
    model.trucks,
    model.truck_destinations,
    model.dates,
    within=NonNegativeReals
)

# If pallets * 320 > units, then partial_pallet_penalty = pallets * 320 - units
def partial_pallet_penalty_rule(model, truck_idx, dest, date):
    total_units = sum(model.truck_load[truck_idx, dest, p, date] for p in model.products)
    pallet_space = model.pallets_loaded[truck_idx, dest, date] * 320
    return model.partial_pallet_penalty[truck_idx, dest, date] >= pallet_space - total_units

# Add to objective with small coefficient
partial_pallet_cost = 0.01  # Small penalty per wasted unit of space
obj_expr += partial_pallet_cost * sum(
    model.partial_pallet_penalty[t, d, dt]
    for t in model.trucks
    for d in model.truck_destinations
    for dt in model.dates
)
```

### 4. **Solver Performance Degradation**

**Issue:** Integer variables increase solve time significantly.

**Scale Analysis:**
- 204 days × 5 products = 1,020 `production_cases` integer variables
- 11 trucks × 10 destinations × 204 days = 22,440 `pallets_loaded` integer variables
- **Total: ~23,500 integer variables** (medium-scale MIP)

**Performance Expectations:**
- **LP (continuous):** 1-10 seconds
- **MIP (integer):** 30 seconds - 5 minutes
- **Large instances:** 5-30 minutes

**Mitigation Strategies:**

1. **Use efficient MIP solver:**
   ```python
   # CBC (open source, good for medium instances)
   solver_config = SolverConfig(solver_name='cbc', time_limit_seconds=300)

   # Gurobi (commercial, best performance)
   solver_config = SolverConfig(solver_name='gurobi', time_limit_seconds=60, mip_gap=0.01)
   ```

2. **Set optimality gap tolerance:**
   ```python
   # Accept 1% optimality gap (99% optimal solution)
   solver_config.mip_gap = 0.01  # Significant speedup
   ```

3. **Reduce variable count with aggregation:**
   ```python
   # Aggregate products if similar packaging
   # Instead of 5 product-specific variables, use 1 aggregate
   # (Only if products have identical packaging rules)
   ```

4. **Warm start from LP relaxation:**
   ```python
   # Solve LP first (fast), then use as initial solution for MIP
   model_lp = model.clone()  # Relax integer variables
   result_lp = solver.solve(model_lp)

   # Use LP solution as MIP start
   for d in model.dates:
       for p in model.products:
           lp_value = value(model_lp.production[d, p])
           model.production[d, p].set_value(lp_value)

   result_mip = solver.solve(model, warmstart=True)
   ```

### 5. **Inconsistent Demand Across Network Legs**

**Issue:** With leg-based routing, demand could be satisfied via multiple routes with different packaging.

**Example:**
- Route A: 6122 → 6104 → 6103 (demand: 9,995 units)
- Round up to 10,000 units at 6122
- Ship 10,000 to 6104
- 6104 → 6103: Only ship 9,995 needed

**Problem:** Mismatch between leg shipments (10,000 vs 9,995)

**Solution:** Enforce case multiples on **all legs**, not just production:
```python
# Case constraint on shipments (optional, may be too restrictive)
model.shipment_cases = Var(
    model.legs,
    model.products,
    model.dates,
    within=NonNegativeIntegers
)

def shipment_case_link_rule(model, origin, dest, p, d):
    return model.shipment_leg[(origin, dest), p, d] == model.shipment_cases[(origin, dest), p, d] * 10

# NOTE: This may be too restrictive. Consider allowing fractional shipments
# at intermediate legs (only enforce at production and final delivery)
```

### 6. **Multiple Products on Same Truck**

**Issue:** If 2 products loaded on same truck, pallet calculation must account for both.

**Example:**
- Product A: 6,400 units = 640 cases = 20 pallets
- Product B: 6,410 units = 641 cases = 21 pallets (20 full + 1 partial with 1 case)
- **Total: 41 pallets** (fits in 44-pallet truck)

**Current Implementation:** ✅ Correctly handles this
```python
# pallet_loading_rule sums across products
total_units = sum(model.truck_load[truck_idx, dest, p, date] for p in model.products)
return total_units <= model.pallets_loaded[truck_idx, dest, date] * 320
```

**Edge Case:** What if Product A + B = 12,800 + 1 case?
- 12,800 units = 1,280 cases = 40 pallets (full)
- +1 case = +1 pallet (partial)
- **Total: 41 pallets** ✅

### 7. **Zero Production Edge Case**

**Issue:** If `production[d, p] = 0`, what should `production_cases[d, p]` be?

**Answer:** 0 cases (handled automatically by linking constraint)
```python
# If production = 0, then production_cases must = 0
0 == production_cases[d, p] * 10
# → production_cases[d, p] = 0 ✓
```

**Potential Issue:** Solver might set `production_cases = 0.000001` due to numerical tolerance

**Solution:** Round to zero in extraction:
```python
cases = value(model.production_cases[d, p])
if cases < 0.5:  # Threshold for rounding to zero
    cases_int = 0
else:
    cases_int = int(round(cases))
```

---

## Testing Strategy

### Unit Tests (High Priority)

#### Test 1: Case Multiple Enforcement
```python
def test_production_case_multiples():
    """All production must be in 10-unit case multiples."""
    model = create_test_model()
    result = model.solve()

    assert result.is_optimal()

    for (date, product), qty in model.solution['production_by_date_product'].items():
        assert qty % 10 == 0, f"{date} {product}: {qty} not a case multiple"

    # Also check extracted cases
    for (date, product), cases in model.solution['production_cases_by_date_product'].items():
        assert isinstance(cases, int), f"Cases should be integer, got {type(cases)}"
```

#### Test 2: Pallet Space Accounting
```python
def test_partial_pallet_space():
    """Partial pallets must consume full pallet space on trucks."""
    model = create_test_model_with_partial_pallet_scenario()
    result = model.solve()

    # Scenario: 10,010 units = 1,001 cases
    # Should require 32 pallets (31 full + 1 partial with 1 case)

    pallet_loads = model.solution['pallet_loads_by_truck_dest_date']
    truck_loads = model.solution['truck_loads_by_truck_dest_product_date']

    for (truck_idx, dest, date), pallets in pallet_loads.items():
        total_units = sum(
            qty for (t, d, p, dt), qty in truck_loads.items()
            if t == truck_idx and d == dest and dt == date
        )

        cases = total_units / 10
        expected_pallets = math.ceil(cases / 32)

        assert pallets == expected_pallets, \
            f"Expected {expected_pallets} pallets for {cases} cases, got {pallets}"
```

#### Test 3: Truck Pallet Capacity
```python
def test_truck_pallet_capacity():
    """Trucks cannot exceed 44-pallet capacity."""
    model = create_test_model()
    result = model.solve()

    pallet_loads = model.solution['pallet_loads_by_truck_dest_date']

    # Aggregate by truck and date
    truck_totals = defaultdict(int)
    for (truck_idx, dest, date), pallets in pallet_loads.items():
        truck_totals[(truck_idx, date)] += pallets

    for (truck_idx, date), total_pallets in truck_totals.items():
        truck = model.truck_by_index[truck_idx]
        assert total_pallets <= truck.pallet_capacity, \
            f"Truck {truck_idx} on {date}: {total_pallets} > {truck.pallet_capacity}"
```

#### Test 4: Infeasibility Handling
```python
def test_infeasible_demand_with_shortages():
    """Model should handle infeasible demand gracefully with shortages."""
    # Create scenario with impossible demand (exceeds capacity)
    model = create_test_model_with_excess_demand(allow_shortages=True)
    result = model.solve()

    # Should be optimal with shortages
    assert result.is_optimal()
    assert model.solution['total_shortage_units'] > 0

    # Production should still be in case multiples
    for (date, product), qty in model.solution['production_by_date_product'].items():
        assert qty % 10 == 0
```

#### Test 5: Validation Method
```python
def test_packaging_validation():
    """Validation method should catch constraint violations."""
    model = create_test_model()
    result = model.solve()

    validation = model.validate_packaging_constraints()

    # Should be valid if constraints enforced
    assert validation['valid'], f"Validation failed: {validation['issues']}"

    # Check metrics
    assert validation['metrics']['total_cases'] > 0
    assert validation['metrics']['total_pallets'] > 0
    assert 0 <= validation['metrics']['pallet_efficiency'] <= 100
```

### Integration Tests (Medium Priority)

#### Test 6: End-to-End Workflow
```python
def test_e2e_packaging_workflow():
    """Test complete workflow from data load to packaging validation."""
    # Load real data
    parser = ExcelParser("data/examples/Gfree Forecast.xlsm")
    # ... load all data ...

    # Build and solve model with packaging constraints
    model = IntegratedProductionDistributionModel(
        ...,
        enforce_packaging_constraints=True
    )

    result = model.solve(time_limit_seconds=300)
    assert result.is_optimal() or result.is_feasible()

    # Validate packaging
    validation = model.validate_packaging_constraints()
    assert validation['valid']

    # Check pallet efficiency is reasonable
    assert validation['metrics']['pallet_efficiency'] > 80, "Low efficiency"
```

#### Test 7: Performance Benchmark
```python
def test_solve_time_with_packaging():
    """Benchmark solve time with packaging constraints vs without."""
    model_continuous = create_test_model(enforce_packaging=False)
    model_integer = create_test_model(enforce_packaging=True)

    import time

    start = time.time()
    result_cont = model_continuous.solve()
    time_continuous = time.time() - start

    start = time.time()
    result_int = model_integer.solve()
    time_integer = time.time() - start

    print(f"Continuous: {time_continuous:.2f}s")
    print(f"Integer: {time_integer:.2f}s")
    print(f"Slowdown: {time_integer / time_continuous:.1f}x")

    # Should be within reasonable bounds (e.g., 10x slowdown acceptable)
    assert time_integer < time_continuous * 10, "Excessive slowdown"
```

### Regression Tests (Low Priority)

#### Test 8: Backward Compatibility
```python
def test_backward_compatibility():
    """Existing code should work with new packaging constraints."""
    # Old code that expects continuous variables
    model = IntegratedProductionDistributionModel(...)
    result = model.solve()

    # Should still have expected solution keys
    assert 'production_by_date_product' in model.solution
    assert 'labor_cost_by_date' in model.solution

    # New keys should be added
    assert 'production_cases_by_date_product' in model.solution
    assert 'pallet_loads_by_truck_dest_date' in model.solution
```

---

## Recommended Implementation Order

### Phase 1: Core Constraints (High Priority) ✅
1. Import `NonNegativeIntegers` from Pyomo
2. Add packaging constants to model class
3. Create `production_cases` integer variable
4. Add `production_case_link_con` linking constraint
5. Test with simple case (1 product, 7 days)

### Phase 2: Pallet Constraints (High Priority) ✅
6. Create `pallets_loaded` integer variable (conditional on truck_schedules)
7. Add `pallet_loading_con` constraint
8. Add `pallet_minimum_con` constraint (ceiling division)
9. Add `truck_pallet_capacity_con` constraint
10. Test with truck loading scenario

### Phase 3: Solution Processing (Medium Priority) ✅
11. Update `extract_solution()` to extract integer variable values
12. Add rounding and validation for integer variables
13. Add packaging data to solution dictionary
14. Implement `validate_packaging_constraints()` method
15. Update `print_solution_summary()` with packaging metrics

### Phase 4: UI & Reporting (Medium Priority)
16. Add packaging metrics to Planning page UI
17. Create efficiency visualization components
18. Add warning display for partial pallets
19. Update cost breakdown to show packaging impact

### Phase 5: Testing & Validation (High Priority)
20. Write unit tests for all constraints
21. Create integration tests with real data
22. Performance benchmarking (LP vs MIP)
23. Edge case testing (infeasibility, rounding, etc.)

### Phase 6: Documentation (Low Priority)
24. Update model docstrings
25. Add packaging section to CLAUDE.md
26. Create user guide for packaging features
27. Document performance characteristics

---

## Key Decisions & Recommendations

### ✅ Implement Packaging Constraints
- **Rationale:** Core business requirement, prevents invalid solutions
- **Approach:** Integer programming with linking constraints
- **Trade-off:** Longer solve times (acceptable for medium-scale problems)

### ✅ Always Enforce (No Toggle Flag)
- **Rationale:** Packaging is fundamental constraint, not optional
- **Benefit:** Simpler code, fewer branches, guaranteed valid solutions
- **Alternative:** Could add flag for debugging, but enable by default

### ✅ Use Existing Feasibility Checker for Validation
- **Rationale:** Reuse proven domain logic, maintain consistency
- **Benefit:** Single source of truth for packaging rules
- **Implementation:** Call `ProductionFeasibilityChecker.analyze_packaging()` in validation

### ✅ Add Soft Penalty for Partial Pallets (Optional)
- **Rationale:** Encourages efficient packing when possible
- **Benefit:** Optimizer naturally prefers full pallets
- **Trade-off:** Adds complexity, may not be necessary if constraints sufficient

### ⚠️ Monitor Solver Performance
- **Action:** Benchmark solve times before/after
- **Threshold:** If >10x slowdown, consider optimizations
- **Mitigation:** Use MIP gap tolerance (1% gap = big speedup)

### ⚠️ Handle Infeasibility Gracefully
- **Strategy:** Enable `allow_shortages=True` by default with packaging constraints
- **Benefit:** Prevents hard failures, provides diagnostic information
- **User Experience:** Show shortage warnings instead of "Infeasible" error

---

## Potential Issues to Watch For

### 1. **Numerical Tolerance Issues**
- Integer variables may have small fractional values (0.9999 instead of 1.0)
- **Mitigation:** Round with tolerance in extraction, validate rounding error < 1e-3

### 2. **Solver Compatibility**
- Not all solvers support integer programming well
- **Test:** CBC (good), GLPK (okay), Gurobi (excellent)
- **Fallback:** If solver fails, try different solver or relax to LP with post-validation

### 3. **Memory Usage**
- Integer programming may use more memory (branch-and-bound tree)
- **Monitor:** Large instances (>30,000 integer variables)
- **Mitigation:** Reduce horizon length or aggregate products if memory becomes issue

### 4. **Optimality Gaps**
- MIP may not reach proven optimality in time limit
- **Current:** Time limit = 300s, may terminate with 5% gap
- **Acceptable:** 1-2% gap is usually fine for planning
- **Report:** Show gap percentage to user ("98% optimal")

---

## Files to Create/Modify Summary

### Create New Files:
1. `/home/sverzijl/planning_latest/tests/test_packaging_constraints.py` - Comprehensive test suite
2. `/home/sverzijl/planning_latest/docs/features/PACKAGING_CONSTRAINTS.md` - User documentation

### Modify Existing Files:
1. `/home/sverzijl/planning_latest/src/optimization/integrated_model.py` - Core implementation
2. `/home/sverzijl/planning_latest/ui/pages/2_Planning.py` - UI components
3. `/home/sverzijl/planning_latest/CLAUDE.md` - Project documentation
4. `/home/sverzijl/planning_latest/requirements.txt` - May need specific solver versions

### No Changes Needed:
1. `/home/sverzijl/planning_latest/src/production/feasibility.py` - Already excellent ✅
2. `/home/sverzijl/planning_latest/src/models/` - Data models are sufficient ✅
3. `/home/sverzijl/planning_latest/data/examples/MANUFACTURING_SCHEDULE.md` - Documentation complete ✅

---

## Next Steps for Pyomo Expert

The Pyomo expert should focus on:

1. **Review the mathematical formulation** in `PACKAGING_CONSTRAINTS_IMPLEMENTATION.md`
2. **Validate constraint correctness**:
   - Does `production_case_link_con` correctly enforce case multiples?
   - Does `pallet_minimum_con` correctly implement ceiling division?
   - Are there any edge cases in the formulation?

3. **Optimize solver performance**:
   - Are there tighter bounds that could be added?
   - Can constraints be reformulated for better LP relaxation?
   - Should we use indicator constraints instead of big-M?

4. **Review integer programming best practices**:
   - Is the variable domain correctly specified?
   - Are there symmetry-breaking constraints needed?
   - Should we add cutting planes or lazy constraints?

5. **Implement in the model**:
   - Add the constraints at the correct location in `build_model()`
   - Ensure constraint indexing is correct
   - Test with a small example first

Once implemented by the Pyomo expert, I (Python developer) will:
- Integrate solution extraction
- Add validation methods
- Create UI components
- Write comprehensive tests
- Update documentation

---

## Conclusion

The packaging constraints implementation is well-scoped and achievable. The codebase has excellent foundations (domain logic, constants, validation), and the required changes are localized to:
1. Integer variable creation
2. Linking constraints
3. Solution extraction
4. Validation & UI

**Estimated Effort:**
- Pyomo implementation: 4-6 hours
- Solution extraction & validation: 3-4 hours
- UI components: 2-3 hours
- Testing: 4-6 hours
- Documentation: 2-3 hours
- **Total: 15-22 hours** (2-3 days of focused work)

**Risk Level:** Low
- Well-understood problem
- Existing domain logic to reference
- Incremental testing possible
- Fallback strategies available (LP relaxation + validation)

**Success Criteria:**
✅ All production in 10-unit case multiples
✅ Partial pallets correctly consume full pallet space
✅ Trucks never exceed 44-pallet capacity
✅ Solution validates successfully
✅ Pallet efficiency metrics displayed in UI
✅ Solve time < 5 minutes for 200-day horizons
