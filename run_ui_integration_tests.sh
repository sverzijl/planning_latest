#!/bin/bash

# Run Daily Snapshot UI Integration Tests
# This script runs the integration tests for the Daily Snapshot UI component

echo "Running Daily Snapshot UI Integration Tests..."
echo "=============================================="
echo ""

# Run pytest with verbose output
pytest tests/test_daily_snapshot_ui_integration.py -v --tb=short

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "=============================================="
    echo "✅ All integration tests passed!"
    echo "=============================================="
else
    echo ""
    echo "=============================================="
    echo "❌ Some integration tests failed!"
    echo "=============================================="
    exit 1
fi
