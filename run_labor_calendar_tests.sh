#!/bin/bash
# Run labor calendar regression tests

echo "=================================="
echo "Labor Calendar Regression Tests"
echo "=================================="
echo ""
echo "Running tests from: tests/test_planning_ui_labor_calendar.py"
echo ""

# Run pytest with verbose output
python -m pytest tests/test_planning_ui_labor_calendar.py -v --tb=short

echo ""
echo "=================================="
echo "Test Summary"
echo "=================================="
