# PHASE 2A: Integration Test Verification - READY TO EXECUTE

## Quick Start: Run This Now

I've prepared comprehensive verification tools for Phase 2A. Here's how to execute:

### Option 1: Quick Automated Check (RECOMMENDED)

```bash
python verify_integration_tests.py
```

This will:
1. Check labor calendar coverage (May 26, 2025 - Dec 31, 2026)
2. Verify all forecast weekdays are covered
3. Run all 3 previously failing tests
4. Generate detailed pass/fail report

**Expected outcome:** All 3 tests PASS ✓

### Option 2: Manual Step-by-Step

```bash
# Step 1: Verify labor calendar was extended
python quick_check_labor_calendar.py

# Step 2: Run each test individually
pytest tests/test_labor_validation_integration.py::test_example_data_with_normal_horizon -v -s
pytest tests/test_labor_validation_integration.py::test_example_data_with_extended_horizon -v -s
pytest tests/test_labor_validation_integration.py::test_labor_validation_distinguishes_weekdays_vs_weekends -v -s

# Step 3: Run full suite
pytest tests/test_labor_validation_integration.py -v
```

### Option 3: Using Test Scripts

```bash
# Python version
python run_integration_tests.py

# Or bash version (Linux/Mac)
bash run_integration_tests.sh
```

## What I've Prepared

I've created 6 verification tools in `/home/sverzijl/planning_latest/`:

1. **verify_integration_tests.py** ← MAIN TOOL (Run this!)
   - Comprehensive automated verification
   - Checks labor calendar coverage
   - Runs all 3 tests
   - Detailed reporting

2. **quick_check_labor_calendar.py**
   - Fast pre-flight check
   - Verifies labor calendar extension
   - Checks forecast coverage

3. **run_integration_tests.py**
   - Subprocess-based test runner
   - Captures pytest output
   - Summary report

4. **run_integration_tests.sh**
   - Bash script version
   - Good for CI/CD

5. **PHASE_2A_INTEGRATION_TEST_VERIFICATION.md**
   - Complete verification guide
   - Troubleshooting steps
   - Success criteria

6. **PHASE_2A_STATUS_REPORT.md**
   - Current status
   - Risk assessment
   - Timeline estimates

## What Should Happen

### If Phase 1 Was Completed (Expected)

```
✓ Labor calendar: May 26, 2025 - Dec 31, 2026 (585 days)
✓ All forecast weekdays covered
✓ Test 1 (normal horizon): PASS
✓ Test 2 (extended horizon): PASS (with UserWarning)
✓ Test 3 (weekday vs weekend): PASS (with UserWarning)

SUCCESS: All 3 previously failing tests now pass!
```

### If Phase 1 Was NOT Completed (Unlikely)

```
⚠ Labor calendar: May 26, 2025 - Dec 22, 2025 (missing 268 weekdays)
✗ Test 1: FAIL - missing critical weekdays
✗ Test 2: FAIL - missing critical weekdays
✗ Test 3: FAIL - missing critical weekdays

ACTION REQUIRED: Complete Phase 1 labor calendar extension
```

## Expected Results Details

### Test 1: test_example_data_with_normal_horizon
- **Expected:** PASS with no warnings
- **Validates:** Labor calendar covers forecast range
- **Duration:** ~30 seconds

### Test 2: test_example_data_with_extended_horizon
- **Expected:** PASS with UserWarning
- **Warning about:** Non-critical missing dates outside forecast
- **Validates:** Distinguishes critical vs non-critical dates
- **Duration:** ~30 seconds

### Test 3: test_labor_validation_distinguishes_weekdays_vs_weekends
- **Expected:** PASS with UserWarning
- **Warning about:** Missing weekends (optional capacity)
- **Validates:** Weekday vs weekend distinction
- **Duration:** ~30 seconds

### Full Suite (5 tests total)
- **Expected:** 5 PASS or 4 PASS + 1 SKIPPED
- **Duration:** ~2 minutes

## Files Reference

All files are absolute paths from project root `/home/sverzijl/planning_latest/`:

**Verification Scripts:**
- `/home/sverzijl/planning_latest/verify_integration_tests.py`
- `/home/sverzijl/planning_latest/quick_check_labor_calendar.py`
- `/home/sverzijl/planning_latest/run_integration_tests.py`
- `/home/sverzijl/planning_latest/run_integration_tests.sh`

**Documentation:**
- `/home/sverzijl/planning_latest/PHASE_2A_INTEGRATION_TEST_VERIFICATION.md`
- `/home/sverzijl/planning_latest/PHASE_2A_STATUS_REPORT.md`
- `/home/sverzijl/planning_latest/RUN_TESTS_NOW.md` (this file)

**Test File:**
- `/home/sverzijl/planning_latest/tests/test_labor_validation_integration.py`

**Data Files:**
- `/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx` (labor calendar)
- `/home/sverzijl/planning_latest/data/examples/Gfree Forecast.xlsm` (forecast)

## Troubleshooting

### If tests fail with "missing critical weekdays"

The labor calendar was not extended. You need to:

1. Open `data/examples/Network_Config.xlsx`
2. Go to "LaborCalendar" sheet
3. Extend rows to cover through Dec 31, 2026
4. Save file
5. Re-run tests

### If tests fail with other errors

Check the error message for:
- File not found → verify data files exist
- Import errors → ensure virtual environment activated
- Solver errors → not relevant for these tests

### If tests pass but with unexpected warnings

This is likely okay. The tests check:
- Test 2 expects UserWarning for non-critical dates
- Test 3 expects UserWarning for missing weekends

## Timeline

- **Pre-flight check:** 30 seconds
- **Test execution:** 2-3 minutes
- **Review results:** 1 minute
- **Total:** ~5 minutes

## Next Steps

1. **Run verification:** `python verify_integration_tests.py`
2. **Review output:** Check all 3 tests pass
3. **Report results:** Document in PHASE_2A_STATUS_REPORT.md
4. **Proceed:** Move to Phase 2B if successful

## Success Criteria

Phase 2A is complete when you can confirm:

- ✓ Labor calendar covers May 26, 2025 - Dec 31, 2026 (585 days)
- ✓ All forecast weekdays covered
- ✓ Test 1 passes without errors
- ✓ Test 2 passes (UserWarning okay)
- ✓ Test 3 passes (UserWarning okay)
- ✓ No "missing 268 weekday dates" error

## Ready?

Run this command now:

```bash
python verify_integration_tests.py
```

Or for quick check first:

```bash
python quick_check_labor_calendar.py
```

Good luck! 🚀
