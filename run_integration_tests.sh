#!/bin/bash
# Run integration tests to verify labor calendar extension fixes

echo "========================================="
echo "PHASE 2A: Integration Test Verification"
echo "========================================="
echo ""
echo "Testing 3 previously failing tests after labor calendar extension..."
echo ""

# Test 1: Normal horizon
echo "Test 1: test_example_data_with_normal_horizon"
echo "-----------------------------------------------"
pytest tests/test_labor_validation_integration.py::test_example_data_with_normal_horizon -v -s
TEST1_RESULT=$?
echo ""

# Test 2: Extended horizon
echo "Test 2: test_example_data_with_extended_horizon"
echo "------------------------------------------------"
pytest tests/test_labor_validation_integration.py::test_example_data_with_extended_horizon -v -s
TEST2_RESULT=$?
echo ""

# Test 3: Weekday vs weekend distinction
echo "Test 3: test_labor_validation_distinguishes_weekdays_vs_weekends"
echo "----------------------------------------------------------------"
pytest tests/test_labor_validation_integration.py::test_labor_validation_distinguishes_weekdays_vs_weekends -v -s
TEST3_RESULT=$?
echo ""

# Summary
echo "========================================="
echo "Test Results Summary:"
echo "========================================="
echo "Test 1 (normal horizon):          $([ $TEST1_RESULT -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "Test 2 (extended horizon):        $([ $TEST2_RESULT -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "Test 3 (weekday vs weekend):      $([ $TEST3_RESULT -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo ""

# Run full suite
echo "Running full integration test suite..."
echo "---------------------------------------"
pytest tests/test_labor_validation_integration.py -v
FULL_RESULT=$?
echo ""

echo "========================================="
echo "Final Status:"
echo "========================================="
if [ $TEST1_RESULT -eq 0 ] && [ $TEST2_RESULT -eq 0 ] && [ $TEST3_RESULT -eq 0 ]; then
    echo "SUCCESS: All 3 previously failing tests now pass! ✓"
    exit 0
else
    echo "FAILURE: Some tests still failing"
    exit 1
fi
