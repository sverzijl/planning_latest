# Comprehensive Test Validation Instructions

## Overview
This document provides step-by-step instructions for validating the non-fixed day fix in `unified_node_model.py` (lines 343-346).

**Fix Summary:**
- Changed: `day_hours = labor_day.fixed_hours` (was 0 on non-fixed days)
- To: `day_hours = 24.0` (reasonable physical upper bound)
- Impact: Enables production on weekends/holidays (was forced to 0, causing infeasibility)

---

## Execution Options

### Option 1: Full Automated Validation (Recommended)
Run all tests in one go with automated reporting:

```bash
chmod +x run_validation.py
./run_validation.py
```

**Expected duration:** ~5-10 minutes
**Output:** Comprehensive report with all test results

---

### Option 2: Phase-by-Phase Validation
Run each phase separately for detailed monitoring:

#### Phase 1: Critical Non-Fixed Day Tests
```bash
chmod +x run_phase1_only.py
./run_phase1_only.py
```

**Expected duration:** ~1-2 minutes
**Purpose:** Verify the three previously failing tests now pass

#### Phase 2: Regression Tests
Run each suite individually:

```bash
# Suite 1: Weekday Labor Costs
venv/bin/python -m pytest tests/test_labor_cost_piecewise.py -v

# Suite 2: Multi-Day Consistency
venv/bin/python -m pytest tests/test_labor_overhead_multi_day.py -v

# Suite 3: Overtime Preference
venv/bin/python -m pytest tests/test_overtime_preference.py -v

# Suite 4: Baseline Labor Costs
venv/bin/python -m pytest tests/test_labor_cost_baseline.py -v

# Suite 5: Labor Cost Isolation
venv/bin/python -m pytest tests/test_labor_cost_isolation.py -v

# Suite 6: Unified Model Core
venv/bin/python -m pytest tests/test_unified_node_model.py -v
```

**Expected duration:** ~3-5 minutes total
**Purpose:** Ensure no regressions in existing tests

#### Phase 3: Integration Test
```bash
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v
```

**Expected duration:** ~30-60 seconds
**Purpose:** Validate real-world scenario compatibility

---

### Option 3: Individual Test Execution
Run specific tests for detailed debugging:

**Test 1: Weekend Production Below Minimum**
```bash
venv/bin/python -m pytest \
  tests/test_labor_cost_piecewise.py::test_piecewise_non_fixed_day_below_minimum \
  -v -s
```

**Test 2: Public Holiday Overhead (Above Minimum)**
```bash
venv/bin/python -m pytest \
  tests/test_labor_overhead_holiday.py::test_public_holiday_overhead_included \
  -v -s
```

**Test 3: Public Holiday Overhead (Below Minimum)**
```bash
venv/bin/python -m pytest \
  tests/test_labor_overhead_holiday.py::test_public_holiday_overhead_below_minimum \
  -v -s
```

---

## Success Criteria

### Phase 1: Non-Fixed Day Tests
- [ ] All 3 tests PASS (were INFEASIBLE before fix)
- [ ] Solve time < 5 seconds per test
- [ ] Solution status: OPTIMAL or FEASIBLE
- [ ] Labor hours include overhead
- [ ] 4-hour minimum enforced on non-fixed days

### Phase 2: Regression Tests
- [ ] No test failures in existing suites
- [ ] All previously passing tests still pass
- [ ] No new skipped tests
- [ ] No performance degradation

### Phase 3: Integration Test
- [ ] Test PASSES
- [ ] Solve time < 30 seconds
- [ ] Fill rate >= 85%
- [ ] MIP gap < 1%
- [ ] No infeasibilities

### Overall Success
- [ ] Phase 1: 3/3 tests passing
- [ ] Phase 2: 6/6 suites passing
- [ ] Phase 3: 1/1 test passing
- [ ] Total execution time < 10 minutes
- [ ] Zero regressions detected

---

## Interpreting Results

### Expected Outcomes

**Phase 1 Tests (Previously Failing):**
These tests were INFEASIBLE before the fix because the Big-M constraint calculation used `day_hours = labor_day.fixed_hours` which was 0 for non-fixed days. This made the constraint:

```
production[n, p, d] <= M * production_day[n, d]
```

effectively become:

```
production[n, p, d] <= 0 * production_day[n, d] = 0
```

forcing production to 0 on weekends/holidays, making demand satisfaction impossible.

**After the fix:** `day_hours = 24.0` provides a reasonable upper bound (24 physical hours in a day), allowing production on non-fixed days.

**Test 1 Expected Output:**
```
Labor hours used: 2.75h (includes overhead)
Labor hours paid: 4.0h (4-hour minimum enforced)
Labor cost: $160.00 (4h × $40/h)
Status: OPTIMAL
```

**Test 2 Expected Output:**
```
Production: 4,200 units on June 9, 2025
Labor hours used: 4.25h (3h production + overhead)
Overhead: 0.75-1.0h
Status: OPTIMAL
```

**Test 3 Expected Output:**
```
Production: 1,400 units
Labor hours used: 1.75h
Labor hours paid: 4.0h (minimum enforced)
Status: OPTIMAL
```

---

## Troubleshooting

### If Phase 1 Tests Still Fail

**Check 1: Verify fix is applied**
```bash
grep -A 5 "Non-fixed day:" src/optimization/unified_node_model.py | head -10
```

Should show:
```python
else:
    # Non-fixed day: unlimited capacity at premium rate
    # Use 24 hours as reasonable physical upper bound for Big-M
    day_hours = 24.0  # FIX: Was labor_day.fixed_hours (which is 0)
```

**Check 2: Verify solver is working**
```bash
venv/bin/python -c "from pyomo.environ import SolverFactory; print(SolverFactory('cbc').available())"
```

Should output: `True`

**Check 3: Check for model errors**
Run test with full output:
```bash
venv/bin/python -m pytest tests/test_labor_cost_piecewise.py::test_piecewise_non_fixed_day_below_minimum -v -s --tb=long
```

---

### If Phase 2 Tests Show Regressions

**Identify failing test:**
```bash
venv/bin/python -m pytest tests/test_labor_cost_piecewise.py -v --tb=short
```

**Common issues:**
1. **Constraint conflicts:** Fix may have exposed edge cases in piecewise labor model
2. **Performance:** Fix shouldn't impact solve time, but verify solve time < 30s
3. **Cost changes:** Labor costs should be accurate with overhead included

**Debug specific test:**
```bash
venv/bin/python -m pytest tests/[FAILING_TEST_FILE] -v -s --tb=long
```

---

### If Integration Test Fails

**Check solve time:**
- Expected: < 30 seconds for 4-week horizon
- If > 60 seconds: Performance regression detected

**Check solution quality:**
- Fill rate should be >= 85%
- MIP gap should be < 1%
- Status should be OPTIMAL or FEASIBLE

**Debug command:**
```bash
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v -s --tb=long
```

---

## Reporting Results

Use the provided `VALIDATION_REPORT_TEMPLATE.md` to document results:

1. Copy template: `cp VALIDATION_REPORT_TEMPLATE.md VALIDATION_REPORT_RESULTS.md`
2. Fill in results as tests complete
3. Check boxes for passing tests
4. Document any failures or anomalies
5. Include timing information

---

## Next Steps After Validation

### If All Tests Pass
1. Document fix in CLAUDE.md (already done)
2. Update UNIFIED_NODE_MODEL_SPECIFICATION.md with Big-M calculation details
3. Commit changes with message: "fix: Enable production on non-fixed days with 24h upper bound"
4. Run full test suite: `pytest tests/ -v`

### If Tests Fail
1. Document failures in validation report
2. Analyze root cause (constraint conflict, solver issue, model bug)
3. Create detailed bug report with:
   - Test name and command
   - Expected vs actual results
   - Model output / solver log
   - Hypothesis for failure
4. Investigate alternative fixes:
   - Different Big-M calculation approach
   - Separate constraints for fixed vs non-fixed days
   - Dynamic M based on actual capacity

---

## Files Reference

**Test Files:**
- `/home/sverzijl/planning_latest/tests/test_labor_cost_piecewise.py` - Phase 1 Test 1, Phase 2 Suite 1
- `/home/sverzijl/planning_latest/tests/test_labor_overhead_holiday.py` - Phase 1 Tests 2-3
- `/home/sverzijl/planning_latest/tests/test_labor_overhead_multi_day.py` - Phase 2 Suite 2
- `/home/sverzijl/planning_latest/tests/test_overtime_preference.py` - Phase 2 Suite 3
- `/home/sverzijl/planning_latest/tests/test_labor_cost_baseline.py` - Phase 2 Suite 4
- `/home/sverzijl/planning_latest/tests/test_labor_cost_isolation.py` - Phase 2 Suite 5
- `/home/sverzijl/planning_latest/tests/test_unified_node_model.py` - Phase 2 Suite 6
- `/home/sverzijl/planning_latest/tests/test_integration_ui_workflow.py` - Phase 3

**Automation Scripts:**
- `/home/sverzijl/planning_latest/run_validation.py` - Full validation (all phases)
- `/home/sverzijl/planning_latest/run_phase1_only.py` - Quick Phase 1 validation
- `/home/sverzijl/planning_latest/run_comprehensive_validation.sh` - Bash alternative

**Model Files:**
- `/home/sverzijl/planning_latest/src/optimization/unified_node_model.py` - Lines 343-346 (fix location)

**Documentation:**
- `/home/sverzijl/planning_latest/VALIDATION_REPORT_TEMPLATE.md` - Report template
- `/home/sverzijl/planning_latest/VALIDATION_INSTRUCTIONS.md` - This file
