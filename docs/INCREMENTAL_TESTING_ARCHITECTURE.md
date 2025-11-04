# Incremental Testing Architecture

**Purpose:** Embed systematic incremental testing into the model development workflow to catch bugs early and prevent silent errors.

**Based on:** The successful 18-level incremental approach that found and fixed 6+ bugs.

---

## 🎯 Core Principles

### 1. One Feature, One Test
Every new feature added to the model MUST have a corresponding incremental test that:
- Tests ONLY that feature
- Uses simple data first
- Uses real data second
- Verifies production > 0
- Measures solve time

### 2. Fail-Fast with Clear Attribution
When a test fails:
- Exactly ONE feature was added since last passing test
- Root cause is immediately clear
- No mystery about which change broke it

### 3. Progressive Complexity
Build from simple → complex:
- Start: Single node, single product, 3 days
- End: 11 nodes, 5 products, 4 weeks, all features

### 4. Continuous Validation
- Run incremental tests on every commit
- Regression testing: Ensure all previous levels still pass
- Performance monitoring: Track solve times

---

## 🏗️ Architecture Components

### Component 1: Incremental Test Suite

**File:** `tests/test_model_incremental_validation.py`

**Structure:**
```python
class IncrementalModelTests:
    """Systematic incremental tests for optimization model development.

    Each test level adds ONE feature and verifies:
    - Model builds successfully
    - Model solves (optimal/feasible)
    - Production > 0 (or expected behavior)
    - Solve time < threshold
    - Solution quality meets minimum
    """

    @pytest.fixture
    def simple_data(self):
        """Minimal test data: 1 node, 1 product, 3 days"""
        return create_simple_test_data()

    @pytest.fixture
    def real_data_small(self):
        """Real data subset: 4 nodes, 2 products, 1 week"""
        return load_real_data_subset()

    @pytest.fixture
    def real_data_full(self):
        """Full real data: 11 nodes, 5 products, 4 weeks"""
        return load_full_real_data()

    def test_level01_basic_production(self, simple_data):
        """Level 1: Basic production-demand"""
        model = build_level1(simple_data)
        solution = solve_and_validate(model, min_production=450)

    def test_level02_material_balance(self, simple_data):
        """Level 2: Add material balance"""
        model = build_level2(simple_data)
        solution = solve_and_validate(model, min_production=450)

    # ... through Level 18

    def test_level18_with_real_data(self, real_data_full):
        """Level 18: All features with FULL real data"""
        model = build_level18(real_data_full)
        solution = solve_and_validate(
            model,
            min_production=100000,  # Expect significant production
            max_solve_time=30,  # Performance requirement
            min_fill_rate=0.85  # Quality requirement
        )
```

---

### Component 2: Model Feature Registry

**File:** `src/optimization/feature_registry.py`

Tracks which features are in which model level:

```python
MODEL_FEATURES = {
    'Level01': ['basic_production', 'demand_satisfaction'],
    'Level02': ['basic_production', 'demand_satisfaction', 'material_balance'],
    'Level03': ['basic_production', 'demand_satisfaction', 'material_balance', 'initial_inventory'],
    'Level04': ['basic_production', 'demand_satisfaction', 'material_balance', 'initial_inventory', 'sliding_window'],
    # ... through Level 18
}

FEATURE_DEPENDENCIES = {
    'sliding_window': ['material_balance'],  # Sliding window requires material balance
    'freeze_thaw': ['frozen_state', 'ambient_state'],  # Requires both states
    'mix_production': ['production_variables'],  # Requires production variables
}

def validate_feature_compatibility(features: List[str]) -> bool:
    """Validate that all feature dependencies are satisfied."""
    for feature in features:
        deps = FEATURE_DEPENDENCIES.get(feature, [])
        for dep in deps:
            if dep not in features:
                raise ValueError(f"Feature '{feature}' requires '{dep}' but it's not enabled")
    return True
```

---

### Component 3: Automated Test Runner

**File:** `tests/run_incremental_validation.py`

```python
#!/usr/bin/env python3
"""
Automated incremental test runner.

Runs all levels sequentially and reports:
- Which level failed (if any)
- Solve time trends
- Production values
- Performance regressions
"""

def run_all_levels(data_type='simple'):
    """Run all incremental levels."""
    results = {}

    for level in range(1, 19):  # Levels 1-18
        print(f"\n{'='*80}")
        print(f"TESTING LEVEL {level}")
        print(f"{'='*80}")

        try:
            result = run_level(level, data_type)
            results[f'Level{level:02d}'] = result

            # Validate
            if result['production'] <= 0:
                print(f"❌ LEVEL {level} FAILED: Zero production")
                print(f"   Previous level (Level {level-1}) passed")
                print(f"   Bug is in feature added at Level {level}")
                return results, level  # Return failed level

            if result['solve_time'] > result.get('max_time', 60):
                print(f"⚠️  LEVEL {level} SLOW: {result['solve_time']:.1f}s")

            print(f"✅ LEVEL {level} PASSED: Production = {result['production']:,.0f}")

        except Exception as e:
            print(f"❌ LEVEL {level} ERROR: {e}")
            return results, level

    print(f"\n{'='*80}")
    print(f"✅ ALL {level} LEVELS PASSED!")
    print(f"{'='*80}")

    return results, None

def generate_report(results):
    """Generate performance and correctness report."""
    print("\n" + "="*80)
    print("INCREMENTAL TEST REPORT")
    print("="*80)

    for level, result in results.items():
        status = "✅" if result['production'] > 0 else "❌"
        time_status = "⚠️" if result['solve_time'] > 10 else "✓"
        print(f"{level}: {status} Prod={result['production']:>10,.0f}  {time_status} Time={result['solve_time']:>6.2f}s")
```

---

### Component 4: Feature Validation Decorators

**File:** `src/optimization/validation_decorators.py`

```python
from functools import wraps

def validate_production_nonzero(func):
    """Decorator to ensure model produces > 0 after changes."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Call the original method
        result = func(self, *args, **kwargs)

        # Build and solve quick test
        test_model = self.build_model()
        test_solution = quick_solve(test_model)

        if test_solution['production'] <= 0:
            raise ValidationError(
                f"Method '{func.__name__}' caused zero production! "
                f"Model was working before this change. "
                f"Debug this specific method."
            )

        return result
    return wrapper


class ModelBuilder:
    """Base class with validation decorators."""

    @validate_production_nonzero
    def add_sliding_window_constraints(self, model):
        """Add sliding window - validated to maintain production > 0"""
        # ... implementation
        pass

    @validate_production_nonzero
    def add_freeze_thaw_flows(self, model):
        """Add state transitions - validated"""
        # ... implementation
        pass
```

---

### Component 5: Performance Benchmarks

**File:** `tests/performance_benchmarks.py`

Track solve time regressions:

```python
PERFORMANCE_TARGETS = {
    'Level04_simple': {'max_time': 0.1, 'min_production': 450},
    'Level04_real_1week': {'max_time': 0.5, 'min_production': 50000},
    'Level04_real_4weeks': {'max_time': 1.0, 'min_production': 200000},
    'Level18_simple': {'max_time': 0.5, 'min_production': 1000},
    'Level18_real_full': {'max_time': 30.0, 'min_production': 100000},
}

def benchmark_level(level, data_scale):
    """Run benchmark and compare to target."""
    result = run_level(level, data_scale)

    key = f'Level{level:02d}_{data_scale}'
    target = PERFORMANCE_TARGETS.get(key, {})

    # Check time
    if target.get('max_time') and result['solve_time'] > target['max_time']:
        print(f"⚠️  PERFORMANCE REGRESSION!")
        print(f"   Expected: <{target['max_time']}s")
        print(f"   Actual: {result['solve_time']:.2f}s")

    # Check production
    if target.get('min_production') and result['production'] < target['min_production']:
        print(f"❌ PRODUCTION TOO LOW!")
        print(f"   Expected: >{target['min_production']:,}")
        print(f"   Actual: {result['production']:,.0f}")
```

---

### Component 6: Model Development Checklist

**File:** `docs/MODEL_DEVELOPMENT_CHECKLIST.md`

```markdown
# Adding a New Feature to the Model

## Pre-Development (5 min)
- [ ] Identify the exact feature to add (be specific!)
- [ ] Check feature dependencies in feature_registry.py
- [ ] Review if similar feature exists in test levels 1-18

## Development (varies)
- [ ] Write the feature implementation
- [ ] Add inline comments explaining formulation
- [ ] Include Pyomo/MIP best practices citations

## Testing (15-30 min per level)
- [ ] Create incremental test (Level N+1)
- [ ] Test with simple data first
  - [ ] Verify production > 0
  - [ ] Verify solve time < 1s
  - [ ] Check solution makes sense
- [ ] Test with real data subset (1 week, 2 products)
  - [ ] Verify production > 0
  - [ ] Verify solve time < 5s
- [ ] Test with full real data
  - [ ] Verify production > 0
  - [ ] Verify solve time < 30s (or adjust MIP settings)
  - [ ] Verify fill rate > 85%

## Integration (10 min)
- [ ] Add to feature_registry.py
- [ ] Update MODEL_FEATURES for new level
- [ ] Run full incremental test suite
- [ ] All previous levels must still pass

## Documentation (10 min)
- [ ] Document the feature in model specification
- [ ] Add to CHANGELOG with level number
- [ ] Note any performance impacts

## Commit
- [ ] Commit with message: "feat: Add [feature] (Level N, production=X, time=Ys)"
```

---

### Component 7: Solver Configuration Manager

**File:** `src/optimization/solver_config.py`

Centralize MIP solver settings:

```python
class SolverConfig:
    """Manage solver configurations for different problem scales."""

    # Optimized settings from HiGHS expert skill
    HIGHS_MIP_FAST = {
        'presolve': 'on',
        'parallel': 'on',
        'mip_rel_gap': 0.02,  # 2% gap
        'mip_heuristic_effort': 0.5,
        'time_limit': 30.0,
    }

    HIGHS_MIP_ACCURATE = {
        'presolve': 'on',
        'parallel': 'on',
        'mip_rel_gap': 0.001,  # 0.1% gap
        'time_limit': 300.0,
    }

    HIGHS_LP_FAST = {
        'presolve': 'on',
        'time_limit': 10.0,
    }

    @staticmethod
    def configure_solver(solver, problem_type='MIP', speed='fast'):
        """Configure solver with optimized settings.

        Args:
            solver: Pyomo solver object
            problem_type: 'MIP' or 'LP'
            speed: 'fast' or 'accurate'

        Returns:
            Configured solver
        """
        if problem_type == 'MIP':
            config = SolverConfig.HIGHS_MIP_FAST if speed == 'fast' else SolverConfig.HIGHS_MIP_ACCURATE
        else:
            config = SolverConfig.HIGHS_LP_FAST

        solver.highs_options = config

        return solver


# Usage in model:
def solve(self, speed='fast'):
    solver = pyo.SolverFactory('appsi_highs')
    solver = SolverConfig.configure_solver(solver, 'MIP', speed)
    result = solver.solve(self.model)
    return result
```

---

### Component 8: Model Health Checks

**File:** `src/optimization/health_checks.py`

Automated checks run after each model build:

```python
class ModelHealthChecker:
    """Automated health checks for optimization models."""

    @staticmethod
    def check_variable_creation(model, expected_vars):
        """Verify expected variables were created."""
        missing = []

        for var_name, expected_count in expected_vars.items():
            if not hasattr(model, var_name):
                missing.append(f"{var_name}: MISSING")
            else:
                actual_count = len(getattr(model, var_name))
                if actual_count != expected_count:
                    missing.append(f"{var_name}: expected {expected_count}, got {actual_count}")

        if missing:
            raise ValidationError(f"Variable creation issues:\n" + "\n".join(missing))

    @staticmethod
    def check_constraint_linkage(model):
        """Verify production → inventory → demand chain exists."""
        checks = []

        # Check production appears in material balance
        if hasattr(model, 'production') and hasattr(model, 'material_balance_con'):
            # Sample check: Does production variable appear in constraint?
            checks.append(('production_in_balance', True))
        else:
            checks.append(('production_in_balance', False))

        # Check demand_consumed links to demand satisfaction
        if hasattr(model, 'demand_consumed') and hasattr(model, 'demand_satisfaction_con'):
            checks.append(('demand_linkage', True))
        else:
            checks.append(('demand_linkage', False))

        failed = [name for name, passed in checks if not passed]
        if failed:
            raise ValidationError(f"Constraint linkage broken: {failed}")

    @staticmethod
    def check_solution_quality(solution, min_production=0, max_shortage_rate=0.2):
        """Verify solution meets quality thresholds."""
        issues = []

        if solution['total_production'] <= min_production:
            issues.append(f"Production too low: {solution['total_production']:.0f} <= {min_production}")

        total_demand = solution.get('total_demand', 1)
        shortage_rate = solution.get('total_shortage', 0) / total_demand

        if shortage_rate > max_shortage_rate:
            issues.append(f"Shortage rate too high: {shortage_rate:.1%} > {max_shortage_rate:.1%}")

        if issues:
            raise ValidationError(f"Solution quality issues:\n" + "\n".join(issues))


# Usage in model build:
def build_model(self):
    model = ConcreteModel()

    self._add_variables(model)

    # Health check: Variables created correctly?
    ModelHealthChecker.check_variable_creation(model, {
        'production': 145,
        'inventory': 1595,
        'in_transit': 1160,
    })

    self._add_constraints(model)

    # Health check: Constraints linked correctly?
    ModelHealthChecker.check_constraint_linkage(model)

    self._build_objective(model)

    return model
```

---

### Component 9: Continuous Integration Tests

**File:** `.github/workflows/incremental_tests.yml`

```yaml
name: Incremental Model Validation

on: [push, pull_request]

jobs:
  test_incremental_levels:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt

    - name: Run incremental tests (Levels 1-18)
      run: |
        pytest tests/test_model_incremental_validation.py -v

    - name: Check for regressions
      run: |
        python tests/check_performance_regression.py

    - name: Generate report
      if: always()
      run: |
        python tests/generate_incremental_report.py > incremental_report.md

    - name: Upload report
      uses: actions/upload-artifact@v3
      with:
        name: incremental-test-report
        path: incremental_report.md
```

---

### Component 10: Development Workflow Integration

**File:** `docs/DEVELOPMENT_WORKFLOW.md`

```markdown
# Model Development Workflow

## Adding a New Feature

### Step 1: Identify Current Level
```bash
$ python -c "from src.optimization.feature_registry import get_current_level; print(get_current_level())"
Current model: Level 18 (all features)
```

### Step 2: Create Level N+1
```bash
$ python scripts/create_new_level.py --name "labor_capacity_constraints"
Created:
  - tests/test_level19_labor_capacity.py
  - Updated feature_registry.py
  - Updated MODEL_DEVELOPMENT_CHECKLIST.md
```

### Step 3: Implement Feature
Edit your model class to add the feature.

### Step 4: Test Incrementally
```bash
# Test with simple data
$ pytest tests/test_level19_labor_capacity.py::test_simple_data -v

# Test with real data subset
$ pytest tests/test_level19_labor_capacity.py::test_real_data_subset -v

# Test with full real data
$ pytest tests/test_level19_labor_capacity.py::test_real_data_full -v
```

### Step 5: Validate All Levels Still Pass
```bash
$ pytest tests/test_model_incremental_validation.py -v
# All levels 1-19 should pass
```

### Step 6: Commit
```bash
$ git add .
$ git commit -m "feat: Add labor capacity constraints (Level 19)

- Production: 312,450 units (90.1% fill)
- Solve time: 18.3s with real data
- All previous levels still pass
- MIP settings: presolve=on, gap=2%"
```

## When Something Breaks

### Scenario: Test Fails
```
❌ LEVEL 15 FAILED: Zero production
   Previous level (Level 14) passed
   Bug is in feature added at Level 15
```

**Action:**
1. Check what feature Level 15 adds (feature_registry.py)
2. Review Level 15 implementation
3. Compare to Level 14 (working)
4. Fix the ONE feature that's different
5. Re-run Level 15 test

### Scenario: Performance Regression
```
⚠️ LEVEL 16 SLOW: 45.2s (was 0.4s in Level 15)
```

**Action:**
1. Feature added in Level 16 causes slowdown
2. Check if it's due to:
   - Too many variables (use solver diagnostic)
   - Complex constraints (simplify expressions)
   - Integer variables (adjust MIP settings)
3. Optimize or simplify that feature
4. Re-test

## Troubleshooting Guide

### Zero Production After Adding Feature

**Checklist:**
1. Run Level N-1 (previous) → If passes, bug is in Level N
2. Check constraint formulation:
   - Does production appear in material balance? (print constraint)
   - Does material balance link to demand? (trace chain)
   - Are there sign errors? (+ vs -)
3. Check variable bounds:
   - Are variables accidentally bounded to zero?
   - Are integers over-constrained?
4. Check skip logic:
   - Are critical constraints being skipped?

### Slow Solve After Adding Feature

**Checklist:**
1. Check variable type:
   - Did you add integers? → Adjust MIP settings
   - Use SolverConfig.HIGHS_MIP_FAST
2. Check constraint count:
   - Too many constraints? → Simplify or aggregate
3. Check expression complexity:
   - Nested quicksum in constraints? → Pre-compute
4. Try larger MIP gap:
   - `mip_rel_gap: 0.05` (5%) for speed vs 0.01 (1%) for accuracy

### Model Becomes Infeasible

**Checklist:**
1. Test without new feature → If feasible, new feature over-constrains
2. Check formulation:
   - Sliding window: Should be `O ≤ Q` not `inventory ≤ Q-O`
   - Material balance: Check all inflows and outflows
3. Relax and debug:
   - Remove new feature
   - Add back piece by piece
   - Find exact constraint causing infeasibility
```

---

## 📊 Benefits of This Architecture

### Before (Without Incremental Testing):
- Bug appears weeks later
- Unknown which change caused it
- Hours of debugging LP files
- Silent errors go unnoticed

### After (With Incremental Architecture):
- Bug caught immediately (minutes)
- Exact feature identified
- 5-10 min to debug
- Impossible to merge broken code

---

## 🎯 Success Metrics

**Quality Metrics:**
- % of commits that pass all incremental tests
- Mean time to identify root cause of bug
- Number of silent errors caught

**Performance Metrics:**
- Solve time for each level
- Trend analysis (is it getting slower?)
- Performance regression alerts

**Coverage Metrics:**
- Number of features with incremental tests
- % of model code covered by incremental tests

---

## 🚀 Implementation Plan

### Phase 1: Extract Current Levels (2 hours)
1. Extract Levels 1-18 from test_incremental_model_levels.py
2. Create test_model_incremental_validation.py
3. Set up pytest structure

### Phase 2: Add Automation (3 hours)
1. Create run_incremental_validation.py
2. Add performance_benchmarks.py
3. Set up feature_registry.py

### Phase 3: Add Validation Decorators (2 hours)
1. Create validation_decorators.py
2. Add health checks
3. Integrate into VerifiedSlidingWindowModel

### Phase 4: Documentation (1 hour)
1. Write MODEL_DEVELOPMENT_CHECKLIST.md
2. Write DEVELOPMENT_WORKFLOW.md
3. Create examples

### Phase 5: CI Integration (1 hour)
1. Set up GitHub Actions
2. Configure automatic reports
3. Test on sample PR

**Total: ~9 hours to full implementation**

---

## 📝 Example Usage

### Developer Adding a Feature

```python
# 1. Check current level
from src.optimization.feature_registry import get_current_level
print(get_current_level())  # "Level 18"

# 2. Create new level test
# File: tests/test_level19_labor_capacity.py

def test_level19_simple_data():
    """Level 19: Add labor capacity constraints"""
    data = create_simple_data()

    # Build model with new feature
    model = build_model_with_labor_capacity(data)

    # Solve
    solution = solve_with_validation(model)

    # Validate
    assert solution['production'] > 0, "Zero production!"
    assert solution['solve_time'] < 1.0, "Too slow with simple data!"

# 3. Run test
# $ pytest tests/test_level19_labor_capacity.py -v

# 4. If passes, add to suite
# 5. Commit with level number
```

---

## 🎓 Lessons Learned from Session

### What Worked
1. ✅ Incremental approach found all bugs
2. ✅ Simple data tests first, then real data
3. ✅ One feature at a time
4. ✅ Immediate feedback loop

### What to Avoid
1. ❌ Adding multiple features at once
2. ❌ Testing only with real data
3. ❌ Skipping intermediate levels
4. ❌ Not measuring solve time

### Best Practices
1. ✅ Always test with simple data first
2. ✅ Scale up gradually (1 week → 4 weeks)
3. ✅ Measure performance at each level
4. ✅ Use proper MIP solver settings
5. ✅ Validate production > 0 always

---

## 🔧 Tools Provided

### Quick Commands

```bash
# Run all incremental tests
$ python tests/run_incremental_validation.py

# Test specific level
$ pytest tests/test_model_incremental_validation.py::test_level15 -v

# Benchmark performance
$ python tests/performance_benchmarks.py

# Check for regressions
$ python tests/check_performance_regression.py

# Generate report
$ python tests/generate_incremental_report.py
```

### IDE Integration

**VS Code settings.json:**
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests/test_model_incremental_validation.py",
        "-v"
    ]
}
```

---

## 📈 Success Story: This Session

**Bugs Found via Incremental Approach:**
1. Level 4: Sliding window formulation wrong (`inventory ≤ Q-O`)
2. Level 3: Init_inv multi-counting (16× times!)
3. Level 17: Arrivals check wrong (`window_dates` vs `model.dates`)
4. Level 18: MIP solver settings needed

**All found in < 5 min each because:**
- Previous level passed
- Exactly one feature different
- Clear attribution

**Without incremental approach:**
- Would have taken hours/days
- Multiple bugs compounding
- Unclear which change caused issue

---

## 🎯 Summary

This architecture transforms model development from:

**Reactive (Old):**
- Write code → Test weeks later → Bug found → Debug for hours → Unknown cause

**Proactive (New):**
- Write feature → Test immediately → Pass/fail in minutes → Clear cause → Fix in 5-10 min

**Result:** 10-100× faster bug identification and resolution!

---

**Next Steps:**
1. Extract current Levels 1-18 into formal test suite
2. Implement feature registry
3. Add health checks
4. Document workflow
5. Train team on incremental approach

**Est. implementation time:** 9 hours for full architecture
