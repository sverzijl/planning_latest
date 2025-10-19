#!/bin/bash
# Comprehensive Test Validation After Non-Fixed Day Fix
# This script validates the fix in unified_node_model.py (lines 343-346)

echo "=========================================================================="
echo "COMPREHENSIVE TEST VALIDATION - NON-FIXED DAY FIX"
echo "=========================================================================="
echo ""
echo "Fix: Changed day_hours = labor_day.fixed_hours (was 0)"
echo "     to day_hours = 24.0 for non-fixed days"
echo ""
echo "Date: $(date)"
echo "=========================================================================="
echo ""

# Set PATH to use virtual environment
VENV_PYTHON="/home/sverzijl/planning_latest/venv/bin/python"

# Phase 1: Non-Fixed Day Unit Tests
echo "=========================================================================="
echo "PHASE 1: NON-FIXED DAY UNIT TESTS"
echo "=========================================================================="
echo ""

echo "Test 1: Weekend Production Below Minimum"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_labor_cost_piecewise.py::test_piecewise_non_fixed_day_below_minimum -v -s
PHASE1_TEST1=$?
echo ""

echo "Test 2: Public Holiday Overhead (Above Minimum)"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_labor_overhead_holiday.py::test_public_holiday_overhead_included -v -s
PHASE1_TEST2=$?
echo ""

echo "Test 3: Public Holiday Overhead (Below Minimum)"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_labor_overhead_holiday.py::test_public_holiday_overhead_below_minimum -v -s
PHASE1_TEST3=$?
echo ""

# Phase 2: Regression Test Suite
echo "=========================================================================="
echo "PHASE 2: REGRESSION TEST SUITE"
echo "=========================================================================="
echo ""

echo "Test Suite 1: Weekday Labor Costs"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_labor_cost_piecewise.py -v
PHASE2_SUITE1=$?
echo ""

echo "Test Suite 2: Multi-Day Consistency"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_labor_overhead_multi_day.py -v
PHASE2_SUITE2=$?
echo ""

echo "Test Suite 3: Overtime Preference"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_overtime_preference.py -v
PHASE2_SUITE3=$?
echo ""

echo "Test Suite 4: Baseline Labor Costs"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_labor_cost_baseline.py -v
PHASE2_SUITE4=$?
echo ""

echo "Test Suite 5: Labor Cost Isolation"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_labor_cost_isolation.py -v
PHASE2_SUITE5=$?
echo ""

echo "Test Suite 6: Unified Model Core"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_unified_node_model.py -v
PHASE2_SUITE6=$?
echo ""

# Phase 3: Integration Test
echo "=========================================================================="
echo "PHASE 3: INTEGRATION TEST"
echo "=========================================================================="
echo ""

echo "Integration Test: UI Workflow (4-week horizon)"
echo "--------------------------------------------------------------------------"
$VENV_PYTHON -m pytest tests/test_integration_ui_workflow.py -v
PHASE3_INTEGRATION=$?
echo ""

# Summary Report
echo "=========================================================================="
echo "VALIDATION SUMMARY"
echo "=========================================================================="
echo ""

echo "PHASE 1: Non-Fixed Day Unit Tests"
echo "  Test 1 (Weekend Below Min):       $([ $PHASE1_TEST1 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "  Test 2 (Holiday Above Min):       $([ $PHASE1_TEST2 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "  Test 3 (Holiday Below Min):       $([ $PHASE1_TEST3 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo ""

echo "PHASE 2: Regression Test Suite"
echo "  Suite 1 (Weekday Labor):          $([ $PHASE2_SUITE1 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "  Suite 2 (Multi-Day):              $([ $PHASE2_SUITE2 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "  Suite 3 (Overtime Preference):    $([ $PHASE2_SUITE3 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "  Suite 4 (Baseline Labor):         $([ $PHASE2_SUITE4 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "  Suite 5 (Labor Isolation):        $([ $PHASE2_SUITE5 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo "  Suite 6 (Unified Model Core):     $([ $PHASE2_SUITE6 -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo ""

echo "PHASE 3: Integration Test"
echo "  Integration Test:                 $([ $PHASE3_INTEGRATION -eq 0 ] && echo 'PASS ✓' || echo 'FAIL ✗')"
echo ""

# Calculate overall status
TOTAL_FAILURES=$((PHASE1_TEST1 + PHASE1_TEST2 + PHASE1_TEST3 + PHASE2_SUITE1 + PHASE2_SUITE2 + PHASE2_SUITE3 + PHASE2_SUITE4 + PHASE2_SUITE5 + PHASE2_SUITE6 + PHASE3_INTEGRATION))

echo "=========================================================================="
if [ $TOTAL_FAILURES -eq 0 ]; then
    echo "OVERALL STATUS: SUCCESS ✓"
    echo "All tests passed! Fix validated successfully."
else
    echo "OVERALL STATUS: FAILURE ✗"
    echo "Total failures: $TOTAL_FAILURES"
fi
echo "=========================================================================="
echo ""

exit $TOTAL_FAILURES
