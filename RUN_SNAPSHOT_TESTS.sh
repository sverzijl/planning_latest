#!/bin/bash
# Run Daily Inventory Snapshot Tests
# This script runs all tests related to the daily snapshot demand consumption fix

echo "================================================================================"
echo "DAILY INVENTORY SNAPSHOT - TEST SUITE"
echo "================================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Run existing unit tests (updated with new semantics)
echo -e "${YELLOW}[1/4] Running daily snapshot unit tests...${NC}"
pytest tests/test_daily_snapshot.py -v --tb=short
RESULT1=$?

echo ""
echo "================================================================================"
echo ""

# Run integration tests (verify still passing)
echo -e "${YELLOW}[2/4] Running daily snapshot integration tests...${NC}"
pytest tests/test_daily_snapshot_integration.py -v --tb=short
RESULT2=$?

echo ""
echo "================================================================================"
echo ""

# Run new demand consumption tests (FIFO)
echo -e "${YELLOW}[3/4] Running demand consumption (FIFO) tests...${NC}"
pytest tests/test_daily_snapshot_demand_consumption.py -v --tb=short
RESULT3=$?

echo ""
echo "================================================================================"
echo ""

# Run all snapshot-related tests
echo -e "${YELLOW}[4/4] Running all snapshot-related tests...${NC}"
pytest tests/ -k "snapshot" -v --tb=short
RESULT4=$?

echo ""
echo "================================================================================"
echo "TEST SUMMARY"
echo "================================================================================"

# Check results
if [ $RESULT1 -eq 0 ] && [ $RESULT2 -eq 0 ] && [ $RESULT3 -eq 0 ] && [ $RESULT4 -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo ""
    echo "The daily inventory snapshot demand consumption fix is validated:"
    echo "  ✓ Existing unit tests updated and passing"
    echo "  ✓ Integration tests verified"
    echo "  ✓ New FIFO consumption tests passing"
    echo "  ✓ No regressions detected"
    echo ""
    echo "Snapshot semantics: Inventory shown AFTER demand consumption (end-of-day)"
    exit 0
else
    echo "✗ SOME TESTS FAILED"
    echo ""
    echo "Results:"
    [ $RESULT1 -eq 0 ] && echo "  ✓ Unit tests passed" || echo "  ✗ Unit tests failed"
    [ $RESULT2 -eq 0 ] && echo "  ✓ Integration tests passed" || echo "  ✗ Integration tests failed"
    [ $RESULT3 -eq 0 ] && echo "  ✓ Demand consumption tests passed" || echo "  ✗ Demand consumption tests failed"
    [ $RESULT4 -eq 0 ] && echo "  ✓ All snapshot tests passed" || echo "  ✗ Some snapshot tests failed"
    echo ""
    echo "Please review the test output above for details."
    exit 1
fi
