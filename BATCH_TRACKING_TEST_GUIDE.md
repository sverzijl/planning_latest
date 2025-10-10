# Batch Tracking Test Suite - Quick Start Guide

## Overview

This guide helps you run and interpret the comprehensive test suite for the age-cohort batch tracking implementation.

---

## Quick Start

### 1. Make Test Script Executable

```bash
chmod +x run_batch_tracking_tests.sh
```

### 2. Run Fast Tests (Recommended First)

```bash
./run_batch_tracking_tests.sh fast
```

Expected duration: ~30 seconds

### 3. Run All Tests

```bash
./run_batch_tracking_tests.sh all
```

Expected duration: ~10 minutes

---

## Test Categories

### Unit Tests (Fast - 30s)

Tests individual components in isolation.

```bash
./run_batch_tracking_tests.sh unit
```

**What it tests:**
- Model construction with `use_batch_tracking` flag
- Sparse cohort indexing
- Production batch creation
- Mass balance validation
- Result structure correctness

**Pass Criteria:**
- All 15+ tests pass
- Build time < 5s for 14-day horizon
- No errors or warnings

---

### Integration Tests (Medium - 3-5min)

Tests end-to-end workflows.

```bash
./run_batch_tracking_tests.sh integration
```

**What it tests:**
- Complete workflow: Build → Solve → Extract → Snapshot
- Batch traceability through multi-leg routes
- FIFO consumption tendency
- Mass balance across supply chain
- Shelf life enforcement
- Daily snapshot with model solution

**Pass Criteria:**
- All 10+ tests pass
- Solutions found within time limits
- FIFO violations < 20%
- Mass balance errors < 10 units

---

### Regression Tests (Medium - 5min)

Ensures backward compatibility.

```bash
./run_batch_tracking_tests.sh regression
```

**What it tests:**
- Legacy mode (`use_batch_tracking=False`) works unchanged
- Cost equivalence between modes (within 10%)
- Production quantities similar (within 5%)
- API stability (no breaking changes)
- All 56+ existing daily snapshot tests still pass

**Pass Criteria:**
- All regression tests pass
- All 56+ existing tests pass
- Cost difference < 10%
- No API changes

---

### Performance Benchmarks (Slow - 5-15min)

Measures scalability and efficiency.

```bash
./run_batch_tracking_tests.sh performance
```

**What it tests:**
- Model size scaling with horizon
- Build time scaling
- Solve time scaling
- Comparison: Legacy vs Cohort

**Expected Results:**

| Horizon | Variables | Build Time | Solve Time |
|---------|-----------|------------|------------|
| 7 days  | ~350      | < 2s       | < 30s      |
| 14 days | ~1,250    | < 5s       | < 120s     |
| 21 days | ~2,900    | < 15s      | < 300s     |

**Pass Criteria:**
- All benchmarks complete
- Times within limits
- Scaling follows expected trends

---

### Coverage Report

Generate HTML coverage report:

```bash
./run_batch_tracking_tests.sh coverage
```

Opens: `htmlcov/index.html`

**Target:** ≥80% coverage for:
- `src/optimization/integrated_model.py`
- `src/analysis/daily_snapshot.py`
- `src/models/production_batch.py`

---

## Interpreting Results

### ✅ All Tests Pass

```
======================== 40 passed in 8m 47s =========================
```

**Action:** Implementation validated! Ready for code review.

### ⚠️ Some Tests Skipped

```
======================== 35 passed, 5 skipped in 6m 12s =========================
```

**Reason:** Tests may skip if:
- Cohort implementation not yet complete
- Solver not finding solution within time limit
- Optional dependencies missing (e.g., memory_profiler)

**Action:** Review skip reasons in output. If skipped due to missing implementation, complete that feature.

### ❌ Tests Failing

```
======================== 30 passed, 10 failed in 5m 43s =========================
```

**Action:**
1. Review failure details: `pytest <test_file> -v --tb=long`
2. Check if failures are in:
   - **Unit tests:** Implementation bug
   - **Integration tests:** Workflow issue
   - **Regression tests:** Breaking change introduced

---

## Common Issues & Solutions

### Issue 1: Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'src.optimization'
```

**Solution:**
```bash
# Ensure you're in the project root
cd /home/sverzijl/planning_latest

# Install in development mode
pip install -e .
```

---

### Issue 2: Solver Not Found

**Error:**
```
ApplicationError: No executable found for solver 'cbc'
```

**Solution:**
```bash
# Install CBC solver
sudo apt-get install coinor-cbc  # Linux
brew install cbc                 # macOS

# Or use conda
conda install -c conda-forge coincbc
```

---

### Issue 3: Tests Timeout

**Error:**
```
Solver exceeded time limit (300s)
```

**Solution:**
- This is normal for 21+ day horizons
- Tests will skip if timeout occurs
- Consider running with shorter horizons for faster validation

---

### Issue 4: Cohort Variables Not Found

**Error:**
```
SKIPPED: Cohort indexes not yet implemented
```

**Solution:**
- This is expected if cohort implementation is in progress
- Tests are designed to skip gracefully
- Complete cohort variable implementation to enable these tests

---

## Test Development Workflow

### 1. TDD Workflow (Recommended)

```bash
# 1. Write failing test
vim tests/test_cohort_model_unit.py

# 2. Run test (should fail)
pytest tests/test_cohort_model_unit.py::test_new_feature -v

# 3. Implement feature
vim src/optimization/integrated_model.py

# 4. Run test again (should pass)
pytest tests/test_cohort_model_unit.py::test_new_feature -v

# 5. Run full suite to check for regressions
./run_batch_tracking_tests.sh all
```

### 2. Adding New Tests

Create test in appropriate file:

- **Unit test:** `tests/test_cohort_model_unit.py`
- **Integration test:** `tests/test_batch_tracking_integration.py`
- **Regression test:** `tests/test_batch_tracking_regression.py`
- **Performance test:** `tests/test_cohort_performance.py`

Template:

```python
def test_my_new_feature(
    standard_forecast: Forecast,
    standard_labor_calendar: LaborCalendar,
    # ... other fixtures
) -> None:
    """Test description."""
    # Arrange
    model = IntegratedProductionDistributionModel(...)

    # Act
    result = model.solve()

    # Assert
    assert result['some_field'] == expected_value
```

---

## CI/CD Integration

### GitHub Actions (Recommended)

Create `.github/workflows/batch_tracking_tests.yml`:

```yaml
name: Batch Tracking Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
        sudo apt-get install coinor-cbc

    - name: Run tests
      run: ./run_batch_tracking_tests.sh all

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Performance Monitoring

### Baseline Performance (14-day horizon)

Track these metrics over time:

| Metric | Baseline | Alert If |
|--------|----------|----------|
| Variables | 1,247 | > 2,000 |
| Build Time | 3.8s | > 10s |
| Solve Time | 42s | > 120s |
| Memory | <500MB | > 1GB |

### Tracking Command

```bash
# Run performance tests and save results
pytest tests/test_cohort_performance.py::test_performance_summary_report \
       -v -s | tee performance_$(date +%Y%m%d).log
```

---

## Troubleshooting

### Enable Verbose Output

```bash
pytest tests/test_cohort_model_unit.py -vv -s
```

### Run Single Test

```bash
pytest tests/test_cohort_model_unit.py::test_batch_tracking_flag_initialization -v
```

### Debug Failing Test

```bash
pytest tests/test_cohort_model_unit.py::test_failing_test -v --pdb
```

### Check Test Discovery

```bash
pytest --collect-only tests/
```

---

## Getting Help

### View Full Test Documentation

```bash
# View test docstrings
pytest tests/test_cohort_model_unit.py --help

# View detailed test results report
cat TEST_RESULTS_BATCH_TRACKING.md
```

### Run Specific Test Pattern

```bash
# All batch tracking tests
pytest -k "batch" -v

# All FIFO tests
pytest -k "fifo" -v

# All regression tests
pytest -k "legacy" -v
```

---

## Success Checklist

Before considering implementation complete:

- [ ] All unit tests pass (15+)
- [ ] All integration tests pass (10+)
- [ ] All regression tests pass (15+)
- [ ] All existing tests pass (56+)
- [ ] Performance within limits (7-day < 60s solve)
- [ ] Code coverage ≥ 80%
- [ ] No breaking API changes
- [ ] Documentation updated
- [ ] CI/CD pipeline green

---

## Next Steps

After all tests pass:

1. **Code Review:** Submit PR with test results
2. **Performance Optimization:** Address identified bottlenecks
3. **Documentation:** Update user guides with batch tracking features
4. **Production Deployment:** Roll out with monitoring

---

## Quick Reference

```bash
# Fast validation (30s)
./run_batch_tracking_tests.sh fast

# Full validation (10min)
./run_batch_tracking_tests.sh all

# With coverage (12min)
./run_batch_tracking_tests.sh coverage

# Performance baseline (15min)
./run_batch_tracking_tests.sh performance

# Single test
pytest tests/test_cohort_model_unit.py::test_name -v

# Debug mode
pytest tests/test_name.py -v --pdb
```

---

**Happy Testing!** 🧪
