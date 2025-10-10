#!/bin/bash
# Batch Tracking Test Suite Runner
# Run comprehensive tests for age-cohort batch tracking implementation

set -e  # Exit on error

echo "=========================================="
echo "Batch Tracking Test Suite"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}ERROR: pytest not found. Please install: pip install pytest${NC}"
    exit 1
fi

# Default: run all tests
TEST_CATEGORY="${1:-all}"

case "$TEST_CATEGORY" in
    unit)
        echo -e "${YELLOW}Running Unit Tests...${NC}"
        pytest tests/test_cohort_model_unit.py -v --tb=short
        ;;

    integration)
        echo -e "${YELLOW}Running Integration Tests...${NC}"
        pytest tests/test_batch_tracking_integration.py -v --tb=short
        ;;

    regression)
        echo -e "${YELLOW}Running Regression Tests...${NC}"
        pytest tests/test_batch_tracking_regression.py -v --tb=short

        echo ""
        echo -e "${YELLOW}Running Existing Tests (Regression Check)...${NC}"
        pytest tests/test_daily_snapshot.py -v --tb=short
        pytest tests/test_daily_snapshot_integration.py -v --tb=short
        ;;

    performance)
        echo -e "${YELLOW}Running Performance Benchmarks...${NC}"
        pytest tests/test_cohort_performance.py -v --tb=short --durations=10
        ;;

    fast)
        echo -e "${YELLOW}Running Fast Tests (Unit + Quick Integration)...${NC}"
        pytest tests/test_cohort_model_unit.py \
               tests/test_batch_tracking_integration.py::test_complete_workflow_batch_tracking \
               -v --tb=short
        ;;

    coverage)
        echo -e "${YELLOW}Running Tests with Coverage Report...${NC}"
        pytest tests/test_cohort_model_unit.py \
               tests/test_batch_tracking_integration.py \
               tests/test_batch_tracking_regression.py \
               --cov=src/optimization/integrated_model \
               --cov=src/analysis/daily_snapshot \
               --cov=src/models/production_batch \
               --cov-report=html \
               --cov-report=term-missing \
               -v

        echo ""
        echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"
        ;;

    all)
        echo -e "${YELLOW}Running All Tests (Unit + Integration + Regression)...${NC}"
        pytest tests/test_cohort_model_unit.py \
               tests/test_batch_tracking_integration.py \
               tests/test_batch_tracking_regression.py \
               -v --tb=short

        echo ""
        echo -e "${GREEN}All tests completed!${NC}"
        echo ""
        echo -e "${YELLOW}To run performance benchmarks:${NC} ./run_batch_tracking_tests.sh performance"
        echo -e "${YELLOW}To run with coverage:${NC} ./run_batch_tracking_tests.sh coverage"
        ;;

    *)
        echo -e "${RED}Unknown test category: $TEST_CATEGORY${NC}"
        echo ""
        echo "Usage: $0 [category]"
        echo ""
        echo "Categories:"
        echo "  unit         - Run unit tests only (fast)"
        echo "  integration  - Run integration tests"
        echo "  regression   - Run regression tests + existing tests"
        echo "  performance  - Run performance benchmarks (slow)"
        echo "  fast         - Run quick smoke tests"
        echo "  coverage     - Run with coverage report"
        echo "  all          - Run all tests (default)"
        echo ""
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Test execution completed!${NC}"
