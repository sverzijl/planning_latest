# Design Decisions and Rationale Log

**Project:** Warmstart Implementation
**Last Updated:** 2025-10-19

---

## Decision Log

### Decision 001: Warmstart Default Behavior
**Date:** 2025-10-19
**Decision:** Enable warmstart by default (`use_warmstart=True`)
**Rationale:**
- **Opt-out approach** provides immediate benefits to all users
- **Graceful degradation** ensures no harm if warmstart fails
- **Expected performance gain** (20-40%) justifies default enablement
- **Easy opt-out** available for debugging or testing (`use_warmstart=False`)

**Alternatives Considered:**
- Opt-in (requires explicit `use_warmstart=True`) - REJECTED
  - Users might not know about feature
  - Performance benefits not automatic
- Always on (no option to disable) - REJECTED
  - Need debugging capability
  - Some scenarios may not benefit

**Status:** APPROVED
**Impact:** unified_node_model.py parameter default value

---

### Decision 002: Integration Point
**Date:** 2025-10-19
**Decision:** Apply warmstart in `BaseOptimizationModel.solve()` at line 283
**Rationale:**
- **Single point of integration** - all models benefit
- **After model build** - variables exist and can be initialized
- **Before solver.solve()** - warmstart applied before optimization
- **Minimal code changes** - localized modification

**Alternatives Considered:**
- In UnifiedNodeModel only - REJECTED
  - Requires duplication for other model classes
  - Not reusable
- In solver_config.py - REJECTED
  - Wrong layer of abstraction
  - Solver config should not know about business logic

**Status:** APPROVED
**Impact:** base_model.py line 283

---

### Decision 003: Warmstart Data Structure
**Date:** 2025-10-19
**Decision:** Use `Dict[Tuple, float]` mapping `(variable_name, index_tuple) -> value`
**Rationale:**
- **Flexible indexing** - supports multi-dimensional indices
- **Self-documenting** - variable name included in key
- **Type-safe** - clear value type (float)
- **Easy debugging** - can inspect keys to see what's initialized

**Example:**
```python
{
    ('production', ('6122', 'PROD_001', date(2025, 10, 20))): 5000.0,
    ('product_produced', ('6122', 'PROD_001', date(2025, 10, 20))): 1.0,
}
```

**Alternatives Considered:**
- Separate dicts per variable type - REJECTED
  - More complex API
  - Harder to aggregate
- Flat dict with string keys - REJECTED
  - Loses type information
  - Harder to parse indices

**Status:** APPROVED
**Impact:** warmstart_generator.py, base_model.py

---

### Decision 004: Campaign Pattern Strategy
**Date:** 2025-10-19
**Decision:** DEMAND_WEIGHTED allocation with fixed product rotation
**Rationale:**
- **Demand-driven** - aligns production with actual needs
- **Predictable rotation** - ensures all products produced weekly
- **Simple algorithm** - fast generation (<5s)
- **Good initial solution** - likely to be near-optimal

**Strategy Details:**
- Group 2-3 SKUs per production day
- Rotate all 5 products weekly
- Allocate quantities proportional to demand
- Prefer weekday production (avoid weekends)

**Alternatives Considered:**
- Equal allocation (divide demand equally) - REJECTED
  - Ignores demand patterns
  - May create stockouts or excess inventory
- Just-in-time (produce day before demand) - REJECTED
  - Doesn't account for transit times
  - May violate capacity constraints
- Optimization-based (solve mini-problem) - REJECTED
  - Too slow (defeats purpose of warmstart)
  - Overly complex

**Status:** PENDING EXPERT VALIDATION (production-planner)
**Impact:** warmstart_generator.py algorithm

---

### Decision 005: Variable Coverage
**Date:** 2025-10-19
**Decision:** Initialize production variables only (MVP approach)
**Rationale:**
- **Minimum viable warmstart** - fastest implementation
- **Core decision variables** - production drives the system
- **Good enough** - CBC can infer inventory/shipments from production
- **Incremental enhancement** - can add more variables later

**Variables Included:**
- `production[node, date, product]` - production quantities
- `product_produced[node, product, date]` - binary indicators
- `num_products_produced[node, date]` - changeover counts

**Variables Deferred (Phase 2):**
- `inventory_cohort` - can be inferred from production + demand
- `shipment_cohort` - can be inferred from production + routes
- `labor_hours_used` - can be calculated from production
- `pallet_count` - can be calculated from quantities

**Alternatives Considered:**
- Full coverage (all variables) - DEFERRED
  - More complex implementation
  - Longer generation time
  - May not provide proportional benefit
- Production + inventory - DEFERRED
  - Can validate in Phase 2 if MVP insufficient

**Status:** PENDING EXPERT VALIDATION (pyomo-modeling-expert)
**Impact:** warmstart_generator.py variable coverage

---

### Decision 006: Error Handling Strategy
**Date:** 2025-10-19
**Decision:** Graceful degradation with warnings (continue without warmstart on failure)
**Rationale:**
- **Robustness** - solve never fails due to warmstart issue
- **Transparency** - warnings inform user of problem
- **Debugging** - logs help diagnose issues
- **Backward compatible** - behaves like no warmstart if generation fails

**Error Scenarios:**
1. **Warmstart generation fails** → Log warning, set `warmstart_values=None`, continue
2. **Variable not found** → Skip that variable, log warning, continue with others
3. **Index mismatch** → Skip that value, log warning, continue with others
4. **Type error** → Skip that value, log warning, continue with others

**Success Rate Threshold:** Warn if <90% of values applied successfully

**Alternatives Considered:**
- Fail fast (raise exception) - REJECTED
  - Breaks existing workflows
  - Not backward compatible
- Silent failure (no warnings) - REJECTED
  - Hard to debug
  - Users unaware of issues

**Status:** APPROVED
**Impact:** base_model.py error handling, warmstart_generator.py error handling

---

### Decision 007: Performance Target
**Date:** 2025-10-19
**Decision:** Target 20-40% solve time reduction for 4-week horizon
**Rationale:**
- **Realistic expectation** - based on MIP warmstart literature
- **Measurable** - clear validation criteria
- **Achievable** - doesn't require perfect initial solution
- **Impactful** - >300s → <120s is significant improvement

**Targets:**
- Baseline: >300s (current timeout scenario)
- With warmstart: <120s (within integration test limit)
- Reduction: 60%+ (conservative: 20-40%)
- Warmstart overhead: <5s

**Validation Method:**
- Run 10 test cases with and without warmstart
- Calculate average solve time for each
- Compute reduction percentage
- Validate objective value unchanged (within 1%)

**Alternatives Considered:**
- 50%+ reduction target - REJECTED
  - May be unrealistic
  - Sets wrong expectations
- 10-20% reduction target - REJECTED
  - May not justify implementation effort
  - Too conservative

**Status:** APPROVED
**Impact:** Test validation thresholds

---

### Decision 008: Backward Compatibility
**Date:** 2025-10-19
**Decision:** ZERO breaking changes required
**Rationale:**
- **All new parameters optional** - default values provided
- **Existing code works unchanged** - no API modifications
- **Gradual adoption** - users can enable/disable as needed
- **Safe deployment** - can rollback easily

**Compatibility Guarantees:**
1. Existing calls to `model.solve()` work without changes
2. New parameters have sensible defaults
3. No changes to return types
4. No changes to required parameters
5. No changes to existing behavior when warmstart disabled

**Validation:**
- All existing tests pass without modification
- Integration test passes with warmstart enabled
- Can run with warmstart disabled (same results as before)

**Status:** APPROVED
**Impact:** All code changes

---

### Decision 009: File Organization
**Date:** 2025-10-19
**Decision:** New file `src/optimization/warmstart_generator.py` for warmstart logic
**Rationale:**
- **Separation of concerns** - warmstart logic isolated
- **Maintainability** - easier to update/debug
- **Testability** - can test independently
- **Reusability** - other models can use WarmstartGenerator

**Alternatives Considered:**
- Add to unified_node_model.py - REJECTED
  - File already large (~1,500 lines)
  - Mixes optimization logic with warmstart heuristics
- Add to base_model.py - REJECTED
  - Base class shouldn't know business logic
  - Campaign pattern specific to production planning

**Status:** APPROVED
**Impact:** File structure

---

### Decision 010: Documentation Strategy
**Date:** 2025-10-19
**Decision:** Update UNIFIED_NODE_MODEL_SPECIFICATION.md with warmstart section
**Rationale:**
- **Comprehensive documentation** - technical reference
- **Change tracking** - document modifications
- **User guidance** - explain how to use warmstart
- **Developer reference** - explain implementation details

**Documentation Updates Required:**
1. UNIFIED_NODE_MODEL_SPECIFICATION.md - add warmstart variables section
2. CLAUDE.md - add warmstart feature to project overview
3. Code docstrings - all functions documented
4. Test documentation - test plan and results

**Status:** APPROVED
**Impact:** Documentation files

---

## Pending Decisions

### PD-001: Pyomo API for Warmstart
**Date:** 2025-10-19
**Question:** What is the correct Pyomo API for setting initial variable values?
**Status:** PENDING EXPERT INPUT (pyomo-modeling-expert)
**Options:**
- A. `variable.value = initial_value`
- B. `variable.set_value(initial_value)`
- C. Pass warmstart dict to solver
- D. Use model.load_solution()

**Impact:** base_model.py implementation

---

### PD-002: Demand Aggregation Method
**Date:** 2025-10-19
**Question:** How to aggregate demand for campaign planning?
**Status:** PENDING EXPERT INPUT (production-planner)
**Options:**
- A. Weekly total demand
- B. Rolling 7-day window
- C. Horizon total ÷ weeks
- D. Daily demand + buffer

**Impact:** warmstart_generator.py algorithm

---

### PD-003: Product Grouping Logic
**Date:** 2025-10-19
**Question:** How to group 5 products into campaigns?
**Status:** PENDING EXPERT INPUT (production-planner)
**Options:**
- A. Fixed rotation (Mon: P1+P2, Tue: P3+P4, etc.)
- B. Demand-weighted grouping
- C. SKU similarity grouping
- D. Random with balancing

**Impact:** warmstart_generator.py algorithm

---

### PD-004: Quantity Allocation Method
**Date:** 2025-10-19
**Question:** How to allocate weekly demand to production days?
**Status:** PENDING EXPERT INPUT (production-planner)
**Options:**
- A. EQUAL (divide equally)
- B. DEMAND_WEIGHTED (proportional)
- C. CAPACITY_BALANCED (smooth utilization)
- D. JUST_IN_TIME (near demand date)

**Impact:** warmstart_generator.py algorithm

---

### PD-005: Overtime Decision Logic
**Date:** 2025-10-19
**Question:** When to use overtime vs split production?
**Status:** PENDING EXPERT INPUT (production-planner)
**Options:**
- A. AVOID_OVERTIME (never use)
- B. USE_IF_NEEDED (when demand exceeds capacity)
- C. AGGRESSIVE_OT (minimize production days)
- D. WEEKEND_LAST (only if weekdays full)

**Impact:** warmstart_generator.py algorithm

---

## Decision Review Process

1. **Proposal:** Agent proposes decision with rationale
2. **Review:** Context manager reviews for consistency
3. **Validation:** Expert agents validate technical correctness
4. **Approval:** Decision approved and logged here
5. **Implementation:** Decision guides code development
6. **Retrospective:** Review decision after implementation

---

## Change History

| Date | Decision ID | Change | Reason |
|------|-------------|--------|--------|
| 2025-10-19 | D001-D010 | Initial decisions logged | Context repository initialization |

---

## Notes

- All decisions are subject to revision based on expert input
- Pending decisions block implementation phase
- Approved decisions guide coding and testing
- Decision rationale helps future maintainers understand choices
