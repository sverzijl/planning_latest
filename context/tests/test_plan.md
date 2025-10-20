# Warmstart Testing Plan

**Status:** PENDING IMPLEMENTATION
**Assigned To:** test-automator
**Priority:** HIGH
**Last Updated:** 2025-10-19

---

## Objective

Comprehensive test suite to validate warmstart functionality, performance, and integration.

---

## Test Strategy

### Test Pyramid

```
                    ┌─────────────┐
                    │  Manual     │  (5%)
                    │  Testing    │
                    └─────────────┘
                ┌───────────────────┐
                │  Integration      │  (20%)
                │  Tests            │
                └───────────────────┘
            ┌───────────────────────────┐
            │  Unit Tests               │  (75%)
            │                           │
            └───────────────────────────┘
```

### Test Coverage Target
- **Overall:** >80% code coverage
- **Critical paths:** 100% coverage
- **Error handling:** 100% coverage
- **Happy paths:** 100% coverage

---

## Test Suites

### Suite 1: Unit Tests - WarmstartGenerator

**File:** `tests/test_warmstart_generator.py`
**Purpose:** Test warmstart generation logic in isolation

#### Test Cases

**TC-UG-001: Initialization**
```python
def test_warmstart_generator_initialization():
    """Test WarmstartGenerator initialization."""
    # Given: UnifiedNodeModel instance
    model = create_test_model()

    # When: Initialize generator
    generator = WarmstartGenerator(model)

    # Then: Properties set correctly
    assert generator.model == model
    assert len(generator.manufacturing_nodes) > 0
    assert len(generator.products) > 0
```

**TC-UG-002: Demand Aggregation - Single Product**
```python
def test_aggregate_demand_single_product():
    """Test demand aggregation for single product."""
    # Given: Forecast with single product
    generator = create_generator_single_product()

    # When: Aggregate demand
    demand = generator._aggregate_demand()

    # Then: Total demand correct
    assert 'PROD_001' in demand
    assert demand['PROD_001'] > 0
    assert len(demand) == 1
```

**TC-UG-003: Demand Aggregation - Multiple Products**
```python
def test_aggregate_demand_multiple_products():
    """Test demand aggregation for multiple products."""
    # Given: Forecast with 5 products
    generator = create_generator_five_products()

    # When: Aggregate demand
    demand = generator._aggregate_demand()

    # Then: All products present
    assert len(demand) == 5
    for product in ['PROD_001', 'PROD_002', 'PROD_003', 'PROD_004', 'PROD_005']:
        assert product in demand
        assert demand[product] > 0
```

**TC-UG-004: Campaign Pattern - Single Week**
```python
def test_campaign_pattern_single_week():
    """Test campaign pattern generation for 1 week."""
    # Given: 5 products, 1 week horizon
    generator = create_generator_one_week()
    demand = {'PROD_001': 10000, 'PROD_002': 8000, ...}

    # When: Generate campaign pattern
    production_plan = generator._generate_campaign_pattern(demand)

    # Then: Validate production plan
    # All products produced at least once
    products_produced = set(p for (n, p, d), q in production_plan.items() if q > 0)
    assert len(products_produced) == 5

    # Total production >= total demand
    total_production = sum(production_plan.values())
    total_demand = sum(demand.values())
    assert total_production >= total_demand

    # Weekday preference (Mon-Fri should have more than Sat-Sun)
    weekday_production = sum(q for (n, p, d), q in production_plan.items() if d.weekday() < 5)
    weekend_production = sum(q for (n, p, d), q in production_plan.items() if d.weekday() >= 5)
    assert weekday_production > weekend_production
```

**TC-UG-005: Campaign Pattern - Four Weeks**
```python
def test_campaign_pattern_four_weeks():
    """Test campaign pattern generation for 4 weeks."""
    # Given: 5 products, 4 week horizon
    generator = create_generator_four_weeks()
    demand = aggregate_four_week_demand()

    # When: Generate campaign pattern
    production_plan = generator._generate_campaign_pattern(demand)

    # Then: Validate production plan
    # All products produced weekly
    for week in range(4):
        week_start = generator.start_date + timedelta(weeks=week)
        week_end = week_start + timedelta(days=7)
        week_products = set(
            p for (n, p, d), q in production_plan.items()
            if week_start <= d < week_end and q > 0
        )
        assert len(week_products) == 5  # All 5 products in each week
```

**TC-UG-006: Campaign Pattern - High Demand (Capacity Test)**
```python
def test_campaign_pattern_high_demand():
    """Test campaign pattern when demand exceeds regular capacity."""
    # Given: High demand week (>84,000 units)
    generator = create_generator_high_demand()
    demand = {'PROD_001': 100000}  # Exceeds weekly regular capacity

    # When: Generate campaign pattern
    production_plan = generator._generate_campaign_pattern(demand)

    # Then: Uses overtime or weekend production
    total_production = sum(production_plan.values())
    assert total_production >= 100000

    # Should use overtime (>16,800 units/day) or weekend
    max_daily = max(
        sum(q for (n, p, d), q in production_plan.items() if d == date)
        for date in get_unique_dates(production_plan)
    )
    has_overtime = max_daily > 16800
    has_weekend = any(
        d.weekday() >= 5 and q > 0
        for (n, p, d), q in production_plan.items()
    )
    assert has_overtime or has_weekend
```

**TC-UG-007: Warmstart Format Conversion**
```python
def test_production_to_warmstart_format():
    """Test conversion of production plan to warmstart format."""
    # Given: Production plan
    production_plan = {
        ('6122', 'PROD_001', date(2025, 10, 20)): 5000.0,
        ('6122', 'PROD_002', date(2025, 10, 20)): 4500.0,
    }

    # When: Convert to warmstart format
    generator = create_generator()
    warmstart = generator._production_to_warmstart(production_plan)

    # Then: Warmstart has correct structure
    # Production variables
    assert ('production', ('6122', date(2025, 10, 20), 'PROD_001')) in warmstart
    assert warmstart[('production', ('6122', date(2025, 10, 20), 'PROD_001'))] == 5000.0

    # Binary indicators
    assert ('product_produced', ('6122', 'PROD_001', date(2025, 10, 20))) in warmstart
    assert warmstart[('product_produced', ('6122', 'PROD_001', date(2025, 10, 20)))] == 1.0

    # Changeover count
    assert ('num_products_produced', ('6122', date(2025, 10, 20))) in warmstart
    assert warmstart[('num_products_produced', ('6122', date(2025, 10, 20)))] == 2
```

**TC-UG-008: Binary Indicators Correctness**
```python
def test_warmstart_binary_indicators():
    """Test binary indicators are 0 or 1."""
    # Given: Generator with production plan
    generator = create_generator()
    warmstart = generator.generate()

    # When: Filter binary indicators
    binary_vars = [
        (k, v) for k, v in warmstart.items()
        if k[0] == 'product_produced'
    ]

    # Then: All values are 0 or 1
    for key, value in binary_vars:
        assert value in [0.0, 1.0]
```

**TC-UG-009: Integer Counts Correctness**
```python
def test_warmstart_integer_counts():
    """Test integer counts are valid integers."""
    # Given: Generator with production plan
    generator = create_generator()
    warmstart = generator.generate()

    # When: Filter integer counts
    integer_vars = [
        (k, v) for k, v in warmstart.items()
        if k[0] == 'num_products_produced'
    ]

    # Then: All values are integers
    for key, value in integer_vars:
        assert isinstance(value, int) or value == int(value)
        assert 0 <= value <= 5  # Max 5 products
```

---

### Suite 2: Unit Tests - BaseModel Warmstart Application

**File:** `tests/test_base_model_warmstart.py`
**Purpose:** Test warmstart application in BaseOptimizationModel

#### Test Cases

**TC-BM-001: Apply Valid Warmstart**
```python
def test_apply_warmstart_valid_values():
    """Test applying warmstart with valid values."""
    # Given: Model with variables and warmstart values
    model = create_simple_model()
    warmstart = {
        ('x', ()): 5.0,
        ('y', (1,)): 10.0,
    }

    # When: Apply warmstart
    base_model = BaseOptimizationModel()
    base_model.model = model
    base_model._apply_warmstart(model, warmstart)

    # Then: Variables have initial values
    assert model.x.value == 5.0
    assert model.y[1].value == 10.0
```

**TC-BM-002: Invalid Variable Name**
```python
def test_apply_warmstart_invalid_variable():
    """Test applying warmstart with invalid variable name."""
    # Given: Warmstart with non-existent variable
    model = create_simple_model()
    warmstart = {
        ('invalid_var', ()): 5.0,
    }

    # When: Apply warmstart
    base_model = BaseOptimizationModel()
    base_model.model = model

    # Then: No exception, warning issued
    with pytest.warns(UserWarning):
        base_model._apply_warmstart(model, warmstart)
```

**TC-BM-003: Invalid Index**
```python
def test_apply_warmstart_invalid_index():
    """Test applying warmstart with invalid index."""
    # Given: Warmstart with invalid index
    model = create_simple_model()
    warmstart = {
        ('y', (999,)): 10.0,  # Index 999 doesn't exist
    }

    # When: Apply warmstart
    base_model = BaseOptimizationModel()
    base_model.model = model

    # Then: No exception, warning issued
    with pytest.warns(UserWarning):
        base_model._apply_warmstart(model, warmstart)
```

**TC-BM-004: Type Mismatch**
```python
def test_apply_warmstart_type_mismatch():
    """Test applying warmstart with type mismatch."""
    # Given: Integer variable with float warmstart
    model = create_model_with_integer_vars()
    warmstart = {
        ('int_var', ()): 5.5,  # Float for integer variable
    }

    # When: Apply warmstart
    base_model = BaseOptimizationModel()
    base_model.model = model

    # Then: Warning issued (Pyomo may handle or reject)
    with pytest.warns(UserWarning):
        base_model._apply_warmstart(model, warmstart)
```

**TC-BM-005: Empty Warmstart**
```python
def test_apply_warmstart_empty_dict():
    """Test applying empty warmstart."""
    # Given: Empty warmstart
    model = create_simple_model()
    warmstart = {}

    # When: Apply warmstart
    base_model = BaseOptimizationModel()
    base_model.model = model
    base_model._apply_warmstart(model, warmstart)

    # Then: No error, no variables initialized
    assert model.x.value is None
```

**TC-BM-006: Partial Coverage**
```python
def test_apply_warmstart_partial_coverage():
    """Test applying warmstart with partial variable coverage."""
    # Given: Warmstart for subset of variables
    model = create_model_with_many_vars()
    warmstart = {
        ('x', ()): 5.0,  # Only x initialized, y and z not
    }

    # When: Apply warmstart
    base_model = BaseOptimizationModel()
    base_model.model = model
    base_model._apply_warmstart(model, warmstart)

    # Then: Only x initialized
    assert model.x.value == 5.0
    assert model.y.value is None
    assert model.z.value is None
```

---

### Suite 3: Integration Tests

**File:** `tests/test_warmstart_integration.py`
**Purpose:** Test end-to-end warmstart workflow

#### Test Cases

**TC-INT-001: Solve with Warmstart**
```python
def test_unified_model_solve_with_warmstart():
    """Test UnifiedNodeModel.solve() with warmstart enabled."""
    # Given: Model with real data
    model = create_unified_model_from_files()

    # When: Solve with warmstart
    result = model.solve(use_warmstart=True)

    # Then: Solve succeeds
    assert result.is_feasible()
    assert result.solve_time_seconds < 120  # Within timeout
```

**TC-INT-002: Solve without Warmstart**
```python
def test_unified_model_solve_without_warmstart():
    """Test UnifiedNodeModel.solve() with warmstart disabled."""
    # Given: Model with real data
    model = create_unified_model_from_files()

    # When: Solve without warmstart
    result = model.solve(use_warmstart=False)

    # Then: Solve succeeds (but slower)
    assert result.is_feasible()
```

**TC-INT-003: Warmstart Generation Failure**
```python
def test_warmstart_generation_failure_handling():
    """Test graceful degradation when warmstart generation fails."""
    # Given: Model with invalid data (to trigger generation failure)
    model = create_model_with_invalid_data()

    # When: Solve with warmstart (expect generation to fail)
    with pytest.warns(UserWarning, match="Warmstart generation failed"):
        result = model.solve(use_warmstart=True)

    # Then: Solve continues without warmstart
    # Should still get a result (may be infeasible)
```

**TC-INT-004: Real Dataset Test**
```python
def test_warmstart_with_real_dataset():
    """Test warmstart with GFree Forecast.xlsm."""
    # Given: Real data files
    model = load_model_from_excel(
        forecast_file='data/examples/GFree Forecast.xlsm',
        config_file='data/examples/Network_Config.xlsx'
    )

    # When: Solve with warmstart
    result = model.solve(
        use_warmstart=True,
        time_limit_seconds=120,
        mip_gap=0.01
    )

    # Then: Performance target met
    assert result.is_feasible()
    assert result.solve_time_seconds < 120
    assert result.gap < 0.01
```

**TC-INT-005: Backward Compatibility**
```python
def test_warmstart_backward_compatibility():
    """Test that existing code works unchanged."""
    # Given: Model with no warmstart parameter
    model = create_unified_model_from_files()

    # When: Call solve() without warmstart parameter (old API)
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=120
    )

    # Then: Solve succeeds (warmstart enabled by default)
    assert result.is_feasible()
```

---

### Suite 4: Performance Tests

**File:** `tests/test_warmstart_performance.py`
**Purpose:** Measure warmstart performance impact

#### Test Cases

**TC-PERF-001: Baseline Solve Time**
```python
def test_baseline_solve_time_measurement():
    """Measure baseline solve time without warmstart."""
    # Given: Model with 4-week horizon
    model = create_four_week_model()

    # When: Solve without warmstart (10 runs)
    solve_times = []
    for i in range(10):
        result = model.solve(use_warmstart=False, time_limit_seconds=300)
        solve_times.append(result.solve_time_seconds)

    # Then: Record baseline
    baseline_avg = sum(solve_times) / len(solve_times)
    print(f"Baseline average: {baseline_avg:.2f}s")
    assert baseline_avg > 30  # Should be slow without warmstart
```

**TC-PERF-002: Warmstart Solve Time**
```python
def test_warmstart_solve_time_measurement():
    """Measure solve time with warmstart."""
    # Given: Model with 4-week horizon
    model = create_four_week_model()

    # When: Solve with warmstart (10 runs)
    solve_times = []
    for i in range(10):
        result = model.solve(use_warmstart=True, time_limit_seconds=300)
        solve_times.append(result.solve_time_seconds)

    # Then: Record warmstart time
    warmstart_avg = sum(solve_times) / len(solve_times)
    print(f"Warmstart average: {warmstart_avg:.2f}s")
    assert warmstart_avg < 120  # Should be faster
```

**TC-PERF-003: Time Reduction Validation**
```python
def test_warmstart_time_reduction_validation():
    """Validate warmstart achieves 20-40% time reduction."""
    # Given: Baseline and warmstart solve times
    baseline_time = measure_baseline_time()
    warmstart_time = measure_warmstart_time()

    # When: Calculate reduction
    reduction_pct = ((baseline_time - warmstart_time) / baseline_time) * 100

    # Then: Meets target
    print(f"Time reduction: {reduction_pct:.1f}%")
    assert reduction_pct >= 20  # At least 20% reduction
    assert reduction_pct <= 60  # Realistic upper bound
```

**TC-PERF-004: Objective Value Comparison**
```python
def test_warmstart_objective_value_comparison():
    """Verify warmstart doesn't degrade objective value."""
    # Given: Model with fixed seed
    model = create_deterministic_model()

    # When: Solve with and without warmstart
    result_baseline = model.solve(use_warmstart=False)
    result_warmstart = model.solve(use_warmstart=True)

    # Then: Objective values similar
    assert result_baseline.is_feasible()
    assert result_warmstart.is_feasible()

    obj_diff_pct = abs(
        (result_warmstart.objective_value - result_baseline.objective_value)
        / result_baseline.objective_value
    ) * 100

    print(f"Objective difference: {obj_diff_pct:.2f}%")
    assert obj_diff_pct < 1.0  # Less than 1% difference
```

**TC-PERF-005: Warmstart Generation Overhead**
```python
def test_warmstart_generation_overhead():
    """Measure warmstart generation time overhead."""
    # Given: Model with 4-week horizon
    model = create_four_week_model()

    # When: Measure generation time
    import time
    start = time.time()
    generator = WarmstartGenerator(model)
    warmstart = generator.generate()
    generation_time = time.time() - start

    # Then: Overhead acceptable
    print(f"Generation time: {generation_time:.2f}s")
    assert generation_time < 5.0  # Less than 5 seconds
```

---

## Test Data

### Test Fixtures

**Simple Model (1 product, 1 week):**
```python
@pytest.fixture
def simple_model():
    """Create model with 1 product, 1 week horizon."""
    return create_model(
        products=['PROD_001'],
        start_date=date(2025, 10, 20),
        end_date=date(2025, 10, 26),
        demand={'PROD_001': 10000}
    )
```

**Standard Model (5 products, 4 weeks):**
```python
@pytest.fixture
def standard_model():
    """Create model with 5 products, 4 week horizon."""
    return create_model(
        products=['PROD_001', 'PROD_002', 'PROD_003', 'PROD_004', 'PROD_005'],
        start_date=date(2025, 10, 20),
        end_date=date(2025, 11, 16),
        demand={
            'PROD_001': 50000,
            'PROD_002': 40000,
            'PROD_003': 35000,
            'PROD_004': 30000,
            'PROD_005': 25000,
        }
    )
```

**High Demand Model:**
```python
@pytest.fixture
def high_demand_model():
    """Create model with high demand (capacity test)."""
    return create_model(
        products=['PROD_001'],
        start_date=date(2025, 10, 20),
        end_date=date(2025, 10, 26),
        demand={'PROD_001': 100000}  # Exceeds weekly regular capacity
    )
```

---

## Test Execution

### Local Testing
```bash
# Run all warmstart tests
pytest tests/test_warmstart*.py -v

# Run with coverage
pytest tests/test_warmstart*.py --cov=src/optimization --cov-report=html

# Run performance tests only
pytest tests/test_warmstart_performance.py -v --durations=10

# Run integration tests only
pytest tests/test_warmstart_integration.py -v
```

### CI/CD Integration
```yaml
# .github/workflows/test.yml (example)
- name: Run warmstart tests
  run: |
    pytest tests/test_warmstart*.py --cov=src/optimization --cov-report=xml

- name: Check performance regression
  run: |
    pytest tests/test_warmstart_performance.py --benchmark-only
```

---

## Success Criteria

### Unit Tests
- ✅ All unit tests pass
- ✅ Code coverage >80%
- ✅ No flaky tests

### Integration Tests
- ✅ Warmstart enabled by default works
- ✅ Warmstart disabled works
- ✅ Real dataset test passes
- ✅ Backward compatibility maintained

### Performance Tests
- ✅ Time reduction ≥20%
- ✅ Solve time <120s for 4-week horizon
- ✅ Objective value unchanged (within 1%)
- ✅ Generation overhead <5s

---

## Test Report Template

```markdown
# Warmstart Test Report

**Date:** YYYY-MM-DD
**Test Suite Version:** X.X.X
**Environment:** [Local/CI/CD]

## Summary
- Total Tests: X
- Passed: X
- Failed: X
- Skipped: X
- Coverage: X%

## Performance Metrics
- Baseline Solve Time: Xs
- Warmstart Solve Time: Xs
- Time Reduction: X%
- Objective Difference: X%
- Generation Overhead: Xs

## Failed Tests
[List of failed tests with reasons]

## Recommendations
[Improvements or fixes needed]
```

---

## Timeline

- **Week 1:** Implement unit tests (Suite 1, Suite 2)
- **Week 2:** Implement integration tests (Suite 3)
- **Week 3:** Implement performance tests (Suite 4)
- **Week 4:** Performance tuning and optimization

---

## Dependencies

**Upstream:**
- python-pro implementation complete
- warmstart_generator.py implemented
- base_model.py modifications complete
- unified_node_model.py modifications complete

**Downstream:**
- code-reviewer validation

---

## Status

- [ ] Test plan reviewed
- [ ] Test fixtures created
- [ ] Unit tests implemented
- [ ] Integration tests implemented
- [ ] Performance tests implemented
- [ ] All tests passing
- [ ] Coverage target met
- [ ] Performance targets met
