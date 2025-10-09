# Labor Calendar Validation Integration Tests

## Overview

The `test_labor_validation_integration.py` file contains comprehensive end-to-end integration tests for the labor calendar validation workflow. These tests use real example data files to validate the distinction between critical and non-critical missing labor dates.

## Background

### The Problem

The labor calendar validation logic was updated to fix a user-reported bug where extending the planning horizon beyond the forecast range (for operational flexibility) would cause hard failures with `ValueError`, even though the extended dates weren't needed to satisfy forecast demand.

### The Solution

The validation now distinguishes between:

1. **Critical dates**: Weekday production dates needed to produce and deliver forecast demand
   - Missing critical weekdays → `ValueError` (hard failure)
   - Error includes forecast range, required production start, labor coverage, and fix instructions

2. **Non-critical dates**: Dates outside the critical forecast range or weekend dates
   - Missing non-critical weekdays → `UserWarning` (soft warning)
   - Missing weekend dates → `UserWarning` (optional capacity)
   - Model proceeds successfully

## Test Coverage

### Test 1: `test_example_data_with_normal_horizon`

**Purpose**: Validate that example data has proper labor calendar coverage for forecast

**Scenario**: Load example data with default planning horizon (no end_date override)

**Expected behavior**:
- Model initializes successfully
- No ValueError raised
- No warnings about missing critical labor dates
- Labor calendar covers all critical production dates

### Test 2: `test_example_data_with_extended_horizon`

**Purpose**: Test the specific bug fix - extended horizons don't fail

**Scenario**: Load example data with planning horizon extended 1 year beyond forecast

**Expected behavior**:
- Model initializes successfully (no ValueError)
- UserWarning issued about non-critical missing dates
- Warning message mentions "outside critical forecast range"
- No critical error about missing weekdays

**This is the key test that validates the bug fix.**

### Test 3: `test_example_data_with_truncated_labor_calendar`

**Purpose**: Validate that missing critical weekdays still properly fail

**Scenario**: Programmatically remove last 10 weekday entries from labor calendar

**Expected behavior**:
- ValueError raised during model initialization
- Error message clearly identifies missing critical weekday dates
- Error includes forecast range, required production start, labor coverage
- Error includes actionable fix instructions

### Test 4: `test_labor_validation_distinguishes_weekdays_vs_weekends`

**Purpose**: Verify different treatment of missing weekends vs. weekdays

**Scenario**: Remove all weekend entries from labor calendar

**Expected behavior**:
- Missing weekends in critical range → UserWarning (not error)
- Warning mentions "weekend" and "zero production capacity"
- Model initializes successfully (weekends are optional)

### Test 5: `test_labor_validation_error_message_quality`

**Purpose**: Verify error message provides all necessary fix information

**Scenario**: Truncate labor calendar to create insufficient coverage

**Expected error message components**:
1. Number of missing dates
2. Sample of missing dates (first 5)
3. Forecast date range
4. Required production start date (with transit buffer)
5. Current labor calendar coverage range
6. Clear fix instruction
7. Multi-line formatting for readability

## Running the Tests

### Run all integration tests:
```bash
pytest tests/test_labor_validation_integration.py -v
```

### Run a specific test:
```bash
pytest tests/test_labor_validation_integration.py::test_example_data_with_extended_horizon -v
```

### Run with detailed output:
```bash
pytest tests/test_labor_validation_integration.py -v -s
```

### Run directly (without pytest):
```bash
python -m tests.test_labor_validation_integration
```

## Test Data Requirements

The tests require these example data files:
- `data/examples/Gfree Forecast.xlsm` - Real SAP IBP export with 9 breadroom locations
- `data/examples/Network_Config.xlsx` - Network configuration (locations, routes, labor, trucks, costs)

**Note**: Tests will be automatically skipped if example files are not available (e.g., in minimal dev environments).

## Key Assertions

### Normal Horizon Test
```python
assert model is not None
assert len(critical_labor_warnings) == 0
assert len(missing_critical_weekdays) == 0
```

### Extended Horizon Test (Bug Fix)
```python
assert model is not None  # No ValueError
assert len(noncritical_warnings) > 0  # Has warnings
assert len(critical_errors) == 0  # But no errors
assert 'outside critical' in warning_message
```

### Truncated Calendar Test
```python
with pytest.raises(ValueError) as exc_info:
    model = IntegratedProductionDistributionModel(...)

assert 'missing' in error_message.lower()
assert 'weekday' in error_message.lower()
assert 'forecast range' in error_message.lower()
assert 'fix' in error_message.lower()
```

## Integration with CI/CD

These integration tests should be run as part of the test suite:

```bash
# Run all tests including integration tests
pytest

# Run only integration tests
pytest tests/test_labor_validation_integration.py

# Check test coverage
pytest --cov=src tests/test_labor_validation_integration.py
```

## Maintenance Notes

### When to Update Tests

Update these tests when:
1. Labor calendar validation logic changes
2. Error message format changes
3. Critical date calculation changes
4. Example data files are updated

### Test Data Stability

The tests programmatically modify the labor calendar to create test scenarios (truncation, weekend removal). This approach:
- ✅ Doesn't require additional test data files
- ✅ Works with any example data (as long as it has sufficient coverage)
- ✅ Tests realistic scenarios (actual data with programmatic modifications)
- ✅ No permanent changes to example data files

## Related Files

- **Implementation**: `src/optimization/integrated_model.py` (lines 691-843)
  - `_validate_feasibility()` method
  - Critical vs. non-critical date logic
  - Error and warning message generation

- **Models**:
  - `src/models/labor_calendar.py` - LaborCalendar, LaborDay
  - `src/parsers/excel_parser.py` - Excel data loading

- **Documentation**:
  - `data/examples/EXCEL_TEMPLATE_SPEC.md` - Input format specification
  - `data/examples/MANUFACTURING_SCHEDULE.md` - Labor calendar requirements

## Example Output

### Test 1 (Normal Horizon) - Success:
```
✓ Test passed: Normal horizon
  Forecast range: 2025-01-01 to 2025-07-23
  Planning horizon: 2024-12-25 to 2025-07-23
  Critical range: 2024-12-25 to 2025-07-23
  Labor calendar coverage: Complete for critical weekdays
```

### Test 2 (Extended Horizon) - Success with Warnings:
```
✓ Test passed: Extended horizon
  Forecast range: 2025-01-01 to 2025-07-23
  Planning horizon: 2024-12-25 to 2026-07-23
  Extended by: 365 days
  Non-critical warnings issued: 1
  Warning sample: Labor calendar missing 52 weekday entries outside critical forecast range...
```

### Test 3 (Truncated Calendar) - Error:
```
✓ Test passed: Truncated labor calendar
  Forecast range: 2025-01-01 to 2025-07-23
  Labor calendar truncated: Removed last 10 weekday entries
  ValueError raised as expected
  Error message includes:
    - Missing critical weekdays: ✓
    - Forecast range: ✓
    - Required production start: ✓
    - Labor calendar coverage: ✓
    - Fix instructions: ✓
```

## Debugging Tips

### Test Failure: "No critical labor warnings expected"

This likely means the example labor calendar is missing critical dates. Check:
```python
# In test output, look for:
Labor calendar coverage: <start_date> to <end_date>
Critical range: <critical_start> to <critical_end>

# If critical_end > labor_end, the calendar is insufficient
```

### Test Failure: "Expected UserWarning about non-critical missing dates"

The extended horizon may not be large enough. Increase the extension:
```python
extended_end_date = forecast_end + timedelta(days=730)  # 2 years instead of 1
```

### Test Skip: "Example forecast file not found"

Ensure example data files exist:
```bash
ls -la data/examples/
# Should see: Gfree Forecast.xlsm, Network_Config.xlsx
```

## Future Enhancements

Potential additions to integration test coverage:

1. **Rolling Horizon Testing**: Test with rolling horizon solver configuration
2. **Multiple Scenarios**: Test with different forecast lengths and patterns
3. **Performance**: Benchmark validation performance with large datasets
4. **Edge Cases**: Test with minimal labor calendar (e.g., single week)
5. **Public Holidays**: Test handling of public holiday dates
6. **Custom Calendars**: Test with non-standard labor calendars

## Related Bug Reports

- **Original Issue**: User extending planning horizon beyond forecast caused ValueError
- **Fix**: Distinguish critical (needed for forecast) vs. non-critical (extended horizon) dates
- **Impact**: Enables rolling horizon planning without labor calendar covering entire extended horizon
