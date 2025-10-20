# CBC Warmstart Mechanism Design

**Status:** PENDING EXPERT INPUT
**Assigned To:** pyomo-modeling-expert
**Priority:** HIGH
**Last Updated:** 2025-10-19

---

## Objective

Design the technical mechanism for providing warmstart solutions to CBC solver via Pyomo.

---

## Requirements

### Functional Requirements
1. **Set initial values** for decision variables before solve
2. **CBC compatibility** with Pyomo 6.x interface
3. **Graceful fallback** if warmstart fails
4. **No breaking changes** to existing code

### Performance Requirements
1. **Target speedup:** 20-40% reduction in solve time
2. **Current baseline:** >300s for 4-week horizon (timeout)
3. **Target solve time:** <120s for 4-week horizon
4. **Warmstart overhead:** <5s

### Quality Requirements
1. **Valid initial solution:** Warmstart must be feasible
2. **Complete coverage:** All key decision variables initialized
3. **Type safety:** Correct variable types (continuous, integer, binary)
4. **Error handling:** Robust failure recovery

---

## Technical Questions for Expert

### Q1: Pyomo API for Warmstart
**Question:** What is the correct Pyomo API for setting initial variable values for CBC solver?

**Options:**
- A. `variable.value = initial_value` before solve
- B. `variable.set_value(initial_value)` before solve
- C. Pass warmstart dict to `solver.solve(warmstart=dict)`
- D. Use `model.load_solution()` with custom solution object

**Required Information:**
- API method signature
- Timing (before/during/after model build)
- Example code snippet
- CBC-specific considerations

### Q2: Variable Coverage
**Question:** Which variables must be initialized for effective warmstart?

**Decision Variables in UnifiedNodeModel:**
- `production[node, date, product]` - Production quantities (continuous)
- `product_produced[node, product, date]` - Binary production indicators
- `num_products_produced[node, date]` - Integer changeover count
- `inventory_cohort[node, product, prod_date, curr_date, state]` - Inventory by batch
- `shipment_cohort[route, product, prod_date, delivery_date, state]` - Shipments by batch
- `labor_hours_used[node, date]` - Labor hours (continuous)
- `uses_overtime[node, date]` - Overtime binary indicator
- Others: `pallet_count`, `truck_load`, etc.

**Required Information:**
- Which variables are critical for CBC warmstart?
- Can we initialize subset (e.g., production only)?
- What happens to uninitialized variables?

### Q3: Feasibility Requirements
**Question:** Must the warmstart solution satisfy all constraints?

**Constraint Categories:**
- Production capacity (must satisfy)
- Inventory balance (must satisfy)
- Demand satisfaction (soft constraint - shortage penalty)
- Shelf life (configurable enforcement)
- Truck capacity (must satisfy)

**Required Information:**
- Can warmstart violate soft constraints?
- Does CBC require strict feasibility?
- How does CBC handle infeasible warmstart?

### Q4: Error Handling
**Question:** How should code handle warmstart failures?

**Failure Scenarios:**
- Invalid variable reference (wrong index)
- Type mismatch (float vs integer)
- Infeasible initial solution
- CBC rejects warmstart

**Required Information:**
- How to detect warmstart failure?
- Should solve continue without warmstart?
- Error messages/logging strategy

### Q5: Performance Validation
**Question:** How to measure warmstart effectiveness?

**Metrics:**
- Solve time reduction (%)
- Initial gap vs final gap
- Number of branch-and-bound nodes
- Presolve impact

**Required Information:**
- Which Pyomo/CBC metrics indicate warmstart success?
- How to extract warmstart utilization from solver output?
- Diagnostic logging recommendations

---

## Expected Deliverables

### From pyomo-modeling-expert:

1. **API Specification**
   - Method signature
   - Code example (5-10 lines)
   - CBC-specific options

2. **Variable Coverage Guidance**
   - Priority ranking of variables
   - Minimum viable warmstart (MVP)
   - Full coverage recommendations

3. **Feasibility Requirements**
   - Constraint satisfaction rules
   - Soft vs hard constraints
   - Validation checklist

4. **Error Handling Strategy**
   - Try-catch structure
   - Fallback logic
   - Logging template

5. **Performance Metrics**
   - Success indicators
   - Diagnostic queries
   - Validation thresholds

---

## Integration Points

### base_model.py (line 283)
```python
# Current code (line 283):
# Solve
solve_start = time.time()

# PROPOSED INTEGRATION POINT:
# >>> INSERT WARMSTART LOGIC HERE <<<
# if use_warmstart and warmstart_values:
#     apply_warmstart_to_model(self.model, warmstart_values)

results = solver.solve(
    self.model,
    tee=tee,
    symbolic_solver_labels=False,
    load_solutions=False,
)
```

### unified_node_model.py (solve method)
```python
# Current code (line 922-949):
def solve(
    self,
    solver_name: Optional[str] = None,
    time_limit_seconds: Optional[float] = None,
    mip_gap: Optional[float] = None,
    tee: bool = False,
    use_aggressive_heuristics: bool = False,
) -> OptimizationResult:

# PROPOSED CHANGE:
def solve(
    self,
    solver_name: Optional[str] = None,
    time_limit_seconds: Optional[float] = None,
    mip_gap: Optional[float] = None,
    tee: bool = False,
    use_aggressive_heuristics: bool = False,
    use_warmstart: bool = True,  # <<< NEW PARAMETER
) -> OptimizationResult:
    """Build and solve the unified node model.

    Args:
        ...
        use_warmstart: Generate and apply warmstart solution (default: True)
    """

    # Generate warmstart if requested
    warmstart_values = None
    if use_warmstart:
        from .warmstart_generator import WarmstartGenerator
        generator = WarmstartGenerator(self)
        warmstart_values = generator.generate()

    # Call base class solve (which applies warmstart at line 283)
    return super().solve(
        solver_name=solver_name,
        time_limit_seconds=time_limit_seconds,
        mip_gap=mip_gap,
        tee=tee,
        use_aggressive_heuristics=use_aggressive_heuristics,
        warmstart_values=warmstart_values,  # <<< PASS TO BASE CLASS
    )
```

---

## Dependencies

**Upstream:** None (this is the first design task)
**Downstream:**
- `campaign_pattern_algorithm.md` (uses warmstart data structure)
- `integration_design.md` (uses API specification)

---

## Timeline

- **Request Date:** 2025-10-19
- **Expected Response:** Within 1 iteration
- **Dependencies:** None
- **Blocking:** All downstream agents

---

## Notes

- CBC solver is open-source (not commercial like Gurobi/CPLEX)
- Pyomo version: 6.x
- CBC version: 2.10.12
- Platform: Linux (cloud VM)
- Python: 3.11+

---

## Status Tracking

- [ ] Expert assigned
- [ ] Questions answered
- [ ] API specification provided
- [ ] Code examples validated
- [ ] Document reviewed
- [ ] Approved for implementation
