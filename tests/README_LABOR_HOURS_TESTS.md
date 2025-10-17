# Labor Hours Dict Format Test Suite

## Quick Reference

**Test File:** `test_result_adapter_labor_hours.py`
**Purpose:** Lock in fix for TypeError in result_adapter when processing dict-format labor hours
**Test Count:** 16 comprehensive tests
**Execution Time:** < 5 seconds

## What This Tests

### The Bug
```python
# BEFORE (caused TypeError)
batch.labor_hours_used = daily_labor_hours.get(batch.production_date, 0) * proportion
# TypeError: unsupported operand type(s) for *: 'dict' and 'float'
```

### The Fix
```python
# AFTER (handles both formats)
labor_hours_value = daily_labor_hours.get(batch.production_date, 0)
if isinstance(labor_hours_value, dict):
    labor_hours_value = labor_hours_value.get('used', 0)
batch.labor_hours_used = labor_hours_value * proportion
```

### Data Format Change

**OLD FORMAT (numeric):**
```python
labor_hours_by_date = {
    date(2025, 10, 15): 12.5,
    date(2025, 10, 16): 14.0,
}
```

**NEW FORMAT (dict with breakdown):**
```python
labor_hours_by_date = {
    date(2025, 10, 15): {
        'used': 12.5,
        'paid': 12.5,
        'fixed': 12.0,
        'overtime': 0.5,
    },
    date(2025, 10, 16): {
        'used': 14.0,
        'paid': 14.0,
        'fixed': 12.0,
        'overtime': 2.0,
    },
}
```

## Running Tests

### Run All Labor Hours Tests
```bash
venv/bin/python -m pytest tests/test_result_adapter_labor_hours.py -v
```

### Run Specific Test Class
```bash
venv/bin/python -m pytest tests/test_result_adapter_labor_hours.py::TestLaborHoursDictExtraction -v
```

### Run Primary Regression Test
```bash
venv/bin/python -m pytest tests/test_result_adapter_labor_hours.py::test_error_detection_dict_multiplication_regression -v
```

### Run with Detailed Output
```bash
venv/bin/python -m pytest tests/test_result_adapter_labor_hours.py -v -s
```

## Test Organization

### 1. TestLaborHoursDictExtraction (4 tests)
**Primary regression tests for dict format**

- `test_labor_hours_dict_format_with_proportional_allocation` ⭐ **PRIMARY TEST**
  - Validates correct extraction of 'used' hours from dict
  - Tests proportional allocation across multiple batches
  - Ensures dict * float TypeError cannot occur

- `test_labor_hours_dict_missing_date`
  - Edge case: production date not in labor_hours_by_date
  - Should default to 0 labor hours

- `test_labor_hours_dict_with_zero_values`
  - Edge case: dict with all zero values
  - Should handle gracefully

- `test_labor_hours_dict_missing_used_field`
  - Edge case: dict without 'used' field
  - Should default to 0 (no KeyError)

### 2. TestBackwardCompatibilityNumericLabor (2 tests)
**Ensure old numeric format still works**

- `test_labor_hours_numeric_format_still_works`
  - Validates OLD numeric format compatibility
  - Ensures no regression for existing code

- `test_labor_hours_mixed_format_graceful_handling`
  - Edge case: mixed dict and numeric values
  - Should handle both in same dataset

### 3. TestProductionScheduleDailyLaborHours (2 tests)
**Validate ProductionSchedule data structures**

- `test_production_schedule_stores_dict_labor_hours`
  - Ensures dict structure preserved in schedule
  - Validates correct field access

- `test_production_schedule_total_labor_hours_calculation`
  - Tests total_labor_hours calculation
  - Should sum 'used' values from dicts

### 4. TestInitialInventoryWithLaborHours (1 test)
**Initial inventory edge case**

- `test_initial_inventory_batches_zero_labor_hours`
  - Initial inventory batches should have 0 labor hours
  - Validates sunk cost handling

### 5. TestEdgeCases (3 tests)
**Defensive programming tests**

- `test_empty_labor_hours_dict`
  - Empty labor_hours_by_date dict
  - Should default to 0 hours

- `test_missing_labor_hours_by_date_key`
  - Missing labor_hours_by_date entirely
  - Should handle gracefully

- `test_none_labor_hours_value`
  - None values in dict
  - Should not raise TypeError

### 6. TestCostBreakdownLabor (1 test)
**Cost breakdown processing**

- `test_cost_breakdown_handles_dict_labor_hours`
  - Tests _create_cost_breakdown() function
  - Validates total_hours calculation

### 7. Integration Test (1 test)
**Full workflow validation**

- `test_full_adapter_integration_with_dict_labor`
  - Tests complete adapt_optimization_results()
  - Validates end-to-end processing

### 8. Regression Detection Tests (2 tests) ⭐ **CRITICAL**
**Prevent future regressions**

- `test_error_detection_dict_multiplication_regression` ⭐ **MUST PASS**
  - Detects if dict * float TypeError reappears
  - Explicitly tests the exact bug scenario
  - **If this fails:** Someone removed the isinstance() check!

- `test_error_detection_missing_used_field_regression`
  - Detects if 'used' field handling breaks
  - Validates graceful degradation
  - **If this fails:** Dict structure changed without updating code!

## What Each Test Validates

| Test | Validates | Failure Impact |
|------|-----------|----------------|
| Primary dict extraction | Correct 'used' hours extraction | Results page TypeError |
| Missing date | Default to 0 hours | KeyError or incorrect hours |
| Zero values | Handle zeros correctly | Incorrect cost calculation |
| Missing 'used' field | Graceful degradation | KeyError |
| Numeric backward compat | Old format still works | Regression for existing code |
| Mixed formats | Both formats in one dataset | Type conflicts |
| Dict preservation | Schedule stores dict | Data loss |
| Total calculation | Sum of 'used' hours | Incorrect totals |
| Initial inventory | Zero labor for initial | Cost attribution error |
| Empty dict | Handle empty gracefully | IndexError |
| Missing key | Handle missing key | KeyError |
| None values | Handle None values | TypeError |
| Cost breakdown | Correct breakdown calc | UI display error |
| Full integration | End-to-end workflow | Results page failure |
| Regression detection | Prevent bug reappearance | **CRITICAL** |
| Field validation | Ensure required fields | Data structure error |

## Expected Output

### All Tests Pass
```
tests/test_result_adapter_labor_hours.py::TestLaborHoursDictExtraction::test_labor_hours_dict_format_with_proportional_allocation PASSED
tests/test_result_adapter_labor_hours.py::TestLaborHoursDictExtraction::test_labor_hours_dict_missing_date PASSED
tests/test_result_adapter_labor_hours.py::TestLaborHoursDictExtraction::test_labor_hours_dict_with_zero_values PASSED
tests/test_result_adapter_labor_hours.py::TestLaborHoursDictExtraction::test_labor_hours_dict_missing_used_field PASSED
tests/test_result_adapter_labor_hours.py::TestBackwardCompatibilityNumericLabor::test_labor_hours_numeric_format_still_works PASSED
tests/test_result_adapter_labor_hours.py::TestBackwardCompatibilityNumericLabor::test_labor_hours_mixed_format_graceful_handling PASSED
tests/test_result_adapter_labor_hours.py::TestProductionScheduleDailyLaborHours::test_production_schedule_stores_dict_labor_hours PASSED
tests/test_result_adapter_labor_hours.py::TestProductionScheduleDailyLaborHours::test_production_schedule_total_labor_hours_calculation PASSED
tests/test_result_adapter_labor_hours.py::TestInitialInventoryWithLaborHours::test_initial_inventory_batches_zero_labor_hours PASSED
tests/test_result_adapter_labor_hours.py::TestEdgeCases::test_empty_labor_hours_dict PASSED
tests/test_result_adapter_labor_hours.py::TestEdgeCases::test_missing_labor_hours_by_date_key PASSED
tests/test_result_adapter_labor_hours.py::TestEdgeCases::test_none_labor_hours_value PASSED
tests/test_result_adapter_labor_hours.py::TestCostBreakdownLabor::test_cost_breakdown_handles_dict_labor_hours PASSED
tests/test_result_adapter_labor_hours.py::test_full_adapter_integration_with_dict_labor PASSED
tests/test_result_adapter_labor_hours.py::test_error_detection_dict_multiplication_regression PASSED
tests/test_result_adapter_labor_hours.py::test_error_detection_missing_used_field_regression PASSED

==================== 16 passed in 0.23s ====================
```

## Troubleshooting

### If Tests Fail

#### Test: `test_error_detection_dict_multiplication_regression` FAILS
**Diagnosis:** The original bug has returned!
**Action:**
1. Check if someone removed the `isinstance()` check in result_adapter.py
2. Look at line 159-160: Should have dict detection logic
3. Revert to fixed version immediately
4. Review recent commits to result_adapter.py

#### Test: `test_error_detection_missing_used_field_regression` FAILS
**Diagnosis:** Labor hours dict structure changed
**Action:**
1. Check unified_node_model.py lines 1065-1070
2. Verify 'used' field still exists in labor hours dict
3. Update extraction logic if structure changed
4. Add new tests for new structure

#### Test: `test_labor_hours_dict_format_with_proportional_allocation` FAILS
**Diagnosis:** Proportional allocation logic broken
**Action:**
1. Check daily_totals calculation (line 143)
2. Verify batch.quantity values are correct
3. Check proportion calculation (line 153)
4. Debug batch assignment logic

#### Test: `test_cost_breakdown_handles_dict_labor_hours` FAILS
**Diagnosis:** Cost breakdown processing broken
**Action:**
1. Check _create_cost_breakdown() function (line 316)
2. Verify total_labor_hours calculation (lines 367-373)
3. Check daily_breakdown_nested logic (lines 343-365)

### Common Issues

1. **Import errors:** Ensure venv is activated
2. **Module not found:** Run from project root directory
3. **Mock errors:** Check unittest.mock is available (Python 3.8+)
4. **Type errors in test:** Update CostStructure initialization if fields changed

## Integration with CI/CD

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
venv/bin/python -m pytest tests/test_result_adapter_labor_hours.py::test_error_detection_dict_multiplication_regression
if [ $? -ne 0 ]; then
    echo "CRITICAL: Labor hours regression test failed! Commit blocked."
    exit 1
fi
```

### CI Pipeline
```yaml
# .github/workflows/test.yml
- name: Run Labor Hours Regression Tests
  run: |
    venv/bin/python -m pytest tests/test_result_adapter_labor_hours.py -v
  if: always()
```

## Related Files

- **`ui/utils/result_adapter.py`** - Fixed code (lines 148-185, 367-373)
- **`src/optimization/unified_node_model.py`** - Source of dict format (lines 1040-1098)
- **`LABOR_HOURS_DICT_FIX_SUMMARY.md`** - Complete fix documentation
- **`PIECEWISE_LABOR_COST_IMPLEMENTATION.md`** - Piecewise labor cost details

## Maintenance

### When to Update Tests

1. **Labor hours dict structure changes**
   - Update extraction logic
   - Add new tests for new fields
   - Maintain backward compatibility

2. **New result_adapter functions added**
   - Add corresponding tests
   - Ensure dict handling is consistent

3. **ProductionSchedule model changes**
   - Update mock setup in tests
   - Verify field mappings still correct

### Test Coverage Goals

- ✅ All code paths in result_adapter labor hours processing
- ✅ All edge cases (missing data, malformed data, None values)
- ✅ Backward compatibility with numeric format
- ✅ Integration with actual optimization model
- ✅ Regression prevention for dict * float TypeError

## Success Criteria

✅ **All 16 tests pass**
✅ **No TypeError in Results page**
✅ **Labor hours display correctly**
✅ **Cost breakdown accurate**
✅ **Regression tests prevent future breaks**

---

**Status:** ✅ **COMPLETE AND LOCKED IN**

**Last Updated:** 2025-10-17

**Maintainer:** Test Automation Team
