# PHASE 2A: Integration Test Verification

## Objective

Verify that the labor calendar extension (completed in Phase 1) resolved the 3 previously failing integration tests.

## Background

### Previously Failing Tests (Before Phase 1)

1. `test_example_data_with_normal_horizon` - FAILED
2. `test_example_data_with_extended_horizon` - FAILED
3. `test_labor_validation_distinguishes_weekdays_vs_weekends` - FAILED

**Root Cause:** The forecast in `data/examples/Gfree Forecast.xlsm` extends through Dec 31, 2026, but the labor calendar previously only covered through Dec 22, 2025. This caused "missing 268 weekday dates" errors.

### Phase 1 Fix (Completed)

Extended labor calendar in `data/examples/Network_Config.xlsx` from:
- **Old range:** May 26, 2025 - Dec 22, 2025 (211 days)
- **New range:** May 26, 2025 - Dec 31, 2026 (585 days)

This should provide full coverage for the forecast period (Oct 2025 - Dec 2026).

## Verification Steps

### Step 1: Check Labor Calendar Coverage

Run quick check to verify labor calendar extension:

```bash
python quick_check_labor_calendar.py
```

**Expected Output:**
```
Labor Calendar Coverage:
  Start date:     2025-05-26
  End date:       2026-12-31
  Total days:     585
  Weekdays:       ~418
  Weekends:       ~167

✓ Labor calendar matches expected range!
✓ All forecast weekdays covered by labor calendar
```

### Step 2: Run Previously Failing Tests

Run each of the 3 tests individually:

```bash
# Test 1: Normal horizon
pytest tests/test_labor_validation_integration.py::test_example_data_with_normal_horizon -v -s

# Test 2: Extended horizon
pytest tests/test_labor_validation_integration.py::test_example_data_with_extended_horizon -v -s

# Test 3: Weekday vs weekend distinction
pytest tests/test_labor_validation_integration.py::test_labor_validation_distinguishes_weekdays_vs_weekends -v -s
```

**Expected Result:** All 3 tests should now PASS ✓

### Step 3: Run Full Integration Test Suite

Run all integration tests to ensure no regressions:

```bash
pytest tests/test_labor_validation_integration.py -v
```

**Expected Result:** All 5 tests should pass:
- ✅ test_example_data_with_normal_horizon
- ✅ test_example_data_with_extended_horizon
- ✅ test_example_data_with_truncated_labor_calendar
- ✅ test_labor_validation_distinguishes_weekdays_vs_weekends
- ✅ test_labor_validation_error_message_quality (may be skipped if no error)

### Step 4: Automated Verification

Run comprehensive verification script:

```bash
python verify_integration_tests.py
```

This script will:
1. Check data file existence
2. Load and verify labor calendar coverage
3. Run all 3 previously failing tests
4. Generate detailed pass/fail report

## Success Criteria

- [  ] Labor calendar covers May 26, 2025 - Dec 31, 2026 (585 days)
- [  ] All forecast weekdays (Oct 2025 - Dec 2026) are in labor calendar
- [  ] Test 1 (normal horizon) passes without errors or warnings
- [  ] Test 2 (extended horizon) passes with UserWarning only (for dates beyond forecast)
- [  ] Test 3 (weekday vs weekend) passes with UserWarning only (for missing weekends)
- [  ] No "missing 268 weekday dates" error
- [  ] All 5 integration tests pass

## Troubleshooting

### If Tests Still Fail

**Possible causes:**

1. **Labor calendar not actually extended**
   - Check `data/examples/Network_Config.xlsx` LaborCalendar sheet
   - Verify end date is Dec 31, 2026
   - Action: Re-run Phase 1 labor calendar extension

2. **Public holidays missing**
   - Australia has 13 public holidays in 2025, 14 in 2026
   - These should be in the calendar with special rates
   - Action: Add missing public holiday entries

3. **Excel file not saved**
   - Verify Network_Config.xlsx file modification date
   - Action: Ensure Excel file was saved after extension

4. **Parser issues**
   - Check for date parsing errors in ExcelParser
   - Action: Add debug logging to parse_labor_calendar()

### Debug Commands

```bash
# Check Excel file directly
python -c "
import pandas as pd
df = pd.read_excel('data/examples/Network_Config.xlsx', sheet_name='LaborCalendar')
print(f'Rows: {len(df)}')
print(f'Date range: {df['date'].min()} to {df['date'].max()}')
"

# Check parsed labor calendar
python -c "
from src.parsers.excel_parser import ExcelParser
from pathlib import Path
parser = ExcelParser(Path('data/examples/Network_Config.xlsx'))
cal = parser.parse_labor_calendar()
dates = sorted([d.date for d in cal.days])
print(f'Parsed range: {dates[0]} to {dates[-1]} ({len(dates)} days)')
"
```

## Expected Timeline

- **Phase 1 (completed):** Labor calendar extension - ~30 minutes
- **Phase 2A (current):** Test verification - ~5 minutes
- **Total elapsed:** ~35 minutes

## Next Steps After Verification

Once all tests pass:

1. **Document results** in this file
2. **Update README** with new labor calendar coverage
3. **Proceed to Phase 2B:** Implement production feasibility checking
4. **Archive Phase 2A artifacts** (verification scripts)

## Verification Results

### Date: [TO BE FILLED]
### Executed by: [TO BE FILLED]

**Labor Calendar Status:**
- [ ] Extended to Dec 31, 2026
- [ ] Covers all forecast dates
- [ ] Includes public holidays

**Test Results:**
- [ ] test_example_data_with_normal_horizon: PASS / FAIL
- [ ] test_example_data_with_extended_horizon: PASS / FAIL
- [ ] test_labor_validation_distinguishes_weekdays_vs_weekends: PASS / FAIL

**Execution Time:** [TO BE FILLED]

**Issues Found:** [TO BE FILLED]

**Resolution:** [TO BE FILLED]

## Files Created for Verification

- `quick_check_labor_calendar.py` - Quick labor calendar coverage check
- `verify_integration_tests.py` - Comprehensive test runner with detailed output
- `run_integration_tests.py` - Automated test execution script
- `run_integration_tests.sh` - Bash version of test runner
- `PHASE_2A_INTEGRATION_TEST_VERIFICATION.md` - This documentation

## References

- Integration test file: `tests/test_labor_validation_integration.py`
- Labor calendar parser: `src/parsers/excel_parser.py` (lines 250-290)
- Example data: `data/examples/Network_Config.xlsx` (LaborCalendar sheet)
- Forecast data: `data/examples/Gfree Forecast.xlsm`
