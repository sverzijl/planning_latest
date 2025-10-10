#!/bin/bash
# Run Daily Inventory Snapshot Integration Test
#
# This script runs the comprehensive integration test for the Daily Inventory
# Snapshot feature, which validates the complete flow of inventory through
# the production-distribution system.

echo "=========================================="
echo "Daily Inventory Snapshot Integration Test"
echo "=========================================="
echo ""

# Check if pytest is available
if ! command -v pytest &> /dev/null
then
    echo "ERROR: pytest not found. Please install:"
    echo "  pip install pytest"
    exit 1
fi

# Run the integration test with verbose output
echo "Running integration test..."
echo ""

pytest tests/test_daily_snapshot_integration.py -v -s

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓✓✓ ALL TESTS PASSED ✓✓✓"
    echo "=========================================="
    echo ""
    echo "The Daily Inventory Snapshot feature is working correctly:"
    echo "  ✓ Production tracking"
    echo "  ✓ Shipment movements"
    echo "  ✓ Demand satisfaction"
    echo "  ✓ Mass balance"
    echo "  ✓ Location visibility"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "✗ TESTS FAILED"
    echo "=========================================="
    echo ""
    echo "Please review the test output above for details."
    echo ""
    exit 1
fi
