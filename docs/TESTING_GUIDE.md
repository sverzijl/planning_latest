# Testing Guide - Production-Distribution Planning

**Last Updated:** November 9, 2025
**Test Count:** ~85 test files (down from 102 after cleanup)
**Model:** SlidingWindowModel (Primary - Only)

---

## Quick Reference

### Run All Tests
```bash
pytest tests/ -v
```
**Target:** ≥90% pass rate

### Run Critical Regression Gate
```bash
pytest tests/test_integration_ui_workflow.py -v
```
**REQUIRED:** Must pass before committing optimization changes

### Run Quick Validation
```bash
venv/bin/python tests/test_import_validation.py
```
**Target:** All imports valid

### Run Specific Category
```bash
pytest tests/test_labor_*.py -v          # Labor cost tests
pytest tests/test_inventory_*.py -v      # Inventory tests
pytest tests/test_solver_*.py -v         # Solver tests
pytest tests/test_ui_*.py -v             # UI integration tests
```

---

## Test Organization

### Test Categories

**1. Integration Tests** (~15 files)
- Test complete workflows with real data
- End-to-end validation
- Performance benchmarks
- Examples:
  - `test_integration_ui_workflow.py` - **CRITICAL**
  - `test_ui_integration_complete.py`
  - `test_sliding_window_ui_integration.py`

**2. Model Tests** (~25 files)
- SlidingWindowModel behavior
- Constraint validation
- Cost calculations
- Examples:
  - `test_labor_costs.py`
  - `test_holding_costs.py`
  - `test_warmstart.py`
  - `test_solvers.py`

**3. Unit Tests** (~45 files)
- Data models
- Parsers
- Validators
- Utilities
- Examples:
  - `test_models.py`
  - `test_parsers.py`
  - `test_data_validator.py`

---

## Critical Regression Tests

### 1. Integration UI Workflow (REQUIRED)

**File:** `tests/test_integration_ui_workflow.py`

**Purpose:** Validation gate for ALL optimization changes

**Tests:**
- `test_ui_workflow_4_weeks_with_initial_inventory` - Main test
- `test_ui_workflow_4_weeks_with_highs` - HiGHS solver validation
- `test_ui_workflow_without_initial_inventory` - Cold start
- `test_ui_workflow_with_warmstart` - Warmstart validation
- `test_ui_workflow_4_weeks_sliding_window` - Model-specific

**Requirements:**
- ✅ Performance: < 10s (baseline 5-7s)
- ✅ Fill rate: ≥ 85%
- ✅ Status: OPTIMAL or FEASIBLE
- ✅ MIP gap: < 1%

**Run before committing:**
```bash
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v
```

**If fails:** DO NOT COMMIT - fix the issue first

### 2. Import Validation (Pre-Commit Hook)

**File:** `tests/test_import_validation.py`

**Purpose:** Catch broken imports immediately

**Runs automatically:** On every commit (pre-commit hook)

**Tests:**
- Core optimization imports (SlidingWindowModel, solvers)
- Validation module imports
- Model imports
- Solver config completeness

**Manual run:**
```bash
venv/bin/python tests/test_import_validation.py
```

---

## Test Execution Groups

### Quick Tests (<1 min)
```bash
pytest tests/test_models.py tests/test_parsers.py tests/test_data_validator.py -v
```
**Use for:** Rapid feedback during development

### Integration Tests (2-5 min)
```bash
pytest tests/test_integration_*.py tests/test_ui_*.py -v
```
**Use for:** Pre-commit validation

### Regression Tests (5-10 min)
```bash
pytest tests/test_integration_ui_workflow.py -v
```
**Use for:** Before merging to main

### Performance Tests (>10 min)
```bash
pytest tests/test_solver_performance.py -v -m slow
```
**Use for:** Performance baseline tracking

---

## Writing New Tests

### Test Template

```python
"""
Brief description of what this test validates.

Test coverage:
- Specific feature or constraint
- Expected behavior
- Edge cases

Uses SlidingWindowModel (primary optimization model).
"""

import pytest
from datetime import date, timedelta

from src.optimization.sliding_window_model import SlidingWindowModel
from src.models import Product, CostStructure
# ... other imports


def test_feature_name():
    """Test specific feature behavior."""

    # Setup
    model = SlidingWindowModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        products=products,
        start_date=date(2025, 11, 10),
        end_date=date(2025, 11, 16),
        allow_shortages=True,
        use_pallet_tracking=True,
    )

    # Build and solve
    result = model.solve(solver_name='highs', mipgap=0.01, timelimit=120)
    solution = model.extract_solution()

    # Assertions
    assert solution.status == "optimal"
    assert solution.objective_value > 0
    # ... specific validations

    # Cleanup
    pass
```

### Test Naming Conventions

**Pattern:** `test_<category>_<feature>.py`

**Examples:**
- `test_labor_overtime.py` - Labor overtime costs
- `test_inventory_state_tracking.py` - State transitions
- `test_solver_performance.py` - Solver benchmarks
- `test_ui_integration_complete.py` - UI workflow

**Functions:** `test_<specific_behavior>`

**Examples:**
- `def test_overtime_avoided_when_possible():`
- `def test_frozen_to_thawed_transition():`
- `def test_highs_faster_than_cbc():`

---

## Test Fixtures

### Using conftest.py

**Shared fixtures in** `tests/conftest.py`:

```python
@pytest.fixture
def create_test_products():
    """Create standard test product dictionary."""
    # Returns {product_id: Product}

@pytest.fixture
def parsed_data():
    """Parse real data files (used by integration tests)."""
    # Returns complete dataset
```

### Creating Custom Fixtures

```python
@pytest.fixture
def simple_network():
    """Create minimal network for unit testing."""
    nodes = [
        UnifiedNode(id="6122", name="Manufacturing", ...),
        UnifiedNode(id="6104", name="Hub NSW", ...),
    ]
    routes = [
        UnifiedRoute(origin_id="6122", destination_id="6104", ...)
    ]
    return nodes, routes
```

---

## Common Test Patterns

### Pattern 1: Constraint Validation

**Purpose:** Verify optimization constraints work correctly

```python
def test_production_capacity_enforced():
    # Setup model with high demand
    model = SlidingWindowModel(...)

    # Solve
    result = model.solve()
    solution = model.extract_solution()

    # Verify production doesn't exceed capacity
    for batch in solution.production_batches:
        assert batch.quantity <= MAX_PRODUCTION_PER_DAY
```

### Pattern 2: Cost Calculation

**Purpose:** Verify costs computed correctly

```python
def test_labor_overtime_cost():
    # Setup scenario requiring overtime
    model = SlidingWindowModel(...)
    result = model.solve()
    solution = model.extract_solution()

    # Verify overtime costs present
    assert solution.total_costs['labor_costs']['overtime_cost'] > 0

    # Verify rate applied correctly
    expected_cost = overtime_hours * overtime_rate
    assert abs(actual_cost - expected_cost) < 0.01
```

### Pattern 3: Performance Validation

**Purpose:** Ensure solve times meet targets

```python
def test_4week_solve_under_10_seconds():
    model = SlidingWindowModel(...)

    start = time.time()
    result = model.solve(solver_name='highs')
    elapsed = time.time() - start

    assert elapsed < 10.0, f"Solve took {elapsed:.1f}s (target: <10s)"
```

### Pattern 4: Solution Quality

**Purpose:** Validate solution meets business requirements

```python
def test_demand_satisfied_at_least_85_percent():
    model = SlidingWindowModel(...)
    result = model.solve()
    solution = model.extract_solution()

    # Calculate fill rate
    total_demand = sum(solution.demand_consumed.values())
    total_required = sum(all_demand_values)
    fill_rate = total_demand / total_required

    assert fill_rate >= 0.85, f"Fill rate {fill_rate:.1%} below 85% target"
```

---

## Debugging Failed Tests

### Step 1: Identify Failure Type

**Import Error:**
```
ImportError: cannot import name 'UnifiedNodeModel'
```
→ Module archived or moved, update import to SlidingWindowModel

**Attribute Error:**
```
AttributeError: 'SlidingWindowModel' object has no attribute 'production_dates'
```
→ Attribute name changed, use `model.dates` instead

**Assertion Error:**
```
AssertionError: Fill rate 72% below 85% target
```
→ Model behavior changed, investigate constraint or cost issue

**Solver Error:**
```
ApplicationError: Solver 'cbc' failed
```
→ Solver not installed or incompatible version

### Step 2: Isolate the Issue

```bash
# Run single test with verbose output
pytest tests/test_specific.py::test_function -v -s

# Run with full traceback
pytest tests/test_specific.py -v --tb=long

# Run with debugger
pytest tests/test_specific.py --pdb
```

### Step 3: Check Recent Changes

```bash
# What changed in optimization module?
git diff HEAD~1 src/optimization/

# What changed in this test?
git log -p tests/test_specific.py

# Who else uses this?
grep -r "function_name" tests/
```

### Step 4: Validate Model Behavior

```bash
# Check if model builds correctly
venv/bin/python -c "
from src.optimization.sliding_window_model import SlidingWindowModel
# ... create model
print('Model builds OK')
"

# Check if solver works
venv/bin/python -c "
from src.optimization import get_solver
solver = get_solver('highs')
print(f'Solver: {solver}')
"
```

---

## Test Maintenance

### When to Update Tests

**After archiving models:**
- Update imports (UnifiedNodeModel → SlidingWindowModel)
- Update attribute references
- Update performance expectations

**After adding features:**
- Add new test file for feature
- Update integration tests if UI affected
- Update documentation

**After performance improvements:**
- Update time limits in performance tests
- Update baseline expectations

### Consolidation Guidelines

**Merge tests if:**
- Testing same feature with minor variations
- Can be parameterized with `@pytest.mark.parametrize`
- Reduce maintenance burden without losing coverage

**Keep separate if:**
- Testing different features (even if similar)
- Require different fixtures or setup
- Serve different purposes (unit vs integration)

---

## Test Coverage Goals

**Target Coverage:**
- Critical paths: 100% (labor costs, shelf life, demand satisfaction)
- Model constraints: 95% (all major constraints tested)
- Data models: 90% (core models + edge cases)
- Parsers: 85% (happy path + common errors)
- UI: 80% (main workflows + critical features)

**Current Focus:**
- SlidingWindowModel constraint validation
- UI workflow compatibility
- Performance regression detection
- Cost calculation accuracy

---

## Archived Tests

**Location:** `archive/tests_unified_node_model_2025_11/`

**Archived (2025-11-09):**
- 12 UnifiedNodeModel-specific tests
- 7 baseline tests (test_baseline_*.py)

**Why Archived:**
- UnifiedNodeModel deprecated
- Redundant with SlidingWindowModel tests
- Historical reference only

**When to Use:**
- Understanding previous approach
- Comparing behaviors
- Research purposes

**Restoration:**
```bash
cp archive/tests_unified_node_model_2025_11/<test_file> tests/
```

---

## CI/CD Integration

### Pre-Commit Hooks

**Automatic validation on every commit:**
1. Import validation (test_import_validation.py)
2. Quick model test (verify SlidingWindowModel loads)

**Configuration:** `.git/hooks/pre-commit`

### Recommended CI Pipeline

```yaml
# .github/workflows/test.yml (example)
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install highspy

      - name: Run quick tests
        run: pytest tests/test_models.py tests/test_parsers.py -v

      - name: Run integration tests
        run: pytest tests/test_integration_ui_workflow.py -v

      - name: Run full suite
        run: pytest tests/ -v
```

---

## Troubleshooting Common Issues

### Test hangs / times out

**Cause:** Optimization solve taking too long

**Solution:**
```python
result = model.solve(timelimit=60)  # Add time limit
```

### Solver not found

**Cause:** HiGHS not installed

**Solution:**
```bash
pip install highspy
```

### Import errors after cleanup

**Cause:** UnifiedNodeModel archived

**Solution:**
```python
# OLD
from src.optimization.unified_node_model import UnifiedNodeModel

# NEW
from src.optimization.sliding_window_model import SlidingWindowModel
```

### Attribute errors (production_dates, etc.)

**Cause:** Attribute name changed between models

**Solution:**
```python
# OLD (UnifiedNodeModel)
len(model.production_dates)

# NEW (SlidingWindowModel)
len(model.dates)
```

---

## Performance Benchmarks

### Expected Solve Times (APPSI HiGHS)

| Horizon | Variables | Expected Time |
|---------|-----------|---------------|
| 1 week  | ~2,800    | <2s           |
| 4 weeks | ~11,000   | 5-7s          |
| 12 weeks| ~33,000   | 30-60s        |

**If slower:**
1. Check solver (should be APPSI HiGHS)
2. Verify using SlidingWindowModel (not archived model)
3. Check pallet tracking (disable with `use_pallet_tracking=False` for 50% speedup)
4. Increase MIP gap (1% → 2%)

### Test Execution Times

| Category | Expected Time | Command |
|----------|---------------|---------|
| Quick    | <1 min        | `pytest tests/test_models.py -v` |
| Integration | 2-5 min    | `pytest tests/test_integration_*.py -v` |
| Regression | 5-10 min     | `pytest tests/test_integration_ui_workflow.py -v` |
| Full suite | 30-60 min   | `pytest tests/ -v` |

---

## Test Development Workflow

### Adding New Feature

1. **Write test first (TDD)**
   ```bash
   # Create test file
   vim tests/test_new_feature.py
   ```

2. **Run test (expect failure)**
   ```bash
   pytest tests/test_new_feature.py -v
   # Should fail - feature not implemented yet
   ```

3. **Implement feature**
   ```bash
   vim src/optimization/sliding_window_model.py
   ```

4. **Run test again (expect pass)**
   ```bash
   pytest tests/test_new_feature.py -v
   # Should pass now
   ```

5. **Run regression tests**
   ```bash
   pytest tests/test_integration_ui_workflow.py -v
   # Make sure nothing broke
   ```

6. **Commit**
   ```bash
   git add tests/test_new_feature.py src/optimization/sliding_window_model.py
   git commit -m "feat: Add <feature>"
   ```

### Updating Existing Tests

1. **Understand why it's failing**
   ```bash
   pytest tests/test_file.py::test_function -v -s
   ```

2. **Check if test is correct**
   - Is the test expectation still valid?
   - Did model behavior intentionally change?
   - Is it testing deprecated functionality?

3. **Update test or fix code**
   - If test is wrong: Update test
   - If code is wrong: Fix code
   - If feature deprecated: Archive test

4. **Verify fix**
   ```bash
   pytest tests/test_file.py -v
   ```

---

## Test Consolidation Guidelines

**When we consolidated (Nov 2025):**
- 102 test files → ~85 files (-17%)
- Removed redundant baseline tests
- Archived UnifiedNodeModel tests
- Kept all unique test coverage

**Rules we followed:**
1. Don't lose coverage (merge, don't delete)
2. Archive deprecated model tests (don't delete)
3. Consolidate similar tests (e.g., labor cost variants)
4. Keep critical regression tests separate

---

## Archived Test Files

**Location:** `archive/tests_unified_node_model_2025_11/`

**Archived (2025-11-09):**
```
test_unified_1week_solve.py
test_unified_conditional_pallet_tracking.py
test_unified_core_constraints.py
test_unified_model_skeleton.py
test_unified_models.py
test_unified_produces.py
test_unified_solution_extraction.py
test_unified_state_transitions_full.py
test_unified_warmstart_integration.py
test_unified_weekend_enforcement.py
test_unified_zero_cost_scenarios.py
test_baseline_1week.py
test_baseline_2week.py
test_baseline_4week.py
test_baseline_initial_inventory.py
test_baseline_state_transitions.py
test_baseline_weekend_trucks.py
```

**Reason:** UnifiedNodeModel archived, tests no longer applicable

**Restoration:** Copy from archive if needed for reference

---

## Test Data

### Real Data Files

**Location:** `data/examples/`

**Files:**
- `Gluten Free Forecast - Latest.xlsm` - Real SAP IBP export
- `Network_Config.xlsx` - 11 locations, 10 routes, 585 labor days
- `inventory_latest.XLSX` - Initial inventory snapshot (optional)

**Usage:** Integration tests use these files

### Test Fixtures

**Location:** `tests/conftest.py`

**Key fixtures:**
- `create_test_products()` - Standard product set
- `parsed_data()` - Complete parsed dataset from real files

---

## FAQs

**Q: Why did test X start failing after cleanup?**
A: Likely uses UnifiedNodeModel (archived). Update to SlidingWindowModel.

**Q: How do I run only fast tests?**
A: `pytest tests/ -v -m "not slow"` (requires pytest markers)

**Q: Can I still test UnifiedNodeModel?**
A: Yes, restore from `archive/optimization_models_deprecated_2025_11/`

**Q: Why is test_integration_ui_workflow.py so important?**
A: It's the **CRITICAL REGRESSION GATE** - validates end-to-end workflow with real data

**Q: How often should I run full test suite?**
A: Before every commit (pre-commit hook runs subset automatically)

**Q: What if tests fail due to solver issues?**
A: Install HiGHS (`pip install highspy`) or use CBC fallback

---

## Contributing Tests

### Before Creating PR

**Required:**
1. ✅ All new tests pass
2. ✅ Integration test passes
3. ✅ No regressions (full suite ≥90% pass)
4. ✅ Tests documented with docstrings

### Code Review Checklist

- [ ] Test names are descriptive
- [ ] Test covers happy path + edge cases
- [ ] Test is in correct category (unit/integration)
- [ ] Test uses SlidingWindowModel (not archived models)
- [ ] Test has reasonable execution time (<30s for unit tests)
- [ ] Test doesn't duplicate existing coverage

---

**Last Updated:** November 9, 2025
**Model:** SlidingWindowModel (Primary - Only)
**Test Count:** ~85 files
**Status:** Active and maintained ✅
