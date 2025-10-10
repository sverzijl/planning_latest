#!/bin/bash

# Production Smoothing Test Suite Runner
# Validates the production smoothing fix and checks for regression

set -e  # Exit on any error

echo "============================================================"
echo "PRODUCTION SMOOTHING FIX - TEST SUITE VALIDATION"
echo "============================================================"
echo ""
echo "This script validates the production smoothing fix that"
echo "prevents the single-day production concentration bug."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run test and track results
run_test() {
    local test_name=$1
    local test_command=$2

    echo "-----------------------------------------------------------"
    echo "Running: $test_name"
    echo "-----------------------------------------------------------"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED${NC}: $test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}: $test_name"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Phase 1: Critical Regression Tests (Must Pass)
echo "============================================================"
echo "PHASE 1: CRITICAL REGRESSION TESTS"
echo "============================================================"
echo ""

run_test \
    "Regression Test: Single-Day Production Bug" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_regression_single_day_production_bug_fixed -v" \
    || echo -e "${RED}CRITICAL FAILURE: Single-day bug detected!${NC}"

run_test \
    "Production Spread Test" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_production_spread_with_smoothing -v" \
    || echo -e "${RED}WARNING: Production not spreading correctly${NC}"

run_test \
    "Smoothing Constraint Test" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_smoothing_constraint_enforced -v" \
    || echo -e "${RED}WARNING: Smoothing constraint violated${NC}"

echo ""

# Phase 2: Parameter and Integration Tests
echo "============================================================"
echo "PHASE 2: PARAMETER AND INTEGRATION TESTS"
echo "============================================================"
echo ""

run_test \
    "Parameter Control Test" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_parameter_control_smoothing_on_off -v"

run_test \
    "Integration Test: Batch Tracking + Smoothing" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_batch_tracking_and_smoothing_integration -v"

run_test \
    "Backward Compatibility Test" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_backward_compatibility_no_batch_tracking -v"

echo ""

# Phase 3: Edge Cases
echo "============================================================"
echo "PHASE 3: EDGE CASE TESTS"
echo "============================================================"
echo ""

run_test \
    "High Demand Edge Case" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_high_demand_edge_case -v"

run_test \
    "Low Demand Edge Case" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_low_demand_edge_case -v"

echo ""

# Phase 4: Summary Test
echo "============================================================"
echo "PHASE 4: COMPREHENSIVE SUMMARY TEST"
echo "============================================================"
echo ""

run_test \
    "Production Smoothing Summary Test" \
    "pytest tests/test_batch_tracking_production_smoothing.py::test_production_smoothing_summary -v -s"

echo ""

# Phase 5: Related Test Suites (Optional)
echo "============================================================"
echo "PHASE 5: RELATED TEST SUITES"
echo "============================================================"
echo ""

if [ "${RUN_ALL_TESTS:-false}" = "true" ]; then
    echo "Running related batch tracking tests..."

    run_test \
        "Batch Tracking Integration Tests" \
        "pytest tests/test_batch_tracking_integration.py -v" \
        || echo -e "${YELLOW}Warning: Some integration tests failed${NC}"

    run_test \
        "Cohort Model Unit Tests" \
        "pytest tests/test_cohort_model_unit.py -v" \
        || echo -e "${YELLOW}Warning: Some cohort tests failed${NC}"
else
    echo "Skipping related test suites (set RUN_ALL_TESTS=true to include)"
    echo "To run all tests: RUN_ALL_TESTS=true ./run_production_smoothing_tests.sh"
fi

echo ""

# Final Summary
echo "============================================================"
echo "TEST SUITE SUMMARY"
echo "============================================================"
echo ""
echo "Total Tests:  $TOTAL_TESTS"
echo -e "${GREEN}Passed:       $PASSED_TESTS${NC}"
echo -e "${RED}Failed:       $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo -e "${GREEN}Production smoothing fix validated successfully!${NC}"
    echo -e "${GREEN}============================================================${NC}"
    exit 0
else
    echo -e "${RED}============================================================${NC}"
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo -e "${RED}Please review failures above and fix issues.${NC}"
    echo -e "${RED}============================================================${NC}"

    # Provide guidance based on which tests failed
    echo ""
    echo "TROUBLESHOOTING:"
    echo "1. Check that CBC solver is installed and working"
    echo "2. Review integrated_model.py lines 1448-1494 (smoothing)"
    echo "3. Verify FIFO penalty is disabled (lines 2215-2240)"
    echo "4. Check enable_production_smoothing defaults correctly"
    echo ""

    exit 1
fi
