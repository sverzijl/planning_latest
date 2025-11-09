# SKU Variable Performance Investigation

## Problem Statement

The Pyomo UnifiedNodeModel has become very slow when allowed to vary the number of SKUs produced per day. When set to produce every product every day, it solved reasonably fast despite pallet tracking. With binary SKU selection enabled, 4-week horizon integration tests are timing out at 120s.

## Current Performance Baseline

From recent commits (f380b0a, 180fc66):

**With Binary SKU Variables:**
- HiGHS: ~96s for 4-week horizon (commit f380b0a benchmark)
- APPSI HiGHS: ~29s for 4-week horizon (commit 180fc66 benchmark)
- CBC: ~226s for 4-week horizon (commit f380b0a benchmark)
- **Integration tests: TIMING OUT at 120s** (all 4 tests failing)

**Expected Performance (from test docstrings):**
- Target: < 30 seconds for 4-week horizon
- Current: 120s+ (timeout)

## Root Cause Analysis

### 1. Binary Variable Structure

**Binary Variables Added (commit f380b0a):**
```python
# Line 600-604 in unified_node_model.py
model.product_produced = Var(
    product_produced_index,  # (node_id, product, date) tuples
    within=Binary,
    doc="Binary indicator: 1 if this product is produced, 0 otherwise"
)
```

**Variable Count:**
- 5 products × 28 days × 1 manufacturing node = **140 binary variables**
- Plus ~18,675 integer pallet_count variables (when pallet tracking enabled)
- Total integer variables: ~18,815

**Linking Constraint (Big-M):**
```python
# Line 2204-2222 in unified_node_model.py
def product_produced_linking_rule(model, node_id, prod, date):
    M = self.get_max_daily_production()  # = 1400 * 24 = 33,600 units
    return model.production[node_id, prod, date] <= M * model.product_produced[node_id, prod, date]
```

### 2. Potential Issues

#### Issue 1: Loose Big-M Constraint
- **Current M value:** 33,600 units per product per day
- **Actual max daily production (all products):** ~19,600 units (14h × 1400)
- **Typical demand per product per day:** 500-2,000 units
- **Problem:** Big-M is 10-60× larger than typical production quantities
- **Impact:** Weak LP relaxation → more branching → slower MIP solve

#### Issue 2: Binary × Integer Interaction
- Binary product_produced (140 vars) interacts with integer pallet_count (~18,675 vars)
- Pallet constraints: `pallet_count * 320 >= inventory_qty`
- Inventory depends on production, which depends on product_produced
- **Problem:** Complex coupling between binary and integer variables
- **Impact:** Difficult branching decisions, poor LP bounds

#### Issue 3: Symmetry in Binary Variables
- All 5 products have identical structure (no product-specific constraints)
- Solver may explore symmetric branches (produce A+B vs B+A)
- HiGHS has symmetry detection but may not fully handle this
- **Impact:** Redundant branching, slower enumeration

## Investigation Plan

### Phase 1: Tighten Big-M Constraint ✓

**Current Implementation:**
```python
M = self.get_max_daily_production()  # = 33,600 units
```

**Proposed Improvement:**
```python
# Use product-specific daily demand as tighter bound
M_prod = min(
    self.get_max_daily_production(),  # Physical capacity limit
    max_daily_demand_for_product * 1.5  # 50% buffer above max demand
)
```

**Expected Impact:** Tighter LP relaxation → fewer branch-and-bound nodes

### Phase 2: Add Parameter to Fix All SKUs ✓

**Proposed Parameter:**
```python
class UnifiedNodeModel:
    def __init__(self, ..., force_all_skus_daily: bool = False):
        """
        If force_all_skus_daily=True:
            - Fix all product_produced[n,p,d] = 1
            - Removes 140 binary variables
            - Converts to continuous relaxation
        """
```

**Expected Impact:**
- Removes binary decision complexity
- Solves as LP with only integer pallet variables
- Useful for baseline comparison and warmstart generation

### Phase 3: Two-Phase Solve with Warmstart ✓

**Approach:**
1. **Phase 1 (Fast Solve):**
   - Fix all SKUs: `force_all_skus_daily=True`
   - Disable pallet tracking: `storage_cost_per_pallet_day_*=0`
   - Solve as pure LP in ~5-10s

2. **Phase 2 (Optimal Solve):**
   - Extract production pattern from Phase 1
   - Initialize product_produced variables based on Phase 1
   - Enable binary SKU selection
   - Enable pallet tracking
   - Solve with APPSI HiGHS using warmstart

**Expected Impact:**
- Phase 1 provides feasible starting point
- Phase 2 starts with good incumbent → faster MIP solve
- APPSI HiGHS supports native warmstart (unlike legacy HiGHS)

### Phase 4: Check Solver Configuration ✓

**Current APPSI HiGHS Settings (from commit 180fc66):**
```python
# base_model.py
solver.config.time_limit = time_limit_seconds
solver.config.mip_gap = mip_gap
solver.config.presolve = 'on'  # CRITICAL
solver.config.parallel = 'on'
solver.config.threads = cpu_count()
```

**Investigate:**
- Are these settings actually being applied in integration tests?
- Is APPSI HiGHS being used or falling back to legacy HiGHS?
- Check solver detection and preference order

## Proposed Solutions

### Solution A: Quick Fix - Tighter Big-M
**Implementation:** 20 lines of code
**Expected speedup:** 20-40% (M reduction factor)
**Risk:** Low (only changes bound, not structure)

### Solution B: Parameter for Fixed SKUs
**Implementation:** 30 lines of code
**Use cases:**
- Baseline testing without binary complexity
- Warmstart generation for two-phase solve
- Debugging and performance comparisons

### Solution C: Two-Phase Solve
**Implementation:** 100 lines of code
**Expected speedup:** 50-70% (Phase 1 provides good warmstart)
**Complexity:** Medium (requires warmstart coordination)

### Solution D: Disable Pallet Tracking for Integration Tests
**Implementation:** 1 line (config file change)
**Expected speedup:** 2× (removes 18,675 integer variables)
**Tradeoff:** Less accurate storage costs, but faster testing

## Recommended Approach

**Immediate Actions (today):**
1. ✅ **Implement Solution A** (tighter Big-M) - quick win
2. ✅ **Implement Solution B** (fixed SKU parameter) - enables testing
3. ✅ **Test with Solution D** (disable pallet costs) - verify root cause

**Follow-up Actions (next session):**
4. ✅ **Implement Solution C** (two-phase solve) - if needed for performance
5. ✅ **Investigate solver configuration** - ensure APPSI HiGHS is used
6. ✅ **Add performance benchmarks** - track regression over time

## Testing Strategy

**Benchmark Tests:**
```bash
# Test 1: Fixed SKUs + No Pallets (baseline - should be ~5-10s)
python test_performance.py --force-all-skus --no-pallets

# Test 2: Fixed SKUs + Pallets (should be ~15-30s)
python test_performance.py --force-all-skus --with-pallets

# Test 3: Binary SKUs + No Pallets (should be ~20-40s)
python test_performance.py --variable-skus --no-pallets

# Test 4: Binary SKUs + Pallets (current = 120s+, target = 60-90s)
python test_performance.py --variable-skus --with-pallets
```

**Success Criteria:**
- Test 1: < 10s ✓
- Test 2: < 30s ✓
- Test 3: < 40s ✓
- Test 4: < 90s ← **PRIMARY GOAL**

## Next Steps

1. Read the current solver configuration code (base_model.py, solver_config.py)
2. Verify which solver is being used in integration tests
3. Implement tighter Big-M constraint
4. Add `force_all_skus_daily` parameter
5. Run benchmark tests to measure impact
6. If needed, implement two-phase solve with warmstart

## Questions for User

1. **Priority:** Do you want all solutions or should we focus on the quickest fix first?
2. **Warmstart:** Is the two-phase approach (fast solve → warmstart → full solve) acceptable?
3. **Pallet tracking:** For integration tests, is it acceptable to disable pallet costs temporarily?
4. **Solver preference:** Should we focus on APPSI HiGHS specifically or support multiple solvers?

---

**Generated:** 2025-10-19
**Context:** Integration tests timing out with binary SKU variables
**Goal:** Restore < 30s solve time for 4-week horizon
