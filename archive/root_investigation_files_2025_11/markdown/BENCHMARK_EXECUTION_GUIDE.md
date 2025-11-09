# Warmstart Performance Benchmark - Execution Guide

## Overview

This guide explains how to execute the warmstart performance benchmarks and interpret the results. All benchmark scripts and tests are ready to run.

## Quick Start

Execute the comprehensive benchmark suite:

```bash
bash run_benchmarks.sh
```

This script runs all 5 benchmark phases sequentially and generates a summary report.

## Benchmark Phases

### Phase 1: Smoke Test (10s)
**Purpose:** Verify warmstart integration works correctly

```bash
venv/bin/python test_warmstart_smoke.py
```

**Expected Output:**
```
Testing warmstart generator import...
✓ Warmstart generator imports successfully

Testing warmstart generation...
✓ Generated 140 warmstart hints
✓ All 140 hints are binary (0 or 1)
✓ Hints pass validation

Testing UnifiedNodeModel warmstart integration...
✓ UnifiedNodeModel has warmstart methods
✓ solve() method has warmstart parameters

✅ ALL SMOKE TESTS PASSED
```

**Success Criteria:**
- All checks pass
- Completes in <5 seconds
- No import errors

### Phase 2: Baseline Integration Test (300s timeout)
**Purpose:** Establish baseline solve time WITHOUT warmstart

```bash
timeout 300 venv/bin/python -m pytest tests/test_integration_ui_workflow.py::test_ui_workflow_4_weeks_with_initial_inventory -v -s
```

**What This Tests:**
- UnifiedNodeModel with binary product_produced variables
- 4-week planning horizon
- Real production data (Gfree Forecast.xlsm)
- No warmstart hints

**Expected Metrics:**
- Solve time: [20-200s range expected]
- Status: OPTIMAL or FEASIBLE
- Fill rate: ≥85%
- MIP gap: <1%

**Critical:** Record the solve time from this test - it's your baseline!

### Phase 3: Warmstart Integration Test (300s timeout)
**Purpose:** Measure performance WITH warmstart

```bash
timeout 300 venv/bin/python -m pytest tests/test_integration_ui_workflow.py::test_ui_workflow_with_warmstart -v -s
```

**What This Tests:**
- Same UnifiedNodeModel configuration
- Warmstart hints applied to product_produced variables
- Campaign-based production pattern (2-3 SKUs per weekday)

**Expected Metrics:**
- Solve time: [Should be faster than baseline]
- Status: OPTIMAL or FEASIBLE
- Fill rate: ≥85%
- MIP gap: <1%

**Success Indicator:** Solve time < baseline solve time

### Phase 4: Comprehensive Benchmark (600s timeout)
**Purpose:** Side-by-side comparison with detailed analysis

```bash
timeout 600 python scripts/benchmark_warmstart_performance.py
```

**What This Does:**
1. Runs baseline test (no warmstart)
2. Runs warmstart test (with hints)
3. Compares performance metrics
4. Generates formatted comparison table
5. Saves results to `benchmark_results.txt`

**Output Files:**
- Console: Formatted comparison table
- `benchmark_results.txt`: Detailed metrics and analysis

**Sample Output:**
```
PERFORMANCE COMPARISON
================================================================================
Metric                    Baseline        Warmstart        Difference
--------------------------------------------------------------------------------
Solve time (s)                 45.2             32.1          -13.1s (-29.0%)
Objective ($)            123,456.78       123,234.56      $-222.22 (-0.2%)
MIP gap (%)                    0.95             0.88               -0.07%
Fill rate (%)                  91.5             91.7                +0.2%
--------------------------------------------------------------------------------

WARMSTART SPEEDUP: 29.0%
Time saved: 13.1s
✅ WARMSTART EFFECTIVE
```

### Phase 5: Performance Comparison Tests (600s timeout)
**Purpose:** Automated pytest validation

```bash
timeout 600 venv/bin/python -m pytest tests/test_warmstart_performance_comparison.py -v -s
```

**What This Tests:**
1. `test_warmstart_performance_improvement`:
   - Runs both baseline and warmstart
   - Asserts objective values within 5%
   - Asserts fill rates ≥85%
   - Validates both complete within time limit

2. `test_warmstart_campaign_pattern_validation`:
   - Validates hint generation correctness
   - Checks binary values (0 or 1)
   - Verifies campaign pattern (2-3 SKUs per weekday)
   - Confirms all products covered

**Success Criteria:**
- Both tests pass
- Assertions validate warmstart effectiveness
- No test failures or timeouts

## Interpreting Results

### Warmstart is EFFECTIVE if:
- ✅ Speedup ≥20% (significant improvement)
- ✅ Solve time <120s with warmstart
- ✅ Objective values within 5%
- ✅ Fill rates ≥85% for both approaches
- ✅ No solution quality degradation

**Recommendation:** ENABLE warmstart by default

### Warmstart is CONDITIONALLY USEFUL if:
- ⚠️  Speedup 10-20% (modest improvement)
- ⚠️  Solve time 120-180s with warmstart
- ⚠️  Slight objective value difference (1-3%)

**Recommendation:** ENABLE for large problems, OPTIONAL for small

### Warmstart is INEFFECTIVE if:
- ❌ Speedup <10% (marginal benefit)
- ❌ Solve time >180s with warmstart
- ❌ Warmstart slower than baseline
- ❌ Solution quality degraded

**Recommendation:** DISABLE warmstart, investigate issue

### Warmstart needs INVESTIGATION if:
- 🔍 Timeout on either baseline or warmstart
- 🔍 Solver crashes or errors
- 🔍 Inconsistent results across runs
- 🔍 Unexpected behavior

**Recommendation:** Debug warmstart logic, check solver logs

## Output Files

After running `run_benchmarks.sh`, you'll have:

1. **baseline_test_output.txt**: Full pytest output from baseline test
2. **warmstart_test_output.txt**: Full pytest output from warmstart test
3. **benchmark_output.txt**: Standalone benchmark script output
4. **benchmark_results.txt**: Detailed comparison metrics (if completed)
5. **performance_test_output.txt**: Pytest performance tests output

## Updating the Performance Report

After benchmarks complete, update `PERFORMANCE_REPORT.md`:

1. Replace `[PENDING]` placeholders with actual metrics
2. Update status fields (PENDING → PASSED/FAILED/TIMEOUT)
3. Fill in "Detailed Findings" section with observations
4. Make final recommendation (ENABLE/DISABLE/INVESTIGATE)
5. Document any unexpected behavior or insights

## Troubleshooting

### Smoke Test Fails
**Issue:** Import errors or hint generation failures

**Solution:**
1. Check warmstart_generator.py exists in src/optimization/
2. Verify UnifiedNodeModel has _generate_warmstart() and _apply_warmstart() methods
3. Review test_warmstart_smoke.py error messages

### Baseline Test Times Out (>300s)
**Issue:** Binary variables make problem too hard for CBC

**Possible Causes:**
1. Too many binary variables (check variable count in solver output)
2. Weak LP relaxation (check gap at root node)
3. Solver configuration issue

**Solutions:**
- Increase timeout to 600s
- Try commercial solver (Gurobi/CPLEX)
- Review binary variable formulation
- Check for constraint conflicts

### Warmstart Test Times Out
**Issue:** Warmstart hints don't help solver enough

**Possible Causes:**
1. Hints are invalid or conflict with constraints
2. Campaign pattern doesn't match optimal solution
3. Solver ignores warmstart (check solver logs)

**Solutions:**
- Review warmstart hint validation
- Analyze optimal solution pattern vs. campaign pattern
- Check solver warmstart support (CBC has limited warmstart)
- Try different warmstart strategy

### Both Tests Timeout
**Issue:** Problem is too large for CBC with binary variables

**Solutions:**
1. Use commercial solver (Gurobi/CPLEX)
2. Reduce planning horizon (2 weeks instead of 4)
3. Reduce number of products
4. Disable pallet-based holding costs (if enabled)
5. Remove binary variables (use continuous production)

### Warmstart SLOWER than Baseline
**Issue:** Warmstart overhead exceeds benefit

**Possible Causes:**
1. Hints are poor quality (far from optimal)
2. Solver re-solves problem from scratch anyway
3. Warmstart conflicts with solver heuristics

**Solutions:**
- Improve warmstart hint quality
- Disable warmstart
- Try different hint generation strategy
- Test with different solver

## Performance Context

### Current Model Characteristics
- **Binary variables (product_produced):** 140 (1 node × 5 products × 28 days)
- **Integer variables (pallet_count):** 0 (pallet costs disabled in current config)
- **Continuous variables:** ~20,000 (production, inventory, shipments)
- **Constraints:** ~10,000-15,000
- **Planning horizon:** 28 days (4 weeks)

### Historical Performance (Continuous Production)
- **Without pallet costs:** 20-30s solve time
- **With pallet costs:** 35-45s solve time
- **Status:** OPTIMAL within 1% gap

### Expected Performance (Binary Production)
- **Without warmstart:** Unknown (first benchmark)
- **With warmstart:** Target 10-40% speedup
- **Worst case:** Timeout (>300s) if problem too hard

### Solver Limitations
- **CBC (open-source):** Good for small-medium MIP, limited warmstart support
- **Gurobi/CPLEX (commercial):** Better MIP performance, full warmstart support

## Next Steps After Benchmarking

### If Warmstart is EFFECTIVE:
1. ✅ Update CLAUDE.md with warmstart documentation
2. ✅ Expose warmstart option in UI Planning Tab
3. ✅ Set default warmstart=True in UnifiedNodeModel.solve()
4. ✅ Add warmstart configuration to Network_Config.xlsx
5. ✅ Document campaign pattern customization

### If Warmstart is INEFFECTIVE:
1. ❌ Keep warmstart code for future investigation
2. ❌ Don't expose in UI (internal use only)
3. ❌ Set default warmstart=False
4. ❌ Document findings in PERFORMANCE_REPORT.md
5. 🔍 Investigate alternative speedup strategies

### Alternative Speedup Strategies:
- Try commercial solvers (Gurobi/CPLEX)
- Implement custom solver cuts/heuristics
- Use rolling horizon with shorter periods
- Aggregate products into families
- Simplify binary variable logic

## Contact

For questions or issues with benchmarking:
1. Review PERFORMANCE_REPORT.md for context
2. Check solver logs for detailed diagnostics
3. Examine test output files for error messages
4. Compare with historical performance in CLAUDE.md

---

**Ready to benchmark?** Run `bash run_benchmarks.sh` and update PERFORMANCE_REPORT.md with results!
