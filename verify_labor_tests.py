#!/usr/bin/env python
"""
Verification script for labor calendar regression tests.

This script imports and validates the test module to ensure all tests
are properly structured and can be discovered by pytest.
"""

import sys
import importlib.util
from pathlib import Path

def load_test_module():
    """Load the test module dynamically."""
    test_file = Path("/home/sverzijl/planning_latest/tests/test_planning_ui_labor_calendar.py")

    spec = importlib.util.spec_from_file_location("test_module", test_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module

def count_tests(module):
    """Count test methods in the module."""
    test_count = 0
    test_classes = []

    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and name.startswith('Test'):
            test_classes.append(name)
            class_test_count = len([m for m in dir(obj) if m.startswith('test_')])
            test_count += class_test_count
            print(f"  {name}: {class_test_count} tests")

    return test_count, test_classes

def verify_imports():
    """Verify all necessary imports are available."""
    print("Verifying imports...")
    try:
        from src.models.labor_calendar import LaborCalendar, LaborDay
        print("  ✓ src.models.labor_calendar imports successful")

        import pytest
        print("  ✓ pytest available")

        from datetime import date, timedelta
        print("  ✓ datetime imports successful")

        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

def main():
    """Main verification routine."""
    print("=" * 60)
    print("Labor Calendar Regression Test Verification")
    print("=" * 60)
    print()

    # Verify imports
    if not verify_imports():
        print("\n❌ Import verification failed!")
        sys.exit(1)

    print()

    # Load and analyze test module
    print("Loading test module...")
    try:
        module = load_test_module()
        print("  ✓ Test module loaded successfully")
    except Exception as e:
        print(f"  ✗ Failed to load test module: {e}")
        sys.exit(1)

    print()

    # Count tests
    print("Test classes and methods:")
    test_count, test_classes = count_tests(module)

    print()
    print("=" * 60)
    print(f"Total test classes: {len(test_classes)}")
    print(f"Total test methods: {test_count}")
    print()
    print("Test classes:")
    for cls in test_classes:
        print(f"  - {cls}")
    print()

    # Verify expected test structure
    expected_classes = [
        'TestLaborCalendarAttributes',
        'TestLaborCalendarMaxDateCalculation',
        'TestLaborCalendarEmptyHandling',
        'TestLaborCalendarNoneHandling',
        'TestPlanningHorizonCoverage',
        'TestLaborCalendarIntegration'
    ]

    print("Verifying expected test classes...")
    all_present = True
    for expected in expected_classes:
        if expected in test_classes:
            print(f"  ✓ {expected}")
        else:
            print(f"  ✗ {expected} (MISSING)")
            all_present = False

    print()

    if all_present and test_count >= 6:
        print("✅ All verification checks passed!")
        print(f"   {test_count} test methods ready to run")
        print()
        print("To run the tests, execute:")
        print("  python -m pytest tests/test_planning_ui_labor_calendar.py -v")
    else:
        print("❌ Verification failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
